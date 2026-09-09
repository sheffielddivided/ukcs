// Entry point (spec section 10.3). Loads meta.json and fields.geojson only
// - nothing else is fetched on startup, and nothing here ever calls an
// NSTA or ArcGIS host (the browser only ever reads ./data/*, pre-built by
// etl/build.py).
import { initMap, filterByOperator } from "./map.js";

const DATA_META_URL = "./data/meta.json";
const DATA_FIELDS_URL = "./data/fields.geojson";

class DataLoadError extends Error {}

// Distinguishes network failure, HTTP error and JSON-parse failure rather
// than collapsing them into one message - the same discipline the ETL
// applies to ArcGIS calls (spec section 3), applied here to our own
// static artifacts.
async function fetchJson(url) {
  let response;
  try {
    response = await fetch(url);
  } catch (networkErr) {
    throw new DataLoadError(
      `Network error fetching ${url}: ${networkErr.message} ` +
        "(the request never completed - check the browser is online and " +
        "the file is being served, not opened via file://)"
    );
  }
  if (!response.ok) {
    throw new DataLoadError(
      `HTTP ${response.status} ${response.statusText} fetching ${url}`
    );
  }
  try {
    return await response.json();
  } catch (parseErr) {
    throw new DataLoadError(
      `Response from ${url} was not valid JSON: ${parseErr.message}`
    );
  }
}

function showError(message) {
  const banner = document.getElementById("status-banner");
  banner.textContent = message;
  banner.classList.add("error");
  banner.hidden = false;
}

function formatPeriod(period) {
  // period is "YYYYMM" as a string, per PPRS (spec section 6).
  if (!/^\d{6}$/.test(period)) return period;
  const year = period.slice(0, 4);
  const month = parseInt(period.slice(4, 6), 10);
  const monthNames = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
  ];
  return `${monthNames[month - 1]} ${year} (period ${period})`;
}

function formatBuiltAt(builtAt) {
  const date = new Date(builtAt);
  if (Number.isNaN(date.getTime())) return builtAt;
  return date.toISOString().replace("T", " ").replace(/\.\d+Z$/, " UTC");
}

function renderFooter(meta) {
  const footer = document.getElementById("footer-text");
  footer.textContent =
    `Source: North Sea Transition Authority. ` +
    `Data as at ${formatPeriod(meta.latest_period)}. ` +
    `Site built ${formatBuiltAt(meta.built_at)}.`;
}

function populateOperatorFilter(fieldsGeojson, onChange) {
  const select = document.getElementById("operator-filter");
  const operators = Array.from(
    new Set(
      fieldsGeojson.features
        .map((f) => f.properties.operator)
        .filter((op) => op != null)
    )
  ).sort();

  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = `All operators (${operators.length})`;
  select.appendChild(allOption);

  for (const operator of operators) {
    const option = document.createElement("option");
    option.value = operator;
    option.textContent = operator;
    select.appendChild(option);
  }

  select.addEventListener("change", () => onChange(select.value || null));
}

async function main() {
  let meta;
  let fieldsGeojson;
  try {
    [meta, fieldsGeojson] = await Promise.all([
      fetchJson(DATA_META_URL),
      fetchJson(DATA_FIELDS_URL),
    ]);
  } catch (err) {
    showError(
      "Failed to load data.\n\n" +
        (err instanceof DataLoadError ? err.message : String(err))
    );
    return;
  }

  renderFooter(meta);

  const map = initMap("map", fieldsGeojson);
  populateOperatorFilter(fieldsGeojson, (operator) => {
    filterByOperator(map, operator);
  });
}

main();
