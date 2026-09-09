// Shareable URL state via location.hash (spec: equity frontend
// checkpoint). Never touches the path, so it stays compatible with the
// /ukcs/ GitHub Pages subpath, and never exposes internal file paths -
// only the view/slug/metric/stream vocabulary below. Uses
// history.replaceState so ordinary interaction never triggers a full
// page reload or pollutes browser history with every panel click, while
// the resulting URL remains copyable and restorable like any other.

const VALID_VIEWS = new Set(["field", "equity", "operator"]);
const VALID_METRICS = new Set(["equity", "operator"]);

export function parseUrlState() {
  const raw = location.hash.replace(/^#/, "");
  if (!raw) return {};
  const params = new URLSearchParams(raw);
  const state = {};
  const view = params.get("view");
  if (view && VALID_VIEWS.has(view)) state.view = view;
  const slug = params.get("slug");
  if (slug) state.slug = slug;
  const metric = params.get("metric");
  if (metric && VALID_METRICS.has(metric)) state.metric = metric;
  const stream = params.get("stream");
  if (stream) state.stream = stream;
  return state;
}

export function setUrlState(state) {
  const params = new URLSearchParams();
  if (state.view) params.set("view", state.view);
  if (state.slug) params.set("slug", state.slug);
  if (state.metric) params.set("metric", state.metric);
  if (state.stream) params.set("stream", state.stream);
  const newHash = params.toString() ? `#${params.toString()}` : " ";
  history.replaceState(null, "", newHash.trim() === "" ? location.pathname + location.search : `${location.pathname}${location.search}${newHash}`);
}
