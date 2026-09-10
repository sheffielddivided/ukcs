// History charts (spec section 10.2 View B / 13 step 6).
//
// Oil/condensate (mb/d) and gas (MMscf/d) are rendered as two SEPARATE
// charts, each with its own single y-axis - never one chart with dual
// y-axes sharing mb/d and MMscf/d. Two charts is a stronger guarantee of
// "never share an axis" than a dual-axis single chart would be, and
// avoids the reader having to work out which line belongs to which axis.
//
// ECharts is loaded lazily on first use (not on page load) via a
// dynamically injected <script> with a verified SRI hash, so the map view
// (spec section 13 step 4) never pays ECharts' ~1.1 MB load cost unless a
// field panel is actually opened.

const ECHARTS_URL = "https://cdn.jsdelivr.net/npm/echarts@6.1.0/dist/echarts.min.js";
const ECHARTS_SRI = "sha256-tmslrrTfhOMxmdwhaUAU0zbSIsvZ3rDlp8FL1qoND9A=";

let echartsLoadPromise = null;

function loadEcharts() {
  if (echartsLoadPromise) return echartsLoadPromise;
  echartsLoadPromise = new Promise((resolve, reject) => {
    if (window.echarts) {
      resolve(window.echarts);
      return;
    }
    const script = document.createElement("script");
    script.src = ECHARTS_URL;
    script.integrity = ECHARTS_SRI;
    script.crossOrigin = "anonymous";
    script.onload = () => resolve(window.echarts);
    script.onerror = () =>
      reject(
        new Error(
          `Failed to load ECharts from ${ECHARTS_URL} - either a network ` +
            "error, or the script was blocked because its bytes did not " +
            "match the pinned integrity hash."
        )
      );
    document.head.appendChild(script);
  });
  return echartsLoadPromise;
}

let liquidsChart = null;
let gasChart = null;
let resizeListenerAttached = false;

function attachResizeListener() {
  if (resizeListenerAttached) return;
  resizeListenerAttached = true;
  window.addEventListener("resize", () => {
    if (liquidsChart) liquidsChart.resize();
    if (gasChart) gasChart.resize();
  });
}

export async function renderHistoryCharts(liquidsEl, gasEl, series) {
  const echarts = await loadEcharts();
  attachResizeListener();

  if (liquidsChart) liquidsChart.dispose();
  if (gasChart) gasChart.dispose();

  const periods = series.map((s) => s.period);
  const axisLabel = { rotate: 45, fontSize: 10 };
  const grid = { top: 56, left: 55, right: 20, bottom: 40 };

  liquidsChart = echarts.init(liquidsEl);
  liquidsChart.setOption({
    title: { text: "Oil & condensate (mb/d)", left: 4, textStyle: { fontSize: 13 } },
    tooltip: { trigger: "axis" },
    legend: { data: ["Oil", "Condensate"], top: 26, textStyle: { fontSize: 11 } },
    grid,
    xAxis: { type: "category", data: periods, axisLabel },
    yAxis: { type: "value", name: "mb/d" },
    series: [
      {
        name: "Oil", type: "line", showSymbol: false, color: "#2a78d6",
        data: series.map((s) => s.oil_mbd),
      },
      {
        name: "Condensate", type: "line", showSymbol: false, color: "#eb6834",
        data: series.map((s) => s.condensate_mbd),
      },
    ],
  });

  gasChart = echarts.init(gasEl);
  gasChart.setOption({
    title: { text: "Gas (MMscf/d)", left: 4, textStyle: { fontSize: 13 } },
    tooltip: { trigger: "axis" },
    legend: { data: ["Associated gas", "Dry gas"], top: 26, textStyle: { fontSize: 11 } },
    grid,
    xAxis: { type: "category", data: periods, axisLabel },
    yAxis: { type: "value", name: "MMscf/d" },
    series: [
      {
        name: "Associated gas", type: "line", showSymbol: false, color: "#1baf7a",
        data: series.map((s) => s.assoc_gas_mmscfd),
      },
      {
        name: "Dry gas", type: "line", showSymbol: false, color: "#eda100",
        data: series.map((s) => s.dry_gas_mmscfd),
      },
    ],
  });
}

// Single-stream equity chart (spec: equity frontend checkpoint). One
// stream per chart, its own unit, never combined with another stream's
// axis. Unavailable months are passed as `value: null` - ECharts leaves a
// genuine gap for a null point (it does not connect across it) unless
// connectNulls is set, which this deliberately never sets, so a gap in
// coverage is never visually smoothed over into an implied continuous
// line (spec: "never display zero as a substitute", "do not connect a
// chart line across an unavailable month").
let equityChart = null;

export async function renderEquityStreamChart(el, points, streamLabel, unit) {
  const echarts = await loadEcharts();
  attachResizeListener();

  if (equityChart) equityChart.dispose();
  equityChart = echarts.init(el);

  const periods = points.map((p) => p.period);
  const values = points.map((p) => (p.status === "unavailable" ? null : p.value));

  equityChart.setOption({
    title: { text: `${streamLabel} (${unit})`, left: 4, textStyle: { fontSize: 13 } },
    tooltip: {
      trigger: "axis",
      formatter: (params) => {
        const p = params[0];
        const point = points[p.dataIndex];
        const statusLabel = { complete: "Complete", warning: "Warning", unavailable: "Not available" }[point.status] || point.status;
        const valueText = point.status === "unavailable" ? "Not available" : `${point.value} ${unit}`;
        const coverageText = point.coverage_pct == null ? "n/a" : `${point.coverage_pct}%`;
        return (
          `${point.period}<br/>` +
          `${streamLabel}: ${valueText}<br/>` +
          `Coverage: ${coverageText} (${statusLabel})`
        );
      },
    },
    grid: { top: 56, left: 60, right: 20, bottom: 40 },
    xAxis: { type: "category", data: periods, axisLabel: { rotate: 45, fontSize: 10 } },
    yAxis: { type: "value", name: unit },
    series: [
      {
        name: streamLabel,
        type: "line",
        showSymbol: false,
        connectNulls: false,
        color: "#2a78d6",
        data: values,
      },
    ],
  });
}

// Production overview chart (Deliverable 1). Renders EITHER the default
// Liquids/Natural gas stacked split (commodity mode) OR an N-series
// stacked split (company/field mode, series pre-built by the caller) -
// one shared renderer since both are "stacked series + an optional
// reconciling Total line", just with a different series list. Unavailable
// points are passed as `value: null` so ECharts leaves a genuine gap
// (never zero - same discipline as renderEquityStreamChart above).
let productionChart = null;

export async function renderProductionChart(el, periods, stackedSeries, totalSeries, unit = "mboe/d") {
  const echarts = await loadEcharts();
  attachResizeListener();

  if (productionChart) productionChart.dispose();
  productionChart = echarts.init(el);

  const series = stackedSeries.map((s) => ({
    name: s.name,
    type: "bar",
    stack: "production",
    color: s.color,
    data: s.data,
  }));
  if (totalSeries) {
    series.push({
      name: totalSeries.name || "Total",
      type: "line",
      showSymbol: false,
      color: totalSeries.color || "#1a1a1a",
      data: totalSeries.data,
      z: 10,
    });
  }

  productionChart.setOption({
    tooltip: { trigger: "axis" },
    legend: { top: 4, textStyle: { fontSize: 11 } },
    grid: { top: 40, left: 60, right: 20, bottom: 60 },
    xAxis: { type: "category", data: periods, axisLabel: { rotate: 45, fontSize: 10 } },
    yAxis: { type: "value", name: unit },
    series,
  });
  return productionChart;
}

export function disposeProductionChart() {
  if (productionChart) {
    productionChart.dispose();
    productionChart = null;
  }
}
