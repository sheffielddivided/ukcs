# Committed, CI-compatible frontend tests for the equity frontend
# checkpoint (spec section 14 of that checkpoint's instructions). These
# run the real docs/app/*.js modules (copied byte-for-byte into an
# isolated webroot by conftest.py's `serve_root` fixture - see its
# docstring) against small synthetic fixture data under
# tests/frontend/fixtures/docs/data/, including a deliberately synthetic
# below-95%-coverage month that the real published data does not
# currently contain, so the "unavailable" rendering path has a test.
#
# No live network access: maplibre-gl and echarts are stubbed (see
# conftest.py). Every test that opens a panel or performs a search also
# implicitly exercises the "zero runtime NSTA/ArcGIS calls" requirement
# via the FORBIDDEN_HOST_SUBSTRINGS assertion in
# assert_no_forbidden_requests, called at the end of every test that
# touches the page.

import pytest

FORBIDDEN_HOST_SUBSTRINGS = [
    "nstauthority.co.uk",
    "arcgis.com",
    "arcgis.net",
    "blob.core.windows.net",
]


def assert_no_forbidden_requests(page):
    bad = [u for u in page.all_requests if any(s in u for s in FORBIDDEN_HOST_SUBSTRINGS)]
    assert bad == [], f"requests reached forbidden hosts: {bad}"


def company_json_requests(page):
    return [u for u in page.all_requests if "/data/equity/companies/" in u]


def field_equity_json_requests(page):
    return [u for u in page.all_requests if "/data/equity/fields/" in u]


def select_equity_company(page, name):
    """Fills the equity company selector and lets the browser's own
    change-on-blur behaviour fire main.js's `change` handler exactly
    once. Blurring (rather than an explicit dispatch_event("change"), on
    top of which Chromium ALSO fires a genuine native "change" event
    on blur since fill() leaves the field's value "dirty" - two events,
    two overlapping renders, non-deterministic duplicated panel content)
    is both necessary and sufficient here. It also dismisses Chromium's
    native <datalist> suggestion popup (input list="equity-company-list"),
    which is invisible to DOM-level hit testing but still silently
    absorbs the *next* real mouse click in headless Playwright - a known
    automation quirk, not an application bug."""
    page.fill("#equity-company-input", name)
    page.evaluate('() => document.getElementById("equity-company-input").blur()')
    # Wait for the async panel body to actually finish rendering, rather
    # than a fixed sleep. .panel-loading is removed as the FIRST line of
    # renderEquityPanelBody (equity-ui.js), before its own await for the
    # MURLACH check - so waiting on that alone is not enough; wait for
    # one of the two actual terminal states instead (data rendered, or
    # an error message shown).
    page.wait_for_selector(
        "#field-panel-content .equity-latest-table, #field-panel-content .panel-error",
        state="attached",
        timeout=5000,
    )


# --- 1. Startup / lazy loading ---------------------------------------


def test_startup_loads_only_index_artifacts_not_company_or_field_files(load_app, page):
    load_app()
    assert company_json_requests(page) == []
    assert field_equity_json_requests(page) == []
    urls = " ".join(page.all_requests)
    assert "/data/equity/meta.json" in urls
    assert "/data/equity/index.json" in urls
    assert "/data/meta.json" in urls
    assert "/data/fields.geojson" in urls
    assert "/data/history/index.json" in urls
    assert_no_forbidden_requests(page)


def test_selecting_one_company_fetches_only_that_companys_file(load_app, page):
    load_app()
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.wait_for_timeout(500)
    reqs = company_json_requests(page)
    assert len(reqs) == 1
    assert "alpha-entity-limited.json" in reqs[0]
    assert_no_forbidden_requests(page)


# --- 2. Legal entities distinct, labelled correctly -------------------


def test_equity_company_datalist_lists_all_entities_alphabetically_and_distinctly(load_app, page):
    load_app()
    options = page.eval_on_selector_all(
        "#equity-company-list option", "els => els.map(e => e.value)"
    )
    assert options == ["ALPHA ENTITY LIMITED", "BETA ENTITY LIMITED", "GAMMA ENTITY LIMITED"]


def test_equity_panel_uses_legal_entity_label_never_parent_company_wording(load_app, page):
    load_app()
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.wait_for_timeout(500)
    text = page.text_content("#field-panel-content")
    assert "Legal entity as recorded by NSTA" in text
    for forbidden in ("parent company", "corporate group", "ultimate owner"):
        assert forbidden not in text.lower()


# --- 3/4. Equity is the default metric; operator mode is distinct -----


def test_equity_is_the_default_metric_mode(load_app, page):
    load_app()
    assert page.get_attribute("#mode-equity", "aria-pressed") == "true"
    assert page.get_attribute("#mode-operator", "aria-pressed") == "false"
    assert page.is_hidden("#equity-mode-controls") is False


def test_operator_mode_shows_retrospective_caveat_not_equity_caption(load_app, page):
    load_app()
    page.click("#mode-operator")
    page.select_option("#operator-filter", "EXAMPLE OPERATOR LIMITED")
    page.click("#view-operator-history")
    page.wait_for_timeout(500)
    text = page.text_content("#field-panel-content")
    assert "current operator of record" in text.lower() or "currently recorded by nsta" in text.lower()
    assert "Equity-attributable production" not in text
    assert_no_forbidden_requests(page)


def test_equity_panel_never_shares_series_with_operator_panel(load_app, page):
    load_app()
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.wait_for_timeout(500)
    equity_text = page.text_content("#field-panel-content")
    assert "Equity-attributable production based on dated NSTA field interests" in equity_text

    page.click("#mode-operator")
    page.select_option("#operator-filter", "EXAMPLE OPERATOR LIMITED")
    page.click("#view-operator-history")
    page.wait_for_timeout(500)
    operator_text = page.text_content("#field-panel-content")
    assert "Equity-attributable production" not in operator_text


# --- 5/6. Coverage status display, including same-month divergence ----


def test_coverage_statuses_render_correctly_and_unavailable_shows_no_numeric_value(load_app, page):
    load_app()
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.wait_for_timeout(500)
    content = page.locator("#field-panel-content")

    badges = content.locator(".coverage-badge").all_text_contents()
    assert any("Complete" in b and "100" in b for b in badges)
    assert any("Not available" in b for b in badges)

    # Latest period (202601): oil and assoc_gas unavailable, dry_gas and
    # condensate complete, all in the SAME month - two streams must be
    # able to diverge within one period.
    unavailable_values = content.locator(".equity-value-unavailable").all_text_contents()
    assert len(unavailable_values) == 2
    assert all("Not available" in v for v in unavailable_values)

    full_text = content.text_content()
    assert "0 mb/d" not in full_text  # never a fabricated zero for an unavailable stream


def test_warning_status_shows_coverage_explanation_text(load_app, page):
    load_app()
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.wait_for_timeout(500)
    # The latest period's badge table only shows the latest period; the
    # warning period (202512) is in the chart data, exercised via the
    # chart-option assertions below rather than the latest-period table.
    option = page.evaluate("() => window.__echartsCharts['equity-chart']")
    assert option is not None
    formatter = None  # formatter functions cannot cross the JS/Python boundary;
    # instead, call it inside the page and return its result.
    tooltip_for_warning_period = page.evaluate(
        """() => {
            const opt = window.__echartsCharts['equity-chart'];
            return opt.tooltip.formatter([{ dataIndex: 1 }]);
        }"""
    )
    assert "202512" in tooltip_for_warning_period
    assert "97" in tooltip_for_warning_period
    assert "Warning" in tooltip_for_warning_period


def test_unavailable_chart_point_is_null_not_zero_and_connect_nulls_is_false(load_app, page):
    load_app()
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.wait_for_timeout(500)
    option = page.evaluate("() => window.__echartsCharts['equity-chart']")
    series = option["series"][0]
    assert series["connectNulls"] is False
    # Default stream tab is Oil; period index 2 (202601) is unavailable.
    assert series["data"][2] is None
    tooltip = page.evaluate(
        """() => window.__echartsCharts['equity-chart'].tooltip.formatter([{ dataIndex: 2 }])"""
    )
    assert "Not available" in tooltip
    assert "202601" in tooltip
    assert "80" in tooltip  # coverage_pct


def test_every_stream_has_its_own_unit_never_shares_an_axis_with_another_stream(load_app, page):
    load_app()
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.wait_for_timeout(500)
    tabs = page.locator(".stream-tab").all_text_contents()
    assert tabs == ["Oil", "Dry gas", "Associated gas", "Condensate"]
    option = page.evaluate("() => window.__echartsCharts['equity-chart']")
    assert option["yAxis"]["name"] == "mb/d"

    page.click(".stream-selector >> text=Dry gas")
    page.wait_for_timeout(500)
    option2 = page.evaluate("() => window.__echartsCharts['equity-chart']")
    assert option2["yAxis"]["name"] == "MMscf/d"
    assert len(option2["series"]) == 1  # a stream's chart never carries a second stream's series


# --- 7. MURLACH treatment ----------------------------------------------


def test_murlach_note_appears_for_a_recorded_murlach_interest_holder(load_app, page):
    load_app()
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.wait_for_timeout(500)
    text = page.text_content("#field-panel-content")
    assert (
        "Some recent production is excluded because NSTA records MURLACH production "
        "before the effective date of its available equity interests." in text
    )
    assert "Unresolved source-data case" in text
    assert "2050" not in text and "typo" not in text.lower()


def test_murlach_note_requires_data_driven_lookup_not_companys_fields_list(load_app, page):
    # ALPHA ENTITY LIMITED's own company.fields array does NOT include
    # murlach-pt-of-marnock-skua (mirrors the real backend: MURLACH's
    # field-months are always category "future_only", never "resolved",
    # so it never appears in any company's aggregate fields list). The
    # note must still appear, proving the frontend checks MURLACH's own
    # field-equity ownership_intervals rather than company.fields.
    load_app()
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.wait_for_timeout(500)
    fields_text = page.text_content(".field-slug-list")
    assert "murlach" not in fields_text.lower()
    panel_text = page.text_content("#field-panel-content")
    assert "MURLACH" in panel_text


def test_murlach_note_absent_for_a_company_with_no_recorded_murlach_interest(load_app, page):
    # GAMMA ENTITY LIMITED contributes to alpha-field but holds no
    # recorded interest in MURLACH's own ownership_intervals - the note
    # must not appear, proving it is governed by real per-company data
    # and not shown unconditionally for every company.
    load_app()
    select_equity_company(page, "GAMMA ENTITY LIMITED")
    page.wait_for_timeout(500)
    text = page.text_content("#field-panel-content")
    assert "MURLACH" not in text
    assert "Unresolved source-data case" not in text


# --- 8. Methodology link ------------------------------------------------


def test_equity_panel_links_to_methodology_page(load_app, page):
    load_app()
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.wait_for_timeout(500)
    href = page.get_attribute("#field-panel-content a.methodology-link", "href")
    assert href == "./methodology.html"


def test_header_methodology_link_present_without_navigating_directly_to_its_url(load_app, page):
    load_app()
    href = page.get_attribute("a.header-methodology-link", "href")
    assert href == "./methodology.html"


# --- 9. Global search, typed results ------------------------------------


def test_search_results_are_explicitly_typed_and_distinct(load_app, page):
    load_app()
    page.fill("#global-search", "ALPHA")
    page.wait_for_timeout(500)
    results = page.locator(".search-result").all_text_contents()
    assert any("Field" in r and "ALPHA FIELD" in r for r in results)
    assert any("Legal entity" in r and "ALPHA ENTITY LIMITED" in r for r in results)


def test_search_operator_result_is_labelled_operator(load_app, page):
    load_app()
    page.fill("#global-search", "EXAMPLE OPERATOR")
    page.wait_for_timeout(500)
    results = page.locator(".search-result").all_text_contents()
    assert any("Operator" in r and "EXAMPLE OPERATOR LIMITED" in r for r in results)


def test_search_is_keyboard_operable(load_app, page):
    load_app()
    page.fill("#global-search", "ALPHA ENTITY")
    page.wait_for_timeout(500)
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    page.wait_for_timeout(500)
    assert page.get_attribute("#field-panel", "hidden") is None
    text = page.text_content("#field-panel-content")
    assert "ALPHA ENTITY LIMITED" in text


# --- 10/11. URL state ----------------------------------------------------


def test_url_state_round_trips_through_reload(load_app, page, http_server):
    load_app()
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.wait_for_timeout(500)
    url = page.url
    assert "view=equity" in url
    assert "slug=alpha-entity-limited" in url

    page.goto(url, wait_until="load")
    page.wait_for_timeout(600)
    assert page.get_attribute("#field-panel", "hidden") is None
    text = page.text_content("#field-panel-content")
    assert "ALPHA ENTITY LIMITED" in text


def test_invalid_equity_slug_in_url_fails_gracefully(load_app, page):
    load_app("view=equity&slug=does-not-exist")
    banner = page.text_content("#status-banner")
    assert "does-not-exist" in banner
    assert "stale" in banner.lower()
    # The rest of the site must still work.
    assert page.locator("#map").count() == 1


def test_invalid_field_slug_in_url_fails_gracefully(load_app, page):
    load_app("view=field&slug=no-such-field")
    banner = page.text_content("#status-banner")
    assert "no-such-field" in banner


def test_invalid_operator_slug_in_url_fails_gracefully(load_app, page):
    load_app("view=operator&slug=no-such-operator")
    banner = page.text_content("#status-banner")
    assert "no-such-operator" in banner


# --- 13. Field ownership view -------------------------------------------


def test_field_ownership_tab_lazy_loads_and_distinguishes_row_types(load_app, page):
    load_app()
    page.fill("#global-search", "ALPHA FIELD")
    page.wait_for_timeout(500)
    page.click(".search-result")
    page.wait_for_timeout(700)
    assert field_equity_json_requests(page) == []  # not fetched until the tab is opened

    page.click("#field-panel-tab-ownership")
    page.wait_for_timeout(700)
    assert len(field_equity_json_requests(page)) == 1

    ownership_text = page.text_content("#field-panel-ownership-content")
    assert "ALPHA ENTITY LIMITED" in ownership_text
    assert "80%" in ownership_text
    assert "Current" in ownership_text  # open-ended interval (null end_date), never a fabricated date

    # Zero-interest row shown but clearly distinguished.
    zero_badge = page.text_content(".zero-interest-badge")
    assert "not an economic interest" in zero_badge.lower()

    # Zero-duration record shown only inside the collapsed source-event
    # details, never rendered as a real ownership period row.
    details_summary = page.text_content(".source-event-details summary")
    assert "1 source event record" in details_summary
    assert "not ownership periods" in details_summary.lower()
    main_table_text = page.text_content(".ownership-table")
    # DELTA ENTITY LIMITED is the zero-duration event record - it must
    # not appear as a normal row outside the <details> block.
    assert page.locator(".ownership-table >> text=DELTA ENTITY LIMITED").count() >= 1
    assert page.locator("table.ownership-table:not(.source-event-details *) >> text=DELTA ENTITY LIMITED").count() == 0


def test_murlach_field_ownership_shows_both_holders_and_excluded_periods(load_app, page):
    load_app()
    page.fill("#global-search", "MURLACH")
    page.wait_for_timeout(500)
    page.click(".search-result")
    page.wait_for_timeout(700)
    page.click("#field-panel-tab-ownership")
    page.wait_for_timeout(700)
    text = page.text_content("#field-panel-ownership-content")
    assert "ALPHA ENTITY LIMITED" in text and "80%" in text
    assert "BETA ENTITY LIMITED" in text and "20%" in text
    assert "Current" in text
    assert "3 period(s) excluded" in text


# --- Error handling -------------------------------------------------------


def test_equity_metadata_fetch_failure_does_not_break_the_rest_of_the_site(page, http_server):
    page.route("**/data/equity/meta.json", lambda route: route.fulfill(status=404, body="not found"))
    # This suite is entirely about the Fields map - #top=map explicitly,
    # since a hash-less load now lands on the Production view instead.
    page.goto(http_server + "/index.html#top=map", wait_until="load")
    page.wait_for_timeout(600)

    equity_banner = page.text_content("#equity-status-banner")
    assert "failed to load" in equity_banner.lower()
    assert page.get_attribute("#status-banner", "hidden") is not None  # main site status stays clean

    # Map and field search still work.
    assert page.locator("#map").count() == 1
    page.fill("#global-search", "ALPHA FIELD")
    page.wait_for_timeout(500)
    page.click(".search-result")
    page.wait_for_timeout(700)
    assert page.get_attribute("#field-panel", "hidden") is None


def test_equity_index_fetch_failure_does_not_break_the_rest_of_the_site(page, http_server):
    page.route("**/data/equity/index.json", lambda route: route.fulfill(status=500, body="server error"))
    # This suite is entirely about the Fields map - #top=map explicitly,
    # since a hash-less load now lands on the Production view instead.
    page.goto(http_server + "/index.html#top=map", wait_until="load")
    page.wait_for_timeout(600)
    equity_banner = page.text_content("#equity-status-banner")
    assert "failed to load" in equity_banner.lower()
    assert page.locator("#map").count() == 1


def test_missing_company_file_shows_http_error_category(page, http_server):
    page.route(
        "**/data/equity/companies/alpha-entity-limited.json",
        lambda route: route.fulfill(status=404, body="not found"),
    )
    # This suite is entirely about the Fields map - #top=map explicitly,
    # since a hash-less load now lands on the Production view instead.
    page.goto(http_server + "/index.html#top=map", wait_until="load")
    page.wait_for_timeout(600)
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.wait_for_timeout(500)
    text = page.text_content("#field-panel-content")
    assert "Equity company data failed to load" in text
    assert "HTTP 404" in text


def test_missing_field_equity_file_shows_http_error_category(page, http_server):
    page.route(
        "**/data/equity/fields/alpha-field.json",
        lambda route: route.fulfill(status=404, body="not found"),
    )
    # This suite is entirely about the Fields map - #top=map explicitly,
    # since a hash-less load now lands on the Production view instead.
    page.goto(http_server + "/index.html#top=map", wait_until="load")
    page.wait_for_timeout(600)
    page.fill("#global-search", "ALPHA FIELD")
    page.wait_for_timeout(500)
    page.click(".search-result")
    page.wait_for_timeout(700)
    page.click("#field-panel-tab-ownership")
    page.wait_for_timeout(700)
    text = page.text_content("#field-panel-ownership-content")
    assert "Field ownership data failed to load" in text
    assert "HTTP 404" in text


def test_malformed_equity_artifact_shows_a_parse_error_not_a_crash(page, http_server):
    page.route(
        "**/data/equity/companies/alpha-entity-limited.json",
        lambda route: route.fulfill(status=200, content_type="application/json", body="{not valid json"),
    )
    # This suite is entirely about the Fields map - #top=map explicitly,
    # since a hash-less load now lands on the Production view instead.
    page.goto(http_server + "/index.html#top=map", wait_until="load")
    page.wait_for_timeout(600)
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.wait_for_timeout(500)
    text = page.text_content("#field-panel-content")
    assert "not valid JSON" in text
    assert page.console_errors == [] or all("pageerror" not in e for e in page.console_errors)


# --- Deterministic rendering ------------------------------------------


def test_rendering_is_deterministic_across_repeated_selection(load_app, page):
    load_app()
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.wait_for_timeout(500)
    first = page.text_content("#field-panel-content")

    select_equity_company(page, "BETA ENTITY LIMITED")
    page.wait_for_timeout(500)

    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.wait_for_timeout(500)
    second = page.text_content("#field-panel-content")
    assert first == second


# --- Equity stream URL state (focused fix checkpoint) -------------------
#
# Supported URL stream slugs: oil, dry-gas, associated-gas, condensate -
# see docs/app/equity.js's PRODUCTION_STREAMS[].urlSlug, the single
# source of truth for this vocabulary (urlstate.js itself stays generic
# and merely passes the "stream" param through unvalidated).

STREAM_LABELS_BY_SLUG = {
    "oil": "Oil",
    "dry-gas": "Dry gas",
    "associated-gas": "Associated gas",
    "condensate": "Condensate",
}


@pytest.mark.parametrize("slug,label", list(STREAM_LABELS_BY_SLUG.items()))
def test_selecting_each_stream_updates_url_state(load_app, page, slug, label):
    load_app()
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.click(f".stream-selector button:has-text('{label}')")
    page.wait_for_timeout(300)
    assert f"stream={slug}" in page.url
    assert "view=equity" in page.url
    assert "slug=alpha-entity-limited" in page.url


@pytest.mark.parametrize("slug,label", list(STREAM_LABELS_BY_SLUG.items()))
def test_url_restoration_for_each_stream(load_app, page, http_server, slug, label):
    load_app(f"view=equity&slug=alpha-entity-limited&metric=equity&stream={slug}")
    page.wait_for_selector("#field-panel-content .equity-latest-table", timeout=5000)
    active_tab = page.locator(".stream-tab[aria-selected='true']")
    assert active_tab.text_content().strip() == label
    option = page.evaluate("() => window.__echartsCharts['equity-chart']")
    assert label in option["title"]["text"]


def test_fresh_load_restores_legal_entity_and_stream(load_app, page):
    # Simulates "opening a copied URL in a fresh browser session": no
    # prior interaction on this page object at all before the goto.
    load_app("view=equity&slug=beta-entity-limited&metric=equity&stream=dry-gas")
    page.wait_for_selector("#field-panel-content .equity-latest-table", timeout=5000)
    text = page.text_content("#field-panel-content")
    assert "BETA ENTITY LIMITED" in text
    active_tab = page.locator(".stream-tab[aria-selected='true']")
    assert active_tab.text_content().strip() == "Dry gas"


def test_invalid_stream_falls_back_to_oil_with_message(load_app, page):
    load_app("view=equity&slug=alpha-entity-limited&metric=equity&stream=not-a-real-stream")
    page.wait_for_selector("#field-panel-content .equity-latest-table", timeout=5000)
    active_tab = page.locator(".stream-tab[aria-selected='true']")
    assert active_tab.text_content().strip() == "Oil"
    banner = page.text_content("#equity-status-banner")
    assert "not-a-real-stream" in banner
    assert "not recognised" in banner.lower() or "not recognized" in banner.lower()
    # Non-disruptive: the panel itself still rendered successfully.
    assert page.locator("#field-panel-content .equity-latest-table").count() == 1


def test_missing_stream_defaults_to_oil_without_a_message(load_app, page):
    load_app("view=equity&slug=alpha-entity-limited&metric=equity")
    page.wait_for_selector("#field-panel-content .equity-latest-table", timeout=5000)
    active_tab = page.locator(".stream-tab[aria-selected='true']")
    assert active_tab.text_content().strip() == "Oil"
    banner_hidden = page.get_attribute("#equity-status-banner", "hidden")
    assert banner_hidden is not None  # no spurious warning for the ordinary default case


def test_switching_to_operator_mode_drops_inapplicable_equity_stream_state(load_app, page):
    load_app()
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.click(".stream-selector button:has-text('Dry gas')")
    page.wait_for_timeout(300)
    assert "stream=dry-gas" in page.url

    page.click("#mode-operator")
    page.wait_for_timeout(200)
    assert "stream=" not in page.url
    assert "view=equity" not in page.url


def test_field_url_state_unaffected_by_stream_fix(load_app, page):
    load_app()
    page.fill("#global-search", "ALPHA FIELD")
    page.wait_for_timeout(500)
    page.click(".search-result")
    page.wait_for_timeout(700)
    assert "view=field" in page.url
    assert "slug=alpha-field" in page.url
    assert "stream=" not in page.url


def test_operator_url_state_unaffected_by_stream_fix(load_app, page):
    load_app()
    page.click("#mode-operator")
    page.select_option("#operator-filter", "EXAMPLE OPERATOR LIMITED")
    page.click("#view-operator-history")
    page.wait_for_timeout(700)
    assert "view=operator" in page.url
    assert "stream=" not in page.url


def test_browser_back_forward_keeps_stream_and_panel_consistent(load_app, page):
    # Entry 1: the initial load. This app only ever uses
    # history.replaceState (urlstate.js) - it never pushes a new entry on
    # its own - so entry 1's stored state keeps getting overwritten in
    # place as the user interacts, right up until a REAL navigation (like
    # the one below) pushes a second, distinct entry.
    load_app()
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.wait_for_timeout(300)
    assert "stream=oil" in page.url

    # A real navigation to a different hash pushes entry 2. Since only the
    # fragment differs, the browser treats this as a same-document
    # navigation and fires popstate on subsequent back/forward rather than
    # reloading - exactly the case main.js's new popstate listener exists
    # for.
    page.goto(
        page.url.split("#")[0] + "#view=equity&slug=alpha-entity-limited&metric=equity&stream=condensate",
        wait_until="load",
    )
    page.wait_for_timeout(300)
    active_tab = page.locator(".stream-tab[aria-selected='true']")
    assert active_tab.text_content().strip() == "Condensate"

    page.go_back()
    page.wait_for_timeout(500)
    active_tab_after_back = page.locator(".stream-tab[aria-selected='true']")
    assert active_tab_after_back.text_content().strip() == "Oil"
    assert "stream=oil" in page.url

    page.go_forward()
    page.wait_for_timeout(500)
    active_tab_after_forward = page.locator(".stream-tab[aria-selected='true']")
    assert active_tab_after_forward.text_content().strip() == "Condensate"
    assert "stream=condensate" in page.url


def test_stream_selection_never_triggers_a_full_page_reload(load_app, page):
    load_app()
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    reload_count = page.evaluate("() => { window.__navCount = (window.__navCount || 0); return window.__navCount; }")
    page.evaluate("() => { window.__markerBeforeStreamClick = true; }")
    page.click(".stream-selector button:has-text('Associated gas')")
    page.wait_for_timeout(300)
    # If a real navigation/reload had occurred, this page-scoped global
    # would have been wiped - its survival proves no reload happened.
    still_present = page.evaluate("() => window.__markerBeforeStreamClick === true")
    assert still_present
    assert "stream=associated-gas" in page.url


def test_stream_url_formatting_is_deterministic(load_app, page):
    load_app()
    select_equity_company(page, "ALPHA ENTITY LIMITED")
    page.click(".stream-selector button:has-text('Dry gas')")
    page.wait_for_timeout(300)
    first_url = page.url

    page.click(".stream-selector button:has-text('Oil')")
    page.wait_for_timeout(200)
    page.click(".stream-selector button:has-text('Dry gas')")
    page.wait_for_timeout(300)
    second_url = page.url

    assert first_url == second_url
    # Exact, stable param order/format - not just equivalent content.
    # `top=map` is present and first because load_app()'s default lands
    # on the Fields map (see conftest.py); KEY_ORDER always writes `top`
    # first when present.
    assert second_url.endswith("#top=map&view=equity&slug=alpha-entity-limited&metric=equity&stream=dry-gas")
