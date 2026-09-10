// Production overview view (Deliverable 1). Default top-level view
// (spec: "Production must be the default view after a normal page load
// with no URL state"). Renders UKCS total production in mboe/d with
// three split modes (Liquids/Natural gas, By company, By field), using
// only ETL-derived fields already published under docs/data/overview/*
// (etl/overview.py) - no gas-conversion arithmetic happens here.

import { getOverviewArtifact, DataLoadError } from "./state.js";
import { renderProductionChart, disposeProductionChart } from "./charts.js";
import { formatPeriodShort, slugify } from "./format.js";
import { parseUrlState, updateUrlState } from "./urlstate.js";

// Must match etl/overview.py's UNRESOLVED_BUCKET_NAME exactly - the one
// collapsed bucket is not a singleton (it has ~182 members), so its
// mapping status can't be inferred from doc.is_singleton like a real
// approved group's could.
const UNRESOLVED_BUCKET_NAME = "Unresolved legal entities";

const RETROSPECTIVE_CAVEAT =
  "Current-group analytical view: historical production has been regrouped using current company " +
  "relationships. It does not represent company ownership structures at the time.";

const COLORS = [
  "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#8855dd", "#d64a8a",
  "#3fa7d6", "#c9862a", "#5ec98f", "#9d6bd6", "#d65454", "#4a9ed6",
];

let root = null;
let meta = null;
let monthlyTotals = null;

function el(html) {
  const div = document.createElement("div");
  div.innerHTML = html.trim();
  return div.firstElementChild;
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------------------------------------------------------------------------
// Init / shell
// ---------------------------------------------------------------------------

export async function initProductionView(container) {
  root = container;
  root.innerHTML = `
    <div id="production-error" class="panel-error" hidden></div>
    <div id="production-stats" class="production-stats"></div>
    <div class="production-controls">
      <div id="production-split-tabs" class="production-tabs" role="tablist" aria-label="Production split mode"></div>
      <div id="production-grain-toggle" class="production-subcontrols" hidden></div>
      <div id="production-topn-controls" class="production-subcontrols" hidden></div>
    </div>
    <div id="production-filters" class="production-filters"></div>
    <div id="production-active-filters" class="production-active-filters" aria-live="polite"></div>
    <div id="production-caveat" class="panel-caveat" hidden>${escapeHtml(RETROSPECTIVE_CAVEAT)}</div>
    <div id="production-chart-wrap">
      <div id="production-chart" style="height:360px"></div>
      <div id="production-empty" class="production-empty" hidden>No data for selected filters</div>
    </div>
    <div id="production-summary" class="sr-summary" aria-live="polite"></div>
    <div id="production-group-detail"></div>
  `;

  try {
    [meta, monthlyTotals] = await Promise.all([
      getOverviewArtifact("meta"),
      getOverviewArtifact("monthly_totals"),
    ]);
  } catch (err) {
    showError(err);
    return;
  }

  renderStats();
  renderSplitTabs();
  await refreshFromUrl();
}

function showError(err) {
  const box = document.getElementById("production-error");
  if (!box) return;
  const category = err instanceof DataLoadError ? "Production data" : "Unexpected error";
  box.textContent = `${category} failed to load.\n\n${err.message}`;
  box.hidden = false;
}

function clearError() {
  const box = document.getElementById("production-error");
  if (box) box.hidden = true;
}

// ---------------------------------------------------------------------------
// Reconciled grouping statistics (spec review, 2026-09-10 fix)
// ---------------------------------------------------------------------------

function renderStats() {
  const box = document.getElementById("production-stats");
  if (!box || !meta) return;
  box.innerHTML = `
    <details>
      <summary>Company-grouping coverage (${meta.distinct_approved_groups} approved groups)</summary>
      <ul>
        <li>Total legal entities: ${meta.total_legal_entities}</li>
        <li>Approved current-group mappings: ${meta.approved_count}</li>
        <li>Reviewed manual mappings: ${meta.reviewed_manual_mapping_count}</li>
        <li>Unresolved legal entities: ${meta.unresolved_count}</li>
        <li>Excluded legal entities: ${meta.excluded_count}</li>
        <li>Distinct approved company groups: ${meta.distinct_approved_groups}</li>
        <li>Unresolved fallback count (one per unresolved entity, not real groups): ${meta.unresolved_fallback_count}</li>
        <li>Latest-period production covered by approved mappings: ${fmtPct(meta.production_weighted_current_coverage_pct)}</li>
        <li>Latest-period production retained under unresolved entities: ${fmtPct(meta.latest_period_production_retained_under_unresolved_pct)}</li>
      </ul>
    </details>
  `;
}

function fmtPct(v) {
  return v == null ? "n/a" : `${v}%`;
}

// ---------------------------------------------------------------------------
// Split-mode tabs
// ---------------------------------------------------------------------------

const SPLITS = [
  { id: "commodity", label: "Liquids / Natural gas" },
  { id: "company", label: "By company" },
  { id: "field", label: "By field" },
];

function renderSplitTabs() {
  const box = document.getElementById("production-split-tabs");
  const current = parseUrlState().psplit || "commodity";
  box.innerHTML = SPLITS.map(
    (s) => `<button type="button" role="tab" data-split="${s.id}" aria-selected="${s.id === current}" class="tab-btn${s.id === current ? " active" : ""}">${s.label}</button>`
  ).join("");
  for (const btn of box.querySelectorAll("button")) {
    btn.addEventListener("click", () => {
      updateUrlState({ psplit: btn.dataset.split === "commodity" ? null : btn.dataset.split, pgroup: null });
      refreshFromUrl();
    });
  }
}

// ---------------------------------------------------------------------------
// URL-driven refresh - the single entry point for (re)rendering after
// any control change or browser back/forward navigation.
// ---------------------------------------------------------------------------

export async function refreshFromUrl() {
  if (!root || !meta) return;
  clearError();
  const state = parseUrlState();
  const split = state.psplit || "commodity";
  highlightActiveTab(split);

  document.getElementById("production-grain-toggle").hidden = split !== "company";
  document.getElementById("production-topn-controls").hidden = split !== "field";
  document.getElementById("production-caveat").hidden = !(split === "company" && (state.pgrain || "group") === "group");
  document.getElementById("production-group-detail").innerHTML = "";

  renderFilters(split, state);
  renderActiveFilterChips(state);

  try {
    if (split === "commodity") await renderCommoditySplit(state);
    else if (split === "company") await renderCompanySplit(state);
    else if (split === "field") await renderFieldSplit(state);
  } catch (err) {
    showError(err);
  }
}

function highlightActiveTab(split) {
  for (const btn of document.querySelectorAll("#production-split-tabs button")) {
    const active = btn.dataset.split === split;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", String(active));
  }
}

// ---------------------------------------------------------------------------
// Filters (shared across split modes, where each applies)
// ---------------------------------------------------------------------------

function renderFilters(split, state) {
  const box = document.getElementById("production-filters");
  const grainNote = split === "company" ? grainToggleHtml(state) : "";
  if (grainNote) document.getElementById("production-grain-toggle").innerHTML = grainNote;
  if (split === "field") {
    document.getElementById("production-topn-controls").innerHTML = topNHtml(state);
    wireTopN();
  }

  box.innerHTML = `
    <label>From <input type="text" id="pf-from" value="${escapeHtml(state.pfrom || "")}" placeholder="YYYYMM" size="7" /></label>
    <label>To <input type="text" id="pf-to" value="${escapeHtml(state.pto || "")}" placeholder="YYYYMM" size="7" /></label>
    ${split === "field" ? `<label>Field status
      <select id="pf-status">
        <option value="" ${!state.pstatus ? "selected" : ""}>All</option>
        <option value="current" ${state.pstatus === "current" ? "selected" : ""}>Current</option>
        <option value="historical" ${state.pstatus === "historical" ? "selected" : ""}>Historical</option>
      </select>
    </label>` : ""}
    <button type="button" id="pf-clear">Clear filters</button>
  `;
  document.getElementById("pf-from").addEventListener("change", (e) => {
    updateUrlState({ pfrom: e.target.value.trim() || null });
    refreshFromUrl();
  });
  document.getElementById("pf-to").addEventListener("change", (e) => {
    updateUrlState({ pto: e.target.value.trim() || null });
    refreshFromUrl();
  });
  const statusEl = document.getElementById("pf-status");
  if (statusEl) {
    statusEl.addEventListener("change", (e) => {
      updateUrlState({ pstatus: e.target.value || null });
      refreshFromUrl();
    });
  }
  document.getElementById("pf-clear").addEventListener("click", () => {
    updateUrlState({
      pfrom: null, pto: null, pstatus: null, pgroup: null, pfields: null, ptopn: null,
    });
    refreshFromUrl();
  });
}

function grainToggleHtml(state) {
  const grain = state.pgrain || "group";
  return `
    <label><input type="radio" name="pgrain" value="group" ${grain === "group" ? "checked" : ""} /> Current company group</label>
    <label><input type="radio" name="pgrain" value="entity" ${grain === "entity" ? "checked" : ""} /> Legal entity as recorded by NSTA</label>
  `;
}

function wireGrainToggle() {
  for (const radio of document.querySelectorAll('input[name="pgrain"]')) {
    radio.addEventListener("change", (e) => {
      if (e.target.checked) {
        updateUrlState({ pgrain: e.target.value === "group" ? null : e.target.value, pgroup: null });
        refreshFromUrl();
      }
    });
  }
}

function topNHtml(state) {
  const n = state.ptopn || "10";
  return `
    <label>Top
      <select id="pf-topn">
        ${["5", "10", "15", "20"].map((v) => `<option value="${v}" ${v === n ? "selected" : ""}>${v}</option>`).join("")}
      </select>
    </label>
  `;
}

function wireTopN() {
  const sel = document.getElementById("pf-topn");
  if (sel) {
    sel.addEventListener("change", (e) => {
      updateUrlState({ ptopn: e.target.value === "10" ? null : e.target.value, pfields: null });
      refreshFromUrl();
    });
  }
}

function renderActiveFilterChips(state) {
  const box = document.getElementById("production-active-filters");
  const chips = [];
  if (state.pfrom) chips.push(`From ${state.pfrom}`);
  if (state.pto) chips.push(`To ${state.pto}`);
  if (state.pstatus) chips.push(`Status: ${state.pstatus}`);
  if (state.pgroup) chips.push(`Selected: ${state.pgroup}`);
  if (state.pfields) chips.push(`Fields: ${state.pfields.split(",").length} selected`);
  box.textContent = chips.length ? `Active filters: ${chips.join(", ")}` : "";
}

function filterPeriods(series, state) {
  return series.filter((p) => {
    if (state.pfrom && p.period < state.pfrom) return false;
    if (state.pto && p.period > state.pto) return false;
    return true;
  });
}

// ---------------------------------------------------------------------------
// Commodity split (default)
// ---------------------------------------------------------------------------

async function renderCommoditySplit(state) {
  const points = filterPeriods(monthlyTotals, state);
  toggleEmpty(points.length === 0);
  if (points.length === 0) return;

  const periods = points.map((p) => formatPeriodShort(p.period));
  await renderProductionChart(
    document.getElementById("production-chart"),
    periods,
    [
      { name: "Liquids", color: COLORS[0], data: points.map((p) => p.liquids_mboed) },
      { name: "Natural gas", color: COLORS[1], data: points.map((p) => p.natural_gas_mboed) },
    ],
    { name: "Total", color: "#1a1a1a", data: points.map((p) => p.total_mboed) }
  );

  const latest = points[points.length - 1];
  document.getElementById("production-summary").textContent =
    `Latest period ${latest.period}: Liquids ${latest.liquids_mboed} mboe/d, ` +
    `Natural gas ${latest.natural_gas_mboed} mboe/d, Total ${latest.total_mboed} mboe/d. ` +
    `${points.length} months shown.`;
  wireChartTooltipA11y(points, "liquids_mboed", "natural_gas_mboed", "total_mboed");
}

function wireChartTooltipA11y() {
  // The accessible summary above already exposes period/values/coverage
  // in text; the chart itself carries ECharts' own tooltip. No further
  // action needed here - kept as a named hook for future keyboard-nav
  // enhancement without changing renderCommoditySplit's call site.
}

function toggleEmpty(isEmpty) {
  document.getElementById("production-chart").style.display = isEmpty ? "none" : "";
  document.getElementById("production-empty").hidden = !isEmpty;
}

// ---------------------------------------------------------------------------
// Company split
// ---------------------------------------------------------------------------

async function renderCompanySplit(state) {
  wireGrainToggle();
  const grain = state.pgrain || "group";
  const artifactName = grain === "group" ? "company_groups" : "legal_entities";
  const data = await getOverviewArtifact(artifactName);

  let names = Object.keys(data);
  if (state.pgroup) {
    names = names.includes(state.pgroup) ? [state.pgroup] : [];
  }

  if (names.length === 0) {
    toggleEmpty(true);
    document.getElementById("production-summary").textContent = "No data for selected filters.";
    return;
  }

  // Union of periods across the (possibly filtered) selection, then
  // apply the date-range filter - never fabricate a period no selected
  // series actually has.
  const periodSet = new Set();
  for (const name of names) for (const p of data[name].series) periodSet.add(p.period);
  let periods = [...periodSet].sort();
  if (state.pfrom) periods = periods.filter((p) => p >= state.pfrom);
  if (state.pto) periods = periods.filter((p) => p <= state.pto);

  toggleEmpty(periods.length === 0);
  if (periods.length === 0) return;

  const stacked = names.map((name, i) => {
    const byPeriod = new Map(data[name].series.map((p) => [p.period, p]));
    return {
      name,
      color: COLORS[i % COLORS.length],
      data: periods.map((period) => {
        const point = byPeriod.get(period);
        return point ? point.total_mboed.value : null;
      }),
    };
  });

  await renderProductionChart(
    document.getElementById("production-chart"),
    periods.map(formatPeriodShort),
    stacked,
    null
  );

  document.getElementById("production-summary").textContent =
    `${names.length} ${grain === "group" ? "company group(s)" : "legal entit(ies)"} shown over ${periods.length} months.`;

  if (state.pgroup && grain === "group") {
    renderGroupDetail(state.pgroup, data[state.pgroup]);
  }

  renderCompanyFilterSelect(names.length ? Object.keys(data) : [], state, grain);
}

function renderCompanyFilterSelect(allNames, state, grain) {
  const box = document.getElementById("production-filters");
  const existing = document.getElementById("pf-company");
  if (existing) existing.closest("label")?.remove();
  const label = document.createElement("label");
  label.innerHTML = `${grain === "group" ? "Company group" : "Legal entity"}
    <select id="pf-company">
      <option value="">All</option>
      ${allNames
        .sort()
        .map((n) => `<option value="${escapeHtml(n)}" ${state.pgroup === n ? "selected" : ""}>${escapeHtml(n)}</option>`)
        .join("")}
    </select>`;
  box.insertBefore(label, box.lastElementChild);
  label.querySelector("select").addEventListener("change", (e) => {
    updateUrlState({ pgroup: e.target.value || null });
    refreshFromUrl();
  });
}

function renderGroupDetail(name, doc) {
  const box = document.getElementById("production-group-detail");
  if (!doc) {
    box.innerHTML = "";
    return;
  }
  const latest = doc.series[doc.series.length - 1];
  const members = doc.member_entities || [];
  box.innerHTML = `
    <div class="group-detail-panel">
      <h3>${escapeHtml(name)}</h3>
      <div>Latest Liquids: ${latest?.liquids_mboed?.value ?? "n/a"} mboe/d</div>
      <div>Latest Natural gas: ${latest?.natural_gas_mboed?.value ?? "n/a"} mboe/d</div>
      <div>Latest Total: ${latest?.total_mboed?.value ?? "n/a"} mboe/d</div>
      <div>Mapping status: ${name === UNRESOLVED_BUCKET_NAME ? "unresolved (collapsed fallback bucket)" : "approved (NSTA equity group)"}</div>
      <details>
        <summary>Source legal entities (${members.length})</summary>
        <ul>${members.map((m) => `<li>${escapeHtml(m)}</li>`).join("")}</ul>
      </details>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Field split (Top N + Other)
// ---------------------------------------------------------------------------

async function renderFieldSplit(state) {
  const fields = await getOverviewArtifact("fields");
  const topN = parseInt(state.ptopn || "10", 10);
  const explicitSlugs = state.pfields ? state.pfields.split(",").filter(Boolean) : null;

  let selectedSlugs;
  if (explicitSlugs && explicitSlugs.length) {
    selectedSlugs = explicitSlugs.filter((s) => fields[s]);
  } else {
    // Rank by latest available total_mboed (spec: "Top N fields by
    // production"; latest-period value is the defensible, documented
    // ranking choice - not cumulative history, which would favour old,
    // now-depleted fields over currently productive ones).
    const ranked = Object.values(fields)
      .map((f) => ({ slug: f.slug, latest: [...f.series].reverse().find((p) => p.total_mboed != null) }))
      .filter((f) => f.latest)
      .sort((a, b) => (b.latest.total_mboed || 0) - (a.latest.total_mboed || 0));
    selectedSlugs = ranked.slice(0, topN).map((f) => f.slug);
  }

  if (selectedSlugs.length === 0) {
    toggleEmpty(true);
    document.getElementById("production-summary").textContent = "No data for selected filters.";
    return;
  }

  const periodSet = new Set();
  for (const slug of selectedSlugs) for (const p of fields[slug].series) periodSet.add(p.period);
  // Also include periods from monthlyTotals so "Other" is defined even
  // for periods where none of the selected fields had a point.
  for (const p of monthlyTotals) periodSet.add(p.period);
  let periods = [...periodSet].sort();
  if (state.pfrom) periods = periods.filter((p) => p >= state.pfrom);
  if (state.pto) periods = periods.filter((p) => p <= state.pto);

  toggleEmpty(periods.length === 0);
  if (periods.length === 0) return;

  const monthlyByPeriod = new Map(monthlyTotals.map((p) => [p.period, p.total_mboed]));
  const fieldSeriesByPeriod = selectedSlugs.map((slug) => new Map(fields[slug].series.map((p) => [p.period, p.total_mboed])));

  const stacked = selectedSlugs.map((slug, i) => ({
    name: fields[slug].name,
    color: COLORS[i % COLORS.length],
    data: periods.map((period) => {
      const v = fieldSeriesByPeriod[i].get(period);
      return v == null ? null : v;
    }),
  }));

  // Other fields = UKCS Total - sum(displayed fields), computed here
  // from the already-published (rounded) values - see
  // etl/overview.py's validate_fields_overview_reconciliation for the
  // server-side guarantee that sum(ALL fields) == monthly_totals, which
  // is what makes this client-side subtraction meaningful rather than
  // an independent, possibly-inconsistent number.
  const otherData = periods.map((period, idx) => {
    const total = monthlyByPeriod.get(period);
    if (total == null) return null;
    let sumDisplayed = 0;
    for (const seriesMap of fieldSeriesByPeriod) sumDisplayed += seriesMap.get(period) || 0;
    return Math.max(0, +(total - sumDisplayed).toFixed(3));
  });
  stacked.push({ name: "Other fields", color: "#b8b8b8", data: otherData });

  await renderProductionChart(
    document.getElementById("production-chart"),
    periods.map(formatPeriodShort),
    stacked,
    { name: "Total", color: "#1a1a1a", data: periods.map((p) => monthlyByPeriod.get(p) ?? null) }
  );

  document.getElementById("production-summary").textContent =
    `Top ${selectedSlugs.length} field(s) shown plus Other fields, over ${periods.length} months.`;
}
