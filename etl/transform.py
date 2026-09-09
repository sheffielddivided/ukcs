"""
Transform PPRS records into field-grain artifacts (spec section 7.4 / 9 / 13
step 3).

Pure functions only - no network calls, no filesystem writes except the CSV
loader. build.py is responsible for I/O and for running validation before
anything from here is persisted.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path

# Value fields carried through from PPRS to the field-grain aggregate,
# mapped to their output key names (spec section 9.2/9.3). Kept in one
# place so fields.geojson and history/*.json (added in a later step) stay
# consistent.
VALUE_FIELD_MAP = {
    "OILPRODMBD": "oil_mbd",
    "AGASPROMMS": "assoc_gas_mmscfd",
    "DGASPROMMS": "dry_gas_mmscfd",
    "GCONDMBD": "condensate_mbd",
    "WATPRODMBD": "water_mbd",
}

ROUND_DECIMALS = 3


def round3(value: float | None) -> float | None:
    """Round to the fixed precision required for deterministic artifacts
    (spec: 'fixed float rounding'). Collapses -0.0 to 0.0 so repeated
    builds of the same input never toggle a value's sign representation in
    the committed JSON."""
    if value is None:
        return None
    rounded = round(float(value), ROUND_DECIMALS)
    if rounded == 0:
        rounded = 0.0
    return rounded


def slugify(name: str) -> str:
    """Deterministic slug: lowercase, non-alphanumeric runs collapsed to a
    single hyphen, no leading/trailing hyphen. No fuzzy normalisation -
    this is an identifier, not a matching key (that's section 15.5's job)."""
    lowered = name.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    if not slug:
        raise ValueError(f"Name {name!r} produced an empty slug.")
    return slug


def load_unit_classification(path: Path) -> dict[tuple[str, str], str]:
    """Load etl/mappings/unit_classification.csv (spec section 7.3).
    Only exceptions are listed in the file; anything absent defaults to
    'production' at the call site, not here - this function returns
    exactly what's in the file, nothing implied."""
    classification: dict[tuple[str, str], str] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        expected_columns = {"field_name", "unit_name", "classification", "note"}
        if reader.fieldnames is None or not expected_columns.issubset(reader.fieldnames):
            raise ValueError(
                f"{path} is missing expected columns {sorted(expected_columns)}; "
                f"found {reader.fieldnames}"
            )
        for row in reader:
            key = (row["field_name"], row["unit_name"])
            value = row["classification"].strip()
            if value not in ("production", "storage"):
                raise ValueError(
                    f"{path}: row {key} has invalid classification "
                    f"{value!r}, expected 'production' or 'storage'"
                )
            classification[key] = value
    return classification


def classify(
    field_name: str, unit_name: str, classification_map: dict[tuple[str, str], str]
) -> str:
    """Default is 'production' - only listed exceptions are 'storage'
    (spec section 7.3: exceptions-only, so a routine new unit never turns
    the build red)."""
    return classification_map.get((field_name, unit_name), "production")


@dataclass
class FieldRecord:
    slug: str
    field: str
    region: str | None
    location: str | None
    operator: str | None
    period: str
    lon: float
    lat: float
    production_units: list[dict] = dataclass_field(default_factory=list)
    storage_units: list[dict] = dataclass_field(default_factory=list)
    totals: dict = dataclass_field(default_factory=dict)


def aggregate_latest_period(
    rows: list[dict], classification_map: dict[tuple[str, str], str]
) -> tuple[list[FieldRecord], dict]:
    """Aggregate raw PPRS features (attributes + geometry) for a single
    period to field grain.

    Storage-classified reporting units (spec 7.3) are excluded from both
    the production totals AND the centroid geometry - a storage unit must
    never pull a field's marker or inflate its production (spec: 'Rough's
    storage unit must not pull the marker').

    A field whose only unit(s) are all storage is dropped entirely from
    the returned records (there is no production to plot) and counted
    separately in the returned stats dict, so the difference between raw
    and production field counts is visible rather than looking like data
    loss.

    Returns (field_records, stats) where stats has:
      raw_field_count, production_field_count, storage_only_field_count,
      production_unit_count, storage_unit_count
    """
    by_field: dict[str, list[dict]] = {}
    for row in rows:
        attrs = row["attributes"]
        by_field.setdefault(attrs["FIELDNAME"], []).append(row)

    raw_field_count = len(by_field)
    production_unit_count = 0
    storage_unit_count = 0
    storage_only_fields: list[str] = []
    records: list[FieldRecord] = []

    for field_name in sorted(by_field.keys()):
        field_rows = by_field[field_name]
        production_rows = []
        storage_rows = []
        for row in field_rows:
            attrs = row["attributes"]
            unit_name = attrs["UNITNAME"]
            unit_class = classify(field_name, unit_name, classification_map)
            if unit_class == "storage":
                storage_rows.append(row)
            else:
                production_rows.append(row)

        production_unit_count += len(production_rows)
        storage_unit_count += len(storage_rows)

        if not production_rows:
            storage_only_fields.append(field_name)
            continue

        # Sort rows deterministically for reproducible output (unit name).
        production_rows.sort(key=lambda r: r["attributes"]["UNITNAME"])
        storage_rows.sort(key=lambda r: r["attributes"]["UNITNAME"])

        totals = {out_key: 0.0 for out_key in VALUE_FIELD_MAP.values()}
        lons, lats = [], []
        period = production_rows[0]["attributes"]["PERIODYRMN"]

        for row in production_rows:
            attrs = row["attributes"]
            for src_key, out_key in VALUE_FIELD_MAP.items():
                value = attrs.get(src_key)
                if value is not None:
                    totals[out_key] += value
            geom = row.get("geometry")
            if geom is not None and geom.get("x") is not None and geom.get("y") is not None:
                lons.append(geom["x"])
                lats.append(geom["y"])

        if not lons:
            raise ValueError(
                f"Field {field_name!r} has no production-unit geometry to "
                "compute a centroid from."
            )
        centroid_lon = sum(lons) / len(lons)
        centroid_lat = sum(lats) / len(lats)

        # Region/location/operator: expected constant across a field's
        # production units within one period. Take the first
        # (deterministic, since production_rows is sorted) and record a
        # note if they actually disagree, rather than silently picking one
        # and hiding a real data inconsistency.
        first_attrs = production_rows[0]["attributes"]
        region_values = {r["attributes"].get("FIELDAREA") for r in production_rows}
        location_values = {r["attributes"].get("LOCATION") for r in production_rows}
        operator_values = {r["attributes"].get("ORGGRPNM") for r in production_rows}

        record = FieldRecord(
            slug=slugify(field_name),
            field=field_name,
            region=first_attrs.get("FIELDAREA"),
            location=first_attrs.get("LOCATION"),
            operator=first_attrs.get("ORGGRPNM"),
            period=period,
            lon=centroid_lon,
            lat=centroid_lat,
            production_units=[
                {
                    "name": r["attributes"]["UNITNAME"],
                    "type": r["attributes"].get("UNITTYPDES"),
                }
                for r in production_rows
            ],
            storage_units=[
                {
                    "name": r["attributes"]["UNITNAME"],
                    "type": r["attributes"].get("UNITTYPDES"),
                }
                for r in storage_rows
            ],
            totals=totals,
        )
        if len(region_values) > 1:
            record.totals.setdefault("_notes", []).append(
                f"inconsistent FIELDAREA across production units: {sorted(region_values)}"
            )
        if len(location_values) > 1:
            record.totals.setdefault("_notes", []).append(
                f"inconsistent LOCATION across production units: {sorted(location_values)}"
            )
        if len(operator_values) > 1:
            record.totals.setdefault("_notes", []).append(
                f"inconsistent ORGGRPNM across production units: {sorted(operator_values)}"
            )

        records.append(record)

    stats = {
        "raw_field_count": raw_field_count,
        "production_field_count": len(records),
        "storage_only_field_count": len(storage_only_fields),
        "storage_only_fields": sorted(storage_only_fields),
        "production_unit_count": production_unit_count,
        "storage_unit_count": storage_unit_count,
    }
    return records, stats


def build_fields_geojson(records: list[FieldRecord]) -> dict:
    """Build the fields.geojson FeatureCollection (spec 9.2). Features are
    sorted by slug for deterministic output."""
    features = []
    for record in sorted(records, key=lambda r: r.slug):
        properties = {
            "slug": record.slug,
            "field": record.field,
            "region": record.region,
            "location": record.location,
            "operator": record.operator,
            "unit_count": len(record.production_units),
            "storage_unit_count": len(record.storage_units),
            "period": record.period,
            "oil_mbd": round3(record.totals.get("oil_mbd")),
            "assoc_gas_mmscfd": round3(record.totals.get("assoc_gas_mmscfd")),
            "dry_gas_mmscfd": round3(record.totals.get("dry_gas_mmscfd")),
            "condensate_mbd": round3(record.totals.get("condensate_mbd")),
            "water_mbd": round3(record.totals.get("water_mbd")),
        }
        notes = record.totals.get("_notes")
        if notes:
            properties["notes"] = notes

        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [round3(record.lon), round3(record.lat)],
                },
                "properties": properties,
            }
        )
    return {"type": "FeatureCollection", "features": features}
