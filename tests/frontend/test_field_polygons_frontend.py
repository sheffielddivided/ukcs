# Committed, CI-compatible frontend tests for authoritative field
# polygons (spec Workstream 3, approved 2026-09-10). Run the real
# docs/app/map.js and main.js against a small synthetic
# field_polygons.geojson fixture (tests/frontend/fixtures/docs/data/) -
# one matched field (ALPHA FIELD / alpha-field) and one deliberately
# unmatched polygon, mirroring the real pipeline's own
# matched/unmatched split.
#
# No live network access: maplibre-gl is stubbed (conftest.py). The stub
# exposes window.__lastMapInstance (mirroring the echarts stub's
# window.__echartsCharts pattern) and a test-only _emitLayerEvent()
# helper so a layer click can be simulated without a real WebGL canvas.

import pytest

from test_equity_frontend import assert_no_forbidden_requests


def _wait_for_polygon_layer(page):
    page.wait_for_function(
        "() => window.__lastMapInstance && window.__lastMapInstance.getLayer('field-polygons-fill')"
    )


def test_field_polygons_geojson_is_fetched_and_layer_added(load_app):
    page = load_app()
    _wait_for_polygon_layer(page)
    urls = [r for r in page.all_requests if "/data/field_polygons.geojson" in r]
    assert urls, "field_polygons.geojson must be fetched at startup"
    has_outline_layer = page.evaluate(
        "() => !!window.__lastMapInstance.getLayer('field-polygons-outline')"
    )
    assert has_outline_layer
    assert_no_forbidden_requests(page)


def test_clicking_matched_polygon_opens_same_panel_as_marker(load_app):
    page = load_app()
    _wait_for_polygon_layer(page)

    page.evaluate(
        """() => {
            window.__lastMapInstance._emitLayerEvent('click', 'field-polygons-fill', {
                properties: {
                    matched_pprs_slug: 'alpha-field',
                    matched_pprs_field: 'ALPHA FIELD',
                    field_no: '001',
                    determination_status: 'CURRENT',
                },
            });
        }"""
    )
    page.wait_for_timeout(300)

    panel = page.locator("#field-panel")
    assert not panel.is_hidden()
    assert "ALPHA FIELD" in page.locator(".panel-field-name").inner_text()
    assert_no_forbidden_requests(page)


def test_clicking_unmatched_polygon_does_not_open_a_panel_or_error(load_app):
    page = load_app()
    _wait_for_polygon_layer(page)

    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    page.evaluate(
        """() => {
            window.__lastMapInstance._emitLayerEvent('click', 'field-polygons-fill', {
                properties: {
                    matched_pprs_slug: null,
                    matched_pprs_field: null,
                    field_no: '002',
                    determination_status: 'CURRENT',
                },
            });
        }"""
    )
    page.wait_for_timeout(300)

    assert errors == []
    panel = page.locator("#field-panel")
    assert panel.is_hidden()  # no field to open - never crashes, never opens a blank panel


def test_layer_toggles_control_bubble_and_outline_visibility(load_app):
    page = load_app()
    _wait_for_polygon_layer(page)

    page.locator("#layer-toggle-bubbles").uncheck()
    page.wait_for_timeout(100)
    circles_visibility = page.evaluate(
        "() => window.__lastMapInstance.getLayoutProperty('fields-circles', 'visibility')"
    )
    assert circles_visibility == "none"

    page.locator("#layer-toggle-outlines").uncheck()
    page.wait_for_timeout(100)
    fill_visibility = page.evaluate(
        "() => window.__lastMapInstance.getLayoutProperty('field-polygons-fill', 'visibility')"
    )
    assert fill_visibility == "none"

    # Turning bubbles back on must not require outlines and vice versa -
    # the two controls are independent (spec: "either can be shown alone
    # or both together").
    page.locator("#layer-toggle-bubbles").check()
    page.wait_for_timeout(100)
    circles_visibility_2 = page.evaluate(
        "() => window.__lastMapInstance.getLayoutProperty('fields-circles', 'visibility')"
    )
    fill_visibility_2 = page.evaluate(
        "() => window.__lastMapInstance.getLayoutProperty('field-polygons-fill', 'visibility')"
    )
    assert circles_visibility_2 == "visible"
    assert fill_visibility_2 == "none"  # unchanged - still off
