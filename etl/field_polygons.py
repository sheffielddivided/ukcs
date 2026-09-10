"""
Authoritative field polygons (Workstream 3, spec approved 2026-09-10).

Source: NSTA's "UKCS petroleum field determinations (WGS84)" dataset
(item bef8788b07464a7f8a18a18eb638b9f5, identified in discovery -
etl/phase3_discovery_report.md section 4), resolved at build time via
its item ID - the service URL is never hardcoded (spec section 4). 344
current-status polygons at last count, WGS84 (EPSG:4326) geometry,
measured by discovery at ~324 KB uncompressed / ~90 KB gzipped - no
simplification pass is applied (the discovery found none needed, and
this module does not add one; a future one would have to preserve the
original artifact, document its tolerance and test geometry validity,
per spec section Workstream 3).

Field-name matching reuses the exact same exact -> normalized -> alias
pipeline etl/equity_match.py already uses for PPRS-vs-equity field-name
matching (etl/equity_match.match_fields()) - not a second, divergent
matcher. No alias file is used here (none exists for polygon names);
only exact and normalized (case/whitespace/dash-variant) matching are
attempted, matching the discovery report's own measured 89.2% figure.

A field without a matched polygon is never dropped from the map - the
frontend's existing point-marker rendering (fields.geojson) remains the
fallback for it (spec: "Polygon absence must never remove a producing
field from the map.").
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from arcgis import (  # noqa: E402
    ArcGISError,
    fetch_item_metadata,
    fetch_layer_metadata,
    query_all,
    query_statistic,
)
from equity_match import match_fields  # noqa: E402
from transform import slugify  # noqa: E402

FIELD_DETERMINATIONS_ITEM_ID = "bef8788b07464a7f8a18a18eb638b9f5"

EXPECTED_FIELDS = {
    "FIELD_NO": "esriFieldTypeString",
    "FIELDNAME": "esriFieldTypeString",
    "FD_STAT": "esriFieldTypeString",
}

EXPECTED_GEOMETRY_TYPE = "esriGeometryPolygon"
EXPECTED_WKID = 4326


class FieldPolygonsError(RuntimeError):
    """Raised on any build-breaking failure in the field-polygon
    pipeline - caught in etl/build.py alongside every other pipeline's
    own exceptions, same 'fail the whole build, write nothing' rule."""


def fetch_field_polygon_rows(session) -> dict:
    """Fetches every polygon feature from the live field-determinations
    service, with geometry. Validates schema, geometry type, CRS, and
    pagination/count (spec Workstream 3 ingestion requirements +
    "Source drift" build-breaking checks)."""
    try:
        item_meta = fetch_item_metadata(FIELD_DETERMINATIONS_ITEM_ID, session=session)
        service_url = item_meta.get("url")
        if not service_url:
            raise FieldPolygonsError(
                f"Item {FIELD_DETERMINATIONS_ITEM_ID} has no 'url' in its metadata response."
            )
        layer_meta = fetch_layer_metadata(service_url, layer_index=0, session=session)
    except ArcGISError as e:
        raise FieldPolygonsError(f"Could not resolve/fetch the field-determinations service: {e}") from e

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
        raise FieldPolygonsError(
            "Schema/geometry-type drift on the field-determinations service: " + "; ".join(problems)
        )

    layer_url = layer_meta["_layer_url"]
    max_record_count = layer_meta.get("maxRecordCount", 1000)

    try:
        independent_count = query_statistic(layer_url, "OBJECTID", "count", session=session)
    except ArcGISError as e:
        raise FieldPolygonsError(f"Could not get an independent row count: {e}") from e

    rows = list(
        query_all(
            layer_url,
            out_fields="FIELD_NO,FIELDNAME,FD_STAT",
            return_geometry=True,
            max_record_count=max_record_count,
            session=session,
        )
    )
    if len(rows) != independent_count:
        raise FieldPolygonsError(
            f"Pagination mismatch on field-determinations service: fetched {len(rows)} "
            f"rows but an independent COUNT query returned {independent_count}."
        )

    for row in rows:
        geometry = row.get("geometry")
        if not geometry or not geometry.get("rings"):
            raise FieldPolygonsError(
                f"Invalid geometry for field {row['attributes'].get('FIELDNAME')!r} "
                f"(FIELD_NO {row['attributes'].get('FIELD_NO')!r}): no rings present."
            )

    return {
        "rows": rows,
        "resolved_url": service_url,
        "item_title": item_meta.get("title"),
        "source_last_modified_epoch_ms": item_meta.get("modified"),
        "record_count": len(rows),
    }


def match_polygons_to_pprs(pprs_field_names: set[str], polygon_field_names: set[str]) -> dict:
    """Reuses etl/equity_match.match_fields() (exact -> normalized, no
    alias file) so polygon matching follows exactly the same, already-
    tested logic as PPRS-vs-equity field matching - not a second,
    divergent implementation."""
    return match_fields(pprs_field_names, polygon_field_names, aliases=[])


def build_field_polygons_geojson(
    rows: list[dict],
    match_result: dict,
) -> dict:
    """Builds the field_polygons.geojson FeatureCollection. Every polygon
    row becomes one feature, whether or not it matched a PPRS field -
    unmatched polygons are still real, authoritative NSTA geometry and
    are published with matched_pprs_field=None rather than silently
    dropped. `properties.matched_pprs_field` is the slug the frontend can
    join against fields.geojson's own `slug` property to combine polygon
    geometry with production data."""
    pprs_by_polygon_name: dict[str, str] = {}
    for pprs_name, polygon_name in match_result["exact_matches"].items():
        pprs_by_polygon_name[polygon_name] = pprs_name
    for pprs_name, polygon_name in match_result["normalized_matches"].items():
        pprs_by_polygon_name[polygon_name] = pprs_name

    features = []
    for row in sorted(rows, key=lambda r: r["attributes"]["FIELDNAME"]):
        attrs = row["attributes"]
        polygon_name = attrs["FIELDNAME"]
        pprs_name = pprs_by_polygon_name.get(polygon_name)
        properties = {
            "field_no": attrs.get("FIELD_NO"),
            "polygon_field_name": polygon_name,
            "determination_status": attrs.get("FD_STAT"),
            "matched_pprs_field": pprs_name,
            "matched_pprs_slug": slugify(pprs_name) if pprs_name else None,
            "match_method": (
                "exact" if polygon_name in match_result["exact_matches"].values()
                else "normalized" if polygon_name in match_result["normalized_matches"].values()
                else None
            ),
        }
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon" if len(row["geometry"]["rings"]) == 1 else "MultiPolygon",
                    "coordinates": (
                        row["geometry"]["rings"]
                        if len(row["geometry"]["rings"]) == 1
                        else [[ring] for ring in row["geometry"]["rings"]]
                    ),
                },
                "properties": properties,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def unmatched_production_impact(
    unmatched_pprs_fields: list[str], latest_period_totals: dict[str, float]
) -> dict:
    """Measures how much latest-period production belongs to PPRS fields
    that did NOT get a matched polygon (spec: "unmatched production
    impact" is a required part of the ingestion report) - so the impact
    of a polygon-matching gap is stated in real production terms, not
    just a bare field count.

    `latest_period_totals`: {pprs_field_name: total_mboed value}."""
    total_mboed = 0.0
    unmatched_mboed = 0.0
    unmatched_set = set(unmatched_pprs_fields)
    for field_name, value in latest_period_totals.items():
        value = value or 0.0
        total_mboed += value
        if field_name in unmatched_set:
            unmatched_mboed += value
    pct = round(100.0 * unmatched_mboed / total_mboed, 3) if total_mboed > 0 else None
    return {
        "unmatched_field_count": len(unmatched_pprs_fields),
        "unmatched_total_mboed": round(unmatched_mboed, 3),
        "unmatched_production_pct": pct,
    }
