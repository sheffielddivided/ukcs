"""
Unit tests for etl/equity_match.py (spec section 15.5 / 15.8 step 3).

Uses small synthetic field-name sets and a fixture alias CSV rather than
the live 552-field PPRS universe / 531-field equity universe, so these run
offline and deterministically - same approach as the other etl tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.equity_match import (  # noqa: E402
    EquityMatchError,
    build_matching_report,
    duplicate_equity_names_after_normalization,
    load_field_aliases,
    match_fields,
    normalize_field_name,
    production_weighted_coverage,
)

FIXTURES = Path(__file__).parent / "fixtures"
ALIAS_FIXTURE = FIXTURES / "field_aliases_fixture.csv"


def test_exact_match():
    pprs = {"ABIGAIL", "AFFLECK"}
    equity = {"ABIGAIL", "AFFLECK"}
    result = match_fields(pprs, equity, aliases=[])
    assert result["exact_matches"] == {"ABIGAIL": "ABIGAIL", "AFFLECK": "AFFLECK"}
    assert result["normalized_matches"] == {}
    assert result["unmatched_pprs"] == []
    assert result["unmatched_equity"] == []


def test_normalized_match_on_whitespace_and_case():
    pprs = {"NORTH   SEAN"}
    equity = {"North Sean"}
    result = match_fields(pprs, equity, aliases=[])
    assert result["exact_matches"] == {}
    assert result["normalized_matches"] == {"NORTH   SEAN": "North Sean"}


def test_normalized_match_folds_dash_variants():
    pprs = {"WEST–BRAE"}  # en-dash
    equity = {"WEST-BRAE"}  # ascii hyphen
    result = match_fields(pprs, equity, aliases=[])
    assert result["normalized_matches"] == {"WEST–BRAE": "WEST-BRAE"}


def test_normalization_never_strips_meaningful_punctuation():
    """Brackets and periods distinguish real, different fields and must
    never be removed - e.g. 'VIKING A [pt of VIKING GROUP]' must not
    normalize to the same key as a hypothetical 'VIKING A'."""
    assert normalize_field_name("VIKING A [pt of VIKING GROUP]") != normalize_field_name("VIKING A")
    assert "[" in normalize_field_name("VIKING A [pt of VIKING GROUP]")
    assert "." in normalize_field_name("AIRTH COAL BED METHANE DEVT.")


def test_explicit_alias_match():
    aliases = load_field_aliases(ALIAS_FIXTURE)
    pprs = {"OLD NAME FIELD"}
    equity = {"NEW NAME FIELD"}
    result = match_fields(pprs, equity, aliases)
    assert result["alias_matches"] == {"OLD NAME FIELD": "NEW NAME FIELD"}
    assert result["exact_matches"] == {}
    assert result["normalized_matches"] == {}


def test_alias_only_applied_after_exact_and_normalized_fail():
    """An alias entry for a field that also has an exact match must not
    interfere - exact match wins."""
    aliases = [{"pprs_field_name": "ABIGAIL", "equity_field_name": "SOMETHING ELSE", "note": "", "reviewed_by": "", "reviewed_on": ""}]
    pprs = {"ABIGAIL"}
    equity = {"ABIGAIL", "SOMETHING ELSE"}
    result = match_fields(pprs, equity, aliases)
    assert result["exact_matches"] == {"ABIGAIL": "ABIGAIL"}
    assert result["alias_matches"] == {}
    assert result["unmatched_equity"] == ["SOMETHING ELSE"]


def test_alias_referencing_nonexistent_equity_field_fails_loudly():
    aliases = [{"pprs_field_name": "GHOST FIELD", "equity_field_name": "DOES NOT EXIST", "note": "", "reviewed_by": "", "reviewed_on": ""}]
    pprs = {"GHOST FIELD"}
    equity = {"SOMETHING UNRELATED"}
    with pytest.raises(EquityMatchError) as excinfo:
        match_fields(pprs, equity, aliases)
    assert "does not exist in the equity workbook" in str(excinfo.value)


def test_unmatched_field_stays_unmatched():
    pprs = {"NEVER SEEN BEFORE"}
    equity = {"COMPLETELY DIFFERENT"}
    result = match_fields(pprs, equity, aliases=[])
    assert result["unmatched_pprs"] == ["NEVER SEEN BEFORE"]
    assert result["unmatched_equity"] == ["COMPLETELY DIFFERENT"]


def test_ambiguous_normalized_key_is_refused_not_guessed():
    """Two distinct equity names that normalize to the same key must not
    be matched to a PPRS field with that key - refuse rather than guess
    which one is correct."""
    pprs = {"FOO BAR"}
    equity = {"Foo  Bar", "FOO BAR "}  # both normalize to "FOO BAR"
    result = match_fields(pprs, equity, aliases=[])
    assert result["normalized_matches"] == {}
    assert result["unmatched_pprs"] == ["FOO BAR"]
    assert "FOO BAR" in result["ambiguous_normalized_keys"]
    assert set(result["ambiguous_normalized_keys"]["FOO BAR"]) == {"Foo  Bar", "FOO BAR "}


def test_no_fuzzy_matching_similar_names_stay_unmatched():
    """Names that a fuzzy/edit-distance matcher would likely conflate must
    remain unmatched here - a plausible but incorrect match is worse than
    an unmatched field."""
    pprs = {"ALISON [CENTRICA]"}
    equity = {"ALISON-KX [CONOCOPHILLIPS]"}  # similar but a different field
    result = match_fields(pprs, equity, aliases=[])
    assert result["exact_matches"] == {}
    assert result["normalized_matches"] == {}
    assert result["unmatched_pprs"] == ["ALISON [CENTRICA]"]
    assert result["unmatched_equity"] == ["ALISON-KX [CONOCOPHILLIPS]"]


def test_duplicate_equity_names_after_normalization():
    equity = {"Foo Bar", "FOO  BAR", "Baz"}
    dupes = duplicate_equity_names_after_normalization(equity)
    assert "FOO BAR" in dupes
    assert set(dupes["FOO BAR"]) == {"Foo Bar", "FOO  BAR"}
    assert "BAZ" not in dupes


def test_no_duplicates_when_all_names_distinct_after_normalization():
    equity = {"ABIGAIL", "AFFLECK", "ALBA"}
    assert duplicate_equity_names_after_normalization(equity) == {}


def test_production_weighted_coverage_basic():
    matched_pprs = {"ABIGAIL"}
    latest_production = {
        "ABIGAIL": {"oil_mbd": 10.0, "dry_gas_mmscfd": 0.0, "assoc_gas_mmscfd": 0.0, "condensate_mbd": 0.0},
        "UNMATCHED FIELD": {"oil_mbd": 5.0, "dry_gas_mmscfd": 0.0, "assoc_gas_mmscfd": 0.0, "condensate_mbd": 0.0},
    }
    coverage = production_weighted_coverage(matched_pprs, latest_production)
    assert coverage["oil_mbd"]["total"] == 15.0
    assert coverage["oil_mbd"]["matched"] == 10.0
    assert coverage["oil_mbd"]["unmatched"] == 5.0
    assert coverage["oil_mbd"]["coverage_pct"] == pytest.approx(66.67, abs=0.01)


def test_production_weighted_coverage_handles_zero_total():
    coverage = production_weighted_coverage(set(), {})
    for stream_coverage in coverage.values():
        assert stream_coverage["total"] == 0.0
        assert stream_coverage["coverage_pct"] is None


def test_load_field_aliases_missing_file_returns_empty():
    assert load_field_aliases(Path("/nonexistent/field_aliases.csv")) == []


def test_load_field_aliases_wrong_header_fails_loudly(tmp_path):
    bad_csv = tmp_path / "bad_aliases.csv"
    bad_csv.write_text("wrong,header,columns\n")
    with pytest.raises(EquityMatchError):
        load_field_aliases(bad_csv)


def test_load_field_aliases_reads_fixture_row():
    aliases = load_field_aliases(ALIAS_FIXTURE)
    assert len(aliases) == 1
    assert aliases[0]["pprs_field_name"] == "OLD NAME FIELD"
    assert aliases[0]["equity_field_name"] == "NEW NAME FIELD"


def test_matching_report_is_deterministic():
    pprs_universe = {"ABIGAIL": {"slug": "abigail", "first_period": "202210", "last_period": "202606", "operator": "X", "region": "CNS"}}
    equity_fields = {"ABIGAIL"}
    equity_rows = []
    match_result = match_fields(set(pprs_universe), equity_fields, aliases=[])
    coverage = production_weighted_coverage(set(match_result["exact_matches"]), {})
    unmatched_detail = []
    dup_equity_norm = {}

    report_a = build_matching_report(pprs_universe, equity_fields, equity_rows, match_result, coverage, unmatched_detail, dup_equity_norm, "202606")
    report_b = build_matching_report(pprs_universe, equity_fields, equity_rows, match_result, coverage, unmatched_detail, dup_equity_norm, "202606")
    assert report_a == report_b


def test_matching_report_contains_key_figures():
    pprs_universe = {
        "ABIGAIL": {"slug": "abigail", "first_period": "202210", "last_period": "202606", "operator": "X", "region": "CNS"},
        "GONE FIELD": {"slug": "gone-field", "first_period": "199001", "last_period": "199512", "operator": "Y", "region": "SNS"},
    }
    equity_fields = {"ABIGAIL"}
    equity_rows = []
    match_result = match_fields(set(pprs_universe), equity_fields, aliases=[])
    coverage = production_weighted_coverage(set(match_result["exact_matches"]), {})
    unmatched_detail = [
        {"field_name": "GONE FIELD", "first_period": "199001", "last_period": "199512", "produced_in_latest_period": False, "latest_period_production": None}
    ]
    report = build_matching_report(pprs_universe, equity_fields, equity_rows, match_result, coverage, unmatched_detail, {}, "202606")
    assert "GONE FIELD" in report
    assert "Exact matches: 1" in report
    assert "Unmatched PPRS fields: 1" in report
