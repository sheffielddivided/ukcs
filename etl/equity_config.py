"""
Single source of truth for the approved equity publication policy (spec
section 15.11, approved). Both the build (this file, imported by
etl/equity_artifacts.py) and the generated artifacts (equity/meta.json,
which a future frontend reads) derive from these constants - they are
never duplicated in a separate JavaScript file.

Changing any of these values is a methodology decision, not a code
change: it must be reviewed and approved the same way the original
values were (see UKCS_DESIGN_v2.md section 15.11), and the fixture tests
that lock these values in (tests/test_equity_config.py) must be updated
alongside it.
"""

from __future__ import annotations

# Compact 'YYYYMM' period string, matching PPRS's own period format
# (docs/data uses this format throughout - see meta.json's latest_period).
EQUITY_PUBLICATION_START = "201303"

# A stream-month is publishable at all only if resolved coverage is at
# least this percentage of that stream's total reported production for
# that field-month set (spec section 15.11 / 15.5: measured per stream,
# never combined into a boe/d figure).
EQUITY_MINIMUM_COVERAGE_PCT = 95.0

# A published stream-month carries a visible warning if coverage is below
# this (but still >= EQUITY_MINIMUM_COVERAGE_PCT).
EQUITY_WARNING_COVERAGE_PCT = 99.5

# Bumped whenever the interval-resolution or publication policy changes
# in a way that would change previously-published values if re-run.
# Recorded in equity/meta.json so a consumer can tell which policy
# generation produced a given artifact set.
EQUITY_METHODOLOGY_VERSION = "2026.1"

# Documented tolerance for the "normalized row count changes beyond a
# documented tolerance against the previous build" source-integrity check
# (spec section 15.11's validation table). The live workbook grows by a
# handful of rows a week; a change larger than this fraction of the
# previous build's row count is far more likely to be a structural change
# in what NSTA publishes than organic growth, and should fail loudly
# rather than being silently absorbed.
EQUITY_ROW_COUNT_TOLERANCE_FRACTION = 0.10
