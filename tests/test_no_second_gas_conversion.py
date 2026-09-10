"""
Repository-wide check (spec section 17/7): there must be exactly one
gas-to-boe numeric constant anywhere in this repository -
etl/production_config.py's GAS_SCF_PER_BOE. This scans every committed
Python and JavaScript file for an assignment to an identifier that looks
like a gas/boe conversion constant (SCF/MSCF combined with BOE in the
same name) and fails if one is found anywhere else.

This is exactly the check the discovery report (etl/phase3_discovery_report.md
section 1.1/9) found missing: docs/app/map.js previously carried its own
undocumented GAS_MSCF_PER_BOE (value 5.8), silently inconsistent with the
approved conversion. That constant was removed in favour of reusing the
one published, ETL-derived value (map.js now reads fields.geojson's own
total_mboed/liquids_mboed properties) - this test exists so a similar
constant can never be silently reintroduced, in either language.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

APPROVED_LOCATION = REPO_ROOT / "etl" / "production_config.py"

# Directories never scanned: dependency/build artifacts, generated data,
# git internals, and this project's own committed fixtures/discovery
# report text (which legitimately DISCUSSES conversion factors in prose
# and JSON sample data - "6000" or "5.8" appearing in a markdown report
# or a JSON fixture is not a code-level constant definition).
EXCLUDED_DIR_PARTS = {".git", "__pycache__", "node_modules", ".pytest_cache"}
EXCLUDED_SUFFIXES = {".md", ".json", ".geojson", ".csv", ".xlsx"}

SCANNED_SUFFIXES = {".py", ".js"}

# Matches an assignment to an identifier that combines SCF/MSCF and BOE
# in its name, in either language's assignment syntax (Python `NAME =`,
# JS `const/let/var NAME =`), case-insensitively on the identifier.
CONVERSION_CONSTANT_PATTERN = re.compile(
    r"(?:const|let|var\s+)?\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*[\d.,]+\s*;?",
)


def _looks_like_gas_boe_constant(identifier: str) -> bool:
    upper = identifier.upper()
    has_scf = "SCF" in upper
    has_boe = "BOE" in upper
    return has_scf and has_boe


def _iter_scanned_files():
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in SCANNED_SUFFIXES:
            continue
        if any(part in EXCLUDED_DIR_PARTS for part in path.parts):
            continue
        yield path


# Both Python (#) and JS (//) use the same single-line comment marker
# once JS's // is added - strip everything from the marker to end of
# line before scanning, so a comment that legitimately EXPLAINS or
# references the approved constant's name/value (as many docstrings and
# inline comments in this codebase deliberately do) is never mistaken
# for a second, real code-level definition.
_COMMENT_STRIP_PATTERN = re.compile(r"(#.*$)|(//.*$)", re.MULTILINE)


def _strip_comments(text: str) -> str:
    return _COMMENT_STRIP_PATTERN.sub("", text)


def test_no_second_gas_conversion_constant_in_repository():
    offenders = []
    for path in _iter_scanned_files():
        raw_text = path.read_text(encoding="utf-8", errors="ignore")
        text = _strip_comments(raw_text)
        for match in CONVERSION_CONSTANT_PATTERN.finditer(text):
            identifier = match.group(1)
            if not _looks_like_gas_boe_constant(identifier):
                continue
            if path == APPROVED_LOCATION:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_no}: {identifier}")

    assert offenders == [], (
        "Found a gas-to-boe conversion constant defined outside the one "
        f"approved location ({APPROVED_LOCATION.relative_to(REPO_ROOT)}): "
        + "; ".join(offenders)
    )


def test_approved_location_actually_defines_the_constant():
    """Guards against the scan above passing vacuously (e.g. if the
    approved file were ever renamed without updating this test)."""
    text = APPROVED_LOCATION.read_text(encoding="utf-8")
    assert re.search(r"^GAS_SCF_PER_BOE\s*=\s*\d+", text, re.MULTILINE), (
        f"{APPROVED_LOCATION.relative_to(REPO_ROOT)} does not define "
        "GAS_SCF_PER_BOE as expected - the repository-wide scan test "
        "would be checking against a location that no longer holds the "
        "approved constant."
    )


def test_map_js_no_longer_computes_its_own_boe_conversion():
    """Direct regression guard for the specific historical offender the
    discovery report found (docs/app/map.js's GAS_MSCF_PER_BOE (value 5.8)) -
    belt-and-braces alongside the generic scan above."""
    map_js = (REPO_ROOT / "docs" / "app" / "map.js").read_text(encoding="utf-8")
    assert "GAS_MSCF_PER_BOE" not in map_js
    assert "5.8" not in map_js
