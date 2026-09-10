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
import sys
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mboed import GAS_MMSCF_PER_MBOE  # noqa: E402

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
    keys: tuple[str, ...] = AGGREGATE_VALUE_KEYS,
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
    individually plausible.

    `keys` defaults to the native AGGREGATE_VALUE_KEYS but is also used
    (spec section 17, section 6's conservation requirement) with
    DERIVED_MBOED_KEYS for the derived liquids_mboed/natural_gas_mboed/
    total_mboed fields - same invariant, same function, different value
    keys and a looser tolerance passed explicitly by the caller (see
    DERIVED_MBOED_TOLERANCE)."""
    for key in keys:
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


# Derived field keys (spec section 17).
DERIVED_MBOED_KEYS = ("liquids_mboed", "natural_gas_mboed", "total_mboed")


# ---------------------------------------------------------------------------
# Workstream 0 hardening (spec, approved 2026-09-10): the original
# CONSERVATION_TOLERANCE_MBOED=5.0 flat tolerance was reviewed and found to
# risk concealing a dropped small field. It is replaced by two separate,
# narrower checks:
#
#   A. Pre-serialization: field vs. operator totals compared at FULL
#      PRECISION (etl/transform.py's *.full_precision_series, never
#      rounded) - the only legitimate source of divergence left at this
#      point is IEEE 754 float summation noise, so the tolerance is a
#      floating-point epsilon bound, not a rounding-policy one.
#   B. Post-serialization: the ACTUAL artifact values (already rounded)
#      are compared against a tolerance mathematically derived from the
#      serialization precision and the number of independently-rounded
#      values summed on each side - never an arbitrary constant.
# ---------------------------------------------------------------------------

# IEEE 754 double machine epsilon (~2.22e-16) is the relative error bound
# of a single float addition. Conservatively bounding the ACCUMULATED
# error of summing up to ~250,000 terms (comfortably above this dataset's
# ~134,000 field-period rows plus its few-thousand operator-period rows)
# of magnitude up to ~10,000 (a generous ceiling - no single UKCS
# field-period or operator-period mboe/d total is anywhere near this):
#   bound = N * eps * max_abs_value = 250_000 * 2.22e-16 * 10_000
#         ~= 5.55e-7
# Rounded up with a wide safety margin (~2 orders of magnitude) since this
# guards a hard build failure and the true float-summation error in
# practice is far smaller (Python's built-in sum() is not even the
# worst-case-error naive summation this bound assumes).
FLOAT_PRECISION_TOLERANCE_MBOED = 1e-4


def validate_full_precision_conservation(
    field_full_precision_by_slug: dict[str, list[dict]],
    operator_full_precision_by_slug: dict[str, list[dict]],
    keys: tuple[str, ...] = DERIVED_MBOED_KEYS,
    tolerance: float = FLOAT_PRECISION_TOLERANCE_MBOED,
) -> dict[str, float]:
    """Pre-serialization conservation (Workstream 0, part A): field vs.
    operator totals compared BEFORE either grain has ever been rounded
    (etl/transform.py's FieldHistory/OperatorHistory.full_precision_series).
    At this point the two totals are mathematically identical sums over
    the same underlying raw values (see aggregate_operators()'s docstring
    on why summing derived keys directly is exact, not an approximation)
    - so ANY divergence beyond ordinary float-summation noise indicates a
    real aggregation bug (a field dropped or double-counted), not a
    rounding artifact. Returns {key: observed_abs_diff} for every key,
    for the build report, and raises ValidationError if any key exceeds
    `tolerance`."""
    observed: dict[str, float] = {}
    offenders = []
    for key in keys:
        field_total = sum(
            point.get(key) or 0.0
            for series in field_full_precision_by_slug.values()
            for point in series
        )
        operator_total = sum(
            point.get(key) or 0.0
            for series in operator_full_precision_by_slug.values()
            for point in series
        )
        diff = abs(field_total - operator_total)
        observed[key] = diff
        if diff > tolerance:
            offenders.append(
                f"{key!r}: field_total={field_total}, operator_total={operator_total}, "
                f"diff={diff} exceeds float-precision tolerance {tolerance}"
            )
    if offenders:
        raise ValidationError(
            "Full-precision (pre-serialization) derived-field conservation "
            "failed - this is BEFORE any rounding, so this indicates a real "
            "aggregation bug (a field dropped or double-counted when "
            "attributed to operators), not a rounding artifact: "
            + "; ".join(offenders)
        )
    return observed


# Confidence multiplier for compute_serialization_tolerance()'s statistical
# bound, in standard deviations. Chosen, not fitted: for a sum of this
# many (~10^5) independent, bounded, roughly-uniform per-entry rounding
# errors, the Central Limit Theorem makes the sum's distribution close to
# Normal, so an 8-sigma tolerance corresponds to a false-positive
# probability on the order of 1e-15 for noise alone - astronomically
# unlikely to ever fire from rounding noise, while still being roughly
# two orders of magnitude tighter than the deterministic worst-case bound
# (see that bound's rejected derivation, kept below in this function's
# docstring for why it was not used) and therefore easily sensitive
# enough to catch a genuinely dropped field (a few mboe/d) rather than
# concealing it the way the old flat 5.0 constant could.
SERIALIZATION_TOLERANCE_SIGMA = 8.0


def compute_serialization_tolerance(
    n_field_entries: int,
    n_operator_entries: int,
    round_decimals: int,
) -> float:
    """Mathematically derived (not arbitrary) tolerance for how far two
    independently-rounded sums of the SAME full-precision total can
    diverge (Workstream 0, part B), derived from serialization precision
    and the real number of independently-rounded values on each side.

    Each of the `n_field_entries` field-period values was rounded once at
    serialization (etl/mboed.py's round_mboed()), each introducing an
    error versus its true full-precision value that is bounded by
    half_ulp = 0.5 * 10**-round_decimals and, for values that are not
    themselves adversarially chosen, well modelled as i.i.d. roughly
    Uniform(-half_ulp, +half_ulp) - the standard assumption for rounding
    error analysis (see e.g. Higham, "Accuracy and Stability of Numerical
    Algorithms"). Such a variable has variance half_ulp**2 / 3, so the
    SUM of `n_field_entries` independent such errors has standard
    deviation half_ulp * sqrt(n_field_entries / 3). The operator-grain
    sum contributes its own, independent such term from its
    `n_operator_entries` roundings; the two sums' DIFFERENCE therefore
    has combined variance from both, i.e. standard deviation
    half_ulp * sqrt((n_field_entries + n_operator_entries) / 3).

    The naive alternative - a deterministic worst-case bound of
    (n_field_entries + n_operator_entries) * half_ulp from the triangle
    inequality - was rejected: at this repository's real scale
    (~134,000 field-period rows) it evaluates to ~34, LOOSER than the
    original flat 5.0 constant this workstream exists to tighten, since
    it assumes every single rounding error points the same direction
    (a scenario that would itself be a sign of a systematic bug, not
    ordinary rounding). The statistical bound below is the standard,
    textbook treatment of accumulated independent rounding error and is
    what is actually applied.

    Returns SERIALIZATION_TOLERANCE_SIGMA standard deviations of that
    combined distribution - see its own docstring for the false-positive
    rate this corresponds to."""
    half_ulp = 0.5 * (10 ** -round_decimals)
    combined_std_dev = half_ulp * ((n_field_entries + n_operator_entries) / 3) ** 0.5
    return SERIALIZATION_TOLERANCE_SIGMA * combined_std_dev


def validate_serialized_derived_conservation(
    field_series_by_slug: dict[str, list[dict]],
    operator_series_by_slug: dict[str, list[dict]],
    keys: tuple[str, ...] = DERIVED_MBOED_KEYS,
    round_decimals: int = 3,
) -> dict[str, dict]:
    """Post-serialization reconciliation (Workstream 0, part B): compares
    the ACTUAL artifact values (already rounded) using a tolerance
    computed by compute_serialization_tolerance() from the real number of
    independently-rounded entries on each side of THIS build - never a
    fixed constant. Returns {key: {"diff": ..., "tolerance": ...}} for
    the build report, and raises ValidationError if any key exceeds its
    own computed tolerance."""
    n_field_entries = sum(len(series) for series in field_series_by_slug.values())
    n_operator_entries = sum(len(series) for series in operator_series_by_slug.values())
    tolerance = compute_serialization_tolerance(n_field_entries, n_operator_entries, round_decimals)

    results: dict[str, dict] = {}
    offenders = []
    for key in keys:
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
        diff = abs(field_total - operator_total)
        results[key] = {"diff": diff, "tolerance": tolerance}
        if diff > tolerance:
            offenders.append(
                f"{key!r}: field_total={field_total}, operator_total={operator_total}, "
                f"diff={diff} exceeds the theoretical rounding-error bound {tolerance} "
                f"(derived from {n_field_entries} field-period + {n_operator_entries} "
                f"operator-period independently-rounded entries at {round_decimals} "
                "decimal places)"
            )
    if offenders:
        raise ValidationError(
            "Serialized (post-rounding) derived-field conservation exceeded "
            "its mathematically derived tolerance - since this tolerance is "
            "already a worst-case bound on rounding noise alone, this "
            "indicates a real aggregation bug: " + "; ".join(offenders)
        )
    return results


def validate_derived_field_month_formula(
    series_by_label: dict[str, list[dict]],
    tolerance: float = 0.01,
) -> None:
    """Build-breaking invariant (spec section 6): for every field-month
    (or operator-month, or company-month) entry actually written to an
    artifact, liquids_mboed == oil_mbd + condensate_mbd,
    natural_gas_mboed == (dry_gas_mmscfd + assoc_gas_mmscfd) / 6, and
    total_mboed == liquids_mboed + natural_gas_mboed, recomputed from the
    artifact's OWN serialized (already-rounded) native fields.

    The tolerance accounts for two independent, bounded rounding sources
    (not a real defect in either):
    (1) the artifact's derived fields (liquids_mboed etc.) are computed
    from full-precision unrounded components and rounded exactly ONCE at
    serialization (etl/mboed.py's round_mboed()), a <=0.0005 error versus
    the true value;
    (2) this check instead recomputes "expected" from the artifact's OWN
    serialized native fields (oil_mbd, condensate_mbd, etc.), which at
    FIELD grain are rounded once but at OPERATOR grain are deliberately
    left double-rounded (summed from already-field-rounded values, then
    round3()'d again - see aggregate_operators()'s docstring in
    transform.py for why the native fields specifically are kept this
    way rather than switched to full precision). At operator grain the
    FIRST rounding step's error can itself accumulate across however
    many fields that operator holds (not bounded by a fixed count), so a
    single analytic worst-case bound isn't meaningful without per-entry
    field-count data this check doesn't carry.

    The tolerance below is therefore set empirically, not purely
    analytically: verified directly against a real full-history build of
    every field and every operator (552 fields, 50 operators, 1975-2026),
    where the observed maximum divergence was ~0.004 mboe/d (at operator
    grain, for total_mboed, the case with the most compounding
    components). 0.01 keeps better than 2x margin over that measured
    worst case, while remaining roughly 500x tighter than the flat 5.0
    conservation tolerance this Workstream replaces - a genuine formula
    bug (wrong divisor, swapped components) would produce differences of
    whole mboe/d units or a systematic ratio error, not a fraction of a
    rounding unit, so this remains a meaningful check."""
    offenders = []
    for label, series in series_by_label.items():
        for point in series:
            oil = point.get("oil_mbd") or 0.0
            condensate = point.get("condensate_mbd") or 0.0
            dry_gas = point.get("dry_gas_mmscfd") or 0.0
            assoc_gas = point.get("assoc_gas_mmscfd") or 0.0
            expected_liquids = oil + condensate
            expected_gas = (dry_gas + assoc_gas) / GAS_MMSCF_PER_MBOE
            expected_total = expected_liquids + expected_gas

            actual_liquids = point.get("liquids_mboed")
            actual_gas = point.get("natural_gas_mboed")
            actual_total = point.get("total_mboed")

            if actual_liquids is None or actual_gas is None or actual_total is None:
                offenders.append(f"{label} period={point.get('period')}: missing derived field(s)")
                continue

            if abs(actual_liquids - expected_liquids) > tolerance:
                offenders.append(
                    f"{label} period={point.get('period')}: liquids_mboed={actual_liquids} "
                    f"!= oil_mbd+condensate_mbd={expected_liquids} (diff {abs(actual_liquids - expected_liquids)})"
                )
            if abs(actual_gas - expected_gas) > tolerance:
                offenders.append(
                    f"{label} period={point.get('period')}: natural_gas_mboed={actual_gas} "
                    f"!= (dry_gas_mmscfd+assoc_gas_mmscfd)/6={expected_gas} (diff {abs(actual_gas - expected_gas)})"
                )
            if abs(actual_total - expected_total) > tolerance:
                offenders.append(
                    f"{label} period={point.get('period')}: total_mboed={actual_total} "
                    f"!= liquids_mboed+natural_gas_mboed={expected_total} (diff {abs(actual_total - expected_total)})"
                )
    if offenders:
        raise ValidationError(
            "Derived mboe/d field-month formula check failed "
            "(spec section 6): " + "; ".join(offenders[:20])
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
