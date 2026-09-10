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

# Explicit tolerance for cross-grain conservation checks (field-to-
# operator, field-to-company) on the DERIVED fields specifically.
#
# This is deliberately looser than validate.py's native-field tolerance
# (0.01) - NOT because the derived model is less strict, but because it
# has a genuinely different, larger noise source. The native fields
# (oil_mbd, dry_gas_mmscfd, etc.) are conserved by plain summation, which
# empirically loses no precision (source values already fall on exact
# 3-decimal boundaries, so round3(a)+round3(b) == round3(a+b) almost
# always; observed field-vs-operator diff over the full 1975-2026 history
# is ~1e-8, pure floating-point noise). natural_gas_mboed instead divides
# by 6 before rounding, which IS a genuine, unavoidable information loss
# at every rounding point - and the two grains round at very different
# points: once per field-period (~134,000 independent roundings across
# the full history) versus once per operator-period (roughly two orders
# of magnitude fewer). Each of those two independent sets of roundings is
# a small random walk of up to +/-0.0005 mboe/d per step; verified against
# a real full-history build, the accumulated field-vs-operator difference
# reached ~0.21 for natural_gas_mboed and ~0.53 for total_mboed (which
# inherits both components' noise). This tolerance is set with roughly an
# order of magnitude of headroom over that observed worst case, while
# staying many orders of magnitude tighter than what an actual aggregation
# bug (a whole field silently dropped or double-counted, which would move
# a cumulative multi-decade total by thousands of mboe/d-months) would
# produce - so it remains a meaningful check, not a rubber stamp.
CONSERVATION_TOLERANCE_MBOED = 5.0
