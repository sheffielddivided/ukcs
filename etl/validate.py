"""
Build-breaking validation (spec section 8.3 / 13 step 3, expanded in step 8).

Every function here either passes silently or raises ValidationError. There
is no "warn and continue" path for these rules - section 8.3 requires the
build to fail loudly and write no artifacts. build.py must run every
relevant check here BEFORE writing any file to docs/data/.

This module currently implements the subset of section 8.3 needed to
produce meta.json / fields.geojson correctly (step 3): schema drift,
negative values, the reporting-unit classification tripwire (section 7.3),
the UKCS bounding box, and the previous-build delta checks with explicit
first-run handling. The full E1-E9 equity rules (section 15.4) are added in
Phase 2.
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


def check_against_previous_build(
    previous_meta: dict | None,
    *,
    current_latest_period: str,
    current_record_count: int,
    current_field_count: int,
) -> list[str]:
    """Delta checks against the previous build's meta.json (spec 8.3).
    Returns a list of human-readable notes describing which checks ran and
    which were skipped - a first run must not silently "pass" checks it
    never performed. Raises ValidationError on an actual failure."""
    notes = []

    if previous_meta is None:
        notes.append(
            "No previous build found (first run) - skipped: record-count "
            "delta check, latest-period regression check, field-count drop "
            "check. These will run starting from the next build."
        )
        return notes

    prev_record_count = previous_meta.get("record_count")
    if prev_record_count:
        delta_pct = abs(current_record_count - prev_record_count) / prev_record_count * 100
        if delta_pct > 20:
            raise ValidationError(
                f"Latest-period record count changed by {delta_pct:.1f}% "
                f"versus previous build ({prev_record_count} -> "
                f"{current_record_count}), exceeding the 20% tolerance."
            )
        notes.append(
            f"Record-count delta check passed: {prev_record_count} -> "
            f"{current_record_count} ({delta_pct:.1f}%)."
        )

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

    prev_field_count = previous_meta.get("field_count")
    if prev_field_count:
        drop_pct = (prev_field_count - current_field_count) / prev_field_count * 100
        if drop_pct > 10:
            raise ValidationError(
                f"Distinct field count dropped by {drop_pct:.1f}% versus "
                f"previous build ({prev_field_count} -> "
                f"{current_field_count}), exceeding the 10% tolerance."
            )
        notes.append(
            f"Field-count drop check passed: {prev_field_count} -> "
            f"{current_field_count} ({drop_pct:.1f}% change)."
        )

    return notes
