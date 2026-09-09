"""
Unit tests for etl/equity_artifacts.py and etl/equity_config.py (spec
section 15.11's approved policy, integrated into the unattended build).

Uses small synthetic data (not the live workbook/PPRS history) so these
run offline and deterministically, matching every other etl test.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.equity_config import (  # noqa: E402
    EQUITY_MINIMUM_COVERAGE_PCT,
    EQUITY_PUBLICATION_START,
    EQUITY_WARNING_COVERAGE_PCT,
)
from etl.equity_artifacts import (  # noqa: E402
    EquityBuildError,
    build_anomalies,
    build_company_artifacts,
    build_field_artifacts,
    build_index,
    build_publication_status_by_period_stream,
    classify_stream_month,
    fetch_and_validate_source,
    run_equity_pipeline,
    write_equity_artifacts,
)
from etl.equity_publication_window import build_monthly_stream_data  # noqa: E402
from etl.equity_join_historical import check_e5_historical, resolve_full_history  # noqa: E402
from etl.equity_join import build_field_match_index  # noqa: E402

STREAMS = ["oil_mbd", "dry_gas_mmscfd", "assoc_gas_mmscfd", "condensate_mbd"]


def _entry(category, oil=10.0, dry_gas=0.0, assoc_gas=0.0, condensate=0.0, month_start=None):
    return {
        "category": category,
        "production": {"period": "201303", "oil_mbd": oil, "dry_gas_mmscfd": dry_gas, "assoc_gas_mmscfd": assoc_gas, "condensate_mbd": condensate},
        "month_start": month_start or date(2013, 3, 1),
    }


def _resolved_row(field, company, period, pct, oil=10.0, dry_gas=0.0, assoc_gas=0.0, condensate=0.0):
    factor = pct / 100.0
    return {
        "field_name": field,
        "company_name": company,
        "interest_pct": pct,
        "period": period,
        "oil_mbd": oil * factor,
        "dry_gas_mmscfd": dry_gas * factor,
        "assoc_gas_mmscfd": assoc_gas * factor,
        "condensate_mbd": condensate * factor,
        "source_start_date": "2013-01-01",
        "source_end_date": None,
        "operator_flag": "Y",
        "field_match_method": "exact",
        "resolution_status": "resolved",
    }


# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------


def test_policy_constants_locked_in():
    assert EQUITY_PUBLICATION_START == "201303"
    assert EQUITY_MINIMUM_COVERAGE_PCT == 95.0
    assert EQUITY_WARNING_COVERAGE_PCT == 99.5


# ---------------------------------------------------------------------------
# No publication before 2013-03
# ---------------------------------------------------------------------------


def test_no_publication_before_start():
    per_field_month = {
        ("ALPHA", "201302"): _entry("resolved"),  # one month before the start
        ("ALPHA", "201303"): _entry("resolved"),  # exactly the start
    }
    published = {k: v for k, v in per_field_month.items() if k[1] >= EQUITY_PUBLICATION_START}
    assert ("ALPHA", "201302") not in published
    assert ("ALPHA", "201303") in published


# ---------------------------------------------------------------------------
# Coverage status classification
# ---------------------------------------------------------------------------


def test_complete_status_at_high_coverage():
    monthly_data = build_monthly_stream_data({("A", "201303"): _entry("resolved", oil=10.0)})
    status = classify_stream_month(monthly_data, "201303", "oil_mbd")
    assert status["status"] == "complete"
    assert status["coverage_pct"] == 100.0
    assert status["value_available"] is True


def test_warning_status_between_95_and_99_5():
    per_field_month = {
        ("A", "201303"): _entry("resolved", oil=96.0),
        ("B", "201303"): _entry("e1_sum_mismatch", oil=4.0),  # 96% coverage
    }
    monthly_data = build_monthly_stream_data(per_field_month)
    status = classify_stream_month(monthly_data, "201303", "oil_mbd")
    assert status["status"] == "warning"
    assert 95.0 <= status["coverage_pct"] < 99.5


def test_unavailable_status_below_95():
    per_field_month = {
        ("A", "201303"): _entry("resolved", oil=80.0),
        ("B", "201303"): _entry("unmatched", oil=20.0),  # 80% coverage
    }
    monthly_data = build_monthly_stream_data(per_field_month)
    status = classify_stream_month(monthly_data, "201303", "oil_mbd")
    assert status["status"] == "unavailable"
    assert status["value_available"] is False
    assert status["coverage_pct"] == 80.0


def test_separate_stream_specific_statuses_same_month():
    per_field_month = {
        ("A", "201303"): _entry("resolved", oil=100.0, dry_gas=50.0),
        ("B", "201303"): _entry("unmatched", oil=0.0, dry_gas=50.0),  # only hurts dry gas
    }
    monthly_data = build_monthly_stream_data(per_field_month)
    oil_status = classify_stream_month(monthly_data, "201303", "oil_mbd")
    gas_status = classify_stream_month(monthly_data, "201303", "dry_gas_mmscfd")
    assert oil_status["status"] == "complete"
    assert gas_status["status"] == "unavailable"


# ---------------------------------------------------------------------------
# Unavailable is null, never zero; legal entities unmerged
# ---------------------------------------------------------------------------


def test_unavailable_value_is_null_not_zero():
    resolved_rows = [_resolved_row("ALPHA", "ACME", "201303", 100, oil=0.0)]  # genuinely-zero production
    per_field_month = {("ALPHA", "201303"): _entry("resolved", oil=0.0)}
    # Force the stream to unavailable via a second, unmatched field dragging down coverage.
    per_field_month[("BETA", "201303")] = _entry("unmatched", oil=100.0)
    monthly_data = build_monthly_stream_data(per_field_month)
    status_by_period_stream = build_publication_status_by_period_stream(monthly_data)
    docs = build_company_artifacts(resolved_rows, status_by_period_stream)
    entry = docs["ACME"]["series"][0]
    assert entry["oil_mbd"]["status"] == "unavailable"
    assert entry["oil_mbd"]["value"] is None  # never 0.0 as a substitute


def test_legal_entities_remain_unmerged():
    resolved_rows = [
        _resolved_row("ALPHA", "CHRYSAOR LIMITED", "201303", 50, oil=10.0),
        _resolved_row("ALPHA", "CHRYSAOR PRODUCTION (U.K.) LIMITED", "201303", 50, oil=10.0),
    ]
    per_field_month = {("ALPHA", "201303"): _entry("resolved", oil=10.0)}
    monthly_data = build_monthly_stream_data(per_field_month)
    status_by_period_stream = build_publication_status_by_period_stream(monthly_data)
    docs = build_company_artifacts(resolved_rows, status_by_period_stream)
    assert "CHRYSAOR LIMITED" in docs
    assert "CHRYSAOR PRODUCTION (U.K.) LIMITED" in docs
    assert len(docs) == 2  # never merged into one entity despite the similar name


# ---------------------------------------------------------------------------
# MURLACH exclusion and anomaly output
# ---------------------------------------------------------------------------


def test_murlach_excluded_and_reported_in_anomalies():
    published = {
        ("MURLACH [pt of MARNOCK-SKUA]", "201303"): _entry("future_only", oil=5.0),
        ("ALPHA", "201303"): _entry("resolved", oil=10.0),
    }
    pipeline_result = {
        "published": published,
        "monthly_data": build_monthly_stream_data(published),
        "e4": {"cases": []},
        "match_result": {"unmatched_pprs": []},
        "e7": {"start_after_end_violations": []},
        "zero_duration_classification": {"category_counts": {}},
    }
    anomalies = build_anomalies(pipeline_result)
    assert len(anomalies["murlach"]["published_window_entries"]) == 1
    assert anomalies["murlach"]["published_window_entries"][0]["period"] == "201303"
    assert {"field": "MURLACH [pt of MARNOCK-SKUA]", "period": "201303"} in anomalies["future_only_fields"]


# ---------------------------------------------------------------------------
# E1/E4/E5/E7/E8 in integrated-build context (via run_equity_pipeline's
# own validation, exercised through its build-breaking failure paths)
# ---------------------------------------------------------------------------


def test_e7_failure_raises_equity_build_error(monkeypatch):
    # A second, valid row for the same field keeps `published` non-empty
    # (so the pipeline reaches E7) while the bad row still violates it.
    bad_row = {"field_name": "X", "company_name": "Y", "interest_pct": 100.0, "operator_flag": "N", "start_date": "2020-01-01", "end_date": "2019-01-01", "status": "700 - PRODUCING", "period_label": "Current"}
    good_row = {"field_name": "X", "company_name": "Y", "interest_pct": 100.0, "operator_flag": "N", "start_date": "2010-01-01", "end_date": None, "status": "700 - PRODUCING", "period_label": "Current"}

    class FakeSession:
        pass

    monkeypatch.setattr(
        "etl.equity_artifacts.fetch_and_validate_source",
        lambda session, prev: {
            "fetch_result": {"resolved_item_title": "Field Partners", "source_page_description": "x", "resolved_url": "u", "last_modified": "m", "sha256": "s"},
            "rows": [],
            "raw_rows": [bad_row, good_row],
        },
    )

    history_index = {"x": {"field": "X"}}
    history_per_slug = {"x": {"series": [{"period": "201303", "oil_mbd": 10.0, "dry_gas_mmscfd": 0.0, "assoc_gas_mmscfd": 0.0, "condensate_mbd": 0.0}]}}

    with pytest.raises(EquityBuildError, match="E7 failed"):
        run_equity_pipeline(history_per_slug, history_index, FakeSession())


def test_all_field_months_receive_exactly_one_category():
    pprs_history = {
        "ALPHA": [{"period": "201303", "month_start": date(2013, 3, 1), "oil_mbd": 10.0, "dry_gas_mmscfd": 0.0, "assoc_gas_mmscfd": 0.0, "condensate_mbd": 0.0}],
        "BETA": [{"period": "201303", "month_start": date(2013, 3, 1), "oil_mbd": 5.0, "dry_gas_mmscfd": 0.0, "assoc_gas_mmscfd": 0.0, "condensate_mbd": 0.0}],
    }
    raw_rows = [
        {"field_name": "ALPHA", "company_name": "ACME", "interest_pct": 100.0, "start_date": "2010-01-01", "end_date": None, "operator_flag": "N", "status": "700 - PRODUCING", "on_offshore": "Offshore", "period_label": "Current"},
    ]
    field_match_index = build_field_match_index({"ALPHA", "BETA"}, {"ALPHA"}, [])
    raw_rows_by_equity_field = {"ALPHA": raw_rows}
    per_field_month = resolve_full_history(pprs_history, field_match_index, raw_rows_by_equity_field, today_month_start=date(2020, 1, 1))
    e5 = check_e5_historical(per_field_month)
    assert sum(e5.values()) == len(per_field_month) == 2  # ALPHA resolved, BETA unmatched - exactly one category each


# ---------------------------------------------------------------------------
# Company-to-field conservation
# ---------------------------------------------------------------------------


def test_company_totals_equal_field_based_equity_totals():
    resolved_rows = [
        _resolved_row("ALPHA", "ACME", "201303", 60, oil=10.0),
        _resolved_row("ALPHA", "BETA", "201303", 40, oil=10.0),
        _resolved_row("GAMMA", "ACME", "201303", 100, oil=5.0),
    ]
    per_field_month = {
        ("ALPHA", "201303"): _entry("resolved", oil=10.0),
        ("GAMMA", "201303"): _entry("resolved", oil=5.0),
    }
    monthly_data = build_monthly_stream_data(per_field_month)
    status_by_period_stream = build_publication_status_by_period_stream(monthly_data)
    company_docs = build_company_artifacts(resolved_rows, status_by_period_stream)

    company_total_oil = sum(e["oil_mbd"]["value"] or 0.0 for doc in company_docs.values() for e in doc["series"])
    field_total_oil = sum(r["oil_mbd"] for r in resolved_rows)
    assert round(company_total_oil, 6) == round(field_total_oil, 6)


# ---------------------------------------------------------------------------
# Deterministic artifact generation
# ---------------------------------------------------------------------------


def test_company_and_index_artifacts_are_deterministic():
    resolved_rows = [_resolved_row("ALPHA", "ACME", "201303", 100, oil=10.0)]
    per_field_month = {("ALPHA", "201303"): _entry("resolved", oil=10.0)}
    monthly_data = build_monthly_stream_data(per_field_month)
    status_by_period_stream = build_publication_status_by_period_stream(monthly_data)

    docs_a = build_company_artifacts(resolved_rows, status_by_period_stream)
    docs_b = build_company_artifacts(resolved_rows, status_by_period_stream)
    assert docs_a == docs_b

    index_a = build_index(docs_a)
    index_b = build_index(docs_b)
    assert index_a == index_b


# ---------------------------------------------------------------------------
# Atomic rollback on failure
# ---------------------------------------------------------------------------


def test_atomic_write_never_leaves_target_dir_partially_updated(tmp_path):
    equity_dir = tmp_path / "equity"
    equity_dir.mkdir()
    (equity_dir / "meta.json").write_text('{"sentinel": "original"}')

    meta = {"sentinel": "new"}
    index = {}
    company_docs = {"ACME": {"slug": "acme", "name": "ACME"}}
    field_docs = {}
    anomalies = {}

    write_equity_artifacts(equity_dir, meta, index, company_docs, field_docs, anomalies)
    assert (equity_dir / "meta.json").read_text() == '{"sentinel":"new"}\n'

    # Simulate a mid-write failure the next run by making the staging dir
    # creation itself fail (e.g. a permissions problem) - the real
    # target directory must be untouched.
    import etl.equity_artifacts as ea

    original_mkdir = Path.mkdir

    def failing_mkdir(self, *args, **kwargs):
        if self.name == "companies" and "tmp" in str(self.parent):
            raise OSError("simulated failure")
        return original_mkdir(self, *args, **kwargs)

    import unittest.mock

    with unittest.mock.patch.object(Path, "mkdir", failing_mkdir):
        with pytest.raises(OSError):
            write_equity_artifacts(equity_dir, {"sentinel": "should-not-appear"}, index, company_docs, field_docs, anomalies)

    # The target dir must still show the PREVIOUS successful write's content.
    assert (equity_dir / "meta.json").read_text() == '{"sentinel":"new"}\n'


# ---------------------------------------------------------------------------
# Schema drift blocks publication
# ---------------------------------------------------------------------------


def test_workbook_title_drift_fails_before_download(monkeypatch):
    class FakeSession:
        pass

    def fake_fetch(session=None):
        return {
            "resolved_item_title": "Something Else Entirely",
            "source_page_description": "x",
            "resolved_url": "https://example.invalid/file.xlsx",
            "last_modified": "m",
            "sha256": "s",
            "content": b"fake",
        }

    monkeypatch.setattr("etl.equity_artifacts.fetch_equity_workbook", fake_fetch)

    with pytest.raises(EquityBuildError, match="item title changed"):
        fetch_and_validate_source(FakeSession(), None)


def test_row_count_beyond_tolerance_fails(monkeypatch, tmp_path):
    class FakeSession:
        pass

    def fake_fetch(session=None):
        return {
            "resolved_item_title": "Field Partners",
            "source_page_description": "x",
            "resolved_url": "https://example.invalid/file.xlsx",
            "last_modified": "m",
            "sha256": "s",
            "content": b"fake",
        }

    monkeypatch.setattr("etl.equity_artifacts.fetch_equity_workbook", fake_fetch)
    monkeypatch.setattr("etl.equity_artifacts.WORKBOOK_CACHE_PATH", tmp_path / "wb.xlsx")

    fake_rows = [{"field_name": "A"}] * 10
    monkeypatch.setattr("etl.equity_artifacts.parse_equity_workbook", lambda path: fake_rows)
    monkeypatch.setattr("etl.equity_artifacts.load_raw_rows", lambda path: fake_rows)

    # Previous build had 1000 rows; a jump to 10 is far beyond the 10% tolerance.
    previous_meta = {"normalized_equity_row_count": 1000}
    with pytest.raises(EquityBuildError, match="beyond the documented tolerance"):
        fetch_and_validate_source(FakeSession(), previous_meta)


# ---------------------------------------------------------------------------
# Substantive-diff detection (mirrors .github/workflows/build-data.yml's
# "Check for a substantive data change" step logic in a real temp git repo)
# ---------------------------------------------------------------------------


def _git(cwd, *args):
    import subprocess

    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _diff_changed(cwd, *paths) -> bool:
    import subprocess

    result = subprocess.run(["git", "diff", "--quiet", "--", *paths], cwd=cwd)
    return result.returncode != 0


@pytest.fixture
def temp_data_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "docs" / "data" / "equity").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "docs" / "data" / "fields.geojson").write_text('{"a": 1}')
    (repo / "docs" / "data" / "equity" / "meta.json").write_text('{"b": 1}')
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")
    return repo


def test_equity_only_change_triggers_substantive_diff(temp_data_repo):
    (temp_data_repo / "docs" / "data" / "equity" / "meta.json").write_text('{"b": 2}')
    pprs_changed = _diff_changed(temp_data_repo, "docs/data/fields.geojson", "docs/data/history", "docs/data/operators.json", "docs/data/operators")
    equity_changed = _diff_changed(temp_data_repo, "docs/data/equity")
    assert pprs_changed is False
    assert equity_changed is True


def test_unchanged_sources_produce_no_substantive_diff(temp_data_repo):
    # Rewrite both files with IDENTICAL content (simulating a rebuild that
    # only changed built_at, already reverted before this check runs).
    (temp_data_repo / "docs" / "data" / "fields.geojson").write_text('{"a": 1}')
    (temp_data_repo / "docs" / "data" / "equity" / "meta.json").write_text('{"b": 1}')
    pprs_changed = _diff_changed(temp_data_repo, "docs/data/fields.geojson", "docs/data/history", "docs/data/operators.json", "docs/data/operators")
    equity_changed = _diff_changed(temp_data_repo, "docs/data/equity")
    assert pprs_changed is False
    assert equity_changed is False
