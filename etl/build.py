"""
ETL entry point (spec section 8 / 13 step 3).

This step: resolve the PPRS points service, validate its schema, fetch the
latest period (with geometry), classify reporting units, aggregate to field
grain, validate, and write meta.json + fields.geojson. Full history
(history/*.json, operators.json) is a later step per the section 13 build
order.

Usage: python etl/build.py
Exit code is non-zero on any validation failure; on failure, docs/data/ is
left untouched (spec 8.3: "Do not write partial artifacts").
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# Allow `python etl/build.py` (script invocation, sys.path[0] == etl/) and
# `python -m etl.build` / imports from tests (package invocation) to both
# resolve these sibling modules.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arcgis import (  # noqa: E402
    ArcGISError,
    fetch_layer_metadata,
    query_all,
    query_statistic,
    quote_where_value,
    resolve_service_url,
)
from transform import (  # noqa: E402
    aggregate_latest_period,
    build_fields_geojson,
    load_unit_classification,
)
from validate import (  # noqa: E402
    ValidationError,
    check_against_previous_build,
    validate_bounding_box,
    validate_no_negative_values,
    validate_schema,
    validate_unit_classification_tripwire,
)

ITEM_ID_POINTS = "dd38204275a04618ab7ddd00f87224e3"
DATASET_NAME = "UKCS hydrocarbon field production reports PPRS points (WGS84)"
PUBLISHER = "North Sea Transition Authority"

# Standing provenance note (spec section 9.1, added v2.2): the summed
# latest-period totals have not been checked against any NSTA-published
# monthly aggregate figure. A web search at build-review time (September
# 2026) found no such monthly figure to reconcile against - only annual/
# multi-year trend figures (~1.09 million boe/d for 2024, projected ~1.0
# million boe/d for 2025). This must be recorded in every build's
# meta.json, not just reported once in a chat, so nobody downstream
# mistakes silence for confirmation. Update this constant (and cite the
# source) if a genuine per-period reconciliation source is added later.
NSTA_RECONCILIATION_NOTE = (
    "Latest-period oil and gas totals have NOT been reconciled against an "
    "NSTA-published monthly aggregate production figure. No such "
    "per-period figure was locatable at build-review time; only annual/ "
    "multi-year trend figures are published. Treat these totals as "
    "internally consistent (paginated, validated, deterministic) but not "
    "independently verified against an NSTA total."
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DATA_DIR = REPO_ROOT / "docs" / "data"
UNIT_CLASSIFICATION_PATH = REPO_ROOT / "etl" / "mappings" / "unit_classification.csv"

OUT_FIELDS = (
    "OBJECTID,FIELDNAME,FIELDAREA,LOCATION,ORGGRPNM,UNITNAME,UNITTYPDES,"
    "PERIODYRMN,OILPRODMBD,AGASPROMMS,DGASPROMMS,GCONDMBD,GASPIPVOLM,WATPRODMBD"
)


class BuildError(RuntimeError):
    """Top-level build failure. Caught in main() to guarantee no partial
    artifacts are written and a clean non-zero exit."""


def compute_schema_hash(fields: list[dict]) -> str:
    """Hash of the sorted (name, type) field list (spec 9.1). Changing this
    on a future run is how schema drift beyond section 6's expected fields
    is detected."""
    pairs = sorted((f["name"], f["type"]) for f in fields)
    payload = json.dumps(pairs, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_previous_meta() -> dict | None:
    path = DOCS_DATA_DIR / "meta.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise BuildError(
            f"docs/data/meta.json exists but could not be read: {e!r}. "
            "Per spec section 8.3 this is a hard failure, not a "
            "first-run case (the file exists but is unreadable)."
        ) from e


def write_json_atomic(path: Path, data: object) -> None:
    """Serialise with sorted keys and fixed separators so a rebuild of
    unchanged input produces a byte-identical file (spec: 'deterministic
    output'), and write via a temp file + atomic rename so a crash
    mid-write can never leave a partial artifact in place (spec 8.3 /
    'atomic writes')."""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    tmp_path.write_text(text + "\n", encoding="utf-8")
    tmp_path.replace(path)


def main() -> int:
    session = requests.Session()
    notes: list[str] = [NSTA_RECONCILIATION_NOTE]

    try:
        service_url = resolve_service_url(ITEM_ID_POINTS, session=session)
        layer_meta = fetch_layer_metadata(service_url, session=session)
        layer_url = layer_meta["_layer_url"]
        max_record_count = layer_meta["maxRecordCount"]

        validate_schema(layer_meta["fields"])
        schema_hash = compute_schema_hash(layer_meta["fields"])

        period_field_type = next(
            f["type"] for f in layer_meta["fields"] if f["name"] == "PERIODYRMN"
        )

        latest_period = query_statistic(layer_url, "PERIODYRMN", "max", session=session)
        earliest_period = query_statistic(layer_url, "PERIODYRMN", "min", session=session)
        print(f"latest_period={latest_period!r} earliest_period={earliest_period!r}")

        where_latest = f"PERIODYRMN={quote_where_value(period_field_type, latest_period)}"

        independent_count = query_statistic(
            layer_url, "OBJECTID", "count", where=where_latest, session=session
        )

        rows = list(
            query_all(
                layer_url,
                where=where_latest,
                out_fields=OUT_FIELDS,
                return_geometry=True,
                max_record_count=max_record_count,
                session=session,
            )
        )
        print(f"Fetched {len(rows)} latest-period rows (independent count: {independent_count})")

        if len(rows) != independent_count:
            raise BuildError(
                f"Pagination mismatch: fetched {len(rows)} rows via "
                f"query_all but an independent outStatistics COUNT query "
                f"returned {independent_count} for the same where clause. "
                "This indicates a pagination bug and must not proceed."
            )

        validate_no_negative_values(rows)

        classification_map = load_unit_classification(UNIT_CLASSIFICATION_PATH)
        validate_unit_classification_tripwire(rows, classification_map)

        records, agg_stats = aggregate_latest_period(rows, classification_map)
        print(f"Aggregation stats: {agg_stats}")

        if agg_stats["storage_only_field_count"]:
            notes.append(
                f"{agg_stats['storage_only_field_count']} field(s) had only "
                "storage reporting units in the latest period and were "
                f"excluded entirely: {agg_stats['storage_only_fields']}"
            )
        if agg_stats["raw_field_count"] != agg_stats["production_field_count"]:
            notes.append(
                f"field_count ({agg_stats['production_field_count']}) differs "
                f"from the raw distinct-FIELDNAME count "
                f"({agg_stats['raw_field_count']}) because "
                f"{agg_stats['storage_only_field_count']} field(s) had no "
                "production reporting units in this period - see "
                "storage_only_fields above. This is not data loss."
            )

        # Bounding-box check: always report observed min/max (headroom),
        # even on a pass, and always name every offending field on failure.
        points = [
            (r.slug, r.lon, r.lat) for r in records
        ]
        bbox_report = validate_bounding_box(points)
        print(
            "Bounding box observed: "
            f"lon [{bbox_report.observed_lon_min}, {bbox_report.observed_lon_max}], "
            f"lat [{bbox_report.observed_lat_min}, {bbox_report.observed_lat_max}] "
            "(allowed: lon [-14, 5], lat [48, 63])"
        )

        fields_geojson = build_fields_geojson(records)

        previous_meta = load_previous_meta()
        delta_notes = check_against_previous_build(
            previous_meta,
            current_latest_period=latest_period,
            current_record_count=len(rows),
            current_field_count=agg_stats["production_field_count"],
        )
        notes.extend(delta_notes)

        meta = {
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sources": {
                "production": {
                    "publisher": PUBLISHER,
                    "dataset": DATASET_NAME,
                    "item_id": ITEM_ID_POINTS,
                    "service_url": service_url,
                    "layer_max_record_count": max_record_count,
                }
            },
            "latest_period": latest_period,
            "earliest_period": earliest_period,
            "field_count": agg_stats["production_field_count"],
            "field_count_raw": agg_stats["raw_field_count"],
            "reporting_unit_count": agg_stats["production_unit_count"],
            "storage_unit_count": agg_stats["storage_unit_count"],
            "company_count": None,
            "record_count": len(rows),
            "schema_hash": schema_hash,
            "notes": notes,
        }

    except (ArcGISError, ValidationError, BuildError, ValueError) as e:
        print(f"\nBUILD FAILED: {e}", file=sys.stderr)
        return 1

    # All validation passed - write artifacts. Both writes are atomic
    # individually; if the process dies between them, the next run's
    # schema/record-count checks will catch any resulting inconsistency
    # rather than serving mismatched files silently.
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_json_atomic(DOCS_DATA_DIR / "meta.json", meta)
    write_json_atomic(DOCS_DATA_DIR / "fields.geojson", fields_geojson)

    print(f"\nWrote {DOCS_DATA_DIR / 'meta.json'}")
    print(f"Wrote {DOCS_DATA_DIR / 'fields.geojson'}")
    print(f"field_count={meta['field_count']} (raw distinct FIELDNAME: {meta['field_count_raw']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
