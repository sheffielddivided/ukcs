"""
Unit tests for etl/overview.py (Deliverable 1 ETL layer). No network
access - synthetic data shaped like the pipeline's own already-tested
FieldHistory objects and equity company docs.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.overview import (  # noqa: E402
    OverviewError,
    UNRESOLVED_BUCKET_NAME,
    build_company_groups_field_breakdown_overview,
    build_company_groups_overview,
    build_fields_overview,
    build_monthly_totals,
    build_overview_meta,
    build_legal_entities_overview,
    validate_company_field_breakdown_reconciliation,
    validate_company_groups_overview_reconciliation,
    validate_fields_overview_reconciliation,
    validate_monthly_totals_reconciliation,
)
from etl.equity_mboed import build_derived_status_by_period  # noqa: E402
from etl.equity_publication_window import build_monthly_stream_data  # noqa: E402


@dataclass
class _FakeHistory:
    slug: str
    field: str
    series: list = dataclass_field(default_factory=list)
    full_precision_series: list = dataclass_field(default_factory=list)


def _fp_point(period, oil=0.0, condensate=0.0, dry_gas=0.0, assoc_gas=0.0):
    liq = oil + condensate
    gas = (dry_gas + assoc_gas) / 6.0
    return {
        "period": period,
        "oil_mbd": oil,
        "condensate_mbd": condensate,
        "dry_gas_mmscfd": dry_gas,
        "assoc_gas_mmscfd": assoc_gas,
        "liquids_mboed": liq,
        "natural_gas_mboed": gas,
        "total_mboed": liq + gas,
    }


def _rounded_point(period, liquids, natural_gas):
    return {
        "period": period,
        "liquids_mboed": round(liquids, 3),
        "natural_gas_mboed": round(natural_gas, 3),
        "total_mboed": round(liquids + natural_gas, 3),
    }


# ---------------------------------------------------------------------------
# Monthly totals (full history, native/derived production)
# ---------------------------------------------------------------------------


def test_build_monthly_totals_sums_across_fields():
    histories = [
        _FakeHistory("alpha", "ALPHA", full_precision_series=[_fp_point("2020-01", oil=10.0, dry_gas=12.0)]),
        _FakeHistory("beta", "BETA", full_precision_series=[_fp_point("2020-01", oil=5.0, dry_gas=6.0)]),
    ]
    series = build_monthly_totals(histories)
    assert len(series) == 1
    point = series[0]
    assert point["period"] == "2020-01"
    assert point["liquids_mboed"] == 15.0
    assert point["natural_gas_mboed"] == 3.0  # (12+6)/6
    assert point["total_mboed"] == 18.0


def test_build_monthly_totals_sorted_by_period():
    histories = [
        _FakeHistory(
            "alpha",
            "ALPHA",
            full_precision_series=[_fp_point("2020-02", oil=1.0), _fp_point("2020-01", oil=2.0)],
        ),
    ]
    series = build_monthly_totals(histories)
    assert [p["period"] for p in series] == ["2020-01", "2020-02"]


def test_validate_monthly_totals_reconciliation_passes_for_correct_data():
    series = [_rounded_point("2020-01", 10.0, 2.0)]
    validate_monthly_totals_reconciliation(series)  # must not raise


def test_validate_monthly_totals_reconciliation_fails_for_broken_total():
    series = [{"period": "2020-01", "liquids_mboed": 10.0, "natural_gas_mboed": 2.0, "total_mboed": 999.0}]
    try:
        validate_monthly_totals_reconciliation(series)
        assert False, "must raise when total != liquids + natural_gas"
    except OverviewError as e:
        assert "2020-01" in str(e)


# ---------------------------------------------------------------------------
# Company-groups overview - collapses unresolved into one bucket
# ---------------------------------------------------------------------------


def _company_doc(series, slug="company"):
    return {"series": series, "slug": slug}


def _company_point(period, oil=None, status="complete"):
    return {
        "period": period,
        "oil_mbd": {"value": oil, "status": status},
        "dry_gas_mmscfd": {"value": None, "status": "not_applicable"},
        "assoc_gas_mmscfd": {"value": None, "status": "not_applicable"},
        "condensate_mbd": {"value": None, "status": "not_applicable"},
        "liquids_mboed": {"value": oil, "status": status},
        "natural_gas_mboed": {"value": 0.0, "status": "not_applicable"},
        "total_mboed": {"value": oil, "status": status},
    }


def test_build_company_groups_overview_collapses_unresolved_to_one_bucket():
    equity_company_docs = {
        "APPROVED CO": _company_doc([_company_point("2020-01", oil=10.0)]),
        "UNRESOLVED CO A": _company_doc([_company_point("2020-01", oil=1.0)]),
        "UNRESOLVED CO B": _company_doc([_company_point("2020-01", oil=2.0)]),
    }
    mapping = [
        {"source_legal_entity": "APPROVED CO", "current_display_group": "BIG GROUP", "status": "approved"},
        {"source_legal_entity": "UNRESOLVED CO A", "current_display_group": "UNRESOLVED CO A", "status": "unresolved"},
        {"source_legal_entity": "UNRESOLVED CO B", "current_display_group": "UNRESOLVED CO B", "status": "unresolved"},
    ]
    overview = build_company_groups_overview(equity_company_docs, mapping)
    assert "BIG GROUP" in overview
    assert UNRESOLVED_BUCKET_NAME in overview
    # Only ONE unresolved bucket, not 2 separate singleton entries.
    assert len([g for g in overview if g not in ("BIG GROUP",)]) == 1
    unresolved_point = overview[UNRESOLVED_BUCKET_NAME]["series"][0]
    assert unresolved_point["oil_mbd"]["value"] == 3.0  # 1.0 + 2.0, never dropped


def test_company_groups_overview_reconciliation_passes_exactly():
    equity_company_docs = {
        "APPROVED CO": _company_doc([_company_point("2020-01", oil=10.0)]),
        "UNRESOLVED CO": _company_doc([_company_point("2020-01", oil=1.0)]),
    }
    mapping = [
        {"source_legal_entity": "APPROVED CO", "current_display_group": "GROUP", "status": "approved"},
        {"source_legal_entity": "UNRESOLVED CO", "current_display_group": "UNRESOLVED CO", "status": "unresolved"},
    ]
    overview = build_company_groups_overview(equity_company_docs, mapping)
    diffs = validate_company_groups_overview_reconciliation(equity_company_docs, overview, streams=["oil_mbd"])
    assert diffs["oil_mbd"] < 1e-9


def test_company_groups_overview_reconciliation_catches_dropped_entity():
    equity_company_docs = {
        "APPROVED CO": _company_doc([_company_point("2020-01", oil=10.0)]),
        "UNRESOLVED CO": _company_doc([_company_point("2020-01", oil=1.0)]),
    }
    # Tampered: the overview is missing the unresolved bucket entirely.
    overview = {"GROUP": {"series": [_company_point("2020-01", oil=10.0)]}}
    try:
        validate_company_groups_overview_reconciliation(equity_company_docs, overview, streams=["oil_mbd"])
        assert False, "must raise when overview drops production"
    except OverviewError as e:
        assert "oil_mbd" in str(e)


# ---------------------------------------------------------------------------
# Company-groups field breakdown (2026-09-10 continuation)
# ---------------------------------------------------------------------------


def _resolved_row(field, company, period, pct, oil=10.0):
    factor = pct / 100.0
    return {
        "field_name": field,
        "company_name": company,
        "interest_pct": pct,
        "period": period,
        "oil_mbd": oil * factor,
        "dry_gas_mmscfd": 0.0,
        "assoc_gas_mmscfd": 0.0,
        "condensate_mbd": 0.0,
    }


def _equity_entry(oil):
    return {
        "category": "resolved",
        "production": {"period": "201303", "oil_mbd": oil, "dry_gas_mmscfd": 0.0, "assoc_gas_mmscfd": 0.0, "condensate_mbd": 0.0},
    }


def test_company_groups_field_breakdown_collapses_unresolved_same_as_totals():
    from etl.equity_artifacts import build_company_artifacts, build_publication_status_by_period_stream

    resolved_rows = [
        _resolved_row("ALPHA", "APPROVED CO", "201303", 100, oil=10.0),
        _resolved_row("BETA", "UNRESOLVED CO A", "201303", 100, oil=1.0),
        _resolved_row("GAMMA", "UNRESOLVED CO B", "201303", 100, oil=2.0),
    ]
    per_field_month = {
        ("ALPHA", "201303"): _equity_entry(10.0),
        ("BETA", "201303"): _equity_entry(1.0),
        ("GAMMA", "201303"): _equity_entry(2.0),
    }
    monthly_data = build_monthly_stream_data(per_field_month)
    status_by_period_stream = build_publication_status_by_period_stream(monthly_data)
    derived_status_by_period = build_derived_status_by_period(monthly_data)

    mapping = [
        {"source_legal_entity": "APPROVED CO", "current_display_group": "BIG GROUP", "status": "approved"},
        {"source_legal_entity": "UNRESOLVED CO A", "current_display_group": "UNRESOLVED CO A", "status": "unresolved"},
        {"source_legal_entity": "UNRESOLVED CO B", "current_display_group": "UNRESOLVED CO B", "status": "unresolved"},
    ]

    equity_company_docs = build_company_artifacts(resolved_rows, status_by_period_stream, derived_status_by_period)
    company_groups_overview = build_company_groups_overview(equity_company_docs, mapping)
    breakdown = build_company_groups_field_breakdown_overview(resolved_rows, derived_status_by_period, mapping)

    assert "BIG GROUP" in breakdown
    assert set(breakdown["BIG GROUP"]) == {"ALPHA"}
    assert UNRESOLVED_BUCKET_NAME in breakdown
    # Both unresolved companies' fields collapse under the one shared bucket.
    assert set(breakdown[UNRESOLVED_BUCKET_NAME]) == {"BETA", "GAMMA"}

    # Must not raise - group-level total reconciles exactly with the
    # field breakdown summed across that group's fields.
    diff = validate_company_field_breakdown_reconciliation(company_groups_overview, breakdown, tolerance=1e-9)
    assert diff < 1e-9


def test_company_field_breakdown_reconciliation_catches_a_dropped_field():
    company_groups_overview = {
        "GROUP": {"series": [{"period": "201303", "total_mboed": {"value": 10.0, "status": "complete"}}]},
    }
    # Tampered: the field breakdown for this group is missing entirely.
    breakdown = {"GROUP": {}}
    try:
        validate_company_field_breakdown_reconciliation(company_groups_overview, breakdown, tolerance=1e-9)
        assert False, "must raise when the field breakdown drops production the group total carries"
    except OverviewError as e:
        assert "GROUP" in str(e)


def test_company_field_breakdown_reconciliation_needs_a_real_tolerance_not_exact_equality():
    """Regression test for a real build failure (2026-09-10 continuation
    live rebuild): each field-period total_mboed and each group-period
    total_mboed is independently rounded ONCE at serialization from its
    own full-precision value - summing several independently-rounded
    field values does not, in general, land on the exact same rounded
    total as a SEPARATELY-rounded group aggregate, even when both derive
    from identical underlying full-precision numbers (double-rounding).
    A near-zero tolerance is too tight for real multi-field companies and
    fails the build on entirely correct data; the statistically-derived
    compute_serialization_tolerance() bound (the same one
    validate_fields_overview_reconciliation already relies on for this
    exact class of comparison) must pass."""
    from etl.validate import compute_serialization_tolerance

    # Five fields' TRUE (full-precision) total_mboed values - each
    # rounded to 3 decimals independently before being summed, while the
    # group's own total is rounded separately from the true full-
    # precision sum, landing on a different 3-decimal value than the sum
    # of the individually-rounded fields (a real divergence this
    # magnitude - 0.002 - was observed in an actual live rebuild).
    true_values = [15.435324, 12.394422, 4.160301, 14.111258, 49.170498]
    field_breakdown = {
        "GROUP": {
            f"FIELD {i}": {
                "series": [{"period": "201303", "total_mboed": {"value": round(v, 3), "status": "complete"}}]
            }
            for i, v in enumerate(true_values)
        }
    }
    field_sum = sum(round(v, 3) for v in true_values)
    group_total = round(sum(true_values), 3)
    assert field_sum != group_total  # the double-rounding divergence this test exists to cover

    company_groups_overview = {
        "GROUP": {"series": [{"period": "201303", "total_mboed": {"value": group_total, "status": "complete"}}]}
    }

    try:
        validate_company_field_breakdown_reconciliation(company_groups_overview, field_breakdown, tolerance=1e-9)
        assert False, "a near-zero tolerance should have rejected this double-rounded divergence"
    except OverviewError:
        pass

    tolerance = compute_serialization_tolerance(n_field_entries=5, n_operator_entries=1, round_decimals=3)
    validate_company_field_breakdown_reconciliation(company_groups_overview, field_breakdown, tolerance=tolerance)  # must not raise


# ---------------------------------------------------------------------------
# Legal entities overview - every entity retained
# ---------------------------------------------------------------------------


def test_build_legal_entities_overview_retains_every_entity():
    equity_company_docs = {
        "CO A": _company_doc([_company_point("2020-01", oil=1.0)], slug="co-a"),
        "CO B": _company_doc([_company_point("2020-01", oil=2.0)], slug="co-b"),
    }
    overview = build_legal_entities_overview(equity_company_docs)
    assert set(overview) == {"CO A", "CO B"}
    assert overview["CO A"]["series"][0]["oil_mbd"]["value"] == 1.0


# ---------------------------------------------------------------------------
# Fields overview - full history, Top-N + Other reconciliation
# ---------------------------------------------------------------------------


def test_build_fields_overview_uses_published_series_values():
    histories = [
        _FakeHistory(
            "alpha",
            "ALPHA",
            series=[{"period": "2020-01", "liquids_mboed": 10.0, "natural_gas_mboed": 2.0, "total_mboed": 12.0}],
        ),
    ]
    overview = build_fields_overview(histories)
    assert overview["alpha"]["name"] == "ALPHA"
    assert overview["alpha"]["series"][0]["total_mboed"] == 12.0


def test_fields_overview_reconciles_with_monthly_totals():
    histories = [
        _FakeHistory(
            "alpha", "ALPHA",
            series=[{"period": "2020-01", "liquids_mboed": 10.0, "natural_gas_mboed": 2.0, "total_mboed": 12.0}],
        ),
        _FakeHistory(
            "beta", "BETA",
            series=[{"period": "2020-01", "liquids_mboed": 5.0, "natural_gas_mboed": 1.0, "total_mboed": 6.0}],
        ),
    ]
    fields_overview = build_fields_overview(histories)
    monthly_totals = [{"period": "2020-01", "total_mboed": 18.0}]
    validate_fields_overview_reconciliation(fields_overview, monthly_totals, tolerance=0.01)  # must not raise


def test_fields_overview_reconciliation_catches_mismatch():
    histories = [
        _FakeHistory(
            "alpha", "ALPHA",
            series=[{"period": "2020-01", "liquids_mboed": 10.0, "natural_gas_mboed": 2.0, "total_mboed": 12.0}],
        ),
    ]
    fields_overview = build_fields_overview(histories)
    monthly_totals = [{"period": "2020-01", "total_mboed": 999.0}]
    try:
        validate_fields_overview_reconciliation(fields_overview, monthly_totals, tolerance=0.01)
        assert False, "must raise on mismatch"
    except OverviewError as e:
        assert "2020-01" in str(e)


# ---------------------------------------------------------------------------
# Overview meta
# ---------------------------------------------------------------------------


def test_build_overview_meta_reports_reconciled_stats():
    grouping_report = {
        "total_legal_entities": 292,
        "approved_count": 110,
        "reviewed_manual_mapping_count": 0,
        "unresolved_count": 182,
        "excluded_count": 0,
        "distinct_approved_groups": 37,
        "unresolved_fallback_count": 182,
        "production_weighted_current_coverage_pct": 95.401,
        "latest_period_production_retained_under_unresolved_pct": 4.599,
    }
    monthly_totals = [{"period": "1975-06"}, {"period": "2026-06"}]
    meta = build_overview_meta(grouping_report, monthly_totals, "201303", "2026-09-10T00:00:00Z")
    assert meta["distinct_approved_groups"] == 37
    assert meta["unresolved_fallback_count"] == 182
    assert meta["monthly_totals_earliest_period"] == "1975-06"
    assert meta["monthly_totals_latest_period"] == "2026-06"
    assert meta["equity_attributable_earliest_period"] == "201303"
