// Equity data loading and in-memory caching (spec section 15.12/frontend
// checkpoint). Same lazy/cache discipline as state.js's field history:
// meta.json and index.json are loaded once at startup by main.js;
// companies/{slug}.json and fields/{slug}.json are fetched at most once
// each, only when actually selected. The browser only ever reads
// ./data/equity/* here - no NSTA or ArcGIS host is ever called, and a
// failure here must never take down the production map or field views
// (see main.js's isolation of the equity startup fetch).

import { DataLoadError, fetchJson } from "./state.js";

export { DataLoadError };

const EQUITY_META_URL = "./data/equity/meta.json";
const EQUITY_INDEX_URL = "./data/equity/index.json";

export const PRODUCTION_STREAMS = [
  { key: "oil_mbd", label: "Oil", unit: "mb/d" },
  { key: "dry_gas_mmscfd", label: "Dry gas", unit: "MMscf/d" },
  { key: "assoc_gas_mmscfd", label: "Associated gas", unit: "MMscf/d" },
  { key: "condensate_mbd", label: "Condensate", unit: "mb/d" },
];

export const LEGAL_ENTITY_LABEL = "Legal entity as recorded by NSTA";

let equityMetaPromise = null;
export function getEquityMeta() {
  if (!equityMetaPromise) {
    equityMetaPromise = fetchJson(EQUITY_META_URL);
  }
  return equityMetaPromise;
}

let equityIndexPromise = null;
export function getEquityIndex() {
  if (!equityIndexPromise) {
    equityIndexPromise = fetchJson(EQUITY_INDEX_URL);
  }
  return equityIndexPromise;
}

const companyCache = new Map();
export async function getCompanyEquity(slug) {
  if (companyCache.has(slug)) {
    return companyCache.get(slug);
  }
  const promise = fetchJson(`./data/equity/companies/${slug}.json`);
  companyCache.set(slug, promise);
  try {
    return await promise;
  } catch (err) {
    companyCache.delete(slug);
    throw err;
  }
}

const fieldEquityCache = new Map();
export async function getFieldEquity(slug) {
  if (fieldEquityCache.has(slug)) {
    return fieldEquityCache.get(slug);
  }
  const promise = fetchJson(`./data/equity/fields/${slug}.json`);
  fieldEquityCache.set(slug, promise);
  try {
    return await promise;
  } catch (err) {
    fieldEquityCache.delete(slug);
    throw err;
  }
}

// MURLACH is the one known, unresolved, unexplained case (spec section
// 15.11's MURLACH investigation). This is a display-only constant used to
// decide whether to show the standing UI note - it does not change any
// calculation, and the UI never speculates about the 2050 date's cause.
export const MURLACH_FIELD_SLUG = "murlach-pt-of-marnock-skua";
export const MURLACH_NOTE =
  "Some recent production is excluded because NSTA records MURLACH production " +
  "before the effective date of its available equity interests.";
