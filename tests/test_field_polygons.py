"""
Unit tests for etl/field_polygons.py (Workstream 3, spec approved
2026-09-10). No network access - synthetic data shaped like the live
NSTA field-determinations service.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.field_polygons import (  # noqa: E402
    build_field_polygons_geojson,
    match_polygons_to_pprs,
    unmatched_production_impact,
)


def _polygon_row(field_no, fieldname, rings=None):
    return {
        "attributes": {"FIELD_NO": field_no, "FIELDNAME": fieldname, "FD_STAT": "CURRENT"},
        "geometry": {"rings": rings or [[[0.0, 58.0], [0.1, 58.0], [0.1, 58.1], [0.0, 58.0]]]},
    }


# ---------------------------------------------------------------------------
# Matching (reuses equity_match.match_fields - just confirm the wiring)
# ---------------------------------------------------------------------------


def test_match_polygons_exact():
    result = match_polygons_to_pprs({"FORTIES"}, {"FORTIES"})
    assert result["exact_matches"] == {"FORTIES": "FORTIES"}


def test_match_polygons_normalized_case_difference():
    # Live service uses title case ("Forties"), PPRS uses upper case.
    result = match_polygons_to_pprs({"FORTIES"}, {"Forties"})
    assert result["normalized_matches"] == {"FORTIES": "Forties"}


def test_match_polygons_unmatched_field_not_dropped_from_result():
    result = match_polygons_to_pprs({"FORTIES", "BUZZARD"}, {"Forties"})
    assert "BUZZARD" in result["unmatched_pprs"]


# ---------------------------------------------------------------------------
# GeoJSON construction
# ---------------------------------------------------------------------------


def test_build_field_polygons_geojson_matched_feature_has_slug():
    rows = [_polygon_row("100", "Forties")]
    match_result = match_polygons_to_pprs({"FORTIES"}, {"Forties"})
    fc = build_field_polygons_geojson(rows, match_result)
    assert len(fc["features"]) == 1
    props = fc["features"][0]["properties"]
    assert props["matched_pprs_field"] == "FORTIES"
    assert props["matched_pprs_slug"] == "forties"
    assert props["match_method"] == "normalized"


def test_build_field_polygons_geojson_unmatched_feature_still_published():
    # An unmatched polygon (no PPRS field of that name) is still real
    # NSTA geometry and must be published, not dropped.
    rows = [_polygon_row("999", "SOME UNKNOWN FIELD")]
    match_result = match_polygons_to_pprs({"FORTIES"}, {"SOME UNKNOWN FIELD"})
    fc = build_field_polygons_geojson(rows, match_result)
    assert len(fc["features"]) == 1
    props = fc["features"][0]["properties"]
    assert props["matched_pprs_field"] is None
    assert props["matched_pprs_slug"] is None


def test_build_field_polygons_geojson_geometry_is_valid_wgs84_polygon():
    rows = [_polygon_row("100", "Forties")]
    match_result = match_polygons_to_pprs({"FORTIES"}, {"Forties"})
    fc = build_field_polygons_geojson(rows, match_result)
    geometry = fc["features"][0]["geometry"]
    assert geometry["type"] == "Polygon"
    assert len(geometry["coordinates"]) == 1
    # Coordinates should be [lon, lat] pairs within a plausible WGS84 range.
    for lon, lat in geometry["coordinates"][0]:
        assert -180 <= lon <= 180
        assert -90 <= lat <= 90


# ---------------------------------------------------------------------------
# Unmatched production impact
# ---------------------------------------------------------------------------


def test_unmatched_production_impact_computes_percentage():
    totals = {"FORTIES": 100.0, "BUZZARD": 20.0, "SMALLFIELD": 5.0}
    impact = unmatched_production_impact(["SMALLFIELD"], totals)
    assert impact["unmatched_field_count"] == 1
    assert impact["unmatched_total_mboed"] == 5.0
    assert impact["unmatched_production_pct"] == round(100.0 * 5.0 / 125.0, 3)


def test_unmatched_production_impact_no_unmatched_fields():
    totals = {"FORTIES": 100.0}
    impact = unmatched_production_impact([], totals)
    assert impact["unmatched_field_count"] == 0
    assert impact["unmatched_total_mboed"] == 0.0
    assert impact["unmatched_production_pct"] == 0.0
