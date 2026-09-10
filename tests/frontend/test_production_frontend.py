# Committed, CI-compatible frontend tests for the Production overview
# view (Deliverable 1, spec approved 2026-09-10 continuation). Run the
# real docs/app/production.js, urlstate.js, main.js against a small
# synthetic overview fixture (tests/frontend/fixtures/docs/data/overview/*):
# one approved group (Alpha Group, two member entities) and one collapsed
# "Unresolved legal entities" bucket, two fields (Alpha Field, Beta Field)
# whose total_mboed sums exactly to monthly_totals for every period.
#
# No live network access: same maplibre-gl/echarts stubbing as the rest
# of this suite (conftest.py). Production never touches maplibre-gl at
# all, but main.js still initialises the map underneath regardless of
# which top-level view is shown, so the same stub is required.

import pytest

from test_equity_frontend import assert_no_forbidden_requests


def test_production_is_the_default_view_on_a_plain_load(load_app):
    page = load_app("")  # explicitly empty hash - a genuine hash-less visit
    page.wait_for_selector("#production-stats details")
    assert page.locator("#view-production").is_visible()
    assert page.locator("#layout").is_hidden()
    assert page.locator("#top-nav-production").get_attribute("aria-current") == "page"
    assert_no_forbidden_requests(page)


def test_default_split_is_commodity_stacked_with_total_overlay(load_app):
    page = load_app("")
    page.wait_for_selector("#production-stats details")
    option = page.evaluate("() => window.__echartsCharts['production-chart']")
    names = [s["name"] for s in option["series"]]
    assert names == ["Liquids", "Natural gas", "Total"]
    assert option["series"][0]["data"] == [10.0, 11.0, 12.0]
    assert option["series"][1]["data"] == [5.0, 5.0, 6.0]
    assert option["series"][2]["data"] == [15.0, 16.0, 18.0]


def test_reconciled_grouping_statistics_are_shown_correctly(load_app):
    """Regression test for the fixed defect: distinct APPROVED groups
    must never be conflated with the unresolved singleton-fallback
    count (the old bug reported '219 distinct display groups')."""
    page = load_app("")
    page.wait_for_selector("#production-stats details")
    text = page.locator("#production-stats").text_content()
    assert "1 approved groups" in text or "Distinct approved company groups: 1" in text
    assert "Unresolved fallback count (one per unresolved entity, not real groups): 1" in text
    assert "Total legal entities: 3" in text
    assert "Approved current-group mappings: 2" in text
    assert "Unresolved legal entities: 1" in text


def test_switching_to_company_split_shows_retrospective_caveat(load_app):
    page = load_app("")
    page.wait_for_selector("#production-stats details")
    page.click('button[data-split="company"]')
    page.wait_for_timeout(200)
    caveat = page.locator("#production-caveat")
    assert not caveat.is_hidden()
    assert "does not represent company ownership structures at the time" in caveat.inner_text()


def test_company_split_default_grain_is_current_group_and_shows_unresolved_bucket(load_app):
    page = load_app("")
    page.wait_for_selector("#production-stats details")
    page.click('button[data-split="company"]')
    page.wait_for_timeout(200)
    option = page.evaluate("() => window.__echartsCharts['production-chart']")
    names = [s["name"] for s in option["series"]]
    assert "Alpha Group" in names
    assert "Unresolved legal entities" in names


def test_company_split_legal_entity_grain_shows_individual_entities_separately(load_app):
    page = load_app("")
    page.wait_for_selector("#production-stats details")
    page.click('button[data-split="company"]')
    page.wait_for_timeout(200)
    page.check('input[name="pgrain"][value="entity"]')
    page.wait_for_timeout(200)
    option = page.evaluate("() => window.__echartsCharts['production-chart']")
    names = set(s["name"] for s in option["series"])
    assert names == {"Alpha Co A", "Alpha Co B", "Gamma Co"}
    assert "top=" not in page.url or "psplit=company" in page.url
    assert "pgrain=entity" in page.url


def test_selecting_a_company_group_shows_drill_down_detail(load_app):
    page = load_app("")
    page.wait_for_selector("#production-stats details")
    page.click('button[data-split="company"]')
    page.wait_for_timeout(200)
    page.select_option("#pf-company", "Alpha Group")
    page.wait_for_timeout(200)
    detail = page.locator("#production-group-detail")
    text = detail.text_content()
    assert "Alpha Group" in text
    assert "approved (NSTA equity group)" in text
    assert "Alpha Co A" in text
    assert "Alpha Co B" in text


def test_field_split_top_n_plus_other_reconciles_to_ukcs_total(load_app):
    page = load_app("")
    page.wait_for_selector("#production-stats details")
    page.click('button[data-split="field"]')
    page.wait_for_timeout(200)
    option = page.evaluate("() => window.__echartsCharts['production-chart']")
    series_by_name = {s["name"]: s["data"] for s in option["series"]}
    assert "Alpha Field" in series_by_name
    assert "Beta Field" in series_by_name
    assert "Other fields" in series_by_name
    for i, total in enumerate([15.0, 16.0, 18.0]):
        displayed_sum = (
            series_by_name["Alpha Field"][i]
            + series_by_name["Beta Field"][i]
            + series_by_name["Other fields"][i]
        )
        assert abs(displayed_sum - total) < 0.01
    # Both fixture fields fit within the default Top 10, so nothing is
    # pushed into "Other fields".
    assert series_by_name["Other fields"] == [0.0, 0.0, 0.0]


def test_clear_filters_resets_date_range_and_selection(load_app):
    page = load_app("")
    page.wait_for_selector("#production-stats details")
    page.click('button[data-split="field"]')
    page.wait_for_timeout(200)
    page.fill("#pf-from", "202402")
    page.dispatch_event("#pf-from", "change")
    page.wait_for_timeout(200)
    assert "pfrom=202402" in page.url
    page.click("#pf-clear")
    page.wait_for_timeout(200)
    assert "pfrom=" not in page.url


def test_empty_result_shows_message_not_zero(load_app):
    page = load_app("")
    page.wait_for_selector("#production-stats details")
    page.fill("#pf-from", "209901")
    page.dispatch_event("#pf-from", "change")
    page.wait_for_timeout(200)
    empty = page.locator("#production-empty")
    assert not empty.is_hidden()
    assert "No data for selected filters" in empty.inner_text()
    assert page.locator("#production-chart").is_hidden()


def test_url_state_round_trips_split_and_grain_on_reload(load_app):
    page = load_app("psplit=company&pgrain=entity")
    page.wait_for_selector("#production-stats details")
    option = page.evaluate("() => window.__echartsCharts['production-chart']")
    names = set(s["name"] for s in option["series"])
    assert names == {"Alpha Co A", "Alpha Co B", "Gamma Co"}
    assert "active" in page.locator('button[data-split="company"]').get_attribute("class")


def test_switching_to_fields_map_hides_production_and_vice_versa(load_app):
    page = load_app("")
    page.wait_for_selector("#production-stats details")
    assert page.locator("#view-production").is_visible()
    assert page.locator("#layout").is_hidden()

    page.click("#top-nav-map")
    page.wait_for_timeout(200)
    assert page.locator("#layout").is_visible()
    assert page.locator("#view-production").is_hidden()
    assert "top=map" in page.url

    page.click("#top-nav-production")
    page.wait_for_timeout(200)
    assert page.locator("#view-production").is_visible()
    assert page.locator("#layout").is_hidden()
    assert_no_forbidden_requests(page)


def test_no_overview_artifacts_fetched_before_production_view_is_shown(load_app):
    """Fields map must never pay Production's overview-fetch cost - the
    Production module is only initialised when its view is actually
    shown (spec: each top-level view must fail/load independently)."""
    page = load_app("top=map")
    page.wait_for_timeout(300)
    overview_requests = [r for r in page.all_requests if "/data/overview/" in r]
    assert overview_requests == []


def test_legacy_deep_link_without_top_param_still_opens_fields_map(load_app):
    """A saved/shared link from before the Production view existed never
    carried a `top=` param - it must keep landing on the Fields map, not
    silently redirect to the new default."""
    page = load_app("view=equity&slug=does-not-exist")
    page.wait_for_timeout(300)
    assert page.locator("#layout").is_visible()
    assert page.locator("#view-production").is_hidden()
