"""
Unit tests for etl/equity_join_historical.py (full-history diagnostic
checkpoint, spec section 15.8 step 5 - diagnostic only, not integrated
into build.py, no docs/data/equity artifacts).

Uses small synthetic multi-year field/production/equity data rather than
the live 552-field, 133,608-field-month dataset, so these run offline and
deterministically.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.equity_join_historical import (  # noqa: E402
    build_company_summary_historical,
    build_historical_report,
    build_resolved_grain_rows_historical,
    check_e1_historical,
    check_e4_historical,
    check_e7_historical,
    check_e8_historical,
    gap_diagnostics,
    historical_matching_report,
    monthly_coverage,
    resolve_full_history,
)
from etl.equity_join import build_field_match_index


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


def _series(field, periods, oil=10.0, dry_gas=0.0, assoc_gas=0.0, condensate=0.0):
    points = []
    for period in periods:
        points.append(
            {
                "period": period,
                "month_start": date(int(period[:4]), int(period[4:6]), 1),
                "oil_mbd": oil,
                "dry_gas_mmscfd": dry_gas,
                "assoc_gas_mmscfd": assoc_gas,
                "condensate_mbd": condensate,
            }
        )
    return points


def _months(start_year, start_month, count):
    periods = []
    y, m = start_year, start_month
    for _ in range(count):
        periods.append(f"{y:04d}{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return periods


def _resolve(pprs_history, raw_rows_by_equity_field, aliases=None):
    equity_fields = set(raw_rows_by_equity_field.keys())
    field_match_index = build_field_match_index(set(pprs_history), equity_fields, aliases or [])
    return resolve_full_history(pprs_history, field_match_index, raw_rows_by_equity_field), field_match_index


def test_multi_year_normal_ownership_history():
    periods = _months(2018, 1, 36)  # 3 years
    pprs_history = {"ALPHA": _series("ALPHA", periods, oil=10.0)}
    rows = {"ALPHA": [_row("ALPHA", "ACME", 100, "2015-01-01", None)]}
    per_field_month, _ = _resolve(pprs_history, rows)
    resolved = [e for (f, p), e in per_field_month.items() if e["category"] == "resolved"]
    assert len(resolved) == 36


def test_transaction_at_month_start():
    periods = _months(2020, 1, 3)
    pprs_history = {"ALPHA": _series("ALPHA", periods)}
    rows = {
        "ALPHA": [
            _row("ALPHA", "ACME", 100, "2018-01-01", "2020-02-01"),
            _row("ALPHA", "BETA", 100, "2020-02-01", None),
        ]
    }
    per_field_month, _ = _resolve(pprs_history, rows)
    assert per_field_month[("ALPHA", "202001")]["active_rows"][0]["company_name"] == "ACME"
    assert per_field_month[("ALPHA", "202002")]["active_rows"][0]["company_name"] == "BETA"


def test_transaction_mid_month_is_a_boundary_artifact_not_a_gap():
    periods = _months(2020, 1, 2)
    pprs_history = {"ALPHA": _series("ALPHA", periods)}
    rows = {
        "ALPHA": [
            _row("ALPHA", "ACME", 100, "2018-01-01", "2020-01-15"),
            _row("ALPHA", "BETA", 100, "2020-01-15", None),
        ]
    }
    per_field_month, _ = _resolve(pprs_history, rows)
    # 202001's month_start (Jan 1) is covered by ACME through Jan 14, so it IS active (ACME).
    assert per_field_month[("ALPHA", "202001")]["category"] == "resolved"
    assert per_field_month[("ALPHA", "202001")]["active_rows"][0]["company_name"] == "ACME"


def test_first_production_month_before_equity_starts():
    periods = _months(2000, 1, 2)
    pprs_history = {"ALPHA": _series("ALPHA", periods)}
    rows = {"ALPHA": [_row("ALPHA", "ACME", 100, "2010-01-01", None)]}
    per_field_month, _ = _resolve(pprs_history, rows)
    assert per_field_month[("ALPHA", "200001")]["category"] == "pre_equity_history"
    assert per_field_month[("ALPHA", "200002")]["category"] == "pre_equity_history"


def test_genuine_interval_gap():
    periods = _months(2015, 1, 3)  # Jan, Feb, Mar 2015
    pprs_history = {"ALPHA": _series("ALPHA", periods)}
    rows = {
        "ALPHA": [
            _row("ALPHA", "ACME", 100, "2010-01-01", "2015-02-01"),
            _row("ALPHA", "ACME", 100, "2015-04-01", None),  # resumes AFTER March - real gap
        ]
    }
    per_field_month, _ = _resolve(pprs_history, rows)
    assert per_field_month[("ALPHA", "201501")]["category"] == "resolved"
    assert per_field_month[("ALPHA", "201502")]["category"] == "genuine_interval_gap"
    assert per_field_month[("ALPHA", "201503")]["category"] == "genuine_interval_gap"


def test_below_100_ownership_month():
    periods = _months(2020, 1, 1)
    pprs_history = {"ALPHA": _series("ALPHA", periods)}
    rows = {"ALPHA": [_row("ALPHA", "ACME", 60, "2018-01-01", None)]}
    per_field_month, _ = _resolve(pprs_history, rows)
    entry = per_field_month[("ALPHA", "202001")]
    assert entry["category"] == "e1_sum_mismatch"
    assert entry["positive_interest_sum"] == 60.0


def test_above_100_ownership_month_without_same_company_duplicate():
    periods = _months(2020, 1, 1)
    pprs_history = {"ALPHA": _series("ALPHA", periods)}
    rows = {
        "ALPHA": [
            _row("ALPHA", "ACME", 70, "2018-01-01", None),
            _row("ALPHA", "BETA", 70, "2018-01-01", None),
        ]
    }
    per_field_month, _ = _resolve(pprs_history, rows)
    assert per_field_month[("ALPHA", "202001")]["category"] == "quarantined"


def test_same_company_overlapping_histories_quarantined():
    periods = _months(2015, 1, 1)
    pprs_history = {"ALPHA": _series("ALPHA", periods)}
    rows = {
        "ALPHA": [
            _row("ALPHA", "ACME", 50, "2010-01-01", "2016-01-01"),
            _row("ALPHA", "ACME", 50, "2014-01-01", None),  # overlaps 2015-01
        ]
    }
    per_field_month, _ = _resolve(pprs_history, rows)
    entry = per_field_month[("ALPHA", "201501")]
    assert entry["category"] == "quarantined"
    assert entry["same_company_overlap"] == {"ACME": 2}


def test_different_company_overlap_and_quarantine_excludes_from_resolved_rows():
    periods = _months(2020, 1, 1)
    pprs_history = {"ALPHA": _series("ALPHA", periods, oil=100.0)}
    rows = {
        "ALPHA": [
            _row("ALPHA", "ACME", 60, "2018-01-01", None),
            _row("ALPHA", "BETA", 60, "2018-01-01", None),
        ]
    }
    per_field_month, _ = _resolve(pprs_history, rows)
    resolved_rows = build_resolved_grain_rows_historical(per_field_month)
    assert resolved_rows == []  # quarantined field-month never contributes an equity row


def test_zero_duration_event_rows_across_history_never_active():
    periods = _months(2020, 1, 3)
    pprs_history = {"ALPHA": _series("ALPHA", periods)}
    rows = {
        "ALPHA": [
            _row("ALPHA", "ACME", 100, "2018-01-01", "2020-02-01"),
            _row("ALPHA", "ACME", 100, "2020-02-01", "2020-02-01"),  # zero-duration
            _row("ALPHA", "ACME", 100, "2020-02-01", None),
        ]
    }
    per_field_month, _ = _resolve(pprs_history, rows)
    for period in ("202001", "202002", "202003"):
        assert per_field_month[("ALPHA", period)]["category"] == "resolved"
        for r in per_field_month[("ALPHA", period)]["active_rows"]:
            assert r["start_date"] != r["end_date"]


def test_zero_interest_operator_rows_across_history_excluded_from_sum():
    periods = _months(2020, 1, 2)
    pprs_history = {"ALPHA": _series("ALPHA", periods)}
    rows = {
        "ALPHA": [
            _row("ALPHA", "OPERATOR_CO", 0, "2018-01-01", None, opflag="Y"),
            _row("ALPHA", "PARTNER_CO", 100, "2018-01-01", None, opflag="N"),
        ]
    }
    per_field_month, _ = _resolve(pprs_history, rows)
    for period in ("202001", "202002"):
        entry = per_field_month[("ALPHA", period)]
        assert entry["category"] == "resolved"
        assert entry["positive_interest_sum"] == 100.0
    resolved_rows = build_resolved_grain_rows_historical(per_field_month)
    assert all(r["company_name"] != "OPERATOR_CO" for r in resolved_rows)  # 0% row produces no equity row


def test_future_only_ownership_with_current_production():
    periods = _months(2026, 1, 1)
    pprs_history = {"ALPHA": _series("ALPHA", periods, oil=50.0)}
    rows = {"ALPHA": [_row("ALPHA", "FUTURE_CO", 100, "2030-05-01", None)]}
    per_field_month, _ = _resolve(pprs_history, rows)
    assert per_field_month[("ALPHA", "202601")]["category"] == "future_only"


def test_unmatched_historical_field_reported_with_cumulative_production():
    pprs_history = {"GHOST FIELD": _series("GHOST FIELD", _months(2000, 1, 2), oil=5.0)}
    field_match_index = {}  # no match at all
    report = historical_matching_report(pprs_history, field_match_index)
    assert report["unmatched_field_count"] == 1
    detail = report["unmatched_fields"][0]
    assert detail["field"] == "GHOST FIELD"
    assert detail["cumulative_production_by_stream"]["oil_mbd"] == 10.0


def test_monthly_e8_conservation():
    periods = _months(2020, 1, 2)
    pprs_history = {"ALPHA": _series("ALPHA", periods, oil=10.0, dry_gas=4.0)}
    rows = {
        "ALPHA": [
            _row("ALPHA", "ACME", 60, "2018-01-01", None),
            _row("ALPHA", "BETA", 40, "2018-01-01", None),
        ]
    }
    per_field_month, _ = _resolve(pprs_history, rows)
    resolved_rows = build_resolved_grain_rows_historical(per_field_month)
    e8 = check_e8_historical(per_field_month, resolved_rows)
    assert e8["passed"] is True
    assert e8["months_checked"] == 2


def test_annual_production_weighted_coverage():
    periods_2000 = _months(2000, 1, 12)
    periods_2020 = _months(2020, 1, 12)
    pprs_history = {"ALPHA": _series("ALPHA", periods_2000 + periods_2020, oil=10.0)}
    rows = {"ALPHA": [_row("ALPHA", "ACME", 100, "2015-01-01", None)]}  # only covers 2020
    per_field_month, _ = _resolve(pprs_history, rows)
    coverage = monthly_coverage(per_field_month)
    assert coverage["annual_coverage_pct"]["2000"]["oil_mbd"] == 0.0
    assert coverage["annual_coverage_pct"]["2020"]["oil_mbd"] == 100.0


def test_full_history_production_weighted_coverage():
    periods = _months(2000, 1, 6) + _months(2020, 1, 6)
    pprs_history = {"ALPHA": _series("ALPHA", periods, oil=10.0)}
    rows = {"ALPHA": [_row("ALPHA", "ACME", 100, "2015-01-01", None)]}  # covers only the 2020 half
    per_field_month, _ = _resolve(pprs_history, rows)
    coverage = monthly_coverage(per_field_month)
    # 6 of 12 months resolved, all equal production -> 50%.
    assert coverage["full_history_coverage_pct"]["oil_mbd"] == 50.0


def test_company_history_summary_is_deterministic():
    periods = _months(2020, 1, 2)
    pprs_history = {"ALPHA": _series("ALPHA", periods, oil=10.0), "BETA": _series("BETA", periods, oil=5.0)}
    rows = {
        "ALPHA": [_row("ALPHA", "ZETA CO", 100, "2018-01-01", None)],
        "BETA": [_row("BETA", "ZETA CO", 100, "2018-01-01", None)],
    }
    per_field_month, _ = _resolve(pprs_history, rows)
    resolved_rows = build_resolved_grain_rows_historical(per_field_month)
    summary_a = build_company_summary_historical(resolved_rows, per_field_month)
    summary_b = build_company_summary_historical(resolved_rows, per_field_month)
    assert summary_a == summary_b
    zeta = summary_a[0]
    assert zeta["company_name"] == "ZETA CO"
    assert zeta["field_count"] == 2
    assert zeta["first_resolved_period"] == "202001"
    assert zeta["last_resolved_period"] == "202002"


def test_diagnostic_report_is_deterministic():
    from etl.equity_join_historical import (
        build_company_summary_historical,
        check_e1_historical,
        check_e4_historical,
        check_e5_historical,
        check_e7_historical,
        gap_diagnostics as gaps_fn,
        murlach_analysis,
    )

    periods = _months(2020, 1, 2)
    pprs_history = {"ALPHA": _series("ALPHA", periods, oil=10.0)}
    rows = {"ALPHA": [_row("ALPHA", "ACME", 100, "2018-01-01", None)]}
    per_field_month, field_match_index = _resolve(pprs_history, rows)
    resolved_rows = build_resolved_grain_rows_historical(per_field_month)

    def make_result():
        return {
            "pprs_field_month_count": 2,
            "normalized_equity_row_count": 1,
            "resolved_row_count": len(resolved_rows),
            "runtime_seconds": 0.0,
            "matching": historical_matching_report(pprs_history, field_match_index),
            "per_field_month": per_field_month,
            "resolved_rows": resolved_rows,
            "e1": check_e1_historical(per_field_month),
            "e4": check_e4_historical(per_field_month),
            "e5": check_e5_historical(per_field_month),
            "e7": check_e7_historical(rows["ALPHA"]),
            "e8": check_e8_historical(per_field_month, resolved_rows),
            "coverage": monthly_coverage(per_field_month),
            "gaps": gaps_fn(per_field_month),
            "murlach": murlach_analysis(per_field_month, rows),
            "company_summary": build_company_summary_historical(resolved_rows, per_field_month),
            "zero_duration_classification": {"category_counts": {}},
        }

    report_a = build_historical_report(make_result())
    report_b = build_historical_report(make_result())
    assert report_a == report_b
