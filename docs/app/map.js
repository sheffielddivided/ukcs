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

// Marker sizing and dominant-commodity colouring use fields.geojson's own
// published total_mboed/liquids_mboed/natural_gas_mboed properties (spec
// section 17, approved 2026-09-10) - these are ETL-derived, using the
// single approved GAS_SCF_PER_BOE=6000 conversion constant
// (etl/production_config.py), the same value recorded in meta.json's
// production_conversion_methodology/gas_scf_per_boe fields. There is no
// second, frontend-local conversion constant here: this file previously
// computed its own undocumented boe/d figure for marker sizing only (a
// gas-per-boe constant never reconciled against any cited source) -
// removed in favour of reusing the one published, documented value, so
// there is exactly one gas-to-boe factor anywhere in this repository
// (tests/test_no_second_gas_conversion.py enforces this).

const SOURCE_ID = "fields";
const CIRCLE_LAYER_ID = "fields-circles";

// Authoritative field polygons (spec Workstream 3, approved 2026-09-10):
// NSTA's own field-determination geometry (docs/data/field_polygons.geojson,
// ETL-matched to PPRS field names - see etl/field_polygons.py). Polygon
// absence for a field never removes it from the map - the circle layer
// above remains the fallback for every field, matched or not (spec:
// "Polygon absence must never remove a producing field from the map.").
const POLYGON_SOURCE_ID = "field-polygons";
const POLYGON_FILL_LAYER_ID = "field-polygons-fill";
const POLYGON_OUTLINE_LAYER_ID = "field-polygons-outline";
const POLYGON_SELECTED_LAYER_ID = "field-polygons-selected";
// Medium/high zoom per spec: polygons become the primary geometry from
// here; below this the circle layer alone carries the map (still with
// low-prominence outlines available via the layer toggle).
const POLYGON_PROMINENT_MIN_ZOOM = 7;

function computeDerivedProperties(fieldsGeojson) {
  // Adds commodity (oil/gas/none, for marker colour) from the two
  // already-published, already-comparable mboe/d component fields - no
  // conversion happens here, both liquids_mboed and natural_gas_mboed
  // are already in the same unit.
  for (const feature of fieldsGeojson.features) {
    const p = feature.properties;
    const total = p.total_mboed || 0;
    if (total <= 0) {
      p.commodity = "none";
    } else if ((p.liquids_mboed || 0) / total >= 0.5) {
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

export function initMap(containerId, fieldsGeojsonRaw, onFieldClick, fieldPolygonsGeojson) {
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
        // Radius scales with sqrt(total_mboed) per spec (View A: "Markers
        // sized by sqrt(value)"), clamped to a sane pixel range.
        "circle-radius": [
          "interpolate",
          ["linear"],
          ["sqrt", ["max", ["get", "total_mboed"], 0]],
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

    // Authoritative field-determination polygons (spec Workstream 3) -
    // added even if there are zero polygons this build, so the layer
    // toggle always has something to attach to; a genuinely empty
    // FeatureCollection just renders nothing. Neutral fill (spec:
    // "Do not colour polygons by company"), low prominence below
    // POLYGON_PROMINENT_MIN_ZOOM, full prominence at/above it.
    if (fieldPolygonsGeojson) {
      map.addSource(POLYGON_SOURCE_ID, { type: "geojson", data: fieldPolygonsGeojson });

      map.addLayer({
        id: POLYGON_FILL_LAYER_ID,
        type: "fill",
        source: POLYGON_SOURCE_ID,
        paint: {
          "fill-color": "#5b6b7a",
          "fill-opacity": [
            "interpolate", ["linear"], ["zoom"],
            POLYGON_PROMINENT_MIN_ZOOM - 2, 0.05,
            POLYGON_PROMINENT_MIN_ZOOM, 0.18,
          ],
        },
      });
      map.addLayer({
        id: POLYGON_OUTLINE_LAYER_ID,
        type: "line",
        source: POLYGON_SOURCE_ID,
        paint: {
          "line-color": "#5b6b7a",
          "line-width": [
            "interpolate", ["linear"], ["zoom"],
            POLYGON_PROMINENT_MIN_ZOOM - 2, 0.5,
            POLYGON_PROMINENT_MIN_ZOOM, 1.5,
          ],
          "line-opacity": [
            "interpolate", ["linear"], ["zoom"],
            POLYGON_PROMINENT_MIN_ZOOM - 2, 0.35,
            POLYGON_PROMINENT_MIN_ZOOM, 0.9,
          ],
        },
      });
      // Selected-field emphasis (spec: "selected field highlighted") -
      // an initially-empty filter, updated by setSelectedFieldPolygon().
      map.addLayer({
        id: POLYGON_SELECTED_LAYER_ID,
        type: "line",
        source: POLYGON_SOURCE_ID,
        filter: ["==", ["get", "matched_pprs_slug"], "__none__"],
        paint: {
          "line-color": "#1d5fd6",
          "line-width": 3,
          "line-opacity": 0.95,
        },
      });

      map.on("mouseenter", POLYGON_FILL_LAYER_ID, () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", POLYGON_FILL_LAYER_ID, () => {
        map.getCanvas().style.cursor = "";
      });
      if (onFieldClick) {
        map.on("click", POLYGON_FILL_LAYER_ID, (e) => {
          const props = e.features[0].properties;
          if (!props.matched_pprs_slug) return; // unmatched polygon - no field to open
          // A polygon's own attributes are NSTA determination fields
          // (field_no, determination_status, ...), not production
          // properties. Signal a polygon-originated click by slug only
          // (fromPolygon: true) so the caller resolves full field
          // properties from its own index - the same resolution path
          // already used for a search result with no latest-period
          // marker (clicking either geometry opens the same panel).
          onFieldClick({ slug: props.matched_pprs_slug, fromPolygon: true });
        });
      }
    }

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

// Layer-toggle IDs exported for the "Production bubbles" / "Field
// outlines" controls (spec Workstream 3) - main.js wires two checkboxes
// to these via setLayerVisibility(), independent of each other so either
// can be shown alone or both together; a field is never made
// unreachable by turning one off, since click handlers exist on both.
export const LAYERS = {
  circles: CIRCLE_LAYER_ID,
  polygonFill: POLYGON_FILL_LAYER_ID,
  polygonOutline: POLYGON_OUTLINE_LAYER_ID,
};

export function setLayerVisibility(map, layerId, visible) {
  if (!map.getLayer(layerId)) return;
  map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
}

// Highlights the polygon for `slug` (spec: "selected field highlighted"),
// or clears the highlight when slug is null/undefined/unmatched.
export function setSelectedFieldPolygon(map, slug) {
  if (!map.getLayer(POLYGON_SELECTED_LAYER_ID)) return;
  map.setFilter(POLYGON_SELECTED_LAYER_ID, ["==", ["get", "matched_pprs_slug"], slug || "__none__"]);
}

export function filterByOperator(map, operator) {
  if (!map.getLayer(CIRCLE_LAYER_ID)) return;
  if (!operator) {
    map.setFilter(CIRCLE_LAYER_ID, null);
  } else {
    map.setFilter(CIRCLE_LAYER_ID, ["==", ["get", "operator"], operator]);
  }
}
