// Equity company panel, field ownership section, and the equity/operator
// metric-mode toggle (spec: equity frontend checkpoint). Legal-entity
// names are used and displayed exactly as recorded by NSTA throughout -
// no parent-company rollup, no merging of similarly-named entities
// (spec section 15.11/15.12 - not re-litigated here, only displayed).

import {
  DataLoadError,
  LEGAL_ENTITY_LABEL,
  MURLACH_FIELD_SLUG,
  MURLACH_NOTE,
  PRODUCTION_STREAMS,
  getCompanyEquity,
  getEquityMeta,
  getFieldEquity,
} from "./equity.js";
import { renderEquityStreamChart } from "./charts.js";
import { formatPeriodShort } from "./format.js";
import { setUrlState } from "./urlstate.js";

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

const STATUS_LABELS = {
  complete: "Complete",
  warning: "Warning",
  unavailable: "Not available",
};

// Icon + text, never colour alone (spec section 11: accessibility).
const STATUS_ICONS = { complete: "✓", warning: "⚠", unavailable: "—" };

function statusBadgeHtml(streamEntry) {
  const status = streamEntry.status;
  const label = STATUS_LABELS[status] || status;
  const icon = STATUS_ICONS[status] || "";
  const coverage = streamEntry.coverage_pct == null ? "n/a" : `${streamEntry.coverage_pct}%`;
  return `<span class="coverage-badge coverage-${status}" title="Coverage: ${coverage}">
    <span aria-hidden="true">${icon}</span> ${escapeHtml(label)} (${coverage})
  </span>`;
}

function latestValueHtml(streamMeta, streamEntry) {
  if (streamEntry.status === "unavailable") {
    return `<span class="equity-value-unavailable">Not available</span>`;
  }
  return `<span class="equity-value">${streamEntry.value} ${streamMeta.unit}</span>`;
}

export function equityMethodologyLinkHtml() {
  return `<a href="./methodology.html" class="methodology-link">Methodology &rarr;</a>`;
}

// A company's MURLACH interest never shows up in company.fields, because
// that list is built from RESOLVED (published, totalled) field-months
// only - and MURLACH's field-months are all category "future_only",
// never resolved (spec section 15.11/15.12). So membership has to be
// checked against MURLACH's own field-equity artifact (its real recorded
// ownership_intervals), not against the company's aggregate field list.
// This one small, cached fetch is the only way to answer "is this
// company one of MURLACH's recorded interest holders?" without
// hardcoding company names into the frontend.
async function isMurlachAffected(companyName) {
  try {
    const murlach = await getFieldEquity(MURLACH_FIELD_SLUG);
    return murlach.ownership_intervals.some((iv) => iv.company_name === companyName);
  } catch {
    return false; // MURLACH data itself failing to load is not this company's problem to report
  }
}

function murlachNoteHtml() {
  return `<div class="murlach-note">
    <strong>Unresolved source-data case:</strong> ${escapeHtml(MURLACH_NOTE)}
    ${equityMethodologyLinkHtml()}
  </div>`;
}

function coverageWarningExplanation(streamMeta, streamEntry) {
  if (streamEntry.status !== "warning") return "";
  return `<div class="coverage-explanation">
    ${escapeHtml(streamMeta.label)} coverage is ${streamEntry.coverage_pct}% this period
    (below 99.5%, at or above 95%): some producing field volumes were excluded
    because current equity interests could not be resolved for every field.
    Value shown is still published.
  </div>`;
}

function renderEquityPanelShell(companyName) {
  const panel = document.getElementById("field-panel");
  const content = document.getElementById("field-panel-content");
  content.innerHTML = `
    <div class="panel-field-name">${escapeHtml(companyName)}</div>
    <div class="panel-meta-row">${escapeHtml(LEGAL_ENTITY_LABEL)}</div>
    <div class="panel-caveat">
      Equity-attributable production based on dated NSTA field interests.
      ${equityMethodologyLinkHtml()}
    </div>
    <div class="panel-loading">Loading equity data&hellip;</div>
  `;
  panel.hidden = false;
}

async function renderEquityPanelBody(company, meta, { initialStreamIndex = 0 } = {}) {
  const content = document.getElementById("field-panel-content");
  const loadingEl = content.querySelector(".panel-loading");
  if (loadingEl) loadingEl.remove();

  const latest = company.series[company.series.length - 1];
  const murlachAffected = await isMurlachAffected(company.name);
  const startIndex =
    Number.isInteger(initialStreamIndex) && initialStreamIndex >= 0 && initialStreamIndex < PRODUCTION_STREAMS.length
      ? initialStreamIndex
      : 0;

  const section = document.createElement("div");
  section.innerHTML = `
    <div class="panel-meta-row">First published period: ${escapeHtml(formatPeriodShort(company.first_published_period))}</div>
    <div class="panel-meta-row">Latest published period: ${escapeHtml(formatPeriodShort(company.last_published_period))}</div>
    <div class="panel-meta-row">Contributing fields: ${company.field_count}</div>

    <div class="panel-section-title">Latest equity-attributable production</div>
    <table class="equity-latest-table">
      <thead><tr><th>Stream</th><th>Value</th><th>Coverage</th></tr></thead>
      <tbody>
        ${PRODUCTION_STREAMS.map((s) => `
          <tr>
            <td>${escapeHtml(s.label)}</td>
            <td>${latestValueHtml(s, latest[s.key])}</td>
            <td>${statusBadgeHtml(latest[s.key])}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
    ${PRODUCTION_STREAMS.map((s) => coverageWarningExplanation(s, latest[s.key])).join("")}

    ${murlachAffected ? murlachNoteHtml() : ""}

    <div class="panel-section-title">Monthly equity-attributable production</div>
    <div class="stream-selector" role="tablist" aria-label="Production stream">
      ${PRODUCTION_STREAMS.map(
        (s, i) => `<button type="button" class="stream-tab" role="tab" aria-selected="${i === startIndex}"
          data-stream-index="${i}">${escapeHtml(s.label)}</button>`
      ).join("")}
    </div>
    <div id="equity-chart" class="chart-box"></div>

    <div class="panel-section-title">Contributing fields (${company.fields.length})</div>
    <div class="field-slug-list">${company.fields.map((f) => escapeHtml(f)).join(", ")}</div>

    <div class="panel-meta-row source-limitations">
      <details>
        <summary>Source limitations</summary>
        <ul>${(meta.source_limitations || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul>
      </details>
    </div>
  `;
  content.appendChild(section);

  const chartEl = document.getElementById("equity-chart");
  const drawStream = (index) => {
    const streamMeta = PRODUCTION_STREAMS[index];
    const points = company.series.map((entry) => ({
      period: entry.period,
      value: entry[streamMeta.key].value,
      status: entry[streamMeta.key].status,
      coverage_pct: entry[streamMeta.key].coverage_pct,
    }));
    renderEquityStreamChart(chartEl, points, streamMeta.label, streamMeta.unit).catch((err) => {
      const errEl = document.createElement("div");
      errEl.className = "panel-error";
      errEl.textContent = `Failed to load chart.\n\n${err.message}`;
      chartEl.appendChild(errEl);
    });
    for (const btn of content.querySelectorAll(".stream-tab")) {
      btn.setAttribute("aria-selected", String(Number(btn.dataset.streamIndex) === index));
    }
    // Selecting a stream updates the shareable URL - never a full reload
    // (history.replaceState, same as every other selection in this app).
    // Always runs, including the initial draw on open/restore: since
    // setUrlState is idempotent (replaceState, not pushState), writing
    // back an already-correct state on restore is a harmless no-op, and
    // this is the one place that guarantees the URL always reflects
    // whichever stream is actually showing.
    setUrlState({ view: "equity", slug: company.slug, metric: "equity", stream: streamMeta.urlSlug });
  };

  for (const btn of content.querySelectorAll(".stream-tab")) {
    btn.addEventListener("click", () => drawStream(Number(btn.dataset.streamIndex)));
  }
  drawStream(startIndex);
}

export async function openEquityPanel(companySlug, companyName, { onError, initialStreamIndex = 0 } = {}) {
  renderEquityPanelShell(companyName ?? companySlug);
  try {
    const [company, meta] = await Promise.all([getCompanyEquity(companySlug), getEquityMeta()]);
    await renderEquityPanelBody(company, meta, { initialStreamIndex });
  } catch (err) {
    const content = document.getElementById("field-panel-content");
    const loadingEl = content.querySelector(".panel-loading");
    if (loadingEl) loadingEl.remove();
    const errEl = document.createElement("div");
    errEl.className = "panel-error";
    const category = err instanceof DataLoadError ? "Equity company data" : "Unexpected error";
    errEl.textContent = `${category} failed to load.\n\n${err.message}`;
    content.appendChild(errEl);
    if (onError) onError(err);
  }
}

// --- Field ownership section (added to the existing field panel) ---

// Current (open-ended, end_date null) interests first - among those,
// most recently started first - then historic (ended) interests sorted
// descending by end_date, i.e. the most recently-ended position at the
// top of the historic block (spec: "current or most recent owners at
// the top... historic ownership positions sorted in descending order by
// date"). start_date/end_date are zero-padded date-like strings
// ("YYYYMM" or "YYYY-MM-DD" depending on source), so a plain string
// comparison already sorts them chronologically - no date parsing needed.
function sortIntervalsByRecency(intervals) {
  return [...intervals].sort((a, b) => {
    const aCurrent = a.end_date == null;
    const bCurrent = b.end_date == null;
    if (aCurrent !== bCurrent) return aCurrent ? -1 : 1;
    if (aCurrent) return b.start_date.localeCompare(a.start_date);
    return b.end_date.localeCompare(a.end_date);
  });
}

function ownershipRowsHtml(intervals) {
  const realIntervals = sortIntervalsByRecency(
    intervals.filter((iv) => iv.start_date !== iv.end_date)
  );
  const eventRecords = [...intervals.filter((iv) => iv.start_date === iv.end_date)].sort(
    (a, b) => b.start_date.localeCompare(a.start_date)
  );

  const rows = realIntervals
    .map((iv) => {
      const isZeroInterest = iv.interest_pct === 0;
      return `<tr class="${isZeroInterest ? "zero-interest-row" : ""}">
        <td>${escapeHtml(iv.company_name)}</td>
        <td>${isZeroInterest ? '<span class="zero-interest-badge">0% (not an economic interest)</span>' : `${iv.interest_pct}%`}</td>
        <td>${escapeHtml(iv.start_date)}</td>
        <td>${iv.end_date ? escapeHtml(iv.end_date) : "Current"}</td>
        <td>${iv.operator_flag === "Y" ? "Operator (source metadata only - not an equity claim)" : "&ndash;"}</td>
      </tr>`;
    })
    .join("");

  const eventRows = eventRecords
    .map(
      (iv) => `<tr>
        <td>${escapeHtml(iv.company_name)}</td>
        <td>${iv.interest_pct}%</td>
        <td colspan="2">${escapeHtml(iv.start_date)} (source event record - not an ownership period)</td>
        <td>${iv.operator_flag === "Y" ? "Operator" : "&ndash;"}</td>
      </tr>`
    )
    .join("");

  return { rows, eventRows, eventCount: eventRecords.length };
}

function renderFieldOwnershipBody(container, fieldEquity) {
  const { rows, eventRows, eventCount } = ownershipRowsHtml(fieldEquity.ownership_intervals);
  const excluded = fieldEquity.excluded_periods || [];
  container.innerHTML = `
    <div class="panel-meta-row">Field-match method: ${escapeHtml(fieldEquity.field_match_method)}</div>
    <table class="unit-table ownership-table">
      <thead><tr><th>Legal entity</th><th>Interest</th><th>From</th><th>To</th><th>Operator flag</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    ${
      eventCount > 0
        ? `<details class="source-event-details">
             <summary>${eventCount} source event record(s) (not ownership periods)</summary>
             <table class="unit-table ownership-table"><tbody>${eventRows}</tbody></table>
           </details>`
        : ""
    }
    ${
      excluded.length > 0
        ? `<div class="panel-storage-note">
             ${excluded.length} period(s) excluded or unresolved for this field's equity
             attribution: ${excluded.map((p) => escapeHtml(formatPeriodShort(p))).join(", ")}.
           </div>`
        : ""
    }
  `;
}

export function attachFieldOwnershipTab(fieldSlug) {
  const tabButton = document.getElementById("field-panel-tab-ownership");
  const productionTab = document.getElementById("field-panel-tab-production");
  const ownershipContent = document.getElementById("field-panel-ownership-content");
  const productionContent = document.getElementById("field-panel-production-content");
  if (!tabButton) return;

  let loaded = false;
  tabButton.hidden = false;
  tabButton.setAttribute("aria-selected", "false");
  productionTab.setAttribute("aria-selected", "true");
  ownershipContent.hidden = true;
  productionContent.hidden = false;

  tabButton.onclick = async () => {
    tabButton.setAttribute("aria-selected", "true");
    productionTab.setAttribute("aria-selected", "false");
    ownershipContent.hidden = false;
    productionContent.hidden = true;
    if (loaded) return;
    loaded = true;
    ownershipContent.innerHTML = `<div class="panel-loading">Loading ownership data&hellip;</div>`;
    try {
      const fieldEquity = await getFieldEquity(fieldSlug);
      renderFieldOwnershipBody(ownershipContent, fieldEquity);
    } catch (err) {
      const category = err instanceof DataLoadError ? "Field ownership data" : "Unexpected error";
      ownershipContent.innerHTML = `<div class="panel-error">${escapeHtml(category)} failed to load.\n\n${escapeHtml(err.message)}</div>`;
    }
  };

  productionTab.onclick = () => {
    productionTab.setAttribute("aria-selected", "true");
    tabButton.setAttribute("aria-selected", "false");
    productionContent.hidden = false;
    ownershipContent.hidden = true;
  };
}
