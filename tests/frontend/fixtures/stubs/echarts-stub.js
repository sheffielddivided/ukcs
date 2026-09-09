// Minimal offline stand-in for the ECharts global, covering only what
// docs/app/charts.js calls (init/setOption/resize/dispose). Installed via
// Playwright's add_init_script BEFORE any page script runs, so
// charts.js's loadEcharts() sees `window.echarts` already defined and
// never attempts its CDN fetch (see the `if (window.echarts)`
// short-circuit in charts.js) - this is how the committed tests avoid
// both a live network dependency and the CDN script's SRI check.
//
// Recorded options are kept on window.__echartsCharts (by container
// element id) so tests can inspect exactly what a chart was asked to
// render - series data, tooltip formatter output, titles - without
// needing a real canvas/WebGL renderer.
(function () {
  window.__echartsCharts = {};

  function FakeChart(el) {
    this._el = el;
  }
  FakeChart.prototype.setOption = function (option) {
    this._lastOption = option;
    if (this._el && this._el.id) {
      window.__echartsCharts[this._el.id] = option;
    }
  };
  FakeChart.prototype.resize = function () {};
  FakeChart.prototype.dispose = function () {};

  window.echarts = {
    init: function (el) {
      return new FakeChart(el);
    },
  };
})();
