"""
Unit tests for etl/licence_portfolio.py (Workstream 4, spec approved
2026-09-10). No network access - synthetic data shaped like the live
NSTA licence-subareas-by-equity-group-holder service.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.licence_portfolio import (  # noqa: E402
    build_portfolio_by_group,
    build_portfolio_entry,
    build_portfolio_geojson,
)


def _row(
    lic_ref="P461",
    subarea="ALL",
    block="48/12f",
    holder="PERENCO OIL & GAS",
    operator="PERENCO OIL & GAS",
    equity=85.0,
    status="Extant",
    start_ms=421459200000,
    end_ms=None,
    rings=None,
):
    return {
        "attributes": {
            "LICNO": 461,
            "LICREF": lic_ref,
            "BLOCKREF": block,
            "SUBAREANAM": subarea,
            "LICSTATUS": status,
            "LICSTARTDT": start_ms,
            "LICENDDT": end_ms,
            "EQGRPHOLD": holder,
            "EQUITY": equity,
            "OPORGGRP": operator,
        },
        "geometry": {"rings": rings if rings is not None else [[[0.0, 58.0], [0.1, 58.0], [0.1, 58.1], [0.0, 58.0]]]},
    }


# ---------------------------------------------------------------------------
# Per-row detail
# ---------------------------------------------------------------------------


def test_build_portfolio_entry_preserves_source_fields_exactly():
    entry = build_portfolio_entry(_row())
    assert entry["licence_reference"] == "P461"
    assert entry["equity_pct"] == 85.0
    assert entry["licence_status"] == "Extant"
    assert entry["licence_start_date"] == "1983-05-11"  # 421459200000 ms
    assert entry["licence_end_date"] is None  # open-ended, never fabricated


def test_build_portfolio_entry_operated_when_holder_equals_operator():
    entry = build_portfolio_entry(_row(holder="PERENCO OIL & GAS", operator="PERENCO OIL & GAS"))
    assert entry["operated"] is True


def test_build_portfolio_entry_non_operated_when_holder_differs_from_operator():
    entry = build_portfolio_entry(_row(holder="EVERARD ENERGY", operator="PERENCO OIL & GAS"))
    assert entry["operated"] is False


def test_build_portfolio_entry_no_percentage_fabricated_if_absent():
    row = _row()
    row["attributes"]["EQUITY"] = None
    entry = build_portfolio_entry(row)
    assert entry["equity_pct"] is None


# ---------------------------------------------------------------------------
# Grouping by current display group
# ---------------------------------------------------------------------------


def test_build_portfolio_by_group_groups_directly_by_eqgrphold():
    rows = [
        _row(lic_ref="P461", holder="PERENCO OIL & GAS", operator="PERENCO OIL & GAS"),
        _row(lic_ref="P1764", holder="PERENCO OIL & GAS", operator="APACHE CORPORATION"),
    ]
    by_group = build_portfolio_by_group(rows)
    assert "PERENCO OIL & GAS" in by_group
    group = by_group["PERENCO OIL & GAS"]
    assert group["distinct_licence_count"] == 2
    assert group["operated_count"] == 1
    assert group["non_operated_count"] == 1


def test_build_portfolio_by_group_distinct_subarea_count_deduplicates():
    rows = [
        _row(lic_ref="P461", subarea="ALL", block="48/12f"),
        _row(lic_ref="P461", subarea="ALL", block="48/12f"),  # exact duplicate row
    ]
    by_group = build_portfolio_by_group(rows)
    group = by_group["PERENCO OIL & GAS"]
    assert group["distinct_subarea_count"] == 1


def test_build_portfolio_by_group_unmapped_holder_never_dropped():
    row = _row()
    row["attributes"]["EQGRPHOLD"] = None
    by_group = build_portfolio_by_group([row])
    assert "Unmapped" in by_group
    assert by_group["Unmapped"]["distinct_licence_count"] == 1


# ---------------------------------------------------------------------------
# GeoJSON construction
# ---------------------------------------------------------------------------


def test_build_portfolio_geojson_valid_wgs84_polygon():
    fc = build_portfolio_geojson([_row()])
    assert len(fc["features"]) == 1
    geometry = fc["features"][0]["geometry"]
    assert geometry["type"] == "Polygon"
    for lon, lat in geometry["coordinates"][0]:
        assert -180 <= lon <= 180
        assert -90 <= lat <= 90


def test_build_portfolio_geojson_skips_rows_with_no_geometry():
    row = _row(rings=[])
    fc = build_portfolio_geojson([row])
    assert fc["features"] == []
