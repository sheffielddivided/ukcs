# UKCS Oil & Gas Production Explorer — Design & Build Specification

**Version:** 2.2
**Date:** September 2026
**Target repo:** `ukcs`
**Deployment:** GitHub Pages (static), GitHub Actions (scheduled data build)
**Intended reader:** Claude Code

---

## 0. Read this first — what changed from v1 and why

Version 1.0 of this specification was written against NSTA endpoints on the host
`data.nstauthority.co.uk`. **That host no longer exists.**

The NSTA migrated its GIS platform from self-hosted ArcGIS Server to ArcGIS Online. The new
platform went live on 22 September 2025, both platforms ran in parallel for eight weeks, and the
old services and Open Data site began decommissioning in the week of 17 November 2025. The
migration also changed dataset names, layer groupings (previously grouped layers are now
individual layers with unique IDs) and attribute field names.

Consequences for this project:

1. Every endpoint URL in specification v1.0 is dead. Do not use any of them.
2. The `Public_WGS84` / `Public_ED50` folder structure no longer exists.
3. Field names in the PPRS schema **may** have changed. They must be discovered at runtime,
   not assumed from v1.0.
4. Any code, comment or README that references `data.nstauthority.co.uk` is wrong.

The v1.0 architecture (PostgreSQL + PostGIS + FastAPI) is also dropped. The target is a
**fully static site on GitHub Pages** with a **scheduled Python build in GitHub Actions**. There
is no server and no database at runtime.

Version 2.1 added the Phase 2 equity specification (section 15), which replaces v1.0's Field
Partners approach with the NSTA Field Equity Shares dataset.

### 0.1 What changed in v2.2

Sections 6, 7 and 15.5 have been corrected against a live run of `etl/discover.py` against the
production ArcGIS Online service (`services-eu1.arcgis.com`, resolved from the item ID at
runtime, per section 4). This is real output, not research — see the per-section notes below and
the committed `etl/schema_snapshot.json` for the raw evidence.

Summary of corrections:

- All PPRS field names in section 6 needed by Phase 1 are confirmed correct as listed in v2.1.
  `PERIODYRMN` is confirmed to be a **string** field, as section 3.2 warned it might not be.
- `supportsPagination` is reported as `null`/`None` by the live layer metadata, not `true` or
  `false`. Code must not gate pagination logic on this flag being truthy — paginate
  unconditionally, as section 8.2 already specifies. The same caution now applies to
  `supportsStatistics`: attempt the `outStatistics` query and treat failure as a hard error,
  rather than skipping it when the flag is falsy or absent.
- The "four reporting unit types" claim is now a **confirmed, observed-over-full-history** fact,
  not an assumption: `Dry Gas Field`, `Offshore Tanker Loader`, `Oil Field Exporting to Pipeline`,
  `Onshore Oil Field`. **These four values do not distinguish production from storage** — see
  section 7.3. Do not build a whitelist keyed on `UNITTYPDES` for that purpose.
- Section 7 is substantially rewritten: the single-period grain investigation in section 7.1
  materially understated the grain problem (251 pairs found vs. 557 across full history), and a
  new section 7.3 documents the production/storage distinction and how it is handled.
- Section 15.5's 2%-unmatched-production tolerance is corrected to apply against production
  across **all fields with production history**, not the latest-period field set.

---

## 1. Purpose

An interactive, static web application for exploring UK Continental Shelf oil and gas production,
built on North Sea Transition Authority (NSTA) open data.

The application shall allow a user to:

1. See UKCS production-reporting locations on a map, sized by production.
2. Filter by commodity, operator and region.
3. Select a field and view its monthly production history.
4. Aggregate production by company and view company history.
5. Compare companies and fields.

The commercially meaningful metric is **equity-attributable production per company**
(section 15). Phase 1 delivers operator production as a stepping stone and an internal
consistency check, not as the intended end product.

Explicitly out of scope: wells, infrastructure, pipelines, daily production.

---

## 2. Non-negotiable constraints

| Constraint | Rationale |
| --- | --- |
| No backend, no database | Deployment is GitHub Pages |
| No API keys of any kind, including map tiles | Keys cannot be kept secret in a static site |
| No build step for the frontend (no bundler, no npm install) | Pages serves the repo directly; keeps the project maintainable |
| The browser never calls NSTA at runtime | Data is pre-built into static JSON artifacts |
| The build must fail loudly on schema drift | Silent truncation or silently missing columns is the main risk in this project |

The third constraint is a deliberate simplification. Use ES modules and CDN-hosted libraries with
pinned versions and SRI hashes where the CDN provides them.

---

## 3. Root cause analysis of the failed prototype

The prototype produced `net::ERR_NAME_NOT_RESOLVED` on:

```
https://data.nstauthority.co.uk/arcgis/rest/services/Public_WGS84/UKCS_PPRS_FieldsPT_WGS84/MapServer/0/query
```

`ERR_NAME_NOT_RESOLVED` is DNS failure — the hostname does not exist. This is not CORS, not a
file:// problem, and not a query-syntax problem. The `TypeError: Failed to fetch` and the
"run the file through a local web server" message in the catch block are both misleading: the
error handler was written for the wrong failure mode and actively sent the developer down a dead
end. **Do not reproduce that error handler.** Distinguish network failure, HTTP error and ArcGIS
application error, and surface the actual message.

Four further defects existed in the prototype that would have caused problems even against a live
endpoint. Fix all of them in the new implementation:

**3.1 Silent truncation.** No pagination anywhere. A single query returns at most
`maxRecordCount` records. Both the latest-period query and the field-history query would have
silently returned partial data with no warning. Always paginate with `resultOffset` /
`resultRecordCount`, and always check `exceededTransferLimit` in the response.

**3.2 Unsafe assumption that `PERIODYRMN` is a string.** The prototype builds
`where=PERIODYRMN='202608'`. If the field is numeric, the quoted literal fails or silently returns
nothing. Inspect the layer schema and quote conditionally on field type.

*Verified live (v2.2): `PERIODYRMN` is `esriFieldTypeString`. The confirmed value does not
change the requirement — quote conditionally at runtime from the live schema, never hardcode the
assumption, since NSTA has already changed this schema once.*

**3.3 Fragile latest-period query.** `returnDistinctValues=true` combined with `orderByFields`
and `resultRecordCount=1` depends on `supportsPagination`, `supportsDistinct` and standardised
queries all being enabled. Use `outStatistics` with a `MAX` on the period field instead — it is
one row, one round trip, and far more widely supported.

*Verified live (v2.2): this was the right call independent of the flags — `supportsPagination`
on the live layer is `null`, which would have made the distinct-values approach undefined
behaviour. `outStatistics` MAX worked cleanly.*

**3.4 Reporting unit treated as field.** The prototype maps one marker per returned record and
sums `OILPRODMBD` across all records to a headline total. PPRS reports per **reporting unit**, and
a field can have more than one — and, as of v2.2, some of those reporting units are storage, not
production. Both the marker layer and the totals may therefore double-count or misclassify
storage as production. See section 7.

---

## 4. Step zero — endpoint discovery (do this before writing any other code)

Do not hardcode service URLs. Resolve them from ArcGIS Online item IDs, which are stable across
service moves.

Known item IDs:

| Dataset | Item ID |
| --- | --- |
| UKCS hydrocarbon field production reports PPRS points (WGS84) | `dd38204275a04618ab7ddd00f87224e3` |
| UKCS hydrocarbon field production reports PPRS polygons (WGS84) | `b51887ab2c8547cfb6807cca0ca5fb88` |

Resolve the service URL with:

```
GET https://www.arcgis.com/sharing/rest/content/items/{itemId}?f=json
```

The `url` property of the response is the service root. Append `/0` for the layer, then `/query`.

*Verified live (v2.2): both item IDs resolve. The points layer resolves to
`https://services-eu1.arcgis.com/OZMfUznmLTnWccBc/arcgis/rest/services/UKCS_hydrocarbon_field_production_reports_PPRS_points_(WGS84)/FeatureServer`.
Do not hardcode this URL either — it is recorded here only as evidence that resolution works, and
services can move again.*

Then fetch the layer metadata:

```
GET {layerUrl}?f=json
```

From this, record and persist into `meta.json`:

- `maxRecordCount` (never assume 2000 — verified live: currently 2000, but read it at runtime)
- `supportsPagination`, `supportsStatistics`, `supportsAdvancedQueries`
- `supportedQueryFormats` (confirm `geoJSON` before using `f=geojson`; verified live: returned as
  the string `"JSON, geoJSON, PBF"` — parse it, don't assume a list shape)
- the full `fields` array — name, type, alias

**Write a discovery script `etl/discover.py` that dumps this to `etl/schema_snapshot.json` and
prints a human-readable field table. Run it and read the output before implementing the ETL.**
The field names in section 6 below have been reconciled against the live schema as of v2.2 — see
section 0.1.

---

## 5. Architecture

```
GitHub Actions (scheduled, weekly)
        │
        ├──►  ArcGIS Online (NSTA PPRS)          [production]
        └──►  nstauthority.co.uk (Excel)         [equity shares]
        │
        ▼
   etl/build.py
        │
        ▼
   docs/data/*.json   (committed to the repo)
        │
        ▼
   GitHub Pages  ──►  docs/index.html + docs/app/*.js
        │
        ▼
      Browser
```

The browser reads only `docs/data/`. No NSTA host is called at runtime.

### 5.1 Repository layout

```
ukcs/
├── .github/workflows/build-data.yml
├── docs/                     ← GitHub Pages root
│   ├── index.html
│   ├── methodology.html
│   ├── app/
│   │   ├── main.js
│   │   ├── map.js
│   │   ├── charts.js
│   │   ├── state.js
│   │   └── format.js
│   ├── styles.css
│   └── data/                 ← generated, committed
│       ├── meta.json
│       ├── fields.geojson
│       ├── operators.json
│       ├── regions.json
│       ├── unmatched.json
│       ├── history/
│       │   ├── index.json
│       │   └── {field-slug}.json
│       └── equity/
│           ├── index.json
│           ├── {company-slug}.json
│           └── by-field/{field-slug}.json
├── etl/
│   ├── discover.py
│   ├── arcgis.py
│   ├── build.py
│   ├── transform.py
│   ├── validate.py
│   ├── equity_fetch.py
│   ├── equity_parse.py
│   ├── equity_join.py
│   ├── validate_equity.py
│   ├── mappings/
│   │   ├── field_aliases.csv
│   │   ├── company_aliases.csv
│   │   └── unit_classification.csv
│   ├── schema_snapshot.json
│   └── requirements.txt
├── tests/
├── ATTRIBUTION.md
└── README.md
```

Configure Pages to serve from `main` / `docs`.

---

## 6. PPRS data model (verified against live schema, v2.2)

The v2.1 candidate field list below has been checked against the live layer
(`etl/schema_snapshot.json`, `services-eu1.arcgis.com`). Every field Phase 1 needs is present
under the same name as v2.1 proposed. The live schema exposes 46 fields in total — far more than
Phase 1 uses (mass/volume/density variants of every stream, plus injection, flare and vent
columns). Those extra columns are recorded as a **Phase 3 reference** in section 16 and are not
used in Phase 1 or Phase 2.

| Field | Meaning | Notes |
| --- | --- | --- |
| `FIELDNAME` | Field name | Join key for aggregation |
| `FIELDAREA` | UKCS region | |
| `LOCATION` | Onshore / offshore flag | |
| `ORGGRPNM` | Operator organisation group | See 6.1 |
| `UNITNAME` | Reporting unit name | The true grain — but not the true production grain; see 7.3 |
| `UNITTYPCOD` / `UNITTYPDES` | Reporting unit type | Confirmed values below. **Does not distinguish production from storage** — see 7.3 |
| `PERIODYRMN` | Reporting period, YYYYMM | Confirmed `esriFieldTypeString`. Still verify the type at runtime from the live schema rather than hardcoding — do not remove the section 3.2 type check just because it's confirmed today |
| `PERIODDATE` | Reporting date | `esriFieldTypeDate`, epoch ms in ArcGIS JSON |
| `OILPRODMBD` | Oil, mb/d | |
| `AGASPROMMS` | Associated gas, MMscf/d | |
| `DGASPROMMS` | Dry gas, MMscf/d | |
| `GCONDMBD` | Condensate, mb/d | |
| `GASPIPVOLM` | Gas to pipeline, MMscf/d | |
| `WATPRODMBD` | Produced water, mb/d | |

Confirmed reporting unit types (`UNITTYPDES`), observed across the **full period history**
(197506–202606, per the live `MIN(PERIODYRMN)`/`MAX(PERIODYRMN)` statistic query - not 197501 as
an earlier draft of this section assumed), not just the latest period:

- `Dry Gas Field`
- `Offshore Tanker Loader`
- `Oil Field Exporting to Pipeline`
- `Onshore Oil Field`

This is now a confirmed, exhaustive-over-history list, not a guess. **It is a commodity/export-route
classification, not a production/storage classification.** A known storage unit
(`ROUGH STORAGE`) and its paired production unit (`ROUGH PRODUCTION`) carry the *identical*
`UNITTYPDES` value (`Dry Gas Field`). Do not attempt to build a storage/production whitelist keyed
on this field — see section 7.3 for what actually works.

Separately, 18 `(FIELDNAME, UNITNAME)` pairs have carried **more than one `UNITTYPDES` value over
their history** (e.g. `ANGUS`, `HARDING`, `STELLA` — export route changed between pipeline and
tanker loading over time). This does not create a grain problem (still one reporting unit, one
row per period) but confirms `UNITTYPDES` is not a stable per-unit attribute over time and must
not be cached or assumed constant anywhere in the ETL.

### 6.1 `ORGGRPNM` is the *current* operator, not the historical one

The operator organisation group in the dataset reflects present-day ownership. Aggregating a 2008
production record under today's operator attributes that production to a company that may not
have operated the field at the time.

Phase 1 must therefore label all operator series *"Operator (as currently recorded by NSTA)"* and
carry a persistent footnote stating that operator attribution is applied retrospectively.

Phase 2 solves this properly for company-level analysis by using dated equity intervals.

---

## 7. The grain problem — reporting unit vs field

**This is the single most important modelling decision in Phase 1. It has been resolved
empirically, twice — first against a single period (7.1), then corrected against full history
(7.2), because the single-period run materially understated the problem. Read 7.2 before
building the aggregation layer; it supersedes 7.1's headline numbers.**

PPRS reports per reporting unit. The NSTA's own PPRS dashboard exposes field region, reporting
unit type and reporting unit as separate, independent filters, which implies the relationship
between field and reporting unit is not guaranteed to be one-to-one.

### 7.1 Single-period investigation (superseded by 7.2 — kept for the record)

Run against the latest period only (`PERIODYRMN='202606'`):

- 250 distinct `FIELDNAME`
- 251 distinct `(FIELDNAME, UNITNAME)` pairs
- 1 field with more than one reporting unit: `ROUGH` (`ROUGH PRODUCTION` / `ROUGH STORAGE`)

**This result is not sufficient to design the aggregation layer.** A single period cannot see
historical unitisation changes, renames, or storage/production splits that predate it. Always run
the grain investigation across full history before relying on its conclusions — see 7.2.

### 7.2 Full-history investigation (authoritative)

Run against the full period range (`where=1=1`), `groupBy FIELDNAME, UNITNAME, UNITTYPDES`:

- **557 distinct `(FIELDNAME, UNITNAME)` pairs** across all history, vs. 251 in the latest period
  alone. Single-period sampling missed 4 of 5 multi-unit fields.
- **5 fields with more than one reporting unit, ever:**

| Field | Units | Periods | Nature |
| --- | --- | --- | --- |
| `ROUGH` | `ROUGH PRODUCTION`, `ROUGH STORAGE` | both current, overlapping | concurrent split: production vs. storage |
| `HATFIELD` | `HATFIELD MOORS`, `HATFIELD MOOR GAS STORAGE INJECTION` | both current, overlapping | concurrent split: production vs. storage |
| `HUMBLY GROVE` | `HUMBLY GROVE`, `HUMBLY GROVE GAS STORAGE` | both current, overlapping | concurrent split: production vs. storage |
| `NORTH SEAN` | `SEAN` (198906–201704), `NORTH SEAN` (201705–202407) | non-overlapping | rename — safe to sum |
| `COLUMBA B/D` | `COLUMBA B` (199608–200006), `COLUMBA BD` (200007–202506) | non-overlapping | rename — safe to sum |

The two rename cases are not a double-counting risk: their periods are strictly non-overlapping,
so summing across the unit's full name history is correct and lossless. They are, however, a
**Phase 2 name-matching risk** — see section 15.5.

The three concurrent splits are a genuine double-counting risk and are handled per 7.3, not by
simple summation.

### 7.3 Production vs. storage — classification mechanism

`ROUGH STORAGE` has reported nonzero values in the production column (`DGASPROMMS`, max observed
~1512 MMscf/d) historically — gas storage redelivery. Summing it into `ROUGH`'s field-level total
would inflate UKCS production by redelivered (not newly produced) gas, and would make the total
swing with seasonal storage withdrawal/injection cycles rather than actual production.
`HATFIELD MOOR GAS STORAGE INJECTION` and `HUMBLY GROVE GAS STORAGE` report `DGASPROMMS = 0` in
every observed row (their volumes are reported under `GASINJVOL` instead) — but they are excluded
on principle, as storage facilities, not because their current numbers happen to be zero.

As established in section 6, `UNITTYPDES` cannot be used to detect this — storage and production
units of the same facility share an identical `UNITTYPDES`. There is no dedicated storage flag
anywhere in the 46-field schema. The only reliable signal is the `UNITNAME` text itself.

Mechanism (exceptions-only, not an allow-list of every unit):

- `etl/mappings/unit_classification.csv` — columns `field_name,unit_name,classification,note`,
  `classification` ∈ `{production, storage}`. **Only exceptions are listed.** Seeded with the
  three known storage units (`ROUGH STORAGE`, `HATFIELD MOOR GAS STORAGE INJECTION`,
  `HUMBLY GROVE GAS STORAGE`).
- Any `(FIELDNAME, UNITNAME)` not listed in the file **defaults to `production`.** A new ordinary
  field or unit added by NSTA passes through without any build change — this is routine, not
  exceptional, and must not turn the build red.
- **Tripwire, not classifier:** at build time, scan every `UNITNAME` in the live schema for
  suspicious tokens (`STORAGE`, `INJECTION`, and any further tokens judged appropriate from the
  observed unit-name corpus). Any unit matching a token that is **not already classified** in
  `unit_classification.csv` **fails the build**, naming the unit. The tripwire only flags for
  human review — it must never auto-assign a classification itself. A token match against a unit
  already listed in the CSV is not a failure.
- A full scan of all 557 `(FIELDNAME, UNITNAME)` pairs (not just the 5 multi-unit fields) for
  these tokens found no storage-only field — i.e. no field where the *only* reporting unit is
  storage with no production counterpart. If one is added later, the tripwire above will catch it
  (a field whose sole unit matches a suspicious token and isn't classified fails the build), and
  it should be added to `unit_classification.csv` and reviewed for whether the field should be
  excluded from the map/totals entirely rather than merely having a unit excluded.
- Rows classified `storage` are excluded from the production sum but retained and surfaced
  separately in the field panel, explicitly labelled as storage.

### 7.4 Rules regardless of outcome

- The canonical grain of the production table is `(field, reporting_unit, period)`.
- Field-level production series are produced by explicit summation over reporting units
  classified `production` (7.3), never by assuming uniqueness and never including units
  classified `storage`.
- The map plots **one marker per field**, at the centroid of its reporting-unit points, with
  summed *production* (not storage) volumes. Not one marker per record.
- Headline totals are computed after aggregation to field level, excluding storage units.
- If a field has multiple reporting units — production, storage, or a rename history — expose
  them in the field panel as a breakdown, with storage units clearly labelled as such.

Field is the join grain for equity. Equity shares are held at field level, not reporting-unit
level, so the aggregation in 7.3–7.4 must be correct before Phase 2 can be trusted. Rough's
equity is equity in the field, which includes the storage facility — section 15 notes this as a
special case for the equity join, since equity in Rough-as-storage is not equity in production.

---

## 8. ETL specification (`etl/build.py`)

### 8.1 Pipeline

```
resolve service URL from item ID
        ↓
fetch + snapshot layer schema
        ↓
validate schema against expectations   → fail build on drift
        ↓
paginate full PPRS history (attributes only, no geometry)
        ↓
paginate latest-period records (with geometry)
        ↓
classify reporting units (production/storage), tripwire unclassified matches
        ↓
normalise → field grain (production units only)
        ↓
[Phase 2] fetch + parse equity shares → interval join
        ↓
build artifacts
        ↓
validate artifacts                     → fail build on regression
        ↓
write docs/data/
```

### 8.2 Pagination (`etl/arcgis.py`)

Implement a single `query_all()` helper used everywhere:

- page size = `min(maxRecordCount from layer metadata, 2000)`
- loop on `resultOffset`, stop when a page returns fewer records than the page size **and**
  `exceededTransferLimit` is falsy
- always send `orderByFields` with a stable, unique-ish ordering (e.g. the OBJECTID field) —
  ArcGIS pagination is undefined without deterministic ordering and will otherwise duplicate or
  drop rows
- do not gate pagination on `supportsPagination` being `true` — the live layer reports this flag
  as `null`; paginate unconditionally regardless of its value (verified live, v2.2)
- retry on 5xx and transient network errors with exponential backoff, max 5 attempts
- hard cap total records and raise if exceeded, so a runaway loop fails the build rather than the
  Actions minutes budget

If the full history fetch is too large for one pass, chunk by reporting year using a `where`
clause on the period field.

### 8.3 Validation (`etl/validate.py`)

Fail the build if any of the following hold:

- an expected field is missing from the layer schema, or its type changed
- the record count for the latest period differs from the previous build by more than 20%
- the latest period is older than the previous build's latest period
- any field-level oil or gas value is negative
- the number of distinct fields drops by more than 10% versus the previous build
- `meta.json` from the previous build cannot be read (first run excepted)
- a `UNITNAME` matches a storage/injection tripwire token (section 7.3) and is not already present
  in `etl/mappings/unit_classification.csv`

On first run (no previous `meta.json`), all delta-based rules above are skipped; only the
absolute rules (missing/changed schema fields, negative values, unclassified storage-like units)
apply.

Validation failure must exit non-zero. Do **not** write partial artifacts.

### 8.4 Units

Preserve NSTA's native units end to end: mb/d for liquids, MMscf/d for gas. Perform no conversion
in the ETL.

A derived `boe_d` may be shown in the UI only if it is computed in the frontend, the conversion
factor is a named constant in one place, and the UI displays the factor used. Given the intended
audience, an undocumented boe conversion is worse than no boe figure at all.

---

## 9. Data artifacts (Phase 1)

### 9.1 `meta.json`

```json
{
  "built_at": "2026-09-09T04:00:00Z",
  "sources": {
    "production": {
      "publisher": "North Sea Transition Authority",
      "dataset": "UKCS hydrocarbon field production reports PPRS points (WGS84)",
      "item_id": "dd38204275a04618ab7ddd00f87224e3",
      "service_url": "<resolved at build time>",
      "layer_max_record_count": 0
    },
    "equity": {
      "dataset": "NSTA Field Equity Shares",
      "page_url": "https://www.nstauthority.co.uk/data-and-insights/data/themes/fields/",
      "resolved_file_url": "<resolved at build time>",
      "file_sha256": "...",
      "last_modified": "..."
    }
  },
  "latest_period": "202606",
  "earliest_period": "197506",
  "field_count": 0,
  "field_count_raw": 0,
  "reporting_unit_count": 0,
  "storage_unit_count": 0,
  "company_count": 0,
  "record_count": 0,
  "schema_hash": "sha256:...",
  "notes": []
}
```

`schema_hash` is a hash of the sorted `(name, type)` field list. Changing it is how schema drift
is detected on the next run. `storage_unit_count` is new in v2.2 — the count of reporting units
classified `storage` per section 7.3, kept visible in `meta.json` so a change in that count (a new
storage unit appearing) is auditable in the same place as everything else. `field_count_raw` is
also new in v2.2 — the distinct-`FIELDNAME` count before storage exclusion, so a difference
between it and `field_count` is visible as an explained reduction (fields with production-unit
data only) rather than looking like unexplained data loss.

`notes` must always carry a standing entry stating whether the latest period's summed oil and gas
totals have been reconciled against an NSTA-published aggregate figure for that period, and if
not, that none was locatable. This is a build-time fact about provenance, not a one-off remark —
it must survive in the committed artifact (and from there onto `methodology.html`), not live only
in a build log or a chat transcript. If a reconciliation source is added later, this note changes
to say so and names the source; until then it must say plainly that the total is unverified
against NSTA, so nobody downstream mistakes silence for confirmation.

### 9.2 `fields.geojson`

One Point feature per field, latest period only, **production units only** (section 7.3/7.4).

```json
{
  "type": "Feature",
  "geometry": { "type": "Point", "coordinates": [1.35, 57.55] },
  "properties": {
    "slug": "buzzard",
    "field": "BUZZARD",
    "region": "Central North Sea",
    "location": "Offshore",
    "operator": "...",
    "unit_count": 1,
    "storage_unit_count": 0,
    "period": "202606",
    "oil_mbd": 0.0,
    "assoc_gas_mmscfd": 0.0,
    "dry_gas_mmscfd": 0.0,
    "condensate_mbd": 0.0,
    "water_mbd": 0.0
  }
}
```

Round values to 3 decimals. Longitude must be signed correctly — most UKCS fields are east of
Greenwich (positive), west of Shetland fields are negative. Assert all coordinates fall within a
UKCS bounding box of roughly lon −14 to 5, lat 48 to 63, and fail the build otherwise.

### 9.3 `history/{slug}.json`

```json
{
  "slug": "buzzard",
  "field": "BUZZARD",
  "operator": "...",
  "units": [{ "name": "...", "type": "...", "classification": "production" }],
  "storage_units": [{ "name": "...", "type": "..." }],
  "series": [
    { "period": "202001", "oil_mbd": 0.0, "dry_gas_mmscfd": 0.0,
      "assoc_gas_mmscfd": 0.0, "condensate_mbd": 0.0, "water_mbd": 0.0 }
  ]
}
```

`units` lists the reporting units included in `series` (production only). `storage_units`, if
any, lists units excluded from `series` per section 7.3, so the field panel can surface them
separately without them ever contributing to the production numbers.

`history/index.json` maps slug → `{ field, operator, region, first_period, last_period }` and is
the source for search and autocomplete.

### 9.4 `operators.json`

Operator-level aggregation, latest values and series, with the `generated_from` field set to
`"current operator of record"`. If it exceeds roughly 2 MB, split per-operator series into
`operators/{slug}.json`.

---

## 10. Frontend

### 10.1 Stack

- Vanilla ES modules, no framework, no build step
- **MapLibre GL JS** (pinned version, CDN) with an OSM raster source — no API key
- **ECharts** (pinned version, CDN) for charts
- CSS in a single `styles.css`, no framework

MapLibre rather than Leaflet because vector-tile field polygons are a likely later requirement.
Respect the OSM tile usage policy: set a proper attribution control and do not preload tiles.

### 10.2 Views

**View A — Map (default).** Full-bleed map, left sidebar of controls. Markers sized by
`sqrt(value)`, colour-coded by commodity. Controls: commodity toggle, company/operator select,
region select, period select, field search.

**View B — Field panel.** Field name, operator, region, reporting unit breakdown (production and
storage units separately labelled, per section 7.3/9.3), latest oil/gas/condensate/water, monthly
history chart with oil and gas on **separate y-axes**. Never plot mb/d and MMscf/d on a shared
axis. Phase 2 adds a partner-history table.

**View C — Company.** Phase 1: operator production. Phase 2: equity-attributable production as
default, operator production as a labelled secondary toggle.

**View D — Comparison.** Up to six companies or fields overlaid. Oil and gas as separate charts.

### 10.3 Loading strategy

On startup load `meta.json`, `fields.geojson` and `history/index.json` only. Load
`history/{slug}.json` and `equity/{slug}.json` lazily on selection and cache in memory.

### 10.4 Provenance in the UI

Persistent footer:

> Source: North Sea Transition Authority. Data as at {latest_period}. Site built {built_at}.

The distinction between *data period* and *build time* must be visible — they are not the same
thing, and conflating them would imply the data is more current than it is.

---

## 11. GitHub Actions (`.github/workflows/build-data.yml`)

- Trigger: `schedule` weekly (PPRS is monthly; equity is weekly), plus `workflow_dispatch`.
- Steps: checkout → setup Python 3.12 → `pip install -r etl/requirements.txt` →
  `python etl/build.py` → commit `docs/data/` only if content changed.
- Use `git diff --quiet` to avoid empty commits.
- Commit message: `data: NSTA refresh, period {latest_period}`.
- `permissions: contents: write`. Concurrency group to prevent overlapping runs.
- Upload the raw equity workbook as a build artifact, retention 90 days.
- On validation failure: exit non-zero, do not commit, let the workflow go red.

---

## 12. Licensing and attribution

**Do not state a licence in the application until it has been confirmed.**

The data.gov.uk entries for the PPRS points dataset and Field Partners show no licence set or
"Custom License". Specification v1.0 asserted Open Government Licence v3.0; that is not supported
by the catalogue entries. NSTA's own map products instead reference an **"OGA Open User Licence"**,
which is a distinct, named instrument.

Therefore:

- `ATTRIBUTION.md` states source, dataset names, item IDs, and that licence terms are to be
  confirmed with the NSTA GIS team (`gis@nstauthority.co.uk`).
- The UI attributes the NSTA and links to the Open Data site.
- The UI shall **not** display an OGL badge or claim any specific licence.
- Read the OGA Open User Licence terms before any public publication.

---

## 13. Phase 1 build order

1. `etl/discover.py` — resolve item → service URL, dump schema, run the grain investigation of
   section 7.1/7.2. **Stop and report the findings.** Correct sections 6 and 7 from actual output.
   — **Done, v2.2. See section 0.1 and the committed `etl/schema_snapshot.json`.**
2. `etl/arcgis.py` — paginated, retrying query client. Unit test pagination against a fixture.
3. `etl/build.py` + `transform.py` — `meta.json` and `fields.geojson`, latest period only.
   Verify the bounding-box assertion passes. Apply the production/storage classification from
   section 7.3.
4. Minimal `docs/index.html` — map, markers, tooltips, operator filter. Deploy and confirm.
5. Extend ETL to full history and per-field history files.
6. Field panel and history charts.
7. `operators.json` and the company view.
8. `etl/validate.py` and the Actions workflow.

Ship Phase 1 after step 8, then proceed to Phase 2.

---

## 14. Acceptance criteria for Phase 1

- [ ] No reference to `data.nstauthority.co.uk` anywhere in the repo.
- [ ] No hardcoded ArcGIS service URL; all resolved from item ID at build time.
- [ ] `etl/build.py` runs clean from a fresh clone with only `etl/requirements.txt` installed.
- [ ] Pagination verified: `meta.json` record count matches an independent count query.
- [ ] Schema drift causes a non-zero exit, demonstrated by a test with a mutated snapshot.
- [ ] All coordinates pass the UKCS bounding-box assertion.
- [ ] Field-level totals equal the sum of their **production** reporting units (storage units
      excluded), asserted in a test — including a test case covering `ROUGH`.
- [ ] A reporting unit whose name matches a storage/injection tripwire token and is not in
      `etl/mappings/unit_classification.csv` fails the build, demonstrated by a test.
- [ ] Map loads in under three seconds on a cold cache.
- [ ] Zero runtime network calls to any NSTA or ArcGIS host from the browser.
- [ ] Every operator chart displays the retrospective-attribution caveat.
- [ ] Footer shows data period and build time as distinct values.
- [ ] No licence claim is made anywhere in the UI or README.

---

## 15. Phase 2 — equity-attributable production per company

This is the commercially interesting metric. Operator production, which attributes 100% of a
field to whichever company operates it, is of limited analytical value. Phase 2 replaces it as
the headline company figure.

### 15.1 Source selection

**Primary source: NSTA "Field Equity Shares".**

The NSTA publishes a dataset described as *current and historical field equity shares*, updated
weekly, on its Fields data theme page. This is the correct source. It supersedes the Field
Partners dataset proposed in specification v1.0.

Field Partners is a **snapshot** of present-day partners in producing fields. Multiplying today's
equity by historical production reproduces exactly the retrospective-attribution error described
in section 6.1, but worse — equity changes hands more frequently than operatorship. Field
Partners must not be used for time series. It may be used only as a cross-check on the latest
period.

An archived earlier release of the Field Equity Shares workbook (covering 2014–2020) confirms the
required structure: each row carries an interest percentage, a **start date** and an **end date**.
Records run back to the late 1960s, and transactions are visible in the data — for example an
84.11% interest running from February 1978 to October 2016, and groups of partner rows all
terminating on a common date as an interest changes hands.

This validity-period structure is what makes a historically correct equity series possible.

**Supporting source: licence blocks history**, for company name history. The UKCS offshore
petroleum licence blocks history layer exposes *licensee historical names* and *operator
historical names*. Use it to seed the alias table in section 15.5. Without it, Chrysaor, Premier,
Spirit and Harbour appear as four unrelated companies in the same series.

**Cross-check only: Sub Areas by Equity Group Holder**, which carries *equity group holder* and
*equity* attributes. This is licence sub-area geography, not field geography, and carries no
history. Do not join it to production.

**Note (v2.2):** `ROUGH` is a field with a genuine, current production/storage split (section
7.3). Rough's field equity is equity in the field as a whole, which includes the storage
facility. Equity-attributable *production* for Rough should be computed only against
`ROUGH PRODUCTION` volumes, consistent with section 7.4 — but this means Rough's E1 check (100%
interest coverage against field production) is checking coverage of a number that already
excludes storage. Document this explicitly in `methodology.html` as a known special case: equity
interest in Rough is not proportionally split between its production and storage roles by
anything in this dataset, and the equity-attributable production figure for Rough reflects
interest in the whole field applied to the production-only volume.

### 15.2 Acquisition — this source is more fragile than the ArcGIS services

Field Equity Shares is an Excel workbook published on a web page, not a REST endpoint. The
archived file's URL embeds a date, which implies the filename changes on republication.

Requirements for `etl/equity_fetch.py`:

- Scrape the NSTA Fields data theme page for the Field Equity Shares link. Do **not** hardcode
  the file URL.
- If no matching link is found, **fail the build** with an explicit message naming the page.
  Never fall back to a cached copy silently.
- Persist the resolved URL, HTTP `Last-Modified`, and a SHA-256 of the file bytes into
  `meta.json` under `sources.equity`.
- Keep the raw workbook as an Actions build artifact for at least 90 days, so a disputed number
  can be traced to the exact input file.
- If the file hash is unchanged from the previous build, skip re-parsing and reuse the previous
  equity artifacts.

Verify the current workbook's sheet and column names before writing the parser. The 2014–2020
archive is a structural guide, not a schema contract.

### 15.3 The interval join

Equity is a set of validity intervals per (field, company). Production is monthly. The join must
be an interval containment test, not an equality join.

Canonical definition:

```
equity_production(company, month)
  = Σ over fields:
        field_production(field, month)
      × interest(company, field, month)

where interest(company, field, month) = the interest_pct of the row for which
      start_date <= month_start  AND  (end_date IS NULL OR end_date > month_start)
```

`field_production(field, month)` is the production-only aggregate from section 7.4 (storage
units excluded).

Implementation rules:

- Normalise each month to its **first day** (`month_start`) and test containment against that
  single instant. Do not test against month-end, and do not test overlap of the month with the
  interval — a mid-month transaction would otherwise match two rows and double-count.
- Treat intervals as **half-open `[start, end)`**. A row ending 2016-10-13 does not contribute to
  October 2016 under a month-start test; the successor row starting the same date does not
  contribute either. This is deliberate and consistent. Document it on the methodology page.
- An empty end date means open-ended. Represent as `None`, never as a sentinel date.
- **Sentinel start dates:** the archive contains rows dated `1900-01-01`, which is a placeholder
  for "unknown / since inception", not a real date. Detect dates before 1960, map them to a
  `start_is_unknown` flag, and treat the interval as open at the start rather than literally
  beginning in 1900.
- Build per-field sorted interval structures and resolve each month by binary search. A naive
  nested loop over ~60 years × ~400 fields × ~10 partners will be slow enough to matter in
  Actions.

### 15.4 Validation rules — all build-breaking

Implement in `etl/validate_equity.py`. Any failure exits non-zero and writes no artifacts.

| # | Rule | Tolerance |
| --- | --- | --- |
| E1 | For every (field, month) with production > 0, resolved interests sum to 100% | ±0.5 pp |
| E2 | No interest is negative | exact |
| E3 | No interest exceeds 100% | exact |
| E4 | No overlapping intervals for the same (field, company) | exact |
| E5 | No coverage gaps for a field between its first and last producing month | exact |
| E6 | Every producing field in PPRS resolves to at least one equity row | see 15.5 |
| E7 | `start_date < end_date` on every closed interval | exact |
| E8 | Σ equity production across all companies equals Σ field production for that month | ±0.5% |
| E9 | Company count does not drop by more than 10% versus previous build | 10% |

E1 and E8 are the load-bearing checks. E1 catches parse and interval errors at source; E8 catches
them at the aggregate. Both must pass.

The archived file contains rows with an interest of `0`. Investigate before deciding how to treat
them: plausibly carried interests, relinquished positions, or nulled records. If they are
legitimate zero-interest partner rows, exclude them from the E1 sum but retain them as partner
records. Do not drop them without establishing what they represent.

### 15.5 Name reconciliation — the real integration risk

Two distinct problems. Handle them separately.

**Field name matching (PPRS ↔ equity workbook).** Deterministic matching only: exact match, then
match on a normalised key (uppercase, strip punctuation, collapse whitespace). **No fuzzy
matching.** A silent mismatch produces a wrong number that looks right, which is the worst
possible failure mode for this application.

**Field universe for matching and for the tolerance check below is every field with production
history, not just the latest-period field set.** The latest period contains 250 fields; full
history contains a substantially larger set of fields that have produced at some point since 1975
but are not currently producing. The equity join must cover all of them, and the 2% tolerance
below is measured against total historical production, not latest-period production only —
matching only against currently-producing fields would silently exclude an unknown amount of
historical volume from the coverage check.

**Rename cases need both names checked (v2.2).** Section 7.2 found two fields whose reporting
unit was renamed partway through history with non-overlapping periods: `SEAN` → `NORTH SEAN`
(transition 201704/201705) and `COLUMBA B` → `COLUMBA BD` (transition 200006/200007). If the
equity workbook uses the pre-rename name for the pre-rename period (plausible, since equity
records run back further than some of these renames), a name matcher keyed only on the current
`FIELDNAME` will silently fail to match the earlier interval. Check both the current and
historical name for every renamed field found in section 7.2 before finalising the alias file
below, and add explicit rows to `field_aliases.csv` for both directions if the workbook does use
the old names.

Unmatched fields go to `etl/mappings/field_aliases.csv`, hand-maintained and committed, with
columns `pprs_field_name,equity_field_name,note,reviewed_by,reviewed_on`. The ETL prints every
unmatched field as a build warning and writes them to `docs/data/unmatched.json`. **If unmatched
fields account for more than 2% of total production across all fields with production history,
fail the build.**

**Company name reconciliation.** Maintain `etl/mappings/company_aliases.csv` with columns
`source_name,canonical_name,parent_group,valid_from,valid_to,source`. Seed from the licence blocks
history historical-name attributes, then curate by hand.

Decide and document one rule: does a series follow the **legal entity as recorded at the time**,
or the **corporate group as it exists today**? Both are defensible; mixing them is not. Recommended:
present the legal entity as recorded at the time, with an optional "roll up to current parent"
toggle. When the toggle is on, the UI must say so prominently.

### 15.6 Artifacts

`equity/{company-slug}.json`:

```json
{
  "slug": "aker-bp",
  "name": "...",
  "canonical_rule": "legal entity as recorded at the time",
  "series": [
    { "period": "202606", "oil_mbd": 0.0, "dry_gas_mmscfd": 0.0,
      "field_count": 0, "coverage_pct": 100.0 }
  ],
  "fields": [
    { "slug": "buzzard", "interest_pct": 0.0, "from": "201610", "to": null }
  ]
}
```

`equity/index.json` maps company slug → name, first/last period, field count, latest values.
`equity/by-field/{field-slug}.json` holds the partner history for the field panel.

`coverage_pct` is the share of that month's underlying field production for which equity resolved
cleanly. **It must be surfaced in the UI.** A month at 87% coverage is not comparable to one at
100%, and hiding that would be exactly the kind of quiet imprecision this project exists to avoid.

### 15.7 UI changes

- Equity-attributable production becomes the **default** company metric.
- Operator production remains available as a clearly labelled secondary toggle.
- The two must never share an axis, a total, or a comparison chart.
- Every equity chart carries the date basis, and a visible coverage indicator wherever
  `coverage_pct` < 99.5 in any displayed month.
- The field panel gains a partner-history table: company, interest, from, to.
- `methodology.html` documents the interval convention, the half-open boundary rule, sentinel-date
  handling, the entity-vs-group choice, the production/storage classification mechanism (section
  7.3) and Rough's special case (section 15.1), and links to `unmatched.json`.

Label the metric **"Equity-attributable production (NSTA field equity shares)"**. Not "net
production", not "working interest production", not "entitlement production" — those terms carry
accounting meanings this figure does not satisfy. It is a gross equity share of wellhead volumes,
before royalty, tax and any entitlement adjustment, and the methodology page must say so plainly.

### 15.8 Phase 2 build order

1. `etl/equity_fetch.py` — locate and download the workbook, hash it, report sheet and column
   structure. **Stop and report before parsing.**
2. `etl/equity_parse.py` — normalised interval table; report row counts, date ranges, and the 0%
   row question. **Stop and report.**
3. Field name matching; produce the unmatched list; build the alias file. Check both pre- and
   post-rename names for `SEAN`/`NORTH SEAN` and `COLUMBA B`/`COLUMBA BD` per section 15.5.
4. `etl/equity_join.py` — interval join, latest period only; run E1 and E8. **Stop and report.**
5. Full history join; all validation rules E1–E9.
6. Company alias reconciliation.
7. Artifacts, UI, methodology page.

**Do not proceed past step 4 until E1 and E8 pass on the latest period.**

### 15.9 Acceptance criteria for Phase 2

- [ ] Equity file URL is resolved by scraping, never hardcoded; missing link fails the build.
- [ ] File SHA-256 and resolved URL recorded in `meta.json`.
- [ ] Interval join uses half-open `[start, end)` against month-start, verified by a unit test
      covering a mid-month transaction.
- [ ] Sentinel dates before 1960 are flagged, not treated literally.
- [ ] E1 passes for every producing field-month.
- [ ] E8 passes for every month in the series.
- [ ] Unmatched fields represent less than 2% of production across all fields with production
      history (not latest-period production only).
- [ ] `coverage_pct` is present on every equity data point and rendered in the UI.
- [ ] Operator and equity production never appear on the same axis or in the same total.
- [ ] The metric is labelled "Equity-attributable production", never "net" or "entitlement".
- [ ] `methodology.html` documents every convention listed in 15.7, including the production/
      storage classification and Rough's special case.
- [ ] Both pre- and post-rename names are checked for `SEAN`/`NORTH SEAN` and
      `COLUMBA B`/`COLUMBA BD` before the alias file is finalised.

---

## 16. Phase 3 — deferred

Field determination polygons and zoom-dependent point-to-polygon switching; wells; infrastructure
and pipelines; hubs; daily production data; production rankings and CAGR.

Note for later: the PPRS polygon layer is reporting-unit shaped and NSTA warns it is slow to
download. For formal field outlines use the separate "UKCS petroleum field determinations (WGS84)"
dataset instead.

**Also deferred to Phase 3 (v2.2):** the 32 non-Phase-1 attribute columns on the PPRS points layer
not listed in section 6 — mass, volume and density variants of oil/gas/condensate/water, plus
`GASINJCV`, `GASINJVOL`, `GASPIPCV`, `GASPIPVOL`, `GASPIPDENS`, `GASFLARVOL`, `GASFLARDEN`,
`GASFLARNH`, `GASVENTVOL`, `GASVENTDEN`, `GASVENTNH`, `INJWATVOL`, `INJWATMBD`, `REINJWATVO`. These
are available on the live layer and were catalogued during discovery but are out of scope for
Phase 1 and Phase 2, which use only the mb/d and MMscf/d production fields listed in section 6.
