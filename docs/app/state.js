// Data loading and in-memory caching (spec section 5.1 / 10.3).
//
// The browser only ever reads ./data/* here, pre-built by etl/build.py -
// no NSTA or ArcGIS host is ever called. Field history is lazy-loaded on
// selection and cached in memory for the lifetime of the page (spec
// 10.3): history/{slug}.json files are fetched at most once each, never
// all up front.

export class DataLoadError extends Error {}

// Distinguishes network failure, HTTP error and JSON-parse failure rather
// than collapsing them into one message - the same discipline the ETL
// applies to ArcGIS calls (spec section 3), applied here to our own
// static artifacts.
export async function fetchJson(url) {
  let response;
  try {
    response = await fetch(url);
  } catch (networkErr) {
    throw new DataLoadError(
      `Network error fetching ${url}: ${networkErr.message} ` +
        "(the request never completed - check the browser is online and " +
        "the file is being served, not opened via file://)"
    );
  }
  if (!response.ok) {
    throw new DataLoadError(
      `HTTP ${response.status} ${response.statusText} fetching ${url}`
    );
  }
  try {
    return await response.json();
  } catch (parseErr) {
    throw new DataLoadError(
      `Response from ${url} was not valid JSON: ${parseErr.message}`
    );
  }
}

const historyCache = new Map();

export async function getFieldHistory(slug) {
  if (historyCache.has(slug)) {
    return historyCache.get(slug);
  }
  const promise = fetchJson(`./data/history/${slug}.json`);
  historyCache.set(slug, promise);
  try {
    return await promise;
  } catch (err) {
    // Don't cache a failed fetch - a transient network error shouldn't
    // permanently poison the cache entry for this field.
    historyCache.delete(slug);
    throw err;
  }
}
