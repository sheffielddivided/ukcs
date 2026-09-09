"""
Phase 1, step 1 (spec section 4 / 13.1).

Resolves the ArcGIS Online item IDs for the PPRS points layer to a live
service URL, dumps the layer schema to etl/schema_snapshot.json, prints a
human-readable field table, and runs the reporting-unit-vs-field grain
investigation required by section 7.1.

This script makes network calls to www.arcgis.com and the resolved service
host. It is read-only (GET only) and writes only to
etl/schema_snapshot.json. It does not touch docs/data/.

Run: python etl/discover.py
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ITEM_ID_POINTS = "dd38204275a04618ab7ddd00f87224e3"
ITEM_ID_POLYGONS = "b51887ab2c8547cfb6807cca0ca5fb88"

SHARING_REST = "https://www.arcgis.com/sharing/rest/content/items"

SCHEMA_SNAPSHOT_PATH = Path(__file__).parent / "schema_snapshot.json"

REQUEST_TIMEOUT_SECONDS = 30


class DiscoveryError(RuntimeError):
    """Raised when discovery cannot proceed. Message must say exactly why."""


def _get_json(url: str, params: dict | None = None) -> dict:
    """GET url (+params) and parse JSON. Distinguishes network, HTTP and
    ArcGIS application-level errors rather than collapsing them into one
    generic message (section 3, root cause analysis)."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url, headers={"User-Agent": "ukcs-discover/0.1"})

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            status = resp.status
            body = resp.read()
    except urllib.error.HTTPError as e:
        raise DiscoveryError(
            f"HTTP error {e.code} {e.reason} fetching {url}: {e.read()[:500]!r}"
        ) from e
    except urllib.error.URLError as e:
        raise DiscoveryError(
            f"Network error fetching {url}: {e.reason!r} "
            "(DNS failure, connection refused, or TLS error - not an "
            "application error; the host may be unreachable or renamed)"
        ) from e

    if status != 200:
        raise DiscoveryError(f"Unexpected HTTP status {status} fetching {url}")

    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise DiscoveryError(
            f"Response from {url} was not valid JSON: {body[:500]!r}"
        ) from e

    if isinstance(data, dict) and "error" in data:
        err = data["error"]
        raise DiscoveryError(
            f"ArcGIS application error from {url}: "
            f"code={err.get('code')} message={err.get('message')} "
            f"details={err.get('details')}"
        )

    return data


def resolve_service_url(item_id: str, label: str) -> str:
    print(f"\n--- Resolving item {item_id} ({label}) ---")
    item = _get_json(f"{SHARING_REST}/{item_id}", {"f": "json"})
    url = item.get("url")
    if not url:
        raise DiscoveryError(
            f"Item {item_id} ({label}) has no 'url' property in its metadata "
            f"response - it may not be a hosted feature service. "
            f"Full response keys: {sorted(item.keys())}"
        )
    print(f"item title:   {item.get('title')}")
    print(f"item type:    {item.get('type')}")
    print(f"service url:  {url}")
    return url


def fetch_layer_metadata(service_url: str, layer_index: int = 0) -> dict:
    layer_url = f"{service_url.rstrip('/')}/{layer_index}"
    print(f"\n--- Fetching layer metadata: {layer_url} ---")
    meta = _get_json(layer_url, {"f": "json"})
    meta["_layer_url"] = layer_url
    return meta


def print_field_table(meta: dict) -> None:
    fields = meta.get("fields", [])
    if not fields:
        raise DiscoveryError(
            "Layer metadata has no 'fields' array - cannot proceed without "
            "a schema to validate against."
        )
    print(f"\n--- Fields ({len(fields)}) ---")
    name_w = max(len(f["name"]) for f in fields) + 2
    type_w = max(len(f["type"]) for f in fields) + 2
    print(f"{'name':<{name_w}}{'type':<{type_w}}alias")
    for f in fields:
        print(f"{f['name']:<{name_w}}{f['type']:<{type_w}}{f.get('alias', '')}")

    print("\n--- Capabilities ---")
    for key in (
        "maxRecordCount",
        "supportsPagination",
        "supportsStatistics",
        "supportsAdvancedQueries",
        "supportedQueryFormats",
    ):
        print(f"{key}: {meta.get(key)!r}")


def query(layer_url: str, params: dict) -> dict:
    full_params = {"f": "json", **params}
    return _get_json(f"{layer_url}/query", full_params)


def find_latest_period(layer_url: str, period_field: str) -> str | int:
    """Use outStatistics with MAX rather than orderByFields+resultRecordCount=1
    (section 3.3 - the prototype's approach depends on supportsDistinct /
    standardised queries and is fragile)."""
    print(f"\n--- Finding latest {period_field} via outStatistics MAX ---")
    stats = [
        {
            "statisticType": "max",
            "onStatisticField": period_field,
            "outStatisticFieldName": "max_period",
        }
    ]
    result = query(
        layer_url,
        {
            "where": "1=1",
            "outStatistics": json.dumps(stats),
        },
    )
    features = result.get("features", [])
    if not features:
        raise DiscoveryError(
            f"outStatistics MAX query on {period_field} returned no features. "
            f"Raw response: {result}"
        )
    latest = features[0]["attributes"]["max_period"]
    print(f"latest {period_field} = {latest!r} (python type: {type(latest).__name__})")
    return latest


def grain_investigation(layer_url: str, meta: dict, period_field: str, latest_period) -> dict:
    """Section 7.1: for the latest period, groupBy FIELDNAME, UNITNAME,
    UNITTYPDES and report field/unit cardinality."""
    print(f"\n--- Grain investigation (section 7.1), period = {latest_period!r} ---")

    field_type = next(
        (f["type"] for f in meta["fields"] if f["name"] == period_field), None
    )
    if field_type is None:
        raise DiscoveryError(
            f"Period field {period_field!r} not found in layer schema; "
            "cannot build a where clause safely."
        )
    is_string = "String" in field_type
    where = f"{period_field}='{latest_period}'" if is_string else f"{period_field}={latest_period}"
    print(f"where clause: {where}  (field type: {field_type})")

    group_fields = "FIELDNAME,UNITNAME,UNITTYPDES"
    stats = [
        {
            "statisticType": "count",
            "onStatisticField": "OBJECTID",
            "outStatisticFieldName": "row_count",
        }
    ]
    result = query(
        layer_url,
        {
            "where": where,
            "groupByFieldsForStatistics": group_fields,
            "outStatistics": json.dumps(stats),
            "orderByFields": group_fields,
        },
    )
    if result.get("exceededTransferLimit"):
        raise DiscoveryError(
            "groupBy query for the grain investigation hit "
            "exceededTransferLimit - this script does not paginate grouped "
            "queries; results below would be incomplete and must not be trusted."
        )

    rows = [f["attributes"] for f in result.get("features", [])]
    if not rows:
        raise DiscoveryError(
            f"Grain investigation groupBy query returned zero rows for "
            f"where={where!r}. Raw response: {result}"
        )

    distinct_fields = sorted({r.get("FIELDNAME") for r in rows})
    distinct_pairs = sorted({(r.get("FIELDNAME"), r.get("UNITNAME")) for r in rows})

    units_per_field: dict[str, set] = {}
    for r in rows:
        units_per_field.setdefault(r.get("FIELDNAME"), set()).add(r.get("UNITNAME"))
    multi_unit_fields = sorted(
        (name, sorted(units)) for name, units in units_per_field.items() if len(units) > 1
    )

    print(f"distinct FIELDNAME:                {len(distinct_fields)}")
    print(f"distinct (FIELDNAME, UNITNAME):     {len(distinct_pairs)}")
    print(f"fields with >1 reporting unit:      {len(multi_unit_fields)}")
    if multi_unit_fields:
        print("\nFields with multiple reporting units:")
        for name, units in multi_unit_fields:
            print(f"  {name}: {units}")

    return {
        "where": where,
        "row_count": len(rows),
        "distinct_field_count": len(distinct_fields),
        "distinct_field_unit_pair_count": len(distinct_pairs),
        "multi_unit_field_count": len(multi_unit_fields),
        "multi_unit_fields": [{"field": n, "units": u} for n, u in multi_unit_fields],
    }


def main() -> int:
    try:
        points_service_url = resolve_service_url(ITEM_ID_POINTS, "PPRS points")
        layer_meta = fetch_layer_metadata(points_service_url, layer_index=0)
        print_field_table(layer_meta)

        field_names = {f["name"] for f in layer_meta["fields"]}
        period_field = "PERIODYRMN" if "PERIODYRMN" in field_names else None
        if period_field is None:
            raise DiscoveryError(
                "Expected period field 'PERIODYRMN' (from spec section 6, "
                "flagged as unverified) is not present in the live schema. "
                f"Actual field names: {sorted(field_names)}. "
                "Section 6 of the spec must be corrected before writing the ETL."
            )

        latest_period = find_latest_period(layer_meta["_layer_url"], period_field)
        grain_result = grain_investigation(
            layer_meta["_layer_url"], layer_meta, period_field, latest_period
        )

        polygons_service_url = resolve_service_url(ITEM_ID_POLYGONS, "PPRS polygons")

        snapshot = {
            "points_service_url": points_service_url,
            "polygons_service_url": polygons_service_url,
            "layer_url": layer_meta["_layer_url"],
            "maxRecordCount": layer_meta.get("maxRecordCount"),
            "supportsPagination": layer_meta.get("supportsPagination"),
            "supportsStatistics": layer_meta.get("supportsStatistics"),
            "supportsAdvancedQueries": layer_meta.get("supportsAdvancedQueries"),
            "supportedQueryFormats": layer_meta.get("supportedQueryFormats"),
            "fields": layer_meta.get("fields"),
            "period_field": period_field,
            "latest_period": latest_period,
            "grain_investigation": grain_result,
        }
        SCHEMA_SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2, default=str))
        print(f"\nSchema snapshot written to {SCHEMA_SNAPSHOT_PATH}")
        return 0

    except DiscoveryError as e:
        print(f"\nDISCOVERY FAILED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
