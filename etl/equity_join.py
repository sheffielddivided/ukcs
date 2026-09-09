"""
Phase 2, step 4 (spec section 15.8 step 4) - latest-period interval-join
checkpoint only.

Resolves active equity interests for the latest PPRS production period and
calculates equity-attributable production at:

    field x month x legal entity as recorded by NSTA

for that single period, using the policy decisions approved after the
milestone-3 interval-semantics investigation (see UKCS_DESIGN_v2.md
sections 15.3-15.4). This module produces **in-memory diagnostic results
only** - it does not write docs/data/equity/*, does not touch build.py,
does not perform company alias/parent-group reconciliation, and does not
run the full historical join (every field x every month back to 1975).
That remains future work, gated on review of this checkpoint.

Policy decisions in force (approved, not re-litigated here):

1. Half-open containment: `start_date <= month_start < end_date`. An empty
   end_date is open-ended.
2. Zero-duration rows (`start_date == end_date`) are retained as source
   event records. They carry no active interest (mathematically inert
   under half-open containment) and never fail validation for having zero
   duration. Their milestone-3 diagnostic classification
   (boundary_duplicate / boundary_transition / termination_marker /
   standalone_snapshot) is carried through unchanged; a fifth category,
   `unresolved`, is available for a future row this module cannot
   classify into the other four (none currently exist).
3. Zero-interest rows are retained as source records, excluded from the
   equity sum. `Operator Flag = 'Y'` is never read as evidence of a
   positive interest.
4. Future-dated intervals are retained, inactive until their start date.
   A field whose only rows are future-dated does not fail E5 before its
   first effective date.
5. `Equity Share Time Period` is retained as source metadata only (in the
   raw row data); it never controls interval resolution here.
6. An unresolved overlap (two rows, same or different companies, both
   active for the same field-month, sum != 100% ± 0.5pp because of it) is
   **quarantined**, not repaired: reported, excluded from any calculated
   equity total for that field-month, coverage status set to
   "quarantined". The two/more conflicting interests are never normalised
   back to 100%, and no owner is ever preferred over another. This
   quarantine policy is temporary pending review before the full
   historical join.

Run: python etl/equity_join.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from equity_interval_diagnostics import classify_zero_duration_rows, load_raw_rows
from equity_match import (
    FIELD_ALIASES_PATH,
    HISTORY_INDEX_PATH,
    PRODUCTION_STREAMS,
    load_field_aliases,
    load_latest_period_production,
    load_pprs_field_universe,
    match_fields,
)

META_PATH = Path(__file__).parent.parent / "docs" / "data" / "meta.json"
DIAGNOSTIC_REPORT_PATH = Path(__file__).parent / "equity_latest_period_join_report.md"

E1_TOLERANCE_PP = 0.5
E8_TOLERANCE_PCT = 0.5


class EquityJoinError(RuntimeError):
    """Raised when the latest-period resolver cannot proceed. Message must
    say exactly why."""


def load_latest_period() -> str:
    with open(META_PATH) as f:
        return json.load(f)["latest_period"]


def _to_date(iso: str) -> date:
    y, m, d = map(int, iso.split("-"))
    return date(y, m, d)


def _month_start_from_period(period: str) -> date:
    """period is 'YYYYMM' as used throughout the site (e.g. '202606')."""
    return date(int(period[:4]), int(period[4:6]), 1)


# ---------------------------------------------------------------------------
# Field matching (reuses etl/equity_match.py's deterministic matcher)
# ---------------------------------------------------------------------------


def build_field_match_index(pprs_fields: set[str], equity_fields: set[str], aliases: list[dict]) -> dict[str, tuple[str, str]]:
    """Returns {pprs_field_name: (equity_field_name, method)} for every
    matched PPRS field, method in {'exact', 'normalized', 'alias'}."""
    result = match_fields(pprs_fields, equity_fields, aliases)
    index = {}
    for pprs_name, equity_name in result["exact_matches"].items():
        index[pprs_name] = (equity_name, "exact")
    for pprs_name, equity_name in result["normalized_matches"].items():
        index[pprs_name] = (equity_name, "normalized")
    for pprs_name, equity_name in result["alias_matches"].items():
        index[pprs_name] = (equity_name, "alias")
    return index


# ---------------------------------------------------------------------------
# Latest-period interval resolution (E1, E4)
# ---------------------------------------------------------------------------


def resolve_field_month(field_rows: list[dict], month_start: date) -> dict:
    """Resolves active interests for one field at one month_start instant.
    Returns active rows, the positive-interest sum, and any E4 overlap
    (same-company duplicate active rows, or a cross-company sum that
    exceeds 100% + tolerance even without a same-company duplicate)."""
    active = []
    for r in field_rows:
        s = _to_date(r["start_date"])
        e = _to_date(r["end_date"]) if r["end_date"] else None
        if s <= month_start and (e is None or month_start < e):
            active.append(r)

    positive_sum = sum(r["interest_pct"] for r in active if r["interest_pct"] > 0)
    companies = [r["company_name"] for r in active]
    company_counts = defaultdict(int)
    for c in companies:
        company_counts[c] += 1
    same_company_overlap = {c: n for c, n in company_counts.items() if n > 1}

    overlap = bool(same_company_overlap) or positive_sum > (100.0 + E1_TOLERANCE_PP)

    return {
        "active_rows": active,
        "positive_interest_sum": round(positive_sum, 4),
        "same_company_overlap": same_company_overlap,
        "overlap": overlap,
    }


# ---------------------------------------------------------------------------
# Field-level resolution categorisation (feeds E1, E5, coverage)
# ---------------------------------------------------------------------------


def build_resolution(
    field_match_index: dict[str, tuple[str, str]],
    raw_rows_by_equity_field: dict[str, list[dict]],
    latest_production: dict[str, dict],
    month_start: date,
) -> dict[str, dict]:
    """For every PPRS field present in the latest period's production
    (docs/data/fields.geojson), categorise it into exactly one of:
    unmatched / future_only / quarantined / resolved / unresolved_gap."""
    resolutions = {}
    for pprs_field in latest_production:
        if pprs_field not in field_match_index:
            resolutions[pprs_field] = {"category": "unmatched", "reason": "no equity workbook field name matched (exact/normalized/alias)"}
            continue

        equity_field, method = field_match_index[pprs_field]
        field_rows = raw_rows_by_equity_field.get(equity_field, [])
        if not field_rows:
            resolutions[pprs_field] = {"category": "unresolved_gap", "reason": "matched equity field name has no rows at all", "field_match_method": method}
            continue

        all_future = all(_to_date(r["start_date"]) > month_start for r in field_rows)
        month_result = resolve_field_month(field_rows, month_start)

        if not month_result["active_rows"]:
            if all_future:
                resolutions[pprs_field] = {
                    "category": "future_only",
                    "reason": "all equity rows for this field have a start_date after the evaluated month_start",
                    "field_match_method": method,
                    "equity_field_name": equity_field,
                    "earliest_future_start": min(r["start_date"] for r in field_rows),
                }
            else:
                resolutions[pprs_field] = {
                    "category": "unresolved_gap",
                    "reason": "matched equity field has rows, but none is active at this month_start and rows are not all future-dated",
                    "field_match_method": method,
                    "equity_field_name": equity_field,
                }
            continue

        if month_result["overlap"]:
            interval_detail = "; ".join(
                f"{r['company_name']} [{r['start_date']} -> {r['end_date'] or 'open'}] {r['interest_pct']}%"
                for r in month_result["active_rows"]
            )
            resolutions[pprs_field] = {
                "category": "quarantined",
                "reason": (
                    "E4 overlap: "
                    + (
                        f"same-company duplicate active rows {month_result['same_company_overlap']}"
                        if month_result["same_company_overlap"]
                        else f"active positive interests sum to {month_result['positive_interest_sum']}% (> 100% + {E1_TOLERANCE_PP}pp)"
                    )
                    + f" -- conflicting source intervals: {interval_detail}"
                ),
                "field_match_method": method,
                "equity_field_name": equity_field,
                "active_rows": month_result["active_rows"],
                "positive_interest_sum": month_result["positive_interest_sum"],
            }
            continue

        total = month_result["positive_interest_sum"]
        if abs(total - 100.0) > E1_TOLERANCE_PP:
            resolutions[pprs_field] = {
                "category": "unresolved_gap",
                "reason": f"active positive interests sum to {total}%, outside 100% +-{E1_TOLERANCE_PP}pp and not an overlap",
                "field_match_method": method,
                "equity_field_name": equity_field,
                "active_rows": month_result["active_rows"],
                "positive_interest_sum": total,
            }
            continue

        resolutions[pprs_field] = {
            "category": "resolved",
            "field_match_method": method,
            "equity_field_name": equity_field,
            "active_rows": month_result["active_rows"],
            "positive_interest_sum": total,
        }

    return resolutions


# ---------------------------------------------------------------------------
# Grain output: field x company (legal entity) x period
# ---------------------------------------------------------------------------


def build_resolved_grain_rows(resolutions: dict[str, dict], latest_production: dict[str, dict], period: str) -> list[dict]:
    """One row per (field, company) for fully RESOLVED fields only. No
    boe/d. No parent-group rollup - company_name is the legal entity name
    exactly as recorded in the workbook."""
    rows = []
    for pprs_field, res in resolutions.items():
        if res["category"] != "resolved":
            continue
        production = latest_production[pprs_field]
        for r in res["active_rows"]:
            if r["interest_pct"] <= 0:
                continue
            factor = r["interest_pct"] / 100.0
            rows.append(
                {
                    "field_name": pprs_field,
                    "company_name": r["company_name"],
                    "interest_pct": r["interest_pct"],
                    "period": period,
                    "oil_mbd": round(production["oil_mbd"] * factor, 6),
                    "dry_gas_mmscfd": round(production["dry_gas_mmscfd"] * factor, 6),
                    "assoc_gas_mmscfd": round(production["assoc_gas_mmscfd"] * factor, 6),
                    "condensate_mbd": round(production["condensate_mbd"] * factor, 6),
                    "source_start_date": r["start_date"],
                    "source_end_date": r["end_date"],
                    "operator_flag": r["operator_flag"],
                    "field_match_method": res["field_match_method"],
                }
            )
    rows.sort(key=lambda r: (r["field_name"], r["company_name"]))
    return rows


# ---------------------------------------------------------------------------
# Validation: E1, E4, E5, E7, E8 (latest-period versions)
# ---------------------------------------------------------------------------


def check_e1(resolutions: dict[str, dict]) -> dict:
    """E1: for every matched field with at least one currently-effective
    ownership interval, active positive interests sum to 100% +-0.5pp.
    Future-only fields and quarantined field-months are excluded from
    pass/fail and reported separately."""
    passing = []
    failing = []
    for field, res in resolutions.items():
        if res["category"] == "resolved":
            passing.append((field, res["positive_interest_sum"]))
        elif res["category"] == "unresolved_gap" and "positive_interest_sum" in res:
            failing.append((field, res["positive_interest_sum"], res["reason"]))
    return {
        "passing_field_count": len(passing),
        "failing_field_count": len(failing),
        "failing_fields": failing,
    }


def check_e4(resolutions: dict[str, dict]) -> dict:
    """E4: overlapping positive-interest intervals, same (field, company)
    or a cross-company field-month total > 100%. Never auto-resolved -
    every violation is quarantined and reported here, not silently fixed."""
    quarantined = [(field, res["reason"]) for field, res in resolutions.items() if res["category"] == "quarantined"]
    return {
        "quarantined_field_count": len(quarantined),
        "quarantined_fields": quarantined,
    }


def check_e5(resolutions: dict[str, dict]) -> dict:
    """E5: a producing latest-period field must resolve to an active
    ownership set unless unmatched, future-only, or quarantined. Each
    category reported separately, never collapsed into one 'missing
    equity' count."""
    by_category = defaultdict(list)
    for field, res in resolutions.items():
        by_category[res["category"]].append(field)
    return {
        "resolved": sorted(by_category.get("resolved", [])),
        "unmatched": sorted(by_category.get("unmatched", [])),
        "future_only": sorted(by_category.get("future_only", [])),
        "quarantined": sorted(by_category.get("quarantined", [])),
        "unresolved_gap": sorted(by_category.get("unresolved_gap", [])),
    }


def check_e7(all_raw_rows: list[dict]) -> dict:
    """E7: start_date <= end_date on every row (closed or zero-duration).
    start_date > end_date is build-breaking. This is a structural check
    over the FULL workbook, not scoped to the latest period, since it is a
    data-integrity property of the source, not a period-specific one."""
    violations = [r for r in all_raw_rows if r["end_date"] is not None and r["start_date"] > r["end_date"]]
    return {
        "total_rows_checked": len(all_raw_rows),
        "violations": [(r["field_name"], r["company_name"], r["start_date"], r["end_date"]) for r in violations],
        "passed": len(violations) == 0,
    }


def check_e8(resolved_rows: list[dict], resolutions: dict[str, dict], latest_production: dict[str, dict]) -> dict:
    """E8 per stream: sum(equity-attributable production) across resolved
    (field, company) rows must equal sum(field production) for the SAME
    set of fully-resolved fields - never compared against quarantined or
    unresolved fields' production. Reports total/included/excluded
    production and coverage_pct per stream."""
    resolved_fields = {field for field, res in resolutions.items() if res["category"] == "resolved"}
    result = {}
    for stream in PRODUCTION_STREAMS:
        total_all = sum(p[stream] for p in latest_production.values())
        included = sum(p[stream] for f, p in latest_production.items() if f in resolved_fields)
        excluded = total_all - included
        equity_sum = sum(r[stream] for r in resolved_rows)
        diff = abs(equity_sum - included)
        tolerance = max(0.001, included * E8_TOLERANCE_PCT / 100.0)
        result[stream] = {
            "total_production": round(total_all, 4),
            "included_production": round(included, 4),
            "excluded_production": round(excluded, 4),
            "equity_attributable_sum": round(equity_sum, 4),
            "difference": round(diff, 6),
            "within_tolerance": diff <= tolerance,
            "coverage_pct": round(100.0 * included / total_all, 3) if total_all > 0 else None,
        }
    return result


# ---------------------------------------------------------------------------
# Coverage reporting
# ---------------------------------------------------------------------------


def coverage_report(resolutions: dict[str, dict], latest_production: dict[str, dict]) -> dict:
    counts = defaultdict(int)
    for res in resolutions.values():
        counts[res["category"]] += 1

    e8 = check_e8(build_resolved_grain_rows(resolutions, latest_production, "n/a"), resolutions, latest_production)
    return {
        "resolved_field_count": counts.get("resolved", 0),
        "unmatched_field_count": counts.get("unmatched", 0),
        "quarantined_field_count": counts.get("quarantined", 0),
        "unresolved_gap_field_count": counts.get("unresolved_gap", 0),
        "future_only_field_count": counts.get("future_only", 0),
        "coverage_by_stream": {stream: e8[stream]["coverage_pct"] for stream in PRODUCTION_STREAMS},
    }


# ---------------------------------------------------------------------------
# Company summary (legal entity as recorded by NSTA - no rollups)
# ---------------------------------------------------------------------------


def build_company_summary(resolved_rows: list[dict]) -> list[dict]:
    by_company: dict[str, dict] = {}
    for r in resolved_rows:
        c = by_company.setdefault(
            r["company_name"],
            {"company_name": r["company_name"], "fields": set(), "oil_mbd": 0.0, "dry_gas_mmscfd": 0.0, "assoc_gas_mmscfd": 0.0, "condensate_mbd": 0.0},
        )
        c["fields"].add(r["field_name"])
        c["oil_mbd"] += r["oil_mbd"]
        c["dry_gas_mmscfd"] += r["dry_gas_mmscfd"]
        c["assoc_gas_mmscfd"] += r["assoc_gas_mmscfd"]
        c["condensate_mbd"] += r["condensate_mbd"]

    summary = []
    for c in by_company.values():
        summary.append(
            {
                "company_name": c["company_name"],
                "producing_field_count": len(c["fields"]),
                "oil_mbd": round(c["oil_mbd"], 6),
                "dry_gas_mmscfd": round(c["dry_gas_mmscfd"], 6),
                "assoc_gas_mmscfd": round(c["assoc_gas_mmscfd"], 6),
                "condensate_mbd": round(c["condensate_mbd"], 6),
            }
        )
    summary.sort(key=lambda c: c["company_name"])
    return summary


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_latest_period_join() -> dict:
    period = load_latest_period()
    month_start = _month_start_from_period(period)

    pprs_universe = load_pprs_field_universe(HISTORY_INDEX_PATH)
    latest_production = load_latest_period_production()
    raw_rows = load_raw_rows()
    aliases = load_field_aliases(FIELD_ALIASES_PATH)

    equity_fields = {r["field_name"] for r in raw_rows}
    raw_rows_by_equity_field: dict[str, list[dict]] = defaultdict(list)
    for r in raw_rows:
        raw_rows_by_equity_field[r["field_name"]].append(r)

    field_match_index = build_field_match_index(set(pprs_universe), equity_fields, aliases)

    resolutions = build_resolution(field_match_index, raw_rows_by_equity_field, latest_production, month_start)
    resolved_rows = build_resolved_grain_rows(resolutions, latest_production, period)

    e1 = check_e1(resolutions)
    e4 = check_e4(resolutions)
    e5 = check_e5(resolutions)
    e7 = check_e7(raw_rows)
    e8 = check_e8(resolved_rows, resolutions, latest_production)
    coverage = coverage_report(resolutions, latest_production)
    company_summary = build_company_summary(resolved_rows)
    zd_classification = classify_zero_duration_rows(raw_rows)

    return {
        "period": period,
        "month_start": month_start.isoformat(),
        "pprs_producing_field_count": len(latest_production),
        "resolutions": resolutions,
        "resolved_rows": resolved_rows,
        "e1": e1,
        "e4": e4,
        "e5": e5,
        "e7": e7,
        "e8": e8,
        "coverage": coverage,
        "company_summary": company_summary,
        "zero_duration_classification": zd_classification,
    }


def build_join_report(result: dict) -> str:
    lines = [
        "# Latest-period equity interval-join checkpoint",
        "",
        "Diagnostic checkpoint only (spec section 15.8 step 4, latest period only). No "
        "docs/data/equity artifacts, no build.py changes, no UI changes, no company alias or "
        "parent-group reconciliation. Company names are the legal entity exactly as recorded by "
        "NSTA.",
        "",
        f"1. Period used: `{result['period']}` (month_start = {result['month_start']})",
        f"2. Producing PPRS fields (latest period): {result['pprs_producing_field_count']}",
        f"3. Matched fields: {result['coverage']['resolved_field_count'] + result['coverage']['quarantined_field_count'] + result['coverage']['unresolved_gap_field_count'] + result['coverage']['future_only_field_count']}",
        f"4. Fully resolved ownership sets: {result['coverage']['resolved_field_count']}",
        "",
        "## 5. Unresolved / quarantined / excluded fields, with reason",
        "",
    ]
    for category in ["unmatched", "future_only", "quarantined", "unresolved_gap"]:
        fields = result["e5"][category]
        lines.append(f"### {category} ({len(fields)})")
        lines.append("")
        for field in fields:
            res = result["resolutions"][field]
            lines.append(f"- **{field}**: {res.get('reason', '(no reason recorded)')}")
        lines.append("")

    lines += [
        "## 6. E1 - interest conservation",
        "",
        f"- Passing (resolved, sum 100% +-0.5pp): {result['e1']['passing_field_count']}",
        f"- Failing (matched, active, sum outside tolerance, not an overlap): {result['e1']['failing_field_count']}",
    ]
    for field, total, reason in result["e1"]["failing_fields"]:
        lines.append(f"  - {field}: sum={total}% - {reason}")
    lines += [
        "",
        "## 7. E4 - overlap validation",
        "",
        f"- Quarantined field-months: {result['e4']['quarantined_field_count']}",
    ]
    for field, reason in result["e4"]["quarantined_fields"]:
        lines.append(f"  - {field}: {reason}")
    lines += [
        "",
        "## 8. E5 - coverage validation",
        "",
        f"- resolved: {len(result['e5']['resolved'])}",
        f"- unmatched: {len(result['e5']['unmatched'])}",
        f"- future_only: {len(result['e5']['future_only'])}",
        f"- quarantined: {len(result['e5']['quarantined'])}",
        f"- unresolved_gap: {len(result['e5']['unresolved_gap'])}",
        "",
        "## E7 - interval validity (full workbook, not period-scoped)",
        "",
        f"- Rows checked: {result['e7']['total_rows_checked']}",
        f"- Violations (start_date > end_date): {len(result['e7']['violations'])}",
        f"- Passed: {result['e7']['passed']}",
        "",
        "## 9. E8 - production conservation, by stream",
        "",
        "| Stream | Total | Included (resolved fields) | Excluded | Equity-attributable sum | Within tolerance | Coverage % |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for stream in PRODUCTION_STREAMS:
        e8s = result["e8"][stream]
        lines.append(
            f"| {stream} | {e8s['total_production']} | {e8s['included_production']} | {e8s['excluded_production']} | "
            f"{e8s['equity_attributable_sum']} | {e8s['within_tolerance']} | {e8s['coverage_pct']} |"
        )
    lines += [
        "",
        "## 10. Coverage percentage by stream",
        "",
    ]
    for stream, pct in result["coverage"]["coverage_by_stream"].items():
        lines.append(f"- {stream}: {pct}%")
    lines += [
        "",
        f"Do not read this as 100% coverage unless both matching AND interval resolution are "
        f"complete: unmatched={result['coverage']['unmatched_field_count']}, "
        f"quarantined={result['coverage']['quarantined_field_count']}, "
        f"unresolved_gap={result['coverage']['unresolved_gap_field_count']}, "
        f"future_only={result['coverage']['future_only_field_count']}.",
        "",
        "## 11. Latest-period company summary",
        "",
        "**Legal entity as recorded by NSTA.** No parent-company mapping, no rollup, no merging "
        "of similarly-named companies.",
        "",
        "| Company | Producing fields | Oil (mbd) | Dry gas (mmscfd) | Assoc. gas (mmscfd) | Condensate (mbd) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for c in result["company_summary"]:
        lines.append(
            f"| {c['company_name']} | {c['producing_field_count']} | {c['oil_mbd']} | {c['dry_gas_mmscfd']} | "
            f"{c['assoc_gas_mmscfd']} | {c['condensate_mbd']} |"
        )
    lines += [
        "",
        "## 12. Confirmation: no parent-company rollup performed",
        "",
        "Confirmed. Every company_name above is the legal entity string exactly as it appears in "
        "the `Organisation Name` column of the source workbook. No `etl/mappings/company_aliases.csv` "
        "exists, none was created by this step, and no rollup logic was written.",
        "",
        "## 13. Confirmation: no public artifacts or UI changes",
        "",
        "Confirmed. This module writes only this report and reads already-built "
        "docs/data/history/index.json, docs/data/fields.geojson and docs/data/meta.json (Phase 1 "
        "artifacts, read-only). It does not write to docs/data/equity/*, does not modify "
        "etl/build.py, and does not touch docs/index.html or docs/app/*.",
        "",
        "## Zero-duration classification (carried through unchanged from milestone 3)",
        "",
        f"- {result['zero_duration_classification']['category_counts']}",
        "- The `boundary_transition` and `standalone_snapshot` categories remain unresolved "
        "source semantics; their meaning is not settled by this checkpoint.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    result = run_latest_period_join()
    report = build_join_report(result)
    DIAGNOSTIC_REPORT_PATH.write_text(report)
    print(report)
    print(f"\nLatest-period join report written to {DIAGNOSTIC_REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
