"""
Phase 2, interval-semantics investigation (not spec section 15.8 step 4 -
this is a diagnostic/policy-definition step preceding it).

This module is a **diagnostic interval resolver**, kept deliberately
separate from any production/equity calculation code (which does not
exist yet - spec section 15.8 step 4 is still pending). It never joins
against PPRS production, never computes equity-attributable production or
company production, and never writes docs/data/equity artifacts.

It exists to answer one question empirically, without assuming the
answer: given the edge cases found in milestones 1-2 (838 zero-duration
rows, 241 zero-interest rows, 4 future-dated rows, 1,187 open-ended rows,
1 genuine interval overlap), what does the workbook's own row structure
actually show about how these should be treated before the real interval
join is written?

Three interval-containment policies are compared (spec's canonical test:
`start_date <= month_start AND (end_date IS NULL OR end_date > month_start)`):

- Policy A: apply the half-open test literally to every row, including
  zero-duration rows, with no special-casing.
- Policy B: explicitly filter out zero-duration rows before applying the
  same test.
- Policy C: prefer the `Equity Share Time Period` column's year range over
  the parsed Start/End Date where the two disagree.

Run: python etl/equity_interval_diagnostics.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.equity_parse import DEFAULT_WORKBOOK_PATH, load_workbook_sheet, parse_equity_workbook, read_header

DIAGNOSTICS_REPORT_PATH = Path(__file__).parent / "equity_interval_diagnostics_report.md"

# "Latest available month" for the diagnostic grid. This is a standalone
# investigation of the workbook's own row structure - it does not read
# meta.json or join against PPRS, per this step's explicit scope. Anchored
# to the wall-clock month this investigation was run, not to PPRS's
# latest_period.
LATEST_AVAILABLE_MONTH = date(2026, 9, 1)

PERIOD_LABEL_CURRENT = re.compile(r"^Current$")
PERIOD_LABEL_PREVIOUS = re.compile(r"^Previous-(\d{4}) to (\d{4})$")


# ---------------------------------------------------------------------------
# Raw row loading (includes columns equity_parse.py deliberately does not
# carry into its normalized output: Status, Operator Flag, Equity Share
# Time Period - all needed for this investigation).
# ---------------------------------------------------------------------------


def load_raw_rows(workbook_path: Path = DEFAULT_WORKBOOK_PATH) -> list[dict]:
    ws = load_workbook_sheet(workbook_path)
    col_index = read_header(ws)
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row is None or all(v is None for v in row):
            continue
        start = row[col_index["Start Date"]]
        end = row[col_index["End Date"]]
        rows.append(
            {
                "field_name": row[col_index["Field Name"]],
                "on_offshore": row[col_index["On Offshore"]],
                "status": row[col_index["Status"]],
                "company_name": row[col_index["Organisation Name"]],
                "interest_pct": float(row[col_index["Percentage Holding"]]),
                "operator_flag": row[col_index["Operator Flag"]],
                "start_date": start.date().isoformat() if start else None,
                "end_date": end.date().isoformat() if end else None,
                "period_label": row[col_index["Equity Share Time Period"]],
            }
        )
    return rows


def _to_date(iso: str) -> date:
    y, m, d = map(int, iso.split("-"))
    return date(y, m, d)


# ---------------------------------------------------------------------------
# 1. Zero-duration interval classification
# ---------------------------------------------------------------------------


def classify_zero_duration_rows(rows: list[dict]) -> dict:
    """Classifies each zero-duration row (start_date == end_date) by its
    relationship to other rows for the same (field, company), and, failing
    that, to other companies' rows for the same field. Categories are
    derived from observed relationships only, not assumed:

    - boundary_duplicate: has a same-(field,company) row starting exactly
      where this row ends (or ending exactly where this row starts) whose
      interest_pct matches this row's exactly.
    - boundary_transition: same adjacency, but interest_pct differs.
    - termination_marker: has a preceding same-(field,company) row, no
      succeeding one - the last recorded entry for that pair.
    - standalone_snapshot: neither a preceding nor succeeding
      same-(field,company) row exists - the only record that pair has.
    """
    by_field_company: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        by_field_company[(r["field_name"], r["company_name"])].append(r)
    for k in by_field_company:
        by_field_company[k].sort(key=lambda r: r["start_date"])

    zero_duration = [r for r in rows if r["start_date"] == r["end_date"]]

    def find_preceding(r):
        for sib in by_field_company[(r["field_name"], r["company_name"])]:
            if sib is r:
                continue
            if sib["end_date"] == r["start_date"] and sib["start_date"] != sib["end_date"]:
                return sib
        return None

    def find_succeeding(r):
        for sib in by_field_company[(r["field_name"], r["company_name"])]:
            if sib is r:
                continue
            if sib["start_date"] == r["end_date"] and sib["start_date"] != sib["end_date"]:
                return sib
        return None

    classified = []
    category_counts = Counter()
    for r in zero_duration:
        prec = find_preceding(r)
        succ = find_succeeding(r)
        if prec and succ:
            category = "boundary_duplicate" if (r["interest_pct"] == prec["interest_pct"] == succ["interest_pct"]) else "boundary_transition"
        elif succ:
            category = "boundary_duplicate" if r["interest_pct"] == succ["interest_pct"] else "boundary_transition"
        elif prec:
            category = "termination_marker"
        else:
            category = "standalone_snapshot"
        category_counts[category] += 1
        classified.append({**r, "zero_duration_category": category})

    date_year_counts = Counter(r["start_date"][:4] for r in zero_duration)
    date_exact_counts = Counter(r["start_date"] for r in zero_duration)
    pct_bucket = Counter()
    for r in zero_duration:
        if r["interest_pct"] == 0:
            pct_bucket["zero"] += 1
        elif r["interest_pct"] == 100:
            pct_bucket["hundred"] += 1
        else:
            pct_bucket["partial"] += 1

    return {
        "total_zero_duration_rows": len(zero_duration),
        "distinct_fields": len({r["field_name"] for r in zero_duration}),
        "distinct_companies": len({r["company_name"] for r in zero_duration}),
        "category_counts": dict(category_counts),
        "classified_rows": classified,
        "date_year_distribution": dict(date_year_counts.most_common()),
        "top_exact_dates": date_exact_counts.most_common(15),
        "interest_pct_bucket": dict(pct_bucket),
        "operator_flag_distribution": dict(Counter(r["operator_flag"] for r in zero_duration)),
        "status_distribution": dict(Counter(r["status"] for r in zero_duration)),
        "on_offshore_distribution": dict(Counter(r["on_offshore"] for r in zero_duration)),
    }


# ---------------------------------------------------------------------------
# 2. Competing interval policies (diagnostic only - no PPRS join)
# ---------------------------------------------------------------------------


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _add_month(d: date) -> date:
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


def _month_range(min_start: date, latest: date = LATEST_AVAILABLE_MONTH) -> list[date]:
    cur = _month_start(min_start)
    months = []
    while cur <= latest:
        months.append(cur)
        cur = _add_month(cur)
    return months


def _period_label_implied_years(period_label: str) -> tuple[int, int] | None:
    """Policy C support: derive a (start_year, end_year) pair from the
    Equity Share Time Period label alone, or None for 'Current'."""
    m = PERIOD_LABEL_PREVIOUS.match(period_label)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _active_rows_for_month(field_rows: list[dict], month: date, policy: str) -> list[dict]:
    active = []
    for r in field_rows:
        is_zero_duration = r["start_date"] == r["end_date"]
        if policy == "B" and is_zero_duration:
            continue

        if policy == "C":
            implied = _period_label_implied_years(r["period_label"])
            actual_start_year = _to_date(r["start_date"]).year
            actual_end_year = _to_date(r["end_date"]).year if r["end_date"] else None
            if implied is not None and implied != (actual_start_year, actual_end_year):
                # The label disagrees with the dates - use its year range
                # at year (not day) granularity, since that's all the
                # label encodes. Not exercised on the live workbook: see
                # equity_share_time_period_analysis(), 0 disagreements
                # found across all 7,683 rows.
                s = date(implied[0], 1, 1)
                e = date(implied[1], 12, 31)
            else:
                s = _to_date(r["start_date"])
                e = _to_date(r["end_date"]) if r["end_date"] else None
        else:
            s = _to_date(r["start_date"])
            e = _to_date(r["end_date"]) if r["end_date"] else None

        if s <= month and (e is None or month < e):
            active.append(r)
    return active


def run_interval_policy(rows: list[dict], policy: str, latest: date = LATEST_AVAILABLE_MONTH) -> dict:
    """Diagnostic only: computes field-month aggregate statistics under one
    containment policy. Never persisted per (field, month, company) -
    that's the real interval join's job (spec section 15.8 step 4), not
    this step's."""
    by_field: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_field[r["field_name"]].append(r)

    total_field_months = 0
    zero_active = 0
    sum_ok = 0
    sum_over = 0
    sum_under = 0
    company_overlap_field_months = 0
    zero_duration_rows_ever_active = 0
    failures = []
    excluded_future_only_fields = []

    for field, field_rows in by_field.items():
        min_start = min(_to_date(r["start_date"]) for r in field_rows)
        if _month_start(min_start) > latest:
            excluded_future_only_fields.append(field)
            continue
        for month in _month_range(min_start, latest):
            active = _active_rows_for_month(field_rows, month, policy)
            total_field_months += 1
            if not active:
                zero_active += 1
                continue
            total_pct = sum(r["interest_pct"] for r in active)
            companies = [r["company_name"] for r in active]
            if len(companies) != len(set(companies)):
                company_overlap_field_months += 1
            if any(r["start_date"] == r["end_date"] for r in active):
                zero_duration_rows_ever_active += 1
            if abs(total_pct - 100.0) <= 0.5:
                sum_ok += 1
            else:
                if total_pct > 100.5:
                    sum_over += 1
                else:
                    sum_under += 1
                failures.append((field, month.isoformat(), round(total_pct, 2), len(active)))

    failures.sort(key=lambda f: -abs(f[2] - 100))
    return {
        "policy": policy,
        "total_field_months": total_field_months,
        "zero_active_field_months": zero_active,
        "sum_ok_field_months": sum_ok,
        "sum_over_100_field_months": sum_over,
        "sum_under_100_field_months": sum_under,
        "company_overlap_field_months": company_overlap_field_months,
        "zero_duration_rows_ever_active": zero_duration_rows_ever_active,
        "excluded_future_only_fields": excluded_future_only_fields,
        "worst_failures": failures[:15],
    }


# ---------------------------------------------------------------------------
# 3. Equity Share Time Period inspection
# ---------------------------------------------------------------------------


def equity_share_time_period_analysis(rows: list[dict]) -> dict:
    matched_current = matched_previous = 0
    unmatched = []
    mismatches = []
    for r in rows:
        label = r["period_label"]
        if PERIOD_LABEL_CURRENT.match(label):
            matched_current += 1
            if r["end_date"] is not None:
                mismatches.append((r, "labelled Current but has a non-null end_date"))
            continue
        m = PERIOD_LABEL_PREVIOUS.match(label)
        if not m:
            unmatched.append(label)
            continue
        matched_previous += 1
        y1, y2 = int(m.group(1)), int(m.group(2))
        start_year = _to_date(r["start_date"]).year if r["start_date"] else None
        end_year = _to_date(r["end_date"]).year if r["end_date"] else None
        if (y1, y2) != (start_year, end_year):
            mismatches.append((r, f"label years ({y1},{y2}) != date years ({start_year},{end_year})"))

    return {
        "total_rows": len(rows),
        "matched_current_format": matched_current,
        "matched_previous_format": matched_previous,
        "unmatched_format": len(unmatched),
        "unmatched_samples": Counter(unmatched).most_common(10),
        "mismatches_with_parsed_dates": len(mismatches),
        "mismatch_examples": [(r["field_name"], r["company_name"], r["period_label"], reason) for r, reason in mismatches[:10]],
    }


# ---------------------------------------------------------------------------
# 4. Zero-interest / operator-flag analysis
# ---------------------------------------------------------------------------


def zero_interest_operator_flag_analysis(rows: list[dict]) -> dict:
    by_field: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_field[r["field_name"]].append(r)

    zero_interest = [r for r in rows if r["interest_pct"] == 0]
    zero_interest_operator = [r for r in zero_interest if r["operator_flag"] == "Y"]

    def other_company_overlaps_with_positive_interest(r) -> bool:
        r_end = r["end_date"] or "9999-99"
        for peer in by_field[r["field_name"]]:
            if peer is r or peer["company_name"] == r["company_name"] or peer["interest_pct"] <= 0:
                continue
            peer_end = peer["end_date"] or "9999-99"
            if peer["start_date"] < r_end and r["start_date"] < peer_end:
                return True
        return False

    def same_company_has_positive_row_elsewhere(r) -> bool:
        return any(
            peer["interest_pct"] > 0
            for peer in by_field[r["field_name"]]
            if peer is not r and peer["company_name"] == r["company_name"]
        )

    overlap_count = sum(1 for r in zero_interest_operator if other_company_overlaps_with_positive_interest(r))
    same_company_elsewhere_count = sum(1 for r in zero_interest_operator if same_company_has_positive_row_elsewhere(r))

    return {
        "total_zero_interest_rows": len(zero_interest),
        "zero_interest_with_operator_flag_y": len(zero_interest_operator),
        "zero_interest_open_ended": sum(1 for r in zero_interest if r["end_date"] is None),
        "zero_interest_closed": sum(1 for r in zero_interest if r["end_date"] is not None),
        "zero_interest_opflag_y_open_ended": sum(1 for r in zero_interest_operator if r["end_date"] is None),
        "zero_interest_opflag_y_closed": sum(1 for r in zero_interest_operator if r["end_date"] is not None),
        "opflag_y_rows_where_another_company_holds_overlapping_positive_interest": overlap_count,
        "opflag_y_rows_with_no_overlapping_positive_interest_elsewhere": len(zero_interest_operator) - overlap_count,
        "opflag_y_rows_where_same_company_holds_positive_interest_elsewhere": same_company_elsewhere_count,
        "status_distribution": dict(Counter(r["status"] for r in zero_interest_operator)),
        "top_fields": Counter(r["field_name"] for r in zero_interest_operator).most_common(10),
        "top_organisations": Counter(r["company_name"] for r in zero_interest_operator).most_common(10),
    }


# ---------------------------------------------------------------------------
# 5. Future-dated rows
# ---------------------------------------------------------------------------


def future_dated_row_analysis(rows: list[dict], as_of: date = LATEST_AVAILABLE_MONTH) -> list[dict]:
    by_field: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_field[r["field_name"]].append(r)

    cutoff = as_of.isoformat()
    future = [r for r in rows if r["start_date"] and r["start_date"] >= f"{as_of.year + 1}-01-01"]

    detail = []
    for r in future:
        peers = [p for p in by_field[r["field_name"]] if p is not r]
        currently_open_peers = [p for p in peers if p["end_date"] is None and p["start_date"] <= cutoff]
        detail.append(
            {
                "field_name": r["field_name"],
                "company_name": r["company_name"],
                "interest_pct": r["interest_pct"],
                "start_date": r["start_date"],
                "end_date": r["end_date"],
                "status": r["status"],
                "operator_flag": r["operator_flag"],
                "period_label": r["period_label"],
                "other_rows_same_field": [
                    {"company_name": p["company_name"], "start_date": p["start_date"], "end_date": p["end_date"], "interest_pct": p["interest_pct"]}
                    for p in peers
                ],
                "overlaps_a_currently_open_interval": len(currently_open_peers) > 0,
            }
        )
    return detail


# ---------------------------------------------------------------------------
# 6. Open-ended interval diagnostics
# ---------------------------------------------------------------------------


def open_ended_diagnostics(rows: list[dict], as_of: date = LATEST_AVAILABLE_MONTH) -> dict:
    by_field: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_field[r["field_name"]].append(r)

    open_ended = [r for r in rows if r["end_date"] is None]
    open_by_field: dict[str, list[dict]] = defaultdict(list)
    for r in open_ended:
        open_by_field[r["field_name"]].append(r)

    fields_with_multi_open_positive = 0
    fields_with_same_company_overlapping_open = []
    for field, rs in open_by_field.items():
        positive = [r for r in rs if r["interest_pct"] > 0]
        if len(positive) > 1:
            fields_with_multi_open_positive += 1
        companies = [r["company_name"] for r in rs]
        if len(companies) != len(set(companies)):
            fields_with_same_company_overlapping_open.append(field)

    cutoff = as_of.isoformat()
    sum_ok = sum_bad = no_current_active = 0
    bad_examples = []
    for field, rs in by_field.items():
        active = [r for r in rs if r["end_date"] is None and r["start_date"] <= cutoff]
        if not active:
            no_current_active += 1
            continue
        total = sum(r["interest_pct"] for r in active)
        if abs(total - 100) <= 0.5:
            sum_ok += 1
        else:
            sum_bad += 1
            bad_examples.append((field, round(total, 2), len(active)))

    future = [r for r in rows if r["start_date"] and r["start_date"] >= f"{as_of.year + 1}-01-01"]
    future_overlap_examples = []
    for r in future:
        currently_open_peers = [
            p for p in by_field[r["field_name"]] if p is not r and p["end_date"] is None and p["start_date"] <= cutoff
        ]
        future_overlap_examples.append((r["field_name"], r["company_name"], len(currently_open_peers)))

    return {
        "total_open_ended_rows": len(open_ended),
        "fields_with_any_open_ended_row": len(open_by_field),
        "fields_with_multiple_open_ended_positive_interest_rows": fields_with_multi_open_positive,
        "fields_with_same_company_overlapping_open_ended_rows": fields_with_same_company_overlapping_open,
        "fields_current_sum_ok": sum_ok,
        "fields_current_sum_not_100pm0_5pp": sum_bad,
        "fields_with_no_current_open_row_at_all": no_current_active,
        "bad_sum_examples": bad_examples[:15],
        "future_dated_rows_overlapping_a_currently_open_interval": [f for f in future_overlap_examples if f[2] > 0],
        "future_dated_rows_not_overlapping_anything_current": [f for f in future_overlap_examples if f[2] == 0],
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def build_diagnostics_report(rows: list[dict]) -> str:
    zd = classify_zero_duration_rows(rows)
    policy_a = run_interval_policy(rows, "A")
    policy_b = run_interval_policy(rows, "B")
    policy_c = run_interval_policy(rows, "C")
    period_analysis = equity_share_time_period_analysis(rows)
    zi_analysis = zero_interest_operator_flag_analysis(rows)
    future_detail = future_dated_row_analysis(rows)
    open_ended = open_ended_diagnostics(rows)

    lines = [
        "# Equity interval-semantics diagnostic report",
        "",
        "Diagnostic only. No PPRS join, no equity-attributable production, no company "
        "production, no docs/data/equity artifacts. See etl/equity_interval_diagnostics.py.",
        "",
        "## 1. Zero-duration intervals (start_date == end_date)",
        "",
        f"- Total: {zd['total_zero_duration_rows']} rows across {zd['distinct_fields']} fields "
        f"and {zd['distinct_companies']} companies.",
        f"- Classification: {zd['category_counts']}",
        f"- Interest % bucket: {zd['interest_pct_bucket']}",
        f"- Operator Flag distribution: {zd['operator_flag_distribution']}",
        f"- Status distribution: {zd['status_distribution']}",
        f"- On Offshore distribution: {zd['on_offshore_distribution']}",
        f"- Top 15 exact dates by frequency: {zd['top_exact_dates']}",
        "",
        "## 2. Interval policy comparison (A / B / C)",
        "",
    ]
    for label, p in [("A (literal half-open, no special-casing)", policy_a), ("B (zero-duration rows explicitly filtered)", policy_b), ("C (Equity Share Time Period preferred on conflict)", policy_c)]:
        lines += [
            f"### Policy {label}",
            "",
            f"- Field-months evaluated: {p['total_field_months']}",
            f"- Zero active interests: {p['zero_active_field_months']}",
            f"- Sum within 100% +-0.5pp: {p['sum_ok_field_months']}",
            f"- Sum over 100.5%: {p['sum_over_100_field_months']}",
            f"- Sum under 99.5%: {p['sum_under_100_field_months']}",
            f"- Field-months with a same-company overlap: {p['company_overlap_field_months']}",
            f"- Zero-duration rows ever counted active: {p['zero_duration_rows_ever_active']}",
            f"- Fields excluded (only future-dated rows, entirely outside the grid): {p['excluded_future_only_fields']}",
            f"- Worst failures: {p['worst_failures']}",
            "",
        ]
    lines += [
        "**Policies A and B are numerically identical on this dataset.** A zero-duration "
        "interval `[d, d)` is empty under the half-open convention regardless of whether it "
        "is explicitly filtered first - no month can ever satisfy `start <= month < end` when "
        "`start == end`. The distinction is documentation/intent, not outcome.",
        "",
        "**Policy C is also numerically identical to A on this dataset**, because the Equity "
        "Share Time Period label never actually disagrees with the parsed dates - see section 3.",
        "",
        "The one genuine anomaly found (ROCHELLE, 2011-08, summing to 200% across 5 companies) "
        "is **not** a zero-duration artifact: it is a real overlapping-interval data error - two "
        "companies' rows both cover 2011-08 (one interval ends 2011-08-31, the next for the same "
        "companies starts 2011-08-01, a genuine one-month overlap, not an adjacency).",
        "",
        "## 3. Equity Share Time Period",
        "",
        f"- {period_analysis['matched_current_format']} rows exactly match `Current`; "
        f"{period_analysis['matched_previous_format']} exactly match `Previous-YYYY to YYYY`; "
        f"{period_analysis['unmatched_format']} match neither format.",
        f"- Rows where the label's year range disagrees with the parsed Start/End Date years: "
        f"{period_analysis['mismatches_with_parsed_dates']} (of {period_analysis['total_rows']}).",
        "",
        "**Finding: the column is fully derived from Start Date and End Date at year "
        "granularity, with zero exceptions.** `Current` means `end_date is None`; "
        "`Previous-Y1 to Y2` means `start_date.year == Y1 and end_date.year == Y2`, always. It "
        "carries no information not already in the two date columns, cannot explain the "
        "zero-duration rows (a `Previous-Y to Y` label there is a trivial consequence of "
        "start_date == end_date, not independent corroboration), and never conflicts with the "
        "dates - there is nothing for Policy C to override on the live workbook. It should be "
        "**retained as source metadata only**, never used in interval resolution: it is strictly "
        "less precise (year, not day) than the date columns it is derived from, and parsing it "
        "would only reintroduce a risk (a future row that violates the pattern) for zero benefit.",
        "",
        "## 4. Zero-interest rows and Operator Flag",
        "",
        f"- Zero-interest rows: {zi_analysis['total_zero_interest_rows']} "
        f"({zi_analysis['zero_interest_open_ended']} open-ended, {zi_analysis['zero_interest_closed']} closed).",
        f"- Of those, {zi_analysis['zero_interest_with_operator_flag_y']} also have Operator Flag = 'Y' "
        f"({zi_analysis['zero_interest_opflag_y_open_ended']} open-ended, "
        f"{zi_analysis['zero_interest_opflag_y_closed']} closed).",
        f"- {zi_analysis['opflag_y_rows_where_another_company_holds_overlapping_positive_interest']} of those "
        f"{zi_analysis['zero_interest_with_operator_flag_y']} rows overlap a DIFFERENT company's positive-interest "
        f"row for the same field during the same period "
        f"({zi_analysis['opflag_y_rows_with_no_overlapping_positive_interest_elsewhere']} do not).",
        f"- {zi_analysis['opflag_y_rows_where_same_company_holds_positive_interest_elsewhere']} of those rows "
        "belong to a company that ALSO holds a positive-interest row for the same field, in a different period.",
        f"- Status distribution: {zi_analysis['status_distribution']}",
        f"- Top fields: {zi_analysis['top_fields']}",
        f"- Top organisations: {zi_analysis['top_organisations']}",
        "",
        "**Finding: Operator Flag represents operatorship independently of economic interest.** "
        "The large majority (86%) of zero-interest, Operator Flag='Y' rows coincide with another "
        "company holding the real equity for the same period - i.e. a company can be recorded as "
        "the field's operator with a 0% ownership stake while a different company (or companies) "
        "hold the interest. This is consistent with real industry arrangements (e.g. a technical "
        "operator without an economic stake) and confirms the instruction not to infer a positive "
        "interest from Operator Flag = 'Y'. Per the milestone-1 default: zero-interest rows are "
        "retained as source records but excluded from any equity-weighted sum, since multiplying "
        "production by 0% contributes no volume regardless of Operator Flag.",
        "",
        "## 5. Future-dated rows",
        "",
    ]
    for r in future_detail:
        lines.append(f"### {r['field_name']} / {r['company_name']}")
        lines.append("")
        lines.append(
            f"- interest_pct={r['interest_pct']}, start_date={r['start_date']}, end_date={r['end_date']}, "
            f"status={r['status']!r}, operator_flag={r['operator_flag']!r}, period_label={r['period_label']!r}"
        )
        lines.append(f"- Other rows for this field: {r['other_rows_same_field'] or '(none - this is the only row this field has)'}")
        lines.append(f"- Overlaps a currently-open interval: {r['overlaps_a_currently_open_interval']}")
        lines.append("")
    lines += [
        "**Finding: all 4 future-dated rows are each the ONLY equity row for their field** "
        "(ALVHEIM, STATFJORD(CROSS BORDER)) or share the field with only the other future-dated "
        "row (MURLACH's two rows, which sum to 100% between them but both start 2050-01-04). None "
        "overlaps a currently-open interval, because none of these fields has any other row at all. "
        "**As of the diagnostic's anchor month (2026-09), these 3 fields have zero active equity "
        "coverage under any policy** - not because of a data error, but because their only recorded "
        "interval(s) genuinely start in the future.",
        "",
        "**Recommendation: retain, but inactive until the start date, under the policy already in "
        "use** (Policy A's literal half-open test already does this correctly with no special-casing "
        "- a row with a future start_date simply never satisfies `start_date <= month_start` for any "
        "month up to and including now). Quarantining would require inventing a rule these rows "
        "don't actually need: the existing containment test already produces the correct behaviour "
        "(no current coverage) without singling them out. The only action needed is a validation "
        "rule that does not treat 'no current equity row' as build-breaking for a field whose only "
        "row(s) are future-dated (see the revised E5 proposal below) - treating it as an unresolved "
        "gap would be wrong, since the gap is real and explained, not a parse or matching error.",
        "",
        "## 6. Open-ended interval diagnostics",
        "",
        f"- Open-ended rows: {open_ended['total_open_ended_rows']} across {open_ended['fields_with_any_open_ended_row']} fields.",
        f"- Fields with more than one open-ended POSITIVE-interest row (multiple current "
        f"partners - expected/normal): {open_ended['fields_with_multiple_open_ended_positive_interest_rows']}.",
        f"- Fields where the SAME company holds more than one open-ended row (a genuine overlap "
        f"anomaly, distinct from multiple different partners): "
        f"{len(open_ended['fields_with_same_company_overlapping_open_ended_rows'])} "
        f"({open_ended['fields_with_same_company_overlapping_open_ended_rows']}).",
        f"- Fields whose currently-open interests sum to 100% +-0.5pp: {open_ended['fields_current_sum_ok']}.",
        f"- Fields whose currently-open interests do NOT sum to 100% +-0.5pp: {open_ended['fields_current_sum_not_100pm0_5pp']} "
        f"(examples: {open_ended['bad_sum_examples']}).",
        f"- Fields with no current open row at all: {open_ended['fields_with_no_current_open_row_at_all']} "
        "(the 3 future-dated-only fields from section 5).",
        f"- Future-dated rows that overlap a currently-open interval: "
        f"{open_ended['future_dated_rows_overlapping_a_currently_open_interval']} (none found).",
        "",
        "## 7. Proposed corrected validation rules",
        "",
        "See the accompanying investigation summary for full rationale. Corrected proposals:",
        "",
        "- **E1** (interest sums to 100% for a field-month with production > 0): unchanged in "
        "intent, but must explicitly exclude zero-duration rows from the summed set (they "
        "already are, under a literal half-open test) and must not fail solely because a field's "
        "only equity row(s) are future-dated - that is E6/E5's concern (coverage), not E1's "
        "(sum correctness of whatever *is* active).",
        "- **E4** (no overlapping intervals for the same field/company): keep, but scope it to "
        "same-(field, company) overlaps only, as the ROCHELLE case demonstrates a real violation "
        "exists (CNOOC and HARBOUR ENERGY WPUK rows for ROCHELLE overlap by one month in 2011) - "
        "this is exactly the case E4 should be catching, not an edge case to special-case away.",
        "- **E5** (no coverage gaps): must not fire on a field whose only equity row(s) have a "
        "future start_date (ALVHEIM, MURLACH, STATFJORD(CROSS BORDER)) - that gap is real and "
        "explained, not a data problem. Should distinguish 'gap because a field genuinely has no "
        "equity row covering this month yet' from 'gap because of a parse/matching failure'.",
        "- **E7** (start_date < end_date, strict): **cannot remain build-breaking as worded** - "
        "838 rows violate it. Replace with a rule that accepts start_date <= end_date, and treats "
        "start_date == end_date rows as **non-interest-bearing event records** (per section 1's "
        "classification) rather than errors: they never contribute to E1's sum (they cannot, "
        "under half-open containment) and should not fail the build. A stricter start_date < "
        "end_date check should apply only to rows that are NOT zero-duration.",
        "",
        "## 8. Not yet resolved",
        "",
        f"- The {zd['category_counts'].get('boundary_transition', 0)} 'boundary_transition' "
        "zero-duration rows (pct differs from the adjacent substantive row at the same instant) "
        "are not fully explained - they may represent a genuine instantaneous same-day "
        "step-change, or a data-entry artifact. Not required to resolve for the field-matching or "
        "latest-period-coverage work already approved; flagged for whoever writes the real "
        "interval join.",
        "- The 16 'standalone_snapshot' rows cluster by date and company across unrelated fields "
        "(e.g. CNR INTERNATIONAL at THELMA/TIFFANY/TONI, all dated 2003-05-01), suggesting a "
        "shared external event rather than field-specific activity, but the specific event is not "
        "identified from this data alone.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    rows = load_raw_rows()
    report = build_diagnostics_report(rows)
    DIAGNOSTICS_REPORT_PATH.write_text(report)
    print(report)
    print(f"\nDiagnostics report written to {DIAGNOSTICS_REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
