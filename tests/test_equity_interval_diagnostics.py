"""
Unit tests for etl/equity_interval_diagnostics.py (Phase 2 interval
semantics investigation, preceding spec section 15.8 step 4).

Uses small synthetic row sets rather than the live 7,683-row workbook, so
these run offline and deterministically. The diagnostic resolver under
test is explicitly NOT the production/equity calculation code - none
exists yet - and these tests never touch PPRS, docs/data, or build.py.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.equity_interval_diagnostics import (  # noqa: E402
    classify_zero_duration_rows,
    equity_share_time_period_analysis,
    future_dated_row_analysis,
    open_ended_diagnostics,
    run_interval_policy,
    zero_interest_operator_flag_analysis,
)


def _row(field, company, pct, start, end, status="700 - PRODUCING", opflag="N", period_label=None, offshore="Offshore"):
    if period_label is None:
        if end is None:
            period_label = "Current"
        else:
            period_label = f"Previous-{start[:4]} to {end[:4]}"
    return {
        "field_name": field,
        "on_offshore": offshore,
        "status": status,
        "company_name": company,
        "interest_pct": float(pct),
        "operator_flag": opflag,
        "start_date": start,
        "end_date": end,
        "period_label": period_label,
    }


def test_normal_closed_interval_is_active_within_its_range():
    rows = [_row("ALPHA", "ACME", 100, "2020-01-01", "2020-06-01")]
    result = run_interval_policy(rows, "A", latest=date(2020, 12, 1))
    # Active for Jan-May (5 months), inactive Jun onward (end is exclusive), zero-active thereafter.
    assert result["sum_ok_field_months"] == 5
    assert result["zero_active_field_months"] == 7  # Jun..Dec


def test_open_ended_interval_stays_active_through_latest_month():
    rows = [_row("ALPHA", "ACME", 100, "2020-01-01", None)]
    result = run_interval_policy(rows, "A", latest=date(2020, 6, 1))
    assert result["sum_ok_field_months"] == 6
    assert result["zero_active_field_months"] == 0


def test_zero_duration_row_never_counts_as_active_under_policy_a():
    rows = [
        _row("ALPHA", "ACME", 100, "2020-01-01", "2020-03-01"),
        _row("ALPHA", "ACME", 100, "2020-03-01", "2020-03-01"),  # zero-duration
        _row("ALPHA", "ACME", 100, "2020-03-01", "2020-06-01"),
    ]
    result = run_interval_policy(rows, "A", latest=date(2020, 6, 1))
    assert result["zero_duration_rows_ever_active"] == 0
    # Jan, Feb (first interval) + Mar, Apr, May (second interval) = 5 months at 100%.
    assert result["sum_ok_field_months"] == 5


def test_adjacent_ownership_intervals_sum_correctly_at_the_boundary():
    """Two intervals for different companies meeting exactly at a boundary
    (one ends where the other starts) must never double-count that month."""
    rows = [
        _row("ALPHA", "ACME", 60, "2020-01-01", "2020-04-01"),
        _row("ALPHA", "BETA", 40, "2020-01-01", "2020-04-01"),
        _row("ALPHA", "ACME", 30, "2020-04-01", "2020-07-01"),
        _row("ALPHA", "GAMMA", 70, "2020-04-01", "2020-07-01"),
    ]
    result = run_interval_policy(rows, "A", latest=date(2020, 7, 1))
    assert result["sum_ok_field_months"] == 6
    assert result["sum_over_100_field_months"] == 0
    assert result["company_overlap_field_months"] == 0


def test_overlapping_ownership_intervals_are_detected():
    """A genuine overlap (like the live ROCHELLE case) must show up as a
    sum-over-100 and a same-company overlap flag."""
    rows = [
        _row("ALPHA", "ACME", 60, "2020-01-01", "2020-05-01"),
        _row("ALPHA", "ACME", 60, "2020-04-01", "2020-07-01"),  # overlaps Apr
        _row("ALPHA", "BETA", 40, "2020-01-01", "2020-07-01"),
    ]
    result = run_interval_policy(rows, "A", latest=date(2020, 7, 1))
    assert result["company_overlap_field_months"] == 1
    assert result["sum_over_100_field_months"] == 1
    field, month, total, n_active = result["worst_failures"][0]
    assert field == "ALPHA"
    assert month == "2020-04-01"
    assert total == 160.0


def test_zero_interest_operator_row_does_not_imply_positive_interest():
    rows = [
        _row("ALPHA", "OPERATOR_CO", 0, "2020-01-01", None, opflag="Y"),
        _row("ALPHA", "PARTNER_CO", 100, "2020-01-01", None, opflag="N"),
    ]
    analysis = zero_interest_operator_flag_analysis(rows)
    assert analysis["total_zero_interest_rows"] == 1
    assert analysis["zero_interest_with_operator_flag_y"] == 1
    assert analysis["opflag_y_rows_where_another_company_holds_overlapping_positive_interest"] == 1


def test_future_dated_interval_is_flagged_and_has_zero_current_coverage():
    rows = [_row("ALPHA", "FUTURE_CO", 100, "2030-05-01", None)]
    detail = future_dated_row_analysis(rows, as_of=date(2026, 9, 1))
    assert len(detail) == 1
    assert detail[0]["field_name"] == "ALPHA"
    assert detail[0]["overlaps_a_currently_open_interval"] is False

    diag = open_ended_diagnostics(rows, as_of=date(2026, 9, 1))
    assert diag["fields_with_no_current_open_row_at_all"] == 1


def test_period_label_conflicting_with_dates_is_detected():
    rows = [
        _row("ALPHA", "ACME", 100, "2020-01-01", "2020-06-01", period_label="Previous-1999 to 1999"),
        _row("BETA", "ACME", 100, "2020-01-01", None, period_label="Current"),
    ]
    analysis = equity_share_time_period_analysis(rows)
    assert analysis["mismatches_with_parsed_dates"] == 1
    assert analysis["mismatch_examples"][0][0] == "ALPHA"


def test_period_label_matching_dates_produces_no_mismatch():
    rows = [_row("ALPHA", "ACME", 100, "2020-01-01", "2020-06-01")]
    analysis = equity_share_time_period_analysis(rows)
    assert analysis["mismatches_with_parsed_dates"] == 0


def test_zero_duration_classification_boundary_duplicate():
    """A zero-duration row whose pct matches the substantive interval that
    starts at the same instant (here, also matching a preceding interval)
    is a boundary duplicate - fully redundant with the substantive row."""
    rows = [
        _row("ALPHA", "ACME", 60, "2019-01-01", "2020-01-01"),
        _row("ALPHA", "ACME", 60, "2020-01-01", "2020-01-01"),  # zero-duration
        _row("ALPHA", "ACME", 60, "2020-01-01", "2020-06-01"),
    ]
    result = classify_zero_duration_rows(rows)
    assert result["total_zero_duration_rows"] == 1
    assert result["category_counts"] == {"boundary_duplicate": 1}


def test_zero_duration_classification_boundary_transition():
    rows = [
        _row("ALPHA", "ACME", 50, "2019-01-01", "2020-01-01"),
        _row("ALPHA", "ACME", 55, "2020-01-01", "2020-01-01"),  # zero-duration, pct differs
        _row("ALPHA", "ACME", 60, "2020-01-01", "2020-06-01"),
    ]
    result = classify_zero_duration_rows(rows)
    assert result["category_counts"] == {"boundary_transition": 1}


def test_zero_duration_classification_termination_marker():
    rows = [
        _row("ALPHA", "ACME", 100, "2019-01-01", "2020-01-01"),
        _row("ALPHA", "ACME", 0, "2020-01-01", "2020-01-01", status="900 - PRODUCTION CEASED"),
    ]
    result = classify_zero_duration_rows(rows)
    assert result["category_counts"] == {"termination_marker": 1}


def test_zero_duration_classification_standalone_snapshot():
    rows = [_row("ALPHA", "ACME", 40, "2020-01-01", "2020-01-01")]
    result = classify_zero_duration_rows(rows)
    assert result["category_counts"] == {"standalone_snapshot": 1}


def test_policies_a_and_b_agree_on_zero_duration_rows():
    """Explicitly filtering zero-duration rows (Policy B) must never change
    the numeric outcome versus the literal half-open test (Policy A) - a
    zero-duration interval is already empty under half-open containment."""
    rows = [
        _row("ALPHA", "ACME", 100, "2020-01-01", "2020-03-01"),
        _row("ALPHA", "ACME", 100, "2020-03-01", "2020-03-01"),
        _row("ALPHA", "ACME", 100, "2020-03-01", "2020-06-01"),
    ]
    result_a = run_interval_policy(rows, "A", latest=date(2020, 6, 1))
    result_b = run_interval_policy(rows, "B", latest=date(2020, 6, 1))
    assert result_a["sum_ok_field_months"] == result_b["sum_ok_field_months"]
    assert result_a["zero_active_field_months"] == result_b["zero_active_field_months"]


def test_diagnostic_report_is_deterministic():
    from etl.equity_interval_diagnostics import build_diagnostics_report

    rows = [
        _row("ALPHA", "ACME", 100, "2020-01-01", "2020-06-01"),
        _row("ALPHA", "ACME", 100, "2020-06-01", "2020-06-01"),
        _row("BETA", "ACME", 100, "2020-01-01", None),
    ]
    report_a = build_diagnostics_report(rows)
    report_b = build_diagnostics_report(rows)
    assert report_a == report_b
