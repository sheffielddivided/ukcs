// Entry point (spec section 10.3, extended for the equity frontend
// checkpoint). Loads meta.json, fields.geojson and history/index.json on
// startup; per-field history is lazy-loaded on selection (state.js).
// Equity meta.json and index.json are also loaded at startup (small
// artifacts, spec: equity frontend checkpoint section 1), but company and
// field equity detail remain lazy (equity.js). Nothing here ever calls an
// NSTA or ArcGIS host - the browser only ever reads ./data/*, pre-built
// by etl/build.py. An equity data-loading failure is isolated: the
// production map and field/operator views must remain usable even if
// docs/data/equity/* fails to load.
import { initMap, filterByOperator, setLayerVisibility, setSelectedFieldPolygon, LAYERS } from "./map.js";
import { renderHistoryCharts } from "./charts.js";
import { DataLoadError, fetchJson, getFieldHistory, getOperatorHistory } from "./state.js";
import { formatBuiltAt, formatPeriod, formatPeriodShort, slugify } from "./format.js";
import { getEquityMeta, getEquityIndex, streamIndexFromUrlSlug } from "./equity.js";
import { openEquityPanel, attachFieldOwnershipTab } from "./equity-ui.js";
import { buildSearchIndex, attachSearchUI } from "./search.js";
import { parseUrlState, setUrlState } from "./urlstate.js";

const DATA_META_URL = "./data/meta.json";
const DATA_FIELDS_URL = "./data/fields.geojson";
const DATA_HISTORY_INDEX_URL = "./data/history/index.json";
const DATA_FIELD_POLYGONS_URL = "./data/field_polygons.geojson";

// Shared UI state, mutated by the mode toggle / selectors / URL restore.
const ui = {
  metricMode: "equity", // "equity" | "operator"
  fieldsBySlug: new Map(),
  fieldsByName: new Map(),
  map: null,
};

function showError(message) {
  const banner = document.getElementById("status-banner");
  banner.textContent = message;
  banner.classList.add("error");
  banner.hidden = false;
}

function showEquityWarning(message) {
  const banner = document.getElementById("equity-status-banner");
  banner.textContent = message;
  banner.classList.add("warning");
  banner.hidden = false;
}

function renderFooter(meta) {
  const footer = document.getElementById("footer-text");
  footer.textContent =
    `Source: North Sea Transition Authority. ` +
    `Data as at ${formatPeriod(meta.latest_period)}. ` +
    `Site built ${formatBuiltAt(meta.built_at)}.`;
}

function populateOperatorFilter(fieldsGeojson, onChange) {
  const select = document.getElementById("operator-filter");
  const viewHistoryButton = document.getElementById("view-operator-history");
  const operators = Array.from(
    new Set(
      fieldsGeojson.features
        .map((f) => f.properties.operator)
        .filter((op) => op != null)
    )
  ).sort();

  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = `All operators (${operators.length})`;
  select.appendChild(allOption);

  for (const operator of operators) {
    const option = document.createElement("option");
    option.value = operator;
    option.textContent = operator;
    select.appendChild(option);
  }

  select.addEventListener("change", () => {
    onChange(select.value || null);
    viewHistoryButton.disabled = !select.value;
  });

  return operators;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function buildUnitTableRows(units, classification) {
  return units
    .map(
      (u) => `
      <tr class="${classification === "storage" ? "storage-row" : ""}">
        <td>${escapeHtml(u.name)}</td>
        <td>${escapeHtml(u.type)}</td>
        <td>${escapeHtml(formatPeriodShort(u.first_period))}&ndash;${escapeHtml(formatPeriodShort(u.last_period))}</td>
        <td><span class="unit-classification-badge ${classification}">${classification}</span></td>
      </tr>`
    )
    .join("");
}

// The field panel now always has a Production / Ownership tab pair (spec
// section 7 of the equity frontend checkpoint). Ownership content is
// only fetched when its tab is actually opened (equity-ui.js's
// attachFieldOwnershipTab), never eagerly.
function renderFieldPanelShell(fieldProps) {
  const panel = document.getElementById("field-panel");
  const content = document.getElementById("field-panel-content");
  content.innerHTML = `
    <div class="panel-field-name">${escapeHtml(fieldProps.field)}</div>
    <div class="panel-meta-row">Operator: ${escapeHtml(fieldProps.operator ?? "–")}</div>
    <div class="panel-meta-row">Region: ${escapeHtml(fieldProps.region ?? "–")} (${escapeHtml(fieldProps.location ?? "–")})</div>
    <div class="field-panel-tabs" role="tablist" aria-label="Field detail">
      <button type="button" id="field-panel-tab-production" class="panel-tab" role="tab" aria-selected="true">Production</button>
      <button type="button" id="field-panel-tab-ownership" class="panel-tab" role="tab" aria-selected="false" hidden>Ownership</button>
    </div>
    <div id="field-panel-production-content">
      <div class="panel-loading">Loading history&hellip;</div>
    </div>
    <div id="field-panel-ownership-content" hidden></div>
  `;
  panel.hidden = false;
  attachFieldOwnershipTab(fieldProps.slug);
}

function renderFieldPanelHistory(history) {
  const content = document.getElementById("field-panel-production-content");
  content.innerHTML = "";

  const hasMultipleProductionNames = history.units.length > 1;
  const hasStorage = history.storage_units.length > 0;

  const section = document.createElement("div");
  section.innerHTML = `
    <div class="panel-section-title">Reporting units</div>
    <table class="unit-table">
      <thead><tr><th>Name</th><th>Type</th><th>Period</th><th>Class</th></tr></thead>
      <tbody>
        ${buildUnitTableRows(history.units, "production")}
        ${buildUnitTableRows(history.storage_units, "storage")}
      </tbody>
    </table>
    ${
      hasStorage
        ? `<div class="panel-storage-note">
             ${history.storage_units.length} storage reporting unit(s)
             (${history.storage_units.map((u) => escapeHtml(u.name)).join(", ")})
             excluded from the production charts and totals below at every period,
             not merged in (spec section 7.3).
           </div>`
        : ""
    }
    ${
      hasMultipleProductionNames
        ? `<div class="panel-storage-note" style="background:transparent;border-color:var(--border);color:var(--text-secondary);">
             This field's production series spans a reporting-unit rename
             (${history.units.map((u) => escapeHtml(u.name)).join(" → ")}).
             The series above is continuous across the rename; see the table
             for exactly which unit name covered which period.
           </div>`
        : ""
    }
    <div class="panel-section-title">Monthly production history</div>
    <div id="chart-liquids" class="chart-box"></div>
    <div id="chart-gas" class="chart-box"></div>
  `;
  content.appendChild(section);

  const liquidsEl = document.getElementById("chart-liquids");
  const gasEl = document.getElementById("chart-gas");
  renderHistoryCharts(liquidsEl, gasEl, history.series).catch((err) => {
    const errEl = document.createElement("div");
    errEl.className = "panel-error";
    errEl.textContent = `Failed to load charts.\n\n${err.message}`;
    content.appendChild(errEl);
  });
}

// Resolves a click that originated on a polygon (map.js passes only
// {slug, fromPolygon: true} - it has no production properties of its
// own) to the same fieldProps shape a circle click already provides,
// preferring the current-period fields.geojson feature (full production
// detail) and falling back to the historyIndex-derived shell used
// elsewhere for a field with no latest-period marker (spec: "Clicking
// either geometry or bubble opens the same field panel.").
function resolveFieldClick(clicked, fieldsBySlugFeature) {
  if (!clicked.fromPolygon) return clicked;
  const feature = fieldsBySlugFeature.get(clicked.slug);
  if (feature) return feature.properties;
  const entry = ui.fieldsBySlug.get(clicked.slug);
  return {
    field: entry?.field ?? clicked.slug,
    slug: clicked.slug,
    operator: entry?.operator ?? null,
    region: entry?.region ?? null,
    location: null,
  };
}

async function openFieldPanel(fieldProps, updateUrl = true) {
  renderFieldPanelShell(fieldProps);
  if (updateUrl) setUrlState({ view: "field", slug: fieldProps.slug });
  if (ui.map) setSelectedFieldPolygon(ui.map, fieldProps.slug);
  try {
    const history = await getFieldHistory(fieldProps.slug);
    renderFieldPanelHistory(history);
  } catch (err) {
    const content = document.getElementById("field-panel-production-content");
    content.innerHTML = "";
    const errEl = document.createElement("div");
    errEl.className = "panel-error";
    const category = err instanceof DataLoadError ? "Field production data" : "Unexpected error";
    errEl.textContent = `${category} failed to load.\n\n${err.message}`;
    content.appendChild(errEl);
  }
}

function closeFieldPanel() {
  document.getElementById("field-panel").hidden = true;
  setUrlState({});
}

const RETROSPECTIVE_CAVEAT =
  "Operator (as currently recorded by NSTA). This series attributes a field's " +
  "ENTIRE production history to whichever company operates it today - not " +
  "whoever operated it at the time. A barrel produced in 2008 is counted " +
  "under the current operator, even if a different company operated the " +
  "field then (spec section 6.1). This is a stepping-stone metric and an " +
  "internal consistency check, not the intended headline figure - " +
  "equity-attributable production is the default company metric.";

function renderOperatorPanelShell(operatorName) {
  const panel = document.getElementById("field-panel");
  const content = document.getElementById("field-panel-content");
  content.innerHTML = `
    <div class="panel-field-name">${escapeHtml(operatorName)}</div>
    <div class="panel-meta-row">Operator (as currently recorded by NSTA)</div>
    <div class="panel-caveat">${escapeHtml(RETROSPECTIVE_CAVEAT)}</div>
    <div class="panel-loading">Loading operator history&hellip;</div>
  `;
  panel.hidden = false;
}

function renderOperatorPanelHistory(operatorHistory) {
  const content = document.getElementById("field-panel-content");
  const loadingEl = content.querySelector(".panel-loading");
  if (loadingEl) loadingEl.remove();

  const section = document.createElement("div");
  section.innerHTML = `
    <div class="panel-section-title">Monthly production history</div>
    <div id="chart-liquids" class="chart-box"></div>
    <div id="chart-gas" class="chart-box"></div>
  `;
  content.appendChild(section);

  const liquidsEl = document.getElementById("chart-liquids");
  const gasEl = document.getElementById("chart-gas");
  renderHistoryCharts(liquidsEl, gasEl, operatorHistory.series).catch((err) => {
    const errEl = document.createElement("div");
    errEl.className = "panel-error";
    errEl.textContent = `Failed to load charts.\n\n${err.message}`;
    content.appendChild(errEl);
  });
}

async function openOperatorPanel(operatorName, operatorsSplit, updateUrl = true) {
  renderOperatorPanelShell(operatorName);
  if (updateUrl) setUrlState({ view: "operator", slug: slugify(operatorName) });
  try {
    const operatorHistory = await getOperatorHistory(slugify(operatorName), operatorsSplit);
    renderOperatorPanelHistory(operatorHistory);
  } catch (err) {
    const content = document.getElementById("field-panel-content");
    const loadingEl = content.querySelector(".panel-loading");
    if (loadingEl) loadingEl.remove();
    const errEl = document.createElement("div");
    errEl.className = "panel-error";
    const category = err instanceof DataLoadError ? "Operator production data" : "Unexpected error";
    errEl.textContent = `${category} failed to load.\n\n${err.message}`;
    content.appendChild(errEl);
  }
}

async function openEquityPanelBySlug(slug, entityName, updateUrl = true, initialStreamIndex = 0) {
  if (updateUrl) setUrlState({ view: "equity", slug, metric: "equity" });
  await openEquityPanel(slug, entityName, { initialStreamIndex });
}

function setMetricMode(mode) {
  ui.metricMode = mode;
  document.getElementById("mode-equity").setAttribute("aria-pressed", String(mode === "equity"));
  document.getElementById("mode-operator").setAttribute("aria-pressed", String(mode === "operator"));
  document.getElementById("equity-mode-controls").hidden = mode !== "equity";
  document.getElementById("view-operator-history").hidden = mode !== "operator";
  // Switching mode never silently carries a selection across into the
  // other mode's control - each mode's own selector starts empty again
  // unless the URL explicitly names an entity for that mode (spec
  // section 3: "do not infer relationships between operator names and
  // equity legal entities").
}

async function main() {
  let meta;
  let fieldsGeojson;
  let historyIndex;
  try {
    [meta, fieldsGeojson, historyIndex] = await Promise.all([
      fetchJson(DATA_META_URL),
      fetchJson(DATA_FIELDS_URL),
      fetchJson(DATA_HISTORY_INDEX_URL),
    ]);
  } catch (err) {
    showError(
      "Failed to load data.\n\n" +
        (err instanceof DataLoadError ? err.message : String(err))
    );
    return;
  }

  renderFooter(meta);
  console.debug(`history index loaded: ${Object.keys(historyIndex).length} fields`);

  for (const [slug, entry] of Object.entries(historyIndex)) {
    ui.fieldsBySlug.set(slug, entry);
    ui.fieldsByName.set(entry.field, slug);
  }
  const fieldsBySlugFeature = new Map(
    fieldsGeojson.features.map((f) => [f.properties.slug, f])
  );

  // Field polygons (spec Workstream 3) are fetched separately from the
  // required startup data above and MUST NOT be allowed to break the
  // map or any other view if this one optional fetch fails (spec:
  // "A failed optional panel/data fetch must not take down: Production
  // overview, Fields map, existing field details, existing operator/
  // equity views.") - the map still works with point markers alone.
  let fieldPolygonsGeojson = null;
  try {
    fieldPolygonsGeojson = await fetchJson(DATA_FIELD_POLYGONS_URL);
  } catch (err) {
    console.warn("Field polygons failed to load - map will show markers only.", err);
  }

  const map = initMap(
    "map",
    fieldsGeojson,
    (clicked) => openFieldPanel(resolveFieldClick(clicked, fieldsBySlugFeature), true),
    fieldPolygonsGeojson
  );
  ui.map = map;
  const operators = populateOperatorFilter(fieldsGeojson, (operator) => {
    filterByOperator(map, operator);
  });

  if (fieldPolygonsGeojson) {
    const bubblesToggle = document.getElementById("layer-toggle-bubbles");
    const outlinesToggle = document.getElementById("layer-toggle-outlines");
    if (bubblesToggle) {
      bubblesToggle.addEventListener("change", () => {
        setLayerVisibility(map, LAYERS.circles, bubblesToggle.checked);
      });
    }
    if (outlinesToggle) {
      outlinesToggle.addEventListener("change", () => {
        setLayerVisibility(map, LAYERS.polygonFill, outlinesToggle.checked);
        setLayerVisibility(map, LAYERS.polygonOutline, outlinesToggle.checked);
      });
    }
  } else {
    document.getElementById("layer-toggles")?.setAttribute("hidden", "");
  }

  document.getElementById("field-panel-close").addEventListener("click", closeFieldPanel);
  document.getElementById("view-operator-history").addEventListener("click", () => {
    const selected = document.getElementById("operator-filter").value;
    if (selected) openOperatorPanel(selected, meta.operators_split, true);
  });

  document.getElementById("mode-equity").addEventListener("click", () => setMetricMode("equity"));
  document.getElementById("mode-operator").addEventListener("click", () => {
    setMetricMode("operator");
    // A stream selection is only ever meaningful in equity mode - leaving
    // an equity URL (with its stream) in place while the UI now shows
    // operator controls would be a stale, inapplicable link. No operator
    // is selected yet at this point (the user just clicked the toggle),
    // so there is nothing else to preserve; selecting an operator next
    // writes its own fresh URL state via openOperatorPanel.
    if (parseUrlState().view === "equity") setUrlState({});
  });
  setMetricMode("equity");

  // --- Equity data (isolated failure: never blocks the production map) ---
  let equityMeta = null;
  let equityIndex = null;
  let equityByName = new Map();
  try {
    [equityMeta, equityIndex] = await Promise.all([getEquityMeta(), getEquityIndex()]);
    for (const [slug, entry] of Object.entries(equityIndex)) {
      equityByName.set(entry.name, slug);
    }
    const datalist = document.getElementById("equity-company-list");
    const sortedNames = Array.from(equityByName.keys()).sort((a, b) => a.localeCompare(b));
    for (const name of sortedNames) {
      const option = document.createElement("option");
      option.value = name;
      datalist.appendChild(option);
    }
    document.getElementById("equity-company-input").addEventListener("change", (e) => {
      const slug = equityByName.get(e.target.value);
      if (slug) openEquityPanelBySlug(slug, e.target.value, true);
    });
  } catch (err) {
    showEquityWarning(
      "Equity-attributable production data failed to load. The map and field/operator " +
        "production views remain available.\n\n" +
        (err instanceof DataLoadError ? err.message : String(err))
    );
  }

  // --- Global search (fields + legal entities + operators) ---
  const searchIndex = buildSearchIndex({
    fields: Array.from(ui.fieldsBySlug.entries()).map(([slug, entry]) => ({ slug, name: entry.field })),
    legalEntities: equityIndex
      ? Object.entries(equityIndex).map(([slug, entry]) => ({ slug, name: entry.name }))
      : [],
    operators,
  });
  attachSearchUI(
    document.getElementById("global-search"),
    document.getElementById("global-search-results"),
    searchIndex,
    (entry) => {
      document.getElementById("global-search").value = "";
      if (entry.type === "field") {
        const fieldFeature = fieldsGeojson.features.find((f) => f.properties.slug === entry.slug);
        if (fieldFeature) {
          openFieldPanel(fieldFeature.properties, true);
        } else {
          // Field with production history but not in the latest period's
          // feature set (e.g. no longer producing) - open with minimal
          // props, matching the existing history-only field code path.
          openFieldPanel({ field: entry.label, slug: entry.slug, operator: null, region: null, location: null }, true);
        }
      } else if (entry.type === "legal-entity") {
        setMetricMode("equity");
        document.getElementById("equity-company-input").value = entry.label;
        openEquityPanelBySlug(entry.slug, entry.label, true);
      } else if (entry.type === "operator") {
        setMetricMode("operator");
        document.getElementById("operator-filter").value = entry.label;
        filterByOperator(map, entry.label);
        openOperatorPanel(entry.label, meta.operators_split, true);
      }
    }
  );

  // --- URL state restore ---
  // Named so it can run both at startup and on popstate (browser
  // back/forward): re-parses location.hash from scratch each time, so
  // the panel/mode/stream shown always matches whatever the current URL
  // actually says - never a stale in-memory leftover from a prior state.
  function restoreFromUrl() {
    const initial = parseUrlState();
    if (initial.view === "field" && initial.slug) {
      const fieldFeature = fieldsGeojson.features.find((f) => f.properties.slug === initial.slug);
      const entry = ui.fieldsBySlug.get(initial.slug);
      if (fieldFeature) {
        openFieldPanel(fieldFeature.properties, false);
      } else if (entry) {
        openFieldPanel({ field: entry.field, slug: initial.slug, operator: null, region: null, location: null }, false);
      } else {
        showError(`No field found for '${initial.slug}' in the saved link. It may be stale.`);
      }
    } else if (initial.view === "equity" && initial.slug) {
      if (equityIndex && equityIndex[initial.slug]) {
        setMetricMode("equity");
        document.getElementById("equity-company-input").value = equityIndex[initial.slug].name;
        let initialStreamIndex = 0;
        if (initial.stream) {
          const idx = streamIndexFromUrlSlug(initial.stream);
          if (idx >= 0) {
            initialStreamIndex = idx;
          } else {
            showEquityWarning(
              `The production stream '${initial.stream}' in this link is not recognised. Showing Oil instead.`
            );
          }
        }
        openEquityPanelBySlug(initial.slug, equityIndex[initial.slug].name, false, initialStreamIndex);
      } else if (equityIndex) {
        showError(`No equity legal entity found for '${initial.slug}' in the saved link. It may be stale.`);
      }
    } else if (initial.view === "operator" && initial.slug) {
      const operatorName = operators.find((op) => slugify(op) === initial.slug);
      if (operatorName) {
        setMetricMode("operator");
        document.getElementById("operator-filter").value = operatorName;
        filterByOperator(map, operatorName);
        openOperatorPanel(operatorName, meta.operators_split, false);
      } else {
        showError(`No operator found for '${initial.slug}' in the saved link. It may be stale.`);
      }
    }
  }

  restoreFromUrl();
  window.addEventListener("popstate", restoreFromUrl);
}

main();
