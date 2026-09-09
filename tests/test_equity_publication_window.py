"""
Unit tests for etl/equity_publication_window.py (publication-window and
coverage-policy decision checkpoint - diagnostic only, no build.py
integration, no docs/data/equity artifacts).

Uses small synthetic per_field_month-shaped data rather than the live
133,608-field-month dataset. No test encodes a final publication date -
per the explicit instruction, that decision is pending human review.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.equity_publication_window import (  # noqa: E402
    breach_cause_analysis,
    build_monthly_stream_data,
    build_report,
    candidate_window_stats,
    stability_threshold,
)

STREAMS = ["oil_mbd", "dry_gas_mmscfd", "assoc_gas_mmscfd", "condensate_mbd"]


def _prod(oil=10.0, dry_gas=0.0, assoc_gas=0.0, condensate=0.0):
    return {"oil_mbd": oil, "dry_gas_mmscfd": dry_gas, "assoc_gas_mmscfd": assoc_gas, "condensate_mbd": condensate}


def _entry(category, production, month_start=None):
    return {"category": category, "production": production, "month_start": month_start or date(2020, 1, 1)}


def test_first_month_after_which_coverage_remains_above_threshold():
    per_field_month = {
        ("A", "202001"): _entry("pre_equity_history", _prod(oil=10.0)),  # 0% coverage
        ("A", "202002"): _entry("resolved", _prod(oil=10.0)),  # 100%
        ("A", "202003"): _entry("resolved", _prod(oil=10.0)),  # 100%
    }
    monthly_data = build_monthly_stream_data(per_field_month)
    assert stability_threshold(monthly_data, "oil_mbd", 95.0) == "202002"


def test_temporary_recovery_followed_by_later_drop():
    """Coverage recovers in month 2 but drops again in month 3 - the
    stability threshold must reflect the LAST violation, not the first
    recovery."""
    per_field_month = {
        ("A", "202001"): _entry("resolved", _prod(oil=10.0)),  # 100% - looks stable...
        ("A", "202002"): _entry("pre_equity_history", _prod(oil=10.0)),  # ...but drops to 0%
        ("A", "202003"): _entry("resolved", _prod(oil=10.0)),  # recovers again
    }
    monthly_data = build_monthly_stream_data(per_field_month)
    # Stability must be reported from AFTER the last (202002) violation, not 202001.
    assert stability_threshold(monthly_data, "oil_mbd", 95.0) == "202003"


def test_never_stabilizes_if_most_recent_month_violates():
    per_field_month = {
        ("A", "202001"): _entry("resolved", _prod(oil=10.0)),
        ("A", "202002"): _entry("pre_equity_history", _prod(oil=10.0)),
    }
    monthly_data = build_monthly_stream_data(per_field_month)
    assert stability_threshold(monthly_data, "oil_mbd", 95.0) is None


def test_never_violates_returns_earliest_month():
    per_field_month = {
        ("A", "202001"): _entry("resolved", _prod(oil=10.0)),
        ("A", "202002"): _entry("resolved", _prod(oil=10.0)),
    }
    monthly_data = build_monthly_stream_data(per_field_month)
    assert stability_threshold(monthly_data, "oil_mbd", 95.0) == "202001"


def test_fixed_window_coverage_excludes_earlier_months():
    per_field_month = {
        ("A", "199901"): _entry("pre_equity_history", _prod(oil=100.0)),  # excluded by window
        ("A", "200001"): _entry("resolved", _prod(oil=10.0)),
        ("A", "200002"): _entry("resolved", _prod(oil=10.0)),
    }
    monthly_data = build_monthly_stream_data(per_field_month)
    stats = candidate_window_stats(monthly_data, "200001")
    assert stats["oil_mbd"]["overall_coverage_pct"] == 100.0
    assert stats["oil_mbd"]["month_count"] == 2


def test_longest_consecutive_run_below_threshold():
    per_field_month = {
        ("A", "202001"): _entry("resolved", _prod(oil=10.0)),  # ok
        ("A", "202002"): _entry("pre_equity_history", _prod(oil=10.0)),  # below
        ("A", "202003"): _entry("pre_equity_history", _prod(oil=10.0)),  # below
        ("A", "202004"): _entry("pre_equity_history", _prod(oil=10.0)),  # below - run of 3
        ("A", "202005"): _entry("resolved", _prod(oil=10.0)),  # ok - run ends
        ("A", "202006"): _entry("pre_equity_history", _prod(oil=10.0)),  # below - new run of 1
    }
    monthly_data = build_monthly_stream_data(per_field_month)
    stats = candidate_window_stats(monthly_data, "202001")
    assert stats["oil_mbd"]["longest_consecutive_run_below_95"] == 3


def test_stream_specific_coverage_independent_per_stream():
    """A field-month can be fully resolved for one stream's underlying
    production but the coverage calculation is still per-stream, driven by
    whether the FIELD-MONTH resolved, not by stream value alone."""
    per_field_month = {
        ("A", "202001"): _entry("resolved", _prod(oil=10.0, dry_gas=5.0)),
        ("B", "202001"): _entry("unmatched", _prod(oil=0.0, dry_gas=20.0)),  # unmatched, large dry gas
    }
    monthly_data = build_monthly_stream_data(per_field_month)
    stats = candidate_window_stats(monthly_data, "202001")
    # oil: total=10 (A only has oil), all resolved -> 100%
    assert stats["oil_mbd"]["overall_coverage_pct"] == 100.0
    # dry gas: total=25 (5 resolved + 20 unmatched), only 5 resolved -> 20%
    assert stats["dry_gas_mmscfd"]["overall_coverage_pct"] == 20.0


def test_candidate_policy_classification_buckets():
    per_field_month = {
        ("A", "202001"): _entry("resolved", _prod(oil=10.0)),  # will be 100% -> at_100
        ("B", "202001"): _entry("pre_equity_history", _prod(oil=0.001)),  # tiny, doesn't change A's bucket
    }
    monthly_data = build_monthly_stream_data(per_field_month)
    stats = candidate_window_stats(monthly_data, "202001")
    b = stats["oil_mbd"]["buckets"]
    assert b["at_100"] + b["99.5_to_100"] + b["95_to_99.5"] + b["below_95"] == 1  # one month total


def test_breach_cause_analysis_identifies_dominant_excluded_category():
    per_field_month = {
        ("A", "202001"): _entry("resolved", _prod(oil=1.0)),
        ("B", "202001"): _entry("pre_equity_history", _prod(oil=50.0)),  # dominant cause
        ("C", "202001"): _entry("unmatched", _prod(oil=2.0)),  # minor cause
    }
    monthly_data = build_monthly_stream_data(per_field_month)
    causes = breach_cause_analysis(monthly_data, "oil_mbd", 95.0)
    assert causes == {"pre_equity_history": 1}  # only one month below threshold, dominant cause is pre_equity_history


def test_diagnostic_report_is_deterministic():
    per_field_month = {
        ("ALPHA", "202001"): _entry("resolved", _prod(oil=10.0)),
        ("ALPHA", "202002"): _entry("pre_equity_history", _prod(oil=10.0)),
    }
    pprs_history = {"MURLACH [pt of MARNOCK-SKUA]": []}
    raw_rows = []
    result = {}

    report_a = build_report(per_field_month, pprs_history, raw_rows, result)
    report_b = build_report(per_field_month, pprs_history, raw_rows, result)
    assert report_a == report_b
