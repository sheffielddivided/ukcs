"""
Unit tests for etl/equity_fetch.py (spec section 15.2 / 15.8 step 1).

Uses canned HTML/JSON fixtures rather than the live NSTA page and ArcGIS
search API, so these run offline and deterministically - same approach as
tests/test_arcgis.py.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.equity_fetch import (  # noqa: E402
    EquityFetchError,
    download_workbook,
    extract_hub_search_query,
    fetch_equity_workbook,
    find_equity_link,
    resolve_workbook_item,
)

FIXTURES = Path(__file__).parent / "fixtures"
PAGE_URL = "https://www.nstauthority.co.uk/data-and-insights/data/themes/fields/"


def _load_fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_find_equity_link_discovers_the_hub_search_url():
    html = _load_fixture_text("nsta_fields_page_with_equity_link.html")
    href = find_equity_link(html, PAGE_URL)
    assert href == "https://open-data-ukcs-transition.hub.arcgis.com/search?q=field%20partners"


def test_find_equity_link_fails_loudly_when_no_link_present():
    html = _load_fixture_text("nsta_fields_page_without_equity_link.html")
    with pytest.raises(EquityFetchError) as excinfo:
        find_equity_link(html, PAGE_URL)
    assert PAGE_URL in str(excinfo.value)
    assert "equity" in str(excinfo.value).lower()


def test_find_equity_link_fails_loudly_when_multiple_links_present():
    html = """
    <a href='https://open-data-ukcs-transition.hub.arcgis.com/search?q=field%20partners'>equity shares one</a>
    <a href='https://open-data-ukcs-transition.hub.arcgis.com/search?q=other'>historical equity data</a>
    """
    with pytest.raises(EquityFetchError) as excinfo:
        find_equity_link(html, PAGE_URL)
    assert "2 links" in str(excinfo.value)


def test_extract_hub_search_query_reads_q_param():
    href = "https://open-data-ukcs-transition.hub.arcgis.com/search?q=field%20partners"
    assert extract_hub_search_query(href) == "field partners"


def test_extract_hub_search_query_rejects_non_hub_url():
    with pytest.raises(EquityFetchError):
        extract_hub_search_query("https://example.invalid/some/direct/file.xlsx")


def _fake_response(json_data=None, content=b"", headers=None, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.content = content
    resp.text = content.decode() if isinstance(content, bytes) else content
    resp.headers = headers or {}
    return resp


def test_resolve_workbook_item_returns_the_single_match():
    import json

    fixture = json.loads((FIXTURES / "arcgis_search_field_partners.json").read_text())
    session = MagicMock()
    session.get.return_value = _fake_response(json_data=fixture)

    item = resolve_workbook_item("field partners", session)
    assert item["id"] == "40fb75005dca48e886891350da9dedd8"
    assert item["title"] == "Field Partners"
    assert item["url"] == "https://datanstauthority.blob.core.windows.net/external/Documents/field_partners.xlsx"


def test_resolve_workbook_item_fails_loudly_on_zero_results():
    import json

    fixture = json.loads((FIXTURES / "arcgis_search_zero_results.json").read_text())
    session = MagicMock()
    session.get.return_value = _fake_response(json_data=fixture)

    with pytest.raises(EquityFetchError) as excinfo:
        resolve_workbook_item("field partners", session)
    assert "zero results" in str(excinfo.value)


def test_resolve_workbook_item_fails_loudly_on_multiple_results():
    import json

    fixture = json.loads((FIXTURES / "arcgis_search_multiple_results.json").read_text())
    session = MagicMock()
    session.get.return_value = _fake_response(json_data=fixture)

    with pytest.raises(EquityFetchError) as excinfo:
        resolve_workbook_item("field partners", session)
    assert "2 results" in str(excinfo.value)
    assert "Refusing to guess" in str(excinfo.value)


def test_download_workbook_captures_bytes_and_last_modified():
    session = MagicMock()
    session.get.return_value = _fake_response(
        content=b"fake-xlsx-bytes",
        headers={"Last-Modified": "Wed, 09 Sep 2026 12:00:02 GMT"},
    )

    content, last_modified = download_workbook("https://example.invalid/file.xlsx", session)
    assert content == b"fake-xlsx-bytes"
    assert last_modified == "Wed, 09 Sep 2026 12:00:02 GMT"


def test_download_workbook_fails_loudly_on_empty_body():
    session = MagicMock()
    session.get.return_value = _fake_response(content=b"", headers={})

    with pytest.raises(EquityFetchError) as excinfo:
        download_workbook("https://example.invalid/file.xlsx", session)
    assert "0 bytes" in str(excinfo.value)


def test_fetch_equity_workbook_end_to_end_with_fixtures():
    """Full orchestration with a fake session that answers each of the
    three real HTTP calls (NSTA page, ArcGIS search, workbook download) in
    turn, never touching the network."""
    import json

    page_html = _load_fixture_text("nsta_fields_page_with_equity_link.html")
    search_json = json.loads((FIXTURES / "arcgis_search_field_partners.json").read_text())
    workbook_bytes = b"fake-workbook-bytes"

    page_response = _fake_response(content=page_html.encode())
    page_response.text = page_html  # find_equity_link reads resp.text, not resp.content

    session = MagicMock()
    session.headers = {}
    session.get.side_effect = [
        page_response,
        _fake_response(json_data=search_json),
        _fake_response(content=workbook_bytes, headers={"Last-Modified": "Wed, 09 Sep 2026 12:00:02 GMT"}),
    ]

    result = fetch_equity_workbook(session=session)

    assert result["resolved_item_id"] == "40fb75005dca48e886891350da9dedd8"
    assert result["resolved_url"] == "https://datanstauthority.blob.core.windows.net/external/Documents/field_partners.xlsx"
    assert result["last_modified"] == "Wed, 09 Sep 2026 12:00:02 GMT"
    assert result["content"] == workbook_bytes
    assert result["sha256"] == hashlib.sha256(workbook_bytes).hexdigest()
    assert result["content_length"] == len(workbook_bytes)
