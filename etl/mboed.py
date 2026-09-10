"""
Derived production-conversion formulas (spec section 17, approved
2026-09-10). Single implementation shared by the plain-production
pipeline (transform.py) and the equity pipeline (equity_artifacts.py) -
there is exactly one place these formulas are written, never two.

    liquids_mboed      = oil_mbd + condensate_mbd
    natural_gas_mboed  = (dry_gas_mmscfd + assoc_gas_mmscfd) / (GAS_SCF_PER_BOE / 1000)
    total_mboed        = liquids_mboed + natural_gas_mboed

oil_mbd/condensate_mbd are already thousand-barrels-per-day, numerically
equivalent to mboe/d for this gross-production presentation with no
conversion needed. GAS_SCF_PER_BOE / 1000 = 6.0 with the approved
constant - dividing MMscf/d (millions of scf/d) by this yields mboe/d
(thousands of boe/d) directly, since the two "M"/"m" magnitude
differences (million vs thousand) cancel exactly against the scf-to-Mscf
factor of 1000 baked into GAS_SCF_PER_BOE.

Every function here takes already-available, UNROUNDED numeric inputs
and returns UNROUNDED outputs - callers round exactly once, via
round_mboed(), at the point of serialisation, never before combining
component streams (spec section 2/6: "do not round component streams
before calculating total_mboed").
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from production_config import GAS_SCF_PER_BOE, MBOED_ROUND_DECIMALS  # noqa: E402

# MMscf/d per mboe/d - the single derived divisor used everywhere below.
# 6.0 with the approved GAS_SCF_PER_BOE = 6000. Never hardcode "6" in a
# formula; always go through this (itself derived from the one approved
# constant, never a second literal).
GAS_MMSCF_PER_MBOE = GAS_SCF_PER_BOE / 1000.0


def liquids_mboed(oil_mbd: float | None, condensate_mbd: float | None) -> float:
    """oil_mbd and condensate_mbd are already numerically equivalent to
    mboe/d for this gross-production presentation - a straight sum, no
    conversion factor involved."""
    return (oil_mbd or 0.0) + (condensate_mbd or 0.0)


def natural_gas_mboed(dry_gas_mmscfd: float | None, assoc_gas_mmscfd: float | None) -> float:
    return ((dry_gas_mmscfd or 0.0) + (assoc_gas_mmscfd or 0.0)) / GAS_MMSCF_PER_MBOE


def total_mboed(liquids: float, natural_gas: float) -> float:
    return liquids + natural_gas


def derive_mboed(
    oil_mbd: float | None,
    condensate_mbd: float | None,
    dry_gas_mmscfd: float | None,
    assoc_gas_mmscfd: float | None,
) -> dict[str, float]:
    """Computes all three derived values from native-unit components in a
    single, unrounded pass. Returns unrounded floats - round via
    round_mboed() at serialisation, not before."""
    liq = liquids_mboed(oil_mbd, condensate_mbd)
    gas = natural_gas_mboed(dry_gas_mmscfd, assoc_gas_mmscfd)
    return {
        "liquids_mboed": liq,
        "natural_gas_mboed": gas,
        "total_mboed": total_mboed(liq, gas),
    }


def round_mboed(value: float | None) -> float | None:
    """Same rounding discipline as transform.py's round3(): fixed
    precision, -0.0 collapsed to 0.0 so a repeated build of unchanged
    input never toggles a value's sign representation in the committed
    JSON."""
    if value is None:
        return None
    rounded = round(float(value), MBOED_ROUND_DECIMALS)
    if rounded == 0:
        rounded = 0.0
    return rounded
