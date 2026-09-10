# Pytest fixtures for the committed, CI-compatible frontend test suite
# (equity frontend checkpoint, section 14). These tests exercise the
# real, unmodified docs/app/*.js modules against small synthetic fixture
# data (tests/frontend/fixtures/docs/data/*) rather than the live
# artifacts under docs/data/ - so a coverage state the real published
# window does not currently contain (e.g. below 95%) can still be tested.
#
# No live network access is required or permitted: the maplibre-gl CDN
# import is intercepted and served from a local stub
# (fixtures/stubs/maplibre-gl.mjs); echarts is pre-stubbed via
# add_init_script so charts.js's own `if (window.echarts)` short-circuit
# means it never even attempts its CDN fetch. Any request that does
# escape interception is still recorded (see the `recorded_requests`
# fixture and the network-isolation test) so an accidental live call is
# caught rather than silently succeeding or silently failing.

import http.server
import os
import shutil
import socketserver
import threading
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
# Not hardcoded: Playwright resolves its own installed Chromium (via
# PLAYWRIGHT_BROWSERS_PATH in this sandbox, or its default cache location
# after `playwright install chromium` in GitHub Actions - see
# .github/workflows/frontend-tests.yml). CHROMIUM_PATH only overrides
# that when explicitly set, so this suite runs unmodified in both places.
CHROMIUM_PATH = os.environ.get("CHROMIUM_PATH")

MAPLIBRE_JS_URL = "https://cdn.jsdelivr.net/npm/maplibre-gl@6.8.0/dist/maplibre-gl.mjs"
MAPLIBRE_CSS_URL = "https://cdn.jsdelivr.net/npm/maplibre-gl@6.8.0/dist/maplibre-gl.css"
ECHARTS_URL = "https://cdn.jsdelivr.net/npm/echarts@6.1.0/dist/echarts.min.js"


@pytest.fixture(scope="session")
def serve_root(tmp_path_factory):
    """Assembles a self-contained webroot: the real docs/app/*.js
    (production code under test, unmodified) plus fixture data and the
    test harness HTML, entirely separate from docs/data/ so these tests
    never depend on - or risk mutating - real published artifacts."""
    root = tmp_path_factory.mktemp("frontend-serve-root")
    shutil.copytree(REPO_ROOT / "docs" / "app", root / "app")
    shutil.copytree(FIXTURES_DIR / "docs" / "data", root / "data")
    shutil.copy(FIXTURES_DIR / "test.html", root / "index.html")
    # The real, unmodified stylesheet - not a test-only stand-in. A CSS-
    # only bug (e.g. a `display` declaration silently overriding the
    # browser's `[hidden]` default) is otherwise invisible to this whole
    # suite, no matter how many assertions run against unstyled markup.
    shutil.copy(REPO_ROOT / "docs" / "styles.css", root / "styles.css")
    (root / "methodology.html").write_text("<!doctype html><title>Methodology</title><h1>Methodology (test fixture)</h1>")
    return root


@pytest.fixture(scope="session")
def http_server(serve_root):
    handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
        *args, directory=str(serve_root), **kwargs
    )
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROMIUM_PATH)
        yield b
        b.close()


@pytest.fixture
def page(browser, http_server):
    context = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = context.new_page()

    all_requests = []
    pg.on("request", lambda req: all_requests.append(req.url))
    pg.all_requests = all_requests  # exposed for assertions

    console_errors = []
    pg.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    pg.on("pageerror", lambda exc: console_errors.append(f"pageerror: {exc}"))
    pg.console_errors = console_errors

    maplibre_stub = (FIXTURES_DIR / "stubs" / "maplibre-gl.mjs").read_bytes()
    echarts_stub_src = (FIXTURES_DIR / "stubs" / "echarts-stub.js").read_text()

    pg.route(
        MAPLIBRE_JS_URL,
        lambda route: route.fulfill(status=200, content_type="text/javascript", body=maplibre_stub),
    )
    # No committed stub can satisfy the real pinned SRI hash on this
    # stylesheet link, and the app does not depend on it functioning -
    # let the browser fail the integrity check silently (styling only).
    pg.route(MAPLIBRE_CSS_URL, lambda route: route.abort())
    # echarts is never fetched at all: add_init_script below defines
    # window.echarts before any page script runs, and charts.js's
    # loadEcharts() short-circuits on that. This route only exists as a
    # backstop so a *failure* to stub would surface as a visible aborted
    # request rather than a silent real CDN call.
    pg.route(ECHARTS_URL, lambda route: route.abort())

    pg.add_init_script(echarts_stub_src)

    yield pg
    context.close()


@pytest.fixture
def load_app(page, http_server):
    """Navigates to the test harness and waits for main.js's startup
    fetches (meta/fields/history index, equity meta/index) to settle."""

    def _load(hash_fragment=None):
        # This suite (equity + field-polygons) predates the Production
        # view and is entirely about the Fields map, so a bare call with
        # no fragment keeps landing on the map - same as every existing
        # test expects - even though Production is now the application's
        # own default for a real, hash-less visit (see
        # test_production_frontend.py for that behaviour).
        if hash_fragment is None:
            hash_fragment = "top=map"
        url = http_server + "/index.html"
        if hash_fragment:
            url += f"#{hash_fragment}"
        page.goto(url, wait_until="load")
        page.wait_for_timeout(500)
        return page

    return _load
