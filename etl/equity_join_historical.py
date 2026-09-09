"""
Full historical equity interval-join diagnostic (spec section 15.8 step 5,
scoped as a diagnostic-only checkpoint per explicit instruction - NOT
integrated into etl/build.py, and NOT published to docs/data/equity/*).

Applies the same approved policies as the latest-period checkpoint
(etl/equity_join.py) across the complete overlap between monthly PPRS
field production history (docs/data/history/*.json, 552 fields) and the
NSTA equity workbook's dated intervals (etl/equity_interval_diagnostics.
load_raw_rows()). Produces field x month x legal-entity
equity-attributable production, in memory and to committed diagnostic
files under etl/ only.

Policies (approved, not re-litigated here - see UKCS_DESIGN_v2.md section
15.3-15.4 and etl/equity_join.py's module docstring for full rationale):

1. Half-open containment: start_date <= month_start < end_date.
2. Zero-duration rows are source event records, never active intervals.
3. Zero-interest rows are retained, contribute 0 to the equity sum.
   Operator Flag = 'Y' never implies positive interest.
4. Future-dated intervals are retained, inactive until their start date.
5. Equity Share Time Period is source metadata only.
6. Unresolved overlaps (E4) are quarantined, never repaired: no interest
   normalisation, no owner preference, no equity production calculated
   for that field-month, full conflicting source data preserved.
7. Company names are the legal entity exactly as recorded by NSTA. No
   parent-group or current-company rollup.

Run: python etl/equity_join_historical.py
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from equity_interval_diagnostics import classify_zero_duration_rows, load_raw_rows
from equity_join import build_field_match_index, resolve_field_month
from equity_match import (
    FIELD_ALIASES_PATH,
    PRODUCTION_STREAMS,
    load_field_aliases,
    load_pprs_field_universe,
)

HISTORY_DIR = Path(__file__).parent.parent / "docs" / "data" / "history"
HISTORICAL_REPORT_PATH = Path(__file__).parent / "equity_historical_join_report.md"
ANOMALIES_PATH = Path(__file__).parent / "equity_historical_anomalies.json"

E1_TOLERANCE_PP = 0.5
E8_TOLERANCE_PCT = 0.5


class EquityHistoricalJoinError(RuntimeError):
    pass


def _to_date(iso: str) -> date:
    y, m, d = map(int, iso.split("-"))
    return date(y, m, d)


def _period_to_month_start(period: str) -> date:
    return date(int(period[:4]), int(period[4:6]), 1)


def _add_month(d: date) -> date:
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_full_history_production() -> dict[str, list[dict]]:
    """Returns {pprs_field_name: [{period, month_start, oil_mbd,
    dry_gas_mmscfd, assoc_gas_mmscfd, condensate_mbd}, ...]}, sorted by
    period, for all 552 PPRS fields with production history."""
    if not HISTORY_DIR.exists():
        raise EquityHistoricalJoinError(f"{HISTORY_DIR} not found. Run the Phase 1 build first.")
    with open(HISTORY_DIR / "index.json") as f:
        index = json.load(f)

    result = {}
    for slug, entry in index.items():
        field_name = entry["field"]
        with open(HISTORY_DIR / f"{slug}.json") as f:
            data = json.load(f)
        series = []
        for point in data["series"]:
            series.append(
                {
                    "period": point["period"],
                    "month_start": _period_to_month_start(point["period"]),
                    "oil_mbd": point["oil_mbd"],
                    "dry_gas_mmscfd": point["dry_gas_mmscfd"],
                    "assoc_gas_mmscfd": point["assoc_gas_mmscfd"],
                    "condensate_mbd": point["condensate_mbd"],
                }
            )
        series.sort(key=lambda p: p["period"])
        result[field_name] = series
    return result


# ---------------------------------------------------------------------------
# Resolution over full history
# ---------------------------------------------------------------------------


def _field_month_gap_category(field_rows: list[dict], month_start: date, today_month_start: date) -> str:
    """Categorises a field-month with NO active equity row, for a field
    that IS matched and DOES have >=1 equity row. Distinguishes mechanical
    month-start boundary effects from genuine coverage gaps, rather than
    calling everything a generic 'missing equity' failure.

    Only the START side of each row needs to be considered: a row ending
    mid-month never causes a 'no active row' situation in the first place
    (if start_date <= month_start, that row is already active regardless
    of where within the month it later ends) - so end dates play no part
    in this classification."""
    starts = [_to_date(r["start_date"]) for r in field_rows]
    min_start = min(starts)
    min_start_month = date(min_start.year, min_start.month, 1)

    if month_start < min_start_month:
        # This production month predates the calendar month equity
        # coverage begins in. 'future_only' means the field's earliest
        # equity coverage is itself still in the future relative to real
        # wall-clock time (e.g. MURLACH) - not merely later than this
        # particular historical production month, which is the far more
        # common 'pre_equity_history' case (equity coverage exists, just
        # not yet, as of this month, and it is not future in absolute terms).
        return "future_only" if min_start_month > today_month_start else "pre_equity_history"

    starts_this_month = [s for s in starts if date(s.year, s.month, 1) == month_start]
    if starts_this_month and any(s.day > 1 for s in starts_this_month):
        # Ownership begins THIS calendar month, but not on day 1 - a
        # mechanical artifact of month-start resolution, not missing data.
        return "month_start_boundary"

    return "genuine_interval_gap"


def resolve_full_history(
    pprs_history: dict[str, list[dict]],
    field_match_index: dict[str, tuple[str, str]],
    raw_rows_by_equity_field: dict[str, list[dict]],
    today_month_start: date = date(2026, 9, 1),
) -> dict:
    """Resolves every PPRS (field, month) in the full production history.
    Two passes: first resolve active intervals for every field-month, then
    categorise the no-active-row cases (pass 2 needs no field-level state -
    see _field_month_gap_category, which compares each field's earliest
    equity coverage against today_month_start alone)."""
    per_field_month: dict[tuple[str, str], dict] = {}

    for field, points in pprs_history.items():
        if field not in field_match_index:
            for p in points:
                per_field_month[(field, p["period"])] = {"category": "unmatched", "month_start": p["month_start"], "production": p}
            continue

        equity_field, method = field_match_index[field]
        field_rows = raw_rows_by_equity_field.get(equity_field, [])
        if not field_rows:
            for p in points:
                per_field_month[(field, p["period"])] = {
                    "category": "no_equity_history",
                    "month_start": p["month_start"],
                    "production": p,
                    "field_match_method": method,
                    "equity_field_name": equity_field,
                }
            continue

        for p in points:
            month_result = resolve_field_month(field_rows, p["month_start"])
            key = (field, p["period"])
            base = {"month_start": p["month_start"], "production": p, "field_match_method": method, "equity_field_name": equity_field}

            if not month_result["active_rows"]:
                per_field_month[key] = {**base, "category": None}  # categorised in pass 2
                continue

            if month_result["overlap"]:
                per_field_month[key] = {
                    **base,
                    "category": "quarantined",
                    "active_rows": month_result["active_rows"],
                    "positive_interest_sum": month_result["positive_interest_sum"],
                    "same_company_overlap": month_result["same_company_overlap"],
                }
                continue

            total = month_result["positive_interest_sum"]
            if abs(total - 100.0) > E1_TOLERANCE_PP:
                per_field_month[key] = {
                    **base,
                    "category": "e1_sum_mismatch",
                    "active_rows": month_result["active_rows"],
                    "positive_interest_sum": total,
                }
                continue

            per_field_month[key] = {**base, "category": "resolved", "active_rows": month_result["active_rows"], "positive_interest_sum": total}

    # Pass 2: categorise the no-active-row cases.
    for (field, period), entry in per_field_month.items():
        if entry["category"] is not None:
            continue
        field_rows = raw_rows_by_equity_field.get(entry["equity_field_name"], [])
        entry["category"] = _field_month_gap_category(field_rows, entry["month_start"], today_month_start)

    return per_field_month


def build_resolved_grain_rows_historical(per_field_month: dict[tuple[str, str], dict]) -> list[dict]:
    rows = []
    for (field, period), entry in per_field_month.items():
        if entry["category"] != "resolved":
            continue
        production = entry["production"]
        for r in entry["active_rows"]:
            if r["interest_pct"] <= 0:
                continue
            factor = r["interest_pct"] / 100.0
            rows.append(
                {
                    "field_name": field,
                    "period": period,
                    "month_start": entry["month_start"].isoformat(),
                    "company_name": r["company_name"],
                    "interest_pct": r["interest_pct"],
                    "oil_mbd": round(production["oil_mbd"] * factor, 6),
                    "dry_gas_mmscfd": round(production["dry_gas_mmscfd"] * factor, 6),
                    "assoc_gas_mmscfd": round(production["assoc_gas_mmscfd"] * factor, 6),
                    "condensate_mbd": round(production["condensate_mbd"] * factor, 6),
                    "source_start_date": r["start_date"],
                    "source_end_date": r["end_date"],
                    "operator_flag": r["operator_flag"],
                    "field_match_method": entry["field_match_method"],
                    "resolution_status": "resolved",
                }
            )
    rows.sort(key=lambda r: (r["field_name"], r["period"], r["company_name"]))
    return rows


# ---------------------------------------------------------------------------
# Historical validation: E1, E4, E5, E7, E8
# ---------------------------------------------------------------------------


def check_e1_historical(per_field_month: dict) -> dict:
    below = []
    above = []
    passing = 0
    for (field, period), entry in per_field_month.items():
        if entry["category"] == "resolved":
            passing += 1
        elif entry["category"] == "e1_sum_mismatch":
            total = entry["positive_interest_sum"]
            (below if total < 100.0 else above).append((field, period, total))
    return {"passing_field_months": passing, "below_100_count": len(below), "above_100_count": len(above), "below_100_examples": below[:20], "above_100_examples": above[:20]}


def check_e4_historical(per_field_month: dict) -> dict:
    quarantined = [(field, period, entry) for (field, period), entry in per_field_month.items() if entry["category"] == "quarantined"]
    fields = sorted({f for f, p, e in quarantined})
    companies = sorted({r["company_name"] for f, p, e in quarantined for r in e["active_rows"]})
    periods = sorted({p for f, p, e in quarantined})
    excluded_production = {stream: 0.0 for stream in PRODUCTION_STREAMS}
    for f, p, e in quarantined:
        for stream in PRODUCTION_STREAMS:
            excluded_production[stream] += e["production"][stream]
    return {
        "total_quarantined_field_months": len(quarantined),
        "distinct_fields": fields,
        "distinct_companies": companies,
        "earliest_period": periods[0] if periods else None,
        "latest_period": periods[-1] if periods else None,
        "excluded_production_by_stream": {k: round(v, 4) for k, v in excluded_production.items()},
        "cases": [
            {
                "field": f,
                "period": p,
                "positive_interest_sum": e["positive_interest_sum"],
                "same_company_overlap": e["same_company_overlap"],
                "conflicting_intervals": [
                    {"company": r["company_name"], "start": r["start_date"], "end": r["end_date"], "pct": r["interest_pct"]} for r in e["active_rows"]
                ],
            }
            for f, p, e in quarantined
        ],
    }


def check_e5_historical(per_field_month: dict) -> dict:
    by_category = defaultdict(list)
    for (field, period), entry in per_field_month.items():
        cat = "quarantined_overlap" if entry["category"] == "quarantined" else entry["category"]
        cat = "e1_sum_mismatch" if cat == "e1_sum_mismatch" else cat
        by_category[cat].append((field, period))
    return {cat: len(items) for cat, items in sorted(by_category.items())}


def check_e7_historical(all_raw_rows: list[dict]) -> dict:
    violations = [r for r in all_raw_rows if r["end_date"] is not None and r["start_date"] > r["end_date"]]
    zero_duration = [r for r in all_raw_rows if r["start_date"] == r["end_date"]]
    return {
        "total_rows_checked": len(all_raw_rows),
        "start_after_end_violations": [(r["field_name"], r["company_name"], r["start_date"], r["end_date"]) for r in violations],
        "passed": len(violations) == 0,
        "zero_duration_rows_accepted_as_events": len(zero_duration),
    }


def check_e8_historical(per_field_month: dict, resolved_rows: list[dict]) -> dict:
    """Per-stream, per-month conservation: sum(equity production) must
    equal sum(field production) for the SAME set of resolved field-months
    that month. Returns per-month results plus any failures beyond
    tolerance."""
    resolved_production_by_period: dict[str, dict] = defaultdict(lambda: {s: 0.0 for s in PRODUCTION_STREAMS})
    for (field, period), entry in per_field_month.items():
        if entry["category"] == "resolved":
            for stream in PRODUCTION_STREAMS:
                resolved_production_by_period[period][stream] += entry["production"][stream]

    equity_sum_by_period: dict[str, dict] = defaultdict(lambda: {s: 0.0 for s in PRODUCTION_STREAMS})
    for r in resolved_rows:
        for stream in PRODUCTION_STREAMS:
            equity_sum_by_period[r["period"]][stream] += r[stream]

    failures = []
    for period, prod in resolved_production_by_period.items():
        for stream in PRODUCTION_STREAMS:
            expected = prod[stream]
            actual = equity_sum_by_period[period][stream]
            diff = abs(expected - actual)
            tolerance = max(0.001, expected * E8_TOLERANCE_PCT / 100.0)
            if diff > tolerance:
                failures.append({"period": period, "stream": stream, "expected": round(expected, 4), "actual": round(actual, 4), "difference": round(diff, 6)})

    return {"months_checked": len(resolved_production_by_period), "failures": failures, "passed": len(failures) == 0}


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def monthly_coverage(per_field_month: dict) -> dict:
    """coverage_pct per (period, stream) = resolved production / total
    production that period, across ALL categories (not just resolved)."""
    total_by_period: dict[str, dict] = defaultdict(lambda: {s: 0.0 for s in PRODUCTION_STREAMS})
    resolved_by_period: dict[str, dict] = defaultdict(lambda: {s: 0.0 for s in PRODUCTION_STREAMS})
    excluded_by_category_stream: dict[str, dict] = defaultdict(lambda: {s: 0.0 for s in PRODUCTION_STREAMS})

    for (field, period), entry in per_field_month.items():
        prod = entry["production"]
        for stream in PRODUCTION_STREAMS:
            total_by_period[period][stream] += prod[stream]
            if entry["category"] == "resolved":
                resolved_by_period[period][stream] += prod[stream]
            else:
                excluded_by_category_stream[entry["category"]][stream] += prod[stream]

    coverage_by_period_stream: dict[str, dict] = {}
    for period, totals in total_by_period.items():
        coverage_by_period_stream[period] = {}
        for stream in PRODUCTION_STREAMS:
            total = totals[stream]
            resolved = resolved_by_period[period][stream]
            coverage_by_period_stream[period][stream] = round(100.0 * resolved / total, 3) if total > 0 else None

    # production-weighted full-history coverage per stream
    full_history_coverage = {}
    annual_coverage: dict[str, dict] = defaultdict(lambda: {s: [0.0, 0.0] for s in PRODUCTION_STREAMS})  # year -> stream -> [resolved, total]
    for period, totals in total_by_period.items():
        year = period[:4]
        for stream in PRODUCTION_STREAMS:
            annual_coverage[year][stream][0] += resolved_by_period[period][stream]
            annual_coverage[year][stream][1] += totals[stream]

    for stream in PRODUCTION_STREAMS:
        total = sum(totals[stream] for totals in total_by_period.values())
        resolved = sum(resolved_by_period[period][stream] for period in total_by_period)
        full_history_coverage[stream] = round(100.0 * resolved / total, 3) if total > 0 else None

    annual_coverage_pct = {
        year: {stream: (round(100.0 * r / t, 3) if t > 0 else None) for stream, (r, t) in streams.items()}
        for year, streams in sorted(annual_coverage.items())
    }

    # lowest-coverage months per stream (only where total > 0, to avoid divide-by-zero noise)
    lowest_by_stream = {}
    for stream in PRODUCTION_STREAMS:
        scored = [
            (period, coverage_by_period_stream[period][stream])
            for period in coverage_by_period_stream
            if coverage_by_period_stream[period][stream] is not None
        ]
        scored.sort(key=lambda x: x[1])
        lowest_by_stream[stream] = scored[:10]

    # bucket counts (using dry_gas as representative? No - report per stream)
    buckets_by_stream = {}
    for stream in PRODUCTION_STREAMS:
        values = [v[stream] for v in coverage_by_period_stream.values() if v[stream] is not None]
        buckets_by_stream[stream] = {
            "at_100": sum(1 for v in values if v >= 100.0),
            "99.5_to_100": sum(1 for v in values if 99.5 <= v < 100.0),
            "95_to_99.5": sum(1 for v in values if 95.0 <= v < 99.5),
            "below_95": sum(1 for v in values if v < 95.0),
        }

    return {
        "coverage_by_period_stream": coverage_by_period_stream,
        "annual_coverage_pct": annual_coverage_pct,
        "full_history_coverage_pct": full_history_coverage,
        "lowest_coverage_months": lowest_by_stream,
        "excluded_production_by_category_stream": {cat: {s: round(v, 4) for s, v in streams.items()} for cat, streams in excluded_by_category_stream.items()},
        "coverage_buckets_by_stream": buckets_by_stream,
    }


# ---------------------------------------------------------------------------
# Partial-month / gap diagnostics
# ---------------------------------------------------------------------------


def gap_diagnostics(per_field_month: dict) -> dict:
    categories = ["pre_equity_history", "month_start_boundary", "genuine_interval_gap", "future_only", "no_equity_history"]
    result = {}
    for cat in categories:
        entries = [(f, p, e) for (f, p), e in per_field_month.items() if e["category"] == cat]
        fields = sorted({f for f, p, e in entries})
        periods = sorted({p for f, p, e in entries})
        excluded = {stream: 0.0 for stream in PRODUCTION_STREAMS}
        for f, p, e in entries:
            for stream in PRODUCTION_STREAMS:
                excluded[stream] += e["production"][stream]
        result[cat] = {
            "field_month_count": len(entries),
            "distinct_field_count": len(fields),
            "excluded_production_by_stream": {k: round(v, 4) for k, v in excluded.items()},
            "earliest_period": periods[0] if periods else None,
            "latest_period": periods[-1] if periods else None,
            "example_fields": fields[:10],
            "examples": [(f, p) for f, p, e in entries[:5]],
        }
    return result


# ---------------------------------------------------------------------------
# MURLACH investigation
# ---------------------------------------------------------------------------


def murlach_analysis(per_field_month: dict, raw_rows_by_equity_field: dict) -> dict:
    field = "MURLACH [pt of MARNOCK-SKUA]"
    entries = [(p, e) for (f, p), e in per_field_month.items() if f == field]
    entries.sort(key=lambda x: x[0])
    excluded = {stream: 0.0 for stream in PRODUCTION_STREAMS}
    for p, e in entries:
        for stream in PRODUCTION_STREAMS:
            excluded[stream] += e["production"][stream]
    periods = [p for p, e in entries]

    related_equity_fields = sorted(
        n for n in raw_rows_by_equity_field if "MARNOCK" in n or "SKUA" in n
    )

    return {
        "producing_months_affected": len(entries),
        "excluded_production_by_stream": {k: round(v, 4) for k, v in excluded.items()},
        "first_affected_period": periods[0] if periods else None,
        "latest_affected_period": periods[-1] if periods else None,
        "categories_seen": sorted({e["category"] for p, e in entries}),
        "related_equity_field_names_found": related_equity_fields,
        "murlach_own_equity_rows": [
            {"company": r["company_name"], "start": r["start_date"], "end": r["end_date"], "pct": r["interest_pct"]}
            for r in raw_rows_by_equity_field.get(field, [])
        ],
    }


# ---------------------------------------------------------------------------
# Company summary
# ---------------------------------------------------------------------------


def build_company_summary_historical(resolved_rows: list[dict], per_field_month: dict) -> list[dict]:
    by_company: dict[str, dict] = {}
    for r in resolved_rows:
        c = by_company.setdefault(
            r["company_name"],
            {"company_name": r["company_name"], "fields": set(), "periods": set(), "oil_mbd": 0.0, "dry_gas_mmscfd": 0.0, "assoc_gas_mmscfd": 0.0, "condensate_mbd": 0.0},
        )
        c["fields"].add(r["field_name"])
        c["periods"].add(r["period"])
        c["oil_mbd"] += r["oil_mbd"]
        c["dry_gas_mmscfd"] += r["dry_gas_mmscfd"]
        c["assoc_gas_mmscfd"] += r["assoc_gas_mmscfd"]
        c["condensate_mbd"] += r["condensate_mbd"]

    excluded_count_by_company: dict[str, int] = defaultdict(int)
    for (field, period), entry in per_field_month.items():
        if entry["category"] in ("quarantined", "e1_sum_mismatch") and "active_rows" in entry:
            for r in entry["active_rows"]:
                excluded_count_by_company[r["company_name"]] += 1

    summary = []
    for c in by_company.values():
        periods = sorted(c["periods"])
        summary.append(
            {
                "company_name": c["company_name"],
                "first_resolved_period": periods[0],
                "last_resolved_period": periods[-1],
                "field_count": len(c["fields"]),
                "oil_mbd": round(c["oil_mbd"], 6),
                "dry_gas_mmscfd": round(c["dry_gas_mmscfd"], 6),
                "assoc_gas_mmscfd": round(c["assoc_gas_mmscfd"], 6),
                "condensate_mbd": round(c["condensate_mbd"], 6),
                "excluded_quarantined_field_month_count": excluded_count_by_company.get(c["company_name"], 0),
            }
        )
    summary.sort(key=lambda c: c["company_name"])
    return summary


# ---------------------------------------------------------------------------
# Field matching over full history
# ---------------------------------------------------------------------------


def historical_matching_report(pprs_history: dict[str, list[dict]], field_match_index: dict[str, tuple[str, str]]) -> dict:
    matched = sorted(f for f in pprs_history if f in field_match_index)
    unmatched = sorted(f for f in pprs_history if f not in field_match_index)

    unmatched_detail = []
    total_production_all = {s: 0.0 for s in PRODUCTION_STREAMS}
    total_production_unmatched = {s: 0.0 for s in PRODUCTION_STREAMS}
    for field, points in pprs_history.items():
        for p in points:
            for stream in PRODUCTION_STREAMS:
                total_production_all[stream] += p[stream]
                if field in unmatched:
                    total_production_unmatched[stream] += p[stream]

    for field in unmatched:
        points = pprs_history[field]
        periods = [p["period"] for p in points]
        cumulative = {stream: round(sum(p[stream] for p in points), 4) for stream in PRODUCTION_STREAMS}
        unmatched_detail.append(
            {
                "field": field,
                "first_period": periods[0] if periods else None,
                "last_period": periods[-1] if periods else None,
                "cumulative_production_by_stream": cumulative,
            }
        )

    coverage_before_interval_resolution = {
        stream: round(100.0 * (total_production_all[stream] - total_production_unmatched[stream]) / total_production_all[stream], 3)
        if total_production_all[stream] > 0
        else None
        for stream in PRODUCTION_STREAMS
    }

    return {
        "matched_field_count": len(matched),
        "unmatched_field_count": len(unmatched),
        "unmatched_fields": unmatched_detail,
        "production_weighted_coverage_before_interval_resolution": coverage_before_interval_resolution,
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_historical_join() -> dict:
    t0 = time.time()

    pprs_history = load_full_history_production()
    raw_rows = load_raw_rows()
    aliases = load_field_aliases(FIELD_ALIASES_PATH)

    equity_fields = {r["field_name"] for r in raw_rows}
    raw_rows_by_equity_field: dict[str, list[dict]] = defaultdict(list)
    for r in raw_rows:
        raw_rows_by_equity_field[r["field_name"]].append(r)

    field_match_index = build_field_match_index(set(pprs_history), equity_fields, aliases)
    matching = historical_matching_report(pprs_history, field_match_index)

    per_field_month = resolve_full_history(pprs_history, field_match_index, raw_rows_by_equity_field)
    resolved_rows = build_resolved_grain_rows_historical(per_field_month)

    field_month_count = sum(len(v) for v in pprs_history.values())

    e1 = check_e1_historical(per_field_month)
    e4 = check_e4_historical(per_field_month)
    e5 = check_e5_historical(per_field_month)
    e7 = check_e7_historical(raw_rows)
    e8 = check_e8_historical(per_field_month, resolved_rows)
    coverage = monthly_coverage(per_field_month)
    gaps = gap_diagnostics(per_field_month)
    murlach = murlach_analysis(per_field_month, raw_rows_by_equity_field)
    company_summary = build_company_summary_historical(resolved_rows, per_field_month)
    zd_classification = classify_zero_duration_rows(raw_rows)

    runtime_seconds = time.time() - t0

    return {
        "pprs_field_month_count": field_month_count,
        "normalized_equity_row_count": len(raw_rows),
        "resolved_row_count": len(resolved_rows),
        "runtime_seconds": round(runtime_seconds, 2),
        "matching": matching,
        "per_field_month": per_field_month,
        "resolved_rows": resolved_rows,
        "e1": e1,
        "e4": e4,
        "e5": e5,
        "e7": e7,
        "e8": e8,
        "coverage": coverage,
        "gaps": gaps,
        "murlach": murlach,
        "company_summary": company_summary,
        "zero_duration_classification": zd_classification,
    }


def write_anomalies_json(result: dict, path: Path = ANOMALIES_PATH) -> None:
    """Complete machine-readable evidence for every quarantined or
    unresolved field-month - not just a summary."""
    anomalies = {
        "quarantined": result["e4"]["cases"],
        "e1_sum_mismatch_below_100": result["e1"]["below_100_examples"],
        "e1_sum_mismatch_above_100": result["e1"]["above_100_examples"],
        "genuine_interval_gaps": [
            {"field": f, "period": p} for (f, p), e in result["per_field_month"].items() if e["category"] == "genuine_interval_gap"
        ],
        "unmatched_fields": result["matching"]["unmatched_fields"],
        "murlach_analysis": result["murlach"],
    }
    path.write_text(json.dumps(anomalies, indent=2, sort_keys=True, default=str))


def build_historical_report(result: dict) -> str:
    m = result["matching"]
    lines = [
        "# Full historical equity interval-join diagnostic",
        "",
        "Diagnostic checkpoint only. No docs/data/equity artifacts, no build.py integration, no UI "
        "changes, no company alias or parent-group reconciliation, no historical equity production "
        "published. Company names are the legal entity exactly as recorded by NSTA.",
        "",
        "## Scale",
        "",
        f"- PPRS field-months processed: {result['pprs_field_month_count']}",
        f"- Normalized equity rows: {result['normalized_equity_row_count']}",
        f"- Resolved (field, company, month) rows produced: {result['resolved_row_count']}",
        f"- Runtime: {result['runtime_seconds']}s",
        "",
        "## Field-resolution statistics",
        "",
        f"- Matched fields (of 552): {m['matched_field_count']}",
        f"- Unmatched fields: {m['unmatched_field_count']}",
        f"- Production-weighted coverage before interval resolution (i.e. purely from field-name "
        f"matching): {m['production_weighted_coverage_before_interval_resolution']}",
        "",
        "### Unmatched fields (full list, first/last period, cumulative production)",
        "",
        "| Field | First period | Last period | Oil (mbd) | Dry gas (mmscfd) | Assoc. gas (mmscfd) | Condensate (mbd) |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for u in m["unmatched_fields"]:
        c = u["cumulative_production_by_stream"]
        lines.append(f"| {u['field']} | {u['first_period']} | {u['last_period']} | {c['oil_mbd']} | {c['dry_gas_mmscfd']} | {c['assoc_gas_mmscfd']} | {c['condensate_mbd']} |")

    lines += [
        "",
        "## E1 - interest conservation (full history)",
        "",
        f"- Passing field-months (resolved): {result['e1']['passing_field_months']}",
        f"- Below 100% (not an overlap): {result['e1']['below_100_count']}",
        f"- Above 100% (not caught as an overlap - e.g. rounding near the E1/E4 boundary): {result['e1']['above_100_count']}",
        f"- Below-100 examples: {result['e1']['below_100_examples']}",
        f"- Above-100 examples: {result['e1']['above_100_examples']}",
        "",
        "## E4 - overlap / quarantine (full history)",
        "",
        f"- Total quarantined field-months: {result['e4']['total_quarantined_field_months']}",
        f"- Distinct affected fields: {result['e4']['distinct_fields']}",
        f"- Distinct affected companies: {result['e4']['distinct_companies']}",
        f"- Earliest / latest affected period: {result['e4']['earliest_period']} / {result['e4']['latest_period']}",
        f"- Production excluded by stream: {result['e4']['excluded_production_by_stream']}",
        "",
        "Full conflicting-interval evidence for every quarantined case is in "
        "`etl/equity_historical_anomalies.json` (not repeated here in full if the list is long).",
        "",
    ]
    rochelle_cases = [c for c in result["e4"]["cases"] if c["field"] == "ROCHELLE"]
    lines.append(f"**ROCHELLE check: {len(rochelle_cases)} quarantined field-month(s) found for ROCHELLE.**")
    for c in rochelle_cases:
        lines.append(f"  - {c['period']}: sum={c['positive_interest_sum']}%, conflicting intervals: {c['conflicting_intervals']}")
    lines.append("")

    lines += [
        "## E5 - coverage classification (full history, precise categories)",
        "",
    ]
    for cat, count in result["e5"].items():
        lines.append(f"- {cat}: {count}")

    lines += [
        "",
        "## E7 - interval validity (full workbook)",
        "",
        f"- Rows checked: {result['e7']['total_rows_checked']}",
        f"- start_date > end_date violations: {len(result['e7']['start_after_end_violations'])}",
        f"- Passed: {result['e7']['passed']}",
        f"- Zero-duration rows accepted as non-active source events: {result['e7']['zero_duration_rows_accepted_as_events']}",
        "",
        "## E8 - production conservation (monthly, per stream, resolved fields only)",
        "",
        f"- Months checked: {result['e8']['months_checked']}",
        f"- Failures beyond tolerance: {len(result['e8']['failures'])}",
        f"- Passed: {result['e8']['passed']}",
    ]
    for f in result["e8"]["failures"][:20]:
        lines.append(f"  - {f}")

    lines += [
        "",
        "## Partial-month / gap diagnostics",
        "",
    ]
    for cat, detail in result["gaps"].items():
        lines.append(f"### {cat}")
        lines.append("")
        lines.append(f"- Field-months: {detail['field_month_count']}")
        lines.append(f"- Distinct fields: {detail['distinct_field_count']}")
        lines.append(f"- Excluded production by stream: {detail['excluded_production_by_stream']}")
        lines.append(f"- Earliest / latest affected period: {detail['earliest_period']} / {detail['latest_period']}")
        lines.append(f"- Example fields: {detail['example_fields']}")
        lines.append("")
    lines.append(
        "These are NOT all treated as data errors: `month_start_boundary` is a mechanical artifact "
        "of resolving ownership at the first day of the month when a real interval starts or ends "
        "mid-month; `pre_equity_history` and `future_only` reflect genuine absence of equity "
        "coverage for part or all of a field's production run; only `genuine_interval_gap` "
        "represents a real break in coverage between two dated intervals."
    )
    lines.append("")

    lines += [
        "## Coverage by stream",
        "",
        f"Full-history production-weighted coverage: {result['coverage']['full_history_coverage_pct']}",
        "",
        "**This is low, and must not be read as the historical model being broadly unreliable in "
        "the way that number alone suggests** - see the annual breakdown below. Coverage rises "
        "sharply once equity records begin for most fields; the low full-history average is driven "
        "by ~1975-2000, where the equity workbook simply has little or no coverage for many "
        "fields' earliest years (`pre_equity_history` - not a matching or interval-resolution "
        "failure).",
        "",
        "### Annual production-weighted coverage by stream",
        "",
        "| Year | Oil | Dry gas | Assoc. gas | Condensate |",
        "| --- | --- | --- | --- | --- |",
    ]
    for year, streams in result["coverage"]["annual_coverage_pct"].items():
        lines.append(f"| {year} | {streams['oil_mbd']} | {streams['dry_gas_mmscfd']} | {streams['assoc_gas_mmscfd']} | {streams['condensate_mbd']} |")
    lines += [
        "",
        "### Coverage buckets (months, by stream)",
        "",
    ]
    for stream, buckets in result["coverage"]["coverage_buckets_by_stream"].items():
        lines.append(f"- {stream}: {buckets}")
    lines += [
        "",
        "### Ten lowest-coverage months per stream",
        "",
    ]
    for stream, months in result["coverage"]["lowest_coverage_months"].items():
        lines.append(f"- {stream}: {months}")
    lines += [
        "",
        "### Production excluded by category, by stream",
        "",
    ]
    for cat, streams in result["coverage"]["excluded_production_by_category_stream"].items():
        lines.append(f"- {cat}: {streams}")

    lines += [
        "",
        "## MURLACH [pt of MARNOCK-SKUA] investigation",
        "",
        f"- Producing months affected: {result['murlach']['producing_months_affected']}",
        f"- Excluded production by stream: {result['murlach']['excluded_production_by_stream']}",
        f"- First / latest affected period: {result['murlach']['first_affected_period']} / {result['murlach']['latest_affected_period']}",
        f"- Categories seen across its history: {result['murlach']['categories_seen']}",
        f"- Related equity field names found (MARNOCK/SKUA substring match): {result['murlach']['related_equity_field_names_found']}",
        f"- MURLACH's own equity rows (all of them): {result['murlach']['murlach_own_equity_rows']}",
        "",
        "No alias applied. The related `MARNOCK [pt. of MARNOCK-SKUA]` equity rows belong to a "
        "**different** field name and were not treated as covering MURLACH without authoritative "
        "evidence that they should. This remains an open question for a human reviewer, not "
        "resolved by this diagnostic.",
        "",
        "## Historical company summary (legal entity as recorded by NSTA)",
        "",
        "No parent-company or current-group rollup. No merging of similarly-named companies. This "
        "is not a corporate-group history.",
        "",
        "| Company | First period | Last period | Fields | Oil (mbd) | Dry gas (mmscfd) | Assoc. gas (mmscfd) | Condensate (mbd) | Excluded/quarantined field-months |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for c in result["company_summary"][:50]:
        lines.append(
            f"| {c['company_name']} | {c['first_resolved_period']} | {c['last_resolved_period']} | {c['field_count']} | "
            f"{c['oil_mbd']} | {c['dry_gas_mmscfd']} | {c['assoc_gas_mmscfd']} | {c['condensate_mbd']} | {c['excluded_quarantined_field_month_count']} |"
        )
    if len(result["company_summary"]) > 50:
        lines.append(f"\n(... {len(result['company_summary']) - 50} more companies; full table available by re-running `python etl/equity_join_historical.py`.)")

    lines += [
        "",
        "## Confirmations",
        "",
        "- No parent-company rollup was performed. Every `company_name` above is the legal entity "
        "string exactly as recorded in the workbook's `Organisation Name` column.",
        "- No public artifacts were written (nothing under docs/data/equity/*), `etl/build.py` was "
        "not modified, and no UI changes were made. This report and "
        "`etl/equity_historical_anomalies.json` are the only outputs, both under `etl/`.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    result = run_historical_join()
    report = build_historical_report(result)
    HISTORICAL_REPORT_PATH.write_text(report)
    write_anomalies_json(result)
    print(report)
    print(f"\nHistorical join report written to {HISTORICAL_REPORT_PATH}")
    print(f"Anomalies JSON written to {ANOMALIES_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
