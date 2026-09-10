"""
ETL entry point (spec section 8 / 13 steps 3, 5 and 7).

Resolves the PPRS points service, validates its schema, fetches the latest
period (with geometry) and the full attribute history (no geometry),
classifies reporting units, aggregates to field and operator grain,
validates, and writes meta.json, fields.geojson, history/*.json and
operators.json (+ operators/*.json if the >2MB split threshold is hit).

Usage: python etl/build.py
Exit code is non-zero on any validation failure; on failure, docs/data/ is
left untouched (spec 8.3: "Do not write partial artifacts").
"""

from __future__ import annotations

import hashlib
import json
import shutil
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
    GENERATED_FROM_OPERATOR,
    aggregate_history,
    aggregate_latest_period,
    aggregate_operators,
    build_fields_geojson,
    build_history_artifacts,
    build_operators_artifacts,
    load_unit_classification,
)
from validate import (  # noqa: E402
    ValidationError,
    check_against_previous_build,
    validate_bounding_box,
    validate_derived_field_month_formula,
    validate_full_precision_conservation,
    validate_no_negative_aggregated_values,
    validate_no_negative_values,
    validate_operator_conservation,
    validate_pagination_count,
    validate_schema,
    validate_serialized_derived_conservation,
    validate_unit_classification_tripwire,
)
from equity_artifacts import (  # noqa: E402
    EquityBuildError,
    build_anomalies,
    build_company_artifacts,
    build_field_artifacts,
    build_index,
    build_meta as build_equity_meta,
    build_publication_status_by_period_stream,
    run_equity_pipeline,
    write_equity_artifacts,
)
from equity_mboed import build_derived_status_by_period  # noqa: E402
from production_config import (  # noqa: E402
    GAS_SCF_PER_BOE,
    PRODUCTION_CONVERSION_METHODOLOGY,
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
EQUITY_DATA_DIR = DOCS_DATA_DIR / "equity"

OUT_FIELDS = (
    "OBJECTID,FIELDNAME,FIELDAREA,LOCATION,ORGGRPNM,UNITNAME,UNITTYPDES,"
    "PERIODYRMN,OILPRODMBD,AGASPROMMS,DGASPROMMS,GCONDMBD,GASPIPVOLM,WATPRODMBD"
)

OPERATORS_SPLIT_THRESHOLD_BYTES = 2 * 1024 * 1024  # spec 9.4


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


def _json_text(data: object) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def write_json_atomic(path: Path, data: object) -> None:
    """Serialise with sorted keys and fixed separators so a rebuild of
    unchanged input produces a byte-identical file (spec: 'deterministic
    output'), and write via a temp file + atomic rename so a crash
    mid-write can never leave a partial artifact in place (spec 8.3 /
    'atomic writes')."""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(_json_text(data), encoding="utf-8")
    tmp_path.replace(path)


def write_history_dir_atomic(history_dir: Path, per_slug: dict, index: dict) -> None:
    """Write every history/{slug}.json plus history/index.json to a
    staging directory, then atomically swap it in for the real
    history/ directory in one rename. This guarantees the directory as a
    whole is never left half-old/half-new (spec 8.3/13 step 5:
    'atomic writes' and 'no partial artifacts') - a per-file crash mid-way
    through hundreds of files would otherwise be a much larger blast
    radius than the single-file case in step 3."""
    staging_dir = history_dir.with_name(history_dir.name + ".tmp")
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)

    for slug, doc in per_slug.items():
        (staging_dir / f"{slug}.json").write_text(_json_text(doc), encoding="utf-8")
    (staging_dir / "index.json").write_text(_json_text(index), encoding="utf-8")

    if history_dir.exists():
        shutil.rmtree(history_dir)
    staging_dir.rename(history_dir)


def write_slug_files_atomic(target_dir: Path, per_slug: dict) -> None:
    """Like write_history_dir_atomic but without an index.json inside the
    directory - used for operators/{slug}.json when the >2MB split (spec
    9.4) is triggered, since operators.json itself (at the docs/data/
    level, not inside this directory) already serves as the index."""
    staging_dir = target_dir.with_name(target_dir.name + ".tmp")
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)

    for slug, doc in per_slug.items():
        (staging_dir / f"{slug}.json").write_text(_json_text(doc), encoding="utf-8")

    if target_dir.exists():
        shutil.rmtree(target_dir)
    staging_dir.rename(target_dir)


def remove_dir_if_exists(target_dir: Path) -> None:
    if target_dir.exists():
        shutil.rmtree(target_dir)


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
        validate_pagination_count(len(rows), independent_count, "latest-period fetch")

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

        # --- Full history (spec 13 step 5): attributes only, no geometry ---
        history_independent_count = query_statistic(
            layer_url, "OBJECTID", "count", where="1=1", session=session
        )
        history_rows = list(
            query_all(
                layer_url,
                where="1=1",
                out_fields=OUT_FIELDS,
                return_geometry=False,
                max_record_count=max_record_count,
                session=session,
            )
        )
        print(
            f"Fetched {len(history_rows)} full-history rows "
            f"(independent count: {history_independent_count})"
        )
        validate_pagination_count(len(history_rows), history_independent_count, "full-history fetch")

        validate_no_negative_values(history_rows)
        validate_unit_classification_tripwire(history_rows, classification_map)

        histories, history_stats = aggregate_history(history_rows, classification_map)
        print(f"History aggregation stats: {history_stats}")

        if history_stats["storage_only_field_count"]:
            notes.append(
                f"{history_stats['storage_only_field_count']} field(s) in the "
                "full history had only storage reporting units at every "
                "observed period and were excluded entirely from history/: "
                f"{history_stats['storage_only_fields']}"
            )

        history_per_slug, history_index = build_history_artifacts(histories)

        # --- Operators (spec 13 step 7): current-operator-of-record
        # aggregation, stepping-stone metric only (spec 6.1/9.4). Storage
        # exclusion is inherited for free - `histories` here is the same
        # storage-excluded FieldHistory list built above.
        operator_histories, operator_stats = aggregate_operators(histories)
        print(f"Operator aggregation stats: {operator_stats}")

        operators_index, operators_per_slug = build_operators_artifacts(operator_histories)

        # Standing conservation rule (spec 8.3/13 step 8 - promoted from a
        # step-7 inline check): same invariant-based pattern Phase 2's E1/
        # E8 equity checks will use. See validate.py for the rationale.
        validate_operator_conservation(
            {slug: doc["series"] for slug, doc in history_per_slug.items()},
            {slug: doc["series"] for slug, doc in operators_per_slug.items()},
        )
        print("Operator aggregation conservation check passed for all value fields.")

        # Explicit aggregate-level negative-value check (spec 8.3's literal
        # "any field-level oil or gas value is negative" wording) across
        # both fields.geojson's latest-period properties and every field's
        # and operator's full history series. Structurally redundant with
        # validate_no_negative_values() above given summation-only
        # aggregation, but made explicit rather than implied - see
        # validate.py.
        validate_no_negative_aggregated_values(
            {r.slug: [{
                "period": r.period,
                "oil_mbd": r.totals.get("oil_mbd"),
                "assoc_gas_mmscfd": r.totals.get("assoc_gas_mmscfd"),
                "dry_gas_mmscfd": r.totals.get("dry_gas_mmscfd"),
                "condensate_mbd": r.totals.get("condensate_mbd"),
                "water_mbd": r.totals.get("water_mbd"),
            }] for r in records}
        )
        validate_no_negative_aggregated_values(
            {slug: doc["series"] for slug, doc in history_per_slug.items()}
        )
        validate_no_negative_aggregated_values(
            {slug: doc["series"] for slug, doc in operators_per_slug.items()}
        )
        print("Aggregate-level negative-value check passed (fields, history, operators).")

        # Derived mboe/d formula and conservation checks (spec section 17/6).
        # Formula check: recompute liquids_mboed/natural_gas_mboed/total_mboed
        # from each artifact's OWN serialized native fields and confirm they
        # match (within the small double-rounding tolerance documented in
        # validate.validate_derived_field_month_formula) - run against
        # fields.geojson's own properties (built above) and every field's
        # and operator's full history series.
        validate_derived_field_month_formula(
            {f["properties"]["slug"]: [f["properties"]] for f in fields_geojson["features"]}
        )
        validate_derived_field_month_formula({slug: doc["series"] for slug, doc in history_per_slug.items()})
        validate_derived_field_month_formula({slug: doc["series"] for slug, doc in operators_per_slug.items()})

        # Cross-grain conservation for the derived fields (Workstream 0
        # hardening, spec approved 2026-09-10): the original flat
        # CONSERVATION_TOLERANCE_MBOED=5.0 was reviewed and replaced with
        # two narrower, mathematically-justified checks - see
        # validate.py's module-level docstring on both functions for the
        # full derivation.
        #
        # A. Pre-serialization: full-precision totals (never rounded) -
        # any divergence beyond float-summation noise is a real
        # aggregation bug, since the two sides are mathematically
        # identical sums of the same raw data at this point.
        full_precision_report = validate_full_precision_conservation(
            {h.slug: h.full_precision_series for h in histories},
            {oh.slug: oh.full_precision_series for oh in operator_histories},
        )
        print(
            "Full-precision (pre-serialization) derived conservation passed: "
            + ", ".join(f"{k}={v:.3e}" for k, v in full_precision_report.items())
        )

        # B. Post-serialization: the actual artifact values, checked
        # against a tolerance mathematically derived from this build's
        # own real entry counts and rounding precision.
        serialization_report = validate_serialized_derived_conservation(
            {slug: doc["series"] for slug, doc in history_per_slug.items()},
            {slug: doc["series"] for slug, doc in operators_per_slug.items()},
        )
        print(
            "Post-serialization derived conservation passed: "
            + ", ".join(
                f"{k}=diff:{v['diff']:.4f}/tol:{v['tolerance']:.4f}"
                for k, v in serialization_report.items()
            )
        )
        print("Derived mboe/d formula and field-to-operator conservation checks passed.")

        operators_full_text_size = len(
            _json_text({"generated_from": None, "operators": {
                slug: {**operators_index[slug], "series": operators_per_slug[slug]["series"]}
                for slug in operators_index
            }}).encode("utf-8")
        )
        operators_split = operators_full_text_size > OPERATORS_SPLIT_THRESHOLD_BYTES
        print(
            f"operators.json embedded-series size would be "
            f"{operators_full_text_size / 1e6:.2f} MB "
            f"(split threshold {OPERATORS_SPLIT_THRESHOLD_BYTES / 1e6:.0f} MB) -> "
            f"{'SPLIT into operators/*.json' if operators_split else 'single operators.json file'}"
        )

        # --- Phase 2 equity (spec 15.8 steps 5-6, restricted publication
        # window per section 15.11): fetch, parse, match, full historical
        # resolve, restrict to EQUITY_PUBLICATION_START onward, validate.
        # Uses history_per_slug/history_index already built above - no
        # disk read of docs/data/history/* (those files may still be the
        # PREVIOUS build's content at this point; the in-memory objects
        # are this run's authoritative data). Raises EquityBuildError
        # (caught below, alongside the production pipeline's exceptions)
        # on any failure - if equity fails, nothing is written, including
        # the production artifacts, so a failed equity refresh can never
        # publish alongside stale-but-passing production data or vice
        # versa (spec 15.11: "the entire build must fail").
        previous_equity_meta = None
        previous_equity_meta_path = EQUITY_DATA_DIR / "meta.json"
        if previous_equity_meta_path.exists():
            with open(previous_equity_meta_path, encoding="utf-8") as f:
                previous_equity_meta = json.load(f)

        equity_result = run_equity_pipeline(
            history_per_slug, history_index, session, previous_equity_meta=previous_equity_meta
        )
        equity_status_by_period_stream = build_publication_status_by_period_stream(equity_result["monthly_data"])
        equity_derived_status_by_period = build_derived_status_by_period(equity_result["monthly_data"])
        equity_company_docs = build_company_artifacts(
            equity_result["resolved_rows"], equity_status_by_period_stream, equity_derived_status_by_period
        )
        equity_field_docs = build_field_artifacts(
            equity_result["field_match_index"],
            equity_result["raw_rows_by_equity_field"],
            equity_result["published"],
        )
        equity_index = build_index(equity_company_docs)
        equity_anomalies = build_anomalies(equity_result)
        equity_built_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        equity_meta = build_equity_meta(equity_result, equity_company_docs, equity_field_docs, equity_built_at)
        print(
            f"Equity pipeline: {equity_meta['matched_field_count']} matched fields, "
            f"{equity_meta['unmatched_field_count']} unmatched, "
            f"{equity_meta['legal_entity_count']} legal entities, "
            f"published {equity_meta['earliest_published_period']}-{equity_meta['latest_published_period']}"
        )

        previous_meta = load_previous_meta()
        delta_notes = check_against_previous_build(
            previous_meta,
            current_latest_period=latest_period,
            current_record_count=len(rows),
            current_field_count=agg_stats["production_field_count"],
            current_history_record_count=len(history_rows),
            current_history_field_count=history_stats["field_with_history_count"],
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
                },
                "equity": {
                    "publisher": PUBLISHER,
                    "source_item_title": equity_meta["source_item_title"],
                    "source_page_description": equity_meta["source_page_description"],
                    "resolved_workbook_url": equity_meta["resolved_workbook_url"],
                    "last_modified": equity_meta["last_modified"],
                    "sha256": equity_meta["sha256"],
                    "publication_start": equity_meta["publication_start"],
                    # Full detail (per-company, per-field, anomalies) lives in
                    # docs/data/equity/meta.json - this is a summary pointer,
                    # not a duplicate of that file.
                },
            },
            "latest_period": latest_period,
            "earliest_period": earliest_period,
            "field_count": agg_stats["production_field_count"],
            "field_count_raw": agg_stats["raw_field_count"],
            "reporting_unit_count": agg_stats["production_unit_count"],
            "storage_unit_count": agg_stats["storage_unit_count"],
            "company_count": equity_meta["legal_entity_count"],
            "record_count": len(rows),
            "history_record_count": len(history_rows),
            "history_field_count": history_stats["field_with_history_count"],
            "history_field_count_raw": history_stats["raw_field_count"],
            "history_series_point_count": history_stats["period_count"],
            "operator_count": operator_stats["operator_count"],
            "operators_split": operators_split,
            "schema_hash": schema_hash,
            "artifact_schema_version": 2,
            "production_conversion_methodology": PRODUCTION_CONVERSION_METHODOLOGY,
            "gas_scf_per_boe": GAS_SCF_PER_BOE,
            "notes": notes,
        }

    except (ArcGISError, ValidationError, BuildError, EquityBuildError, ValueError) as e:
        print(f"\nBUILD FAILED: {e}", file=sys.stderr)
        return 1

    # All validation passed - write artifacts. Writes are atomic
    # individually; if the process dies between them, the next run's
    # schema/record-count checks will catch any resulting inconsistency
    # rather than serving mismatched files silently.
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_json_atomic(DOCS_DATA_DIR / "meta.json", meta)
    write_json_atomic(DOCS_DATA_DIR / "fields.geojson", fields_geojson)
    write_history_dir_atomic(DOCS_DATA_DIR / "history", history_per_slug, history_index)
    write_equity_artifacts(EQUITY_DATA_DIR, equity_meta, equity_index, equity_company_docs, equity_field_docs, equity_anomalies)
    print(
        f"Wrote {EQUITY_DATA_DIR} ({len(equity_company_docs)} company files, "
        f"{len(equity_field_docs)} field files)"
    )

    operators_doc = {
        "generated_from": GENERATED_FROM_OPERATOR,
        "operators": {
            slug: (
                {**operators_index[slug]}
                if operators_split
                else {**operators_index[slug], "series": operators_per_slug[slug]["series"]}
            )
            for slug in operators_index
        },
    }
    write_json_atomic(DOCS_DATA_DIR / "operators.json", operators_doc)
    if operators_split:
        write_slug_files_atomic(DOCS_DATA_DIR / "operators", operators_per_slug)
    else:
        remove_dir_if_exists(DOCS_DATA_DIR / "operators")

    print(f"\nWrote {DOCS_DATA_DIR / 'meta.json'}")
    print(f"Wrote {DOCS_DATA_DIR / 'fields.geojson'}")
    print(f"Wrote {DOCS_DATA_DIR / 'history'}/ ({len(history_per_slug)} field files + index.json)")
    print(
        f"Wrote {DOCS_DATA_DIR / 'operators.json'}"
        + (f" + {DOCS_DATA_DIR / 'operators'}/ ({len(operators_per_slug)} files)" if operators_split else "")
    )
    print(f"field_count={meta['field_count']} (raw distinct FIELDNAME: {meta['field_count_raw']})")
    print(f"operator_count={meta['operator_count']} (split={operators_split})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
