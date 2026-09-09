"""
Build-breaking validation (spec section 8.3 / 13 steps 3, 5, 7 and 8).

Every function here either passes silently or raises ValidationError. There
is no "warn and continue" path for these rules - section 8.3 requires the
build to fail loudly and write no artifacts. build.py must run every
relevant check here BEFORE writing any file to docs/data/.

Status as of step 8 (see the step-8 build report for the full audit): all
six literal section 8.3 rules were already implemented as of step 3
(schema drift, latest-period record-count delta, latest-period regression,
negative values, latest-period field-count drop, previous-meta
unreadable) - the module's own docstring previously undersold this as a
"subset", which was stale. New in step 8: an explicit aggregate-level
negative-value check (the raw-row check already made this mathematically
impossible via summation-only aggregation, but the literal spec wording is
about field-level values, so this closes it explicitly rather than by
implication); history-level record-count and field-count delta checks
(extending the existing latest-period-only checks to the full history
fetch, since a truncation could plausibly hit history without moving the
latest period); a formal pagination-count-mismatch check (previously
inline BuildError in build.py); and the operator-conservation check
promoted from a step-7 inline check to a standing, always-run rule. The
full E1-E9 equity rules (section 15.4) are added in Phase 2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dataclass_field

# Fields Phase 1 depends on, and the esri type each must have. Section 6 /
# 0.1: these are the names verified live in v2.2 - if any of them go
# missing or change type, everything downstream is unsafe to trust.
EXPECTED_FIELDS: dict[str, str] = {
    "OBJECTID": "esriFieldTypeOID",
    "FIELDNAME": "esriFieldTypeString",
    "FIELDAREA": "esriFieldTypeString",
    "LOCATION": "esriFieldTypeString",
    "ORGGRPNM": "esriFieldTypeString",
    "UNITNAME": "esriFieldTypeString",
    "UNITTYPCOD": "esriFieldTypeString",
    "UNITTYPDES": "esriFieldTypeString",
    "PERIODYRMN": "esriFieldTypeString",
    "PERIODDATE": "esriFieldTypeDate",
    "OILPRODMBD": "esriFieldTypeDouble",
    "AGASPROMMS": "esriFieldTypeDouble",
    "DGASPROMMS": "esriFieldTypeDouble",
    "GCONDMBD": "esriFieldTypeDouble",
    "GASPIPVOLM": "esriFieldTypeDouble",
    "WATPRODMBD": "esriFieldTypeDouble",
}

# Value fields that must never be negative (spec section 8.3).
PRODUCTION_VALUE_FIELDS = (
    "OILPRODMBD",
    "AGASPROMMS",
    "DGASPROMMS",
    "GCONDMBD",
    "GASPIPVOLM",
    "WATPRODMBD",
)

# Tokens that flag a reporting unit as possibly storage/injection rather
# than production (spec section 7.3). This is a tripwire, not a
# classifier: a match that isn't already in unit_classification.csv fails
# the build for human review, it is never auto-assigned.
STORAGE_TRIPWIRE_TOKENS = ("STORAGE", "INJECTION")

# UKCS bounding box (spec section 9.2): lon -14 to 5, lat 48 to 63.
UKCS_LON_MIN, UKCS_LON_MAX = -14.0, 5.0
UKCS_LAT_MIN, UKCS_LAT_MAX = 48.0, 63.0


class ValidationError(RuntimeError):
    """Raised on any build-breaking validation failure. The build must
    catch this, write no artifacts, and exit non-zero."""


def validate_schema(live_fields: list[dict]) -> None:
    """Fail if an expected field is missing or has changed type (spec
    8.3, first bullet)."""
    by_name = {f["name"]: f["type"] for f in live_fields}
    problems = []
    for name, expected_type in EXPECTED_FIELDS.items():
        if name not in by_name:
            problems.append(f"missing expected field {name!r}")
        elif by_name[name] != expected_type:
            problems.append(
                f"field {name!r} changed type: expected {expected_type!r}, "
                f"got {by_name[name]!r}"
            )
    if problems:
        raise ValidationError(
            "Schema drift detected against expected PPRS fields "
            "(spec section 6): " + "; ".join(problems)
        )


def validate_no_negative_values(rows: list[dict]) -> None:
    """Fail if any production value is negative (spec 8.3)."""
    offenders = []
    for row in rows:
        attrs = row["attributes"]
        for field_name in PRODUCTION_VALUE_FIELDS:
            value = attrs.get(field_name)
            if value is not None and value < 0:
                offenders.append(
                    f"{attrs.get('FIELDNAME')}/{attrs.get('UNITNAME')} "
                    f"period={attrs.get('PERIODYRMN')} {field_name}={value}"
                )
    if offenders:
        raise ValidationError(
            "Negative production value(s) found: " + "; ".join(offenders[:20])
            + (f" (+{len(offenders) - 20} more)" if len(offenders) > 20 else "")
        )


AGGREGATE_VALUE_KEYS = (
    "oil_mbd",
    "assoc_gas_mmscfd",
    "dry_gas_mmscfd",
    "condensate_mbd",
    "water_mbd",
)


def validate_no_negative_aggregated_values(series_by_label: dict[str, list[dict]]) -> None:
    """Fail if any AGGREGATE (field- or operator-level, post-summation)
    value is negative (spec 8.3's literal wording: "any field-level oil or
    gas value is negative"). validate_no_negative_values() above checks
    raw PPRS rows, which already makes this mathematically impossible
    given aggregation is summation-only - a negative aggregate is
    unreachable if every addend is non-negative. This function exists to
    make that guarantee explicit and structural rather than implied, so a
    future change to the aggregation logic (e.g. introducing a subtraction
    or a derived field) cannot silently reintroduce the failure mode
    without tripping a build.

    series_by_label: {label -> [{"period": ..., <value keys>: ...}, ...]},
    e.g. {"buzzard": history_doc["series"], ...}."""
    offenders = []
    for label, series in series_by_label.items():
        for point in series:
            for key in AGGREGATE_VALUE_KEYS:
                value = point.get(key)
                if value is not None and value < 0:
                    offenders.append(f"{label} period={point.get('period')} {key}={value}")
    if offenders:
        raise ValidationError(
            "Negative AGGREGATE value(s) found (post-summation, should be "
            "structurally impossible - indicates an aggregation logic bug, "
            "not a raw-data issue): " + "; ".join(offenders[:20])
            + (f" (+{len(offenders) - 20} more)" if len(offenders) > 20 else "")
        )


def validate_pagination_count(fetched_count: int, independent_count: int, label: str) -> None:
    """Fail if the number of rows actually fetched via query_all()
    disagrees with an independent outStatistics COUNT query for the same
    where clause. The two are computed by different code paths against
    the same live query, so a mismatch means pagination genuinely dropped
    or duplicated rows - the paginated fetch on its own can never detect
    this against itself (spec section 3.1 / 8.2)."""
    if fetched_count != independent_count:
        raise ValidationError(
            f"Pagination mismatch on {label}: fetched {fetched_count} rows "
            f"via query_all but an independent outStatistics COUNT query "
            f"returned {independent_count} for the same where clause. This "
            "indicates a pagination bug (or the service changed data mid-"
            "fetch) and must not proceed."
        )


def validate_operator_conservation(
    field_series_by_slug: dict[str, list[dict]],
    operator_series_by_slug: dict[str, list[dict]],
    tolerance: float = 0.01,
) -> None:
    """Standing rule (promoted from a step-7 inline check, spec 9.4 / 13
    step 8): attributing every field's history to its current operator
    (section 6.1) is a straight repartition - each field belongs to
    exactly one operator - so the sum of every value field across all
    operator-period entries must equal the sum across all field-period
    entries, exactly, for every value field independently. This is the
    same invariant-based pattern as Phase 2's E1/E8 equity checks: it
    catches a field silently dropped or double-counted during rollup,
    which would otherwise produce numbers that are wrong but still look
    individually plausible."""
    for key in AGGREGATE_VALUE_KEYS:
        field_total = sum(
            point.get(key) or 0.0
            for series in field_series_by_slug.values()
            for point in series
        )
        operator_total = sum(
            point.get(key) or 0.0
            for series in operator_series_by_slug.values()
            for point in series
        )
        if abs(field_total - operator_total) > tolerance:
            raise ValidationError(
                f"Operator aggregation is not conservative for {key!r}: "
                f"sum across all fields = {field_total}, sum across all "
                f"operators = {operator_total} (difference "
                f"{abs(field_total - operator_total)} exceeds tolerance "
                f"{tolerance}). This indicates fields were dropped or "
                "double-counted when attributed to operators."
            )


def find_unclassified_storage_like_units(
    rows: list[dict], classification_map: dict[tuple[str, str], str]
) -> list[tuple[str, str]]:
    """Tripwire (spec 7.3): return every (field, unit) whose UNITNAME
    matches a storage/injection token and is NOT already present in
    unit_classification.csv. Does not classify - only detects. Caller
    decides whether to raise."""
    seen: set[tuple[str, str]] = set()
    flagged: list[tuple[str, str]] = []
    for row in rows:
        attrs = row["attributes"]
        key = (attrs.get("FIELDNAME"), attrs.get("UNITNAME"))
        if key in seen:
            continue
        seen.add(key)
        unit_name = (attrs.get("UNITNAME") or "").upper()
        if key in classification_map:
            continue
        if any(token in unit_name for token in STORAGE_TRIPWIRE_TOKENS):
            flagged.append(key)
    return flagged


def validate_unit_classification_tripwire(
    rows: list[dict], classification_map: dict[tuple[str, str], str]
) -> None:
    flagged = find_unclassified_storage_like_units(rows, classification_map)
    if flagged:
        names = "; ".join(f"{f}/{u}" for f, u in flagged)
        raise ValidationError(
            "Reporting unit(s) matched a storage/injection tripwire token "
            "but are not classified in etl/mappings/unit_classification.csv "
            "(spec section 7.3). Review and add them to the CSV before "
            f"rebuilding: {names}"
        )


@dataclass
class BoundingBoxReport:
    observed_lon_min: float
    observed_lon_max: float
    observed_lat_min: float
    observed_lat_max: float
    violations: list[str] = dataclass_field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


def check_bounding_box(points: list[tuple[str, float, float]]) -> BoundingBoxReport:
    """points: list of (label, lon, lat). Always computes the observed
    min/max regardless of pass/fail, so headroom against the box is
    visible even on a passing build - not just reported on failure."""
    if not points:
        raise ValidationError("No points supplied to the bounding-box check.")

    lons = [p[1] for p in points]
    lats = [p[2] for p in points]
    report = BoundingBoxReport(
        observed_lon_min=min(lons),
        observed_lon_max=max(lons),
        observed_lat_min=min(lats),
        observed_lat_max=max(lats),
    )
    for label, lon, lat in points:
        if not (UKCS_LON_MIN <= lon <= UKCS_LON_MAX and UKCS_LAT_MIN <= lat <= UKCS_LAT_MAX):
            report.violations.append(f"{label}: lon={lon}, lat={lat}")
    return report


def validate_bounding_box(points: list[tuple[str, float, float]]) -> BoundingBoxReport:
    """Raises ValidationError naming every offending point if any point
    falls outside the UKCS bounding box (spec 9.2)."""
    report = check_bounding_box(points)
    if not report.ok:
        raise ValidationError(
            "Coordinate(s) outside the UKCS bounding box "
            f"(lon [{UKCS_LON_MIN}, {UKCS_LON_MAX}], "
            f"lat [{UKCS_LAT_MIN}, {UKCS_LAT_MAX}]): "
            + "; ".join(report.violations)
        )
    return report


def _check_delta(
    label: str,
    prev_value: int | None,
    current_value: int,
    tolerance_pct: float,
    direction: str,  # "delta" (either direction) or "drop" (decrease only)
) -> str | None:
    """Shared delta-check logic for a (previous, current) count pair.
    Returns a pass note, or raises ValidationError on a threshold breach.
    Returns None if there is nothing to compare (prev_value falsy)."""
    if not prev_value:
        return None
    if direction == "drop":
        change_pct = (prev_value - current_value) / prev_value * 100
        breached = change_pct > tolerance_pct
        verb = "dropped"
    else:
        change_pct = abs(current_value - prev_value) / prev_value * 100
        breached = change_pct > tolerance_pct
        verb = "changed"
    if breached:
        raise ValidationError(
            f"{label} {verb} by {change_pct:.1f}% versus previous build "
            f"({prev_value} -> {current_value}), exceeding the "
            f"{tolerance_pct:.0f}% tolerance."
        )
    return f"{label} check passed: {prev_value} -> {current_value} ({change_pct:.1f}%)."


def check_against_previous_build(
    previous_meta: dict | None,
    *,
    current_latest_period: str,
    current_record_count: int,
    current_field_count: int,
    current_history_record_count: int | None = None,
    current_history_field_count: int | None = None,
) -> list[str]:
    """Delta checks against the previous build's meta.json (spec 8.3, plus
    the step-8 history-level extensions - see module docstring). Returns a
    list of human-readable notes describing which checks ran and which
    were skipped - a first run must not silently "pass" checks it never
    performed. Raises ValidationError on an actual failure.

    current_history_record_count / current_history_field_count are
    optional (step 5+ only) extensions of the same delta-check pattern to
    the full-history fetch, not just the latest period - a truncation
    that hits historical data without moving the latest period's own
    counts would otherwise pass every section 8.3 rule undetected."""
    notes = []

    if previous_meta is None:
        notes.append(
            "No previous build found (first run) - skipped: record-count "
            "delta check, latest-period regression check, field-count drop "
            "check, history-record-count delta check, history-field-count "
            "drop check. These will run starting from the next build."
        )
        return notes

    note = _check_delta(
        "Latest-period record-count delta",
        previous_meta.get("record_count"), current_record_count, 20, "delta",
    )
    if note:
        notes.append(note)

    prev_latest_period = previous_meta.get("latest_period")
    if prev_latest_period and current_latest_period < prev_latest_period:
        raise ValidationError(
            f"Latest period regressed: previous build had "
            f"{prev_latest_period!r}, this build has "
            f"{current_latest_period!r}."
        )
    if prev_latest_period:
        notes.append(
            f"Latest-period regression check passed: "
            f"{prev_latest_period!r} -> {current_latest_period!r}."
        )

    note = _check_delta(
        "Latest-period field-count drop",
        previous_meta.get("field_count"), current_field_count, 10, "drop",
    )
    if note:
        notes.append(note)

    # Step 8 additions: the same delta-check pattern applied to the full
    # history fetch, not just the latest period - closes part of the gap
    # where a truncation hits historical data without moving the latest
    # period's own counts (see the step-8 build report for what this does
    # and does not close).
    if current_history_record_count is not None:
        note = _check_delta(
            "History record-count delta",
            previous_meta.get("history_record_count"), current_history_record_count, 20, "delta",
        )
        if note:
            notes.append(note)

    if current_history_field_count is not None:
        note = _check_delta(
            "History field-count drop",
            previous_meta.get("history_field_count"), current_history_field_count, 10, "drop",
        )
        if note:
            notes.append(note)

    return notes
