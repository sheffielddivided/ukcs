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

// operators.json is either the full index WITH each operator's series
// embedded (small build), or an index with series omitted plus separate
// operators/{slug}.json files (spec 9.4's >2MB split - meta.json's
// operators_split flag says which). Either way this loads operators.json
// at most once and caches per-operator series lookups, mirroring
// getFieldHistory's lazy/cached behaviour.
let operatorsIndexPromise = null;
function getOperatorsIndex() {
  if (!operatorsIndexPromise) {
    operatorsIndexPromise = fetchJson("./data/operators.json");
  }
  return operatorsIndexPromise;
}

const operatorHistoryCache = new Map();

export async function getOperatorHistory(slug, operatorsSplit) {
  if (operatorHistoryCache.has(slug)) {
    return operatorHistoryCache.get(slug);
  }
  const promise = (async () => {
    if (operatorsSplit) {
      return fetchJson(`./data/operators/${slug}.json`);
    }
    const index = await getOperatorsIndex();
    const entry = index.operators[slug];
    if (!entry || !entry.series) {
      throw new DataLoadError(
        `Operator '${slug}' not found (or has no series) in operators.json`
      );
    }
    return { slug, name: entry.name, series: entry.series };
  })();
  operatorHistoryCache.set(slug, promise);
  try {
    return await promise;
  } catch (err) {
    operatorHistoryCache.delete(slug);
    throw err;
  }
}
