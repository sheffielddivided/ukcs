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
let fieldAnnualChart = null;
let resizeListenerAttached = false;

function attachResizeListener() {
  if (resizeListenerAttached) return;
  resizeListenerAttached = true;
  window.addEventListener("resize", () => {
    // Every live chart, not just the field panel's pair - an ECharts
    // instance never reflows on its own, so one left out of this list
    // keeps its old pixel width after a rotation or window resize.
    for (const chart of [liquidsChart, gasChart, fieldAnnualChart, equityChart, productionChart]) {
      if (chart) chart.resize();
    }
  });
}

// ---------------------------------------------------------------------------
// Chart theme
//
// Colours are read from the stylesheet's design tokens at render time rather
// than hardcoded here, so there is exactly ONE palette in the project and
// charts follow the page's light/dark theme automatically (the dark steps are
// a selected set for the dark surface, not an auto-flip of the light ones -
// see docs/styles.css). A chart rendered before the stylesheet resolves falls
// back to the light-mode value baked in as the second argument.
// ---------------------------------------------------------------------------

const FONT_FAMILY = 'system-ui, -apple-system, "Segoe UI", sans-serif';

function chartTheme() {
  const css = getComputedStyle(document.documentElement);
  const token = (name, fallback) => (css.getPropertyValue(name) || "").trim() || fallback;
  return {
    surface: token("--surface", "#fcfcfb"),
    surfaceRaised: token("--surface-raised", "#ffffff"),
    grid: token("--grid", "#e1e0d9"),
    axis: token("--axis", "#c3c2b7"),
    border: token("--border-strong", "rgba(11,11,11,0.18)"),
    ink: token("--text-primary", "#0b0b0b"),
    secondary: token("--text-secondary", "#52514e"),
    muted: token("--text-muted", "#898781"),
    series: [
      token("--series-1", "#2a78d6"),
      token("--series-2", "#eb6834"),
      token("--series-3", "#1baf7a"),
      token("--series-4", "#eda100"),
      token("--series-5", "#e87ba4"),
      token("--series-6", "#008300"),
      token("--series-7", "#4a3aa7"),
      token("--series-8", "#e34948"),
      token("--series-9", "#009aa8"),
      token("--series-10", "#9c5f1f"),
    ],
    other: token("--series-other", "#c3c2b7"),
  };
}

/** The categorical series palette, in fixed slot order, for the current
 * theme. Callers assign slot N to the Nth series and never cycle past the
 * end - beyond ten series, identity stops being readable by colour, which
 * is why both split views fold the remainder into a single "Other". */
export function seriesPalette() {
  const theme = chartTheme();
  return { colors: theme.series, other: theme.other };
}

// Recessive chrome: hairline gridlines one step off the surface, no axis
// line doubling up with the baseline, muted tick labels.
function axisDefaults(theme) {
  return {
    category: {
      axisLine: { lineStyle: { color: theme.axis } },
      axisTick: { show: false },
      axisLabel: { color: theme.muted, fontSize: 11, fontFamily: FONT_FAMILY, hideOverlap: true },
    },
    value: {
      splitLine: { lineStyle: { color: theme.grid, width: 1, type: "solid" } },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: theme.muted, fontSize: 11, fontFamily: FONT_FAMILY },
      nameTextStyle: { color: theme.muted, fontSize: 11, align: "left" },
      nameGap: 12,
    },
  };
}

function tooltipDefaults(theme) {
  return {
    backgroundColor: theme.surfaceRaised,
    borderColor: theme.border,
    borderWidth: 1,
    padding: [8, 10],
    extraCssText: "border-radius:10px;box-shadow:0 6px 20px -6px rgba(11,11,11,0.18);",
    textStyle: { color: theme.ink, fontSize: 12, fontFamily: FONT_FAMILY },
    axisPointer: { lineStyle: { color: theme.axis }, crossStyle: { color: theme.axis } },
  };
}

/** One segment of a stacked bar. Segments are separated by a gap in the
 * surface colour (a border drawn in the surface colour on each of two
 * touching segments) rather than by an outline: an ink stroke would add
 * weight that isn't data, while the gap lets neighbouring slots read as
 * distinct without one.
 *
 * `dense` turns that gap off. ECharts borders a bar on all four sides, so
 * on a long series - the full 1975-2026 history is 52 columns, a few pixels
 * each on a phone - a 1px border per side eats most of the bar's width and
 * the run reads as hairline stripes instead of a mass. Dense runs are
 * already separated by the category gap, so they don't need it. */
function stackedBar(name, color, data, theme, { stack = "production", dense = false } = {}) {
  return {
    name,
    type: "bar",
    stack,
    color,
    data,
    barMaxWidth: 24,
    barCategoryGap: dense ? "12%" : "20%",
    itemStyle: dense ? {} : { borderColor: theme.surface, borderWidth: 1 },
  };
}

// Above this many categories, bars are too narrow to carry a surface gap.
const DENSE_CATEGORY_COUNT = 36;

function legendDefaults(theme) {
  return {
    type: "scroll",
    icon: "circle",
    itemWidth: 9,
    itemHeight: 9,
    itemGap: 14,
    // Legend text wears an ink token, never the series colour - a light
    // categorical hue is illegible as text; the dot beside it carries identity.
    textStyle: { color: theme.secondary, fontSize: 11, fontFamily: FONT_FAMILY },
    pageTextStyle: { color: theme.muted, fontSize: 11 },
    pageIconColor: theme.secondary,
    pageIconInactiveColor: theme.axis,
    pageIconSize: 10,
  };
}

export async function renderHistoryCharts(liquidsEl, gasEl, series) {
  const echarts = await loadEcharts();
  attachResizeListener();

  if (liquidsChart) liquidsChart.dispose();
  if (gasChart) gasChart.dispose();

  const theme = chartTheme();
  const axes = axisDefaults(theme);
  const periods = series.map((s) => s.period);
  const grid = { top: 54, left: 8, right: 16, bottom: 8, containLabel: true };
  const title = (text) => ({
    text,
    left: 0,
    top: 0,
    textStyle: { fontSize: 12.5, fontWeight: 600, color: theme.ink, fontFamily: FONT_FAMILY },
  });
  const line = (name, color, data) => ({
    name,
    type: "line",
    showSymbol: false,
    color,
    data,
    lineStyle: { width: 2, cap: "round", join: "round" },
  });

  liquidsChart = echarts.init(liquidsEl);
  liquidsChart.setOption({
    title: title("Oil & condensate (mb/d)"),
    tooltip: { trigger: "axis", ...tooltipDefaults(theme) },
    legend: { ...legendDefaults(theme), data: ["Oil", "Condensate"], top: 22, left: 0 },
    grid,
    xAxis: { type: "category", data: periods, ...axes.category },
    yAxis: { type: "value", ...axes.value },
    series: [
      line("Oil", theme.series[0], series.map((s) => s.oil_mbd)),
      line("Condensate", theme.series[1], series.map((s) => s.condensate_mbd)),
    ],
  });

  gasChart = echarts.init(gasEl);
  gasChart.setOption({
    title: title("Gas (MMscf/d)"),
    tooltip: { trigger: "axis", ...tooltipDefaults(theme) },
    legend: { ...legendDefaults(theme), data: ["Associated gas", "Dry gas"], top: 22, left: 0 },
    grid,
    xAxis: { type: "category", data: periods, ...axes.category },
    yAxis: { type: "value", ...axes.value },
    series: [
      line("Associated gas", theme.series[2], series.map((s) => s.assoc_gas_mmscfd)),
      line("Dry gas", theme.series[3], series.map((s) => s.dry_gas_mmscfd)),
    ],
  });
}

// Field panel's annual oil/gas bar chart (2026-09-10 continuation):
// consolidates the field's native-unit series down to two mboe/d series -
// Oil (oil + condensate) and Gas (assoc + dry gas, already converted by
// the caller using the one published gas_scf_per_boe factor) - shown as
// annual averages, in bars, replacing the previous two separate
// monthly line charts (mb/d and MMscf/d, on two different units). A
// year with no known value for a series is passed as `value: null` so
// ECharts leaves a genuine gap rather than drawing a fabricated zero bar.
export async function renderFieldAnnualChart(el, years, oilMboed, gasMboed) {
  const echarts = await loadEcharts();
  attachResizeListener();

  if (fieldAnnualChart) fieldAnnualChart.dispose();
  const theme = chartTheme();
  const axes = axisDefaults(theme);
  fieldAnnualChart = echarts.init(el);
  fieldAnnualChart.setOption({
    tooltip: { trigger: "axis", ...tooltipDefaults(theme) },
    legend: { ...legendDefaults(theme), data: ["Oil", "Gas"], top: 0, left: 78, right: 4 },
    grid: { top: 38, left: 8, right: 16, bottom: 4, containLabel: true },
    xAxis: { type: "category", data: years, ...axes.category },
    yAxis: { type: "value", name: "mboe/d", ...axes.value },
    series: [
      stackedBar("Oil", theme.series[1], oilMboed, theme, { dense: years.length > DENSE_CATEGORY_COUNT }),
      stackedBar("Gas", theme.series[0], gasMboed, theme, { dense: years.length > DENSE_CATEGORY_COUNT }),
    ],
  });
  return fieldAnnualChart;
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

  const theme = chartTheme();
  const axes = axisDefaults(theme);

  equityChart.setOption({
    title: {
      text: streamLabel,
      left: 0,
      top: 0,
      textStyle: { fontSize: 12.5, fontWeight: 600, color: theme.ink, fontFamily: FONT_FAMILY },
    },
    tooltip: {
      trigger: "axis",
      ...tooltipDefaults(theme),
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
    grid: { top: 46, left: 8, right: 16, bottom: 4, containLabel: true },
    xAxis: { type: "category", data: periods, ...axes.category },
    // The unit lives on the axis, not in the title: one stream per chart,
    // one unit per axis, and the axis is where a reader looks for it.
    yAxis: { type: "value", name: unit, ...axes.value },
    series: [
      {
        name: streamLabel,
        type: "line",
        showSymbol: false,
        connectNulls: false,
        color: theme.series[0],
        lineStyle: { width: 2, cap: "round", join: "round" },
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

  const theme = chartTheme();
  const axes = axisDefaults(theme);

  const dense = periods.length > DENSE_CATEGORY_COUNT;
  const series = stackedSeries.map((s) => stackedBar(s.name, s.color, s.data, theme, { dense }));
  if (totalSeries) {
    series.push({
      name: totalSeries.name || "Total",
      type: "line",
      showSymbol: false,
      // The reconciling total is chrome, not a category: it wears ink so it
      // reads as "the envelope" and never competes with a series colour.
      color: totalSeries.color || theme.ink,
      lineStyle: { width: 2, cap: "round", join: "round" },
      data: totalSeries.data,
      z: 10,
    });
  }

  productionChart.setOption({
    tooltip: { trigger: "axis", ...tooltipDefaults(theme) },
    // The unit label sits at the top-left (the y-axis `name`), so the legend
    // is bounded to the right of it and scrolls within that space. Letting
    // both claim the top-left is what had the legend sitting on top of
    // "mboe/d" on a narrow screen. A ten-series split pages rather than
    // wrapping (ECharts' scroll legend is single-row by design); every
    // segment is still identifiable without paging via the axis tooltip,
    // which names each series at the hovered period.
    legend: { ...legendDefaults(theme), top: 0, left: 78, right: 4 },
    grid: { top: 44, left: 8, right: 16, bottom: 4, containLabel: true },
    xAxis: { type: "category", data: periods, ...axes.category },
    yAxis: { type: "value", name: unit, ...axes.value },
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
