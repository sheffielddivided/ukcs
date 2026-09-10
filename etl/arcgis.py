"""
Paginated, retrying ArcGIS REST query client (spec section 8.2 / 13 step 2).

Used by every ETL step that talks to the NSTA ArcGIS Online services. Fixes
the prototype defects catalogued in spec section 3:

- always paginates (query_all), and checks exceededTransferLimit rather than
  trusting a single page (3.1)
- quotes where-clause literals conditionally on the live field type instead
  of assuming a type (3.2, quote_where_value)
- does not gate pagination on supportsPagination - the live PPRS layer
  reports this flag as null, so it is ignored entirely and pagination is
  always applied (section 0.1 / 8.2)
- distinguishes network failure, HTTP error and ArcGIS application error in
  every raised ArcGISError rather than collapsing them into one message (3)
"""

from __future__ import annotations

import json
import time
from typing import Iterator

import requests

SHARING_REST_ITEM_URL = "https://www.arcgis.com/sharing/rest/content/items/{item_id}"
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 5
RETRY_BACKOFF_BASE_SECONDS = 1.0
HARD_RECORD_CAP = 500_000


class ArcGISError(RuntimeError):
    """Raised when an ArcGIS REST call cannot be completed. The message
    always says whether this was a network failure, an HTTP error or an
    ArcGIS application-level error - never a generic "failed to fetch"."""


def _sleep_backoff(attempt: int) -> None:
    time.sleep(RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))


def _request_json(session: requests.Session, url: str, params: dict) -> dict:
    """GET url with params, retrying on 5xx and transient network errors
    (exponential backoff, max MAX_RETRIES attempts). 4xx errors are not
    retried - they are not transient."""
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(
                url, params={**params, "f": "json"}, timeout=REQUEST_TIMEOUT_SECONDS
            )
        except requests.exceptions.RequestException as e:
            last_exc = e
            if attempt == MAX_RETRIES:
                raise ArcGISError(
                    f"Network error fetching {url} after {MAX_RETRIES} attempts: {e!r} "
                    "(DNS failure, connection refused, timeout or TLS error - "
                    "not an application error; the host may be unreachable)"
                ) from e
            _sleep_backoff(attempt)
            continue

        if 500 <= resp.status_code < 600:
            last_exc = ArcGISError(f"HTTP {resp.status_code} from {url}")
            if attempt == MAX_RETRIES:
                raise ArcGISError(
                    f"HTTP {resp.status_code} fetching {url} after {MAX_RETRIES} "
                    f"attempts: {resp.text[:500]!r}"
                )
            _sleep_backoff(attempt)
            continue

        if resp.status_code != 200:
            raise ArcGISError(
                f"HTTP error {resp.status_code} fetching {url}: {resp.text[:500]!r}"
            )

        try:
            data = resp.json()
        except ValueError as e:
            raise ArcGISError(
                f"Response from {url} was not valid JSON: {resp.text[:500]!r}"
            ) from e

        if isinstance(data, dict) and "error" in data:
            err = data["error"]
            raise ArcGISError(
                f"ArcGIS application error from {url}: code={err.get('code')} "
                f"message={err.get('message')} details={err.get('details')}"
            )

        return data

    raise ArcGISError(f"Exhausted retries fetching {url}") from last_exc


def fetch_item_metadata(item_id: str, session: requests.Session | None = None) -> dict:
    """Fetch an ArcGIS Online item's full metadata dict (title, url,
    modified epoch-ms timestamp, etc). Callers that need the item's own
    `modified` timestamp for provenance/change-detection (rather than a
    live fetch-time wall clock, which would make a rebuild's output
    non-deterministic in content even when nothing upstream changed -
    see etl/company_groups.py) should use this instead of
    resolve_service_url(), which only returns the bare URL."""
    session = session or requests.Session()
    url = SHARING_REST_ITEM_URL.format(item_id=item_id)
    return _request_json(session, url, {})


def resolve_service_url(item_id: str, session: requests.Session | None = None) -> str:
    """Resolve an ArcGIS Online item ID to its service root URL. Never
    hardcode the result - services move (spec section 4)."""
    session = session or requests.Session()
    item = fetch_item_metadata(item_id, session=session)
    service_url = item.get("url")
    if not service_url:
        raise ArcGISError(
            f"Item {item_id} has no 'url' property in its metadata response - "
            f"it is not a hosted feature service. Response keys: {sorted(item.keys())}"
        )
    return service_url


def fetch_layer_metadata(
    service_url: str, layer_index: int = 0, session: requests.Session | None = None
) -> dict:
    """Fetch layer metadata (fields, maxRecordCount, capability flags)."""
    session = session or requests.Session()
    layer_url = f"{service_url.rstrip('/')}/{layer_index}"
    meta = _request_json(session, layer_url, {})
    meta["_layer_url"] = layer_url
    return meta


def quote_where_value(field_type: str, value) -> str:
    """Quote a where-clause literal conditionally on the live field type
    (spec section 3.2) - never assume a field is or isn't a string."""
    if "String" in field_type or "Date" in field_type:
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"
    return str(value)


def query_all(
    layer_url: str,
    *,
    where: str = "1=1",
    out_fields: str = "*",
    return_geometry: bool = False,
    max_record_count: int,
    session: requests.Session | None = None,
    hard_cap: int = HARD_RECORD_CAP,
) -> Iterator[dict]:
    """Yield every feature matching `where`, one at a time, paginating with
    resultOffset/resultRecordCount and checking exceededTransferLimit on
    every page (spec section 3.1 / 8.2).

    Always orders by OBJECTID for deterministic pagination - ArcGIS
    pagination is undefined without a stable order and will otherwise
    duplicate or drop rows across pages.

    Does not gate on supportsPagination: the live PPRS layer reports this
    flag as null, so pagination is applied unconditionally regardless of
    what the layer metadata claims.

    Raises ArcGISError and stops paginating if the hard record cap is
    exceeded, so a pagination bug or runaway query fails the build rather
    than exhausting the Actions minutes budget.
    """
    session = session or requests.Session()
    page_size = min(max_record_count, 2000)
    if page_size <= 0:
        raise ArcGISError(f"Invalid max_record_count={max_record_count!r} for pagination")

    offset = 0
    total_yielded = 0

    while True:
        params = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": "true" if return_geometry else "false",
            "orderByFields": "OBJECTID",
            "resultOffset": offset,
            "resultRecordCount": page_size,
        }
        data = _request_json(session, f"{layer_url}/query", params)
        features = data.get("features", [])
        exceeded = bool(data.get("exceededTransferLimit", False))

        for feature in features:
            total_yielded += 1
            if total_yielded > hard_cap:
                raise ArcGISError(
                    f"query_all exceeded hard cap of {hard_cap} records for "
                    f"where={where!r} - aborting rather than looping "
                    "indefinitely (possible pagination bug or runaway query)."
                )
            yield feature

        if not features:
            break
        if len(features) < page_size and not exceeded:
            break

        offset += page_size


def query_statistic(
    layer_url: str,
    field: str,
    statistic_type: str,
    *,
    where: str = "1=1",
    session: requests.Session | None = None,
) -> object:
    """Single round-trip statistic query via outStatistics (spec section
    3.3, in place of the fragile returnDistinctValues+orderByFields+
    limit=1 approach, which depends on supportsDistinct/supportsPagination
    being enabled - the live layer reports supportsPagination as null).

    statistic_type is any ArcGIS statisticType, e.g. "max", "min", "count".
    """
    session = session or requests.Session()
    stats = [
        {
            "statisticType": statistic_type,
            "onStatisticField": field,
            "outStatisticFieldName": "stat_value",
        }
    ]
    data = _request_json(
        session,
        f"{layer_url}/query",
        {"where": where, "outStatistics": json.dumps(stats)},
    )
    features = data.get("features", [])
    if not features:
        raise ArcGISError(
            f"outStatistics {statistic_type.upper()} query on {field!r} "
            f"returned no features (where={where!r})."
        )
    return features[0]["attributes"]["stat_value"]


def query_max_statistic(
    layer_url: str,
    field: str,
    *,
    where: str = "1=1",
    session: requests.Session | None = None,
) -> object:
    """Convenience wrapper for query_statistic(..., statistic_type='max')."""
    return query_statistic(layer_url, field, "max", where=where, session=session)
