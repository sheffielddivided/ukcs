"""
Phase 2 publication-window and coverage-policy decision checkpoint
(diagnostic only - not spec section 15.8 step 6/7, no build.py
integration, no docs/data/equity/*, no UI, no company aliases, no
equity-attributable production published).

Builds on etl/equity_join_historical.py's full-history resolution to
answer one question: given that full-history coverage is known to be
structurally incomplete before the 2000s (see UKCS_DESIGN_v2.md section
15.10), what is the earliest defensible month to start publishing
equity-attributable production, and under what coverage rules?

This module does not decide the policy - it computes the evidence
(candidate-window statistics, stability thresholds, breach causes) that a
human reviewer needs to decide it, and drafts (but does not create) the
methodology text that would accompany publication.

Run: python etl/equity_publication_window.py
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.equity_join_historical import run_historical_join
from etl.equity_match import PRODUCTION_STREAMS

PUBLICATION_REPORT_PATH = Path(__file__).parent / "equity_publication_window_report.md"

CANDIDATE_START_PERIODS = ["200001", "200501", "200701", "200901", "201001", "201201", "201501"]
STABILITY_THRESHOLDS = [95.0, 99.0, 99.5]
COVERAGE_WARNING_THRESHOLD = 99.5
COVERAGE_PUBLICATION_THRESHOLD = 95.0


# ---------------------------------------------------------------------------
# Monthly, per-stream, per-category production data
# ---------------------------------------------------------------------------


def build_monthly_stream_data(per_field_month: dict) -> dict[str, dict]:
    """Returns {period: {stream: {"total": x, "resolved": y, "by_category": {cat: prod}}}}."""
    data: dict[str, dict] = defaultdict(lambda: {s: {"total": 0.0, "resolved": 0.0, "by_category": defaultdict(float)} for s in PRODUCTION_STREAMS})
    for (field, period), entry in per_field_month.items():
        prod = entry["production"]
        category = entry["category"]
        for stream in PRODUCTION_STREAMS:
            data[period][stream]["total"] += prod[stream]
            if category == "resolved":
                data[period][stream]["resolved"] += prod[stream]
            else:
                data[period][stream]["by_category"][category] += prod[stream]
    return dict(sorted(data.items()))


def coverage_pct(period_data: dict) -> float | None:
    total = period_data["total"]
    if total <= 0:
        return None
    return round(100.0 * period_data["resolved"] / total, 3)


# ---------------------------------------------------------------------------
# 1. Candidate publication windows
# ---------------------------------------------------------------------------


def candidate_window_stats(monthly_data: dict, start_period: str) -> dict:
    periods = sorted(p for p in monthly_data if p >= start_period)
    result = {}
    for stream in PRODUCTION_STREAMS:
        monthly_coverage = [(p, coverage_pct(monthly_data[p][stream])) for p in periods]
        monthly_coverage = [(p, c) for p, c in monthly_coverage if c is not None]
        if not monthly_coverage:
            result[stream] = None
            continue

        total = sum(monthly_data[p][stream]["total"] for p in periods)
        resolved = sum(monthly_data[p][stream]["resolved"] for p in periods)
        overall_coverage = round(100.0 * resolved / total, 3) if total > 0 else None

        values = sorted(c for p, c in monthly_coverage)
        n = len(values)
        median = values[n // 2] if n % 2 == 1 else round((values[n // 2 - 1] + values[n // 2]) / 2, 3)

        buckets = {
            "at_100": sum(1 for p, c in monthly_coverage if c >= 100.0),
            "99.5_to_100": sum(1 for p, c in monthly_coverage if 99.5 <= c < 100.0),
            "95_to_99.5": sum(1 for p, c in monthly_coverage if 95.0 <= c < 99.5),
            "below_95": sum(1 for p, c in monthly_coverage if c < 95.0),
        }

        longest_run = 0
        current_run = 0
        for p, c in monthly_coverage:
            if c < 95.0:
                current_run += 1
                longest_run = max(longest_run, current_run)
            else:
                current_run = 0

        excluded_by_category = defaultdict(float)
        for p in periods:
            for cat, val in monthly_data[p][stream]["by_category"].items():
                excluded_by_category[cat] += val

        result[stream] = {
            "overall_coverage_pct": overall_coverage,
            "lowest_monthly_coverage": min(values),
            "median_monthly_coverage": median,
            "buckets": buckets,
            "longest_consecutive_run_below_95": longest_run,
            "excluded_production_by_category": {k: round(v, 4) for k, v in excluded_by_category.items()},
            "month_count": len(monthly_coverage),
        }
    return result


# ---------------------------------------------------------------------------
# 2. Stability thresholds
# ---------------------------------------------------------------------------


def stability_threshold(monthly_data: dict, stream: str, threshold: float) -> str | None:
    """First period after which coverage for `stream` never again falls
    below `threshold`. Returns None if no such period exists (i.e. even
    the most recent period is below threshold, or a later violation always
    exists)."""
    periods = sorted(monthly_data.keys())
    series = [(p, coverage_pct(monthly_data[p][stream])) for p in periods]
    series = [(p, c) for p, c in series if c is not None]
    if not series:
        return None

    last_violation_index = None
    for i, (p, c) in enumerate(series):
        if c < threshold:
            last_violation_index = i

    if last_violation_index is None:
        return series[0][0]  # never violates at all
    if last_violation_index == len(series) - 1:
        return None  # violates even in the most recent period
    return series[last_violation_index + 1][0]


def breach_cause_analysis(monthly_data: dict, stream: str, threshold: float) -> dict:
    """For every month below `threshold`, identifies the dominant excluded
    category (by production volume) - i.e. what is actually causing the
    shortfall, not just that a shortfall exists."""
    dominant_cause_counts: dict[str, int] = defaultdict(int)
    for period, streams in monthly_data.items():
        c = coverage_pct(streams[stream])
        if c is None or c >= threshold:
            continue
        by_cat = streams[stream]["by_category"]
        if not by_cat:
            dominant_cause_counts["unexplained"] += 1
            continue
        dominant = max(by_cat.items(), key=lambda kv: kv[1])[0]
        dominant_cause_counts[dominant] += 1
    return dict(sorted(dominant_cause_counts.items(), key=lambda kv: -kv[1]))


# ---------------------------------------------------------------------------
# 3/4. Candidate policy assessment (structured for the report; the actual
# recommendation text is prose, written directly into build_report)
# ---------------------------------------------------------------------------

POLICY_ASSESSMENTS = {
    "A": {
        "name": "Fixed start date",
        "comparability": "High - every published month has the same coverage floor, so period-over-period comparison is safe by construction.",
        "risk_of_misleading": "Low, provided the start date is chosen from persistent (not one-off) coverage.",
        "implementation_complexity": "Low - a single constant date gate in the build.",
        "transparency": "Moderate - excludes data outright rather than showing it with a caveat; must be documented prominently so 'no data before X' is not read as 'no production before X'.",
        "suitability_for_ir": "High - investor-relations users need a stable, comparable series more than they need every available data point.",
    },
    "B": {
        "name": "Dynamic coverage threshold",
        "comparability": "Low - a stream could gain or lose months as coverage crosses 95% in either direction between builds if the underlying source data changes, silently changing which periods are comparable.",
        "risk_of_misleading": "High - a user comparing two builds could see a formerly-published month disappear, or a previously-missing month reappear, with no visible reason.",
        "implementation_complexity": "Moderate - needs per-month, per-stream gating logic and a way to signal 'this month exists in principle but coverage dropped below the bar'.",
        "suitability_for_ir": "Low - instability in what is published is the opposite of what an investor-relations audience needs.",
    },
    "C": {
        "name": "Publish all periods with coverage warnings",
        "comparability": "Very low for early periods - showing coverage_pct honestly does not fix the fact that 0-10% coverage in the 1970s-1990s is not a usable equity-attributable production series, only a labelled unusable one.",
        "risk_of_misleading": "High despite the labelling - a chart that visually shows a full multi-decade series, with a small coverage indicator, invites exactly the kind of quick misread this project exists to avoid. Technical transparency (coverage_pct is present) does not equal analytical usability.",
        "implementation_complexity": "Low - no gating logic needed.",
        "suitability_for_ir": "Low, for the same reason - an investor-relations user skimming a chart will see a full historical series and reasonably assume it means something, coverage caveat or not.",
    },
    "D": {
        "name": "Hybrid: fixed start date + monthly coverage + warning threshold",
        "comparability": "High within the published window (same floor as Policy A), plus a finer-grained warning signal for the (rare, within-window) months that dip between 95% and 99.5%.",
        "risk_of_misleading": "Low - the published window is stable and gated, and the warning threshold catches genuine within-window softness (e.g. a field temporarily quarantined) without hiding it or excluding the whole month.",
        "implementation_complexity": "Moderate - both a fixed gate and a per-month warning need implementing, but each is simple on its own.",
        "suitability_for_ir": "High - combines a stable, comparable series with visible, month-level honesty about residual imperfection inside that series.",
    },
}


# ---------------------------------------------------------------------------
# 5. MURLACH deep-dive
# ---------------------------------------------------------------------------


def murlach_deep_dive(pprs_history: dict, raw_rows: list[dict]) -> dict:
    field = "MURLACH [pt of MARNOCK-SKUA]"
    pprs_records = pprs_history.get(field, [])
    equity_rows_for_field = [r for r in raw_rows if r["field_name"] == field]
    related_rows = [r for r in raw_rows if any(token in r["field_name"] for token in ("MURLACH", "MARNOCK", "SKUA"))]

    return {
        "pprs_production_records": [
            {"period": p["period"], "oil_mbd": p["oil_mbd"], "dry_gas_mmscfd": p["dry_gas_mmscfd"], "assoc_gas_mmscfd": p["assoc_gas_mmscfd"], "condensate_mbd": p["condensate_mbd"]}
            for p in pprs_records
        ],
        "murlach_equity_rows": [
            {"company": r["company_name"], "start": r["start_date"], "end": r["end_date"], "pct": r["interest_pct"], "status": r["status"], "operator_flag": r["operator_flag"], "period_label": r["period_label"]}
            for r in equity_rows_for_field
        ],
        "all_related_rows_murlach_marnock_skua": [
            {"field": r["field_name"], "company": r["company_name"], "start": r["start_date"], "end": r["end_date"], "pct": r["interest_pct"], "status": r["status"], "operator_flag": r["operator_flag"]}
            for r in sorted(related_rows, key=lambda r: (r["field_name"], r["start_date"]))
        ],
    }


# ---------------------------------------------------------------------------
# 6. Pre-2000 source inventory (populated by hand from WebSearch findings -
# see the diagnostic report's "how this inventory was produced" note; this
# constant is data, not a live lookup, since no source is ingested here)
# ---------------------------------------------------------------------------

PRE_2000_SOURCE_INVENTORY = [
    {
        "name": "NSTA/OGA \"Field Partners\" workbook itself (this project's current source)",
        "publisher": "North Sea Transition Authority",
        "period_covered": "Earliest observed row: 1968-08-01, but per-field coverage is sparse before ~2000 (see section 15.10)",
        "grain": "Field-level, dated intervals with percentage and effective dates",
        "has_pct_and_dates": True,
        "format": "Excel (.xlsx)",
        "licence_reuse_terms": "NSTA User Agreement (June 2023) - see ATTRIBUTION.md; same basis already used for this project's other NSTA data",
        "could_improve_pre_2000_coverage": "No - this IS the source with the coverage gap. Re-checking it does not add data it does not have.",
    },
    {
        "name": "NSTA Licences / Licence Blocks / Sub Areas (PEARS-derived)",
        "publisher": "North Sea Transition Authority",
        "period_covered": "Offshore licensing back to the 1960s-70s (exact per-licence start dates vary)",
        "grain": "Licence-level (who holds which licence/block), not field-level production-equity percentage",
        "has_pct_and_dates": False,
        "format": "GIS layers / data.gov.uk downloads",
        "licence_reuse_terms": "Government/NSTA open data terms (not independently re-verified in this checkpoint)",
        "could_improve_pre_2000_coverage": (
            "No, for this project's purpose. This is the same 'licence blocks history' dataset "
            "already identified in spec section 15.1 as a company-name-history source, not an "
            "equity-interest source: it records licensee-of-record, not what share of a field's "
            "reported production a company is entitled to. Confirmed by web search (see queries "
            "below), not merely assumed from the spec."
        ),
    },
    {
        "name": "\"Field Data\" GOV.UK page (withdrawn)",
        "publisher": "gov.uk / DECC-predecessor department",
        "period_covered": "Referenced 'offshore field consents since 1976' in search result summary; page itself is withdrawn/archived",
        "grain": "Unclear at time of search - page is withdrawn and was not fetched in full (out of scope: this checkpoint catalogues sources, it does not ingest them)",
        "has_pct_and_dates": "Unknown - not verifiable without fetching the withdrawn page's archived content, which was not done here",
        "format": "Unknown",
        "licence_reuse_terms": "Unknown",
        "could_improve_pre_2000_coverage": (
            "Possibly, but unverified - this is the one lead from the search that is not clearly "
            "ruled out. If pursued, it should be checked for field-level percentage-and-date "
            "structure before being treated as usable, per the same standard applied to the current "
            "source in milestone 1."
        ),
    },
]

PRE_2000_SOURCE_INVENTORY_QUERIES = [
    'NSTA OGA "field equity" OR "field partners" historical archive UKCS pre-2000 percentage ownership dataset',
    'NSTA "licensee" OR "licence" history offshore petroleum blocks dataset dated interest percentage 1970s 1980s 1990s',
]

PRE_2000_SOURCE_INVENTORY_NOT_FOUND_NOTE = (
    "A bounded web search (two queries, listed below) did not surface a distinct, citable, "
    "field-level dated-equity dataset from NSTA/OGA or another regulator covering the pre-2000 "
    "UKCS period at the percentage-and-effective-date grain this project needs. What exists "
    "publicly and was found is mostly licence-level (who holds which licence, not what percentage "
    "of a field's production they are entitled to) or the current 'Field Partners' workbook itself "
    "- the source with the known gap. One unverified lead (a withdrawn GOV.UK 'field data' page "
    "referencing 'offshore field consents since 1976') was found and is listed but not pursued "
    "further, since fetching and assessing it is ingestion-adjacent work this checkpoint is scoped "
    "not to do. Per the explicit instruction for this checkpoint, no narrative or company-history "
    "material is treated as a usable source here, however specific it sounds, and general web "
    "search was not used to reconstruct actual historical equity figures - only to catalogue what "
    "citable datasets exist."
)


# ---------------------------------------------------------------------------
# 7. Methodology text (draft only - not written to methodology.html)
# ---------------------------------------------------------------------------

DRAFT_METHODOLOGY_TEXT = """\
## Equity-attributable production - methodology (DRAFT, not yet published)

**Source.** Equity-attributable production is calculated from the NSTA dataset whose ArcGIS item
is titled "Field Partners". The NSTA Fields data theme page describes this same dataset as
"Current and historical field equity shares". Both names are recorded as provenance; the item
title is a publisher naming choice, not a description of the data's temporal scope, and the
workbook's actual content - dated ownership intervals back to the late 1960s - has been verified
directly rather than assumed from either name.

**Interval resolution.** Ownership is resolved once per calendar month, at the first day of the
month ("month-start"), using half-open intervals: an interest is active for a given month if
`start_date <= month_start < end_date`. An open (blank) end date means the interest is still
current. This is a deliberate simplification - ownership changing mid-month is attributed entirely
to whichever interest was in force on day 1 of that month, never prorated.

**Zero-duration rows.** A small but non-trivial share of source rows record an identical start and
end date. These are retained as source records but are never treated as an active ownership
interval for any month - mathematically, a zero-duration interval cannot satisfy the half-open
test above for any month-start.

**Zero-interest rows.** Some source rows record a company's involvement in a field with a recorded
interest of 0%. These are retained as source records but contribute no equity-attributable
production, since production multiplied by a 0% share is 0 regardless of the row's other
attributes.

**Operator status.** The source separately records which company operates a field. Operator status
does not imply a positive economic interest - in fact a substantial share of 0%-interest rows
belong to the recorded operator. Operator status is never used as a proxy for ownership.

**Unresolved field-months.** Where a field's ownership records for a given month cannot be
resolved cleanly - most commonly because two records genuinely overlap and together claim more
than 100% of the field - that field-month is excluded from the calculation entirely, not repaired,
normalised back to 100%, or resolved by preferring one recorded owner over another. This is
reported, not silently absorbed into the total.

**Coverage.** Coverage is measured and shown separately for each production stream (oil, dry gas,
associated gas, condensate) as the share of that stream's total reported field production for
which ownership was cleanly resolved that month. Streams are never combined into a single boe/d
figure for this purpose.

**Publication window.** Equity ownership records are not evenly available across the production
history this site otherwise covers back to 1975. Coverage in earlier years is materially
incomplete - the underlying NSTA equity dataset was not populated retroactively to most fields'
actual production start dates. Equity-attributable production is therefore published only from
[PUBLICATION START DATE - pending review, see etl/equity_publication_window_report.md], the
earliest month for which coverage has been verified to be consistently high, not merely high in
one good year. Coverage for every published month is shown alongside the figure it belongs to.

**What this figure is not.** Equity-attributable production is a gross equity share of reported
field production - the field's reported volume multiplied by each company's recorded ownership
percentage for that month. It is not net production, not working-interest production, and not
entitlement production: it carries no adjustment for royalty, tax, or any other entitlement
mechanism. It should not be read as a substitute for those figures.
"""


def build_report(per_field_month, pprs_history, raw_rows, result) -> str:
    monthly_data = build_monthly_stream_data(per_field_month)

    lines = [
        "# Equity publication-window and coverage-policy decision checkpoint",
        "",
        "Diagnostic checkpoint only. No build.py integration, no docs/data/equity artifacts, no UI "
        "changes, no company aliases, no equity-attributable production published. This report "
        "computes evidence for a human decision; it does not make the decision.",
        "",
        "## 1. Candidate publication window comparison",
        "",
    ]
    for start in CANDIDATE_START_PERIODS:
        stats = candidate_window_stats(monthly_data, start)
        lines.append(f"### Window starting {start}")
        lines.append("")
        lines.append("| Stream | Overall coverage | Lowest month | Median month | At 100% | 99.5-100% | 95-99.5% | Below 95% | Longest run <95% | Months |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for stream in PRODUCTION_STREAMS:
            s = stats[stream]
            if s is None:
                lines.append(f"| {stream} | (no data) | | | | | | | | |")
                continue
            b = s["buckets"]
            lines.append(
                f"| {stream} | {s['overall_coverage_pct']}% | {s['lowest_monthly_coverage']}% | {s['median_monthly_coverage']}% | "
                f"{b['at_100']} | {b['99.5_to_100']} | {b['95_to_99.5']} | {b['below_95']} | {s['longest_consecutive_run_below_95']} | {s['month_count']} |"
            )
        lines.append("")
        for stream in PRODUCTION_STREAMS:
            s = stats[stream]
            if s:
                lines.append(f"- {stream} excluded production by category: {s['excluded_production_by_category']}")
        lines.append("")

    lines += [
        "## 2. Stability thresholds by stream",
        "",
        "First month after which coverage never again falls below the threshold (None = no such "
        "month exists in the observed data):",
        "",
        "| Stream | Never below 95% from... | Never below 99% from... | Never below 99.5% from... |",
        "| --- | --- | --- | --- |",
    ]
    for stream in PRODUCTION_STREAMS:
        thresholds = {t: stability_threshold(monthly_data, stream, t) for t in STABILITY_THRESHOLDS}
        lines.append(f"| {stream} | {thresholds[95.0]} | {thresholds[99.0]} | {thresholds[99.5]} |")

    lines += [
        "",
        "### Breach cause analysis (dominant excluded category per below-threshold month)",
        "",
    ]
    for stream in PRODUCTION_STREAMS:
        causes_95 = breach_cause_analysis(monthly_data, stream, 95.0)
        lines.append(f"- {stream} (months below 95%): {causes_95}")
    lines.append("")
    lines.append(
        "Across every stream, `pre_equity_history` dominates almost every below-threshold month "
        "before the 2000s (see UKCS_DESIGN_v2.md section 15.10) - low coverage is caused by the "
        "source genuinely lacking equity records for that era, not by unmatched fields, boundary "
        "effects, future-only equity, or quarantined overlaps, all of which are minor contributors "
        "by comparison."
    )
    lines.append("")

    lines += [
        "## 3. Candidate publication policy assessment",
        "",
    ]
    for key, a in POLICY_ASSESSMENTS.items():
        lines.append(f"### Policy {key}: {a['name']}")
        lines.append("")
        lines.append(f"- Comparability across time: {a['comparability']}")
        lines.append(f"- Risk of misleading users: {a['risk_of_misleading']}")
        lines.append(f"- Implementation complexity: {a['implementation_complexity']}")
        lines.append(f"- Transparency: {a.get('transparency', 'n/a')}")
        lines.append(f"- Suitability for investor-relations analysis: {a['suitability_for_ir']}")
        lines.append("")
    lines += [
        "**Recommendation: Policy D (hybrid).** Policy B is rejected outright - an unstable "
        "publication set (months appearing/disappearing as coverage crosses a threshold between "
        "builds) is close to the worst possible failure mode for an audience that needs to compare "
        "periods reliably. Policy C is rejected for the reason the brief specifically warns "
        "against: a coverage_pct label does not make a 0-10%-covered decade analytically usable, "
        "and presenting a full multi-decade series invites exactly the kind of quick, wrong read "
        "this project exists to avoid. Policy A is a reasonable floor but discards useful "
        "information about softness *within* the published window. Policy D keeps A's stability "
        "guarantee and adds C's transparency where it is actually informative - inside a window "
        "already known to be reliable.",
        "",
        "## 4. Proposed publication threshold",
        "",
        f"- Publication threshold: **{COVERAGE_PUBLICATION_THRESHOLD}%** (a month within the "
        "published window is included if its stream coverage is at least this)",
        f"- Warning threshold: **{COVERAGE_WARNING_THRESHOLD}%** (a visible warning is shown for "
        "any published month whose stream coverage falls below this, without excluding it)",
        "- Applied **separately by production stream, at field-month resolution, before stream "
        "aggregation**: a field-month is either fully resolved or excluded (quarantined/unresolved "
        "categories are never partially counted - see etl/equity_join_historical.py's E5 "
        "categories), and stream-level coverage_pct is the aggregate of those binary field-month "
        "outcomes for that stream and month. The alternative - a single combined threshold across "
        "all four streams - would hide a stream-specific problem (e.g. a field with resolved oil "
        "but quarantined gas) behind an averaged number, which section 15.5 and the milestone-2/3 "
        "work already established this project should not do.",
        "",
        "Fixed start date: **left for your review below (section 6/'Recommended publication start' "
        "of the accompanying answer) - see the stability-threshold table in section 2 above. This "
        "report does not assert a specific month as approved.**",
        "",
        "## 5. MURLACH [pt of MARNOCK-SKUA] source review",
        "",
    ]
    murlach = murlach_deep_dive(pprs_history, raw_rows)
    lines.append("### All PPRS production records")
    lines.append("")
    lines.append(f"{murlach['pprs_production_records']}")
    lines.append("")
    lines.append("### All Field Partners equity rows for MURLACH")
    lines.append("")
    lines.append(f"{murlach['murlach_equity_rows']}")
    lines.append("")
    lines.append("### All rows containing MURLACH, MARNOCK or SKUA in the field name")
    lines.append("")
    for r in murlach["all_related_rows_murlach_marnock_skua"]:
        lines.append(f"- {r}")
    lines += [
        "",
        "**Finding**: MURLACH's own equity rows (both partners, BP 80% / NEO ENERGY 20%) share an "
        "identical start date, 2050-01-04, with no preceding record of any kind for MURLACH under "
        "that name. The related `MARNOCK [pt. of MARNOCK-SKUA]` rows are a **separate field entry** "
        "in the source with its own distinct company/interest/date history, not a parent record "
        "MURLACH derives from - the source provides no explicit relationship (no shared row, no "
        "cross-reference field, no note) linking MURLACH's ownership to MARNOCK's. `SKUA [pt. of "
        "MARNOCK-SKUA]` (the third PPRS sub-unit of this group) has no equity rows under any name "
        "at all - not even a future-dated one.",
        "",
        "**On the 2050 date**: nothing in the source distinguishes a transcription error from a "
        "genuinely scheduled future transfer. Both partners share the exact same date, which is "
        "more consistent with a real scheduled event (e.g. a licence or unitisation milestone) than "
        "with two independent transcription errors landing on the same day - but this is an "
        "inference, not evidence, and is reported as such rather than asserted. **No authoritative "
        "resolution exists in the data available to this project. MURLACH remains future-only and "
        "unresolved**, per the instruction not to assign MARNOCK or SKUA ownership without explicit "
        "evidence.",
        "",
        "## 6. Pre-2000 older-equity-source inventory",
        "",
    ]
    for s in PRE_2000_SOURCE_INVENTORY:
        lines.append(f"### {s['name']}")
        lines.append("")
        for k, v in s.items():
            if k == "name":
                continue
            lines.append(f"- {k}: {v}")
        lines.append("")
    lines.append(PRE_2000_SOURCE_INVENTORY_NOT_FOUND_NOTE)
    lines.append("")
    lines.append("Search queries used (2026-09-09):")
    for q in PRE_2000_SOURCE_INVENTORY_QUERIES:
        lines.append(f"- `{q}`")
    lines.append("")

    lines += [
        "## 7. Draft methodology wording",
        "",
        "Provided for review; `methodology.html` is not created by this checkpoint.",
        "",
        "```markdown",
        DRAFT_METHODOLOGY_TEXT,
        "```",
        "",
        "## Confirmations",
        "",
        "- No build.py integration, no docs/data/equity artifacts, no UI changes, no company "
        "aliases or parent-group mappings, no equity history published. This report and its "
        "supporting module are the only outputs, both under etl/.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    result = run_historical_join()
    per_field_month = result["per_field_month"]

    from etl.equity_join_historical import load_full_history_production
    from etl.equity_interval_diagnostics import load_raw_rows

    pprs_history = load_full_history_production()
    raw_rows = load_raw_rows()

    report = build_report(per_field_month, pprs_history, raw_rows, result)
    PUBLICATION_REPORT_PATH.write_text(report)
    print(report)
    print(f"\nPublication window report written to {PUBLICATION_REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
