"""
Unit tests for etl/equity_parse.py (spec section 15.8 step 2).

Uses a small synthetic .xlsx fixture (tests/fixtures/equity_workbook_fixture.xlsx)
built to mirror the live workbook's real column structure and cover the
required edge cases, rather than the live 7,683-row download - same
fixture-based approach as tests/test_arcgis.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.equity_parse import (  # noqa: E402
    EquityParseError,
    load_workbook_sheet,
    parse_equity_workbook,
    read_header,
)

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_WORKBOOK = FIXTURES / "equity_workbook_fixture.xlsx"
MISSING_COLUMN_WORKBOOK = FIXTURES / "equity_workbook_missing_column_fixture.xlsx"


def test_missing_workbook_file_fails_loudly():
    with pytest.raises(EquityParseError) as excinfo:
        parse_equity_workbook(Path("/nonexistent/path/does_not_exist.xlsx"))
    assert "not found" in str(excinfo.value)


def test_missing_expected_column_fails_loudly():
    with pytest.raises(EquityParseError) as excinfo:
        parse_equity_workbook(MISSING_COLUMN_WORKBOOK)
    assert "End Date" in str(excinfo.value)


def test_parses_expected_row_count():
    rows = parse_equity_workbook(FIXTURE_WORKBOOK)
    assert len(rows) == 5


def test_open_ended_interval_has_none_end_date():
    rows = parse_equity_workbook(FIXTURE_WORKBOOK)
    abigail_current = next(r for r in rows if r["field_name"] == "ABIGAIL" and r["company_name"] == "ITHACA SP E&P LIMITED")
    assert abigail_current["end_date"] is None
    assert abigail_current["start_date"] == "2024-05-30"


def test_sentinel_start_date_is_flagged_not_reinterpreted():
    rows = parse_equity_workbook(FIXTURE_WORKBOOK)
    oldfield = next(r for r in rows if r["field_name"] == "OLDFIELD")
    assert oldfield["start_is_sentinel"] is True
    # Raw value passed through unchanged - interpretation is deferred, not
    # silently rewritten to None or "open".
    assert oldfield["start_date"] == "1900-01-01"
    assert oldfield["end_date"] == "1985-06-01"


def test_normal_row_is_not_flagged_as_sentinel():
    rows = parse_equity_workbook(FIXTURE_WORKBOOK)
    abigail_closed = next(r for r in rows if r["field_name"] == "ABIGAIL" and r["company_name"] == "ITHACA ENERGY (UK) LIMITED")
    assert abigail_closed["start_is_sentinel"] is False


def test_zero_interest_row_is_retained_and_flagged():
    rows = parse_equity_workbook(FIXTURE_WORKBOOK)
    affleck = next(r for r in rows if r["field_name"] == "AFFLECK")
    assert affleck["interest_pct"] == 0.0
    assert affleck["is_zero_interest"] is True
    # The row must survive parsing, not be dropped.
    assert affleck in rows


def test_zero_interest_row_count_matches_source():
    rows = parse_equity_workbook(FIXTURE_WORKBOOK)
    zero_rows = [r for r in rows if r["is_zero_interest"]]
    assert len(zero_rows) == 1


def test_nonzero_interest_rows_are_not_flagged_zero():
    rows = parse_equity_workbook(FIXTURE_WORKBOOK)
    non_zero = [r for r in rows if not r["is_zero_interest"]]
    assert all(r["interest_pct"] > 0 for r in non_zero)
    assert len(non_zero) == 4


def test_zero_duration_interval_is_parsed_not_rejected():
    """Start Date == End Date is a real, observed case in the live data
    (spec section 15.4's E7 rule doesn't currently account for it) - the
    parser must not reject it in this milestone."""
    rows = parse_equity_workbook(FIXTURE_WORKBOOK)
    alison = next(r for r in rows if r["field_name"] == "ALISON")
    assert alison["start_date"] == alison["end_date"] == "2016-05-17"


def test_parsing_is_deterministic():
    rows_a = parse_equity_workbook(FIXTURE_WORKBOOK)
    rows_b = parse_equity_workbook(FIXTURE_WORKBOOK)
    assert rows_a == rows_b


def test_header_maps_all_expected_columns():
    ws = load_workbook_sheet(FIXTURE_WORKBOOK)
    col_index = read_header(ws)
    assert col_index["Field Name"] == 0
    assert col_index["Organisation Name"] == 4
    assert col_index["Percentage Holding"] == 5
    assert col_index["Start Date"] == 7
    assert col_index["End Date"] == 8


def test_row_has_only_the_required_normalized_fields():
    rows = parse_equity_workbook(FIXTURE_WORKBOOK)
    expected_keys = {
        "field_name",
        "company_name",
        "interest_pct",
        "start_date",
        "end_date",
        "start_is_sentinel",
        "is_zero_interest",
    }
    assert set(rows[0].keys()) == expected_keys
