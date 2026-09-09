"""
Phase 2, step 1 (spec section 15.2 / 15.8 step 1).

Locates and downloads the NSTA field equity workbook, hashes it, and
reports what was found. Does NOT parse the workbook (see equity_parse.py)
and does NOT touch docs/data/.

Live discovery findings (2026-09-09) that shaped this script - see
etl/equity_schema_report.md for the full detail and the spec deviations
they imply:

- The NSTA Fields data theme page's "Current and historical field equity
  shares" link does not point to a file. It points to an ArcGIS Hub
  *search* page (https://open-data-ukcs-transition.hub.arcgis.com/search
  ?q=field+partners), which is a client-rendered SPA with no server-side
  link to scrape.
- That search page is scoped to ArcGIS Online org OZMfUznmLTnWccBc
  (orgUrlKey "ukcs-transition") - the same org that hosts the PPRS
  FeatureServer resolved in Phase 1.
- Resolving the same search term against the ArcGIS Online search API,
  scoped to that org, returns exactly one item: "Field Partners"
  (Document Link type), whose `url` property is a direct .xlsx download
  hosted on Azure Blob Storage (datanstauthority.blob.core.windows.net).

Nothing about this resolution path is hardcoded end-to-end: only the NSTA
page URL and the ArcGIS org ID are fixed constants (analogous to the item
IDs fixed in etl/discover.py). The link text, the search query, and the
final download URL are all re-derived from live pages/APIs on every run,
so a change on NSTA's end is followed rather than silently missed.

Run: python etl/equity_fetch.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

NSTA_FIELDS_PAGE = "https://www.nstauthority.co.uk/data-and-insights/data/themes/fields/"
ARCGIS_SEARCH_URL = "https://www.arcgis.com/sharing/rest/search"

# The NSTA/UKCS-transition ArcGIS Online org. Confirmed live (2026-09-09) by
# decoding the embedded site JSON on the Hub search page, and matches the
# org that hosts the PPRS FeatureServer resolved in etl/discover.py.
UKCS_ORG_ID = "OZMfUznmLTnWccBc"

CACHE_DIR = Path(__file__).parent / ".cache"
WORKBOOK_CACHE_PATH = CACHE_DIR / "equity_workbook.xlsx"
# Ephemeral run artifact (hash/date change on every fetch) - not committed,
# unlike etl/equity_schema_report.md which equity_parse.py writes and is
# tracked in git.
FETCH_REPORT_PATH = CACHE_DIR / "equity_fetch_report.json"

REQUEST_TIMEOUT_SECONDS = 30
USER_AGENT = "ukcs-equity-fetch/0.1"


class EquityFetchError(RuntimeError):
    """Raised when the equity workbook cannot be located or downloaded.
    Message must say exactly why. Never falls back to a cached copy."""


def find_equity_link(html: str, page_url: str) -> str:
    """Find the anchor on the NSTA Fields page whose visible text mentions
    'equity', and return its href resolved against page_url. Fails loudly
    if none or more than one are found, rather than guessing."""
    soup = BeautifulSoup(html, "html.parser")
    matches = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        if "equity" in text.lower():
            matches.append((text, a["href"]))

    if not matches:
        raise EquityFetchError(
            f"No link mentioning 'equity' found on {page_url}. The NSTA "
            "Fields data theme page structure may have changed; refusing "
            "to fall back to a cached URL."
        )
    if len(matches) > 1:
        raise EquityFetchError(
            f"Found {len(matches)} links mentioning 'equity' on {page_url}, "
            f"expected exactly 1: {matches}. Refusing to guess which is "
            "correct."
        )

    text, href = matches[0]
    resolved = urllib.parse.urljoin(page_url, href)
    print(f"Found equity link: text={text!r} href={resolved!r}")
    return resolved


def extract_hub_search_query(hub_url: str) -> str:
    """The NSTA link resolves to an ArcGIS Hub *search* page
    (*.hub.arcgis.com/search?q=...), not a file. Extract its q= parameter
    so the same search term can be run against the ArcGIS Online search
    API instead of scraping the Hub site's client-rendered SPA."""
    parsed = urllib.parse.urlparse(hub_url)
    if "hub.arcgis.com" not in parsed.netloc:
        raise EquityFetchError(
            f"Expected the equity link to resolve to an ArcGIS Hub URL "
            f"(*.hub.arcgis.com), got {hub_url!r}. The link may now point "
            "directly to a file - this script needs updating to handle "
            "that case rather than assuming a Hub search redirect."
        )
    query = urllib.parse.parse_qs(parsed.query).get("q")
    if not query:
        raise EquityFetchError(
            f"ArcGIS Hub URL {hub_url!r} has no 'q' search parameter to "
            "resolve against the ArcGIS Online search API."
        )
    return query[0]


def resolve_workbook_item(search_query: str, session: requests.Session) -> dict:
    """Query the ArcGIS Online search API, scoped to the NSTA/UKCS-transition
    org, for the search term extracted from the Hub search link. Requires
    exactly one result - refuses to guess between multiple candidates
    (no fuzzy matching, same rule as field/company name matching)."""
    q = f"{search_query} orgid:{UKCS_ORG_ID}"
    print(f"\nQuerying ArcGIS Online search API: q={q!r}")
    resp = session.get(
        ARCGIS_SEARCH_URL,
        params={"q": q, "f": "json", "num": 20},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if resp.status_code != 200:
        raise EquityFetchError(
            f"ArcGIS search API returned HTTP {resp.status_code} for "
            f"query {q!r}."
        )
    data = resp.json()
    if "error" in data:
        err = data["error"]
        raise EquityFetchError(
            f"ArcGIS search API error for query {q!r}: "
            f"code={err.get('code')} message={err.get('message')}"
        )

    results = data.get("results", [])
    if not results:
        raise EquityFetchError(
            f"ArcGIS search for {q!r} returned zero results in org "
            f"{UKCS_ORG_ID}. The dataset may have been renamed or removed "
            "from the org."
        )
    if len(results) > 1:
        titles = [r.get("title") for r in results]
        raise EquityFetchError(
            f"ArcGIS search for {q!r} returned {len(results)} results, "
            f"expected exactly 1: {titles}. Refusing to guess which item "
            "is the equity workbook."
        )

    item = results[0]
    url = item.get("url")
    if not url:
        raise EquityFetchError(
            f"Resolved item {item.get('id')} ({item.get('title')!r}) has "
            f"no 'url' property - not a directly downloadable file. Item "
            f"type: {item.get('type')!r}."
        )
    print(
        f"Resolved item: id={item.get('id')} title={item.get('title')!r} "
        f"type={item.get('type')!r} url={url!r}"
    )
    return item


def download_workbook(url: str, session: requests.Session) -> tuple[bytes, str | None]:
    print(f"\nDownloading workbook from {url}")
    resp = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    if resp.status_code != 200:
        raise EquityFetchError(
            f"Downloading workbook from {url} returned HTTP {resp.status_code}."
        )
    content = resp.content
    if not content:
        raise EquityFetchError(f"Downloaded workbook from {url} is empty (0 bytes).")
    last_modified = resp.headers.get("Last-Modified")
    print(f"Downloaded {len(content)} bytes. Last-Modified: {last_modified!r}")
    return content, last_modified


def fetch_equity_workbook(session: requests.Session | None = None) -> dict:
    """Orchestrates discovery end-to-end: NSTA page -> equity link -> Hub
    search query -> ArcGIS search API -> resolved item -> downloaded bytes.
    Never hardcodes the resolved .xlsx URL."""
    session = session or requests.Session()
    session.headers.setdefault("User-Agent", USER_AGENT)

    print(f"--- Fetching NSTA Fields page: {NSTA_FIELDS_PAGE} ---")
    resp = session.get(NSTA_FIELDS_PAGE, timeout=REQUEST_TIMEOUT_SECONDS)
    if resp.status_code != 200:
        raise EquityFetchError(
            f"NSTA Fields page {NSTA_FIELDS_PAGE} returned HTTP {resp.status_code}."
        )
    hub_search_url = find_equity_link(resp.text, NSTA_FIELDS_PAGE)
    search_query = extract_hub_search_query(hub_search_url)
    item = resolve_workbook_item(search_query, session)
    content, last_modified = download_workbook(item["url"], session)
    sha256 = hashlib.sha256(content).hexdigest()

    return {
        "nsta_page_url": NSTA_FIELDS_PAGE,
        "hub_search_url": hub_search_url,
        "resolved_item_id": item.get("id"),
        "resolved_item_title": item.get("title"),
        "resolved_item_type": item.get("type"),
        "resolved_url": item["url"],
        "last_modified": last_modified,
        "sha256": sha256,
        "content_length": len(content),
        "content": content,
    }


def main() -> int:
    try:
        result = fetch_equity_workbook()

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        WORKBOOK_CACHE_PATH.write_bytes(result["content"])
        print(f"\nWorkbook written to {WORKBOOK_CACHE_PATH}")

        report = {k: v for k, v in result.items() if k != "content"}
        report["cached_at"] = str(WORKBOOK_CACHE_PATH)
        FETCH_REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True))
        print(f"Fetch report written to {FETCH_REPORT_PATH}")

        print("\n--- Fetch summary ---")
        for k, v in report.items():
            print(f"{k}: {v}")

        return 0
    except EquityFetchError as e:
        print(f"\nEQUITY FETCH FAILED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
