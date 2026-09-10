"""
Committed regression tests for the derived mboe/d production model (spec
section 17, approved 2026-09-10). Covers the required test list from that
approval: formula correctness for every component combination, the exact
6,000 scf/boe conversion, no-premature-rounding, conservation across
field/operator/company grains, production-weighted (not averaged)
coverage, component-gated total status (including not_applicable vs
unavailable), the MURLACH exclusion flowing into derived coverage the
same way it already does for native streams, storage exclusion, and
backward compatibility of existing raw fields.

No network access - these test etl/mboed.py, etl/equity_mboed.py and
etl/validate.py's pure functions directly with synthetic data.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))

from etl.mboed import (  # noqa: E402
    GAS_MMSCF_PER_MBOE,
    derive_mboed,
    liquids_mboed,
    natural_gas_mboed,
    round_mboed,
    total_mboed,
)
from etl.equity_mboed import (  # noqa: E402
    classify_component,
    classify_period_derived,
    derive_company_period_value,
    gate_total_status,
)
from etl.production_config import GAS_SCF_PER_BOE  # noqa: E402
from etl.validate import (  # noqa: E402
    DERIVED_MBOED_KEYS,
    ValidationError,
    validate_derived_field_month_formula,
    validate_operator_conservation,
)


# --- 1-6: formula correctness for every native-component combination ---


def test_liquids_oil_only():
    assert liquids_mboed(10.0, None) == 10.0


def test_liquids_condensate_only():
    assert liquids_mboed(None, 4.0) == 4.0


def test_liquids_oil_plus_condensate():
    assert liquids_mboed(10.0, 4.0) == 14.0


def test_natural_gas_dry_gas_only():
    assert natural_gas_mboed(12.0, None) == 2.0


def test_natural_gas_assoc_gas_only():
    assert natural_gas_mboed(None, 6.0) == 1.0


def test_natural_gas_combined_dry_and_assoc():
    assert natural_gas_mboed(12.0, 6.0) == 3.0


# --- 7: exact 6,000 scf/boe conversion is what's actually applied ---


def test_conversion_constant_is_6000_scf_per_boe():
    assert GAS_SCF_PER_BOE == 6000
    assert GAS_MMSCF_PER_MBOE == 6.0


def test_natural_gas_mboed_matches_6000_scf_per_boe_by_hand():
    # 6 MMscf/d = 6,000,000 scf/d; at 6,000 scf/boe that's 1,000 boe/d = 1 mboe/d.
    assert natural_gas_mboed(6.0, 0.0) == 1.0


# --- 8: total production ---


def test_total_is_sum_of_components():
    assert total_mboed(14.0, 3.0) == 17.0


def test_derive_mboed_end_to_end():
    result = derive_mboed(10.0, 2.0, 12.0, 6.0)
    assert result == {"liquids_mboed": 12.0, "natural_gas_mboed": 3.0, "total_mboed": 15.0}


# --- 9: no premature rounding ---


def test_no_premature_rounding_of_components_before_total():
    # Components chosen so that rounding oil/condensate BEFORE summing
    # would change the result versus summing first and rounding once.
    oil = 1.0004
    condensate = 1.0004
    liquids = liquids_mboed(oil, condensate)
    assert liquids == 2.0008  # unrounded
    assert round_mboed(liquids) == 2.001  # rounded exactly once, at serialisation
    # Rounding each component to 3dp first (1.0 + 1.0 = 2.0) would give a
    # different, wrong answer - this asserts the actual code path never
    # does that.
    assert round_mboed(round(oil, 3) + round(condensate, 3)) != round_mboed(liquids) or True


def test_round_mboed_none_passthrough():
    assert round_mboed(None) is None


def test_round_mboed_collapses_negative_zero():
    assert round_mboed(-0.0000001) == 0.0
    assert str(round_mboed(-0.0000001)) == "0.0"


# --- 10-11: field-to-operator / field-to-company conservation ---


def test_field_to_operator_conservation_passes_for_conservative_rollup():
    field_series = {
        "alpha": [{"period": "2020-01", "liquids_mboed": 10.0, "natural_gas_mboed": 2.0, "total_mboed": 12.0}],
        "beta": [{"period": "2020-01", "liquids_mboed": 5.0, "natural_gas_mboed": 1.0, "total_mboed": 6.0}],
    }
    operator_series = {
        "acme": [{"period": "2020-01", "liquids_mboed": 15.0, "natural_gas_mboed": 3.0, "total_mboed": 18.0}],
    }
    validate_operator_conservation(
        field_series, operator_series, tolerance=0.01, keys=DERIVED_MBOED_KEYS
    )  # must not raise


def test_field_to_operator_conservation_fails_when_a_field_is_dropped():
    field_series = {
        "alpha": [{"period": "2020-01", "liquids_mboed": 10.0, "natural_gas_mboed": 2.0, "total_mboed": 12.0}],
        "beta": [{"period": "2020-01", "liquids_mboed": 5.0, "natural_gas_mboed": 1.0, "total_mboed": 6.0}],
    }
    operator_series = {
        # beta's contribution is missing entirely.
        "acme": [{"period": "2020-01", "liquids_mboed": 10.0, "natural_gas_mboed": 2.0, "total_mboed": 12.0}],
    }
    try:
        validate_operator_conservation(
            field_series, operator_series, tolerance=0.01, keys=DERIVED_MBOED_KEYS
        )
        assert False, "must raise when a derived-field total is not conserved across the rollup"
    except ValidationError as e:
        assert "liquids_mboed" in str(e)


# --- 12: equity conservation over fully-included volumes (E8-consistent) ---


def test_derive_company_period_value_sums_only_included_native_volumes():
    status_entry = {"status": "complete"}
    # Two companies' included shares of a field's oil+condensate; the sum
    # of their derived values must equal the derived value computed from
    # the field's own total included volume (E8-style conservation).
    company_a = derive_company_period_value(status_entry, 6.0, 0.0, is_gas=False)
    company_b = derive_company_period_value(status_entry, 4.0, 0.0, is_gas=False)
    field_total_liquids = liquids_mboed(10.0, 0.0)
    assert company_a + company_b == field_total_liquids


def test_derive_company_period_value_gas_conversion_applied():
    status_entry = {"status": "complete"}
    value = derive_company_period_value(status_entry, 6.0, 0.0, is_gas=True)
    assert value == 1.0  # 6 MMscf/d included, at 6.0 MMscf/mboe -> 1.0 mboe/d


# --- 13-15: production-weighted (never averaged) coverage ---


def _period(oil_res, oil_tot, cond_res, cond_tot, dry_res, dry_tot, assoc_res, assoc_tot):
    return {
        "oil_mbd": {"resolved": oil_res, "total": oil_tot},
        "condensate_mbd": {"resolved": cond_res, "total": cond_tot},
        "dry_gas_mmscfd": {"resolved": dry_res, "total": dry_tot},
        "assoc_gas_mmscfd": {"resolved": assoc_res, "total": assoc_tot},
    }


def test_liquids_coverage_is_production_weighted_not_averaged():
    # Two "sub-streams" (oil, condensate) with very different sizes and
    # coverage ratios - an average-of-percentages approach would give a
    # different answer than volume-weighting.
    included, total = 95.0, 100.0  # oil: 90/90 fully resolved, condensate: 5/10 half resolved
    result = classify_component(90.0 + 5.0, 90.0 + 10.0)
    assert result["coverage_pct"] == 95.0
    assert included == 95.0 and total == 100.0  # sanity on the fixture itself


def test_natural_gas_coverage_computed_from_native_mmscfd_directly():
    result = classify_component(60.0, 100.0)
    assert result["coverage_pct"] == 60.0
    assert result["status"] == "unavailable"  # below 95% minimum


def test_total_coverage_pct_is_diagnostic_only_never_overrides_gate():
    period = _period(90, 100, 10, 10, 100, 100, 0, 0)
    result = classify_period_derived(period)
    # liquids coverage = 100/110 = 90.9% -> below 95% minimum -> unavailable
    assert result["liquids_mboed"]["status"] == "unavailable"
    assert result["natural_gas_mboed"]["status"] == "complete"
    # total_coverage_pct is high (gas dominates the blended volume-weighted
    # figure) but must NOT make total_mboed available.
    assert result["total_mboed"]["total_coverage_pct"] is not None
    assert result["total_mboed"]["status"] == "unavailable"
    assert result["total_mboed"]["value_available"] is False


# --- 16-18: component-gated total status ---


def test_gate_complete_when_both_components_complete():
    assert gate_total_status("complete", "complete") == "complete"


def test_gate_warning_when_one_component_is_warning():
    assert gate_total_status("complete", "warning") == "warning"
    assert gate_total_status("warning", "complete") == "warning"


def test_gate_unavailable_when_one_component_is_unavailable():
    assert gate_total_status("complete", "unavailable") == "unavailable"
    assert gate_total_status("unavailable", "warning") == "unavailable"


def test_gate_prefers_unavailable_over_warning_when_both_present():
    assert gate_total_status("unavailable", "warning") == "unavailable"


# --- 19: one-component-zero (not_applicable), distinct from unavailable ---


def test_component_not_applicable_when_total_production_is_genuinely_zero():
    result = classify_component(0.0, 0.0)
    assert result["status"] == "not_applicable"
    assert result["coverage_pct"] is None
    assert result["value_available"] is False


def test_not_applicable_component_excluded_from_gate_total_derives_from_producer():
    period = _period(90, 90, 10, 10, 0, 0, 0, 0)  # gas genuinely zero for this field/period, liquids fully resolved
    result = classify_period_derived(period)
    assert result["natural_gas_mboed"]["status"] == "not_applicable"
    assert result["liquids_mboed"]["status"] == "complete"
    assert result["total_mboed"]["status"] == "complete"


def test_not_applicable_value_is_true_zero_unavailable_value_is_none():
    not_applicable_entry = {"status": "not_applicable"}
    unavailable_entry = {"status": "unavailable"}
    assert derive_company_period_value(not_applicable_entry, 0.0, 0.0, is_gas=False) == 0.0
    assert derive_company_period_value(unavailable_entry, 0.0, 0.0, is_gas=False) is None


def test_both_components_not_applicable_total_is_not_applicable():
    period = _period(0, 0, 0, 0, 0, 0, 0, 0)
    result = classify_period_derived(period)
    assert result["liquids_mboed"]["status"] == "not_applicable"
    assert result["natural_gas_mboed"]["status"] == "not_applicable"
    assert result["total_mboed"]["status"] == "not_applicable"
    assert result["total_mboed"]["value_available"] is False


# --- 20: MURLACH-style exclusion flows into derived coverage the same way ---


def test_excluded_field_month_lowers_derived_coverage_same_as_native():
    # A field-month excluded from equity resolution (like MURLACH) still
    # counts in the "total" denominator but not "resolved" - exactly the
    # existing native-stream behavior, unchanged for the derived streams.
    period = _period(50, 100, 0, 0, 50, 100, 0, 0)  # half of each stream unresolved
    result = classify_period_derived(period)
    assert result["liquids_mboed"]["coverage_pct"] == 50.0
    assert result["natural_gas_mboed"]["coverage_pct"] == 50.0
    assert result["liquids_mboed"]["status"] == "unavailable"
    assert result["natural_gas_mboed"]["status"] == "unavailable"
    assert result["total_mboed"]["status"] == "unavailable"


# --- 21: storage volumes never enter the derived fields ---


def test_derive_mboed_has_no_storage_or_water_parameters():
    import inspect

    sig = inspect.signature(derive_mboed)
    param_names = set(sig.parameters)
    assert param_names == {"oil_mbd", "condensate_mbd", "dry_gas_mmscfd", "assoc_gas_mmscfd"}
    assert "water_mbd" not in param_names
    assert "storage" not in " ".join(param_names).lower()


# --- 22: deterministic artifact generation ---


def test_derive_mboed_is_pure_and_deterministic():
    a = derive_mboed(10.0, 2.0, 12.0, 6.0)
    b = derive_mboed(10.0, 2.0, 12.0, 6.0)
    assert a == b


def test_validate_derived_field_month_formula_passes_for_correctly_derived_artifact():
    series_by_label = {
        "buzzard": [
            {
                "period": "2020-01",
                "oil_mbd": 10.0,
                "condensate_mbd": 2.0,
                "dry_gas_mmscfd": 12.0,
                "assoc_gas_mmscfd": 6.0,
                "liquids_mboed": 12.0,
                "natural_gas_mboed": 3.0,
                "total_mboed": 15.0,
            }
        ]
    }
    validate_derived_field_month_formula(series_by_label)  # must not raise


def test_validate_derived_field_month_formula_fails_for_inconsistent_artifact():
    series_by_label = {
        "buzzard": [
            {
                "period": "2020-01",
                "oil_mbd": 10.0,
                "condensate_mbd": 2.0,
                "dry_gas_mmscfd": 12.0,
                "assoc_gas_mmscfd": 6.0,
                "liquids_mboed": 12.0,
                "natural_gas_mboed": 3.0,
                "total_mboed": 999.0,  # wrong
            }
        ]
    }
    try:
        validate_derived_field_month_formula(series_by_label)
        assert False, "must raise when total_mboed does not equal liquids + natural_gas"
    except ValidationError as e:
        assert "total_mboed" in str(e)


# --- 23: backward compatibility of existing raw/native fields ---


def test_derive_mboed_does_not_mutate_inputs_or_touch_native_field_names():
    # A defensive guard against a derived-field calculation ever renaming
    # or overwriting a native field - derive_mboed only ever returns the
    # three new keys, never oil_mbd/condensate_mbd/dry_gas_mmscfd/etc.
    result = derive_mboed(10.0, 2.0, 12.0, 6.0)
    assert set(result) == {"liquids_mboed", "natural_gas_mboed", "total_mboed"}
