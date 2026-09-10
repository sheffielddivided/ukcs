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

// Production overview compact artifacts (Deliverable 1). Each is
// fetched and cached at most once, on first use by whichever split mode
// needs it - monthly_totals/meta are small enough for the default view's
// eager load; company_groups/legal_entities/fields are larger and are
// only ever requested when their split mode is actually selected.
const overviewCache = new Map();

export function getOverviewArtifact(name) {
  if (!overviewCache.has(name)) {
    const promise = fetchJson(`./data/overview/${name}.json`);
    overviewCache.set(name, promise);
    promise.catch(() => overviewCache.delete(name));
  }
  return overviewCache.get(name);
}

// Current licence-portfolio artifacts (Workstream 4) - index is small
// (fetched eagerly by the Licence portfolio view); per-group detail and
// the full polygon GeoJSON are fetched lazily.
let licencePortfolioIndexPromise = null;
export function getLicencePortfolioIndex() {
  if (!licencePortfolioIndexPromise) {
    licencePortfolioIndexPromise = fetchJson("./data/licence_portfolio_index.json");
  }
  return licencePortfolioIndexPromise;
}

const licenceGroupCache = new Map();
export function getLicencePortfolioGroup(slug) {
  if (!licenceGroupCache.has(slug)) {
    const promise = fetchJson(`./data/licence_portfolio_groups/${slug}.json`);
    licenceGroupCache.set(slug, promise);
    promise.catch(() => licenceGroupCache.delete(slug));
  }
  return licenceGroupCache.get(slug);
}

let licencePortfolioGeojsonPromise = null;
export function getLicencePortfolioGeojson() {
  if (!licencePortfolioGeojsonPromise) {
    licencePortfolioGeojsonPromise = fetchJson("./data/licence_portfolio.geojson");
  }
  return licencePortfolioGeojsonPromise;
}

// Historical licence-interest artifacts (Deliverable 3).
let licenceHistoryIndexPromise = null;
export function getLicenceHistoryIndex() {
  if (!licenceHistoryIndexPromise) {
    licenceHistoryIndexPromise = fetchJson("./data/licence_history_index.json");
  }
  return licenceHistoryIndexPromise;
}

let licenceHistoryGeojsonPromise = null;
export function getLicenceHistoryGeojson() {
  if (!licenceHistoryGeojsonPromise) {
    licenceHistoryGeojsonPromise = fetchJson("./data/licence_history.geojson");
  }
  return licenceHistoryGeojsonPromise;
}
