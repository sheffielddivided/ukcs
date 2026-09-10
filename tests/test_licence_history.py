"""
Unit tests for etl/licence_history.py (Deliverable 3, spec approved
2026-09-10 continuation). No network access - synthetic data shaped
like the live NSTA "UKCS offshore petroleum licence blocks history
(WGS84)" service (item 855237fb38bb44b2afc52a3ea4a48903), confirmed
live on 2026-09-10: HISTORY='N' rows are the current open episode
(LICORG/OPORG/ADMORG populated, *HISNAME fields null); HISTORY='Y'
rows are past episodes (LICORG/OPORG/ADMORG populated with THAT
episode's names).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.licence_history import (  # noqa: E402
    LicenceHistoryError,
    build_history_entry,
    build_history_geojson,
    build_history_meta,
    validate_history_dates,
    validate_no_fabricated_equity_fields,
    validate_source_names_retained,
)


def _row(
    object_id=1,
    history="Y",
    lic_ref="P335",
    block="9/11",
    lic_no=335,
    status="Expired",
    licensee="GETTY OIL (BRITAIN) LIMITED (01006065)",
    licensee_group="GETTY OIL",
    operator="UNOCAL EXPLORATION AND PRODUCTION COMPANY (U.K.) LIMITED",
    operator_group="UNOCAL",
    admin_org="GETTY OIL (BRITAIN) LIMITED (01006065)",
    admin_group="GETTY OIL",
    start_ms=346118400000,  # 1980-12-20
    end_ms=536457600000,  # 1987-01-01
    rings=None,
):
    return {
        "attributes": {
            "OBJECTID": object_id,
            "HISTORY": history,
            "LICNO": lic_no,
            "LICREF": lic_ref,
            "BLOCKREF": block,
            "LICSTATUS": status,
            "BLCKSTRTDT": start_ms,
            "BLCKENDDT": end_ms,
            "LICORG": licensee,
            "LICORGGRP": licensee_group,
            "OPORG": operator,
            "OPORGGRP": operator_group,
            "ADMORG": admin_org,
            "ADMORGGRP": admin_group,
        },
        "geometry": {"rings": rings if rings is not None else [[[1.0, 58.0], [1.1, 58.0], [1.1, 58.1], [1.0, 58.0]]]},
    }


# ---------------------------------------------------------------------------
# Per-row detail
# ---------------------------------------------------------------------------


def test_build_history_entry_preserves_source_fields_exactly():
    entry = build_history_entry(_row())
    assert entry["licence_reference"] == "P335"
    assert entry["block_reference"] == "9/11"
    assert entry["licence_status"] == "Expired"
    assert entry["start_date"] == "1980-12-20"
    assert entry["end_date"] == "1987-01-01"
    assert entry["licensee_names"] == "GETTY OIL (BRITAIN) LIMITED (01006065)"
    assert entry["operator_names"] == "UNOCAL EXPLORATION AND PRODUCTION COMPANY (U.K.) LIMITED"
    assert entry["is_current_episode"] is False


def test_build_history_entry_marks_history_n_as_current_episode():
    entry = build_history_entry(_row(history="N", end_ms=None))
    assert entry["is_current_episode"] is True
    assert entry["end_date"] is None  # open-ended, not a defect


def test_build_history_entry_never_fabricates_an_equity_field():
    entry = build_history_entry(_row())
    assert not any("equity" in k.lower() for k in entry)
    assert not any("pct" in k.lower() for k in entry)


# ---------------------------------------------------------------------------
# GeoJSON
# ---------------------------------------------------------------------------


def test_build_history_geojson_one_feature_per_row_with_stable_episode_id():
    rows = [_row(object_id=1), _row(object_id=2, lic_ref="P920", history="N", end_ms=None)]
    geojson = build_history_geojson(rows)
    assert len(geojson["features"]) == 2
    ids = {f["properties"]["episode_id"] for f in geojson["features"]}
    assert ids == {1, 2}


def test_build_history_geojson_skips_rows_with_no_geometry():
    rows = [_row(object_id=1, rings=[])]
    geojson = build_history_geojson(rows)
    assert geojson["features"] == []


def test_build_history_geojson_preserves_overlapping_records_without_picking_one():
    """Two rows covering the SAME block with overlapping dates (e.g. a
    licence-transfer boundary case) must both survive as separate
    features - this pipeline never collapses or picks a 'winner'."""
    rows = [
        _row(object_id=1, block="9/11", start_ms=346118400000, end_ms=536457600000, licensee="OWNER A"),
        _row(object_id=2, block="9/11", start_ms=346118400000, end_ms=536457600000, licensee="OWNER B"),
    ]
    geojson = build_history_geojson(rows)
    assert len(geojson["features"]) == 2
    licensees = {f["properties"]["licensee_names"] for f in geojson["features"]}
    assert licensees == {"OWNER A", "OWNER B"}


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------


def test_build_history_meta_reports_date_range_and_distinct_groups():
    rows = [
        _row(object_id=1, operator_group="ALPHA", status="Expired", start_ms=346118400000, end_ms=536457600000),
        _row(object_id=2, operator_group="BETA", status="Extant", history="N", start_ms=1384732800000, end_ms=None),
    ]
    meta = build_history_meta(rows, "https://example.invalid", "Blocks history", 2)
    assert meta["record_count"] == 2
    assert meta["earliest_start_date"] == "1980-12-20"
    assert meta["latest_start_date"] == "2013-11-18"
    assert meta["open_ended_count"] == 1
    assert set(meta["distinct_operator_groups"]) == {"ALPHA", "BETA"}
    assert set(meta["distinct_licence_statuses"]) == {"Expired", "Extant"}
    assert meta["source"]["item_title"] == "Blocks history"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validate_no_fabricated_equity_fields_passes_on_clean_geojson():
    geojson = build_history_geojson([_row()])
    validate_no_fabricated_equity_fields(geojson)  # must not raise


def test_validate_no_fabricated_equity_fields_catches_a_fabricated_field():
    geojson = build_history_geojson([_row()])
    geojson["features"][0]["properties"]["equity_pct"] = 50.0
    try:
        validate_no_fabricated_equity_fields(geojson)
        assert False, "expected LicenceHistoryError"
    except LicenceHistoryError as e:
        assert "equity_pct" in str(e)


def test_validate_history_dates_passes_on_clean_rows():
    rows = [_row(start_ms=346118400000, end_ms=536457600000), _row(object_id=2, history="N", end_ms=None)]
    validate_history_dates(rows)  # must not raise


def test_validate_history_dates_catches_missing_start_date():
    rows = [_row(start_ms=None)]
    try:
        validate_history_dates(rows)
        assert False, "expected LicenceHistoryError"
    except LicenceHistoryError as e:
        assert "missing start_date" in str(e)


def test_validate_history_dates_catches_end_before_start():
    rows = [_row(start_ms=536457600000, end_ms=346118400000)]
    try:
        validate_history_dates(rows)
        assert False, "expected LicenceHistoryError"
    except LicenceHistoryError as e:
        assert "before start_date" in str(e)


def test_validate_source_names_retained_passes_on_clean_rows():
    rows = [_row()]
    validate_source_names_retained(rows)  # must not raise


def test_validate_source_names_retained_catches_a_blank_licensee_name():
    rows = [_row(licensee="")]
    try:
        validate_source_names_retained(rows)
        assert False, "expected LicenceHistoryError"
    except LicenceHistoryError as e:
        assert "1" in str(e)
