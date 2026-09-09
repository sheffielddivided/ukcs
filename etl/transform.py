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


@dataclass
class FieldHistory:
    slug: str
    field: str
    region: str | None
    location: str | None
    operator: str | None
    series: list[dict] = dataclass_field(default_factory=list)
    production_units: list[dict] = dataclass_field(default_factory=list)
    storage_units: list[dict] = dataclass_field(default_factory=list)


def aggregate_history(
    rows: list[dict], classification_map: dict[tuple[str, str], str]
) -> tuple[list[FieldHistory], dict]:
    """Aggregate the full PPRS attribute history to (field, period) grain
    (spec section 9.3 / 13 step 5).

    Grain and exclusion rules are identical to aggregate_latest_period
    (section 7.4/7.3), just applied across every observed period instead
    of one: storage-classified units are excluded from every period's
    totals, never only the latest one - Rough's history must not contain
    ROUGH STORAGE's redelivery volumes in any period, not just not the
    latest.

    A period is included in a field's series only if that field had at
    least one PRODUCTION row in that period. A field with no production
    period at all (storage-only, at every point in its history) is
    dropped entirely, same as in the latest-period aggregate, and counted
    in stats rather than silently omitted.

    The rename cases identified in spec section 7.2 (SEAN -> NORTH SEAN,
    COLUMBA B -> COLUMBA BD) require no special handling here: NSTA
    already carries both old and new unit names under one FIELDNAME, and
    because their periods never overlap, summing every production unit
    for a given (FIELDNAME, period) naturally yields one continuous
    series with no double-counting - this is the same mechanism that
    handles ROUGH's concurrent production+storage split, just with
    non-overlapping unit lifetimes instead of concurrent ones. The
    rename itself is still surfaced explicitly: `production_units`
    lists every historical unit name with its first/last period, so a
    reader can see the handover from the unit list even though the
    series itself is unbroken.

    Returns (field_histories, stats) where stats has:
      raw_field_count, field_with_history_count, storage_only_field_count,
      production_row_count, storage_row_count, period_count (total
      field-period series entries written)
    """
    by_field: dict[str, list[dict]] = {}
    for row in rows:
        attrs = row["attributes"]
        by_field.setdefault(attrs["FIELDNAME"], []).append(row)

    raw_field_count = len(by_field)
    production_row_count = 0
    storage_row_count = 0
    storage_only_fields: list[str] = []
    period_count = 0
    histories: list[FieldHistory] = []

    for field_name in sorted(by_field.keys()):
        field_rows = by_field[field_name]
        production_rows = []
        storage_rows = []
        for row in field_rows:
            attrs = row["attributes"]
            unit_class = classify(field_name, attrs["UNITNAME"], classification_map)
            if unit_class == "storage":
                storage_rows.append(row)
            else:
                production_rows.append(row)

        production_row_count += len(production_rows)
        storage_row_count += len(storage_rows)

        if not production_rows:
            storage_only_fields.append(field_name)
            continue

        by_period: dict[str, list[dict]] = {}
        for row in production_rows:
            by_period.setdefault(row["attributes"]["PERIODYRMN"], []).append(row)

        series = []
        for period in sorted(by_period.keys()):
            period_rows = by_period[period]
            totals = {out_key: 0.0 for out_key in VALUE_FIELD_MAP.values()}
            for row in period_rows:
                attrs = row["attributes"]
                for src_key, out_key in VALUE_FIELD_MAP.items():
                    value = attrs.get(src_key)
                    if value is not None:
                        totals[out_key] += value
            series.append(
                {
                    "period": period,
                    **{key: round3(val) for key, val in totals.items()},
                }
            )
        period_count += len(series)

        # "Current" region/location/operator per section 6.1's convention:
        # taken from the most recent production period on record, not an
        # arbitrary historical one.
        latest_period_rows = by_period[max(by_period.keys())]
        latest_attrs = latest_period_rows[0]["attributes"]

        production_unit_periods: dict[str, dict] = {}
        for row in production_rows:
            attrs = row["attributes"]
            name = attrs["UNITNAME"]
            entry = production_unit_periods.setdefault(
                name, {"name": name, "type": attrs.get("UNITTYPDES"),
                       "first_period": attrs["PERIODYRMN"], "last_period": attrs["PERIODYRMN"]}
            )
            entry["first_period"] = min(entry["first_period"], attrs["PERIODYRMN"])
            entry["last_period"] = max(entry["last_period"], attrs["PERIODYRMN"])

        storage_unit_periods: dict[str, dict] = {}
        for row in storage_rows:
            attrs = row["attributes"]
            name = attrs["UNITNAME"]
            entry = storage_unit_periods.setdefault(
                name, {"name": name, "type": attrs.get("UNITTYPDES"),
                       "first_period": attrs["PERIODYRMN"], "last_period": attrs["PERIODYRMN"]}
            )
            entry["first_period"] = min(entry["first_period"], attrs["PERIODYRMN"])
            entry["last_period"] = max(entry["last_period"], attrs["PERIODYRMN"])

        histories.append(
            FieldHistory(
                slug=slugify(field_name),
                field=field_name,
                region=latest_attrs.get("FIELDAREA"),
                location=latest_attrs.get("LOCATION"),
                operator=latest_attrs.get("ORGGRPNM"),
                series=series,
                production_units=sorted(
                    production_unit_periods.values(), key=lambda u: u["first_period"]
                ),
                storage_units=sorted(
                    storage_unit_periods.values(), key=lambda u: u["first_period"]
                ),
            )
        )

    stats = {
        "raw_field_count": raw_field_count,
        "field_with_history_count": len(histories),
        "storage_only_field_count": len(storage_only_fields),
        "storage_only_fields": sorted(storage_only_fields),
        "production_row_count": production_row_count,
        "storage_row_count": storage_row_count,
        "period_count": period_count,
    }
    return histories, stats


def build_history_artifacts(histories: list[FieldHistory]) -> tuple[dict, dict]:
    """Build history/{slug}.json contents (one per field) and the
    history/index.json summary (spec 9.3). Returns
    (per_slug_documents, index_document)."""
    per_slug = {}
    index = {}
    for h in sorted(histories, key=lambda h: h.slug):
        per_slug[h.slug] = {
            "slug": h.slug,
            "field": h.field,
            "operator": h.operator,
            "region": h.region,
            "location": h.location,
            "units": h.production_units,
            "storage_units": h.storage_units,
            "series": h.series,
        }
        index[h.slug] = {
            "field": h.field,
            "operator": h.operator,
            "region": h.region,
            "first_period": h.series[0]["period"],
            "last_period": h.series[-1]["period"],
        }
    return per_slug, index


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


GENERATED_FROM_OPERATOR = "current operator of record"


@dataclass
class OperatorHistory:
    slug: str
    name: str
    field_slugs: list[str] = dataclass_field(default_factory=list)
    series: list[dict] = dataclass_field(default_factory=list)


def aggregate_operators(histories: list[FieldHistory]) -> tuple[list[OperatorHistory], dict]:
    """Aggregate field histories to operator grain (spec section 9.4 / 13
    step 7).

    Every field's ENTIRE history is attributed to whichever operator most
    recently held it (FieldHistory.operator, itself already the "current
    operator of record" per section 6.1's retrospective convention) - a
    2008 barrel is counted under today's operator, not whoever operated
    the field in 2008. This is explicitly a stepping stone/consistency
    check (spec section 1), not the intended end product; Phase 2 replaces
    it with dated equity intervals.

    Storage exclusion is inherited for free: `histories` here is the same
    FieldHistory list aggregate_history() already built with storage units
    excluded from every series point, so no separate handling is needed.

    A field is never split across operators - one field has exactly one
    "current operator of record", so summing per (operator, period) is a
    straight sum over whichever fields currently belong to that operator,
    with no risk of double-counting a field under two operators.

    Returns (operator_histories, stats) where stats has:
      operator_count, field_count (== len(histories), for cross-checking).
    """
    by_operator: dict[str, list[FieldHistory]] = {}
    for h in histories:
        if not h.operator:
            raise ValueError(
                f"Field {h.field!r} (slug {h.slug!r}) has no operator on "
                "record - cannot attribute it to an operator grain."
            )
        by_operator.setdefault(h.operator, []).append(h)

    operator_histories: list[OperatorHistory] = []
    for operator_name in sorted(by_operator.keys()):
        field_histories = by_operator[operator_name]
        by_period: dict[str, dict] = {}
        for fh in field_histories:
            for point in fh.series:
                period = point["period"]
                totals = by_period.setdefault(
                    period, {out_key: 0.0 for out_key in VALUE_FIELD_MAP.values()}
                )
                for out_key in VALUE_FIELD_MAP.values():
                    value = point.get(out_key)
                    if value is not None:
                        totals[out_key] += value

        series = [
            {"period": period, **{k: round3(v) for k, v in by_period[period].items()}}
            for period in sorted(by_period.keys())
        ]

        operator_histories.append(
            OperatorHistory(
                slug=slugify(operator_name),
                name=operator_name,
                field_slugs=sorted(fh.slug for fh in field_histories),
                series=series,
            )
        )

    stats = {
        "operator_count": len(operator_histories),
        "field_count": len(histories),
    }
    return operator_histories, stats


def build_operators_artifacts(
    operator_histories: list[OperatorHistory],
) -> tuple[dict, dict]:
    """Build the operators.json index document (latest values only) and
    the full per-operator series documents (spec 9.4). Returns
    (index_document, per_slug_documents). Caller decides whether the
    per-slug documents are actually written to separate files (>2MB
    threshold, spec 9.4) or embedded back into operators.json."""
    index: dict = {}
    per_slug: dict = {}
    for oh in sorted(operator_histories, key=lambda o: o.slug):
        latest = oh.series[-1] if oh.series else None
        index[oh.slug] = {
            "name": oh.name,
            "field_count": len(oh.field_slugs),
            "first_period": oh.series[0]["period"] if oh.series else None,
            "last_period": latest["period"] if latest else None,
            "latest": latest,
        }
        per_slug[oh.slug] = {
            "slug": oh.slug,
            "name": oh.name,
            "generated_from": GENERATED_FROM_OPERATOR,
            "fields": oh.field_slugs,
            "series": oh.series,
        }
    return index, per_slug
