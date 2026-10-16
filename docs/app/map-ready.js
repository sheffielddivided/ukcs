// Shared map-readiness helper for the two MapLibre views (Fields map in
// map.js, Licence portfolio in licence.js).
//
// Both views used to add their GeoJSON sources and layers inside
// `map.on("load", ...)`. MapLibre fires `load` only once the style AND the
// initial basemap tiles have loaded, so when the OSM basemap could not be
// fetched - blocked by a network, an ad blocker or a corporate proxy, or
// rate-limited by OSM - the handler never ran and the data layers were
// never added at all. The map still reported `loaded() === true` and
// `isStyleLoaded() === true`, so nothing looked wrong from the outside;
// the style simply contained the `osm` layer and nothing else, and every
// field or licence polygon disappeared along with the basemap it does not
// depend on.
//
// Measured against maplibre-gl 6.8.0 with a basemap that 404s:
//
//   tiles OK   styledata, style.load, sourcedata, sourcedata, styledata, load, idle
//   tiles 404  styledata, style.load, sourcedata, sourcedata, styledata
//
// `style.load` fires either way, and it is the point at which addSource and
// addLayer are legal. That is what this hangs on instead.
//
// The basemap is decoration here. The data is the product, and it must
// survive the basemap failing.

/**
 * Run `fn` once, as soon as the map's style is ready for addSource and
 * addLayer - independently of whether any basemap tile ever arrives.
 *
 * Must be called synchronously after `new Map(...)`, before the style has
 * had a chance to load, which is how both callers use it.
 */
export function onStyleReady(map, fn) {
  let ran = false;
  const run = () => {
    if (ran) return;
    ran = true;
    fn();
  };

  // Already usable (defensive - not the path either caller takes today).
  if (typeof map.isStyleLoaded === "function" && map.isStyleLoaded()) {
    run();
    return;
  }

  map.on("style.load", run);
}
