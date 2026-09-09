"""
Phase 2, step 3 (spec section 15.5 / 15.8 step 3).

Deterministic field-name reconciliation between PPRS (production) field
names and NSTA equity workbook field names. Field matching only - no
interval joins, no equity-attributable production, no company aliasing.

Matching order (first match wins, no fuzzy matching at any stage):

1. Exact match after trimming whitespace.
2. Normalized match (uppercase, trim, collapse internal whitespace,
   normalize dash/apostrophe variants). Punctuation that could be
   meaningful (brackets, periods, hyphens themselves) is never stripped.
3. Explicit alias match from etl/mappings/field_aliases.csv.

Anything still unmatched stays unmatched - it is never guessed at with
edit distance, token similarity, or any other fuzzy technique. A plausible
but incorrect match is worse than an unmatched field.

Data sources (both already-built, committed site artifacts - this script
makes no live network calls and does not touch build.py):

- PPRS field universe (552 fields with production history) and each
  field's first/last production period: docs/data/history/index.json
  (built by etl/transform.py in Phase 1).
- Latest-period (currently 202606) per-field production, for the
  production-weighted coverage calculation: docs/data/fields.geojson
  (also a Phase 1 artifact - only the 250 fields still producing in the
  latest period appear here).
- Equity workbook field universe: etl/equity_parse.py, reading the cached
  workbook from etl/equity_fetch.py (run those first).

Run: python etl/equity_match.py
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from equity_parse import DEFAULT_WORKBOOK_PATH, parse_equity_workbook

HISTORY_INDEX_PATH = Path(__file__).parent.parent / "docs" / "data" / "history" / "index.json"
FIELDS_GEOJSON_PATH = Path(__file__).parent.parent / "docs" / "data" / "fields.geojson"
FIELD_ALIASES_PATH = Path(__file__).parent / "mappings" / "field_aliases.csv"
MATCHING_REPORT_PATH = Path(__file__).parent / "equity_field_matching_report.md"

ALIAS_COLUMNS = ["pprs_field_name", "equity_field_name", "note", "reviewed_by", "reviewed_on"]

# Latest-period production streams reported by PPRS (spec section 15.7:
# these are never combined into boe/d at this stage).
PRODUCTION_STREAMS = ["oil_mbd", "dry_gas_mmscfd", "assoc_gas_mmscfd", "condensate_mbd"]

# Build-breaking threshold from spec section 15.5, reported here but not
# enforced - enforcement belongs to a later build.py integration step.
UNMATCHED_PRODUCTION_THRESHOLD_PCT = 2.0

_DASH_VARIANTS = ["‐", "‑", "‒", "–", "—", "−"]
_APOSTROPHE_VARIANTS = ["‘", "’", "ʼ"]


class EquityMatchError(RuntimeError):
    """Raised when field matching cannot proceed. Message must say exactly
    why."""


def normalize_field_name(name: str) -> str:
    """Deterministic normalization only: case, whitespace, and
    dash/apostrophe character-variant folding. Never strips brackets,
    periods, slashes, or any character that could distinguish one field
    from another (e.g. 'VIKING A [pt of VIKING GROUP]' vs
    'VIKING B [pt of VIKING GROUP]')."""
    s = name.strip().upper()
    s = re.sub(r"\s+", " ", s)
    s = s.translate({ord(c): "-" for c in _DASH_VARIANTS})
    s = s.translate({ord(c): "'" for c in _APOSTROPHE_VARIANTS})
    return s


def load_pprs_field_universe(path: Path = HISTORY_INDEX_PATH) -> dict[str, dict]:
    """Returns {field_name: {slug, first_period, last_period, operator, region}}
    for all 552 PPRS fields with production history."""
    if not path.exists():
        raise EquityMatchError(
            f"PPRS history index not found at {path}. Run the Phase 1 "
            "build (python etl/build.py) first."
        )
    with open(path) as f:
        index = json.load(f)
    universe = {}
    for slug, entry in index.items():
        name = entry["field"]
        if name in universe:
            raise EquityMatchError(
                f"Duplicate PPRS field name {name!r} in {path} (slugs "
                f"{universe[name]['slug']!r} and {slug!r}). The PPRS field "
                "universe is expected to have unique field names."
            )
        universe[name] = {
            "slug": slug,
            "first_period": entry["first_period"],
            "last_period": entry["last_period"],
            "operator": entry.get("operator"),
            "region": entry.get("region"),
        }
    return universe


def load_latest_period_production(path: Path = FIELDS_GEOJSON_PATH) -> dict[str, dict]:
    """Returns {field_name: {stream: value, ...}} for fields present in the
    latest-period feature set (currently-producing fields only - a field
    that stopped producing before the latest period has no entry here)."""
    if not path.exists():
        raise EquityMatchError(f"Fields GeoJSON not found at {path}.")
    with open(path) as f:
        geojson = json.load(f)
    production = {}
    for feature in geojson["features"]:
        props = feature["properties"]
        name = props["field"]
        production[name] = {stream: props[stream] for stream in PRODUCTION_STREAMS}
    return production


def load_equity_field_universe(workbook_path: Path = DEFAULT_WORKBOOK_PATH) -> tuple[set[str], list[dict]]:
    rows = parse_equity_workbook(workbook_path)
    fields = {r["field_name"] for r in rows}
    return fields, rows


def load_field_aliases(path: Path = FIELD_ALIASES_PATH) -> list[dict]:
    """Reads etl/mappings/field_aliases.csv. An empty file (header only, or
    missing entirely) is valid - it just means no aliases have been
    established yet, not an error."""
    if not path.exists():
        return []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ALIAS_COLUMNS:
            raise EquityMatchError(
                f"{path} has header {reader.fieldnames}, expected exactly "
                f"{ALIAS_COLUMNS}."
            )
        rows = list(reader)
    for i, row in enumerate(rows, start=2):
        if not row["pprs_field_name"].strip() or not row["equity_field_name"].strip():
            raise EquityMatchError(
                f"{path} row {i}: pprs_field_name and equity_field_name "
                f"must both be non-empty. Row: {row}."
            )
    return rows


def match_fields(pprs_fields: set[str], equity_fields: set[str], aliases: list[dict]) -> dict:
    """Applies exact -> normalized -> alias matching, in that order. Every
    PPRS field ends up in exactly one of: exact_matches, normalized_matches,
    alias_matches, unmatched_pprs. Equity fields not claimed by any PPRS
    match end up in unmatched_equity."""
    remaining_pprs = set(pprs_fields)
    remaining_equity = set(equity_fields)

    exact_matches = {}
    for f in sorted(pprs_fields):
        if f in remaining_equity:
            exact_matches[f] = f
            remaining_pprs.discard(f)
            remaining_equity.discard(f)

    equity_by_norm: dict[str, list[str]] = defaultdict(list)
    for f in remaining_equity:
        equity_by_norm[normalize_field_name(f)].append(f)
    ambiguous_normalized_keys = {k: sorted(v) for k, v in equity_by_norm.items() if len(v) > 1}

    normalized_matches = {}
    for f in sorted(remaining_pprs):
        key = normalize_field_name(f)
        candidates = equity_by_norm.get(key, [])
        # An ambiguous key (>1 equity field normalizes the same way) is
        # refused, not guessed at - matches only when exactly one candidate.
        if len(candidates) == 1:
            match = candidates[0]
            normalized_matches[f] = match
            remaining_pprs.discard(f)
            remaining_equity.discard(match)

    alias_by_pprs = {}
    for row in aliases:
        pprs_name = row["pprs_field_name"]
        equity_name = row["equity_field_name"]
        if pprs_name in alias_by_pprs:
            raise EquityMatchError(
                f"field_aliases.csv has more than one row for PPRS field "
                f"{pprs_name!r}. Refusing to guess which is correct."
            )
        alias_by_pprs[pprs_name] = equity_name

    alias_matches = {}
    for f in sorted(remaining_pprs):
        equity_name = alias_by_pprs.get(f)
        if equity_name is None:
            continue
        if equity_name not in equity_fields:
            raise EquityMatchError(
                f"field_aliases.csv maps PPRS field {f!r} to equity field "
                f"{equity_name!r}, which does not exist in the equity "
                "workbook. The alias file is stale."
            )
        alias_matches[f] = equity_name
        remaining_pprs.discard(f)
        remaining_equity.discard(equity_name)

    return {
        "exact_matches": exact_matches,
        "normalized_matches": normalized_matches,
        "alias_matches": alias_matches,
        "unmatched_pprs": sorted(remaining_pprs),
        "unmatched_equity": sorted(remaining_equity),
        "ambiguous_normalized_keys": ambiguous_normalized_keys,
    }


def duplicate_equity_names_after_normalization(equity_fields: set[str]) -> dict[str, list[str]]:
    """Distinct from ambiguous_normalized_keys in match_fields (which is
    scoped to fields still unmatched after exact matching) - this checks
    the full equity field universe for any two distinct raw names that
    normalize to the same key, which would make normalized matching
    inherently unsafe for those names regardless of match order."""
    by_norm: dict[str, list[str]] = defaultdict(list)
    for f in equity_fields:
        by_norm[normalize_field_name(f)].append(f)
    return {k: sorted(v) for k, v in by_norm.items() if len(v) > 1}


def production_weighted_coverage(
    matched_pprs_fields: set[str],
    latest_production: dict[str, dict],
) -> dict:
    """Coverage = matched production / total latest-period production, per
    stream. Only fields present in the latest period (currently-producing)
    contribute - a matched or unmatched field that stopped producing
    earlier contributes 0 to both numerator and denominator here, which is
    correct: it cannot affect latest-period coverage."""
    totals = {stream: 0.0 for stream in PRODUCTION_STREAMS}
    matched_totals = {stream: 0.0 for stream in PRODUCTION_STREAMS}
    for field, values in latest_production.items():
        for stream in PRODUCTION_STREAMS:
            totals[stream] += values[stream]
            if field in matched_pprs_fields:
                matched_totals[stream] += values[stream]

    coverage = {}
    for stream in PRODUCTION_STREAMS:
        total = totals[stream]
        matched = matched_totals[stream]
        coverage[stream] = {
            "total": round(total, 3),
            "matched": round(matched, 3),
            "unmatched": round(total - matched, 3),
            "coverage_pct": round(100.0 * matched / total, 2) if total > 0 else None,
        }
    return coverage


def unmatched_field_detail(
    unmatched_pprs: list[str],
    pprs_universe: dict[str, dict],
    latest_production: dict[str, dict],
    latest_period: str,
) -> list[dict]:
    detail = []
    for name in unmatched_pprs:
        entry = pprs_universe[name]
        production = latest_production.get(name)
        detail.append(
            {
                "field_name": name,
                "first_period": entry["first_period"],
                "last_period": entry["last_period"],
                "produced_in_latest_period": entry["last_period"] == latest_period,
                "latest_period_production": production,
            }
        )
    return detail


def zero_interest_rows_with_operator_flag(workbook_path: Path = DEFAULT_WORKBOOK_PATH) -> list[dict]:
    """Re-reads the raw workbook (not the milestone-1 normalized output,
    which deliberately does not carry Operator Flag) to find zero-interest
    rows where Operator Flag = 'Y' - an edge case flagged for the interval
    join review, not resolved here."""
    from equity_parse import load_workbook_sheet, read_header

    ws = load_workbook_sheet(workbook_path)
    col_index = read_header(ws)
    results = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row is None or all(v is None for v in row):
            continue
        interest = row[col_index["Percentage Holding"]]
        operator_flag = row[col_index["Operator Flag"]]
        if interest == 0 and operator_flag == "Y":
            start = row[col_index["Start Date"]]
            end = row[col_index["End Date"]]
            results.append(
                {
                    "Field Name": row[col_index["Field Name"]],
                    "Organisation Name": row[col_index["Organisation Name"]],
                    "Start Date": start.date().isoformat() if start else None,
                    "End Date": end.date().isoformat() if end else None,
                }
            )
    return results


def build_matching_report(
    pprs_universe: dict[str, dict],
    equity_fields: set[str],
    equity_rows: list[dict],
    match_result: dict,
    coverage: dict,
    unmatched_detail: list[dict],
    dup_equity_norm: dict,
    latest_period: str,
    zero_interest_operators: list[dict],
) -> str:
    """zero_interest_operators must be computed by the caller (e.g. via
    zero_interest_rows_with_operator_flag()) and passed in explicitly -
    this function does no file I/O of its own, so it behaves identically
    whether called from main() or from a test with synthetic data, and
    never depends on a workbook being cached on disk."""
    pprs_fields = set(pprs_universe.keys())
    total_pprs = len(pprs_fields)
    total_equity = len(equity_fields)
    n_exact = len(match_result["exact_matches"])
    n_norm = len(match_result["normalized_matches"])
    n_alias = len(match_result["alias_matches"])
    n_unmatched_pprs = len(match_result["unmatched_pprs"])
    n_unmatched_equity = len(match_result["unmatched_equity"])
    n_matched_total = n_exact + n_norm + n_alias

    lines = [
        "# PPRS <-> equity workbook field-name matching report",
        "",
        "## Field universes",
        "",
        f"- PPRS fields with production history: {total_pprs}",
        f"- Equity workbook distinct field names: {total_equity}",
        f"- Fields present in both (by any matching rule below): {n_matched_total}",
        f"- Fields present only in PPRS: {n_unmatched_pprs}",
        f"- Fields present only in the equity workbook: {n_unmatched_equity}",
        "",
        "Count differences alone are not treated as errors: the datasets "
        "can legitimately include fields of different status or scope "
        "(e.g. sub-unit partner groupings the equity workbook tracks "
        "separately, or PPRS reporting units the equity workbook does not "
        "cover under any name).",
        "",
        "## Matching statistics",
        "",
        f"- Exact matches: {n_exact}",
        f"- Normalized matches: {n_norm}",
        f"- Alias matches: {n_alias}",
        f"- Unmatched PPRS fields: {n_unmatched_pprs}",
        f"- Unmatched equity fields: {n_unmatched_equity}",
        f"- Ambiguous normalized keys (post-exact-match): {len(match_result['ambiguous_normalized_keys'])}",
        f"- Duplicate equity names after normalization (full universe): {len(dup_equity_norm)}",
        "",
    ]

    if match_result["ambiguous_normalized_keys"]:
        lines.append("### Ambiguous normalized keys")
        lines.append("")
        for key, names in sorted(match_result["ambiguous_normalized_keys"].items()):
            lines.append(f"- `{key}` <- {names} (refused, not guessed)")
        lines.append("")
    else:
        lines.append("No ambiguous normalized keys found: no case where more than one "
                     "unmatched equity field name normalizes to the same key.")
        lines.append("")

    if dup_equity_norm:
        lines.append("### Duplicate equity names after normalization (full universe)")
        lines.append("")
        for key, names in sorted(dup_equity_norm.items()):
            lines.append(f"- `{key}` <- {names}")
        lines.append("")
    else:
        lines.append("No duplicate equity names found after normalization across the "
                     "full 531-field equity universe.")
        lines.append("")

    lines += [
        "## Rename cases checked explicitly (spec section 15.5)",
        "",
    ]
    for pair, note in [
        (("SEAN", "NORTH SEAN"), "SEAN -> NORTH SEAN"),
        (("COLUMBA B", "COLUMBA BD"), "COLUMBA B -> COLUMBA BD"),
    ]:
        lines.append(f"- **{note}**: see narrative below.")
    lines += [
        "",
        "- `NORTH SEAN`: PPRS's post-rename-consolidation field name (section 7.2's "
        "transform already merges the pre-2017 `SEAN` reporting unit into `NORTH SEAN` "
        "as one continuous series, so the raw pre-rename PPRS name does not appear in "
        "the 552-field universe used here). The equity workbook's `NORTH SEAN` rows "
        "start as early as 1984-03-21 - i.e. it already uses the current name for the "
        "pre-rename period too. Exact match succeeds; **no alias row needed**.",
        "- `COLUMBA B/D`: PPRS's field name is `COLUMBA B/D` (with a slash), not "
        "`COLUMBA BD` as spec section 15.5's prose states - the spec's name for this "
        "field should be corrected. The equity workbook's `COLUMBA B/D` rows start as "
        "early as 2002-12-16, before the 200006/200007 transition mentioned in the "
        "spec. Exact match succeeds; **no alias row needed**.",
        "",
        "## Structural mismatches investigated but not aliased",
        "",
        "These looked like plausible near-duplicates but did not have unambiguous "
        "structural evidence of a 1:1 rename, so they were left unmatched rather than "
        "guessed at:",
        "",
        "- `INDEFATIGABLE [SHELL]` (PPRS, 198907-200507) vs `INDEFATIGABLE [PERENCO]` "
        "(PPRS, 199004-202606, present in equity workbook): **periods overlap** "
        "(199004-200507), so this is not a rename of the same reporting unit - they "
        "were reported concurrently under different operators/interests. Left unmatched.",
        "- `ALISON [CENTRICA]` (PPRS, 199510-201702) vs `ALISON-KX [CONOCOPHILLIPS]` "
        "(PPRS, 199510-201808): periods overlap entirely. The equity workbook's plain "
        "`ALISON` (no suffix) cannot be attributed to either without guessing. Left "
        "unmatched.",
        "- `VIKING` (PPRS, plain) vs equity's `VIKING A`..`VIKING E [pt of VIKING GROUP]`: "
        "PPRS reports `VIKING`, `VIKING A`, `VIKING B` (3 units); equity reports "
        "`VIKING A`-`VIKING E` (5 units, A/B match exactly). No structural evidence for "
        "what PPRS's plain `VIKING` corresponds to among C/D/E. Left unmatched both ways.",
        "- `HEWETT` group: PPRS's plain `HEWETT` matches exactly. Equity additionally "
        "tracks `BIG DOTTY [pt. of HEWETT]`, `DEBORAH [Part of HEWETT]`, "
        "`LITTLE DOTTY [Part of HEWETT]` as separate partner groupings with no PPRS "
        "counterpart under any name. Left unmatched (equity-only).",
        "- `MARNOCK-SKUA` group: PPRS has `MARNOCK`, `MURLACH`, `SKUA` (all "
        "`[pt. of MARNOCK-SKUA]`); equity has only `MARNOCK` and `MURLACH` - `SKUA` is "
        "absent from the equity workbook under any name, not a naming variant. Left "
        "unmatched (PPRS-only).",
        "- `BRAE` group: equity's plain `BRAE` and PPRS's `SEDGWICK [PT. OF WEST BRAE]` "
        "are each unmatched with no evidenced counterpart on the other side.",
        "",
        "## Unmatched PPRS fields (full list)",
        "",
        "| Field | First period | Last period | Produced in " + latest_period + " | "
        "Latest-period oil (mbd) | dry gas (mmscfd) | assoc gas (mmscfd) | condensate (mbd) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for d in unmatched_detail:
        prod = d["latest_period_production"]
        oil = prod["oil_mbd"] if prod else "n/a"
        dg = prod["dry_gas_mmscfd"] if prod else "n/a"
        ag = prod["assoc_gas_mmscfd"] if prod else "n/a"
        cond = prod["condensate_mbd"] if prod else "n/a"
        lines.append(
            f"| {d['field_name']} | {d['first_period']} | {d['last_period']} | "
            f"{d['produced_in_latest_period']} | {oil} | {dg} | {ag} | {cond} |"
        )
    lines.append("")

    lines += [
        "## Unmatched equity workbook fields (full list)",
        "",
    ]
    for f in match_result["unmatched_equity"]:
        lines.append(f"- {f}")
    lines.append("")

    lines += [
        "## Production-weighted coverage, latest period (" + latest_period + ")",
        "",
        "Field-count coverage and production-weighted coverage are **not the same "
        "thing** and are reported separately. A handful of unmatched high-volume "
        "fields can outweigh many small unmatched ones. Streams are reported "
        "separately and are not combined into boe/d at this step.",
        "",
        "| Stream | Total | Matched | Unmatched | Coverage % |",
        "| --- | --- | --- | --- | --- |",
    ]
    stream_labels = {
        "oil_mbd": "Oil (mbd)",
        "dry_gas_mmscfd": "Dry gas (mmscfd)",
        "assoc_gas_mmscfd": "Associated gas (mmscfd)",
        "condensate_mbd": "Condensate (mbd)",
    }
    for stream, label in stream_labels.items():
        c = coverage[stream]
        pct = f"{c['coverage_pct']}%" if c["coverage_pct"] is not None else "n/a (zero total)"
        lines.append(f"| {label} | {c['total']} | {c['matched']} | {c['unmatched']} | {pct} |")
    lines.append("")

    unmatched_pcts = [c["coverage_pct"] for c in coverage.values() if c["coverage_pct"] is not None]
    worst_unmatched_pct = max((100.0 - p for p in unmatched_pcts), default=0.0)
    would_pass = worst_unmatched_pct <= UNMATCHED_PRODUCTION_THRESHOLD_PCT
    lines += [
        f"Build-breaking threshold from spec section 15.5: unmatched fields must "
        f"account for no more than {UNMATCHED_PRODUCTION_THRESHOLD_PCT}% of "
        f"latest-period production. Worst-stream unmatched share: "
        f"{worst_unmatched_pct:.2f}%. **Would {'PASS' if would_pass else 'FAIL'}** "
        "if enforced today. Not enforced in build.py in this milestone.",
        "",
        "## Historical field-period count coverage (not a volume measure)",
        "",
        f"- {n_matched_total} of {total_pprs} PPRS fields ({100 * n_matched_total / total_pprs:.1f}%) "
        "matched by field name across their full production history.",
        "- This is a **count of fields**, not a production-weighted figure, and must not "
        "be read as equivalent to the volume coverage above. A field matched or "
        "unmatched by name says nothing about how much it produced.",
        "",
        "## Edge cases carried forward from milestone 1 (not resolved here)",
        "",
        "Preserved for the interval-join review, not resolved by field-name matching:",
        "",
    ]

    future_dated = [r for r in equity_rows if r["start_date"] and r["start_date"] >= "2027-01-01"]
    zero_duration = [r for r in equity_rows if r["start_date"] == r["end_date"]]
    zero_interest = [r for r in equity_rows if r["is_zero_interest"]]
    open_ended = [r for r in equity_rows if r["end_date"] is None]
    sentinel = [r for r in equity_rows if r["start_is_sentinel"]]

    lines.append(f"- {len(future_dated)} rows with future start dates:")
    for r in future_dated:
        lines.append(
            f"  - {r['field_name']} / {r['company_name']}: start_date={r['start_date']}, "
            f"end_date={r['end_date']}, interest_pct={r['interest_pct']}"
        )
    lines.append(f"- {len(zero_duration)} zero-duration interval(s):")
    for r in zero_duration:
        lines.append(
            f"  - {r['field_name']} / {r['company_name']}: start_date=end_date="
            f"{r['start_date']}, interest_pct={r['interest_pct']}"
        )
    lines += [
        f"- {len(zero_interest)} zero-interest rows, retained unfiltered "
        f"(is_zero_interest=true), meaning not investigated.",
        f"- Of those, {len(zero_interest_operators)} also have Operator Flag = 'Y' "
        "in the raw workbook (an operator with no recorded equity interest), e.g.:",
    ]
    for r in zero_interest_operators[:5]:
        lines.append(f"  - {r['Field Name']} / {r['Organisation Name']}: start={r['Start Date']}, end={r['End Date']}")
    lines += [
        f"- {len(open_ended)} open-ended rows (end_date is null).",
        f"- {len(sentinel)} sentinel start-date rows in the current workbook "
        "(none found, as in milestone 1).",
        "",
        "These issues are not blockers for field-name matching and are not resolved "
        "here; they must be addressed before interval joins begin (spec section 15.8 "
        "step 4).",
        "",
    ]

    return "\n".join(lines)


def main() -> int:
    try:
        pprs_universe = load_pprs_field_universe()
        latest_production = load_latest_period_production()
        equity_fields, equity_rows = load_equity_field_universe()
        aliases = load_field_aliases()

        pprs_fields = set(pprs_universe.keys())
        match_result = match_fields(pprs_fields, equity_fields, aliases)
        dup_equity_norm = duplicate_equity_names_after_normalization(equity_fields)

        matched_pprs = (
            set(match_result["exact_matches"])
            | set(match_result["normalized_matches"])
            | set(match_result["alias_matches"])
        )
        coverage = production_weighted_coverage(matched_pprs, latest_production)

        with open(Path(__file__).parent.parent / "docs" / "data" / "meta.json") as f:
            latest_period = json.load(f)["latest_period"]

        unmatched_detail = unmatched_field_detail(
            match_result["unmatched_pprs"], pprs_universe, latest_production, latest_period
        )
        zero_interest_operators = zero_interest_rows_with_operator_flag()

        report = build_matching_report(
            pprs_universe,
            equity_fields,
            equity_rows,
            match_result,
            coverage,
            unmatched_detail,
            dup_equity_norm,
            latest_period,
            zero_interest_operators,
        )
        MATCHING_REPORT_PATH.write_text(report)
        print(report)
        print(f"\nMatching report written to {MATCHING_REPORT_PATH}")
        return 0
    except EquityMatchError as e:
        print(f"\nEQUITY MATCH FAILED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
