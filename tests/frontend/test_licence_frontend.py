# Committed, CI-compatible frontend tests for the Current licence
# portfolio view (Deliverable 2, spec approved 2026-09-10 continuation).
# Runs the real docs/app/licence.js, urlstate.js, main.js against a
# small synthetic licence-portfolio fixture
# (tests/frontend/fixtures/docs/data/licence_portfolio*.json[on]):
# two groups (Alpha Group operates one subarea and holds a second
# non-operated subarea of the same licence P100; Beta Group holds one
# relinquished, non-operated subarea P200).
#
# No live network access: same maplibre-gl/echarts stubbing as the rest
# of this suite. The licence-portfolio map is a SEPARATE MapLibre
# instance from the Fields map - main.js always constructs the Fields
# map too, regardless of which top-level view is active, so a single
# window.__lastMapInstance global would be ambiguous about which map a
# test just got. The stub instead keys instances by container id
# (window.__mapInstancesByContainer, see stubs/maplibre-gl.mjs), so
# every test below addresses 'licence-map' unambiguously no matter which
# map was constructed most recently.

import pytest

from test_equity_frontend import assert_no_forbidden_requests


def _open_licence_view(page):
    page.click("#top-nav-licence")
    page.wait_for_function(
        "() => window.__mapInstancesByContainer['licence-map'] && window.__mapInstancesByContainer['licence-map'].getLayer('licence-fill')"
    )
    page.wait_for_timeout(200)


def test_switching_to_licence_portfolio_is_isolated_from_fields_map(load_app):
    page = load_app("top=map")
    page.wait_for_timeout(300)
    assert page.locator("#layout").is_visible()

    _open_licence_view(page)
    assert page.locator("#layout").is_hidden()
    assert page.locator("#view-licence").is_visible()
    assert "top=licence" in page.url
    # Switching top-level views must not carry Fields-map params (view=/
    # slug=/etc.) into the licence URL state.
    assert "view=" not in page.url
    assert_no_forbidden_requests(page)


def test_current_portfolio_is_the_default_sub_view(load_app):
    page = load_app("top=licence")
    _open_licence_view(page)
    assert page.locator("#licence-current-view").is_visible()
    assert page.locator("#licence-historical-view").is_hidden()
    assert "Current portfolio" in page.locator('[data-lmode="current"]').inner_text()
    assert "active" in page.locator('[data-lmode="current"]').get_attribute("class")


def test_historical_interests_placeholder_never_claims_equity_percentages(load_app):
    page = load_app("top=licence")
    _open_licence_view(page)
    page.click('[data-lmode="historical"]')
    page.wait_for_timeout(200)
    assert page.locator("#licence-historical-view").is_visible()
    assert page.locator("#licence-current-view").is_hidden()
    text = " ".join(page.locator("#licence-historical-view").text_content().split())
    assert "not yet available" in text
    assert "cannot be reconstructed" in text


def test_map_layers_are_created_with_operated_colour_and_text_label(load_app):
    page = load_app("top=licence")
    _open_licence_view(page)
    has_fill = page.evaluate("() => !!window.__mapInstancesByContainer['licence-map'].getLayer('licence-fill')")
    has_outline = page.evaluate("() => !!window.__mapInstancesByContainer['licence-map'].getLayer('licence-outline')")
    has_labels = page.evaluate("() => !!window.__mapInstancesByContainer['licence-map'].getLayer('licence-labels')")
    assert has_fill and has_outline and has_labels
    label_layer = page.evaluate("() => window.__mapInstancesByContainer['licence-map'].getLayer('licence-labels')")
    assert "text-field" in label_layer["layout"]


def test_summary_reflects_filtered_set_not_global_totals(load_app):
    page = load_app("top=licence")
    _open_licence_view(page)
    text = page.locator("#licence-summary").text_content()
    assert "Distinct licences: 2" in text
    assert "Distinct subareas: 3" in text
    assert "Operated subareas: 1" in text
    assert "Non-operated subareas: 2" in text


def test_group_filter_updates_map_filter_summary_and_url(load_app):
    page = load_app("top=licence")
    _open_licence_view(page)
    page.fill("#lf-group", "Alpha Group")
    page.dispatch_event("#lf-group", "change")
    page.wait_for_timeout(200)
    assert "lgroup=alpha-group" in page.url
    text = page.locator("#licence-summary").text_content()
    assert "Distinct licences: 1" in text
    assert "Distinct subareas: 2" in text
    layer_filter = page.evaluate("() => window.__mapInstancesByContainer['licence-map'].getLayer('licence-fill').filter")
    assert layer_filter is not None


def test_operated_filter_combines_with_group_filter(load_app):
    page = load_app("top=licence&lgroup=alpha-group")
    _open_licence_view(page)
    page.select_option("#lf-operated", "operated")
    page.wait_for_timeout(200)
    assert "loperated=operated" in page.url
    text = page.locator("#licence-summary").text_content()
    assert "Distinct subareas: 1" in text
    assert "Non-operated subareas: 0" in text


def test_clear_filters_resets_all_licence_params(load_app):
    page = load_app("top=licence&lgroup=alpha-group&loperated=operated&lstatus=Extant")
    _open_licence_view(page)
    page.click("#lf-clear")
    page.wait_for_timeout(200)
    assert "lgroup=" not in page.url
    assert "loperated=" not in page.url
    assert "lstatus=" not in page.url
    text = page.locator("#licence-summary").text_content()
    assert "Distinct licences: 2" in text


def test_fit_portfolio_button_does_not_error(load_app):
    page = load_app("top=licence")
    _open_licence_view(page)
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.click("#lf-fit")
    page.wait_for_timeout(200)
    assert errors == []


def test_clicking_a_subarea_shows_required_detail_fields(load_app):
    page = load_app("top=licence")
    _open_licence_view(page)
    page.evaluate(
        """() => {
            window.__mapInstancesByContainer['licence-map']._emitLayerEvent('click', 'licence-fill', {
                properties: {
                    licence_number: 100,
                    licence_reference: 'P100',
                    block_reference: '1/1a',
                    subarea_name: 'ALL',
                    licence_status: 'Extant',
                    equity_pct: 60,
                    operator_group: 'Alpha Group',
                    current_display_group: 'Alpha Group',
                    operated: true,
                    licence_start_date: '2000-01-01',
                    licence_end_date: null,
                },
            });
        }"""
    )
    page.wait_for_timeout(200)
    text = page.locator("#licence-detail").text_content()
    assert "P100" in text
    assert "1/1a" in text
    assert "Extant" in text
    assert "60%" in text
    assert "Alpha Group" in text
    assert "Operated by this group" in text
    assert "2000-01-01" in text
    assert "Ongoing" in text
    assert "North Sea Transition Authority" in text


def test_no_area_figure_is_shown_anywhere_in_the_view(load_app):
    page = load_app("top=licence")
    _open_licence_view(page)
    text = page.locator("#view-licence").text_content().lower()
    assert "hectare" not in text
    assert "km²" not in text
    assert " sq " not in text
    assert "area:" not in text


def test_empty_result_never_renders_as_zero_totals(load_app):
    page = load_app("top=licence")
    _open_licence_view(page)
    page.fill("#lf-licence", "P999-DOES-NOT-EXIST")
    page.dispatch_event("#lf-licence", "change")
    page.wait_for_timeout(200)
    text = page.locator("#licence-summary").text_content()
    assert "No licences match the selected filters" in text


def test_url_state_round_trips_group_and_operated_filter(load_app):
    page = load_app("top=licence&lgroup=beta-group&loperated=nonoperated")
    _open_licence_view(page)
    text = page.locator("#licence-summary").text_content()
    assert "Distinct licences: 1" in text
    assert "Non-operated subareas: 1" in text
