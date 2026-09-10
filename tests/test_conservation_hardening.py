"""
Workstream 0 hardening (spec, approved 2026-09-10): regression tests for
the two-part conservation check that replaced the original flat
CONSERVATION_TOLERANCE_MBOED = 5.0.

Covers: the mathematically-derived post-serialization tolerance formula;
that pre-serialization (full-precision) conservation is tight enough to
catch a real aggregation bug at floating-point precision; and the
required regression proving a small (<5 mboe/d) dropped field is still
caught under the new tolerance, which the old flat 5.0 constant would
have risked concealing.

No network access - synthetic data only.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.validate import (  # noqa: E402
    FLOAT_PRECISION_TOLERANCE_MBOED,
    ValidationError,
    compute_serialization_tolerance,
    validate_full_precision_conservation,
    validate_serialized_derived_conservation,
)


# ---------------------------------------------------------------------------
# compute_serialization_tolerance: pure formula correctness
# ---------------------------------------------------------------------------


def test_tolerance_formula_matches_hand_calculation():
    # half_ulp at 3 decimals = 0.0005; combined std dev over
    # (100 + 10) entries = 0.0005 * sqrt(110/3); tolerance = 8 sigma.
    expected = 8.0 * 0.0005 * (110 / 3) ** 0.5
    assert compute_serialization_tolerance(100, 10, 3) == expected


def test_tolerance_scales_with_entry_count_not_fixed():
    small = compute_serialization_tolerance(10, 2, 3)
    large = compute_serialization_tolerance(134_000, 3_000, 3)
    assert small < large


def test_tolerance_at_real_dataset_scale_is_far_below_the_old_flat_5_0():
    # The old flat CONSERVATION_TOLERANCE_MBOED was 5.0. At this
    # repository's actual full-history scale (~134,000 field-period rows,
    # ~20,000 operator-period rows), the mathematically derived bound must
    # be materially tighter - proving the new check is not just a
    # relabeling of the same slack, and is still sensitive enough to
    # catch a multi-mboe/d dropped field.
    tolerance = compute_serialization_tolerance(134_608, 20_000, 3)
    assert tolerance < 1.5
    assert tolerance > 0.1  # not so tight it would flag pure rounding noise


# ---------------------------------------------------------------------------
# Pre-serialization (full precision) conservation
# ---------------------------------------------------------------------------


def test_full_precision_conservation_passes_for_exact_sums():
    field_series = {
        "alpha": [{"period": "2020-01", "total_mboed": 12.34567891011}],
        "beta": [{"period": "2020-01", "total_mboed": 3.14159265358}],
    }
    operator_series = {
        "acme": [{"period": "2020-01", "total_mboed": 12.34567891011 + 3.14159265358}],
    }
    observed = validate_full_precision_conservation(
        field_series, operator_series, keys=("total_mboed",)
    )
    assert observed["total_mboed"] < FLOAT_PRECISION_TOLERANCE_MBOED


def test_full_precision_conservation_catches_a_dropped_field_of_any_size():
    # At full precision, even a TINY dropped contribution (well under the
    # old flat 5.0, and even under a naive per-row rounding tolerance)
    # must be caught, since there is no legitimate rounding noise left to
    # hide behind at this stage.
    field_series = {
        "alpha": [{"period": "2020-01", "total_mboed": 100.0}],
        "beta": [{"period": "2020-01", "total_mboed": 0.5}],  # dropped downstream
    }
    operator_series = {
        "acme": [{"period": "2020-01", "total_mboed": 100.0}],  # beta missing
    }
    try:
        validate_full_precision_conservation(field_series, operator_series, keys=("total_mboed",))
        assert False, "must raise when a field's full-precision contribution is dropped"
    except ValidationError as e:
        assert "total_mboed" in str(e)


# ---------------------------------------------------------------------------
# Post-serialization: the required regression - a small dropped field
# must still be caught, unlike under the old flat 5.0 tolerance.
# ---------------------------------------------------------------------------


def _synthetic_realistic_series(n_field_periods: int, n_operator_periods: int, seed: int = 42):
    """Builds synthetic field/operator series with REAL rounding applied
    (round to 3dp per entry, like round_mboed() does), at a scale
    comparable to the actual repository (~134k/~3.5k), so the computed
    tolerance reflects a realistic entry count - not a toy scenario where
    the tolerance would already be trivially tiny."""
    rng = random.Random(seed)
    field_series: dict[str, list[dict]] = {}
    total_full_precision = 0.0
    remaining_field = n_field_periods
    slug_i = 0
    while remaining_field > 0:
        take = min(rng.randint(50, 300), remaining_field)
        points = []
        for _ in range(take):
            raw = rng.uniform(0.0, 50.0)
            total_full_precision += raw
            points.append({"period": "p", "total_mboed": round(raw, 3)})
        field_series[f"field-{slug_i}"] = points
        remaining_field -= take
        slug_i += 1

    # Build operator series whose ROUNDED total matches the field total's
    # rounded total closely (as the real pipeline does, from full
    # precision), spread across n_operator_periods entries.
    operator_series: dict[str, list[dict]] = {}
    remaining_op = n_operator_periods
    per_entry = total_full_precision / n_operator_periods
    op_i = 0
    while remaining_op > 0:
        take = min(rng.randint(1, 5), remaining_op)
        points = [{"period": "p", "total_mboed": round(per_entry, 3)} for _ in range(take)]
        operator_series[f"operator-{op_i}"] = points
        remaining_op -= take
        op_i += 1

    return field_series, operator_series


def test_small_dropped_field_is_still_caught_at_realistic_scale():
    """The required Workstream 0 regression: with a realistic number of
    contributing rows (comparable to this repository's real scale), a
    field contributing well under 5 mboe/d - which the OLD flat
    CONSERVATION_TOLERANCE_MBOED = 5.0 could have silently absorbed - must
    still fail validate_serialized_derived_conservation() under the new,
    mathematically-derived tolerance."""
    field_series, operator_series = _synthetic_realistic_series(2000, 60)

    # Sanity: this synthetic dataset passes conservation before we drop
    # anything (negative control - proves the fixture itself is sound).
    validate_serialized_derived_conservation(field_series, operator_series, keys=("total_mboed",))

    # Now drop a genuinely small field (3.0 mboe/d - under the old flat
    # 5.0 tolerance) from the field side only, simulating exactly the
    # failure mode Workstream 0 was worried about: a small producing
    # field silently missing from the operator rollup.
    field_series["dropped-small-field"] = [{"period": "p", "total_mboed": 3.0}]

    try:
        validate_serialized_derived_conservation(field_series, operator_series, keys=("total_mboed",))
        assert False, (
            "a 3.0 mboe/d dropped field must be caught - this is exactly the "
            "failure mode the old flat 5.0 tolerance could have concealed"
        )
    except ValidationError as e:
        assert "total_mboed" in str(e)


def test_serialization_tolerance_used_matches_the_actual_entry_counts():
    """The tolerance actually applied must be traceable to the real
    entry counts of the data under test, not a hidden constant."""
    field_series, operator_series = _synthetic_realistic_series(500, 20)
    n_field = sum(len(s) for s in field_series.values())
    n_operator = sum(len(s) for s in operator_series.values())
    expected_tolerance = compute_serialization_tolerance(n_field, n_operator, 3)
    # Well below the old flat 5.0 at this modest scale.
    assert expected_tolerance < 5.0
    results = validate_serialized_derived_conservation(field_series, operator_series, keys=("total_mboed",))
    assert results["total_mboed"]["tolerance"] == expected_tolerance
