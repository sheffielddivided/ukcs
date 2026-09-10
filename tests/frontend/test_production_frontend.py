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

import json

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
    # Explicit pfreq=monthly - annual average is the default frequency
    # (2026-09-10 continuation, see test_annual_average_is_the_default_
    # frequency_on_a_plain_load below); this test is about the SPLIT
    # default (commodity), so it pins frequency to keep asserting the
    # original three-month series.
    page = load_app("pfreq=monthly")
    page.wait_for_selector("#production-stats details")
    option = page.evaluate("() => window.__echartsCharts['production-chart']")
    names = [s["name"] for s in option["series"]]
    assert names == ["Liquids", "Natural gas", "Total"]
    assert option["series"][0]["data"] == [10.0, 11.0, 12.0]
    assert option["series"][1]["data"] == [5.0, 5.0, 6.0]
    assert option["series"][2]["data"] == [15.0, 16.0, 18.0]


def test_annual_average_is_the_default_frequency_on_a_plain_load(load_app):
    """Regression test (2026-09-10 continuation): annual average must be
    selected by default, with no `pfreq` param needed in the URL - a
    plain load already shows one averaged point per year, matching the
    "annual" radio being pre-checked."""
    page = load_app("")
    page.wait_for_selector("#production-stats details")
    assert "pfreq=" not in page.url
    assert page.locator('input[name="pfreq"][value="annual"]').is_checked()
    option = page.evaluate("() => window.__echartsCharts['production-chart']")
    # All three fixture months (202401-202403) fall in 2024, so the
    # default annual grain must collapse them into exactly one averaged
    # point, with no further interaction required.
    assert option["xAxis"]["data"] == ["2024"]
    liquids, gas, total = (s["data"] for s in option["series"])
    assert liquids == [11.0]  # (10+11+12)/3
    assert gas == [pytest.approx(5.333, abs=0.001)]  # (5+5+6)/3
    assert total == [pytest.approx(16.333, abs=0.001)]  # (15+16+18)/3
    # Annual being the DEFAULT means it is never called out as an active
    # (non-default) filter - only explicitly choosing Monthly is.
    assert "Annual average" not in page.locator("#production-active-filters").text_content()


def test_switching_to_monthly_shows_the_original_series_and_is_recorded_in_the_url(load_app):
    page = load_app("psplit=commodity")
    page.wait_for_selector("#production-stats details")
    page.check('input[name="pfreq"][value="monthly"]')
    page.wait_for_timeout(200)
    assert "pfreq=monthly" in page.url  # the non-default choice is the one written
    assert "Monthly" in page.locator("#production-active-filters").text_content()
    option = page.evaluate("() => window.__echartsCharts['production-chart']")
    assert option["series"][2]["data"] == [15.0, 16.0, 18.0]

    # Switching back to annual (the default) clears pfreq from the URL.
    page.check('input[name="pfreq"][value="annual"]')
    page.wait_for_timeout(200)
    assert "pfreq=" not in page.url


def test_annual_average_field_split_still_reconciles_to_total(load_app):
    page = load_app("psplit=field&pfreq=annual")
    page.wait_for_selector("#production-stats details")
    option = page.evaluate("() => window.__echartsCharts['production-chart']")
    series_by_name = {s["name"]: s["data"] for s in option["series"]}
    assert option["xAxis"]["data"] == ["2024"]
    total = series_by_name["Total"][0]
    displayed_sum = (
        series_by_name["Alpha Field"][0] + series_by_name["Beta Field"][0] + series_by_name["Other fields"][0]
    )
    assert abs(displayed_sum - total) < 0.01


def test_annual_average_company_split_shows_one_point_per_year(load_app):
    page = load_app("psplit=company&pfreq=annual")
    page.wait_for_selector("#production-stats details")
    option = page.evaluate("() => window.__echartsCharts['production-chart']")
    assert option["xAxis"]["data"] == ["2024"]
    alpha = next(s for s in option["series"] if s["name"] == "Alpha Group")
    assert alpha["data"] == [pytest.approx(8.667, abs=0.001)]  # (8.0+8.5+9.5)/3


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


# --- Single-company category split (2026-09-10 continuation) -------------
# Selecting exactly one company in "By company" used to leave the chart
# showing a single undifferentiated Total bar. It must now split into
# categories - By field (default) or Oil vs Gas.


def test_single_company_selection_defaults_to_by_field_breakdown(load_app):
    page = load_app("")
    page.wait_for_selector("#production-stats details")
    page.click('button[data-split="company"]')
    page.wait_for_timeout(200)
    page.select_option("#pf-company", "Alpha Group")
    page.wait_for_timeout(400)  # extra async fetch (company_groups_field_breakdown.json)

    assert "pcat=" not in page.url  # by field is the default, no URL param needed
    category_box = page.locator("#production-category-toggle")
    assert not category_box.is_hidden()
    assert category_box.locator('input[name="pcat"][value="field"]').is_checked()

    option = page.evaluate("() => window.__echartsCharts['production-chart']")
    series_by_name = {s["name"]: s["data"] for s in option["series"]}
    assert set(series_by_name) == {"ALPHA FIELD", "BETA FIELD"}
    # Annual average is ALSO the default - one point per year (2024), and
    # the two fields' averaged values must sum to Alpha Group's own
    # averaged total ((8.0+8.5+9.5)/3 = 8.667 mboe/d).
    assert option["xAxis"]["data"] == ["2024"]
    assert series_by_name["ALPHA FIELD"][0] + series_by_name["BETA FIELD"][0] == pytest.approx(8.667, abs=0.001)


def test_single_company_selection_can_switch_to_oil_vs_gas(load_app):
    page = load_app("")
    page.wait_for_selector("#production-stats details")
    page.click('button[data-split="company"]')
    page.wait_for_timeout(200)
    page.select_option("#pf-company", "Alpha Group")
    page.wait_for_timeout(400)

    page.check('input[name="pcat"][value="commodity"]')
    page.wait_for_timeout(200)
    assert "pcat=commodity" in page.url
    assert "Oil vs Gas" in page.locator("#production-active-filters").text_content()

    option = page.evaluate("() => window.__echartsCharts['production-chart']")
    series_by_name = {s["name"]: s["data"] for s in option["series"]}
    assert set(series_by_name) == {"Liquids", "Natural gas"}
    # Alpha Group's own liquids/gas averaged over 2024: (5.0+5.5+6.0)/3,
    # (3.0+3.0+3.5)/3.
    assert series_by_name["Liquids"][0] == pytest.approx(5.5, abs=0.001)
    assert series_by_name["Natural gas"][0] == pytest.approx(3.167, abs=0.001)


def test_multiple_companies_selected_never_shows_the_category_toggle(load_app):
    page = load_app("psplit=company")
    page.wait_for_selector("#production-stats details")
    assert page.locator("#production-category-toggle").is_hidden()
    option = page.evaluate("() => window.__echartsCharts['production-chart']")
    names = {s["name"] for s in option["series"]}
    assert names == {"Alpha Group", "Unresolved legal entities"}


def test_single_legal_entity_selection_has_no_by_field_option(load_app):
    """company_groups_field_breakdown.json is only published at GROUP
    grain - at legal-entity grain, By field must never be silently
    offered against data that doesn't exist; the toggle falls back to
    Oil vs Gas only, with the By field option disabled."""
    page = load_app("")
    page.wait_for_selector("#production-stats details")
    page.click('button[data-split="company"]')
    page.wait_for_timeout(200)
    page.check('input[name="pgrain"][value="entity"]')
    page.wait_for_timeout(200)
    page.select_option("#pf-company", "Gamma Co")
    page.wait_for_timeout(300)

    category_box = page.locator("#production-category-toggle")
    assert not category_box.is_hidden()
    assert category_box.locator('input[name="pcat"][value="commodity"]').is_checked()
    assert category_box.locator('input[name="pcat"][value="field"]').is_disabled()

    option = page.evaluate("() => window.__echartsCharts['production-chart']")
    names = {s["name"] for s in option["series"]}
    assert names == {"Liquids", "Natural gas"}


def test_single_company_field_breakdown_caps_to_top_10_plus_other(load_app, page):
    """Regression test (2026-09-10 continuation): a company with more
    than 10 fields must show only its 10 largest (by latest total_mboed),
    the rest folded into one "Other fields" bar - defined the same
    subtractive way (company total minus displayed top 10) as the
    UKCS-wide By field split's own "Other fields", so it reconciles
    exactly regardless of how many fields are excluded."""

    def _flat_field_doc(name, value):
        return {
            "slug": name.lower().replace(" ", "-"),
            "name": name,
            "series": [
                {
                    "period": p,
                    "liquids_mboed": {"value": round(value * 0.6, 3), "status": "complete"},
                    "natural_gas_mboed": {"value": round(value * 0.4, 3), "status": "complete"},
                    "total_mboed": {"value": value, "status": "complete"},
                }
                for p in ["202401", "202402", "202403"]
            ],
        }

    top_field_values = [
        ("FIELD 1", 1.5), ("FIELD 2", 1.2), ("FIELD 3", 1.0), ("FIELD 4", 0.9), ("FIELD 5", 0.8),
        ("FIELD 6", 0.7), ("FIELD 7", 0.6), ("FIELD 8", 0.5), ("FIELD 9", 0.4), ("FIELD 10", 0.3),
    ]
    excluded_field_values = [("FIELD 11", 0.2), ("FIELD 12", 0.1)]
    breakdown = {
        "Alpha Group": {
            name: _flat_field_doc(name, v) for name, v in top_field_values + excluded_field_values
        }
    }
    page.route(
        "**/data/overview/company_groups_field_breakdown.json",
        lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(breakdown)),
    )

    load_app("")
    page.wait_for_selector("#production-stats details")
    page.click('button[data-split="company"]')
    page.wait_for_timeout(200)
    page.select_option("#pf-company", "Alpha Group")
    page.wait_for_timeout(400)

    option = page.evaluate("() => window.__echartsCharts['production-chart']")
    series_by_name = {s["name"]: s["data"] for s in option["series"]}
    assert set(series_by_name) == {name for name, _ in top_field_values} | {"Other fields"}
    assert "FIELD 11" not in series_by_name
    assert "FIELD 12" not in series_by_name
    # Other fields = Alpha Group's own published total_mboed (8.0/8.5/9.5)
    # minus the top-10 sum (7.9 every period), annual-averaged:
    # ((8.0-7.9)+(8.5-7.9)+(9.5-7.9))/3 = (0.1+0.6+1.6)/3.
    assert series_by_name["Other fields"][0] == pytest.approx(0.767, abs=0.001)
    assert "top 10 shown, rest grouped as Other" in page.locator("#production-summary").text_content()

    note = page.locator("#production-other-note")
    assert not note.is_hidden()
    assert note.text_content() == "Other fields includes: FIELD 11, FIELD 12."
    assert_no_forbidden_requests(page)


def test_other_footnote_collapses_behind_details_when_the_list_is_long(load_app, page):
    """A long excluded list (more than 15 items) collapses behind
    <details> instead of dumping dozens of names straight onto the
    page - still fully present in the DOM, just not sprawled open by
    default."""

    def _flat_field_doc(name, value):
        return {
            "slug": name.lower().replace(" ", "-"),
            "name": name,
            "series": [
                {
                    "period": p,
                    "liquids_mboed": {"value": round(value * 0.6, 3), "status": "complete"},
                    "natural_gas_mboed": {"value": round(value * 0.4, 3), "status": "complete"},
                    "total_mboed": {"value": value, "status": "complete"},
                }
                for p in ["202401", "202402", "202403"]
            ],
        }

    # 10 large fields (shown) + 20 tiny ones (excluded - well over the
    # 15-item collapse threshold).
    field_values = [(f"BIG FIELD {i}", 10.0 - i * 0.1) for i in range(10)] + [
        (f"SMALL FIELD {i}", 0.01) for i in range(20)
    ]
    breakdown = {"Alpha Group": {name: _flat_field_doc(name, v) for name, v in field_values}}
    page.route(
        "**/data/overview/company_groups_field_breakdown.json",
        lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(breakdown)),
    )

    load_app("")
    page.wait_for_selector("#production-stats details")
    page.click('button[data-split="company"]')
    page.wait_for_timeout(200)
    page.select_option("#pf-company", "Alpha Group")
    page.wait_for_timeout(400)

    note = page.locator("#production-other-note")
    assert not note.is_hidden()
    assert note.locator("details summary").count() == 1
    assert "Other fields (20)" in note.locator("summary").text_content()
    full_text = note.text_content()
    assert "SMALL FIELD 0" in full_text
    assert "SMALL FIELD 19" in full_text
    assert "BIG FIELD 0" not in full_text
    assert_no_forbidden_requests(page)


def test_multiple_companies_capped_to_top_10_plus_other_companies(load_app, page):
    """Regression test (2026-09-10 continuation): showing every company
    (no single selection) must cap the chart to the 10 largest by
    latest total_mboed, folding the rest into one "Other companies" bar
    - a DIRECT sum of the excluded companies' own totals (there is no
    independent grand total at this grain to reconcile subtractively
    against, unlike the field-breakdown case)."""

    def _flat_group_doc(value, member):
        return {
            "member_entities": [member],
            "is_singleton": True,
            "series": [
                {
                    "period": p,
                    "liquids_mboed": {"value": round(value * 0.6, 3), "status": "complete"},
                    "natural_gas_mboed": {"value": round(value * 0.4, 3), "status": "complete"},
                    "total_mboed": {"value": value, "status": "complete"},
                }
                for p in ["202401", "202402", "202403"]
            ],
        }

    # Ranked by latest (202403) total_mboed: Alpha Group (9.5) > NewCo1..9
    # (7.0 down to 2.05) - the top 10 - then NewCo10 Group (1.9) and
    # Unresolved legal entities (1.8) - the 2 excluded, folded into
    # "Other companies".
    top_new_co_values = [7.0, 6.0, 5.0, 4.0, 3.0, 2.5, 2.2, 2.1, 2.05]
    groups = {
        "Alpha Group": {
            "member_entities": ["Alpha Co A", "Alpha Co B"],
            "is_singleton": False,
            "series": [
                {"period": "202401", "liquids_mboed": {"value": 5.0, "status": "complete"}, "natural_gas_mboed": {"value": 3.0, "status": "complete"}, "total_mboed": {"value": 8.0, "status": "complete"}},
                {"period": "202402", "liquids_mboed": {"value": 5.5, "status": "complete"}, "natural_gas_mboed": {"value": 3.0, "status": "complete"}, "total_mboed": {"value": 8.5, "status": "complete"}},
                {"period": "202403", "liquids_mboed": {"value": 6.0, "status": "complete"}, "natural_gas_mboed": {"value": 3.5, "status": "complete"}, "total_mboed": {"value": 9.5, "status": "complete"}},
            ],
        },
        "Unresolved legal entities": {
            "member_entities": ["Gamma Co"],
            "is_singleton": False,
            "series": [
                {"period": "202401", "liquids_mboed": {"value": 1.0, "status": "complete"}, "natural_gas_mboed": {"value": 0.5, "status": "complete"}, "total_mboed": {"value": 1.5, "status": "complete"}},
                {"period": "202402", "liquids_mboed": {"value": 1.0, "status": "complete"}, "natural_gas_mboed": {"value": 0.5, "status": "complete"}, "total_mboed": {"value": 1.5, "status": "complete"}},
                {"period": "202403", "liquids_mboed": {"value": 1.2, "status": "complete"}, "natural_gas_mboed": {"value": 0.6, "status": "complete"}, "total_mboed": {"value": 1.8, "status": "complete"}},
            ],
        },
        **{
            f"NewCo{i} Group": _flat_group_doc(v, f"NewCo{i} Co")
            for i, v in enumerate(top_new_co_values, start=1)
        },
        "NewCo10 Group": _flat_group_doc(1.9, "NewCo10 Co"),
    }
    page.route(
        "**/data/overview/company_groups.json",
        lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(groups)),
    )

    load_app("")
    page.wait_for_selector("#production-stats details")
    page.click('button[data-split="company"]')
    page.wait_for_timeout(300)

    assert page.locator("#production-category-toggle").is_hidden()
    option = page.evaluate("() => window.__echartsCharts['production-chart']")
    series_by_name = {s["name"]: s["data"] for s in option["series"]}
    expected_top = {"Alpha Group"} | {f"NewCo{i} Group" for i in range(1, 10)}
    assert set(series_by_name) == expected_top | {"Other companies"}
    assert "NewCo10 Group" not in series_by_name
    assert "Unresolved legal entities" not in series_by_name
    # Other companies = NewCo10 Group (1.9 every period) + Unresolved
    # legal entities (1.5/1.5/1.8), summed per month then annual-averaged:
    # ((1.9+1.5)+(1.9+1.5)+(1.9+1.8)) / 3 = 3.5.
    assert series_by_name["Other companies"][0] == pytest.approx(3.5, abs=0.001)
    assert "top 10 of 12 shown" in page.locator("#production-summary").text_content()

    note = page.locator("#production-other-note")
    assert not note.is_hidden()
    assert note.text_content() == "Other companies includes: NewCo10 Group, Unresolved legal entities."
    assert_no_forbidden_requests(page)


def test_field_split_top_n_plus_other_reconciles_to_ukcs_total(load_app):
    page = load_app("pfreq=monthly")  # pin monthly - annual is now the default
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
    # Nothing excluded - the footnote must not appear at all.
    assert page.locator("#production-other-note").is_hidden()


def test_field_split_other_footnote_names_the_excluded_fields(load_app):
    """Regression test (2026-09-10 continuation): whenever a chart has an
    "Other" bucket, a footnote below it must name exactly which
    fields/companies were folded into it."""
    page = load_app("psplit=field&pfields=alpha-field&pfreq=monthly")
    page.wait_for_selector("#production-stats details")
    option = page.evaluate("() => window.__echartsCharts['production-chart']")
    series_by_name = {s["name"] for s in option["series"]}
    assert series_by_name == {"Alpha Field", "Other fields", "Total"}

    note = page.locator("#production-other-note")
    assert not note.is_hidden()
    assert note.text_content() == "Other fields includes: Beta Field."
    assert_no_forbidden_requests(page)


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


def test_layout_hidden_attribute_actually_hides_it_not_just_the_dom_flag(load_app):
    """Regression test: #layout sets its own `display: flex` (needed for
    its sidebar/map/panel layout), which - being an author rule - always
    overrides the browser's built-in `[hidden] { display: none }`
    default regardless of selector specificity. Without a matching
    `#layout[hidden] { display: none }` override in docs/styles.css,
    main.js's `layout.hidden = true` had NO visual effect: the Fields
    map sidebar (#sidebar, #equity-company-input, etc) kept rendering
    underneath the Production/Licence portfolio view - a real
    "split-screen" bug none of this suite's other assertions caught,
    because the test harness did not load the real stylesheet at all
    until this fix (see conftest.py's serve_root)."""
    page = load_app("")
    page.wait_for_selector("#production-stats details")
    # Real computed style, not just the DOM `hidden` property/attribute.
    display = page.eval_on_selector("#layout", "el => getComputedStyle(el).display")
    assert display == "none"
    # The Fields-map-only sidebar must not be present in the render tree
    # at all while Production is the active view.
    assert page.locator("#sidebar").is_hidden()
    assert page.locator("#equity-company-input").is_hidden()


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
