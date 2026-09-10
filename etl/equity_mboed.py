"""
Derived mboe/d streams for the equity pipeline (spec section 17, approved
2026-09-10). Extends the existing per-stream equity coverage model
(equity_publication_window.py's monthly_data / coverage_pct) to the two
derived component streams (liquids, natural gas) and a component-gated
total, WITHOUT averaging percentages and WITHOUT changing the existing
publication-window or interval-resolution policies.

Coverage here is production-weighted (included volume / total volume),
computed at the same (period, aggregate-across-all-companies) grain the
existing four native streams already use - liquids_coverage_pct and
natural_gas_coverage_pct are period-wide properties, identical for every
company in a given period, exactly like oil_mbd's own coverage_pct is
today (see equity_artifacts.py's classify_stream_month). Per-company
VALUES differ; per-period STATUS does not.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from equity_config import EQUITY_MINIMUM_COVERAGE_PCT, EQUITY_WARNING_COVERAGE_PCT  # noqa: E402
from mboed import GAS_MMSCF_PER_MBOE  # noqa: E402

DERIVED_STREAMS = ("liquids_mboed", "natural_gas_mboed", "total_mboed")

# Rounding for coverage percentages - matches equity_publication_window.py's
# coverage_pct() (3 decimal places), not production_config's
# MBOED_ROUND_DECIMALS (which governs the mboe/d VALUES, a separate thing).
COVERAGE_PCT_DECIMALS = 3


def _component_included_total(monthly_data_period: dict, native_streams: tuple[str, str]) -> tuple[float, float]:
    """native_streams e.g. ("oil_mbd", "condensate_mbd") for liquids, or
    ("dry_gas_mmscfd", "assoc_gas_mmscfd") for natural gas. Returns
    (included, total) in the NATIVE unit sum - the mmscf/d-to-mboe/d
    conversion is applied by the caller only where it actually changes a
    reported VALUE; a coverage ratio is scale-invariant to it, so
    natural-gas coverage is computed directly from mmscf/d sums without
    ever converting (dividing both numerator and denominator by the same
    constant leaves the ratio unchanged - converting first would be
    pointless extra floating-point work, not a different answer)."""
    a, b = native_streams
    included = monthly_data_period[a]["resolved"] + monthly_data_period[b]["resolved"]
    total = monthly_data_period[a]["total"] + monthly_data_period[b]["total"]
    return included, total


def classify_component(included: float, total: float) -> dict:
    """One component (liquids or natural gas) at one period, production-
    weighted (included/total), never averaged. Returns
    {"status", "coverage_pct", "value_available"}.

    status is one of "complete" / "warning" / "unavailable" /
    "not_applicable". "not_applicable" is used only when this component's
    TOTAL reported production for the period is genuinely zero (nothing
    to have coverage over) - distinct from "unavailable", which means
    production existed but ownership could not be resolved for enough of
    it. value_available is True only for "complete"/"warning" (a real,
    published, non-zero-in-principle value) - never for "unavailable" or
    "not_applicable", each of which has its own explicit meaning for
    what the *value* should be (see derive_company_period_streams)."""
    if total <= 0:
        return {"status": "not_applicable", "coverage_pct": None, "value_available": False}
    coverage = round(100.0 * included / total, COVERAGE_PCT_DECIMALS)
    if coverage < EQUITY_MINIMUM_COVERAGE_PCT:
        return {"status": "unavailable", "coverage_pct": coverage, "value_available": False}
    status = "complete" if coverage >= EQUITY_WARNING_COVERAGE_PCT else "warning"
    return {"status": status, "coverage_pct": coverage, "value_available": True}


def gate_total_status(liquids_status: str, natural_gas_status: str) -> str:
    """Component gate (spec section 17/4): unavailable if either
    component is unavailable; warning if both are available (i.e.
    complete or warning, never unavailable) but either is warning;
    complete only if both are complete. A "not_applicable" component is
    excluded from the gate entirely and total status is derived from
    whichever component actually has production - never treated as a
    reason to downgrade the total, and never allowed to make a genuinely
    unavailable co-component look better than it is."""
    considered = [s for s in (liquids_status, natural_gas_status) if s != "not_applicable"]
    if not considered:
        return "not_applicable"
    if "unavailable" in considered:
        return "unavailable"
    if "warning" in considered:
        return "warning"
    return "complete"


def classify_period_derived(monthly_data_period: dict) -> dict:
    """monthly_data_period = monthly_data[period] (the existing
    equity_publication_window.build_monthly_stream_data() shape, keyed by
    the four native PRODUCTION_STREAMS). Returns
    {"liquids_mboed": {...}, "natural_gas_mboed": {...}, "total_mboed": {...}}
    in the same {"status", "coverage_pct", "value_available"} shape
    classify_stream_month already uses for the native streams, PLUS a
    "total_coverage_pct" diagnostic field on the total_mboed entry only
    (explanatory metadata - never used to override the component gate,
    per spec section 17/4)."""
    liquids_included, liquids_total = _component_included_total(monthly_data_period, ("oil_mbd", "condensate_mbd"))
    gas_included_mmscfd, gas_total_mmscfd = _component_included_total(
        monthly_data_period, ("dry_gas_mmscfd", "assoc_gas_mmscfd")
    )

    liquids = classify_component(liquids_included, liquids_total)
    natural_gas = classify_component(gas_included_mmscfd, gas_total_mmscfd)

    total_status = gate_total_status(liquids["status"], natural_gas["status"])
    # Diagnostic only (spec: "retain total_coverage_pct as explanatory
    # metadata, but do not use that aggregate percentage to override the
    # component gate") - computed from included/total mboe/d, summed
    # across BOTH components, never averaged.
    total_included_mboed = liquids_included + gas_included_mmscfd / GAS_MMSCF_PER_MBOE
    total_available_mboed = liquids_total + gas_total_mmscfd / GAS_MMSCF_PER_MBOE
    total_coverage_pct = (
        round(100.0 * total_included_mboed / total_available_mboed, COVERAGE_PCT_DECIMALS)
        if total_available_mboed > 0
        else None
    )

    return {
        "liquids_mboed": liquids,
        "natural_gas_mboed": natural_gas,
        "total_mboed": {
            "status": total_status,
            "value_available": total_status in ("complete", "warning"),
            "total_coverage_pct": total_coverage_pct,
        },
    }


def build_derived_status_by_period(monthly_data: dict) -> dict[str, dict]:
    """{period: {"liquids_mboed": {...}, "natural_gas_mboed": {...}, "total_mboed": {...}}}
    for every period in monthly_data - the derived-field analogue of
    equity_artifacts.build_publication_status_by_period_stream()."""
    return {period: classify_period_derived(monthly_data[period]) for period in sorted(monthly_data)}


def derive_company_period_value(
    status_entry: dict,
    included_native_a: float,
    included_native_b: float,
    is_gas: bool,
) -> float | None:
    """The reported VALUE for one company, one derived stream, one period.

    - "unavailable": None (the true value is unknown - could be non-zero,
      but ownership could not be resolved for enough of it; never a
      silent zero).
    - "not_applicable": 0.0 (the true value IS known and IS exactly
      zero - the period's total production for this component was
      genuinely zero, so a zero-share company's zero is not a guess).
    - "complete"/"warning": the company's own included production for
      this component, in mboe/d.
    """
    if status_entry["status"] == "unavailable":
        return None
    if status_entry["status"] == "not_applicable":
        return 0.0
    value = (included_native_a or 0.0) + (included_native_b or 0.0)
    if is_gas:
        value = value / GAS_MMSCF_PER_MBOE
    return value
