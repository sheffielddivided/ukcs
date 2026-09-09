// Entry point (spec section 10.3). Loads meta.json, fields.geojson and
// history/index.json on startup; per-field history is lazy-loaded on
// selection (state.js). Nothing here ever calls an NSTA or ArcGIS host -
// the browser only ever reads ./data/*, pre-built by etl/build.py.
import { initMap, filterByOperator } from "./map.js";
import { renderHistoryCharts } from "./charts.js";
import { DataLoadError, fetchJson, getFieldHistory, getOperatorHistory } from "./state.js";
import { formatBuiltAt, formatPeriod, formatPeriodShort, slugify } from "./format.js";

const DATA_META_URL = "./data/meta.json";
const DATA_FIELDS_URL = "./data/fields.geojson";
const DATA_HISTORY_INDEX_URL = "./data/history/index.json";

function showError(message) {
  const banner = document.getElementById("status-banner");
  banner.textContent = message;
  banner.classList.add("error");
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

function renderFieldPanelShell(fieldProps) {
  const panel = document.getElementById("field-panel");
  const content = document.getElementById("field-panel-content");
  content.innerHTML = `
    <div class="panel-field-name">${escapeHtml(fieldProps.field)}</div>
    <div class="panel-meta-row">Operator: ${escapeHtml(fieldProps.operator ?? "–")}</div>
    <div class="panel-meta-row">Region: ${escapeHtml(fieldProps.region ?? "–")} (${escapeHtml(fieldProps.location ?? "–")})</div>
    <div class="panel-loading">Loading history&hellip;</div>
  `;
  panel.hidden = false;
}

function renderFieldPanelHistory(history) {
  const content = document.getElementById("field-panel-content");
  const loadingEl = content.querySelector(".panel-loading");
  if (loadingEl) loadingEl.remove();

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

async function openFieldPanel(fieldProps) {
  renderFieldPanelShell(fieldProps);
  try {
    const history = await getFieldHistory(fieldProps.slug);
    renderFieldPanelHistory(history);
  } catch (err) {
    const content = document.getElementById("field-panel-content");
    const loadingEl = content.querySelector(".panel-loading");
    if (loadingEl) loadingEl.remove();
    const errEl = document.createElement("div");
    errEl.className = "panel-error";
    errEl.textContent =
      "Failed to load field history.\n\n" +
      (err instanceof DataLoadError ? err.message : String(err));
    content.appendChild(errEl);
  }
}

function closeFieldPanel() {
  document.getElementById("field-panel").hidden = true;
}

const RETROSPECTIVE_CAVEAT =
  "Operator (as currently recorded by NSTA). This series attributes a field's " +
  "ENTIRE production history to whichever company operates it today - not " +
  "whoever operated it at the time. A barrel produced in 2008 is counted " +
  "under the current operator, even if a different company operated the " +
  "field then (spec section 6.1). This is a stepping-stone metric and an " +
  "internal consistency check, not the intended headline figure - a later " +
  "phase replaces it with dated equity-share attribution.";

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

async function openOperatorPanel(operatorName, operatorsSplit) {
  renderOperatorPanelShell(operatorName);
  try {
    const operatorHistory = await getOperatorHistory(slugify(operatorName), operatorsSplit);
    renderOperatorPanelHistory(operatorHistory);
  } catch (err) {
    const content = document.getElementById("field-panel-content");
    const loadingEl = content.querySelector(".panel-loading");
    if (loadingEl) loadingEl.remove();
    const errEl = document.createElement("div");
    errEl.className = "panel-error";
    errEl.textContent =
      "Failed to load operator history.\n\n" +
      (err instanceof DataLoadError ? err.message : String(err));
    content.appendChild(errEl);
  }
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
  // history/index.json (field -> operator/region/first/last period, spec
  // 9.3) is loaded at startup per spec 10.3, ready for the search/
  // autocomplete UI - not built in this step, so nothing reads
  // historyIndex yet beyond confirming it loaded successfully as part of
  // this fetch. Its size is still genuinely part of the measured
  // cold-cache load below.
  console.debug(`history index loaded: ${Object.keys(historyIndex).length} fields`);

  const map = initMap("map", fieldsGeojson, openFieldPanel);
  populateOperatorFilter(fieldsGeojson, (operator) => {
    filterByOperator(map, operator);
  });

  document.getElementById("field-panel-close").addEventListener("click", closeFieldPanel);
  document.getElementById("view-operator-history").addEventListener("click", () => {
    const selected = document.getElementById("operator-filter").value;
    if (selected) openOperatorPanel(selected, meta.operators_split);
  });
}

main();
