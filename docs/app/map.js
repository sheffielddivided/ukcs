// Map view (spec section 10.2 View A, minimal scope for step 4: map,
// markers, tooltips, operator filter only - no commodity toggle, region
// select, period select or search yet).
//
// MapLibre GL JS, pinned version, loaded as an ES module from jsDelivr
// with a verified SRI hash (spec section 2/10.1). OSM raster tiles, no
// API key. The browser never calls any NSTA or ArcGIS host - the only
// network calls this file makes are to the CDN (once, for the library)
// and to OSM tile servers for basemap imagery.
// maplibre-gl@6.8.0 ships only named exports (no default export) from its
// ESM build - import the pieces this file actually uses.
import {
  Map as MapLibreMap,
  AttributionControl,
  NavigationControl,
  Popup,
} from "https://cdn.jsdelivr.net/npm/maplibre-gl@6.8.0/dist/maplibre-gl.mjs";

const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors';

// Named boe/d conversion constant for marker sizing only (spec section
// 8.4: a derived boe_d figure is permitted in the UI only if computed in
// the frontend, with a single named constant, displayed to the user).
// This value is NOT written to any committed artifact - it exists solely
// to give markers of different commodities a comparable size, and is
// shown in the legend so the convention is never hidden.
const GAS_MSCF_PER_BOE = 5.8;

const SOURCE_ID = "fields";
const CIRCLE_LAYER_ID = "fields-circles";

function computeDerivedProperties(fieldsGeojson) {
  // Adds boe_d (sizing only) and commodity (oil/gas/none, for colour) to
  // each feature's properties. Pure frontend derivation - fields.geojson
  // itself carries only the native-unit values per spec section 8.4.
  for (const feature of fieldsGeojson.features) {
    const p = feature.properties;
    const oil = (p.oil_mbd || 0) + (p.condensate_mbd || 0);
    const gas = ((p.assoc_gas_mmscfd || 0) + (p.dry_gas_mmscfd || 0)) / GAS_MSCF_PER_BOE;
    const boeD = oil + gas;
    p.boe_d = boeD;
    if (boeD <= 0) {
      p.commodity = "none";
    } else if (oil / boeD >= 0.5) {
      p.commodity = "oil";
    } else {
      p.commodity = "gas";
    }
  }
  return fieldsGeojson;
}

function buildPopupHtml(properties) {
  const notesHtml = properties.notes
    ? `<div class="popup-caveat">${properties.notes.join("; ")}</div>`
    : "";
  const storageNote =
    properties.storage_unit_count > 0
      ? `<div class="popup-caveat">${properties.storage_unit_count} storage reporting unit(s) excluded from these totals.</div>`
      : "";
  return `
    <div class="popup-field-name">${properties.field}</div>
    <div class="popup-row">Operator: ${properties.operator ?? "–"}</div>
    <div class="popup-row">Region: ${properties.region ?? "–"} (${properties.location ?? "–"})</div>
    <div class="popup-row">Period: ${properties.period}</div>
    <div class="popup-row">Oil: ${properties.oil_mbd} mb/d &middot; Condensate: ${properties.condensate_mbd} mb/d</div>
    <div class="popup-row">Assoc. gas: ${properties.assoc_gas_mmscfd} MMscf/d &middot; Dry gas: ${properties.dry_gas_mmscfd} MMscf/d</div>
    <div class="popup-row">Water: ${properties.water_mbd} mb/d</div>
    <div class="popup-row">Reporting units: ${properties.unit_count} production${
    properties.storage_unit_count ? `, ${properties.storage_unit_count} storage` : ""
  }</div>
    ${storageNote}
    ${notesHtml}
  `;
}

export function initMap(containerId, fieldsGeojsonRaw, onFieldClick) {
  const fieldsGeojson = computeDerivedProperties(fieldsGeojsonRaw);

  const map = new MapLibreMap({
    container: containerId,
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
      layers: [
        {
          id: "osm",
          type: "raster",
          source: "osm",
        },
      ],
    },
    center: [-1.5, 58],
    zoom: 5,
  });

  map.addControl(new AttributionControl({ compact: false }));
  map.addControl(new NavigationControl(), "top-right");

  map.on("load", () => {
    map.addSource(SOURCE_ID, { type: "geojson", data: fieldsGeojson });

    map.addLayer({
      id: CIRCLE_LAYER_ID,
      type: "circle",
      source: SOURCE_ID,
      paint: {
        // Radius scales with sqrt(boe_d) per spec (View A: "Markers sized
        // by sqrt(value)"), clamped to a sane pixel range.
        "circle-radius": [
          "interpolate",
          ["linear"],
          ["sqrt", ["max", ["get", "boe_d"], 0]],
          0, 4,
          5, 8,
          10, 14,
          20, 22,
          30, 28,
        ],
        "circle-color": [
          "match",
          ["get", "commodity"],
          "oil", "#eb6834",
          "gas", "#2a78d6",
          "#898781",
        ],
        "circle-opacity": 0.85,
        "circle-stroke-width": 1,
        "circle-stroke-color": "#ffffff",
      },
    });

    const popup = new Popup({
      closeButton: false,
      closeOnClick: false,
      maxWidth: "280px",
    });

    map.on("mouseenter", CIRCLE_LAYER_ID, (e) => {
      map.getCanvas().style.cursor = "pointer";
      const feature = e.features[0];
      popup
        .setLngLat(feature.geometry.coordinates)
        .setHTML(buildPopupHtml(feature.properties))
        .addTo(map);
    });

    map.on("mousemove", CIRCLE_LAYER_ID, (e) => {
      const feature = e.features[0];
      popup
        .setLngLat(feature.geometry.coordinates)
        .setHTML(buildPopupHtml(feature.properties));
    });

    map.on("mouseleave", CIRCLE_LAYER_ID, () => {
      map.getCanvas().style.cursor = "";
      popup.remove();
    });

    if (onFieldClick) {
      map.on("click", CIRCLE_LAYER_ID, (e) => {
        onFieldClick(e.features[0].properties);
      });
    }
  });

  return map;
}

export function filterByOperator(map, operator) {
  if (!map.getLayer(CIRCLE_LAYER_ID)) return;
  if (!operator) {
    map.setFilter(CIRCLE_LAYER_ID, null);
  } else {
    map.setFilter(CIRCLE_LAYER_ID, ["==", ["get", "operator"], operator]);
  }
}
