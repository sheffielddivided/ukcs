# Committed, CI-compatible frontend tests for the Historical licence
# interests and operators sub-view (Deliverable 3, spec approved
# 2026-09-10 continuation). Runs the real docs/app/licence.js,
# urlstate.js, main.js against a small synthetic fixture
# (tests/frontend/fixtures/docs/data/licence_history*.json[on]): three
# historical episodes on block 9/11 (licence P335, two successive
# licensees - GETTY OIL -> TEXACO, mirroring the real historical-name-
# reconstruction example in the Phase 3 discovery report) plus one
# open-ended current episode on block 3/27b (licence P920).
#
# No live network access: same maplibre-gl/echarts stubbing as the rest
# of this suite. Historical interests shares ONE MapLibre instance with
# Current portfolio (both are sub-views of the same Licence portfolio
# top-level view) - window.__mapInstancesByContainer['licence-map']
# addresses it unambiguously regardless of which sub-view added it.

import pytest

from test_equity_frontend import assert_no_forbidden_requests


def _open_historical_view(page):
    page.click("#top-nav-licence")
    page.wait_for_function(
        "() => window.__mapInstancesByContainer['licence-map'] && "
        "window.__mapInstancesByContainer['licence-map'].getLayer('licence-fill')"
    )
    page.click('[data-lmode="historical"]')
    page.wait_for_function(
        "() => window.__mapInstancesByContainer['licence-map'].getLayer('licence-history-fill')"
    )
    page.wait_for_timeout(200)


def test_mode_is_labelled_historical_licence_interests_and_operators(load_app):
    page = load_app("top=licence")
    _open_historical_view(page)
    text = page.locator('[data-lmode="historical"]').inner_text()
    assert text == "Historical licence interests and operators"
    # The forbidden label must never appear anywhere in this sub-view.
    view_text = page.locator("#licence-historical-view").text_content()
    assert "Historical equity portfolio" not in view_text


def test_no_equity_percentage_statement_is_shown_prominently(load_app):
    page = load_app("top=licence")
    _open_historical_view(page)
    text = " ".join(page.locator("#licence-historical-view").text_content().split())
    assert (
        "Historical geometry and recorded organisation names are available, but historical "
        "subarea equity percentages cannot be reconstructed from the published NSTA source."
    ) in text


def test_default_date_shows_only_the_currently_open_episode(load_app):
    page = load_app("top=licence")
    _open_historical_view(page)
    # historyMeta.latest_start_date = 2013-11-18, which is exactly when
    # episode 3 (P920, open-ended) starts and episode 2 (P335) ends -
    # exclusive end-date semantics mean only episode 3 matches.
    summary = page.locator("#licence-history-summary").text_content()
    assert "Distinct licences active on 2013-11-18: 1" in summary
    assert "Total recorded episodes shown: 1" in summary


def test_selecting_an_earlier_date_shows_the_historical_licensee(load_app):
    page = load_app("top=licence")
    _open_historical_view(page)
    page.fill("#lhf-date", "2000-01-01")
    page.dispatch_event("#lhf-date", "change")
    page.wait_for_timeout(200)
    assert "ldate=2000-01-01" in page.url
    summary = page.locator("#licence-history-summary").text_content()
    assert "Distinct licences active on 2000-01-01: 1" in summary


def test_clicking_an_historical_episode_shows_required_detail_fields_and_no_percentage(load_app):
    page = load_app("top=licence&ldate=1985-01-01")
    _open_historical_view(page)
    page.evaluate(
        """() => {
            window.__mapInstancesByContainer['licence-map']._emitLayerEvent('click', 'licence-history-fill', {
                properties: {
                    episode_id: 1,
                    licence_number: 335,
                    licence_reference: 'P335',
                    block_reference: '9/11',
                    licence_status: 'Expired',
                    start_date: '1980-12-20',
                    end_date: '1987-01-01',
                    licensee_names: 'GETTY OIL (BRITAIN) LIMITED (01006065)',
                    licensee_group: 'GETTY OIL',
                    operator_names: 'UNOCAL EXPLORATION AND PRODUCTION COMPANY (U.K.) LIMITED',
                    operator_group: 'ALPHA GROUP',
                    admin_org: 'GETTY OIL (BRITAIN) LIMITED (01006065)',
                    admin_group: 'GETTY OIL',
                },
            });
        }"""
    )
    page.wait_for_timeout(200)
    text = " ".join(page.locator("#licence-history-detail").text_content().split())
    assert "P335" in text
    assert "9/11" in text
    assert "1980-12-20" in text
    assert "1987-01-01" in text
    assert "GETTY OIL (BRITAIN) LIMITED (01006065)" in text
    assert "UNOCAL EXPLORATION AND PRODUCTION COMPANY (U.K.) LIMITED" in text
    assert "cannot be reconstructed from the published NSTA source" in text
    assert "North Sea Transition Authority" in text
    # Never a percentage figure anywhere in the detail panel.
    assert "%" not in text


def test_operator_group_filter_matches_the_active_episode_at_that_date(load_app):
    # At 1985-01-01 only episode 1 (block 9/11, ALPHA GROUP) is active.
    page = load_app("top=licence&ldate=1985-01-01")
    _open_historical_view(page)
    page.fill("#lhf-operator", "ALPHA GROUP")
    page.dispatch_event("#lhf-operator", "change")
    page.wait_for_timeout(200)
    assert "lgroup=ALPHA" in page.url
    summary = page.locator("#licence-history-summary").text_content()
    assert "Distinct licences active on 1985-01-01: 1" in summary


def test_operator_group_filter_excludes_a_non_matching_episode(load_app):
    # At 1985-01-01 the active episode's operator group is ALPHA GROUP,
    # not BETA GROUP - filtering by BETA GROUP must show no results.
    page = load_app("top=licence&ldate=1985-01-01")
    _open_historical_view(page)
    page.fill("#lhf-operator", "BETA GROUP")
    page.dispatch_event("#lhf-operator", "change")
    page.wait_for_timeout(200)
    summary = page.locator("#licence-history-summary").text_content()
    assert "No historical licence interests match" in summary


def test_clear_filters_resets_date_and_group(load_app):
    page = load_app("top=licence&ldate=1985-01-01&lgroup=ALPHA+GROUP")
    _open_historical_view(page)
    page.click("#lhf-clear")
    page.wait_for_timeout(200)
    assert "ldate=" not in page.url
    assert "lgroup=" not in page.url
    summary = page.locator("#licence-history-summary").text_content()
    assert "Distinct licences active on 2013-11-18: 1" in summary


def test_fit_results_button_does_not_error(load_app):
    page = load_app("top=licence")
    _open_historical_view(page)
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.click("#lhf-fit")
    page.wait_for_timeout(200)
    assert errors == []


def test_switching_sub_mode_clears_stale_group_filter(load_app):
    """A company-group SLUG selected in Current portfolio must not leak
    into Historical interests, where lgroup means a recorded operator
    GROUP NAME instead - different vocabularies, same URL key."""
    page = load_app("top=licence")
    page.wait_for_function(
        "() => window.__mapInstancesByContainer['licence-map'] && "
        "window.__mapInstancesByContainer['licence-map'].getLayer('licence-fill')"
    )
    page.fill("#lf-group", "Alpha Group")
    page.dispatch_event("#lf-group", "change")
    page.wait_for_timeout(200)
    assert "lgroup=alpha-group" in page.url

    page.click('[data-lmode="historical"]')
    page.wait_for_timeout(200)
    assert "lgroup=" not in page.url


def test_no_area_figure_is_shown_in_historical_view(load_app):
    page = load_app("top=licence")
    _open_historical_view(page)
    text = page.locator("#licence-historical-view").text_content().lower()
    assert "hectare" not in text
    assert "km²" not in text
    assert "area:" not in text


def test_url_state_round_trips_date_and_status(load_app):
    page = load_app("top=licence&ldate=1985-01-01&lstatus=Expired")
    _open_historical_view(page)
    summary = page.locator("#licence-history-summary").text_content()
    assert "Distinct licences active on 1985-01-01: 1" in summary


def test_no_forbidden_network_requests(load_app):
    page = load_app("top=licence")
    _open_historical_view(page)
    assert_no_forbidden_requests(page)
