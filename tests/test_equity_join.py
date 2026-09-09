"""
Unit tests for etl/equity_join.py (spec section 15.8 step 4, latest-period
checkpoint only).

Uses small synthetic field/company data rather than the live workbook, so
these run offline and deterministically. Exercises the approved policy
decisions directly: half-open containment, zero-duration rows as inert
source events, zero-interest exclusion, future-dated inactivity, and
quarantine-not-repair for genuine overlaps (the ROCHELLE case).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.equity_join import (  # noqa: E402
    build_company_summary,
    build_field_match_index,
    build_resolution,
    build_resolved_grain_rows,
    check_e1,
    check_e4,
    check_e5,
    check_e7,
    check_e8,
    resolve_field_month,
)


def _row(field, company, pct, start, end, opflag="N", status="700 - PRODUCING", period_label=None):
    if period_label is None:
        period_label = "Current" if end is None else f"Previous-{start[:4]} to {end[:4]}"
    return {
        "field_name": field,
        "on_offshore": "Offshore",
        "status": status,
        "company_name": company,
        "interest_pct": float(pct),
        "operator_flag": opflag,
        "start_date": start,
        "end_date": end,
        "period_label": period_label,
    }


def _production(oil=10.0, dry_gas=0.0, assoc_gas=0.0, condensate=0.0):
    return {"oil_mbd": oil, "dry_gas_mmscfd": dry_gas, "assoc_gas_mmscfd": assoc_gas, "condensate_mbd": condensate}


MONTH = date(2026, 6, 1)


def test_normal_100pct_single_owner_field():
    rows = [_row("ALPHA", "ACME", 100, "2020-01-01", None)]
    result = resolve_field_month(rows, MONTH)
    assert result["positive_interest_sum"] == 100.0
    assert not result["overlap"]
    assert len(result["active_rows"]) == 1


def test_normal_multi_partner_field_sums_to_100():
    rows = [
        _row("ALPHA", "ACME", 60, "2020-01-01", None),
        _row("ALPHA", "BETA", 40, "2020-01-01", None),
    ]
    result = resolve_field_month(rows, MONTH)
    assert result["positive_interest_sum"] == 100.0
    assert not result["overlap"]


def test_interest_sum_below_100_is_not_an_overlap():
    rows = [_row("ALPHA", "ACME", 60, "2020-01-01", None)]
    result = resolve_field_month(rows, MONTH)
    assert result["positive_interest_sum"] == 60.0
    assert not result["overlap"]


def test_interest_sum_above_100_is_flagged_overlap():
    rows = [
        _row("ALPHA", "ACME", 70, "2020-01-01", None),
        _row("ALPHA", "BETA", 70, "2020-01-01", None),
    ]
    result = resolve_field_month(rows, MONTH)
    assert result["positive_interest_sum"] == 140.0
    assert result["overlap"]


def test_same_company_overlapping_intervals_detected():
    rows = [
        _row("ALPHA", "ACME", 50, "2020-01-01", "2027-01-01"),
        _row("ALPHA", "ACME", 50, "2026-01-01", None),  # overlaps the first at MONTH
    ]
    result = resolve_field_month(rows, MONTH)
    assert result["same_company_overlap"] == {"ACME": 2}
    assert result["overlap"]


def test_different_company_field_month_total_above_100():
    rows = [
        _row("ALPHA", "ACME", 60, "2020-01-01", None),
        _row("ALPHA", "BETA", 60, "2020-01-01", None),
    ]
    result = resolve_field_month(rows, MONTH)
    assert not result["same_company_overlap"]
    assert result["overlap"]  # caught by the cross-company sum check, not a same-company duplicate


def test_zero_interest_operator_row_excluded_from_sum_but_present():
    rows = [
        _row("ALPHA", "OPERATOR_CO", 0, "2020-01-01", None, opflag="Y"),
        _row("ALPHA", "PARTNER_CO", 100, "2020-01-01", None, opflag="N"),
    ]
    result = resolve_field_month(rows, MONTH)
    assert result["positive_interest_sum"] == 100.0  # OPERATOR_CO's 0% does not affect the sum
    assert len(result["active_rows"]) == 2  # but the row is still present/active
    assert not result["overlap"]


def test_zero_duration_row_never_active():
    rows = [
        _row("ALPHA", "ACME", 100, "2020-01-01", "2026-06-01"),
        _row("ALPHA", "ACME", 100, "2026-06-01", "2026-06-01"),  # zero-duration, at month_start
        _row("ALPHA", "ACME", 100, "2026-06-01", None),
    ]
    result = resolve_field_month(rows, MONTH)
    # The zero-duration row's own interval [2026-06-01, 2026-06-01) is empty and
    # never satisfies containment; the open-ended row starting the same date does.
    assert result["positive_interest_sum"] == 100.0
    zero_duration_active = [r for r in result["active_rows"] if r["start_date"] == r["end_date"]]
    assert zero_duration_active == []


def test_open_ended_interval_active_indefinitely():
    rows = [_row("ALPHA", "ACME", 100, "2020-01-01", None)]
    far_future = date(2040, 1, 1)
    result = resolve_field_month(rows, far_future)
    assert result["positive_interest_sum"] == 100.0


def test_future_only_field_categorised_not_a_failure():
    field_match_index = {"ALPHA": ("ALPHA", "exact")}
    raw_rows_by_equity_field = {"ALPHA": [_row("ALPHA", "ACME", 100, "2030-05-01", None)]}
    latest_production = {"ALPHA": _production()}
    resolutions = build_resolution(field_match_index, raw_rows_by_equity_field, latest_production, MONTH)
    assert resolutions["ALPHA"]["category"] == "future_only"

    e1 = check_e1(resolutions)
    assert e1["failing_field_count"] == 0  # future-only is not an E1 failure

    e5 = check_e5(resolutions)
    assert "ALPHA" in e5["future_only"]
    assert "ALPHA" not in e5["unresolved_gap"]


def test_unmatched_field_categorised_separately():
    field_match_index = {}  # ALPHA has no equity match
    latest_production = {"ALPHA": _production()}
    resolutions = build_resolution(field_match_index, {}, latest_production, MONTH)
    assert resolutions["ALPHA"]["category"] == "unmatched"
    e5 = check_e5(resolutions)
    assert "ALPHA" in e5["unmatched"]


def test_explicit_alias_match_recorded_as_method():
    from etl.equity_match import match_fields

    aliases = [{"pprs_field_name": "OLD NAME", "equity_field_name": "NEW NAME", "note": "", "reviewed_by": "", "reviewed_on": ""}]
    result = match_fields({"OLD NAME"}, {"NEW NAME"}, aliases)
    assert result["alias_matches"] == {"OLD NAME": "NEW NAME"}

    index = build_field_match_index({"OLD NAME"}, {"NEW NAME"}, aliases)
    assert index["OLD NAME"] == ("NEW NAME", "alias")


def test_mid_month_start_not_active_for_that_month():
    rows = [_row("ALPHA", "ACME", 100, "2026-06-15", None)]
    result = resolve_field_month(rows, date(2026, 6, 1))
    assert result["active_rows"] == []
    assert result["positive_interest_sum"] == 0.0


def test_mid_month_end_active_if_valid_at_month_start():
    rows = [_row("ALPHA", "ACME", 100, "2020-01-01", "2026-06-15")]
    result = resolve_field_month(rows, date(2026, 6, 1))
    assert len(result["active_rows"]) == 1
    assert result["positive_interest_sum"] == 100.0


def test_adjacent_half_open_intervals_do_not_overlap():
    rows = [
        _row("ALPHA", "ACME", 100, "2020-01-01", "2026-06-01"),
        _row("ALPHA", "BETA", 100, "2026-06-01", None),
    ]
    result_before = resolve_field_month(rows, date(2026, 5, 1))
    result_at_boundary = resolve_field_month(rows, date(2026, 6, 1))
    assert [r["company_name"] for r in result_before["active_rows"]] == ["ACME"]
    assert [r["company_name"] for r in result_at_boundary["active_rows"]] == ["BETA"]
    assert not result_at_boundary["overlap"]


def test_rochelle_style_quarantine():
    """Reproduces the real August 2011 ROCHELLE 200% case: two rows for the
    same company overlap by one month. The resolver must quarantine it, not
    normalize the two interests or pick one owner."""
    rows = [
        _row("ROCHELLE", "CNOOC PETROLEUM EUROPE LIMITED", 44.39, "2008-03-25", "2011-08-31"),
        _row("ROCHELLE", "HARBOUR ENERGY WPUK LIMITED", 55.61, "2008-03-25", "2011-08-31"),
        _row("ROCHELLE", "CNOOC PETROLEUM EUROPE LIMITED", 41.0, "2011-08-01", "2013-07-01"),
        _row("ROCHELLE", "HARBOUR ENERGY WPUK LIMITED", 44.0, "2011-08-01", "2013-07-01"),
        _row("ROCHELLE", "PREMIER OIL UK LIMITED", 15.0, "2011-08-01", "2013-07-01"),
    ]
    field_match_index = {"ROCHELLE": ("ROCHELLE", "exact")}
    raw_rows_by_equity_field = {"ROCHELLE": rows}
    latest_production = {"ROCHELLE": _production(oil=5.0)}

    resolutions = build_resolution(field_match_index, raw_rows_by_equity_field, latest_production, date(2011, 8, 1))
    res = resolutions["ROCHELLE"]
    assert res["category"] == "quarantined"
    assert "CNOOC PETROLEUM EUROPE LIMITED" in res["reason"]

    resolved_rows = build_resolved_grain_rows(resolutions, latest_production, "201108")
    assert resolved_rows == []  # no equity-attributable result for a quarantined field

    e4 = check_e4(resolutions)
    assert e4["quarantined_field_count"] == 1
    field, reason = e4["quarantined_fields"][0]
    assert field == "ROCHELLE"
    assert "CNOOC PETROLEUM EUROPE LIMITED" in reason or "same-company" in reason

    # The sum must not have been silently normalized back to 100%.
    month_result = resolve_field_month(rows, date(2011, 8, 1))
    assert month_result["positive_interest_sum"] > 100.0


def test_e7_flags_start_after_end_and_permits_zero_duration():
    rows = [
        _row("ALPHA", "ACME", 100, "2020-01-01", "2020-06-01"),  # fine
        _row("BETA", "ACME", 100, "2020-06-01", "2020-06-01"),  # zero-duration, fine (not an E7 violation)
        _row("GAMMA", "ACME", 100, "2020-06-01", "2020-01-01"),  # start > end - violation
    ]
    result = check_e7(rows)
    assert result["passed"] is False
    assert len(result["violations"]) == 1
    assert result["violations"][0][0] == "GAMMA"


def test_e8_conservation_by_stream_and_coverage():
    field_match_index = {"ALPHA": ("ALPHA", "exact"), "BETA": ("BETA", "exact")}
    raw_rows_by_equity_field = {
        "ALPHA": [_row("ALPHA", "ACME", 100, "2020-01-01", None)],
        "BETA": [_row("BETA", "ACME", 100, "2030-05-01", None)],  # future-only, excluded
    }
    latest_production = {
        "ALPHA": _production(oil=10.0, dry_gas=5.0, assoc_gas=2.0, condensate=1.0),
        "BETA": _production(oil=4.0, dry_gas=0.0, assoc_gas=0.0, condensate=0.0),
    }
    resolutions = build_resolution(field_match_index, raw_rows_by_equity_field, latest_production, MONTH)
    resolved_rows = build_resolved_grain_rows(resolutions, latest_production, "202606")
    e8 = check_e8(resolved_rows, resolutions, latest_production)

    assert e8["oil_mbd"]["total_production"] == 14.0
    assert e8["oil_mbd"]["included_production"] == 10.0
    assert e8["oil_mbd"]["excluded_production"] == 4.0
    assert e8["oil_mbd"]["within_tolerance"] is True
    assert e8["oil_mbd"]["coverage_pct"] == round(100.0 * 10.0 / 14.0, 3)

    assert e8["dry_gas_mmscfd"]["coverage_pct"] == 100.0
    assert e8["assoc_gas_mmscfd"]["coverage_pct"] == 100.0
    assert e8["condensate_mbd"]["coverage_pct"] == 100.0


def test_company_summary_is_deterministic_and_sorted():
    field_match_index = {"ALPHA": ("ALPHA", "exact"), "BETA": ("BETA", "exact")}
    raw_rows_by_equity_field = {
        "ALPHA": [_row("ALPHA", "ZETA CO", 60, "2020-01-01", None), _row("ALPHA", "ACME", 40, "2020-01-01", None)],
        "BETA": [_row("BETA", "ACME", 100, "2020-01-01", None)],
    }
    latest_production = {
        "ALPHA": _production(oil=10.0),
        "BETA": _production(oil=5.0),
    }
    resolutions = build_resolution(field_match_index, raw_rows_by_equity_field, latest_production, MONTH)
    resolved_rows = build_resolved_grain_rows(resolutions, latest_production, "202606")

    summary_a = build_company_summary(resolved_rows)
    summary_b = build_company_summary(resolved_rows)
    assert summary_a == summary_b  # deterministic
    assert [c["company_name"] for c in summary_a] == ["ACME", "ZETA CO"]  # sorted

    acme = next(c for c in summary_a if c["company_name"] == "ACME")
    assert acme["producing_field_count"] == 2
    assert acme["oil_mbd"] == round(10.0 * 0.4 + 5.0 * 1.0, 6)
