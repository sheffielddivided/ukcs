"""
Unit tests for etl/company_groups.py (Workstream 1, spec approved
2026-09-10). No network access - tests the pure functions directly with
synthetic data shaped like the live NSTA equity-group-holder service and
this project's own company/equity artifacts.
"""

from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.company_groups import (  # noqa: E402
    CompanyGroupsError,
    aggregate_company_series_by_group,
    build_company_groups_mapping,
    build_group_resolution,
    build_grouping_review_report,
    mapping_by_entity,
    parse_eqorg_segments,
    resolve_row_holder_name,
    validate_group_conservation,
    write_company_groups_csv,
)


# ---------------------------------------------------------------------------
# EQORG parsing / row holder resolution
# ---------------------------------------------------------------------------


def test_parse_eqorg_segments_multiple_holders():
    segments = parse_eqorg_segments("PERENCO GAS (UK) LIMITED (85%), EVERARD ENERGY LIMITED (15%)")
    assert segments == [("PERENCO GAS (UK) LIMITED", 85.0), ("EVERARD ENERGY LIMITED", 15.0)]


def test_parse_eqorg_segments_single_holder():
    assert parse_eqorg_segments("SPIRIT ENERGY PRODUCTION UK LIMITED (100%)") == [
        ("SPIRIT ENERGY PRODUCTION UK LIMITED", 100.0)
    ]


def test_parse_eqorg_segments_blank():
    assert parse_eqorg_segments(None) == []
    assert parse_eqorg_segments("") == []


def test_resolve_row_holder_name_unambiguous():
    eqorg = "PERENCO GAS (UK) LIMITED (85%), EVERARD ENERGY LIMITED (15%)"
    assert resolve_row_holder_name(eqorg, 85.0) == "PERENCO GAS (UK) LIMITED"
    assert resolve_row_holder_name(eqorg, 15.0) == "EVERARD ENERGY LIMITED"


def test_resolve_row_holder_name_tied_percentage_is_ambiguous():
    # Two holders both at 50% - genuinely cannot disambiguate from EQUITY alone.
    eqorg = "COMPANY A (50%), COMPANY B (50%)"
    assert resolve_row_holder_name(eqorg, 50.0) is None


def test_resolve_row_holder_name_no_match():
    eqorg = "COMPANY A (60%), COMPANY B (40%)"
    assert resolve_row_holder_name(eqorg, 99.0) is None


# ---------------------------------------------------------------------------
# Group resolution from raw rows
# ---------------------------------------------------------------------------


def _row(eqorg, eqgrphold, equity):
    return {"attributes": {"EQORG": eqorg, "EQGRPHOLD": eqgrphold, "EQUITY": equity}}


def test_build_group_resolution_consistent_across_rows():
    rows = [
        _row("CNR INTERNATIONAL (U.K.) LIMITED (100%)", "CNR INTERNATIONAL", 100.0),
        _row("CNR INTERNATIONAL (U.K.) DEVELOPMENTS LIMITED (100%)", "CNR INTERNATIONAL", 100.0),
    ]
    resolution = build_group_resolution(rows)
    assert resolution["CNR INTERNATIONAL (U.K.) LIMITED"]["groups"] == {"CNR INTERNATIONAL": 1}
    assert resolution["CNR INTERNATIONAL (U.K.) DEVELOPMENTS LIMITED"]["groups"] == {
        "CNR INTERNATIONAL": 1
    }


def test_build_group_resolution_skips_ambiguous_rows():
    rows = [_row("COMPANY A (50%), COMPANY B (50%)", "SOME GROUP", 50.0)]
    resolution = build_group_resolution(rows)
    assert resolution == {}


def test_build_group_resolution_detects_conflict():
    rows = [
        _row("COMPANY X (100%)", "GROUP ONE", 100.0),
        _row("COMPANY X (100%)", "GROUP TWO", 100.0),
    ]
    resolution = build_group_resolution(rows)
    assert resolution["COMPANY X"]["groups"] == {"GROUP ONE": 1, "GROUP TWO": 1}


# ---------------------------------------------------------------------------
# Mapping construction - every entity gets exactly one result
# ---------------------------------------------------------------------------


def test_every_known_entity_gets_a_mapping_row():
    known = {"RESOLVED CO", "CONFLICTED CO", "UNKNOWN CO"}
    resolution = {
        "RESOLVED CO": {"groups": {"BIG GROUP": 3}, "ambiguous_row_count": 0},
        "CONFLICTED CO": {"groups": {"GROUP A": 1, "GROUP B": 1}, "ambiguous_row_count": 0},
    }
    mapping = build_company_groups_mapping(known, resolution, "source desc", "2026-09-10")
    by_entity = mapping_by_entity(mapping)

    assert set(by_entity) == known  # no entity disappears

    assert by_entity["RESOLVED CO"]["current_display_group"] == "BIG GROUP"
    assert by_entity["RESOLVED CO"]["status"] == "approved"
    assert by_entity["RESOLVED CO"]["grouping_basis"] == "NSTA equity group"

    # Conflicting NSTA evidence is surfaced, not guessed.
    assert by_entity["CONFLICTED CO"]["current_display_group"] == "CONFLICTED CO"
    assert by_entity["CONFLICTED CO"]["status"] == "unresolved"

    # No evidence at all -> falls back to itself, never fabricated.
    assert by_entity["UNKNOWN CO"]["current_display_group"] == "UNKNOWN CO"
    assert by_entity["UNKNOWN CO"]["status"] == "unresolved"
    assert by_entity["UNKNOWN CO"]["grouping_basis"] == "registered company identity"


def test_no_fuzzy_grouping_shared_token_does_not_group():
    # "CHRYSAOR LIMITED" and "CHRYSAOR PRODUCTION (U.K.) LIMITED" share a
    # token but must NOT be grouped together without explicit NSTA/
    # reviewed evidence naming them under the same EQGRPHOLD.
    known = {"CHRYSAOR LIMITED", "CHRYSAOR PRODUCTION (U.K.) LIMITED"}
    resolution: dict = {}  # no NSTA evidence for either
    mapping = build_company_groups_mapping(known, resolution, "source", "2026-09-10")
    by_entity = mapping_by_entity(mapping)
    assert by_entity["CHRYSAOR LIMITED"]["current_display_group"] == "CHRYSAOR LIMITED"
    assert (
        by_entity["CHRYSAOR PRODUCTION (U.K.) LIMITED"]["current_display_group"]
        == "CHRYSAOR PRODUCTION (U.K.) LIMITED"
    )


# ---------------------------------------------------------------------------
# CSV writer - deterministic, correct schema
# ---------------------------------------------------------------------------


def test_write_company_groups_csv_schema_and_determinism():
    mapping = build_company_groups_mapping(
        {"B CO", "A CO"}, {}, "no evidence", "2026-09-10"
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "company_groups.csv"
        write_company_groups_csv(path, mapping)
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert [r["source_legal_entity"] for r in rows] == ["A CO", "B CO"]  # sorted
        assert set(rows[0].keys()) == {
            "source_legal_entity",
            "current_display_group",
            "valid_from",
            "valid_to",
            "grouping_basis",
            "source",
            "reviewed_by",
            "reviewed_on",
            "status",
        }


# ---------------------------------------------------------------------------
# Group-level series aggregation and conservation
# ---------------------------------------------------------------------------


def _company_doc(series):
    return {"series": series}


def _point(period, oil=None, oil_status="complete"):
    return {
        "period": period,
        "oil_mbd": {"value": oil, "status": oil_status},
        "dry_gas_mmscfd": {"value": None, "status": "not_applicable"},
        "assoc_gas_mmscfd": {"value": None, "status": "not_applicable"},
        "condensate_mbd": {"value": None, "status": "not_applicable"},
        "liquids_mboed": {"value": oil, "status": oil_status},
        "natural_gas_mboed": {"value": 0.0, "status": "not_applicable"},
        "total_mboed": {"value": oil, "status": oil_status},
    }


def test_aggregate_company_series_by_group_sums_members():
    company_docs = {
        "ALPHA CO": _company_doc([_point("2020-01", oil=10.0)]),
        "BETA CO": _company_doc([_point("2020-01", oil=5.0)]),
    }
    entity_to_group = {"ALPHA CO": "BIG GROUP", "BETA CO": "BIG GROUP"}
    group_docs = aggregate_company_series_by_group(company_docs, entity_to_group)
    assert "BIG GROUP" in group_docs
    entry = group_docs["BIG GROUP"]["series"][0]
    assert entry["oil_mbd"]["value"] == 15.0
    assert entry["oil_mbd"]["status"] == "complete"
    assert group_docs["BIG GROUP"]["member_entities"] == ["ALPHA CO", "BETA CO"]
    assert group_docs["BIG GROUP"]["is_singleton"] is False


def test_aggregate_company_series_by_group_unmapped_entity_is_its_own_group():
    company_docs = {"SOLO CO": _company_doc([_point("2020-01", oil=3.0)])}
    group_docs = aggregate_company_series_by_group(company_docs, {})
    assert "SOLO CO" in group_docs
    assert group_docs["SOLO CO"]["is_singleton"] is True
    assert group_docs["SOLO CO"]["series"][0]["oil_mbd"]["value"] == 3.0


def test_aggregate_company_series_by_group_partial_status_when_one_constituent_unavailable():
    company_docs = {
        "ALPHA CO": _company_doc([_point("2020-01", oil=10.0, oil_status="complete")]),
        "BETA CO": _company_doc([_point("2020-01", oil=None, oil_status="unavailable")]),
    }
    entity_to_group = {"ALPHA CO": "GROUP", "BETA CO": "GROUP"}
    group_docs = aggregate_company_series_by_group(company_docs, entity_to_group)
    entry = group_docs["GROUP"]["series"][0]
    # Alpha's real 10.0 is never dropped just because Beta is unavailable.
    assert entry["oil_mbd"]["value"] == 10.0
    assert entry["oil_mbd"]["status"] == "partial"


def test_aggregate_company_series_by_group_all_unavailable_is_none_not_zero():
    company_docs = {
        "ALPHA CO": _company_doc([_point("2020-01", oil=None, oil_status="unavailable")]),
    }
    group_docs = aggregate_company_series_by_group(company_docs, {})
    entry = group_docs["ALPHA CO"]["series"][0]
    assert entry["oil_mbd"]["value"] is None
    assert entry["oil_mbd"]["status"] == "unavailable"


def test_group_conservation_holds_exactly():
    company_docs = {
        "ALPHA CO": _company_doc([_point("2020-01", oil=10.0), _point("2020-02", oil=4.0)]),
        "BETA CO": _company_doc([_point("2020-01", oil=5.0)]),
        "SOLO CO": _company_doc([_point("2020-01", oil=1.0)]),
    }
    entity_to_group = {"ALPHA CO": "BIG GROUP", "BETA CO": "BIG GROUP"}
    group_docs = aggregate_company_series_by_group(company_docs, entity_to_group)
    diffs = validate_group_conservation(company_docs, group_docs, streams=["oil_mbd"])
    assert diffs["oil_mbd"] < 1e-9


def test_group_conservation_catches_a_real_mismatch():
    company_docs = {"ALPHA CO": _company_doc([_point("2020-01", oil=10.0)])}
    # Tampered group doc that doesn't match the company doc - simulates a
    # real aggregation bug.
    group_docs = {
        "ALPHA CO": {
            "series": [
                {
                    "oil_mbd": {"value": 999.0, "status": "complete"},
                    "dry_gas_mmscfd": {"value": None, "status": "not_applicable"},
                }
            ]
        }
    }
    try:
        validate_group_conservation(company_docs, group_docs, streams=["oil_mbd"])
        assert False, "must raise when group total does not match legal-entity total"
    except CompanyGroupsError as e:
        assert "oil_mbd" in str(e)


# ---------------------------------------------------------------------------
# Regression: distinct_current_display_groups must not present unresolved
# singleton fallbacks as if they were approved company groups (spec
# review, 2026-09-10: the figure previously read 219 when only 37 were
# genuine NSTA-approved groups, the rest being one fallback "group" per
# unresolved entity).
# ---------------------------------------------------------------------------


def test_grouping_report_separates_approved_from_unresolved_fallback_groups():
    known = {"RESOLVED CO", "SOLO CO A", "SOLO CO B", "SOLO CO C"}
    resolution = {"RESOLVED CO": {"groups": {"BIG GROUP": 1}, "ambiguous_row_count": 0}}
    mapping = build_company_groups_mapping(known, resolution, "src", "2026-09-10")
    group_docs = aggregate_company_series_by_group(
        {e: {"series": []} for e in known},
        {row["source_legal_entity"]: row["current_display_group"] for row in mapping},
    )
    report = build_grouping_review_report(mapping, group_docs, latest_period="2026-01")

    # One real approved group ("BIG GROUP"); three unresolved singleton
    # fallbacks (each entity is its own "group" of one).
    assert report["distinct_approved_groups"] == 1
    assert report["unresolved_fallback_count"] == 3
    # The combined figure is retained for backward compatibility, but
    # must never be mistaken for "distinct approved company groups".
    assert report["distinct_current_display_groups"] == 4
    assert report["approved_count"] == 1
    assert report["unresolved_count"] == 3
    assert report["reviewed_manual_mapping_count"] == 0
    assert report["excluded_count"] == 0


def test_grouping_report_against_real_repository_scale_bug_reproduction():
    """Reproduces the exact real-data shape that surfaced the bug: many
    unresolved entities, few approved groups - distinct_approved_groups
    must be far smaller than distinct_current_display_groups."""
    known = {f"UNRESOLVED CO {i}" for i in range(50)} | {"ENTITY A", "ENTITY B", "ENTITY C"}
    resolution = {
        "ENTITY A": {"groups": {"GROUP X": 1}, "ambiguous_row_count": 0},
        "ENTITY B": {"groups": {"GROUP X": 1}, "ambiguous_row_count": 0},
        "ENTITY C": {"groups": {"GROUP Y": 1}, "ambiguous_row_count": 0},
    }
    mapping = build_company_groups_mapping(known, resolution, "src", "2026-09-10")
    group_docs = aggregate_company_series_by_group(
        {e: {"series": []} for e in known},
        {row["source_legal_entity"]: row["current_display_group"] for row in mapping},
    )
    report = build_grouping_review_report(mapping, group_docs, latest_period="2026-01")

    assert report["distinct_approved_groups"] == 2  # GROUP X, GROUP Y
    assert report["unresolved_fallback_count"] == 50
    assert report["distinct_current_display_groups"] == 52
    # The bug: presenting 52 as "distinct company groups" would be wrong;
    # 2 is the real answer.
    assert report["distinct_approved_groups"] < report["distinct_current_display_groups"]
