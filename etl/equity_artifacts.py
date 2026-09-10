"""
Unattended build-integration for equity-attributable production (spec
section 15.8 steps 5-6, restricted to the approved publication window).

Orchestrates: fetch -> parse -> match -> full historical resolve ->
restrict to the approved publication window (>= EQUITY_PUBLICATION_START)
-> validate -> build deterministic docs/data/equity/* artifacts. Called
from etl/build.py's main(), inside the same try block as the production
pipeline, so an equity failure fails the whole build and leaves
docs/data/ untouched (no equity artifacts are written until every check
below has passed).

This module writes NOTHING to disk itself except via the atomic
write_equity_artifacts() call at the very end of the pipeline, mirroring
etl/build.py's own "compute everything, validate everything, THEN write
everything" shape.

Policy constants (fixed start date, coverage thresholds) come from
etl/equity_config.py and are never duplicated here or in JavaScript -
this module reads them from that one place and writes them into
equity/meta.json so a future frontend can read the policy from data.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from equity_config import (  # noqa: E402
    EQUITY_METHODOLOGY_VERSION,
    EQUITY_MINIMUM_COVERAGE_PCT,
    EQUITY_PUBLICATION_START,
    EQUITY_ROW_COUNT_TOLERANCE_FRACTION,
    EQUITY_WARNING_COVERAGE_PCT,
)
from equity_fetch import EquityFetchError, fetch_equity_workbook  # noqa: E402
from equity_interval_diagnostics import classify_zero_duration_rows, load_raw_rows  # noqa: E402
from equity_join import build_field_match_index  # noqa: E402
from equity_join_historical import (  # noqa: E402
    build_resolved_grain_rows_historical,
    check_e1_historical,
    check_e4_historical,
    check_e5_historical,
    check_e7_historical,
    check_e8_historical,
    resolve_full_history,
)
from equity_match import (  # noqa: E402
    FIELD_ALIASES_PATH,
    PRODUCTION_STREAMS,
    load_field_aliases,
    match_fields,
)
from equity_mboed import (  # noqa: E402
    DERIVED_STREAMS,
    build_derived_status_by_period,
    derive_company_period_value,
)
from equity_parse import EquityParseError, parse_equity_workbook  # noqa: E402
from equity_publication_window import build_monthly_stream_data, coverage_pct  # noqa: E402
from mboed import round_mboed  # noqa: E402
from production_config import GAS_SCF_PER_BOE, PRODUCTION_CONVERSION_METHODOLOGY  # noqa: E402
from transform import round3, slugify  # noqa: E402

CACHE_DIR = Path(__file__).parent / ".cache"
WORKBOOK_CACHE_PATH = CACHE_DIR / "equity_workbook.xlsx"

SOURCE_ITEM_TITLE_EXPECTED = "Field Partners"


class EquityBuildError(RuntimeError):
    """Equity pipeline failure. Caught by etl/build.py's main() alongside
    the production pipeline's own exceptions, so the whole build fails
    and docs/data/ is left untouched."""


# ---------------------------------------------------------------------------
# In-memory adapters: build.py has already computed history_per_slug /
# history_index in memory (they are about to be written to
# docs/data/history/*) - these adapt that shape into what the equity
# resolver needs, without any disk I/O of their own.
# ---------------------------------------------------------------------------


def pprs_field_universe_from_history_index(history_index: dict) -> set[str]:
    return {entry["field"] for entry in history_index.values()}


def pprs_history_production_from_history(history_per_slug: dict, history_index: dict) -> dict[str, list[dict]]:
    result = {}
    for slug, entry in history_index.items():
        field_name = entry["field"]
        series = history_per_slug[slug]["series"]
        points = []
        for point in series:
            points.append(
                {
                    "period": point["period"],
                    "month_start": date(int(point["period"][:4]), int(point["period"][4:6]), 1),
                    "oil_mbd": point["oil_mbd"],
                    "dry_gas_mmscfd": point["dry_gas_mmscfd"],
                    "assoc_gas_mmscfd": point["assoc_gas_mmscfd"],
                    "condensate_mbd": point["condensate_mbd"],
                }
            )
        points.sort(key=lambda p: p["period"])
        result[field_name] = points
    return result


# ---------------------------------------------------------------------------
# Source integrity
# ---------------------------------------------------------------------------


def fetch_and_validate_source(session, previous_equity_meta: dict | None) -> dict:
    try:
        fetch_result = fetch_equity_workbook(session=session)
    except EquityFetchError as e:
        raise EquityBuildError(f"Equity source fetch failed: {e}") from e

    if fetch_result["resolved_item_title"] != SOURCE_ITEM_TITLE_EXPECTED:
        raise EquityBuildError(
            f"Equity source item title changed from the expected "
            f"{SOURCE_ITEM_TITLE_EXPECTED!r} to "
            f"{fetch_result['resolved_item_title']!r}. This is exactly the kind "
            "of unhandled source-structure change spec section 15.11's "
            "validation table requires to fail the build, not pass silently."
        )

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    WORKBOOK_CACHE_PATH.write_bytes(fetch_result["content"])

    try:
        rows = parse_equity_workbook(WORKBOOK_CACHE_PATH)
    except EquityParseError as e:
        raise EquityBuildError(f"Equity workbook parse failed: {e}") from e
    if not rows:
        raise EquityBuildError("Equity workbook parsed to zero rows.")

    raw_rows = load_raw_rows(WORKBOOK_CACHE_PATH)

    if previous_equity_meta is not None:
        previous_count = previous_equity_meta.get("normalized_equity_row_count")
        if previous_count:
            change = abs(len(raw_rows) - previous_count) / previous_count
            if change > EQUITY_ROW_COUNT_TOLERANCE_FRACTION:
                raise EquityBuildError(
                    f"Normalized equity row count changed from {previous_count} to "
                    f"{len(raw_rows)} ({change:.1%}), beyond the documented tolerance "
                    f"of {EQUITY_ROW_COUNT_TOLERANCE_FRACTION:.0%}. This is treated as "
                    "a likely structural change in the source, not organic growth - "
                    "failing loudly rather than silently absorbing it."
                )

    return {"fetch_result": fetch_result, "rows": rows, "raw_rows": raw_rows}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_equity_pipeline(
    history_per_slug: dict,
    history_index: dict,
    session,
    previous_equity_meta: dict | None = None,
    today_month_start: date = date(2026, 9, 1),
) -> dict:
    source = fetch_and_validate_source(session, previous_equity_meta)
    fetch_result = source["fetch_result"]
    raw_rows = source["raw_rows"]

    pprs_fields = pprs_field_universe_from_history_index(history_index)
    pprs_history = pprs_history_production_from_history(history_per_slug, history_index)
    equity_fields = {r["field_name"] for r in raw_rows}
    aliases = load_field_aliases(FIELD_ALIASES_PATH)

    match_result = match_fields(pprs_fields, equity_fields, aliases)
    field_match_index = build_field_match_index(pprs_fields, equity_fields, aliases)

    raw_rows_by_equity_field: dict[str, list[dict]] = defaultdict(list)
    for r in raw_rows:
        raw_rows_by_equity_field[r["field_name"]].append(r)

    per_field_month = resolve_full_history(pprs_history, field_match_index, raw_rows_by_equity_field, today_month_start)

    published = {(f, p): e for (f, p), e in per_field_month.items() if p >= EQUITY_PUBLICATION_START}
    if not published:
        raise EquityBuildError(
            f"No field-months at or after the publication start "
            f"{EQUITY_PUBLICATION_START} were found in the resolved history. "
            "Refusing to publish an empty equity dataset."
        )

    resolved_rows = build_resolved_grain_rows_historical(published)

    # --- Validation (build-breaking, spec section 15.11) ---
    e1 = check_e1_historical(published)
    if e1["below_100_count"] or e1["above_100_count"]:
        raise EquityBuildError(
            f"E1 failed within the published window: {e1['below_100_count']} "
            f"below-100% and {e1['above_100_count']} above-100% field-months. "
            f"Examples: {e1['below_100_examples'][:5]} {e1['above_100_examples'][:5]}"
        )

    e4 = check_e4_historical(published)
    # Quarantine is not build-breaking BY ITSELF: build_resolved_grain_rows_historical
    # only ever includes category == "resolved" rows (see its own source), which is
    # the structural proof required by spec section 15.11 that no quarantined value
    # can enter a published total. It is still required to be complete in
    # anomalies.json - see build_equity_artifacts below.
    quarantined_field_names = {c["field"] for c in e4["cases"]}
    if any(r["field_name"] in quarantined_field_names for r in resolved_rows):
        raise EquityBuildError(
            "INTERNAL INVARIANT VIOLATED: a quarantined field appears in "
            "resolved_rows. Refusing to publish - this should be structurally "
            "impossible and indicates a bug in the resolver, not a data issue."
        )

    e5 = check_e5_historical(published)
    total_categorised = sum(e5.values())
    if total_categorised != len(published):
        raise EquityBuildError(
            f"E5 category counts ({total_categorised}) do not sum to the "
            f"published field-month count ({len(published)}) - at least one "
            "field-month is missing a resolution category."
        )

    e7 = check_e7_historical(raw_rows)
    if not e7["passed"]:
        raise EquityBuildError(f"E7 failed: {len(e7['start_after_end_violations'])} rows with start_date > end_date: {e7['start_after_end_violations']}")

    e8 = check_e8_historical(published, resolved_rows)
    if not e8["passed"]:
        raise EquityBuildError(f"E8 failed for {len(e8['failures'])} (period, stream) pairs: {e8['failures'][:10]}")

    monthly_data = build_monthly_stream_data(published)
    for period in monthly_data:
        if period < EQUITY_PUBLICATION_START:
            raise EquityBuildError(
                f"INTERNAL INVARIANT VIOLATED: period {period} precedes the "
                f"publication start {EQUITY_PUBLICATION_START} but appears in "
                "the coverage data considered for publication."
            )

    return {
        "fetch_result": fetch_result,
        "raw_rows": raw_rows,
        "raw_rows_by_equity_field": dict(raw_rows_by_equity_field),
        "field_match_index": field_match_index,
        "match_result": match_result,
        "per_field_month": per_field_month,
        "published": published,
        "resolved_rows": resolved_rows,
        "monthly_data": monthly_data,
        "e1": e1,
        "e4": e4,
        "e5": e5,
        "e7": e7,
        "e8": e8,
        "zero_duration_classification": classify_zero_duration_rows(raw_rows),
    }


# ---------------------------------------------------------------------------
# Publication status classification
# ---------------------------------------------------------------------------


def classify_stream_month(monthly_data: dict, period: str, stream: str) -> dict:
    c = coverage_pct(monthly_data[period][stream])
    if c is None:
        return {"status": "unavailable", "coverage_pct": None, "value_available": False}
    if c < EQUITY_MINIMUM_COVERAGE_PCT:
        by_cat = monthly_data[period][stream]["by_category"]
        dominant = max(by_cat.items(), key=lambda kv: kv[1])[0] if by_cat else "unknown"
        return {"status": "unavailable", "coverage_pct": c, "value_available": False, "dominant_exclusion_category": dominant}
    status = "complete" if c >= EQUITY_WARNING_COVERAGE_PCT else "warning"
    return {"status": status, "coverage_pct": c, "value_available": True}


def build_publication_status_by_period_stream(monthly_data: dict) -> dict[str, dict[str, dict]]:
    return {period: {stream: classify_stream_month(monthly_data, period, stream) for stream in PRODUCTION_STREAMS} for period in sorted(monthly_data)}


# ---------------------------------------------------------------------------
# Artifact construction
# ---------------------------------------------------------------------------


def build_company_artifacts(
    resolved_rows: list[dict],
    status_by_period_stream: dict,
    derived_status_by_period: dict,
) -> dict[str, dict]:
    """{company_name: doc}. Only PUBLISHED (status.value_available) values
    are ever non-null - never zero as a substitute for unavailable.

    derived_status_by_period (equity_mboed.build_derived_status_by_period)
    supplies the period-wide liquids_mboed/natural_gas_mboed/total_mboed
    status entries (spec section 17) - each company's own derived VALUE is
    computed here from this company's own included native volumes
    (by_company_period), never by re-deriving from another company's
    figures or from the period-wide aggregate."""
    by_company_period: dict[tuple[str, str], dict] = defaultdict(lambda: {s: 0.0 for s in PRODUCTION_STREAMS})
    fields_by_company: dict[str, set] = defaultdict(set)
    for r in resolved_rows:
        key = (r["company_name"], r["period"])
        for stream in PRODUCTION_STREAMS:
            by_company_period[key][stream] += r[stream]
        fields_by_company[r["company_name"]].add(r["field_name"])

    periods_by_company: dict[str, set] = defaultdict(set)
    for company, period in by_company_period:
        periods_by_company[company].add(period)

    docs = {}
    for company, periods in periods_by_company.items():
        sorted_periods = sorted(periods)
        series = []
        for period in sorted_periods:
            entry = {"period": period}
            for stream in PRODUCTION_STREAMS:
                s = status_by_period_stream[period][stream]
                value = round3(by_company_period[(company, period)][stream]) if s["value_available"] else None
                entry[stream] = {"value": value, "status": s["status"], "coverage_pct": s["coverage_pct"]}

            company_totals = by_company_period[(company, period)]
            derived_status = derived_status_by_period[period]

            liquids_status = derived_status["liquids_mboed"]
            liquids_value = derive_company_period_value(
                liquids_status, company_totals["oil_mbd"], company_totals["condensate_mbd"], is_gas=False
            )
            entry["liquids_mboed"] = {
                "value": round_mboed(liquids_value),
                "status": liquids_status["status"],
                "coverage_pct": liquids_status["coverage_pct"],
            }

            gas_status = derived_status["natural_gas_mboed"]
            gas_value = derive_company_period_value(
                gas_status, company_totals["dry_gas_mmscfd"], company_totals["assoc_gas_mmscfd"], is_gas=True
            )
            entry["natural_gas_mboed"] = {
                "value": round_mboed(gas_value),
                "status": gas_status["status"],
                "coverage_pct": gas_status["coverage_pct"],
            }

            total_status = derived_status["total_mboed"]
            # Component-gated (spec section 17/4): the total VALUE is
            # None iff either component's own derived value is None (i.e.
            # iff that component was genuinely "unavailable") - a
            # "not_applicable" component contributes a real 0.0, never
            # turns the total into a silent None.
            total_value = None if (liquids_value is None or gas_value is None) else liquids_value + gas_value
            entry["total_mboed"] = {
                "value": round_mboed(total_value),
                "status": total_status["status"],
                "total_coverage_pct": total_status["total_coverage_pct"],
            }

            series.append(entry)

        docs[company] = {
            "slug": slugify(company),
            "name": company,
            "label": "Legal entity as recorded by NSTA",
            "first_published_period": sorted_periods[0],
            "last_published_period": sorted_periods[-1],
            "field_count": len(fields_by_company[company]),
            "fields": sorted(slugify(f) for f in fields_by_company[company]),
            "series": series,
        }
    return docs


def build_field_artifacts(
    field_match_index: dict[str, tuple[str, str]],
    raw_rows_by_equity_field: dict[str, list[dict]],
    published: dict,
) -> dict[str, dict]:
    """{pprs_field_name: doc}. One doc per PPRS field that matched an
    equity field name - unmatched fields are not represented here (they
    are in anomalies.json instead)."""
    resolution_by_field: dict[str, dict[str, str]] = defaultdict(dict)
    for (field, period), entry in published.items():
        resolution_by_field[field][period] = entry["category"]

    docs = {}
    for field, (equity_field, method) in field_match_index.items():
        if field not in resolution_by_field:
            continue  # matched but has no published-window field-months at all
        rows = raw_rows_by_equity_field.get(equity_field, [])
        docs[field] = {
            "slug": slugify(field),
            "field_name": field,
            "equity_field_name": equity_field,
            "field_match_method": method,
            "ownership_intervals": [
                {
                    "company_name": r["company_name"],
                    "interest_pct": r["interest_pct"],
                    "start_date": r["start_date"],
                    "end_date": r["end_date"],
                    "operator_flag": r["operator_flag"],
                    "status": r["status"],
                }
                for r in sorted(rows, key=lambda r: (r["company_name"], r["start_date"]))
            ],
            "resolution_status_by_period": dict(sorted(resolution_by_field[field].items())),
            "excluded_periods": sorted(p for p, cat in resolution_by_field[field].items() if cat != "resolved"),
        }
    return docs


def build_index(company_docs: dict[str, dict]) -> dict:
    index = {}
    for company, doc in sorted(company_docs.items()):
        latest_period = doc["last_published_period"]
        latest_entry = next(e for e in doc["series"] if e["period"] == latest_period)
        index[doc["slug"]] = {
            "name": doc["name"],
            "first_published_period": doc["first_published_period"],
            "last_published_period": doc["last_published_period"],
            "field_count": doc["field_count"],
            "latest_production": {
                stream: latest_entry[stream]["value"] for stream in list(PRODUCTION_STREAMS) + list(DERIVED_STREAMS)
            },
            "latest_coverage_status": {
                stream: latest_entry[stream]["status"] for stream in list(PRODUCTION_STREAMS) + list(DERIVED_STREAMS)
            },
        }
    return index


def build_anomalies(pipeline_result: dict, murlach_field_name: str = "MURLACH [pt of MARNOCK-SKUA]") -> dict:
    published = pipeline_result["published"]
    monthly_data = pipeline_result["monthly_data"]
    status_by_period_stream = build_publication_status_by_period_stream(monthly_data)

    murlach_entries = [
        {
            "period": p,
            "category": e["category"],
            "production": {k: v for k, v in e["production"].items() if k != "month_start"},
        }
        for (f, p), e in published.items()
        if f == murlach_field_name
    ]

    future_only = [{"field": f, "period": p} for (f, p), e in published.items() if e["category"] == "future_only"]
    quarantined = pipeline_result["e4"]["cases"]
    unresolved_gap = [{"field": f, "period": p} for (f, p), e in published.items() if e["category"] in ("e1_sum_mismatch", "genuine_interval_gap", "no_equity_history")]
    unmatched = pipeline_result["match_result"]["unmatched_pprs"]

    below_threshold = []
    for period, streams in status_by_period_stream.items():
        for stream, s in streams.items():
            if s["status"] == "unavailable":
                below_threshold.append({"period": period, "stream": stream, "coverage_pct": s["coverage_pct"], "dominant_exclusion_category": s.get("dominant_exclusion_category")})

    e7 = pipeline_result["e7"]

    return {
        "murlach": {
            "field_name": murlach_field_name,
            "status": "future_only_unresolved",
            "note": "Ownership of MARNOCK, SKUA or any related grouping was NOT applied. See UKCS_DESIGN_v2.md section 15.11.",
            "published_window_entries": murlach_entries,
        },
        "future_only_fields": future_only,
        "quarantined_overlaps": quarantined,
        "unresolved_gaps": unresolved_gap,
        "unmatched_fields": unmatched,
        "below_threshold_stream_months": below_threshold,
        "start_after_end_violations": e7["start_after_end_violations"],
        "zero_duration_classification": pipeline_result["zero_duration_classification"]["category_counts"],
    }


def build_meta(pipeline_result: dict, company_docs: dict, field_docs: dict, build_timestamp: str) -> dict:
    fetch_result = pipeline_result["fetch_result"]
    published = pipeline_result["published"]
    periods = sorted({p for (f, p) in published})
    return {
        "publication_start": EQUITY_PUBLICATION_START,
        "minimum_coverage_pct": EQUITY_MINIMUM_COVERAGE_PCT,
        "warning_coverage_pct": EQUITY_WARNING_COVERAGE_PCT,
        "earliest_published_period": periods[0],
        "latest_published_period": periods[-1],
        "source_item_title": fetch_result["resolved_item_title"],
        "source_page_description": fetch_result["source_page_description"],
        "resolved_workbook_url": fetch_result["resolved_url"],
        "last_modified": fetch_result["last_modified"],
        "sha256": fetch_result["sha256"],
        "normalized_equity_row_count": len(pipeline_result["raw_rows"]),
        "matched_field_count": len(pipeline_result["match_result"]["exact_matches"]) + len(pipeline_result["match_result"]["normalized_matches"]) + len(pipeline_result["match_result"]["alias_matches"]),
        "unmatched_field_count": len(pipeline_result["match_result"]["unmatched_pprs"]),
        "legal_entity_count": len(company_docs),
        "built_at": build_timestamp,
        "methodology_version": EQUITY_METHODOLOGY_VERSION,
        "production_conversion_methodology": PRODUCTION_CONVERSION_METHODOLOGY,
        "gas_scf_per_boe": GAS_SCF_PER_BOE,
        "source_limitations": [
            "Equity coverage before 2013-03 is structurally incomplete in the source workbook and "
            "is not published - see UKCS_DESIGN_v2.md section 15.10/15.11.",
            "MURLACH [pt of MARNOCK-SKUA] is excluded from equity-attributable totals: its only "
            "recorded equity rows have an unexplained 2050-01-04 start date. See anomalies.json.",
            "Equity-attributable production is a gross equity share of reported field production, "
            "not net, entitlement or accounting production.",
            "Internally consistent but incomplete source data may not be independently detectable "
            "by this pipeline's checks - see README.md's known-limitation note.",
            "liquids_mboed/natural_gas_mboed/total_mboed are ETL-derived analytical measures "
            "(natural gas converted at 6,000 scf/boe, a conventional energy-equivalence factor, "
            "not measured calorific value) - NSTA does not publish these directly. See "
            "methodology.html.",
        ],
        "murlach_unresolved": True,
    }


# ---------------------------------------------------------------------------
# Atomic write (mirrors etl/build.py's write_history_dir_atomic pattern)
# ---------------------------------------------------------------------------


def _json_text(data: object) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def write_equity_artifacts(
    equity_dir: Path,
    meta: dict,
    index: dict,
    company_docs: dict,
    field_docs: dict,
    anomalies: dict,
    group_docs: dict | None = None,
    groups_report: dict | None = None,
    groups_mapping: list[dict] | None = None,
) -> None:
    staging_dir = equity_dir.with_name(equity_dir.name + ".tmp")
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    (staging_dir / "companies").mkdir(parents=True)
    (staging_dir / "fields").mkdir(parents=True)

    (staging_dir / "meta.json").write_text(_json_text(meta), encoding="utf-8")
    (staging_dir / "index.json").write_text(_json_text(index), encoding="utf-8")
    (staging_dir / "anomalies.json").write_text(_json_text(anomalies), encoding="utf-8")

    for company, doc in company_docs.items():
        (staging_dir / "companies" / f"{doc['slug']}.json").write_text(_json_text(doc), encoding="utf-8")
    for field, doc in field_docs.items():
        (staging_dir / "fields" / f"{doc['slug']}.json").write_text(_json_text(doc), encoding="utf-8")

    # Company grouping (Workstream 1, spec approved 2026-09-10) - written
    # into the SAME atomic staging directory as every other equity
    # artifact above, so a company-group publish can never land
    # inconsistently with the legal-entity artifacts it was derived from
    # (one staging dir, one atomic rename, all-or-nothing).
    if group_docs is not None:
        (staging_dir / "groups").mkdir(parents=True)
        group_index = {
            doc["slug"]: {
                "name": doc["name"],
                "member_entities": doc["member_entities"],
                "is_singleton": doc["is_singleton"],
            }
            for doc in group_docs.values()
        }
        (staging_dir / "groups" / "index.json").write_text(_json_text(group_index), encoding="utf-8")
        (staging_dir / "groups" / "report.json").write_text(_json_text(groups_report), encoding="utf-8")
        (staging_dir / "groups" / "mapping.json").write_text(_json_text(groups_mapping), encoding="utf-8")
        for doc in group_docs.values():
            (staging_dir / "groups" / f"{doc['slug']}.json").write_text(_json_text(doc), encoding="utf-8")

    if equity_dir.exists():
        shutil.rmtree(equity_dir)
    staging_dir.rename(equity_dir)
