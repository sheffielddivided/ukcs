"""
Company grouping (Workstream 1, spec approved 2026-09-10): retains the
three concepts the approval requires as distinct -

    1. Legal entity as recorded by NSTA - already the sole grain of the
       equity artifacts (etl/equity_artifacts.py), unchanged.
    2. Current display group - IMPLEMENTED here.
    3. Historical group-at-the-time - NOT implemented: no dated,
       authoritative corporate-group evidence was found in discovery
       (etl/phase3_discovery_report.md section 3), so this module never
       produces one. A current display group is never presented as
       historically contemporaneous ownership - see
       docs/methodology.html's retrospective-grouping caveat and every
       consumer of GROUP_RETROSPECTIVE_WARNING below.

Primary source: NSTA's own current-state group taxonomy, the
`EQGRPHOLD` ("equity group holder") field on the live "UKCS offshore
petroleum licence subareas by equity group holder (WGS84)" service
(item 40c65d96a1a14da8b066f2abbb345fed, resolved at build time - never
hardcoded, per spec section 4). This is a (subarea, holder) grain: each
row carries EQGRPHOLD (the group) and EQUITY (that holder's own
percentage for that row) but the *individual* legal entity name for that
row must be recovered from EQORG, a single string listing every holder
of the subarea with their percentages (e.g.
"PERENCO GAS (UK) LIMITED (85%), EVERARD ENERGY LIMITED (15%)"). A row's
own legal entity is identified by matching EQUITY against the one EQORG
segment with the same percentage; where two holders in the same subarea
tie on percentage this is genuinely ambiguous (the discovery report
measured 488 of 1,803 rows this way) and is never guessed.

No fuzzy grouping: an entity is only ever assigned a non-self group when
NSTA's own EQGRPHOLD evidence unambiguously names it (same group on
every row it appears in). Sharing a name token is never sufficient.

Every entity NSTA's current-licence source does not cover - most of the
292 equity legal entities in docs/data/equity, since most never held
this equity dataset's current slice of licences - falls back to being
its own singleton display group (grouping_basis="registered company
identity"), status="unresolved" (not reviewed/approved as a genuine
corporate family, simply un-grouped). This is a structural fallback, not
a claim: it groups nothing, so it never fabricates a relationship, and
production conservation (sum(legal entity) == sum(current display
group)) holds by construction either way.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from datetime import datetime, timezone  # noqa: E402

from arcgis import (  # noqa: E402
    ArcGISError,
    fetch_item_metadata,
    fetch_layer_metadata,
    query_all,
    query_statistic,
)
from equity_match import PRODUCTION_STREAMS  # noqa: E402
from equity_mboed import DERIVED_STREAMS  # noqa: E402
from mboed import round_mboed  # noqa: E402
from transform import round3, slugify  # noqa: E402

ALL_STREAMS = list(PRODUCTION_STREAMS) + list(DERIVED_STREAMS)
_ROUND_FN = {**{s: round3 for s in PRODUCTION_STREAMS}, **{s: round_mboed for s in DERIVED_STREAMS}}

EQUITY_GROUP_HOLDER_ITEM_ID = "40c65d96a1a14da8b066f2abbb345fed"

EXPECTED_FIELDS = {
    "EQORG": "esriFieldTypeString",
    "EQGRPHOLD": "esriFieldTypeString",
    "EQUITY": "esriFieldTypeDouble",
}

# Displayed on every UI surface that shows production regrouped by
# current display group over historical periods (spec Workstream 1 UI
# policy) - the exact required wording.
GROUP_RETROSPECTIVE_WARNING = (
    "Current-group view: historical production has been regrouped using "
    "current company relationships. This is an analytical presentation "
    "and does not represent ownership at the time."
)

# The bucket a legal entity's OWN name-as-display-group falls under in
# any UI listing/filter of entities with no reviewed corporate-group
# evidence (spec Workstream 1: "Unresolved legal entities must remain
# visible under an explicit 'Unmapped legal entities' group. They must
# never disappear from totals.") - this is a UI/listing label only; the
# entity's own production is never merged into any other entity's total
# under this bucket (see build_company_groups_mapping()'s docstring).
UNMAPPED_BUCKET_LABEL = "Unmapped legal entities"


class CompanyGroupsError(RuntimeError):
    """Raised on any build-breaking failure in the company-grouping
    pipeline - caught in etl/build.py alongside the equity pipeline's own
    exceptions, per the same 'fail the whole build, write nothing' rule."""


_EQORG_SEGMENT_RE = re.compile(r"^(.*?)\s*\(([\d.]+)\s*%\)\s*$")


def parse_eqorg_segments(eqorg: str | None) -> list[tuple[str, float]]:
    """Parses NSTA's combined EQORG string ("NAME (85%), NAME2 (15%)")
    into [(name, pct), ...]. Returns [] for a blank/unparseable value -
    callers treat that as "no usable holder detail", never as a crash."""
    if not eqorg:
        return []
    segments = []
    for part in eqorg.split(","):
        match = _EQORG_SEGMENT_RE.match(part.strip())
        if match:
            name = match.group(1).strip()
            try:
                pct = float(match.group(2))
            except ValueError:
                continue
            segments.append((name, pct))
    return segments


PERCENTAGE_MATCH_TOLERANCE = 1e-6


def resolve_row_holder_name(eqorg: str | None, equity_pct: float | None) -> str | None:
    """Identifies THIS row's own legal entity name from its combined
    EQORG string, by matching `equity_pct` against the one EQORG segment
    with the same percentage. Returns None (never a guess) if there is
    no segment at that percentage, or more than one (a genuine tie - see
    module docstring; the discovery report measured this at 488/1,803
    rows across the whole dataset)."""
    if equity_pct is None:
        return None
    segments = parse_eqorg_segments(eqorg)
    matches = [name for name, pct in segments if abs(pct - equity_pct) <= PERCENTAGE_MATCH_TOLERANCE]
    if len(matches) != 1:
        return None
    return matches[0]


def _epoch_ms_to_iso(epoch_ms: int | None) -> str | None:
    if epoch_ms is None:
        return None
    return datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_equity_group_holder_rows(session) -> dict:
    """Fetches every row of the live equity-group-holder service (spec:
    resolve the item ID at build time, never hardcode the resolved
    service URL). Returns {"rows": [...], "resolved_url": ..., "item_title": ...,
    "source_last_modified": ..., "record_count": ...}. Raises
    CompanyGroupsError on schema drift or a pagination/count mismatch -
    the same build-breaking discipline as the production/equity
    pipelines.

    `source_last_modified` is the ITEM's own modification timestamp (from
    ArcGIS Online's item metadata), not a live fetch-time wall clock -
    deliberately, so that re-running the build against unchanged upstream
    data produces byte-identical mapping output (see build_company_groups_mapping()
    callers) instead of a spurious diff on every single run, mirroring
    every other source's own last_modified-based provenance in this
    build (e.g. the equity workbook's own Last-Modified header)."""
    try:
        item_meta = fetch_item_metadata(EQUITY_GROUP_HOLDER_ITEM_ID, session=session)
        service_url = item_meta.get("url")
        if not service_url:
            raise CompanyGroupsError(
                f"Item {EQUITY_GROUP_HOLDER_ITEM_ID} has no 'url' in its metadata response."
            )
        layer_meta = fetch_layer_metadata(service_url, layer_index=0, session=session)
    except ArcGISError as e:
        raise CompanyGroupsError(f"Could not resolve/fetch the equity-group-holder service: {e}") from e

    live_fields = {f["name"]: f["type"] for f in layer_meta.get("fields", [])}
    problems = []
    for name, expected_type in EXPECTED_FIELDS.items():
        if name not in live_fields:
            problems.append(f"missing expected field {name!r}")
        elif live_fields[name] != expected_type:
            problems.append(
                f"field {name!r} changed type: expected {expected_type!r}, got {live_fields[name]!r}"
            )
    if problems:
        raise CompanyGroupsError(
            "Schema drift on the equity-group-holder service: " + "; ".join(problems)
        )

    layer_url = layer_meta["_layer_url"]
    max_record_count = layer_meta.get("maxRecordCount", 1000)

    try:
        independent_count = query_statistic(layer_url, "OBJECTID", "count", session=session)
    except ArcGISError as e:
        raise CompanyGroupsError(f"Could not get an independent row count: {e}") from e

    rows = list(
        query_all(
            layer_url,
            out_fields="EQORG,EQGRPHOLD,EQUITY",
            max_record_count=max_record_count,
            session=session,
        )
    )
    if len(rows) != independent_count:
        raise CompanyGroupsError(
            f"Pagination mismatch on equity-group-holder service: fetched {len(rows)} "
            f"rows but an independent COUNT query returned {independent_count}."
        )

    return {
        "rows": rows,
        "resolved_url": service_url,
        "item_title": item_meta.get("title"),
        "source_last_modified": _epoch_ms_to_iso(item_meta.get("modified")),
        "record_count": len(rows),
    }


def build_group_resolution(rows: list[dict]) -> dict[str, dict]:
    """From raw equity-group-holder rows, builds
    {legal_entity_name: {"groups": {group_name: row_count}, "ambiguous_row_count": int}}
    - every legal entity name NSTA's own EQORG/EQGRPHOLD/EQUITY combination
    could unambiguously identify, together with which group(s) it was seen
    under (almost always exactly one; more than one is a genuine
    cross-subarea conflict in the source, surfaced rather than picked
    arbitrarily) and how many of its OWN rows were tie-ambiguous and
    therefore skipped."""
    resolution: dict[str, dict] = {}
    for row in rows:
        attrs = row["attributes"]
        holder_name = resolve_row_holder_name(attrs.get("EQORG"), attrs.get("EQUITY"))
        group = attrs.get("EQGRPHOLD")
        if holder_name is None or not group:
            continue
        entry = resolution.setdefault(holder_name, {"groups": {}, "ambiguous_row_count": 0})
        entry["groups"][group] = entry["groups"].get(group, 0) + 1
    return resolution


CSV_REQUIRED_COLUMNS = {
    "source_legal_entity",
    "current_display_group",
    "valid_from",
    "valid_to",
    "grouping_basis",
    "source",
    "reviewed_by",
    "reviewed_on",
    "status",
}


def load_company_groups_overrides(path) -> dict[str, dict]:
    """Loads etl/mappings/company_groups.csv (spec Workstream 1) - a
    CURATED, human-reviewed exceptions file, matching the exact pattern
    of etl/mappings/unit_classification.csv: only explicit, evidenced
    overrides are listed here, never a full company list, and nothing
    absent from this file is implied by its absence (the automated NSTA
    EQGRPHOLD resolution, or a self-fallback, fills every entity not
    listed here). A row here always takes precedence over the automated
    NSTA resolution for the same entity - this is the ONLY route to
    grouping_basis="reviewed manual mapping". The file currently ships
    with no rows: no additional authoritative, dated corporate-group
    evidence beyond NSTA's own live EQGRPHOLD field was available at
    implementation time (spec: "No fuzzy grouping. No grouping merely
    because names share a token.") - entries should only ever be added
    here alongside real, citable evidence and a real reviewer name/date,
    never fabricated to fill this out."""
    import csv as csv_module

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv_module.DictReader(f)
        if reader.fieldnames is None or not CSV_REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise CompanyGroupsError(
                f"{path} is missing expected columns {sorted(CSV_REQUIRED_COLUMNS)}; "
                f"found {reader.fieldnames}"
            )
        overrides = {}
        for row in reader:
            entity = row["source_legal_entity"].strip()
            if not entity:
                continue
            overrides[entity] = dict(row)
    return overrides


def build_company_groups_mapping(
    known_legal_entities: set[str],
    resolution: dict[str, dict],
    source_description: str,
    fetch_timestamp: str,
    overrides: dict[str, dict] | None = None,
) -> list[dict]:
    """Builds one mapping row per entity in `known_legal_entities` (every
    legal entity name actually used in the equity artifacts), in the
    etl/mappings/company_groups.csv schema. Every entity gets exactly one
    row - never silently dropped.

    Resolution precedence per entity:
    - A curated override row in `overrides` (etl/mappings/company_groups.csv,
      see load_company_groups_overrides()) - always wins, unchanged.
    - Unambiguous NSTA EQGRPHOLD evidence (exactly one group seen across
      every row) -> grouping_basis="NSTA equity group", status="approved".
    - NSTA evidence exists but conflicts (more than one group seen) ->
      falls back to itself, status="unresolved" (a real, surfaced data
      conflict - never picked arbitrarily).
    - No evidence at all -> falls back to itself,
      grouping_basis="registered company identity", status="unresolved".
    Nothing is fabricated automatically (spec: "No fuzzy grouping.")."""
    overrides = overrides or {}
    out = []
    for entity in sorted(known_legal_entities):
        if entity in overrides:
            out.append(dict(overrides[entity]))
            continue
        entry = resolution.get(entity)
        if entry and len(entry["groups"]) == 1:
            (group_name,) = entry["groups"].keys()
            out.append(
                {
                    "source_legal_entity": entity,
                    "current_display_group": group_name,
                    "valid_from": "",
                    "valid_to": "",
                    "grouping_basis": "NSTA equity group",
                    "source": source_description,
                    "reviewed_by": "automated-nsta-source",
                    "reviewed_on": fetch_timestamp,
                    "status": "approved",
                }
            )
        elif entry and len(entry["groups"]) > 1:
            out.append(
                {
                    "source_legal_entity": entity,
                    "current_display_group": entity,
                    "valid_from": "",
                    "valid_to": "",
                    "grouping_basis": "registered company identity",
                    "source": (
                        f"NSTA source shows conflicting EQGRPHOLD values for this entity: "
                        f"{sorted(entry['groups'].keys())} - not auto-resolved"
                    ),
                    "reviewed_by": "",
                    "reviewed_on": fetch_timestamp,
                    "status": "unresolved",
                }
            )
        else:
            out.append(
                {
                    "source_legal_entity": entity,
                    "current_display_group": entity,
                    "valid_from": "",
                    "valid_to": "",
                    "grouping_basis": "registered company identity",
                    "source": "no current NSTA licence equity-group evidence for this entity",
                    "reviewed_by": "",
                    "reviewed_on": fetch_timestamp,
                    "status": "unresolved",
                }
            )
    return out


def mapping_by_entity(mapping_rows: list[dict]) -> dict[str, dict]:
    return {row["source_legal_entity"]: row for row in mapping_rows}


# ---------------------------------------------------------------------------
# Group-level series aggregation
# ---------------------------------------------------------------------------


def _aggregate_stream_point(constituent_points: list[dict | None]) -> dict:
    """Aggregates one stream's {value, status, ...} entries across every
    constituent legal entity of a group, for one (period, stream).

    None-safe sum (spec: exact conservation is required) - a constituent
    with an unavailable/unpublished value (value is None) contributes
    nothing to the sum, exactly as it already contributes nothing to a
    plain "sum across all legal entities" at the legal-entity grain. This
    makes sum(legal-entity) == sum(current-display-group) hold by
    construction: regrouping only changes which bucket a published number
    lands in, never drops or fabricates one.

    Status: "complete" only if every constituent was complete;
    "unavailable" only if every constituent had no published value;
    otherwise "partial" - a distinct status (not reused from the
    per-entity vocabulary) meaning "this group total sums only the
    constituents that had a published value this period; at least one
    other constituent's production for this period is not published" -
    surfaced explicitly rather than silently presented as a complete
    total."""
    available = [p for p in constituent_points if p and p.get("value") is not None]
    if not available:
        return {"value": None, "status": "unavailable", "constituent_count": len(constituent_points)}
    total = sum(p["value"] for p in available)
    if len(available) == len(constituent_points) and all(
        p.get("status") == "complete" for p in available
    ):
        status = "complete"
    elif len(available) == len(constituent_points):
        status = "warning" if any(p.get("status") == "warning" for p in available) else "complete"
    else:
        status = "partial"
    return {"value": total, "status": status, "constituent_count": len(constituent_points)}


def aggregate_company_series_by_group(
    company_docs: dict[str, dict], entity_to_group: dict[str, str]
) -> dict[str, dict]:
    """Groups company-grain production series (etl/equity_artifacts.py's
    build_company_artifacts() output) into current-display-group series,
    per the mapping in `entity_to_group` (source_legal_entity ->
    current_display_group, e.g. from mapping_by_entity() applied to
    build_company_groups_mapping()'s rows). An entity with no mapping
    entry is treated as its own singleton group (never dropped - spec:
    "No entity disappears").

    Returns {group_name: {"member_entities": [...], "series": [...]}} in
    the same per-period {stream: {"value", "status", ...}} shape as the
    company docs, so the frontend can reuse the same rendering code for
    both grains."""
    members_by_group: dict[str, list[str]] = {}
    for entity in company_docs:
        group = entity_to_group.get(entity, entity)
        members_by_group.setdefault(group, []).append(entity)

    group_docs: dict[str, dict] = {}
    for group, members in members_by_group.items():
        periods = sorted({point["period"] for m in members for point in company_docs[m]["series"]})
        by_period_by_entity = {
            m: {point["period"]: point for point in company_docs[m]["series"]} for m in members
        }
        series = []
        for period in periods:
            entry = {"period": period}
            for stream in ALL_STREAMS:
                constituent_points = [
                    by_period_by_entity[m].get(period, {}).get(stream) for m in members
                ]
                aggregated = _aggregate_stream_point(constituent_points)
                round_fn = _ROUND_FN[stream]
                entry[stream] = {
                    "value": round_fn(aggregated["value"]) if aggregated["value"] is not None else None,
                    "status": aggregated["status"],
                }
            series.append(entry)
        group_docs[group] = {
            "slug": slugify(group),
            "name": group,
            "member_entities": sorted(members),
            "is_singleton": len(members) == 1,
            "series": series,
        }
    return group_docs


def validate_group_conservation(
    company_docs: dict[str, dict], group_docs: dict[str, dict], streams: list[str] = ALL_STREAMS
) -> dict[str, float]:
    """Build-breaking check (spec Workstream 1 validation): for every
    stream, sum(legal-entity production) must equal
    sum(current-display-group production) across the ENTIRE published
    history - not just true "by construction", but explicitly verified
    against the actual artifacts about to be written, the same
    defence-in-depth pattern etl/validate.py already uses for the native
    and derived field conservation checks. Returns {stream: diff} and
    raises CompanyGroupsError if any stream's diff exceeds a tight
    floating-point tolerance (both sides are None-safe sums of the same
    underlying published values - no rounding-order difference is
    possible here, unlike the field/operator derived-conservation case,
    since regrouping performs no arithmetic transformation, only
    relabels and sums the same numbers)."""
    tolerance = 1e-6
    diffs = {}
    offenders = []
    for stream in streams:
        entity_total = sum(
            point[stream]["value"] or 0.0
            for doc in company_docs.values()
            for point in doc["series"]
            if point[stream]["value"] is not None
        )
        group_total = sum(
            point[stream]["value"] or 0.0
            for doc in group_docs.values()
            for point in doc["series"]
            if point[stream]["value"] is not None
        )
        diff = abs(entity_total - group_total)
        diffs[stream] = diff
        if diff > tolerance:
            offenders.append(
                f"{stream!r}: legal-entity total={entity_total}, group total={group_total}, "
                f"diff={diff} exceeds tolerance {tolerance}"
            )
    if offenders:
        raise CompanyGroupsError(
            "Company-group conservation failed - regrouping must never change a "
            "total, only relabel it: " + "; ".join(offenders)
        )
    return diffs


# ---------------------------------------------------------------------------
# Mapping CSV (etl/mappings/company_groups.csv) and grouping review report
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    "source_legal_entity",
    "current_display_group",
    "valid_from",
    "valid_to",
    "grouping_basis",
    "source",
    "reviewed_by",
    "reviewed_on",
    "status",
]


def write_company_groups_csv(path, mapping_rows: list[dict]) -> None:
    """Deterministic (sorted by source_legal_entity, fixed column order)
    write of the mapping CSV, so a rebuild against unchanged source data
    produces a byte-identical file - matches every other artifact's
    determinism discipline in this build."""
    import csv

    rows_sorted = sorted(mapping_rows, key=lambda r: r["source_legal_entity"])
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows_sorted:
            writer.writerow({col: row.get(col, "") for col in CSV_COLUMNS})


def build_grouping_review_report(
    mapping_rows: list[dict],
    group_docs: dict[str, dict],
    latest_period: str,
) -> dict:
    """Builds the committed grouping review report (spec Workstream 1):
    every known legal entity with its matched group and grouping source,
    unresolved entities, ambiguous candidates, production-weighted
    current coverage, and historical production affected by retrospective
    grouping. Written as docs/data/equity/groups/report.json (an
    ordinary generated, git-committed artifact, like every other
    docs/data/equity/* file - not a separate hand-maintained document)."""
    approved = [r for r in mapping_rows if r["status"] == "approved"]
    unresolved = [r for r in mapping_rows if r["status"] == "unresolved"]
    ambiguous = [
        r for r in unresolved if "conflicting EQGRPHOLD" in r["source"]
    ]

    # Production-weighted current coverage: share of latest-period total
    # mboe/d (summed across every legal entity with a published latest-
    # period value) contributed by entities with an APPROVED (non-
    # self-fallback) group mapping.
    approved_entities = {r["source_legal_entity"] for r in approved}
    latest_total = 0.0
    latest_approved_total = 0.0
    for group in group_docs.values():
        latest_point = next((p for p in group["series"] if p["period"] == latest_period), None)
        if not latest_point:
            continue
        value = latest_point.get("total_mboed", {}).get("value")
        if value is None:
            continue
        latest_total += value
        if any(member in approved_entities for member in group["member_entities"]):
            latest_approved_total += value

    coverage_pct = round(100.0 * latest_approved_total / latest_total, 3) if latest_total > 0 else None

    # Historical production affected by retrospective grouping: every
    # period's total_mboed contributed by a NON-singleton group (i.e. a
    # group that actually merges more than one legal entity) - by
    # definition, every period of that group's history is being shown
    # under a label that was not necessarily the entity's own name at
    # that time, which is exactly what the UI's retrospective warning
    # exists to flag.
    non_singleton_groups = [g for g in group_docs.values() if not g["is_singleton"]]
    historical_affected_total = sum(
        point.get("total_mboed", {}).get("value") or 0.0
        for g in non_singleton_groups
        for point in g["series"]
    )
    all_historical_total = sum(
        point.get("total_mboed", {}).get("value") or 0.0
        for g in group_docs.values()
        for point in g["series"]
    )
    historical_affected_pct = (
        round(100.0 * historical_affected_total / all_historical_total, 3)
        if all_historical_total > 0
        else None
    )

    return {
        "total_legal_entities": len(mapping_rows),
        "approved_count": len(approved),
        "unresolved_count": len(unresolved),
        "ambiguous_conflict_count": len(ambiguous),
        "distinct_current_display_groups": len({r["current_display_group"] for r in mapping_rows}),
        "non_singleton_group_count": len(non_singleton_groups),
        "latest_period": latest_period,
        "production_weighted_current_coverage_pct": coverage_pct,
        "historical_production_affected_by_retrospective_grouping_pct": historical_affected_pct,
        "unresolved_entities": sorted(r["source_legal_entity"] for r in unresolved),
        "ambiguous_entities": sorted(r["source_legal_entity"] for r in ambiguous),
        "entities": sorted(
            [
                {
                    "source_legal_entity": r["source_legal_entity"],
                    "current_display_group": r["current_display_group"],
                    "grouping_basis": r["grouping_basis"],
                    "status": r["status"],
                }
                for r in mapping_rows
            ],
            key=lambda r: r["source_legal_entity"],
        ),
    }
