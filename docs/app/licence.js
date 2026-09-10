// Licence portfolio view (Deliverable 2/3, spec approved 2026-09-10
// continuation). "Current portfolio" sub-view renders the already-
// published current subarea-equity-holder polygons
// (docs/data/licence_portfolio.geojson, etl/licence_portfolio.py).
// "Historical licence interests and operators" (Deliverable 3) renders
// docs/data/licence_history.geojson (etl/licence_history.py) - recorded
// historical licensee/operator NAMES and geometry by date, deliberately
// NEVER a historical equity percentage (no NSTA source publishes one -
// see etl/licence_history.py's module docstring). Both sub-views share
// ONE isolated MapLibre instance (their own source/layer sets, visible
// one at a time) - a completely separate map object from the Fields map
// (docs/app/map.js), so switching top-level views never leaks layers,
// filters, selection or URL state between the two (spec: "map state/
// legends must be fully isolated from Fields map").
//
// No area/hectarage figure is shown anywhere in this view: the source
// geometry is unprojected WGS84 and no projected-CRS area methodology
// has been implemented or tested, so an area figure would be either
// wrong or fabricated-looking precision (spec: "explicitly omit area
// unless a proper projected CRS + documented units + tested
// methodology + reconciliation exist").

import {
  Map as MapLibreMap,
  AttributionControl,
  NavigationControl,
} from "https://cdn.jsdelivr.net/npm/maplibre-gl@6.8.0/dist/maplibre-gl.mjs";
import {
  getLicencePortfolioIndex,
  getLicencePortfolioGeojson,
  getLicenceHistoryIndex,
  getLicenceHistoryGeojson,
  DataLoadError,
  fetchJson,
} from "./state.js";
import { parseUrlState, updateUrlState } from "./urlstate.js";

const SOURCE_ID = "licence-portfolio";
const FILL_LAYER_ID = "licence-fill";
const OUTLINE_LAYER_ID = "licence-outline";
const LABEL_LAYER_ID = "licence-labels";
const SELECTED_LAYER_ID = "licence-selected";

const HIST_SOURCE_ID = "licence-history";
const HIST_FILL_LAYER_ID = "licence-history-fill";
const HIST_OUTLINE_LAYER_ID = "licence-history-outline";
const HIST_SELECTED_LAYER_ID = "licence-history-selected";

const NO_HISTORICAL_EQUITY_STATEMENT =
  "Historical geometry and recorded organisation names are available, but historical subarea " +
  "equity percentages cannot be reconstructed from the published NSTA source.";

const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors';

let root = null;
let map = null;
let portfolioIndex = null; // {slug: {name, distinct_licence_count, ...}}
let portfolioGeojson = null;
let meta = null;
let selectedFeatureKey = null; // "licref|blockref|subarea"

let historyMeta = null;
let historyGeojson = null;
let selectedEpisodeId = null;

function el(html) {
  const div = document.createElement("div");
  div.innerHTML = html.trim();
  return div.firstElementChild;
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function featureKey(props) {
  return `${props.licence_reference || ""}|${props.block_reference || ""}|${props.subarea_name || ""}`;
}

// ---------------------------------------------------------------------------
// Init / shell
// ---------------------------------------------------------------------------

export async function initLicenceView(container) {
  root = container;
  root.innerHTML = `
    <div id="licence-error" class="panel-error" hidden></div>
    <div class="production-tabs" role="tablist" aria-label="Licence portfolio mode">
      <button type="button" role="tab" data-lmode="current" class="tab-btn active">Current portfolio</button>
      <button type="button" role="tab" data-lmode="historical" class="tab-btn">Historical licence interests and operators</button>
    </div>
    <div id="licence-map-wrap">
      <div id="licence-map"></div>
    </div>
    <div id="licence-current-view">
      <div id="licence-filters" class="production-filters"></div>
      <div id="licence-active-filters" class="production-active-filters" aria-live="polite"></div>
      <div id="licence-summary" class="production-stats"></div>
      <div class="legend" id="licence-legend">
        <h2>Operated / Non-operated</h2>
        <div class="legend-row"><span class="legend-swatch licence-operated"></span> Operated (OP)</div>
        <div class="legend-row"><span class="legend-swatch licence-nonoperated"></span> Non-operated (NOP)</div>
        <div class="legend-note">Colour and the OP/NOP label on the map both encode this - never colour alone.</div>
      </div>
      <div id="licence-detail"></div>
    </div>
    <div id="licence-historical-view" hidden>
      <div class="panel-caveat">${escapeHtml(NO_HISTORICAL_EQUITY_STATEMENT)}</div>
      <div id="licence-history-filters" class="production-filters"></div>
      <div id="licence-history-active-filters" class="production-active-filters" aria-live="polite"></div>
      <div id="licence-history-summary" class="production-stats"></div>
      <div id="licence-history-detail"></div>
    </div>
  `;

  for (const btn of root.querySelectorAll('[data-lmode]')) {
    btn.addEventListener("click", () => {
      // lgroup/lstatus/llicence mean something different in each
      // sub-mode (a group SLUG in Current portfolio vs. a recorded
      // operator-group NAME in Historical interests) - clearing them on
      // every sub-mode switch avoids a stale filter from one mode
      // silently producing an empty result in the other.
      updateUrlState({
        lmode: btn.dataset.lmode === "current" ? null : btn.dataset.lmode,
        lgroup: null,
        lstatus: null,
        llicence: null,
      });
      refreshFromUrl();
    });
  }

  try {
    [portfolioIndex, meta] = await Promise.all([
      getLicencePortfolioIndex(),
      fetchJson("./data/meta.json"),
    ]);
  } catch (err) {
    showError(err);
    return;
  }

  await refreshFromUrl();
}

function showError(err) {
  const box = document.getElementById("licence-error");
  if (!box) return;
  const category = err instanceof DataLoadError ? "Licence portfolio data" : "Unexpected error";
  box.textContent = `${category} failed to load.\n\n${err.message}`;
  box.hidden = false;
}

function clearError() {
  const box = document.getElementById("licence-error");
  if (box) box.hidden = true;
}

// ---------------------------------------------------------------------------
// URL-driven refresh
// ---------------------------------------------------------------------------

export async function refreshFromUrl() {
  if (!root) return;
  clearError();
  const state = parseUrlState();
  const mode = state.lmode === "historical" ? "historical" : "current";

  for (const btn of root.querySelectorAll('[data-lmode]')) {
    const active = btn.dataset.lmode === mode;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", String(active));
  }
  document.getElementById("licence-current-view").hidden = mode !== "current";
  document.getElementById("licence-historical-view").hidden = mode !== "historical";

  await ensureMap();
  if (map) map.resize();

  if (mode === "current") {
    setHistoryLayersVisible(false);
    setCurrentLayersVisible(true);
    try {
      if (!portfolioGeojson) portfolioGeojson = await getLicencePortfolioGeojson();
    } catch (err) {
      showError(err);
      return;
    }
    renderFilterInputs(state);
    renderActiveFilterChips(state);
    applyFilters(state);
    renderSummary(state);
  } else {
    setCurrentLayersVisible(false);
    setHistoryLayersVisible(true);
    try {
      if (!historyMeta) historyMeta = await getLicenceHistoryIndex();
      if (!historyGeojson) historyGeojson = await getLicenceHistoryGeojson();
    } catch (err) {
      showError(err);
      return;
    }
    await ensureHistoryLayers();
    renderHistoryFilterInputs(state);
    renderHistoryActiveFilterChips(state);
    applyHistoryFilters(state);
    renderHistorySummary(state);
  }
}

// ---------------------------------------------------------------------------
// Map (own isolated instance - never shares state with the Fields map)
// ---------------------------------------------------------------------------

// Memoized so concurrent callers (the eager top-nav-driven init at
// startup and a later restoreFromUrl() re-entry once other startup
// fetches finish) always await the SAME in-flight map creation instead
// of each constructing their own MapLibre instance and racing on the
// shared `map` module variable.
let ensureMapPromise = null;

function ensureMap() {
  if (ensureMapPromise) return ensureMapPromise;
  ensureMapPromise = new Promise((resolve) => {
    map = new MapLibreMap({
      container: "licence-map",
      attributionControl: false,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            maxzoom: 19,
            attribution: OSM_ATTRIBUTION,
          },
        },
        layers: [{ id: "osm", type: "raster", source: "osm" }],
      },
      center: [-1.5, 58],
      zoom: 5,
    });
    map.addControl(new AttributionControl({ compact: false }));
    map.addControl(new NavigationControl(), "top-right");

    map.on("load", () => {
      map.addSource(SOURCE_ID, { type: "geojson", data: portfolioGeojson });

      map.addLayer({
        id: FILL_LAYER_ID,
        type: "fill",
        source: SOURCE_ID,
        paint: {
          "fill-color": ["case", ["get", "operated"], "#1baf7a", "#eda100"],
          "fill-opacity": 0.45,
        },
      });
      map.addLayer({
        id: OUTLINE_LAYER_ID,
        type: "line",
        source: SOURCE_ID,
        paint: { "line-color": "#3a3a3a", "line-width": 0.75, "line-opacity": 0.6 },
      });
      map.addLayer({
        id: LABEL_LAYER_ID,
        type: "symbol",
        source: SOURCE_ID,
        layout: {
          "text-field": ["case", ["get", "operated"], "OP", "NOP"],
          "text-size": 10,
          "text-font": ["Noto Sans Regular"],
          "symbol-placement": "point",
        },
        paint: {
          "text-color": "#1a1a1a",
          "text-halo-color": "#ffffff",
          "text-halo-width": 1.2,
        },
      });
      map.addLayer({
        id: SELECTED_LAYER_ID,
        type: "line",
        source: SOURCE_ID,
        filter: ["==", ["get", "licence_reference"], "__none__"],
        paint: { "line-color": "#1d5fd6", "line-width": 3, "line-opacity": 0.95 },
      });

      map.on("mouseenter", FILL_LAYER_ID, () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", FILL_LAYER_ID, () => (map.getCanvas().style.cursor = ""));
      map.on("click", FILL_LAYER_ID, (e) => {
        const props = e.features[0].properties;
        selectedFeatureKey = featureKey(props);
        updateSelectedLayerFilter();
        renderDetail(props);
      });

      resolve();
    });
  });
}

function setCurrentLayersVisible(visible) {
  if (!map) return;
  for (const id of [FILL_LAYER_ID, OUTLINE_LAYER_ID, LABEL_LAYER_ID, SELECTED_LAYER_ID]) {
    if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
  }
}

function setHistoryLayersVisible(visible) {
  if (!map) return;
  for (const id of [HIST_FILL_LAYER_ID, HIST_OUTLINE_LAYER_ID, HIST_SELECTED_LAYER_ID]) {
    if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
  }
}

// Added lazily, the first time the Historical sub-view is actually
// opened - never fetched or rendered just because the Current
// portfolio sub-view (or the Fields map, or Production) is in use.
let ensureHistoryLayersPromise = null;

function ensureHistoryLayers() {
  if (ensureHistoryLayersPromise) return ensureHistoryLayersPromise;
  ensureHistoryLayersPromise = new Promise((resolve) => {
    map.addSource(HIST_SOURCE_ID, { type: "geojson", data: historyGeojson });
    map.addLayer({
      id: HIST_FILL_LAYER_ID,
      type: "fill",
      source: HIST_SOURCE_ID,
      paint: { "fill-color": "#8855dd", "fill-opacity": 0.35 },
    });
    map.addLayer({
      id: HIST_OUTLINE_LAYER_ID,
      type: "line",
      source: HIST_SOURCE_ID,
      paint: { "line-color": "#4a2f7a", "line-width": 0.75, "line-opacity": 0.7 },
    });
    map.addLayer({
      id: HIST_SELECTED_LAYER_ID,
      type: "line",
      source: HIST_SOURCE_ID,
      filter: ["==", ["get", "episode_id"], -1],
      paint: { "line-color": "#1d5fd6", "line-width": 3, "line-opacity": 0.95 },
    });
    map.on("mouseenter", HIST_FILL_LAYER_ID, () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", HIST_FILL_LAYER_ID, () => (map.getCanvas().style.cursor = ""));
    map.on("click", HIST_FILL_LAYER_ID, (e) => {
      const props = e.features[0].properties;
      selectedEpisodeId = props.episode_id;
      if (map.getLayer(HIST_SELECTED_LAYER_ID)) {
        map.setFilter(HIST_SELECTED_LAYER_ID, ["==", ["get", "episode_id"], selectedEpisodeId]);
      }
      renderHistoryDetail(props);
    });
    resolve();
  });
  return ensureHistoryLayersPromise;
}

function updateSelectedLayerFilter() {
  if (!map || !map.getLayer(SELECTED_LAYER_ID)) return;
  if (!selectedFeatureKey) {
    map.setFilter(SELECTED_LAYER_ID, ["==", ["get", "licence_reference"], "__none__"]);
    return;
  }
  const [licref, blockref, subarea] = selectedFeatureKey.split("|");
  map.setFilter(SELECTED_LAYER_ID, [
    "all",
    ["==", ["get", "licence_reference"], licref],
    ["==", ["get", "block_reference"], blockref],
    ["==", ["get", "subarea_name"], subarea],
  ]);
}

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

function buildMapFilter(state) {
  const clauses = ["all"];
  if (state.lgroup) clauses.push(["==", ["get", "group_slug"], state.lgroup]);
  if (state.loperated === "operated") clauses.push(["==", ["get", "operated"], true]);
  else if (state.loperated === "nonoperated") clauses.push(["==", ["get", "operated"], false]);
  if (state.lstatus) clauses.push(["==", ["get", "licence_status"], state.lstatus]);
  if (state.llicence) clauses.push(["==", ["get", "licence_reference"], state.llicence]);
  return clauses.length > 1 ? clauses : null;
}

function filteredFeatures(state) {
  if (!portfolioGeojson) return [];
  return portfolioGeojson.features.filter((f) => {
    const p = f.properties;
    if (state.lgroup && p.group_slug !== state.lgroup) return false;
    if (state.loperated === "operated" && !p.operated) return false;
    if (state.loperated === "nonoperated" && p.operated) return false;
    if (state.lstatus && p.licence_status !== state.lstatus) return false;
    if (state.llicence && p.licence_reference !== state.llicence) return false;
    return true;
  });
}

function applyFilters(state) {
  const filter = buildMapFilter(state);
  for (const id of [FILL_LAYER_ID, OUTLINE_LAYER_ID, LABEL_LAYER_ID]) {
    if (map.getLayer(id)) map.setFilter(id, filter);
  }
}

function distinctStatuses() {
  if (!portfolioGeojson) return [];
  return [...new Set(portfolioGeojson.features.map((f) => f.properties.licence_status).filter(Boolean))].sort();
}

function renderFilterInputs(state) {
  const box = document.getElementById("licence-filters");
  const groupNames = Object.entries(portfolioIndex || {})
    .map(([slug, g]) => ({ slug, name: g.name }))
    .sort((a, b) => a.name.localeCompare(b.name));
  const statuses = distinctStatuses();
  const currentGroupName = state.lgroup ? groupNames.find((g) => g.slug === state.lgroup)?.name || "" : "";

  box.innerHTML = `
    <label>Company group
      <input type="text" id="lf-group" list="licence-group-list" value="${escapeHtml(currentGroupName)}" placeholder="All groups" autocomplete="off" />
      <datalist id="licence-group-list">
        ${groupNames.map((g) => `<option value="${escapeHtml(g.name)}"></option>`).join("")}
      </datalist>
    </label>
    <label>Operated
      <select id="lf-operated">
        <option value="" ${!state.loperated || state.loperated === "all" ? "selected" : ""}>All</option>
        <option value="operated" ${state.loperated === "operated" ? "selected" : ""}>Operated</option>
        <option value="nonoperated" ${state.loperated === "nonoperated" ? "selected" : ""}>Non-operated</option>
      </select>
    </label>
    <label>Licence status
      <select id="lf-status">
        <option value="" ${!state.lstatus ? "selected" : ""}>All</option>
        ${statuses.map((s) => `<option value="${escapeHtml(s)}" ${state.lstatus === s ? "selected" : ""}>${escapeHtml(s)}</option>`).join("")}
      </select>
    </label>
    <label>Selected licence
      <input type="text" id="lf-licence" list="licence-ref-list" value="${escapeHtml(state.llicence || "")}" placeholder="All licences" autocomplete="off" />
      <datalist id="licence-ref-list">
        ${[...new Set(filteredFeatures(state).map((f) => f.properties.licence_reference).filter(Boolean))]
          .sort()
          .slice(0, 500)
          .map((r) => `<option value="${escapeHtml(r)}"></option>`)
          .join("")}
      </datalist>
    </label>
    <button type="button" id="lf-fit">Fit portfolio</button>
    <button type="button" id="lf-clear">Clear filters</button>
  `;

  document.getElementById("lf-group").addEventListener("change", (e) => {
    const match = groupNames.find((g) => g.name === e.target.value);
    updateUrlState({ lgroup: match ? match.slug : null });
    refreshFromUrl();
  });
  document.getElementById("lf-operated").addEventListener("change", (e) => {
    updateUrlState({ loperated: e.target.value || null });
    refreshFromUrl();
  });
  document.getElementById("lf-status").addEventListener("change", (e) => {
    updateUrlState({ lstatus: e.target.value || null });
    refreshFromUrl();
  });
  document.getElementById("lf-licence").addEventListener("change", (e) => {
    updateUrlState({ llicence: e.target.value.trim() || null });
    refreshFromUrl();
  });
  document.getElementById("lf-fit").addEventListener("click", () => fitToFiltered(state));
  document.getElementById("lf-clear").addEventListener("click", () => {
    updateUrlState({ lgroup: null, loperated: null, lstatus: null, llicence: null });
    refreshFromUrl();
  });
}

function renderActiveFilterChips(state) {
  const box = document.getElementById("licence-active-filters");
  const chips = [];
  if (state.lgroup) chips.push(`Group: ${portfolioIndex[state.lgroup]?.name || state.lgroup}`);
  if (state.loperated && state.loperated !== "all") chips.push(`Operated: ${state.loperated}`);
  if (state.lstatus) chips.push(`Status: ${state.lstatus}`);
  if (state.llicence) chips.push(`Licence: ${state.llicence}`);
  box.textContent = chips.length ? `Active filters: ${chips.join(", ")}` : "";
}

function fitToFiltered(state) {
  const features = filteredFeatures(state);
  if (features.length === 0) return;
  let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;
  const walk = (coords) => {
    if (typeof coords[0] === "number") {
      const [lng, lat] = coords;
      if (lng < minLng) minLng = lng;
      if (lng > maxLng) maxLng = lng;
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
    } else {
      coords.forEach(walk);
    }
  };
  for (const f of features) walk(f.geometry.coordinates);
  if (minLng === Infinity) return;
  map.fitBounds([[minLng, minLat], [maxLng, maxLat]], { padding: 40, maxZoom: 12 });
}

// ---------------------------------------------------------------------------
// Summary (validated metrics only - no area figure, see module docstring)
// ---------------------------------------------------------------------------

function renderSummary(state) {
  const box = document.getElementById("licence-summary");
  const features = filteredFeatures(state);
  if (features.length === 0) {
    box.innerHTML = `<div class="production-empty">No licences match the selected filters.</div>`;
    return;
  }
  const distinctLicences = new Set(features.map((f) => f.properties.licence_reference).filter(Boolean));
  const distinctSubareas = new Set(
    features.map((f) => `${f.properties.licence_reference}|${f.properties.block_reference}|${f.properties.subarea_name}`)
  );
  const operatedCount = features.filter((f) => f.properties.operated).length;
  const nonOperatedCount = features.length - operatedCount;
  box.innerHTML = `
    <ul>
      <li>Distinct licences: ${distinctLicences.size}</li>
      <li>Distinct subareas: ${distinctSubareas.size}</li>
      <li>Operated subareas: ${operatedCount}</li>
      <li>Non-operated subareas: ${nonOperatedCount}</li>
    </ul>
  `;
}

// ---------------------------------------------------------------------------
// Selected-subarea detail panel
// ---------------------------------------------------------------------------

function fmtDate(d) {
  return d || "Ongoing / not recorded as ended";
}

function renderDetail(props) {
  const box = document.getElementById("licence-detail");
  const source = meta?.sources?.licence_portfolio;
  const attribution = source
    ? `${escapeHtml(source.item_title || "")} &mdash; ${escapeHtml(source.publisher || "")}`
    : "North Sea Transition Authority";
  box.innerHTML = `
    <div class="group-detail-panel">
      <h3>${escapeHtml(props.licence_reference || "")} &mdash; ${escapeHtml(props.block_reference || "")} / ${escapeHtml(props.subarea_name || "")}</h3>
      <div>Licence number: ${escapeHtml(props.licence_number)}</div>
      <div>Status: ${escapeHtml(props.licence_status)}</div>
      <div>Equity share: ${props.equity_pct != null ? props.equity_pct + "%" : "n/a"}</div>
      <div>Operator (current group): ${escapeHtml(props.operator_group)}</div>
      <div>
        Equity holder (as recorded by NSTA, already reported at current-group grain by this
        source dataset - see methodology): ${escapeHtml(props.current_display_group)}
      </div>
      <div>${props.operated ? "Operated by this group" : "Non-operated"}</div>
      <div>Licence start date: ${escapeHtml(fmtDate(props.licence_start_date))}</div>
      <div>Licence end date: ${escapeHtml(fmtDate(props.licence_end_date))}</div>
      <div class="panel-caveat">Source: ${attribution}</div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Historical licence interests and operators (Deliverable 3)
// ---------------------------------------------------------------------------

// Date-containment convention (spec): start_date <= selected_date <
// end_date; an absent end_date is open-ended and always matches from
// its start onward. ISO 8601 (YYYY-MM-DD) strings compare correctly
// with plain string operators, so no date parsing is needed here.
function episodeContainsDate(entry, dateStr) {
  if (!entry.start_date || entry.start_date > dateStr) return false;
  if (entry.end_date && entry.end_date <= dateStr) return false;
  return true;
}

function selectedDate(state) {
  return state.ldate || historyMeta?.latest_start_date || null;
}

function filteredHistoryFeatures(state) {
  if (!historyGeojson) return [];
  const date = selectedDate(state);
  return historyGeojson.features.filter((f) => {
    const p = f.properties;
    if (date && !episodeContainsDate(p, date)) return false;
    if (state.lgroup && p.operator_group !== state.lgroup) return false;
    if (state.lstatus && p.licence_status !== state.lstatus) return false;
    if (state.llicence && p.licence_reference !== state.llicence) return false;
    return true;
  });
}

function buildHistoryMapFilter(state) {
  const ids = filteredHistoryFeatures(state).map((f) => f.properties.episode_id);
  return ["in", ["get", "episode_id"], ["literal", ids]];
}

function applyHistoryFilters(state) {
  const filter = buildHistoryMapFilter(state);
  for (const id of [HIST_FILL_LAYER_ID, HIST_OUTLINE_LAYER_ID]) {
    if (map.getLayer(id)) map.setFilter(id, filter);
  }
}

function distinctHistoryStatuses() {
  return historyMeta?.distinct_licence_statuses || [];
}

function renderHistoryFilterInputs(state) {
  const box = document.getElementById("licence-history-filters");
  const date = selectedDate(state);
  const operatorGroups = historyMeta?.distinct_operator_groups || [];
  const statuses = distinctHistoryStatuses();

  box.innerHTML = `
    <label>Date
      <input type="date" id="lhf-date" value="${escapeHtml(date || "")}"
        min="${escapeHtml(historyMeta?.earliest_start_date || "")}"
        max="${escapeHtml(historyMeta?.latest_start_date || "")}" />
    </label>
    <label>Historical operator group
      <input type="text" id="lhf-operator" list="licence-history-operator-list" value="${escapeHtml(state.lgroup || "")}" placeholder="All operator groups" autocomplete="off" />
      <datalist id="licence-history-operator-list">
        ${operatorGroups.map((g) => `<option value="${escapeHtml(g)}"></option>`).join("")}
      </datalist>
    </label>
    <label>Licence status
      <select id="lhf-status">
        <option value="" ${!state.lstatus ? "selected" : ""}>All</option>
        ${statuses.map((s) => `<option value="${escapeHtml(s)}" ${state.lstatus === s ? "selected" : ""}>${escapeHtml(s)}</option>`).join("")}
      </select>
    </label>
    <label>Selected licence
      <input type="text" id="lhf-licence" list="licence-history-ref-list" value="${escapeHtml(state.llicence || "")}" placeholder="All licences" autocomplete="off" />
      <datalist id="licence-history-ref-list">
        ${[...new Set(filteredHistoryFeatures(state).map((f) => f.properties.licence_reference).filter(Boolean))]
          .sort()
          .slice(0, 500)
          .map((r) => `<option value="${escapeHtml(r)}"></option>`)
          .join("")}
      </datalist>
    </label>
    <button type="button" id="lhf-fit">Fit results</button>
    <button type="button" id="lhf-clear">Clear filters</button>
  `;

  document.getElementById("lhf-date").addEventListener("change", (e) => {
    updateUrlState({ ldate: e.target.value || null });
    refreshFromUrl();
  });
  document.getElementById("lhf-operator").addEventListener("change", (e) => {
    updateUrlState({ lgroup: e.target.value.trim() || null });
    refreshFromUrl();
  });
  document.getElementById("lhf-status").addEventListener("change", (e) => {
    updateUrlState({ lstatus: e.target.value || null });
    refreshFromUrl();
  });
  document.getElementById("lhf-licence").addEventListener("change", (e) => {
    updateUrlState({ llicence: e.target.value.trim() || null });
    refreshFromUrl();
  });
  document.getElementById("lhf-fit").addEventListener("click", () => fitToFilteredHistory(state));
  document.getElementById("lhf-clear").addEventListener("click", () => {
    updateUrlState({ ldate: null, lgroup: null, lstatus: null, llicence: null });
    refreshFromUrl();
  });
}

function renderHistoryActiveFilterChips(state) {
  const box = document.getElementById("licence-history-active-filters");
  const chips = [`Date: ${selectedDate(state) || "n/a"}`];
  if (state.lgroup) chips.push(`Operator group: ${state.lgroup}`);
  if (state.lstatus) chips.push(`Status: ${state.lstatus}`);
  if (state.llicence) chips.push(`Licence: ${state.llicence}`);
  box.textContent = `Active filters: ${chips.join(", ")}`;
}

function fitToFilteredHistory(state) {
  const features = filteredHistoryFeatures(state);
  if (features.length === 0) return;
  let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;
  const walk = (coords) => {
    if (typeof coords[0] === "number") {
      const [lng, lat] = coords;
      if (lng < minLng) minLng = lng;
      if (lng > maxLng) maxLng = lng;
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
    } else {
      coords.forEach(walk);
    }
  };
  for (const f of features) walk(f.geometry.coordinates);
  if (minLng === Infinity) return;
  map.fitBounds([[minLng, minLat], [maxLng, maxLat]], { padding: 40, maxZoom: 12 });
}

function renderHistorySummary(state) {
  const box = document.getElementById("licence-history-summary");
  const features = filteredHistoryFeatures(state);
  if (features.length === 0) {
    box.innerHTML = `<div class="production-empty">No historical licence interests match the selected date and filters.</div>`;
    return;
  }
  const distinctLicences = new Set(features.map((f) => f.properties.licence_reference).filter(Boolean));
  const distinctBlocks = new Set(features.map((f) => f.properties.block_reference).filter(Boolean));
  box.innerHTML = `
    <ul>
      <li>Distinct licences active on ${escapeHtml(selectedDate(state) || "n/a")}: ${distinctLicences.size}</li>
      <li>Distinct blocks: ${distinctBlocks.size}</li>
      <li>Total recorded episodes shown: ${features.length}</li>
    </ul>
  `;
}

function renderHistoryDetail(props) {
  const box = document.getElementById("licence-history-detail");
  const source = historyMeta?.source;
  const attribution = source
    ? `${escapeHtml(source.item_title || "")} &mdash; ${escapeHtml(source.publisher || "")}`
    : "North Sea Transition Authority";
  box.innerHTML = `
    <div class="group-detail-panel">
      <h3>${escapeHtml(props.licence_reference || "")} &mdash; Block ${escapeHtml(props.block_reference || "")}</h3>
      <div>Licence number: ${escapeHtml(props.licence_number)}</div>
      <div>Status (as recorded on this episode): ${escapeHtml(props.licence_status)}</div>
      <div>Effective from: ${escapeHtml(props.start_date)}</div>
      <div>Effective to: ${escapeHtml(fmtDate(props.end_date))}</div>
      <div>Recorded licensee name(s): ${escapeHtml(props.licensee_names)}</div>
      <div>Recorded licensee group: ${escapeHtml(props.licensee_group)}</div>
      <div>Recorded operator name(s): ${escapeHtml(props.operator_names)}</div>
      <div>Recorded operator group: ${escapeHtml(props.operator_group)}</div>
      <div>Recorded administrative organisation: ${escapeHtml(props.admin_org)}</div>
      <div class="panel-caveat">${escapeHtml(NO_HISTORICAL_EQUITY_STATEMENT)}</div>
      <div class="panel-caveat">Source: ${attribution}</div>
    </div>
  `;
}
