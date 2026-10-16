"""
The basemap is decoration; the data is the product.

Both map views (Fields map, Licence portfolio) draw NSTA GeoJSON on top of
an OSM raster basemap. The GeoJSON does not depend on that basemap in any
way, so a reader whose browser cannot reach tile.openstreetmap.org - a
network that blocks it, an ad blocker, a corporate proxy, OSM rate-limiting
their address - must still see every field and every licence.

They did not. Both views added their sources and layers inside
`map.on("load", ...)`, and maplibre-gl fires `load` only once the style AND
the initial basemap tiles have loaded. With the basemap unreachable the
handler never ran, so the layers were never added. Nothing looked broken
from the outside: `map.loaded()` and `map.isStyleLoaded()` both returned
true, and the style simply contained the `osm` layer and nothing else.

Measured against maplibre-gl 6.8.0 with a 404ing basemap:

    tiles OK   styledata, style.load, sourcedata, sourcedata, styledata, load, idle
    tiles 404  styledata, style.load, sourcedata, sourcedata, styledata

`style.load` fires either way, which is what docs/app/map-ready.js hangs on.

The stub models that distinction: `window.__stubBasemapFails = true` makes
it fire `style.load` and never `load`, exactly as the real library does.
"""

from __future__ import annotations

import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "docs" / "app"
MAP_MODULES = ("map.js", "licence.js")


def _layers_added(page, container_id):
    """Layer ids the app actually added to the map in `container_id`."""
    return page.evaluate(
        """(id) => {
            const m = (window.__mapInstancesByContainer || {})[id];
            if (!m) return null;
            return Object.keys(m._layers || {});
        }""",
        container_id,
    )


def test_fields_map_still_draws_its_data_when_the_basemap_fails(page, http_server):
    """A reader who cannot load OSM tiles must still get the fields."""
    page.add_init_script("window.__stubBasemapFails = true;")
    page.goto(http_server + "/index.html#top=map", wait_until="load")
    page.wait_for_timeout(800)

    layers = _layers_added(page, "map")
    assert layers, "the Fields map added no layers at all with the basemap failing"
    assert any("circle" in layer or "polygon" in layer for layer in layers), (
        f"the Fields map's own data layers are missing; only got {layers}"
    )


def test_licence_map_still_draws_its_data_when_the_basemap_fails(page, http_server):
    """Same for the Licence portfolio - this is the view the defect was
    reported against."""
    page.add_init_script("window.__stubBasemapFails = true;")
    page.goto(http_server + "/index.html#top=licence", wait_until="load")
    page.wait_for_timeout(800)

    layers = _layers_added(page, "licence-map")
    assert layers, "the Licence map added no layers at all with the basemap failing"
    assert "licence-fill" in layers, (
        f"the licence polygons are missing; only got {layers}"
    )


def test_no_map_view_gates_its_layers_on_the_load_event():
    """The source-level invariant behind both tests above.

    `load` means "style and first tiles"; `style.load` means "you may now
    call addSource/addLayer". Creating layers inside a `load` handler ties
    the data to the basemap, which is the defect. Asserted on the source
    because a stub that fires both events happily passes either way - only
    the real library distinguishes them, and the suite does not run against
    the real library."""
    offenders = []
    for name in MAP_MODULES:
        for number, line in enumerate((APP_DIR / name).read_text().split("\n"), 1):
            stripped = line.strip()
            # A comment explaining the defect is not the defect. Both
            # modules carry one that quotes the broken form verbatim.
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            if re.search(r'\bmap\.(?:on|once)\(\s*["\']load["\']', line):
                offenders.append(f"{name}:{number}")
    assert not offenders, (
        "these handlers run only once the basemap has loaded, so the data "
        f"layers they create vanish when it does not: {offenders}. "
        "Use onStyleReady() from docs/app/map-ready.js instead."
    )


# ---------------------------------------------------------------------------
# The race underneath the defect above
# ---------------------------------------------------------------------------
#
# The licence view does two independent async things: it builds the map and
# it fetches the portfolio GeoJSON. Whichever finishes second must be the
# one that completes the picture, because which one wins is decided by the
# reader's browser cache, not by the code - a visitor with the OSM tiles
# already cached and the GeoJSON not is the fast-style case, and a first-
# time visitor on a slow link is usually the other.
#
# The pre-fix code could only survive one order. It created the source from
# `portfolioGeojson` at style time and never filled it afterwards, so with
# the style ready first the source was built from `null`: a working basemap,
# the full filter UI, and no licences on the map. That is the reported
# symptom, and it is not the basemap failing - it is the basemap being
# FASTER.


def _portfolio_features(page):
    """How many features the licence map's own source actually holds."""
    return page.evaluate(
        """() => {
            const m = (window.__mapInstancesByContainer || {})["licence-map"];
            if (!m) return null;
            const src = m.getSource("licence-portfolio");
            if (!src) return "no-source";
            if (!src.data || !src.data.features) return 0;
            return src.data.features.length;
        }"""
    )


def test_licence_polygons_survive_the_style_winning_the_race(page, http_server):
    """Style ready long before the GeoJSON arrives - the order that broke."""
    page.route(
        "**/licence_portfolio.geojson",
        lambda route: (page.wait_for_timeout(600), route.continue_())[-1],
    )
    page.goto(http_server + "/index.html#top=licence", wait_until="load")
    page.wait_for_timeout(2500)

    count = _portfolio_features(page)
    assert count not in (None, "no-source"), f"the licence source is missing: {count}"
    assert count > 0, (
        "the licence map's source is empty: the GeoJSON arrived after the "
        "style was ready and nothing filled the source afterwards"
    )


def test_licence_polygons_survive_the_fetch_winning_the_race(page, http_server):
    """GeoJSON in hand long before the style is ready - the other order.

    This is the order that always worked, including before the fix, so it
    does not fail against the original defect. It is here so that a future
    change made for one order cannot quietly break the other: the pre-fix
    code passed exactly this test while failing the one above."""
    page.add_init_script("window.__stubStyleDelayMs = 600;")
    page.goto(http_server + "/index.html#top=licence", wait_until="load")
    page.wait_for_timeout(2500)

    count = _portfolio_features(page)
    assert count not in (None, "no-source"), f"the licence source is missing: {count}"
    assert count > 0, (
        "the licence map's source is empty: the style became ready after the "
        "fetch and did not pick up the data already waiting for it"
    )


def test_ensure_map_returns_its_memoized_promise():
    """`ensureMap()` returning undefined on its FIRST call is what let the
    view run on past a map that did not exist yet, and what put the fetch
    on the wrong side of the race to begin with. The memoized-return line
    on the second call is not enough - the first caller is the one that
    builds the map."""
    source = (APP_DIR / "licence.js").read_text()
    body = source[source.index("\nfunction ensureMap() {") :]
    body = body[: body.index("\n}\n")]
    assert "  return ensureMapPromise;" in body, (
        "ensureMap() does not return its promise on the first call, so the "
        "first caller's `await` resolves immediately and continues before "
        "the map's style exists"
    )
