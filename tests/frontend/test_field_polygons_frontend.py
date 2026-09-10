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


# --- Polygon colour fill + popup-on-polygon (2026-09-10 continuation) -----
# Matched fields are now coloured/popup'd via their polygon, not a circle
# dot; the circle layer is filtered down to ONLY fields with no polygon
# match at all (fixture: "murlach-pt-of-marnock-skua" has no polygon
# representation, "alpha-field" does), so a producing field is never
# dropped from the map even though polygon match rate is well under 100%.


def test_matched_polygon_fill_is_coloured_by_commodity(load_app):
    """alpha-field has liquids_mboed(10)/total_mboed(12) >= 0.5, so its
    matched polygon's fill must carry the same "oil" colour the circle
    layer would have used - production colour now lives on the polygon."""
    page = load_app()
    _wait_for_polygon_layer(page)
    fill_color = page.evaluate(
        "() => window.__lastMapInstance.getLayer('field-polygons-fill').paint['fill-color']"
    )
    assert fill_color == ["match", ["get", "commodity"], "oil", "#eb6834", "gas", "#2a78d6", "none", "#898781", "#5b6b7a"]


def test_circle_layer_is_filtered_to_fields_with_no_polygon_match(load_app):
    """murlach-pt-of-marnock-skua has no polygon at all in
    field_polygons.geojson - it must remain reachable via the (fallback)
    circle layer. alpha-field IS matched, so it must be excluded from the
    circle layer's filter (its colour/popup now live on the polygon)."""
    page = load_app()
    _wait_for_polygon_layer(page)
    circle_filter = page.evaluate(
        "() => window.__lastMapInstance.getLayer('fields-circles').filter"
    )
    assert circle_filter == ["all", ["!", ["in", ["get", "slug"], ["literal", ["alpha-field"]]]]]


def test_hovering_matched_polygon_shows_popup_with_field_detail(load_app):
    page = load_app()
    _wait_for_polygon_layer(page)

    page.evaluate(
        """() => {
            window.__lastMapInstance._emitLayerEvent('mouseenter', 'field-polygons-fill', {
                properties: {
                    matched_pprs_slug: 'alpha-field',
                    matched_pprs_field: 'ALPHA FIELD',
                    field_no: '001',
                    determination_status: 'CURRENT',
                    field: 'ALPHA FIELD',
                    operator: 'EXAMPLE OPERATOR LIMITED',
                    region: 'CNS',
                    location: 'Offshore',
                    period: '202601',
                    oil_mbd: 10.0,
                    condensate_mbd: 0.1,
                    assoc_gas_mmscfd: 1.0,
                    dry_gas_mmscfd: 4.5,
                    water_mbd: 2.0,
                    unit_count: 1,
                    storage_unit_count: 0,
                },
                lngLat: { lng: 1.5, lat: 58.0 },
            });
        }"""
    )
    assert page.evaluate("() => window.__lastPopupOpen") is True
    html = page.evaluate("() => window.__lastPopupHtml")
    assert "ALPHA FIELD" in html
    assert "EXAMPLE OPERATOR LIMITED" in html


def test_hovering_unmatched_polygon_shows_no_popup(load_app):
    page = load_app()
    _wait_for_polygon_layer(page)

    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    page.evaluate(
        """() => {
            window.__lastMapInstance._emitLayerEvent('mouseenter', 'field-polygons-fill', {
                properties: {
                    matched_pprs_slug: null,
                    matched_pprs_field: null,
                    field_no: '002',
                    determination_status: 'CURRENT',
                },
                lngLat: { lng: 3.1, lat: 59.1 },
            });
        }"""
    )
    assert errors == []
    assert page.evaluate("() => window.__lastPopupOpen") is not True


def test_operator_filter_combines_with_polygon_match_base_filter_and_covers_polygons(load_app):
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
    page.wait_for_timeout(200)

    page.select_option("#operator-filter", "EXAMPLE OPERATOR LIMITED")
    page.wait_for_timeout(200)

    circle_filter = page.evaluate(
        "() => window.__lastMapInstance.getLayer('fields-circles').filter"
    )
    assert circle_filter == [
        "all",
        ["!", ["in", ["get", "slug"], ["literal", ["alpha-field"]]]],
        ["==", ["get", "operator"], "EXAMPLE OPERATOR LIMITED"],
    ]

    polygon_filter = page.evaluate(
        "() => window.__lastMapInstance.getLayer('field-polygons-fill').filter"
    )
    assert polygon_filter == [
        "any",
        ["!", ["to-boolean", ["get", "matched_pprs_slug"]]],
        ["==", ["get", "operator"], "EXAMPLE OPERATOR LIMITED"],
    ]
    outline_filter = page.evaluate(
        "() => window.__lastMapInstance.getLayer('field-polygons-outline').filter"
    )
    assert outline_filter == polygon_filter
