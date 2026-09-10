"""
Current company licence portfolio (Workstream 4, spec approved
2026-09-10).

Uses the SAME NSTA service as company grouping (etl/company_groups.py) -
"UKCS offshore petroleum licence subareas by equity group holder
(WGS84)", item resolved at build time - but keeps a different, wider set
of fields and the geometry, since the portfolio view needs the
subarea-grain detail (licence number/reference, status, dates, equity
percentage, operator role) that the grouping module discards. This is
the preferred current-portfolio grain per discovery: licence blocks and
subareas may have different beneficiaries, so a whole-licence polygon
would conceal subarea-level ownership.

Each row already names its own current display group directly via
EQGRPHOLD - no percentage-matching disambiguation is needed here (unlike
company_groups.py, which has to recover an individual LEGAL ENTITY name
from the combined EQORG string). A row's "operated" flag is a direct,
unambiguous comparison: this row's holder group (EQGRPHOLD) against the
subarea's operator group (OPORGGRP).

No date range fabricated: LICSTARTDT/LICENDDT are published exactly as
recorded (an open LICENDDT means "still current"), and nothing here
claims an equity percentage exists where the source has none.
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
from transform import slugify  # noqa: E402

LICENCE_SUBAREAS_ITEM_ID = "40c65d96a1a14da8b066f2abbb345fed"

EXPECTED_FIELDS = {
    "SUBAREANAM": "esriFieldTypeString",
    "BLOCKREF": "esriFieldTypeString",
    "LICNO": "esriFieldTypeInteger",
    "LICREF": "esriFieldTypeString",
    "LICSTATUS": "esriFieldTypeString",
    "LICSTARTDT": "esriFieldTypeDate",
    "LICENDDT": "esriFieldTypeDate",
    "EQGRPHOLD": "esriFieldTypeString",
    "EQUITY": "esriFieldTypeDouble",
    "OPORGGRP": "esriFieldTypeString",
}

OUT_FIELDS = ",".join(EXPECTED_FIELDS)
EXPECTED_GEOMETRY_TYPE = "esriGeometryPolygon"


class LicencePortfolioError(RuntimeError):
    """Raised on any build-breaking failure in the licence-portfolio
    pipeline - caught in etl/build.py alongside every other pipeline's
    own exceptions, same 'fail the whole build, write nothing' rule."""


def _epoch_ms_to_date(epoch_ms) -> str | None:
    if epoch_ms is None:
        return None
    return datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")


def fetch_licence_subarea_rows(session) -> dict:
    """Fetches every current licence-subarea-by-holder row, with
    geometry, validating schema, geometry type, and pagination/count."""
    try:
        item_meta = fetch_item_metadata(LICENCE_SUBAREAS_ITEM_ID, session=session)
        service_url = item_meta.get("url")
        if not service_url:
            raise LicencePortfolioError(
                f"Item {LICENCE_SUBAREAS_ITEM_ID} has no 'url' in its metadata response."
            )
        layer_meta = fetch_layer_metadata(service_url, layer_index=0, session=session)
    except ArcGISError as e:
        raise LicencePortfolioError(f"Could not resolve/fetch the licence-subareas service: {e}") from e

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
        raise LicencePortfolioError(
            "Schema/geometry-type drift on the licence-subareas service: " + "; ".join(problems)
        )

    layer_url = layer_meta["_layer_url"]
    max_record_count = layer_meta.get("maxRecordCount", 1000)

    try:
        independent_count = query_statistic(layer_url, "OBJECTID", "count", session=session)
    except ArcGISError as e:
        raise LicencePortfolioError(f"Could not get an independent row count: {e}") from e

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
        raise LicencePortfolioError(
            f"Pagination mismatch on licence-subareas service: fetched {len(rows)} "
            f"rows but an independent COUNT query returned {independent_count}."
        )

    return {
        "rows": rows,
        "resolved_url": service_url,
        "item_title": item_meta.get("title"),
        "record_count": len(rows),
    }


def build_portfolio_entry(row: dict) -> dict:
    """One subarea-holder row's published detail - every field taken
    exactly as recorded, no percentage or date fabricated where the
    source has none."""
    attrs = row["attributes"]
    holder_group = attrs.get("EQGRPHOLD")
    operator_group = attrs.get("OPORGGRP")
    return {
        "licence_number": attrs.get("LICNO"),
        "licence_reference": attrs.get("LICREF"),
        "block_reference": attrs.get("BLOCKREF"),
        "subarea_name": attrs.get("SUBAREANAM"),
        "licence_status": attrs.get("LICSTATUS"),
        "licence_start_date": _epoch_ms_to_date(attrs.get("LICSTARTDT")),
        "licence_end_date": _epoch_ms_to_date(attrs.get("LICENDDT")),
        "equity_pct": attrs.get("EQUITY"),
        "current_display_group": holder_group,
        "operator_group": operator_group,
        "operated": bool(holder_group) and holder_group == operator_group,
    }


def build_portfolio_by_group(rows: list[dict]) -> dict[str, dict]:
    """{group_name: {slug, subareas: [...], distinct_licence_count,
    distinct_subarea_count, operated_count, non_operated_count}} -
    grouped directly by each row's own EQGRPHOLD (spec: "current display
    group"), no ambiguity to resolve since this dataset names the holder
    group per row explicitly. Rows with no EQGRPHOLD (a genuinely blank
    holder) are collected under an explicit 'Unmapped' bucket rather
    than silently dropped."""
    by_group: dict[str, list[dict]] = {}
    for row in rows:
        entry = build_portfolio_entry(row)
        group = entry["current_display_group"] or "Unmapped"
        by_group.setdefault(group, []).append(entry)

    result = {}
    for group, entries in by_group.items():
        distinct_licences = {e["licence_reference"] for e in entries if e["licence_reference"]}
        distinct_subareas = {
            (e["licence_reference"], e["block_reference"], e["subarea_name"]) for e in entries
        }
        result[group] = {
            "slug": slugify(group),
            "name": group,
            "subareas": sorted(
                entries, key=lambda e: (e["licence_reference"] or "", e["block_reference"] or "")
            ),
            "distinct_licence_count": len(distinct_licences),
            "distinct_subarea_count": len(distinct_subareas),
            "operated_count": sum(1 for e in entries if e["operated"]),
            "non_operated_count": sum(1 for e in entries if not e["operated"]),
        }
    return result


def build_portfolio_geojson(rows: list[dict]) -> dict:
    """One feature per subarea-holder row, WGS84 polygon geometry plus
    the same detail build_portfolio_entry() publishes per group -
    lets the frontend draw the current portfolio directly on the map."""
    features = []
    for row in rows:
        entry = build_portfolio_entry(row)
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
                "properties": {**entry, "group_slug": slugify(entry["current_display_group"] or "Unmapped")},
            }
        )
    return {"type": "FeatureCollection", "features": features}
