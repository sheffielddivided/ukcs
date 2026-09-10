"""
Historical licence-interest pipeline (Deliverable 3, spec approved
2026-09-10 continuation).

Uses NSTA's "UKCS offshore petroleum licence blocks history (WGS84)"
service - the dataset identified in the Phase 3 discovery report
(section 5.6, question 2) as the only one of the five licence/block/
subarea datasets with real historical name and date reconstruction
(BLCKSTRTDT/BLCKENDDT, LICORG/OPORG per historical episode). Item ID
resolved at build time via fetch_item_metadata(), never hardcoded as a
service URL (same discipline as every other ArcGIS source in this
project).

Every row is one block's ONE historical licensing episode: HISTORY='N'
rows are the current (open-ended or not) episode, HISTORY='Y' rows are
past episodes. Live inspection (2026-09-10) confirmed LICORG/OPORG/
ADMORG are populated identically for both - the separate LICHISNAME/
OPHISNAMES/ADMHISNAME fields only ever duplicate LICORG/OPORG/ADMORG on
HISTORY='Y' rows and are null on HISTORY='N' rows, so this module reads
LICORG/OPORG/ADMORG uniformly rather than branching on HISTORY - one
fewer special case, same information.

Explicitly does NOT add a historical equity percentage anywhere: per
the Phase 3 discovery report (5.6, question 3), no NSTA source
publishes a historical equity split - subareas_equity (the only source
with a real EQUITY percentage) is a current-state-only snapshot with no
historical variant. tests/test_licence_history.py enforces this with a
schema-key scan, not just a code comment.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from arcgis import (  # noqa: E402
    ArcGISError,
    fetch_item_metadata,
    fetch_layer_metadata,
    query_all,
    query_statistic,
)

LICENCE_BLOCKS_HISTORY_ITEM_ID = "855237fb38bb44b2afc52a3ea4a48903"

EXPECTED_FIELDS = {
    "HISTORY": "esriFieldTypeString",
    "BLOCKREF": "esriFieldTypeString",
    "BLCKSTRTDT": "esriFieldTypeDate",
    "BLCKENDDT": "esriFieldTypeDate",
    "LICTYPE": "esriFieldTypeString",
    "LICNO": "esriFieldTypeDouble",
    "LICREF": "esriFieldTypeString",
    "LICSTATUS": "esriFieldTypeString",
    "LICORG": "esriFieldTypeString",
    "LICORGGRP": "esriFieldTypeString",
    "OPORG": "esriFieldTypeString",
    "OPORGGRP": "esriFieldTypeString",
    "ADMORG": "esriFieldTypeString",
    "ADMORGGRP": "esriFieldTypeString",
}

OUT_FIELDS = ",".join(EXPECTED_FIELDS)
EXPECTED_GEOMETRY_TYPE = "esriGeometryPolygon"


class LicenceHistoryError(RuntimeError):
    """Raised on any build-breaking failure in the historical
    licence-interest pipeline - caught in etl/build.py alongside every
    other pipeline's own exceptions, same 'fail the whole build, write
    nothing' rule."""


def _epoch_ms_to_date(epoch_ms) -> str | None:
    if epoch_ms is None:
        return None
    return datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")


def fetch_licence_history_rows(session=None) -> dict:
    """Fetches every historical block-licensing-episode row, with
    geometry, validating schema, geometry type, and pagination/count -
    same discipline as licence_portfolio.py's fetch function."""
    try:
        item_meta = fetch_item_metadata(LICENCE_BLOCKS_HISTORY_ITEM_ID, session=session)
        service_url = item_meta.get("url")
        if not service_url:
            raise LicenceHistoryError(
                f"Item {LICENCE_BLOCKS_HISTORY_ITEM_ID} has no 'url' in its metadata response."
            )
        layer_meta = fetch_layer_metadata(service_url, layer_index=0, session=session)
    except ArcGISError as e:
        raise LicenceHistoryError(f"Could not resolve/fetch the licence-blocks-history service: {e}") from e

    live_fields = {f["name"]: f["type"] for f in layer_meta.get("fields", [])}
    problems = []
    for name, expected_type in EXPECTED_FIELDS.items():
        if name not in live_fields:
            problems.append(f"missing expected field {name!r}")
        elif live_fields[name] != expected_type:
            problems.append(
                f"field {name!r} changed type: expected {expected_type!r}, got {live_fields[name]!r}"
            )
    live_geometry_type = layer_meta.get("geometryType")
    if live_geometry_type != EXPECTED_GEOMETRY_TYPE:
        problems.append(
            f"geometry type changed: expected {EXPECTED_GEOMETRY_TYPE!r}, got {live_geometry_type!r}"
        )
    if problems:
        raise LicenceHistoryError(
            "Schema/geometry-type drift on the licence-blocks-history service: " + "; ".join(problems)
        )

    layer_url = layer_meta["_layer_url"]
    max_record_count = layer_meta.get("maxRecordCount", 1000)

    try:
        independent_count = query_statistic(layer_url, "OBJECTID", "count", session=session)
    except ArcGISError as e:
        raise LicenceHistoryError(f"Could not get an independent row count: {e}") from e

    rows = list(
        query_all(
            layer_url,
            out_fields=OUT_FIELDS,
            return_geometry=True,
            max_record_count=max_record_count,
            session=session,
        )
    )
    if len(rows) != independent_count:
        raise LicenceHistoryError(
            f"Pagination mismatch on licence-blocks-history service: fetched {len(rows)} "
            f"rows but an independent COUNT query returned {independent_count}."
        )

    return {
        "rows": rows,
        "resolved_url": service_url,
        "item_title": item_meta.get("title"),
        "record_count": len(rows),
    }


def build_history_entry(row: dict) -> dict:
    """One historical block-licensing-episode row's published detail -
    every field taken exactly as recorded. Deliberately NO equity
    percentage field anywhere (see module docstring) - only source-
    supported geometry, licence identifiers, dates, status, and
    recorded organisation names."""
    attrs = row["attributes"]
    return {
        "is_current_episode": attrs.get("HISTORY") == "N",
        "licence_number": attrs.get("LICNO"),
        "licence_reference": attrs.get("LICREF"),
        "block_reference": attrs.get("BLOCKREF"),
        "licence_status": attrs.get("LICSTATUS"),
        "start_date": _epoch_ms_to_date(attrs.get("BLCKSTRTDT")),
        "end_date": _epoch_ms_to_date(attrs.get("BLCKENDDT")),
        "licensee_names": attrs.get("LICORG"),
        "licensee_group": attrs.get("LICORGGRP"),
        "operator_names": attrs.get("OPORG"),
        "operator_group": attrs.get("OPORGGRP"),
        "admin_org": attrs.get("ADMORG"),
        "admin_group": attrs.get("ADMORGGRP"),
    }


def build_history_geojson(rows: list[dict]) -> dict:
    """One feature per historical block-licensing-episode row, WGS84
    polygon geometry plus the same detail build_history_entry()
    publishes. Every feature carries a stable `episode_id` (its source
    OBJECTID) so the frontend can uniquely address one episode without
    relying on a (possibly non-unique) combination of other fields."""
    features = []
    for row in rows:
        entry = build_history_entry(row)
        geometry = row.get("geometry") or {}
        rings = geometry.get("rings") or []
        if not rings:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon" if len(rings) == 1 else "MultiPolygon",
                    "coordinates": rings if len(rings) == 1 else [[ring] for ring in rings],
                },
                "properties": {**entry, "episode_id": row["attributes"].get("OBJECTID")},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def build_history_meta(rows: list[dict], resolved_url: str, item_title: str, record_count: int) -> dict:
    """Compact index for the frontend's date selector and filters -
    distinct operator groups/statuses and the overall date range, so
    the browser never has to scan the full 8,886-feature GeoJSON just
    to populate a <select> or a date input's min/max."""
    entries = [build_history_entry(r) for r in rows]
    start_dates = [e["start_date"] for e in entries if e["start_date"]]
    end_dates = [e["end_date"] for e in entries if e["end_date"]]
    return {
        "record_count": record_count,
        "earliest_start_date": min(start_dates) if start_dates else None,
        "latest_start_date": max(start_dates) if start_dates else None,
        "latest_end_date": max(end_dates) if end_dates else None,
        "open_ended_count": sum(1 for e in entries if e["end_date"] is None),
        "distinct_operator_groups": sorted({e["operator_group"] for e in entries if e["operator_group"]}),
        "distinct_licence_statuses": sorted({e["licence_status"] for e in entries if e["licence_status"]}),
        "source": {
            "item_title": item_title,
            "resolved_url": resolved_url,
            "publisher": "North Sea Transition Authority",
        },
    }


# ---------------------------------------------------------------------------
# Validation (all build-breaking)
# ---------------------------------------------------------------------------


def validate_no_fabricated_equity_fields(geojson: dict) -> None:
    """Build-breaking invariant: no feature property key may reference
    an equity/percentage concept anywhere in this artifact - the
    published source has no historical equity split (Phase 3 discovery
    report 5.6 question 3), so this pipeline must never invent one."""
    forbidden_substrings = ("equity", "pct", "percent", "share")
    if not geojson["features"]:
        return
    keys = geojson["features"][0]["properties"].keys()
    offenders = [k for k in keys if any(s in k.lower() for s in forbidden_substrings)]
    if offenders:
        raise LicenceHistoryError(
            "Historical licence-interest artifact must never carry an equity/percentage "
            f"field (none exists in the published source): found {offenders}"
        )


def validate_history_dates(rows: list[dict]) -> None:
    """Build-breaking invariant: every row has a valid start date, and
    where an end date is present it is never before the start date. An
    absent end date is explicitly valid (open-ended, not a defect)."""
    offenders = []
    for row in rows:
        entry = build_history_entry(row)
        if not entry["start_date"]:
            offenders.append(f"OBJECTID={row['attributes'].get('OBJECTID')}: missing start_date")
            continue
        if entry["end_date"] and entry["end_date"] < entry["start_date"]:
            offenders.append(
                f"OBJECTID={row['attributes'].get('OBJECTID')}: end_date {entry['end_date']} "
                f"before start_date {entry['start_date']}"
            )
    if offenders:
        raise LicenceHistoryError(
            "Historical licence-interest date validation failed: " + "; ".join(offenders[:20])
        )


def validate_source_names_retained(rows: list[dict]) -> None:
    """Build-breaking invariant: every row retains a non-empty
    licensee-organisation string as recorded by NSTA (even a
    legitimate 'NO OPERATOR' value for the operator field is fine -
    only a genuinely missing/blank licensee name is a defect, since
    that is the field this whole pipeline exists to preserve)."""
    offenders = [
        row["attributes"].get("OBJECTID")
        for row in rows
        if not (row["attributes"].get("LICORG") or "").strip()
    ]
    if offenders:
        raise LicenceHistoryError(
            f"Historical licence-interest rows with no recorded licensee name (LICORG): {offenders[:20]}"
        )
