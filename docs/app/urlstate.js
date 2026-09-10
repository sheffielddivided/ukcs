// Shared URL state via location.hash (extended for Production overview /
// Licence portfolio - never a second mechanism). Never touches the path,
// so it stays compatible with the /ukcs/ GitHub Pages subpath, and never
// exposes internal file paths - only this fixed, documented parameter
// vocabulary. Uses history.replaceState so ordinary interaction never
// triggers a full page reload or pollutes browser history with every
// click, while the resulting URL remains copyable and restorable.
//
// Absence of `top` means Production (the default view after a normal
// page load with no URL state). Keys are namespaced by prefix so each
// top-level view (Production `p*`, Fields map `view`/`slug`/`metric`/
// `stream`/`m*`, Licence portfolio `l*`) owns a disjoint set, and
// switchTopView() clears every OTHER view's keys on a top-level switch
// (spec: "Switching between views must not leak layers, filters,
// selections or URL state between the two maps").

const VALID_TOP = new Set(["production", "map", "licence"]);
const VALID_VIEWS = new Set(["field", "equity", "operator"]);
const VALID_METRICS = new Set(["equity", "operator"]);
const VALID_PSPLIT = new Set(["commodity", "company", "field"]);
const VALID_PGRAIN = new Set(["group", "entity"]);
const VALID_PFREQ = new Set(["monthly", "annual"]);
const VALID_PSTATUS = new Set(["current", "historical", "all"]);
const VALID_PTOPN = new Set(["5", "10", "15", "20"]);
const VALID_LMODE = new Set(["current", "historical"]);
const VALID_LOPERATED = new Set(["all", "operated", "nonoperated"]);

// Fixed, deterministic serialization order (spec: "deterministic
// parameter order") - every key below is written in this order whenever
// present, regardless of the order patches were applied in.
const KEY_ORDER = [
  "top",
  "view", "slug", "metric", "stream",
  "psplit", "pfreq", "pgrain", "pgroup", "ptopn", "pfields", "pfrom", "pto", "pstatus",
  "mbubbles", "mpolygons",
  "lmode", "lgroup", "ldate", "loperated", "lstatus", "llicence",
];

const PREFIX_BY_TOP = {
  map: ["view", "slug", "metric", "stream", "mbubbles", "mpolygons"],
  production: ["psplit", "pfreq", "pgrain", "pgroup", "ptopn", "pfields", "pfrom", "pto", "pstatus"],
  licence: ["lmode", "lgroup", "ldate", "loperated", "lstatus", "llicence"],
};

function validate(key, value) {
  if (value == null || value === "") return undefined;
  switch (key) {
    case "top":
      return VALID_TOP.has(value) ? value : undefined;
    case "view":
      return VALID_VIEWS.has(value) ? value : undefined;
    case "metric":
      return VALID_METRICS.has(value) ? value : undefined;
    case "psplit":
      return VALID_PSPLIT.has(value) ? value : undefined;
    case "pgrain":
      return VALID_PGRAIN.has(value) ? value : undefined;
    case "pfreq":
      return VALID_PFREQ.has(value) ? value : undefined;
    case "ptopn":
      return VALID_PTOPN.has(value) ? value : undefined;
    case "pstatus":
      return VALID_PSTATUS.has(value) ? value : undefined;
    case "mbubbles":
    case "mpolygons":
      return value === "0" || value === "1" ? value : undefined;
    case "lmode":
      return VALID_LMODE.has(value) ? value : undefined;
    case "loperated":
      return VALID_LOPERATED.has(value) ? value : undefined;
    default:
      return value; // slug/stream/pgroup/pfields/pfrom/pto/lgroup/ldate/lstatus/llicence: free-form
  }
}

/** Parses the full current URL state. Invalid values for a constrained
 * key are dropped silently (spec: "invalid state fails gracefully") -
 * never thrown, never left as a raw unvalidated string a renderer might
 * trust. */
export function parseUrlState() {
  const raw = location.hash.replace(/^#/, "");
  const state = {};
  if (!raw) return state;
  const params = new URLSearchParams(raw);
  for (const key of KEY_ORDER) {
    if (!params.has(key)) continue;
    const value = validate(key, params.get(key));
    if (value !== undefined) state[key] = value;
  }
  return state;
}

function serialize(state) {
  const params = new URLSearchParams();
  for (const key of KEY_ORDER) {
    if (state[key] != null && state[key] !== "") params.set(key, state[key]);
  }
  const qs = params.toString();
  return qs ? `${location.pathname}${location.search}#${qs}` : `${location.pathname}${location.search}`;
}

/** Merges `patch` into the CURRENT full URL state and writes the result
 * (history.replaceState - never a page reload, never a new history
 * entry per interaction). A key set to null/undefined/"" in `patch` is
 * removed. Keys not mentioned in `patch` are left untouched, so
 * independent widgets (filters, split mode, a drill-down selection)
 * never clobber each other's state. */
export function updateUrlState(patch) {
  const current = parseUrlState();
  const next = { ...current };
  for (const [key, value] of Object.entries(patch)) {
    if (value == null || value === "") delete next[key];
    else next[key] = String(value);
  }
  history.replaceState(null, "", serialize(next));
}

/** Full-replace helper retained for the existing Fields-map panel
 * open/close call sites (field/equity/operator detail), which have
 * always treated their own params as the complete relevant state for
 * that action - equivalent to updateUrlState() with every OTHER
 * map-prefixed key explicitly cleared first, so opening one panel
 * always replaces (never merges with) a previously open one. */
export function setUrlState(state) {
  const current = parseUrlState();
  const next = { ...current };
  for (const key of PREFIX_BY_TOP.map) delete next[key];
  for (const [key, value] of Object.entries(state)) {
    if (value != null && value !== "") next[key] = String(value);
  }
  history.replaceState(null, "", serialize(next));
}

/** Switches the top-level view, clearing every OTHER top-level view's
 * own keys (spec: no state leakage between views) while preserving the
 * new view's existing keys (e.g. a restored deep link). `top` itself is
 * omitted from the URL when it equals "production" (the default), so a
 * plain reload of the production view keeps the shortest possible URL. */
export function switchTopView(top) {
  const current = parseUrlState();
  const next = {};
  if (top !== "production") next.top = top;
  for (const key of PREFIX_BY_TOP[top] || []) {
    if (current[key] != null) next[key] = current[key];
  }
  history.replaceState(null, "", serialize(next));
}

/** Absence of `top` means Production - EXCEPT a legacy deep link that
 * carries a `view` param (field/equity/operator) but no `top` predates
 * the Production view entirely and always addressed the Fields map, so
 * it must keep resolving to `map` for every pre-existing saved/shared
 * link and every existing frontend test to keep working unmodified. */
export function currentTopView() {
  const state = parseUrlState();
  if (state.top) return state.top;
  if (state.view) return "map";
  return "production";
}
