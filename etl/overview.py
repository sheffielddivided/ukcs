"""
Production overview compact artifacts (Deliverable 1, spec approved
2026-09-10 continuation). Builds purpose-built, small, deterministic
static artifacts for the new Production view so the browser never loads
all 552 field-history files or all 292 equity company files to render
the default chart.

Grain and scope:
  - monthly_totals: FULL UKCS production history (1975-2026), built from
    etl/transform.py's FieldHistory.full_precision_series (never
    rounded until this module's own single rounding pass at
    serialization) - NOT restricted to the equity publication window,
    since this is native/derived production, not equity-attributable.
  - company_groups / legal_entities: EQUITY-ATTRIBUTABLE series, so
    necessarily restricted to the equity publication window
    (2013-03 onward) - inherited directly from the already-validated
    equity_company_docs / company_group_docs.
  - fields: full-history per-field derived series, for client-side
    Top-N + Other computation.

All four artifacts are built from data structures the rest of build.py
already computed and validated (histories, equity_company_docs,
company_group_docs) - this module performs no new network access and no
new aggregation logic beyond what is documented per function.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from company_groups import (  # noqa: E402
    ALL_STREAMS,
    aggregate_company_series_by_group,
)
from equity_artifacts import build_company_field_artifacts  # noqa: E402
from equity_match import PRODUCTION_STREAMS  # noqa: E402
from equity_mboed import DERIVED_STREAMS  # noqa: E402
from mboed import round_mboed  # noqa: E402


class OverviewError(RuntimeError):
    """Raised on any build-breaking failure in the overview pipeline -
    caught in etl/build.py alongside every other pipeline's own
    exceptions, same 'fail the whole build, write nothing' rule."""


# ---------------------------------------------------------------------------
# Monthly UKCS totals (full history, native/derived production)
# ---------------------------------------------------------------------------


def build_monthly_totals(histories: list) -> list[dict]:
    """Full-history UKCS total liquids_mboed/natural_gas_mboed/total_mboed
    per period, summed across every field's FULL-PRECISION per-period
    derived values (FieldHistory.full_precision_series - never rounded
    until the single round_mboed() pass below), sorted by period.
    Coverage/status is not applicable here - this is native/derived
    production, not equity-attributable, so it is always fully known
    (never "unavailable")."""
    by_period: dict[str, dict[str, float]] = {}
    for h in histories:
        for point in h.full_precision_series:
            period = point["period"]
            totals = by_period.setdefault(period, {k: 0.0 for k in DERIVED_STREAMS})
            for key in DERIVED_STREAMS:
                value = point.get(key)
                if value is not None:
                    totals[key] += value

    series = []
    for period in sorted(by_period.keys()):
        totals = by_period[period]
        series.append(
            {
                "period": period,
                "liquids_mboed": round_mboed(totals["liquids_mboed"]),
                "natural_gas_mboed": round_mboed(totals["natural_gas_mboed"]),
                "total_mboed": round_mboed(totals["total_mboed"]),
            }
        )
    return series


def validate_monthly_totals_reconciliation(series: list[dict], tolerance: float = 0.01) -> None:
    """Build-breaking invariant: for every month, liquids + natural_gas
    == total, recomputed from the artifact's own serialized values. The
    tolerance is the same double-rounding bound already documented and
    empirically verified for etl/validate.py's
    validate_derived_field_month_formula (this is the same formula
    check, applied to the UKCS-total grain instead of field/operator
    grain)."""
    offenders = []
    for point in series:
        liq = point.get("liquids_mboed") or 0.0
        gas = point.get("natural_gas_mboed") or 0.0
        total = point.get("total_mboed")
        expected = liq + gas
        if total is None or abs(total - expected) > tolerance:
            offenders.append(f"period={point.get('period')}: total={total} != liquids+natural_gas={expected}")
    if offenders:
        raise OverviewError(
            "monthly_totals reconciliation failed (liquids + natural_gas != total): "
            + "; ".join(offenders[:20])
        )


# ---------------------------------------------------------------------------
# Company-group overview (equity-attributable, publication-window only)
# ---------------------------------------------------------------------------

UNRESOLVED_BUCKET_NAME = "Unresolved legal entities"


def build_company_groups_overview(
    equity_company_docs: dict[str, dict],
    company_groups_mapping: list[dict],
) -> dict[str, dict]:
    """Compact company-split series: one entry per APPROVED current
    display group, plus exactly ONE aggregated "Unresolved legal
    entities" bucket collapsing every unresolved singleton fallback
    "group" (spec: unmapped/unresolved entities must remain visible and
    must contribute to Total, but 182 individual one-entity series would
    make the company split unusable and is not what a "distinct
    approved group" count should include - see
    company_groups.build_grouping_review_report's distinct_approved_groups
    fix). Built by re-running the SAME tested aggregate_company_series_by_group()
    used for the full per-entity group docs, just with unresolved
    entities' target relabelled to the one shared bucket name - this
    keeps the None-safe-sum/status-combination logic in exactly one
    place, not duplicated."""
    entity_status = {row["source_legal_entity"]: row["status"] for row in company_groups_mapping}
    entity_group = {row["source_legal_entity"]: row["current_display_group"] for row in company_groups_mapping}

    collapsed_entity_to_group = {}
    for entity in equity_company_docs:
        if entity_status.get(entity) == "approved":
            collapsed_entity_to_group[entity] = entity_group.get(entity, entity)
        else:
            collapsed_entity_to_group[entity] = UNRESOLVED_BUCKET_NAME

    return aggregate_company_series_by_group(equity_company_docs, collapsed_entity_to_group)


def validate_company_groups_overview_reconciliation(
    equity_company_docs: dict[str, dict],
    company_groups_overview: dict[str, dict],
    streams: list[str] = ALL_STREAMS,
    tolerance: float = 1e-6,
) -> dict[str, float]:
    """Build-breaking invariant: sum(approved groups) + sum(unresolved
    bucket) == sum(all legal entities), exactly, for every stream - the
    collapsing in build_company_groups_overview() must never drop or
    duplicate a legal entity's production. Same None-safe-sum
    exactness argument as company_groups.validate_group_conservation,
    verified explicitly rather than only trusted by construction."""
    diffs = {}
    offenders = []
    for stream in streams:
        entity_total = sum(
            point[stream]["value"] or 0.0
            for doc in equity_company_docs.values()
            for point in doc["series"]
            if point[stream]["value"] is not None
        )
        overview_total = sum(
            point[stream]["value"] or 0.0
            for doc in company_groups_overview.values()
            for point in doc["series"]
            if point[stream]["value"] is not None
        )
        diff = abs(entity_total - overview_total)
        diffs[stream] = diff
        if diff > tolerance:
            offenders.append(f"{stream!r}: legal-entity total={entity_total}, overview total={overview_total}, diff={diff}")
    if offenders:
        raise OverviewError(
            "Company-groups overview reconciliation failed (approved groups + "
            "unresolved bucket must equal legal-entity total): " + "; ".join(offenders)
        )
    return diffs


# ---------------------------------------------------------------------------
# Company-groups field breakdown (2026-09-10 continuation): lets the
# Production overview's "By company" split show a SINGLE selected
# company group's own production split by field, instead of collapsing
# to one undifferentiated Total bar - the Production overview previously
# had no company<->field attribution at all (company_groups_overview
# above only carries company-level totals; build_fields_overview below
# only carries UNATTRIBUTED field totals - neither says which company
# a field's production belongs to).
# ---------------------------------------------------------------------------


def build_company_groups_field_breakdown_overview(
    resolved_rows: list[dict],
    derived_status_by_period: dict,
    company_groups_mapping: list[dict],
) -> dict[str, dict]:
    """{group_name: {field_name: doc}} - the field-level counterpart of
    build_company_groups_overview, computed the same way (collapsing
    unapproved entities to the one shared UNRESOLVED_BUCKET_NAME) but
    going straight from resolved_rows via build_company_field_artifacts'
    key_fn, rather than re-aggregating an already-built per-entity
    field-breakdown doc - see that function's docstring for why."""
    entity_status = {row["source_legal_entity"]: row["status"] for row in company_groups_mapping}
    entity_group = {row["source_legal_entity"]: row["current_display_group"] for row in company_groups_mapping}

    def group_key(row: dict) -> str:
        entity = row["company_name"]
        if entity_status.get(entity) == "approved":
            return entity_group.get(entity, entity)
        return UNRESOLVED_BUCKET_NAME

    return build_company_field_artifacts(resolved_rows, derived_status_by_period, key_fn=group_key)


def validate_company_field_breakdown_reconciliation(
    company_groups_overview: dict[str, dict],
    company_groups_field_breakdown: dict[str, dict],
    tolerance: float,
) -> float:
    """Build-breaking invariant: for every company group and period,
    summing that group's per-field total_mboed values must reproduce
    that SAME group's own company_groups_overview total_mboed value
    within `tolerance` (None-safe: a group-level None value must never
    coincide with a non-None field-breakdown value for the same period -
    both must equally mean 'unavailable').

    NOT an exact-equality check: each field-period total_mboed and each
    group-period total_mboed was independently rounded once at
    serialization (round_mboed(), 3 decimals) from its own full-precision
    value - summing several independently-3-decimal-rounded field values
    does not, in general, exactly equal a SEPARATELY-rounded group total
    even though both derive from the same underlying full-precision
    numbers (double-rounding). `tolerance` should be the same
    statistically-derived bound `etl/validate.py`'s
    compute_serialization_tolerance() already provides for this exact
    class of comparison (independently-rounded-values-summed vs a
    separately-rounded aggregate) elsewhere in this pipeline - a fixed
    epsilon here would either be too tight (spurious build failures) or
    an arbitrary guess."""
    max_diff = 0.0
    offenders = []
    for group, doc in company_groups_overview.items():
        field_docs = company_groups_field_breakdown.get(group, {})
        field_sum_by_period: dict[str, float] = defaultdict(float)
        field_has_value_by_period: dict[str, bool] = defaultdict(bool)
        for field_doc in field_docs.values():
            for point in field_doc["series"]:
                v = point["total_mboed"]["value"]
                if v is not None:
                    field_sum_by_period[point["period"]] += v
                    field_has_value_by_period[point["period"]] = True

        for point in doc["series"]:
            period = point["period"]
            group_value = point["total_mboed"]["value"]
            if group_value is None:
                if field_has_value_by_period.get(period):
                    offenders.append(f"{group}/{period}: group total is None but field breakdown has a value")
                continue
            field_sum = field_sum_by_period.get(period, 0.0)
            diff = abs(group_value - field_sum)
            max_diff = max(max_diff, diff)
            if diff > tolerance:
                offenders.append(f"{group}/{period}: group total={group_value}, field_sum={field_sum}, diff={diff}")
    if offenders:
        raise OverviewError(
            "Company-groups field breakdown does not reconcile with company-groups "
            "overview: " + "; ".join(offenders[:20])
        )
    return max_diff


# ---------------------------------------------------------------------------
# Legal-entity overview (equity-attributable, publication-window only)
# ---------------------------------------------------------------------------


def build_legal_entities_overview(equity_company_docs: dict[str, dict]) -> dict[str, dict]:
    """One compact entry per legal entity: {slug, name, series:[{period,
    stream: {value, status}}]} - drops coverage_pct and field lists
    (available in the existing per-company detail file for a user who
    drills into one entity) to keep this single combined artifact small
    enough to ship as one file for legal-entity mode."""
    out = {}
    for name, doc in equity_company_docs.items():
        series = []
        for point in doc["series"]:
            entry = {"period": point["period"]}
            for stream in ALL_STREAMS:
                entry[stream] = {"value": point[stream]["value"], "status": point[stream]["status"]}
            series.append(entry)
        out[name] = {"slug": doc["slug"], "name": name, "series": series}
    return out


# ---------------------------------------------------------------------------
# Field overview (full history, native/derived production)
# ---------------------------------------------------------------------------


def build_fields_overview(histories: list) -> dict[str, dict]:
    """One compact entry per field: {slug, name, series:[{period,
    liquids_mboed, natural_gas_mboed, total_mboed}]} for client-side
    Top-N + Other computation - reuses each FieldHistory's ALREADY-
    published, already-rounded `series` (the same values in
    history/{slug}.json) rather than recomputing, so the field-split
    view is guaranteed to reconcile with the existing field detail
    views by construction (same numbers, not independently derived)."""
    out = {}
    for h in histories:
        series = [
            {
                "period": point["period"],
                "liquids_mboed": point.get("liquids_mboed"),
                "natural_gas_mboed": point.get("natural_gas_mboed"),
                "total_mboed": point.get("total_mboed"),
            }
            for point in h.series
        ]
        out[h.slug] = {"slug": h.slug, "name": h.field, "series": series}
    return out


def validate_fields_overview_reconciliation(
    fields_overview: dict[str, dict], monthly_totals: list[dict], tolerance: float
) -> None:
    """Build-breaking invariant: for every period, summing every field's
    total_mboed in fields_overview must equal monthly_totals' total for
    that period - the invariant the client-side "Top N + Other = Total"
    computation depends on (Other is defined client-side as
    Total - sum(displayed fields), which is only a meaningful
    reconciliation if Total truly equals the sum of ALL fields
    server-side first). `tolerance` should be the same
    statistically-derived bound used for the field-vs-operator
    conservation check (etl/validate.py's compute_serialization_tolerance),
    since this is the same class of independently-rounded-values-summed
    comparison."""
    by_period_field_total: dict[str, float] = {}
    for field in fields_overview.values():
        for point in field["series"]:
            period = point["period"]
            by_period_field_total[period] = by_period_field_total.get(period, 0.0) + (point.get("total_mboed") or 0.0)

    by_period_monthly_total = {p["period"]: p["total_mboed"] or 0.0 for p in monthly_totals}

    offenders = []
    for period, field_sum in by_period_field_total.items():
        monthly_total = by_period_monthly_total.get(period)
        if monthly_total is None:
            offenders.append(f"period={period}: no matching monthly_totals entry")
            continue
        diff = abs(field_sum - monthly_total)
        if diff > tolerance:
            offenders.append(f"period={period}: field_sum={field_sum} != monthly_total={monthly_total} (diff={diff})")
    if offenders:
        raise OverviewError(
            "Fields overview does not reconcile with monthly_totals: " + "; ".join(offenders[:20])
        )


# ---------------------------------------------------------------------------
# Overview meta (grouping statistics + provenance)
# ---------------------------------------------------------------------------


def build_overview_meta(
    grouping_report: dict,
    monthly_totals: list[dict],
    equity_publication_start: str,
    build_timestamp: str,
) -> dict:
    """Overview-specific metadata: the reconciled grouping statistics
    (spec review, 2026-09-10) plus the date ranges each split mode
    actually covers, so the frontend can render an accurate caveat when
    switching from the full-history default view into the equity-
    window-restricted company/legal-entity splits."""
    return {
        "built_at": build_timestamp,
        "monthly_totals_earliest_period": monthly_totals[0]["period"] if monthly_totals else None,
        "monthly_totals_latest_period": monthly_totals[-1]["period"] if monthly_totals else None,
        "equity_attributable_earliest_period": equity_publication_start,
        "total_legal_entities": grouping_report["total_legal_entities"],
        "approved_count": grouping_report["approved_count"],
        "reviewed_manual_mapping_count": grouping_report["reviewed_manual_mapping_count"],
        "unresolved_count": grouping_report["unresolved_count"],
        "excluded_count": grouping_report["excluded_count"],
        "distinct_approved_groups": grouping_report["distinct_approved_groups"],
        "unresolved_fallback_count": grouping_report["unresolved_fallback_count"],
        "production_weighted_current_coverage_pct": grouping_report["production_weighted_current_coverage_pct"],
        "latest_period_production_retained_under_unresolved_pct": grouping_report[
            "latest_period_production_retained_under_unresolved_pct"
        ],
    }
