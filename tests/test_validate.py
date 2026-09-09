"""
Committed regression tests for etl/validate.py (spec section 8.3 / 14).

These lock in two behaviors that were previously verified only by live,
one-off monkeypatch runs against the real ArcGIS service during the
Phase 1 closeout audit (see the audit report): schema drift causing a
non-zero exit, and the storage/injection tripwire firing on an
unclassified storage-like reporting unit. Both scenarios here are the
EXACT scenarios used in that live audit, reproduced as fast, deterministic,
network-free unit tests so the behavior is protected against regression,
not just demonstrated once in a chat transcript.

No network access, no live ArcGIS calls - these test validate.py's pure
functions directly with synthetic data shaped like real PPRS rows/schema.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.validate import (  # noqa: E402
    EXPECTED_FIELDS,
    ValidationError,
    find_unclassified_storage_like_units,
    validate_schema,
    validate_unit_classification_tripwire,
)


def _live_schema_fields() -> list[dict]:
    """A schema shaped exactly like the live PPRS layer's `fields` array
    (name/type only - alias omitted, validate_schema doesn't use it),
    built from EXPECTED_FIELDS itself so this fixture can never drift out
    of sync with what validate_schema actually checks."""
    return [{"name": name, "type": type_} for name, type_ in EXPECTED_FIELDS.items()]


# --- A. Schema drift ---
# Reproduces the exact audit scenario: PERIODYRMN's type corrupted from
# esriFieldTypeString to esriFieldTypeInteger after a real fetch.


def test_schema_drift_on_periodyrmn_type_change_fails_validation():
    fields = _live_schema_fields()
    for f in fields:
        if f["name"] == "PERIODYRMN":
            f["type"] = "esriFieldTypeInteger"

    try:
        validate_schema(fields)
        assert False, "validate_schema() must raise on a type change, but did not"
    except ValidationError as e:
        message = str(e)
        assert "PERIODYRMN" in message, (
            f"error must name the offending field 'PERIODYRMN', got: {message}"
        )
        assert "esriFieldTypeString" in message and "esriFieldTypeInteger" in message, (
            f"error must name both the expected and actual type, got: {message}"
        )
        # TEMPORARY, deliberately false assertion - proves CI goes red on
        # a real test failure. This branch is never merged to main.
        assert 1 == 2, "deliberate CI-red demonstration for the Phase 1 closeout audit"


def test_schema_drift_on_missing_field_fails_validation():
    fields = [f for f in _live_schema_fields() if f["name"] != "FIELDNAME"]

    try:
        validate_schema(fields)
        assert False, "validate_schema() must raise when an expected field is missing"
    except ValidationError as e:
        assert "FIELDNAME" in str(e)


def test_unchanged_live_schema_passes_validation():
    """Negative control: the exact live schema shape must NOT raise -
    otherwise the two tests above could be passing for the wrong reason
    (e.g. validate_schema always raising)."""
    validate_schema(_live_schema_fields())  # must not raise


def test_validation_error_is_caught_by_build_main_except_clause():
    """Locks in the failure PATH, not just the exception being raised:
    build.py's main() must catch ValidationError (which validate_schema
    and validate_unit_classification_tripwire raise) in the same except
    clause as its other build-fatal error types, guaranteeing a
    ValidationError produces a clean non-zero exit rather than an
    uncaught traceback. Checked by inspecting build.main()'s actual source
    rather than invoking it, since main() itself makes live network calls
    that must not run inside the test suite."""
    # etl/build.py inserts its own directory onto sys.path on import (see
    # its own docstring), which is what lets its internal sibling imports
    # (`from arcgis import ...` etc.) resolve here too.
    from etl import build

    source = inspect.getsource(build.main)
    except_lines = [line for line in source.splitlines() if line.strip().startswith("except")]
    assert except_lines, "build.main() has no except clause at all"
    assert any("ValidationError" in line for line in except_lines), (
        "ValidationError is not caught by build.main() - a validation "
        "failure would crash with an uncaught traceback instead of a "
        "clean non-zero exit"
    )


# --- B. Storage tripwire ---
# Reproduces the exact audit scenario: unit_classification.csv emptied,
# so ROUGH STORAGE (a real, known storage unit) is unclassified.


def _row(field: str, unit: str) -> dict:
    return {"attributes": {"FIELDNAME": field, "UNITNAME": unit, "PERIODYRMN": "202606"}}


def test_tripwire_fires_on_unclassified_rough_storage():
    rows = [
        _row("ROUGH", "ROUGH PRODUCTION"),
        _row("ROUGH", "ROUGH STORAGE"),
    ]
    empty_classification_map: dict[tuple[str, str], str] = {}  # simulates the emptied CSV

    try:
        validate_unit_classification_tripwire(rows, empty_classification_map)
        assert False, "tripwire must fire on an unclassified storage-like unit"
    except ValidationError as e:
        message = str(e)
        assert "ROUGH/ROUGH STORAGE" in message, (
            f"error must name the exact (field, unit) pair, got: {message}"
        )
        # ROUGH PRODUCTION must NOT be named - only the storage-like unit
        # should trip the wire, not every unit in the same field.
        assert "ROUGH/ROUGH PRODUCTION" not in message


def test_tripwire_path_is_exercised_not_generic_validation():
    """Confirms this is specifically the TRIPWIRE detector firing, not
    some other validation rule coincidentally also failing on this input:
    find_unclassified_storage_like_units() (the tripwire's own detection
    function) must itself report exactly the offending pair."""
    rows = [_row("ROUGH", "ROUGH STORAGE")]
    flagged = find_unclassified_storage_like_units(rows, {})
    assert flagged == [("ROUGH", "ROUGH STORAGE")]


def test_tripwire_does_not_fire_when_unit_is_classified():
    """Negative control: a storage-like unit that IS present in
    unit_classification.csv (represented here by the classification map)
    must not trip the wire - this is the exceptions-only design (spec
    7.3), not a blanket ban on the word STORAGE."""
    rows = [_row("ROUGH", "ROUGH STORAGE")]
    classification_map = {("ROUGH", "ROUGH STORAGE"): "storage"}
    validate_unit_classification_tripwire(rows, classification_map)  # must not raise


def test_tripwire_does_not_fire_on_ordinary_unclassified_unit():
    """Negative control: an ordinary new unit with no suspicious token
    must default to production silently (spec 7.3: exceptions-only, a
    routine new field/unit must never turn the build red)."""
    rows = [_row("BUZZARD", "BUZZARD")]
    validate_unit_classification_tripwire(rows, {})  # must not raise


def test_tripwire_fires_on_injection_token_too():
    """The tripwire's second token (INJECTION) fires the same way -
    reproduces the HATFIELD MOOR GAS STORAGE INJECTION case from the live
    unit_classification.csv, minus the word STORAGE, to confirm both
    tokens are live, not just STORAGE."""
    rows = [_row("HATFIELD", "SOME GAS INJECTION POINT")]
    try:
        validate_unit_classification_tripwire(rows, {})
        assert False, "tripwire must fire on the INJECTION token too"
    except ValidationError as e:
        assert "HATFIELD/SOME GAS INJECTION POINT" in str(e)
