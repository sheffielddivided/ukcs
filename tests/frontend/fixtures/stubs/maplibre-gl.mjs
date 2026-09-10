// Minimal offline stand-in for maplibre-gl's ESM API surface, covering
// only what docs/app/map.js actually calls. Not a real map: no tiles are
// rendered, no WebGL context is created. This exists so the committed
// frontend tests can run in CI without a live CDN fetch or a real GPU.

class FakeCanvas {
  constructor() {
    this.style = {};
  }
}

// NB: this class is intentionally named Map (matching maplibre-gl's real
// export), which shadows the built-in Map inside this module - so
// internal bookkeeping below uses plain objects instead of `new Map()`.
export class Map {
  constructor(options) {
    this.options = options;
    this._handlers = {};
    this._layers = {};
    this._sources = {};
    this._canvas = new FakeCanvas();
    const container =
      typeof options.container === "string"
        ? document.getElementById(options.container)
        : options.container;
    if (container) {
      const div = document.createElement("div");
      div.className = "maplibregl-stub-canvas";
      container.appendChild(div);
    }
    // Fire "load" asynchronously, like the real library does.
    setTimeout(() => this._emit("load"), 0);
    // Test-only hook (mirrors the echarts stub's window.__echartsCharts
    // pattern) so committed tests can reach the map instance map.js
    // creates internally, to simulate layer click/hover events.
    window.__lastMapInstance = this;
  }

  addControl() {
    return this;
  }

  on(event, layerIdOrHandler, maybeHandler) {
    const handler = maybeHandler ?? layerIdOrHandler;
    const key = maybeHandler ? `${event}:${layerIdOrHandler}` : event;
    (this._handlers[key] ||= []).push(handler);
    return this;
  }

  _emit(event, payload) {
    for (const h of this._handlers[event] || []) h(payload);
  }

  // Test-only helper (not part of the real maplibre-gl API): fires a
  // layer-scoped event exactly as map.js's own `map.on(event, layerId,
  // handler)` registrations expect, so committed tests can simulate a
  // user clicking a specific rendered feature without a real WebGL
  // canvas or hit-testing.
  _emitLayerEvent(event, layerId, feature) {
    const key = `${event}:${layerId}`;
    for (const h of this._handlers[key] || []) h({ features: [feature] });
  }

  addSource(id, source) {
    this._sources[id] = source;
  }

  getSource(id) {
    return this._sources[id];
  }

  addLayer(layer) {
    this._layers[layer.id] = layer;
  }

  getLayer(id) {
    return this._layers[id];
  }

  setFilter(id, filter) {
    const layer = this._layers[id];
    if (layer) layer.filter = filter;
  }

  setLayoutProperty(id, name, value) {
    const layer = this._layers[id];
    if (layer) {
      layer.layout ||= {};
      layer.layout[name] = value;
    }
  }

  getLayoutProperty(id, name) {
    return this._layers[id]?.layout?.[name];
  }

  getCanvas() {
    return this._canvas;
  }
}

export class AttributionControl {
  constructor(options) {
    this.options = options;
  }
}

export class NavigationControl {}

export class Popup {
  constructor(options) {
    this.options = options;
  }
  setLngLat() {
    return this;
  }
  setHTML() {
    return this;
  }
  addTo() {
    return this;
  }
  remove() {
    return this;
  }
}
