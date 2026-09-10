"""
Single source of truth for the approved production-conversion policy
(spec section 17, approved 2026-09-10 - see UKCS_DESIGN_v2.md section 17
and etl/phase3_discovery_report.md section 1 for the discovery and
comparison that preceded this decision).

This is the ONLY place a gas-to-boe numeric constant may be defined
anywhere in this repository - tests/test_no_second_gas_conversion.py
scans the repository (Python and JavaScript) for other such literals and
fails the build if one is found. Both the ETL (etl/mboed.py, imported
from here) and the generated artifacts (meta.json, equity/meta.json,
which the frontend reads) derive from this one constant - it is never
duplicated in a separate JavaScript file, and docs/app/map.js's own
former undocumented constant was removed for exactly this reason (see
UKCS_DESIGN_v2.md section 17).

Changing this value is a methodology decision, not a code change: it
must be reviewed and approved the same way this original value was, and
PRODUCTION_CONVERSION_METHODOLOGY below must be bumped alongside it so a
consumer of an already-published artifact can tell which methodology
generation produced it.
"""

from __future__ import annotations

# Conventional investor-reporting conversion: 6,000 standard cubic feet of
# natural gas = 1 barrel of oil equivalent (boe). This is a conventional
# energy-equivalence factor used for cross-commodity comparability - it is
# not a claim about realised energy content, sales specification,
# entitlement production, revenue equivalence, or measured field-specific
# calorific value (docs/methodology.html states this explicitly). See
# etl/phase3_discovery_report.md section 1 for the comparison against an
# energy-content-sourced alternative that led to this choice.
GAS_SCF_PER_BOE = 6000

# Bumped whenever the conversion factor or derived-value formulas change
# in a way that would change previously-published mboe/d values if
# re-run. Recorded in meta.json and equity/meta.json so a consumer can
# tell which methodology generation produced a given artifact set (same
# pattern as EQUITY_METHODOLOGY_VERSION in etl/equity_config.py).
PRODUCTION_CONVERSION_METHODOLOGY = "mboed-v1-6000-scf-per-boe"

# Derived mboe/d values (liquids_mboed, natural_gas_mboed, total_mboed)
# are rounded to this many decimal places only at serialisation, never
# before combining component streams into a derived value. Matches
# transform.py's existing ROUND_DECIMALS for every native-unit field, so
# derived and native values read at consistent precision throughout every
# artifact - not a separate policy invented for this milestone.
MBOED_ROUND_DECIMALS = 3

# NOTE (Workstream 0 hardening, spec approved 2026-09-10): this module
# previously defined a single flat CONSERVATION_TOLERANCE_MBOED = 5.0 for
# cross-grain (field-vs-operator) conservation of the derived fields. On
# review this was found to risk concealing a dropped field producing
# under ~5 mboe/d. It has been replaced by two narrower,
# mathematically-derived checks in etl/validate.py:
#   - validate_full_precision_conservation() - a tight, floating-point-
#     only tolerance (FLOAT_PRECISION_TOLERANCE_MBOED, also defined in
#     validate.py) applied BEFORE any rounding.
#   - validate_serialized_derived_conservation() - a tolerance computed
#     at build time via compute_serialization_tolerance(), from this
#     build's own real entry counts and the MBOED_ROUND_DECIMALS
#     precision above, rather than a fixed constant.
# See etl/validate.py's docstrings on both functions for the full
# derivation and etl/build.py's call sites for how they're wired in.
