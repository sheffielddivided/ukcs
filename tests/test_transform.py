"""
Unit tests for etl/transform.py aggregation (spec section 7.4 / 9 / 14).

Covers the acceptance criterion "field-level totals equal the sum of their
production reporting units" and the ROUGH storage-exclusion case
specifically, using synthetic rows rather than the live service.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.transform import (  # noqa: E402
    aggregate_history,
    aggregate_latest_period,
    aggregate_operators,
    build_fields_geojson,
    build_history_artifacts,
    build_operators_artifacts,
    round3,
    slugify,
)


def _hrow(field, unit, period, oil=0.0, dgas=0.0, agas=0.0, cond=0.0, water=0.0):
    """Attributes-only row (no geometry) for history aggregation tests."""
    return {
        "attributes": {
            "FIELDNAME": field,
            "UNITNAME": unit,
            "FIELDAREA": "SNS",
            "LOCATION": "Offshore",
            "ORGGRPNM": "OPERATOR CO",
            "PERIODYRMN": period,
            "OILPRODMBD": oil,
            "AGASPROMMS": agas,
            "DGASPROMMS": dgas,
            "GCONDMBD": cond,
            "WATPRODMBD": water,
        }
    }


def _row(field, unit, lon, lat, oil=0.0, dgas=0.0, agas=0.0, cond=0.0, water=0.0):
    return {
        "attributes": {
            "FIELDNAME": field,
            "UNITNAME": unit,
            "FIELDAREA": "SNS",
            "LOCATION": "Offshore",
            "ORGGRPNM": "OPERATOR CO",
            "PERIODYRMN": "202606",
            "OILPRODMBD": oil,
            "AGASPROMMS": agas,
            "DGASPROMMS": dgas,
            "GCONDMBD": cond,
            "WATPRODMBD": water,
        },
        "geometry": {"x": lon, "y": lat},
    }


def test_single_unit_field_sums_directly():
    rows = [_row("BUZZARD", "BUZZARD", 1.0, 57.0, oil=100.0)]
    records, stats = aggregate_latest_period(rows, {})
    assert stats["raw_field_count"] == 1
    assert stats["production_field_count"] == 1
    assert records[0].totals["oil_mbd"] == 100.0
    assert (records[0].lon, records[0].lat) == (1.0, 57.0)


def test_rough_storage_unit_excluded_from_totals_and_centroid():
    """The core section 7.3 requirement: ROUGH STORAGE must not be summed
    into ROUGH's production, and must not pull the field's marker."""
    rows = [
        _row("ROUGH", "ROUGH PRODUCTION", lon=0.4, lat=53.8, dgas=25.0),
        _row("ROUGH", "ROUGH STORAGE", lon=99.0, lat=99.0, dgas=1500.0),
    ]
    classification_map = {("ROUGH", "ROUGH STORAGE"): "storage"}
    records, stats = aggregate_latest_period(rows, classification_map)

    assert len(records) == 1
    record = records[0]
    # Totals must equal the sum of PRODUCTION units only.
    assert record.totals["dry_gas_mmscfd"] == 25.0
    # Centroid must come only from the production unit's geometry - the
    # storage unit's wildly different (99, 99) coordinates must not
    # appear in it at all.
    assert (record.lon, record.lat) == (0.4, 53.8)
    assert len(record.production_units) == 1
    assert len(record.storage_units) == 1
    assert record.storage_units[0]["name"] == "ROUGH STORAGE"
    assert stats["production_unit_count"] == 1
    assert stats["storage_unit_count"] == 1


def test_field_totals_equal_sum_of_production_units_multi_unit_case():
    """A field with more than one PRODUCTION unit (not a storage split)
    must still sum correctly and centroid over both points."""
    rows = [
        _row("MULTI", "MULTI A", lon=1.0, lat=57.0, oil=10.0),
        _row("MULTI", "MULTI B", lon=3.0, lat=59.0, oil=20.0),
    ]
    records, stats = aggregate_latest_period(rows, {})
    record = records[0]
    assert record.totals["oil_mbd"] == 30.0
    assert record.lon == 2.0  # midpoint of 1.0 and 3.0
    assert record.lat == 58.0
    assert len(record.production_units) == 2


def test_storage_only_field_is_excluded_entirely_not_silently_summed():
    rows = [_row("PURE_STORE", "PURE STORE UNIT", lon=0.0, lat=55.0, dgas=5.0)]
    classification_map = {("PURE_STORE", "PURE STORE UNIT"): "storage"}
    records, stats = aggregate_latest_period(rows, classification_map)

    assert records == []
    assert stats["storage_only_field_count"] == 1
    assert stats["storage_only_fields"] == ["PURE_STORE"]
    assert stats["raw_field_count"] == 1
    assert stats["production_field_count"] == 0


def test_unclassified_unit_defaults_to_production():
    """A brand-new, ordinary field/unit not in unit_classification.csv
    must default to production and pass through untouched - the CSV is
    exceptions-only (spec section 7.3)."""
    rows = [_row("NEW_FIELD", "NEW_FIELD", lon=1.0, lat=56.0, oil=5.0)]
    records, stats = aggregate_latest_period(rows, {})
    assert len(records) == 1
    assert records[0].totals["oil_mbd"] == 5.0


def test_round3_collapses_negative_zero():
    assert round3(-0.0000001) == 0.0
    assert str(round3(-0.0000001)) == "0.0"


def test_slugify_deterministic_and_lossless_enough():
    assert slugify("ROUGH") == "rough"
    assert slugify("COLUMBA B/D") == "columba-b-d"
    assert slugify("  DONAN [MAERSK]  ") == "donan-maersk"


def test_build_fields_geojson_sorted_by_slug():
    rows = [
        _row("ZULU", "ZULU", lon=1.0, lat=57.0, oil=1.0),
        _row("ALPHA", "ALPHA", lon=1.0, lat=57.0, oil=1.0),
    ]
    records, _ = aggregate_latest_period(rows, {})
    geojson = build_fields_geojson(records)
    slugs = [f["properties"]["slug"] for f in geojson["features"]]
    assert slugs == sorted(slugs)
    assert slugs == ["alpha", "zulu"]


# --- aggregate_history (spec section 9.3 / 13 step 5) ---


def test_history_rough_storage_excluded_from_every_period_not_just_latest():
    """The double-counting risk section 7.3 exists for is exactly this:
    a storage unit reporting nonzero volumes in an EARLIER period, not
    just the latest one. Must be excluded throughout the series."""
    rows = [
        _hrow("ROUGH", "ROUGH PRODUCTION", "200001", dgas=10.0),
        _hrow("ROUGH", "ROUGH STORAGE", "200001", dgas=999.0),
        _hrow("ROUGH", "ROUGH PRODUCTION", "200002", dgas=12.0),
        _hrow("ROUGH", "ROUGH STORAGE", "200002", dgas=888.0),
    ]
    classification_map = {("ROUGH", "ROUGH STORAGE"): "storage"}
    histories, stats = aggregate_history(rows, classification_map)

    assert len(histories) == 1
    h = histories[0]
    assert [s["period"] for s in h.series] == ["200001", "200002"]
    assert [s["dry_gas_mmscfd"] for s in h.series] == [10.0, 12.0]
    assert h.storage_units[0]["name"] == "ROUGH STORAGE"
    assert stats["storage_row_count"] == 2
    assert stats["production_row_count"] == 2


def test_history_rename_case_produces_one_continuous_series():
    """SEAN -> NORTH SEAN (spec section 7.2): both unit names share one
    FIELDNAME and their periods never overlap, so the series must be
    continuous across the boundary with no gap, while the unit list still
    exposes both names and their date ranges (the discontinuity must be
    visible, not smoothed over)."""
    rows = [
        _hrow("NORTH SEAN", "SEAN", "201703", dgas=5.0),
        _hrow("NORTH SEAN", "SEAN", "201704", dgas=6.0),
        _hrow("NORTH SEAN", "NORTH SEAN", "201705", dgas=7.0),
        _hrow("NORTH SEAN", "NORTH SEAN", "201706", dgas=8.0),
    ]
    histories, _ = aggregate_history(rows, {})
    assert len(histories) == 1
    h = histories[0]
    periods = [s["period"] for s in h.series]
    assert periods == ["201703", "201704", "201705", "201706"], (
        "series must be continuous across the rename boundary, no gap or duplicate"
    )
    values = [s["dry_gas_mmscfd"] for s in h.series]
    assert values == [5.0, 6.0, 7.0, 8.0]
    unit_names = {u["name"] for u in h.production_units}
    assert unit_names == {"SEAN", "NORTH SEAN"}
    sean_unit = next(u for u in h.production_units if u["name"] == "SEAN")
    north_sean_unit = next(u for u in h.production_units if u["name"] == "NORTH SEAN")
    assert sean_unit["last_period"] == "201704"
    assert north_sean_unit["first_period"] == "201705"


def test_history_storage_only_field_excluded_entirely():
    rows = [_hrow("PURE_STORE", "PURE STORE UNIT", "200001", dgas=5.0)]
    classification_map = {("PURE_STORE", "PURE STORE UNIT"): "storage"}
    histories, stats = aggregate_history(rows, classification_map)
    assert histories == []
    assert stats["storage_only_field_count"] == 1
    assert stats["storage_only_fields"] == ["PURE_STORE"]


def test_history_operator_region_taken_from_most_recent_period():
    """Section 6.1's 'current operator of record' convention applied to
    history: metadata should reflect the most recent production period,
    not an arbitrary historical one."""
    rows = [
        {
            "attributes": {
                "FIELDNAME": "BUZZARD", "UNITNAME": "BUZZARD",
                "FIELDAREA": "OLD REGION", "LOCATION": "Offshore",
                "ORGGRPNM": "OLD OPERATOR", "PERIODYRMN": "200001",
                "OILPRODMBD": 1.0, "AGASPROMMS": 0.0, "DGASPROMMS": 0.0,
                "GCONDMBD": 0.0, "WATPRODMBD": 0.0,
            }
        },
        {
            "attributes": {
                "FIELDNAME": "BUZZARD", "UNITNAME": "BUZZARD",
                "FIELDAREA": "NEW REGION", "LOCATION": "Offshore",
                "ORGGRPNM": "NEW OPERATOR", "PERIODYRMN": "200606",
                "OILPRODMBD": 2.0, "AGASPROMMS": 0.0, "DGASPROMMS": 0.0,
                "GCONDMBD": 0.0, "WATPRODMBD": 0.0,
            }
        },
    ]
    histories, _ = aggregate_history(rows, {})
    h = histories[0]
    assert h.operator == "NEW OPERATOR"
    assert h.region == "NEW REGION"


def test_build_history_artifacts_index_first_last_period():
    rows = [
        _hrow("BUZZARD", "BUZZARD", "200001", oil=1.0),
        _hrow("BUZZARD", "BUZZARD", "200606", oil=2.0),
    ]
    histories, _ = aggregate_history(rows, {})
    per_slug, index = build_history_artifacts(histories)
    assert index["buzzard"]["first_period"] == "200001"
    assert index["buzzard"]["last_period"] == "200606"
    assert per_slug["buzzard"]["series"][0]["period"] == "200001"


# --- aggregate_operators (spec section 9.4 / 13 step 7) ---


def test_operators_sum_multiple_fields_same_operator_same_period():
    rows = [
        _hrow("FIELD_A", "FIELD_A", "200606", oil=10.0),
        _hrow("FIELD_B", "FIELD_B", "200606", oil=5.0),
    ]
    # Both fields' most recent (only) period has the same operator.
    rows[0]["attributes"]["ORGGRPNM"] = "BIG OPERATOR"
    rows[1]["attributes"]["ORGGRPNM"] = "BIG OPERATOR"
    histories, _ = aggregate_history(rows, {})
    operator_histories, stats = aggregate_operators(histories)

    assert stats["operator_count"] == 1
    op = operator_histories[0]
    assert op.name == "BIG OPERATOR"
    assert sorted(op.field_slugs) == ["field-a", "field-b"]
    assert op.series == [{"period": "200606", "oil_mbd": 15.0, "assoc_gas_mmscfd": 0.0,
                           "dry_gas_mmscfd": 0.0, "condensate_mbd": 0.0, "water_mbd": 0.0,
                           "liquids_mboed": 15.0, "natural_gas_mboed": 0.0, "total_mboed": 15.0}]


def test_operators_inherit_storage_exclusion_from_field_history():
    """A storage unit excluded from a field's history (section 7.3) must
    stay excluded once that field's history is rolled up to its
    operator - the operator aggregation must not re-introduce storage
    volumes by operating on raw rows instead of the already-filtered
    FieldHistory series."""
    rows = [
        _hrow("ROUGH", "ROUGH PRODUCTION", "200601", dgas=10.0),
        _hrow("ROUGH", "ROUGH STORAGE", "200601", dgas=999.0),
    ]
    classification_map = {("ROUGH", "ROUGH STORAGE"): "storage"}
    histories, _ = aggregate_history(rows, classification_map)
    operator_histories, _ = aggregate_operators(histories)

    op = operator_histories[0]
    assert op.series[0]["dry_gas_mmscfd"] == 10.0


def test_operators_different_operators_kept_separate():
    rows = [
        _hrow("FIELD_A", "FIELD_A", "200606", oil=10.0),
        _hrow("FIELD_B", "FIELD_B", "200606", oil=5.0),
    ]
    rows[0]["attributes"]["ORGGRPNM"] = "OPERATOR ONE"
    rows[1]["attributes"]["ORGGRPNM"] = "OPERATOR TWO"
    histories, _ = aggregate_history(rows, {})
    operator_histories, stats = aggregate_operators(histories)

    assert stats["operator_count"] == 2
    by_name = {op.name: op for op in operator_histories}
    assert by_name["OPERATOR ONE"].series[0]["oil_mbd"] == 10.0
    assert by_name["OPERATOR TWO"].series[0]["oil_mbd"] == 5.0


def test_operators_conservation_total_volume_unchanged():
    """Summing a value field across every operator-period entry must equal
    summing it across every field-period entry - attributing fields to
    operators is a repartition, it must never add or drop volume."""
    rows = [
        _hrow("FIELD_A", "FIELD_A", "200601", oil=10.0),
        _hrow("FIELD_A", "FIELD_A", "200602", oil=12.0),
        _hrow("FIELD_B", "FIELD_B", "200601", oil=3.0),
    ]
    rows[0]["attributes"]["ORGGRPNM"] = "OP1"
    rows[1]["attributes"]["ORGGRPNM"] = "OP1"
    rows[2]["attributes"]["ORGGRPNM"] = "OP2"
    histories, _ = aggregate_history(rows, {})
    operator_histories, _ = aggregate_operators(histories)

    field_total = sum(p["oil_mbd"] for h in histories for p in h.series)
    operator_total = sum(p["oil_mbd"] for op in operator_histories for p in op.series)
    assert field_total == operator_total == 25.0


def test_build_operators_artifacts_index_has_latest_not_full_series():
    rows = [
        _hrow("FIELD_A", "FIELD_A", "200601", oil=1.0),
        _hrow("FIELD_A", "FIELD_A", "200602", oil=2.0),
    ]
    rows[0]["attributes"]["ORGGRPNM"] = "OP1"
    rows[1]["attributes"]["ORGGRPNM"] = "OP1"
    histories, _ = aggregate_history(rows, {})
    operator_histories, _ = aggregate_operators(histories)
    index, per_slug = build_operators_artifacts(operator_histories)

    assert index["op1"]["field_count"] == 1
    assert index["op1"]["latest"]["period"] == "200602"
    assert "series" not in index["op1"]
    assert per_slug["op1"]["generated_from"] == "current operator of record"
    assert [p["period"] for p in per_slug["op1"]["series"]] == ["200601", "200602"]
