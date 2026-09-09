"""
Unit tests for etl/arcgis.py pagination (spec section 8.2 / 13 step 2).

Uses a canned fixture (tests/fixtures/pprs_pagination_fixture.json) rather
than the live service, so these run offline and deterministically.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.arcgis import ArcGISError, query_all  # noqa: E402

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "pprs_pagination_fixture.json"


def _load_fixture() -> dict:
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def _make_session(pages: list[dict]) -> MagicMock:
    """A fake requests.Session whose .get() returns fixture pages in order,
    selecting the page by the resultOffset param it was called with."""
    page_size = len(pages[0]["features"]) if pages else 0

    def fake_get(url, params=None, timeout=None):
        offset = params["resultOffset"]
        index = offset // page_size if page_size else 0
        resp = MagicMock()
        resp.status_code = 200
        if index < len(pages):
            resp.json.return_value = pages[index]
        else:
            resp.json.return_value = {"features": [], "exceededTransferLimit": False}
        return resp

    session = MagicMock()
    session.get.side_effect = fake_get
    return session


def test_query_all_paginates_across_all_pages():
    fixture = _load_fixture()
    session = _make_session(fixture["pages"])

    features = list(
        query_all(
            "https://example.invalid/FeatureServer/0",
            max_record_count=fixture["page_size"],
            session=session,
        )
    )

    object_ids = [f["attributes"]["OBJECTID"] for f in features]
    assert object_ids == [1, 2, 3, 4, 5, 6, 7]
    # 3 pages requested: two full pages (exceededTransferLimit=true) plus
    # the short final page that terminates the loop.
    assert session.get.call_count == 3


def test_query_all_every_request_orders_by_objectid():
    fixture = _load_fixture()
    session = _make_session(fixture["pages"])

    list(
        query_all(
            "https://example.invalid/FeatureServer/0",
            max_record_count=fixture["page_size"],
            session=session,
        )
    )

    for call in session.get.call_args_list:
        params = call.kwargs["params"]
        assert params["orderByFields"] == "OBJECTID"


def test_query_all_keeps_paginating_when_exceeded_flag_true_even_if_page_short():
    """A page shorter than page_size with exceededTransferLimit still true
    must not be treated as the last page - only a short page with the flag
    false ends pagination (spec section 8.2)."""
    pages = [
        {
            "exceededTransferLimit": True,
            "features": [{"attributes": {"OBJECTID": 1}}],
        },
        {
            "exceededTransferLimit": False,
            "features": [{"attributes": {"OBJECTID": 2}}],
        },
    ]

    call_count = {"n": 0}

    def fake_get(url, params=None, timeout=None):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = pages[call_count["n"]]
        call_count["n"] += 1
        return resp

    session = MagicMock()
    session.get.side_effect = fake_get

    features = list(
        query_all(
            "https://example.invalid/FeatureServer/0",
            max_record_count=5,
            session=session,
        )
    )

    object_ids = [f["attributes"]["OBJECTID"] for f in features]
    assert object_ids == [1, 2]
    assert session.get.call_count == 2


def test_query_all_stops_on_empty_page():
    session = _make_session(
        [{"exceededTransferLimit": False, "features": []}]
    )

    features = list(
        query_all(
            "https://example.invalid/FeatureServer/0",
            max_record_count=10,
            session=session,
        )
    )
    assert features == []


def test_query_all_raises_when_hard_cap_exceeded():
    fixture = _load_fixture()
    session = _make_session(fixture["pages"])

    with pytest.raises(ArcGISError, match="hard cap"):
        list(
            query_all(
                "https://example.invalid/FeatureServer/0",
                max_record_count=fixture["page_size"],
                session=session,
                hard_cap=2,
            )
        )


def test_query_all_raises_on_arcgis_application_error():
    def fake_get(url, params=None, timeout=None):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "error": {"code": 400, "message": "Invalid field", "details": []}
        }
        return resp

    session = MagicMock()
    session.get.side_effect = fake_get

    with pytest.raises(ArcGISError, match="ArcGIS application error"):
        list(
            query_all(
                "https://example.invalid/FeatureServer/0",
                max_record_count=10,
                session=session,
            )
        )


def test_query_all_raises_distinct_message_on_http_500(monkeypatch):
    monkeypatch.setattr("etl.arcgis.RETRY_BACKOFF_BASE_SECONDS", 0)

    def fake_get(url, params=None, timeout=None):
        resp = MagicMock()
        resp.status_code = 503
        resp.text = "service unavailable"
        return resp

    session = MagicMock()
    session.get.side_effect = fake_get

    with pytest.raises(ArcGISError, match="HTTP 503"):
        list(
            query_all(
                "https://example.invalid/FeatureServer/0",
                max_record_count=10,
                session=session,
            )
        )
    assert session.get.call_count == 5  # MAX_RETRIES


def test_quote_where_value_quotes_strings_and_dates_not_numbers():
    from etl.arcgis import quote_where_value

    assert quote_where_value("esriFieldTypeString", "202606") == "'202606'"
    assert quote_where_value("esriFieldTypeDate", "2026-06-01") == "'2026-06-01'"
    assert quote_where_value("esriFieldTypeInteger", 202606) == "202606"
    assert quote_where_value("esriFieldTypeDouble", 1.5) == "1.5"


def test_quote_where_value_escapes_embedded_quotes():
    from etl.arcgis import quote_where_value

    assert quote_where_value("esriFieldTypeString", "O'BRIEN") == "'O''BRIEN'"
