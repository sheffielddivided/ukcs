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
    aggregate_latest_period,
    build_fields_geojson,
    round3,
    slugify,
)


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
