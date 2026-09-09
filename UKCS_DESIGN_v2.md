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

### 0.2 What changed in v2.3

Sections 15.1, 15.2 and 15.5 have been corrected against live discovery and field-matching runs
for Phase 2 milestones 1 and 2 (`etl/equity_fetch.py`, `etl/equity_parse.py`,
`etl/equity_match.py`). See `etl/equity_schema_report.md` and
`etl/equity_field_matching_report.md` for the full evidence.

Summary of corrections:

- **No dataset titled "Field Equity Shares" exists.** Section 15.1's assumption of two separate
  NSTA datasets (a time-series "Field Equity Shares" source and a snapshot-only "Field Partners"
  source) was wrong. There is only one live dataset, an ArcGIS item titled **"Field Partners"**,
  which the NSTA Fields page describes as *"Current and historical field equity shares"*. Its
  content is full interval history back to 1968, not a snapshot. Section 15.1 no longer
  characterises this workbook as a present-day snapshot, and records source identity using both
  the item title and the page description rather than assuming one name is authoritative.
- **Acquisition is a two-hop resolution, not a single-page scrape** (section 15.2): NSTA page ->
  ArcGIS Hub search page (client-rendered, no scrapeable link) -> ArcGIS Online search API scoped
  to org `OZMfUznmLTnWccBc` -> resolved item -> direct `.xlsx` URL on Azure Blob Storage.
- **`COLUMBA BD` corrected to `COLUMBA B/D`** (with a slash) — the actual current, post-merge PPRS
  field name (section 15.5).
- **Both rename cases (`SEAN`/`NORTH SEAN`, `COLUMBA B`/`COLUMBA B/D`) are checked and resolved**:
  neither needs an alias row. The PPRS field universe used for matching is already
  rename-consolidated, and the equity workbook independently uses the current name for each
  field's full history.
- **No sentinel (`1900-01-01`-style) start dates exist in the live workbook**, contradicting the
  assumption drawn from the archived 2014-2020 file. Detection logic is retained defensively.
- **Two new data anomalies found, not yet resolved**: 4 rows with future start dates (2030, 2050)
  and 838 rows with a zero-duration interval (`start_date == end_date`) — far more than the single
  example noted during milestone 1's spot-check. Both are carried forward for the interval-join
  step (15.8 step 4); section 15.4's proposed `E7` rule (`start_date < end_date`, strict) would
  fail all 838 as currently worded.
- Field-name matching (milestone 2) achieved 500/552 exact matches (90.6% field-count coverage)
  and **100% production-weighted coverage** on the latest period across all four streams (oil, dry
  gas, associated gas, condensate) — comfortably inside the 2% unmatched-production threshold. See
  `etl/equity_field_matching_report.md` for the full unmatched-field lists and the structural
  (non-naming) mismatches investigated and left unmatched rather than guessed at.

### 0.3 What changed in v2.4

Sections 15.3 and 15.4 have been corrected against a dedicated interval-semantics investigation
(`etl/equity_interval_diagnostics.py`, `etl/equity_interval_diagnostics_report.md`, 2026-09-09),
run before writing the real interval join. **Interval-treatment rules in these two sections are
marked PENDING, not settled**, until the real join (build order step 4) is written against the
corrections below.

Summary of corrections:

- **838 zero-duration rows** (`start_date == end_date`), not "possibly a few noticed during
  milestone 1's spot-check" — 10.9% of all rows. Classified by relationship to neighbouring rows:
  689 `boundary_duplicate`, 91 `boundary_transition`, 42 `termination_marker`, 16
  `standalone_snapshot`. None are discarded; all remain source records. Under the existing
  half-open containment test, they are already mathematically inert (a `[d, d)` interval matches
  no month) — no special-casing is needed to exclude them from any sum.
- **`E7` (`start_date < end_date`, strict, build-breaking) cannot ship as worded** — corrected to
  accept `start_date <= end_date`, treating zero-duration rows as non-interest-bearing event
  records rather than errors.
- **One genuine overlapping-interval error found and confirmed real, not hypothetical**:
  `ROCHELLE`, August 2011, two companies' rows overlap by one month, producing a 200% field-month
  sum. This is exactly what `E4` (kept, scoped to same-(field, company) overlaps) must catch.
- **`Equity Share Time Period` is proven fully derived from Start/End Date** at year granularity
  (zero exceptions across 7,683 rows) — confirmed to carry no independent information and to never
  conflict with the dates. Policy C (prefer the label on conflict) is therefore numerically
  identical to the literal half-open test on this workbook; retain the label as source metadata
  only.
- **4 future-dated rows** (`ALVHEIM`, `STATFJORD(CROSS BORDER)`, `MURLACH [pt of MARNOCK-SKUA]`
  ×2) each leave their field with zero current equity coverage, correctly and without
  special-casing, under the existing containment test — no repair or quarantine needed. `E5` is
  corrected to not treat this as a coverage-gap failure.
- **Zero-interest rows (241, 218 with Operator Flag='Y') are confirmed, not just anticipated**:
  86% of the Operator-Flag='Y' zero-interest rows coincide with a different company holding the
  real equity for the same period, confirming Operator Flag records operatorship independently of
  economic interest. The existing default (retain as source records, exclude from the `E1` sum) is
  confirmed correct by this evidence, not merely assumed.
- **No sentinel (`1900-01-01`-style) dates exist** in the live 7,683-row workbook — the earliest
  observed start date is 1968-08-01. Detection logic is retained defensively; it currently never
  fires.

### 0.4 What changed in v2.5

Sections 15.3 and 15.4 are updated from PENDING to **APPROVED for the latest-period checkpoint**.
`etl/equity_join.py` implements the policy decisions v2.4 proposed, resolves active equity
interests for the single latest PPRS period (currently 202606), and calculates
equity-attributable production at field × month × legal-entity grain for that period only. See
`etl/equity_latest_period_join_report.md` for the full run.

Summary:

- Of 250 latest-period producing PPRS fields: **249 fully resolved**, 1 `future_only`
  (`MURLACH [pt of MARNOCK-SKUA]`, whose only equity rows start 2050-01-04), 0 unmatched, 0
  quarantined, 0 unresolved_gap.
- E1 (interest conservation): 249/249 resolved fields pass, 0 fail.
- E4 (overlap validation): 0 quarantined field-months in the latest period. `ROCHELLE`'s known
  2011-08 overlap is historical and does not recur; a committed regression fixture reproduces it
  exactly and confirms the resolver quarantines rather than repairs it.
- E5 (coverage validation): categories reported separately (resolved / unmatched / future_only /
  quarantined / unresolved_gap), never collapsed into one count.
- E7 (interval validity): 0 rows with `start_date > end_date`, checked across the full workbook
  (not period-scoped, since this is a structural property of the source).
- E8 (production conservation) by stream: dry gas 100.0%, condensate 100.0%, associated gas
  99.458%, oil 96.928% coverage — the oil/gas shortfall is entirely `MURLACH`'s real 202606
  production, excluded because its only equity rows are future-dated.
- The latest-period company summary uses legal-entity names exactly as recorded in the workbook —
  no parent-group rollup, no company alias reconciliation (both remain out of scope; spec section
  15.8 steps 6-7).
- This is a **diagnostic checkpoint only**: no `docs/data/equity/*` artifacts were created, no
  UI was changed, and `etl/build.py` was not modified. The full historical join (~60 years ×
  ~550 fields) remains future work.

### 0.5 What changed in v2.6

`etl/equity_join_historical.py` runs the full historical interval-join diagnostic (spec section
15.8 step 5) across all 133,608 PPRS field-months and 7,683 equity rows. See section 15.10 for
the full write-up and `etl/equity_historical_join_report.md` /
`etl/equity_historical_anomalies.json` for the complete run. Still a **diagnostic checkpoint
only** - not integrated into `etl/build.py`, no `docs/data/equity/*` artifacts, no company alias
or parent-group reconciliation, no UI changes.

Headline finding, stated plainly because the evidence requires it: **full-history
production-weighted coverage is low (oil 33.0%, dry gas 56.1%, associated gas 52.1%, condensate
62.3%) and the historical model is not ready for publication or for integration into the
unattended build.** This is not a defect in the join logic - annual coverage is close to 0% for
most of 1975-2000 and only reaches consistently >95% from around 2009-2010 onward, because the
equity workbook was not populated retroactively to most fields' actual production start dates
(`pre_equity_history`: 27,064 of 133,608 field-months). A human decision is needed on how to
proceed (restrict publication to well-covered years, or find an additional pre-2000 source) before
any further Phase 2 work builds on this join.

Other confirmed findings: partial first months are correctly isolated as `month_start_boundary`
(100 field-months, mechanical, not missing data) and kept distinct from genuine gaps
(`genuine_interval_gap`: 0 in the live data, once boundary effects are excluded); `ROCHELLE`'s
known equity overlap predates its own PPRS production history and so never surfaces in this
production-scoped run, though the quarantine mechanism itself is verified by a dedicated
regression fixture; no new source anomalies beyond those already known in sections 15.3-15.4 were
found at full-history scale.

### 0.6 What changed in v2.7

Section 15.11 (new) records the publication-window and coverage-policy decision checkpoint
(`etl/equity_publication_window.py`). **This is evidence, not a decision**: no publication start
date, and no final policy among A-D, is approved by this version. See section 15.11 for the
stability-threshold findings (condensate is the binding constraint among the four streams,
stabilizing at 2013-03), the recommended-but-unadopted Policy D, the deeper MURLACH source review
(confirms it remains unresolved; a working hypothesis about the 2050 date's origin is recorded as
speculation, not fact), the bounded pre-2000 source search (nothing found that would close the
gap), and draft (unpublished) methodology wording.

### 0.7 What changed in v2.8

Section 15.11's policy is **approved and settled** (Policy D, fixed start `2013-03`, 95%/99.5%
thresholds, applied separately by stream, MURLACH excluded). Section 15.12 (new) records the
unattended build integration: `etl/equity_artifacts.py` is wired into `etl/build.py`, generating
deterministic `docs/data/equity/*` artifacts (`meta.json`, `index.json`, `companies/*.json`,
`fields/*.json`, `anomalies.json`) on every weekly build, validated build-breaking (source
integrity, E1, E4, E5, E7, E8, coverage policy, artifact conservation) before anything is written.
`docs/methodology.html` documents the approved policy. **The frontend is unchanged** — no equity
charts, controls, or company-equity view exist yet; that is a separate, not-yet-approved step.

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
      "source_item_title": "Field Partners",
      "source_page_description": "Current and historical field equity shares",
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
  "region": "...",
  "location": "...",
  "units": [{ "name": "...", "type": "...", "first_period": "200207", "last_period": "202606" }],
  "storage_units": [{ "name": "...", "type": "...", "first_period": "...", "last_period": "..." }],
  "series": [
    { "period": "202001", "oil_mbd": 0.0, "dry_gas_mmscfd": 0.0,
      "assoc_gas_mmscfd": 0.0, "condensate_mbd": 0.0, "water_mbd": 0.0 }
  ]
}
```

`units` lists every historical reporting unit ever classified `production` for this field
(section 7.3), each with the period range it was actually reporting under that name — not just
its current unit name. Classification itself is implicit in which list a unit appears under
(`units` vs `storage_units`); it is not repeated as a per-unit field since the two lists are
already a partition. `storage_units` lists units excluded from `series` per section 7.3, with the
same period-range shape, so the field panel can surface them separately without them ever
contributing to the production numbers, in any period, not only the latest one.

`operator`, `region` and `location` reflect the **most recent** production period on record, per
the same "current, applied retrospectively" convention as section 6.1 — not an arbitrary
historical value from early in the field's life.

**The two rename cases** identified in section 7.2 (`SEAN` → `NORTH SEAN`, `COLUMBA B` →
`COLUMBA BD`) are resolved as **one continuous series per field**, not two separate series. This
requires no special-case code: NSTA already carries both the old and new unit names under a single
`FIELDNAME`, and because the two unit names' periods never overlap, summing every production unit
for a given `(FIELDNAME, period)` — the same rule that already handles ROUGH's concurrent
production/storage split — naturally produces one unbroken series across the rename boundary. The
alternative (two separate series, one per unit name) would fragment a single field's history for
no operational reason and complicate every downstream consumer (search, equity matching in Phase
2) for a purely administrative renaming. The discontinuity is not hidden, though: `units` lists
both historical names with their own period ranges, so a reader can see the handover even though
`series` itself has no gap or seam. Verified with a unit test asserting a continuous period
sequence across the boundary (`tests/test_transform.py`).

**Field universe.** The set of fields with a `history/{slug}.json` file is larger than
`fields.geojson`'s 250 (latest-period-only) fields — full history covers every field that has
*ever* produced since the earliest observed period (197506), 552 as of the September 2026 build.
This is the field universe section 15.5's equity-matching tolerance must be measured against, not
the latest-period 250.

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

**Resolved, v2.2: the operative document is the NSTA User Agreement, dated June 2023.**

The data.gov.uk entries for the PPRS points dataset and Field Partners show no licence set or
"Custom License". Specification v1.0 asserted Open Government Licence v3.0; that is not supported
by the catalogue entries. NSTA's own site instead links, from its own terms-and-conditions page
(`nstauthority.co.uk/site-tools/terms-and-conditions/`), to a PDF titled **"North Sea Transition
Authority User Agreement"**, dated June 2023 (`nsta-user-agreeement-june-2023.pdf`). This is the
operative document and was read in full (not summarised) before this section was written.

**A materially different, older document is still mirrored by third parties and must not be
relied on.** A page at marine.gov.scot mirrors an older text called the "OGA Open User Licence"
(version 1.0). It differs from the June 2023 document in ways that matter:

| | Older "OGA Open User Licence" v1.0 (third-party mirror) | **Current NSTA User Agreement, June 2023 (operative)** |
| --- | --- | --- |
| Commercial use | Permits exploiting the Information "commercially and non-commercially" | Permits exploiting the Information **non-commercially** only — no commercial-use grant |
| Attribution string | "Contains information provided by the OGA." | "Contains information provided by the North Sea Transition Authority and/or other third parties." |
| Link to licence | "where possible, provide a link to this licence" | No such clause |

Both documents share the same structure otherwise: worldwide/royalty-free/perpetual/non-exclusive
rights to copy, publish, distribute, transmit and adapt the Information; a mandatory verbatim
attribution statement whose omission automatically terminates the granted rights; exemptions for
personal data, unpublished information, logos, third-party rights and other IP; a non-endorsement
clause; no warranty; and English & Wales governing law.

**Use of this project's NSTA-derived data has been assessed as non-commercial** under the June
2023 User Agreement, recorded in `ATTRIBUTION.md` with the assessment date. That assessment is
specific to the current use and the current document version — a change in either requires
re-assessment; this section does not pre-authorise one.

Therefore:

- `ATTRIBUTION.md` states the source, dataset names, item IDs, the operative licence document and
  its date, the non-commercial-use assessment and when it was made, the verbatim required
  attribution string, and explicitly flags that the older mirrored "OGA Open User Licence" text is
  superseded and must not be relied on.
- The UI carries the verbatim required attribution string in the footer, alongside a link to the
  NSTA terms-and-conditions page.
- The UI does **not** display any licence badge (no OGL badge, no "open data" badge) and makes no
  claim beyond the required attribution string itself — the attribution string is a licence
  condition being met, not a badge asserting a licence status.

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
5. Extend ETL to full history and per-field history files. — **Done, v2.2. See section 9.3.**
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

**Primary source: the item titled "Field Partners".**

**Correction (v2.3, milestone 1 live investigation, 2026-09-09):** Specification v2.2 and
earlier assumed two separate NSTA datasets existed — a time-series "Field Equity Shares"
dataset (the correct primary source) and a present-day-only "Field Partners" snapshot
(forbidden for time series, cross-check only). Live investigation found this to be wrong.
There is no dataset titled "Field Equity Shares" anywhere in the NSTA ArcGIS Online
organisation (`OZMfUznmLTnWccBc`, `orgUrlKey: ukcs-transition`) — searching that org for the
exact phrase "field equity shares" returns zero results. The NSTA Fields data theme page's own
link, labelled **"Current and historical field equity shares"**, resolves (via an ArcGIS Hub
search redirect, not a direct file link) to a single ArcGIS item titled **"Field Partners"**
(item id `40fb75005dca48e886891350da9dedd8`), whose `url` property is a direct `.xlsx` download.

The workbook's actual content does not match the "present-day snapshot" description. It contains
full historical validity intervals: 7,683 rows as of 2026-09-09, start dates back to 1968-08-01,
and 277 distinct "Equity Share Time Period" labels (e.g. `Previous-2005 to 2020`, `Current`).
This is the dataset structure section 15.1 originally required of "Field Equity Shares", just
published under the "Field Partners" item title.

**This is the one and only live source used from here on.** Do not infer snapshot-only behaviour
from the item title — the title is a publisher naming choice, not a description of the data's
temporal scope, and has been checked directly against the live file's contents. Record source
identity using **both** names, since they answer different questions and neither alone is
sufficient provenance:

- source item title (as recorded in ArcGIS Online): **"Field Partners"**
- source-page description (as written on the NSTA Fields page): **"Current and historical field
  equity shares"**

If NSTA ever publishes a distinct item actually titled "Field Equity Shares" in the same org,
treat that as a new discovery requiring the same live-structure verification as this one — do not
assume it supersedes this source without checking its contents first.

An archived earlier release of this workbook (covering 2014–2020, then found under the "Field
Equity Shares" description) confirms the same interval structure: each row carries an interest
percentage, a **start date** and an **end date**. Records run back to the late 1960s, and
transactions are visible in the data — for example an 84.11% interest running from February 1978
to October 2016, and groups of partner rows all terminating on a common date as an interest
changes hands.

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

The equity workbook is an Excel file published on a web page, not a REST endpoint. The archived
file's URL embeds a date, which implies the filename changes on republication.

**Correction (v2.3):** the acquisition path is not a single-page scrape to a direct file link.
Live investigation found it is a two-hop resolution: the NSTA Fields data theme page links to an
ArcGIS Hub *search* page (a client-rendered SPA with no server-side link to scrape), which must be
resolved via the ArcGIS Online search API, scoped to org `OZMfUznmLTnWccBc`, using the search term
embedded in the Hub URL's `q` parameter. The matched item's `url` property is the actual direct
`.xlsx` download, hosted on Azure Blob Storage (`datanstauthority.blob.core.windows.net`), not on
`nstauthority.co.uk`. `etl/equity_fetch.py` implements this two-hop resolution and requires
exactly one ArcGIS search result, refusing to guess between multiple candidates.

Requirements for `etl/equity_fetch.py`:

- Scrape the NSTA Fields data theme page for the equity-shares link (see the two-hop resolution
  above). Do **not** hardcode the file URL.
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

**Status: policy decisions below are APPROVED for the latest-period checkpoint (v2.5,
2026-09-09)**, implemented in `etl/equity_join.py` and reported in
`etl/equity_latest_period_join_report.md`. They are not yet exercised against the full
1975–present history — that remains future work, gated on review of this checkpoint (see
`etl/equity_interval_diagnostics_report.md` for the investigation that produced them). Two
specific findings remain genuinely unresolved, not merely deferred: the meaning of the 91
`boundary_transition` and 16 `standalone_snapshot` zero-duration rows (see below) is not settled
by this checkpoint and must not be read as such.

Equity is a set of validity intervals per (field, company). Production is monthly. The join must
be an interval containment test, not an equality join.

Canonical definition (unchanged, and confirmed correct by the diagnostic investigation — see
below):

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
- **Sentinel start dates: none exist in the live workbook (v2.4 correction).** The archived
  2014–2020 file was believed to contain rows dated `1900-01-01` ("unknown / since inception").
  The live 7,683-row workbook (2026-09-09) has **zero** rows with a start date before 1960 (the
  earliest observed start date is 1968-08-01). Detection logic (dates before 1960 → a
  `start_is_sentinel` flag) is retained defensively in `etl/equity_parse.py`, but it currently
  never fires. Re-verify this whenever the live source changes materially.
- **Zero-duration rows: 838 exist, not "possibly a few" (v2.4 correction).** Rows where
  `start_date == end_date` are common (10.9% of all rows), not a rare anomaly. Under the
  half-open convention above, a zero-duration interval `[d, d)` is mathematically empty — it
  never contributes to any month's containment test — so **no special-casing is required to
  exclude them from the sum**. What is required is that E7 (below) not treat them as a build
  error. `etl/equity_interval_diagnostics.py` classifies all 838 by relationship to neighbouring
  rows: 689 `boundary_duplicate` (pct matches the substantive interval starting at the same
  instant — fully redundant with it), 91 `boundary_transition` (pct differs from that interval —
  not fully explained, possibly a genuine same-day step-change), 42 `termination_marker` (last
  recorded entry for a (field, company) pair, no successor), 16 `standalone_snapshot` (the only
  record that pair ever has, clustering by date across unrelated fields/companies — suggestive of
  a shared external event, not identified further). None of these are discarded or repaired by
  the diagnostic; they are retained and classified only.
- **One genuine overlapping-interval data error found**: `ROCHELLE`, August 2011 — two companies'
  (CNOOC PETROLEUM EUROPE LIMITED and HARBOUR ENERGY WPUK LIMITED) rows genuinely overlap by one
  month (one ends 2011-08-31, the next for the same companies starts 2011-08-01), producing a
  200% sum for that field-month. This is **not** a zero-duration or sentinel-date artifact — it is
  exactly the kind of error E4 exists to catch. **Approved policy: quarantine, never repair.** A
  field-month E4 flags is excluded from any calculated equity total, its coverage status is set to
  `quarantined`, and it is reported by name with its conflicting companies and source intervals
  (`etl/equity_join.py`'s `check_e4`). The two or more conflicting interests are never normalised
  back to 100%, and no owner is ever preferred over another. **This is temporary**: it must be
  reviewed again before the full historical join, since a policy adequate for one known 2011
  incident may not be adequate at full-history scale. ROCHELLE itself does not affect the latest
  period (202606) — it produced no quarantines in the checkpoint run — but a regression fixture
  reproducing it is committed in `tests/test_equity_join.py` so the quarantine behaviour is
  verified even though the live case is historical.
- **4 future-dated rows exist** (`ALVHEIM`/AKER BP ASA and `STATFJORD(CROSS BORDER)`/EQUINOR, both
  starting 2030-05-01; `MURLACH [pt of MARNOCK-SKUA]`/BP and `MURLACH [pt of MARNOCK-SKUA]`/NEO
  ENERGY, both starting 2050-01-04). Each is the only equity row (or, for MURLACH, one of only two
  rows) its field has. None overlaps a currently-open interval — there is nothing to overlap with.
  As of any month up to and including the present, these 3 fields correctly resolve to **zero**
  active interest under the canonical containment test above, with no special-casing needed: a
  future `start_date` simply never satisfies `start_date <= month_start` yet. This is a real,
  explained gap, not a parse error — see the revised E5 below.
- **1,187 open-ended rows exist**, covering 531 fields. 342 fields have more than one open-ended
  *positive*-interest row, which is expected (multiple current partners). Zero fields have the
  *same* company holding more than one open-ended row (which would be a genuine overlap). 528 of
  531 fields' currently-open interests sum to 100% ±0.5pp; the 3 exceptions are exactly the
  future-dated-only fields above (no current row at all, not a sum error).
- **`Equity Share Time Period` is fully derived from Start/End Date** at year granularity, with
  zero exceptions across all 7,683 rows (`Current` ⟺ `end_date is None`; `Previous-Y1 to Y2` ⟺
  `start_date.year == Y1 and end_date.year == Y2`, always). It carries no information not already
  in the two date columns and never conflicts with them. **Retain it as source metadata only.**
  Do not parse or rely on it for interval resolution — it is strictly less precise than the date
  columns it is derived from.
- Build per-field sorted interval structures and resolve each month by binary search. A naive
  nested loop over ~60 years × ~400 fields × ~10 partners will be slow enough to matter in
  Actions.

### 15.4 Validation rules — all build-breaking

**Status: E1, E4, E5, E7 and E8 corrections below are APPROVED and implemented for the
latest-period checkpoint (v2.5)**, in `etl/equity_join.py`'s `check_e1`/`check_e4`/`check_e5`/
`check_e7`/`check_e8`. E2, E3, E6 and E9 are unaffected and remain as originally worded, not yet
implemented (no code exists for them yet — they were out of scope for this checkpoint). The
table's original E1/E4/E5/E7 wording is superseded by the corrections below; do not implement the
table literally.

Implement in `etl/validate_equity.py`. Any failure exits non-zero and writes no artifacts.

| # | Rule (original wording — superseded, see corrections below) | Tolerance |
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

**Corrected rules, approved and implemented for the latest-period checkpoint (v2.5):**

- **E1** (interest conservation): sum to 100% ±0.5pp, for every matched field with at least one
  currently-effective ownership interval. Does not fail solely because a field's only equity
  row(s) are future-dated (that is E5's concern), and quarantined field-months are excluded from
  the pass/fail count and reported separately by E4, never counted as passing. Latest-period
  result (202606): 249 fields pass, 0 fail.
- **E2, E3, E6, E9**: no changes proposed; not implicated by this investigation, and not yet
  implemented (no code exists for them — out of scope for this checkpoint).
- **E4** (overlap validation): detects overlapping positive-interest intervals for the same
  (field, company), and separately detects a field-month total exceeding 100% even when the
  conflicting rows belong to different companies. Never auto-resolves — every violation is
  quarantined and reported by name with its conflicting companies and source intervals. Confirmed
  necessary, not just theoretical: the live `ROCHELLE` case is a real violation of exactly this
  kind. Latest-period result: 0 quarantined field-months (ROCHELLE's overlap is historical,
  2011-08, and does not recur in 202606) — verified live and by a committed regression fixture
  reproducing the ROCHELLE case exactly (`tests/test_equity_join.py::test_rochelle_style_quarantine`).
- **E5** (coverage validation): a producing latest-period field must resolve to an active
  ownership set unless field matching is unresolved (`unmatched`), the source contains only
  future-dated ownership (`future_only`), or the field-month is quarantined due to a source
  anomaly (`quarantined`) — each category reported separately, never collapsed into one generic
  "missing equity" count. Latest-period result: 249 resolved, 0 unmatched, 1 future_only
  (`MURLACH [pt of MARNOCK-SKUA]`), 0 quarantined, 0 unresolved_gap.
- **E7** (interval validity): `start_date <= end_date` on every row (not the original strict `<`)
  — 838 live rows have `start_date == end_date` and are accepted as source event records, never
  active ownership intervals, never a build failure for that reason. `start_date > end_date`
  remains build-breaking (0 such rows found in the live workbook — verified over all 7,683 rows,
  not scoped to the latest period, since this is a structural data-integrity property of the
  source).
- **E8** (production conservation): computed per stream (oil, dry gas, associated gas,
  condensate) separately — never combined. Compares `sum(equity-attributable production)` against
  `sum(field production)` **only for fully-resolved fields**; explicitly reports total production,
  production included in the test, production excluded due to unresolved coverage, and the
  resulting `coverage_pct`, rather than silently comparing against quarantined/unresolved
  production. Latest-period result: dry gas and condensate at 100.0% coverage; associated gas at
  99.458%; oil at 96.928% (the shortfall in both is `MURLACH`'s real 202606 production, excluded
  because its equity is future-only — see `etl/equity_latest_period_join_report.md` for the full
  breakdown). None of the four streams is claimed at 100% coverage where matching or interval
  resolution is incomplete.

**Zero-interest rows are confirmed to exist and their intended exclusion is confirmed correct, not
merely proposed.** 241 rows have `interest_pct == 0` (218 of them also have `Operator Flag = 'Y'`).
The diagnostic investigation found 86% of the zero-interest, Operator-Flag='Y' rows coincide with
a *different* company holding the real equity for the same field and period — i.e. Operator Flag
records operatorship independently of economic interest, and must never be read as implying a
positive interest. Per the existing default: retain zero-interest rows as source records, but
exclude them from the E1 sum, since multiplying production by 0% contributes no volume regardless
of Operator Flag.

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
(transition 201704/201705) and `COLUMBA B` → `COLUMBA BD` (transition 200006/200007; the current,
post-merge PPRS field name is `COLUMBA B/D`, with a slash — earlier drafts of this spec wrote
`COLUMBA BD` without one, which was imprecise). If the equity workbook uses the pre-rename name
for the pre-rename period (plausible, since equity records run back further than some of these
renames), a name matcher keyed only on the current `FIELDNAME` will silently fail to match the
earlier interval. Check both the current and historical name for every renamed field found in
section 7.2 before finalising the alias file below, and add explicit rows to `field_aliases.csv`
for both directions if the workbook does use the old names.

**Checked, resolved (v2.3, milestone 2, 2026-09-09):** both cases were verified against the live
equity workbook. Neither needs an alias row. The PPRS field universe used for matching
(`docs/data/history/index.json`) is already the section 7.2 rename-consolidated view — it exposes
only the current, merged names (`NORTH SEAN`, `COLUMBA B/D`), not the raw pre-rename PPRS
`FIELDNAME` values. The equity workbook independently uses the same current names for the full
history of both fields: `NORTH SEAN` rows start as early as 1984-03-21 (well before the
201704/201705 transition) and `COLUMBA B/D` rows start as early as 2002-12-16 (before the
200006/200007 transition). Both matched by exact string match with no alias needed. See
`etl/equity_field_matching_report.md` for the full matching output.

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
   structure. **Stop and report before parsing.** — **Done.**
2. `etl/equity_parse.py` — normalised interval table; report row counts, date ranges, and the 0%
   row question. **Stop and report.** — **Done.**
3. Field name matching; produce the unmatched list; build the alias file. Check both pre- and
   post-rename names for `SEAN`/`NORTH SEAN` and `COLUMBA B`/`COLUMBA BD` per section 15.5. —
   **Done.** No alias rows were needed (section 15.5).
4. `etl/equity_join.py` — interval join, latest period only; run E1 and E8. **Stop and report.** —
   **Done.**
5. Full history join; all validation rules E1–E9 (E2, E3, E6, E9 not yet implemented as
   standalone checks; E1/E4/E5/E7/E8 are implemented and build-breaking as of step 5's build
   integration). — **Done.** Diagnosed (`etl/equity_join_historical.py`, section 15.10), a
   publication window approved (section 15.11), and integrated into the unattended build within
   that window (`etl/equity_artifacts.py`, section 15.12).
6. Company alias reconciliation. — **Not started** (deliberately: section 15.12's artifacts use
   legal-entity names exactly as recorded, no rollup).
7. Artifacts, UI, methodology page. — **Artifacts and methodology page done** (section 15.12,
   `docs/methodology.html`). **UI not started** — no equity charts, controls, or company view
   exist in `docs/index.html` / `docs/app/*` yet.

**Do not proceed past step 4 until E1 and E8 pass on the latest period.** (They do — see section
0.4.) **Do not proceed past step 5 (to company alias reconciliation or publication) until the
full-history coverage picture in section 15.10 is judged acceptable by a human reviewer** — the
diagnostic found coverage below 50% in most years before 2002, which the checkpoint does not
consider itself qualified to approve or reject.

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

### 15.10 Full-history diagnostic findings (v2.6, 2026-09-09) — NOT ready for publication

`etl/equity_join_historical.py` applies the approved policies (sections 15.3-15.4) across the
complete overlap between PPRS's 133,608 field-months (552 fields, 1975–present) and the equity
workbook's 7,683 rows. **This is a diagnostic checkpoint only — not integrated into
`etl/build.py`, no `docs/data/equity/*` artifacts, no company alias or parent-group
reconciliation.** See `etl/equity_historical_join_report.md` and
`etl/equity_historical_anomalies.json` for the full run.

**Full-history production-weighted coverage is low and must not be read as the model being ready
to publish**: oil 33.0%, dry gas 56.1%, associated gas 52.1%, condensate 62.3%. The reason is not
a matching or interval-resolution defect — it is a genuine, structural property of the source:
**annual coverage is close to 0% for most of 1975–2000, rises sharply through the early-to-mid
2000s, and only reaches ~97–100% from around 2009–2010 onward** (e.g. oil coverage: 0.0% in
1975–1980, 8.4% in 2000, 41.9% in 2002, 92.1% in 2007, 96.9% in 2011, 100.0% in 2018–2024). The
equity workbook simply was not populated retroactively to most fields' actual production start
dates — see `pre_equity_history` below.

**E5 final resolution categories** (every producing field-month falls into exactly one):

| Category | Field-months (live run) | Meaning |
| --- | --- | --- |
| `resolved` | 100,307 | Fully resolved, sum 100% ±0.5pp, no overlap |
| `pre_equity_history` | 27,064 | Production month predates this field's earliest equity coverage, and that coverage is not itself future-dated relative to today — genuine absence of historical equity records, not an error |
| `unmatched` | 6,127 | Field name has no equity workbook counterpart (52 fields, matches the milestone-2 field-matching result) |
| `month_start_boundary` | 100 | Mechanical artifact: ownership begins this calendar month but not on day 1, so the month-start test finds nothing active for that one month even though coverage is effectively continuous |
| `future_only` | 10 | Every equity row for this field starts after today (`MURLACH [pt of MARNOCK-SKUA]` only, in the live run) |
| `quarantined` (E4 overlap) | 0 (live run) | Overlapping intervals. `ROCHELLE`'s August 2011 equity overlap is real (confirmed in the milestone-3 investigation and by a committed regression fixture) but never surfaces here: `ROCHELLE`'s own PPRS production history only starts 201306, after the overlap, so this production-scoped diagnostic never evaluates that field-month — there is no production to quarantine, not because the overlap was missed |
| `e1_sum_mismatch` | 0 (live run) | Active interests resolve but do not sum to 100% ±0.5pp, and it is not an overlap |
| `genuine_interval_gap` | 0 (live run) | A real break in equity coverage between two dated intervals, for a field that has coverage both before and after |
| `no_equity_history` | 0 (live run) | Field matched by name, but the matched equity field name has zero rows (a defensive category; does not occur under the current exact/normalized/alias matcher) |

**Partial first months are confirmed handled correctly, not merely assumed**: `month_start_boundary`
only fires when an interval's own start date falls within the evaluated calendar month but after
day 1 — 100 field-months across 97 fields, excluding a combined 424 mbd oil / 481 mmscfd dry gas /
640 mmscfd associated gas / 1.4 mbd condensate from the historical total. This is distinct from,
and far smaller than, `pre_equity_history`'s 27,064 field-months. The two must never be conflated:
one is a one-month boundary rounding effect: the other is decades of the source simply not
existing yet for a given field.

**Historical quarantine**: 0 quarantined field-months in the current run, over the 133,608
field-months where PPRS has actual production. `ROCHELLE`'s real August 2011 equity overlap
predates `ROCHELLE`'s own production history (which starts 201306) so it is never evaluated here -
the quarantine mechanism itself is verified independently by a dedicated regression fixture rather
than relying on a live case recurring within the production-scoped range (see
`tests/test_equity_join_historical.py::test_same_company_overlapping_histories_quarantined` and
`etl/equity_join.py`'s own `test_rochelle_style_quarantine`). If a future workbook update
reintroduces overlaps at scale, or extends any field's production history earlier, the quarantine
policy (report, exclude, never normalise or prefer an owner) is unchanged, but its reporting
format should be reviewed for scale per section 15.3.

**No new source anomalies were identified beyond those already known** (838 zero-duration rows,
241 zero-interest rows, 4 future-dated rows, 1 historical overlap). The full-history run confirms
`genuine_interval_gap` is **zero** once boundary effects are correctly excluded — every apparent
gap in the live data resolves to either `pre_equity_history`, `future_only`, or
`month_start_boundary`.

**MURLACH**: 10 affected producing months (202509–202606), excluding 110.3 mbd oil and 82.7 mmscfd
associated gas from the historical total, entirely `future_only` (no `pre_equity_history` months
for MURLACH — its full production history overlaps this single gap). A related equity field name,
`MARNOCK [pt. of MARNOCK-SKUA]`, exists in the workbook, but its rows belong to a **different**
field and were not applied to MURLACH without authoritative evidence they should be. This remains
open for human review, not resolved here.

**Conclusion: the historical model is not reliable enough to integrate into the unattended build
pipeline as-is.** It is demonstrably reliable for recent history (~2009 onward, coverage
consistently >95%) but not for 1975–2000, where coverage is frequently below 10%. Any future
integration must either (a) restrict published historical equity-attributable production to the
period where coverage is adequate, with the restriction stated prominently in the UI, or (b) find
and integrate a source of pre-2000 equity intervals this workbook does not contain — a decision
for a human reviewer, not made here.

### 15.11 Publication-window and coverage-policy checkpoint (v2.7-v2.8) — POLICY APPROVED (v2.8, 2026-09-09)

`etl/equity_publication_window.py` computes the evidence a human reviewer needs to set a
publication window and coverage rules; **it does not set them**. See
`etl/equity_publication_window_report.md` for the full run (candidate-window statistics for seven
start dates, stability thresholds, breach-cause analysis, and an assessment of four candidate
policies). **No publication start date is approved by this section.** The specific date remains
whatever the reviewer decides after reading that report — this spec does not anticipate it.

**Stability thresholds found** (first month after which coverage never again falls below the
threshold, per stream): the last stream to stabilize at the 95% level is condensate, at 2013-03 —
meaning a single fixed start date chosen for *all four streams together* cannot be earlier than
2013-03 without reintroducing a below-95% month in at least one stream. Oil and associated gas
never reach a state of "never again below 99%" even in the most recent observed data, because
`MURLACH [pt of MARNOCK-SKUA]`'s ongoing future-only exclusion (section 15.10) keeps trimming a
small amount of oil/associated-gas coverage in the most recent months for as long as that
field remains unresolved.

**Breach cause, confirmed at threshold-stability precision, not just qualitatively**: of the
months below 95% coverage (any stream, any candidate window), `pre_equity_history` is the
dominant excluded category by a wide margin (405/419 oil months, 276/293 dry-gas months,
402/406 associated-gas months, 264/293 condensate months) — confirming section 15.10's
conclusion that the coverage gap is structural and source-driven, not a matching, boundary, or
quarantine artifact.

**Candidate policies A–D were assessed** (comparability, risk of misleading, implementation
complexity, transparency, investor-relations suitability); **Policy D (fixed start date + retained
monthly `coverage_pct` + a warning threshold within the published window) is recommended** over a
dynamic threshold (Policy B, rejected: makes the published set unstable between builds) and over
publishing the full series with only a coverage label (Policy C, rejected: a coverage_pct label
does not make a 0–10%-covered decade analytically usable, and this project should not invite that
misread). **Approved (v2.8): Policy D, as recommended.**

**MURLACH**: a focused source review (full production and equity row dump in the report) confirms
section 15.10's finding with more detail. `MURLACH [pt of MARNOCK-SKUA]` began producing per PPRS
only in 2025-09 — a very recently started sub-unit. Its only two equity rows (BP 80%, NEO ENERGY
20%) share an identical, unexplained start date of 2050-01-04, with no prior record under that
name. The related `MARNOCK [pt. of MARNOCK-SKUA]` entry is a **separate field** in the source with
its own complete, current, non-future ownership history (currently 100% BP EXPLORATION OPERATING
COMPANY LIMITED since 2017-03-31) — the source provides no explicit link between the two.
**Working hypothesis, not a finding**: MURLACH's very recent first-production date is consistent
with the 2050 date being an un-updated placeholder rather than a literal scheduled transfer, but
this is speculation and is explicitly not acted on. **MURLACH remains future-only and unresolved.**
No alias or inherited ownership was applied.

**Pre-2000 source inventory**: a bounded web search (two queries, logged in the report) found no
distinct, citable, field-level dated-equity dataset for the pre-2000 UKCS at the
percentage-and-effective-date grain this project needs. The NSTA licence/licence-block datasets
already identified in section 15.1 as company-name-history sources were confirmed (not merely
assumed) to be licence-level, not equity-percentage-level, and therefore unable to close this gap.
One unverified lead (a withdrawn GOV.UK "field data" page) was found and logged but not pursued —
assessing it further is ingestion-adjacent work outside this checkpoint's scope. **No pre-2000
source was ingested, merged, or scraped into the model.**

**Draft methodology wording** for eventual publication is in the report (section 7 of
`etl/equity_publication_window_report.md`), covering source identity (both the "Field Partners"
item title and the NSTA page's "current and historical field equity shares" description),
half-open month-start resolution, zero-duration and zero-interest row treatment, operator-status
independence from economic interest, quarantine-not-repair, per-stream coverage, the restricted
publication window (placeholder pending the actual date), and the gross-equity-share framing. **Not
written to `methodology.html`.**

**Status: full-history equity coverage is confirmed insufficient for publication from 1975. The
historical model is validated internally (E1/E4/E5/E7/E8 all pass on the field-months it does
resolve) but is not yet approved for unattended publication under any window — that approval is
pending your review of this checkpoint's recommendation.**

### 15.12 Unattended build integration (v2.8, 2026-09-09) — ARTIFACTS PUBLISHED, UI NOT YET

**Approved policy, settled (not subject to change without an explicit methodology decision and a
test update — see `etl/equity_config.py`):**

| Constant | Value |
| --- | --- |
| Publication policy | Policy D (fixed start date + monthly stream-specific coverage) |
| Fixed publication start | `2013-03` |
| Minimum coverage to publish a stream-month | 95% |
| Warning threshold | 99.5% |
| Thresholds applied | Separately by production stream, never combined |
| `MURLACH [pt of MARNOCK-SKUA]` | Unresolved, future-only, excluded from totals; included in coverage/anomaly reporting |
| Start-date movement | Never dynamic — requires an explicit methodology decision and test update |

Equity is now integrated into `etl/build.py` (via `etl/equity_artifacts.py`), inserted at the
extension point section 15.8 anticipated: after history aggregation, before the meta dict and
write block, inside the same try/except as the production pipeline. **An equity failure fails the
whole build and leaves `docs/data/` completely untouched** — verified by a committed atomic-write
test (`tests/test_equity_artifacts.py::test_atomic_write_never_leaves_target_dir_partially_updated`)
and by the shared try/except around both pipelines in `build.py`.

**Artifact schema**, all under `docs/data/equity/`:

- `meta.json` — publication policy constants, source provenance (both the item title and the
  page description, per section 15.1), resolved URL/Last-Modified/SHA-256, row/field/entity
  counts, build timestamp, methodology version, source limitations (including MURLACH and the
  standing internally-consistent-but-incomplete-source caveat).
- `index.json` — per company: slug, name, first/last published period, field count, latest
  production and coverage status by stream. Deliberately excludes full monthly series to keep
  startup data small.
- `companies/{slug}.json` — monthly series per stream, each entry `{value, status, coverage_pct}`
  with `value` **null, never zero**, when `status` is `unavailable`; contributing field slugs;
  first/last published period; explicit `"Legal entity as recorded by NSTA"` label.
- `fields/{slug}.json` — dated ownership intervals (company, interest %, dates, operator flag,
  status) exactly as recorded; resolution status by published period; excluded periods; field-match
  method.
- `anomalies.json` — complete evidence for MURLACH, future-only fields, quarantined overlaps,
  unresolved gaps, unmatched fields, below-threshold stream-months, and any `start_date > end_date`
  rows (none found live). Resolved zero-duration rows are not listed individually — only their
  aggregate classification counts, per the milestone-3/4 categories.

**Live run (2026-09-09)**: 500/552 fields matched (52 unmatched, same set as milestone 2), 292
legal entities, 491 field files, published `201303`–`202606`. Zero quarantined overlaps, zero
unresolved gaps, zero `start_date > end_date` violations, zero below-95%-threshold stream-months in
the published window. `docs/data/equity/` is 13 MB uncompressed (~660 KB gzip-equivalent);
`index.json` is the largest non-company file at 113 KB. Deterministic rebuild with unchanged
source input verified byte-identical except `built_at`. Full build runtime (production + equity):
under 1 minute locally.

**Validation, all build-breaking, implemented in `etl/equity_artifacts.py`:**

- Source integrity: item title drift, fetch/parse failure, and a >10% normalized-row-count change
  against the previous build's `meta.json` all fail the build (`EQUITY_ROW_COUNT_TOLERANCE_FRACTION`
  in `etl/equity_config.py`).
- E1: every resolved field-month sums to 100% ±0.5pp within the published window; any
  `e1_sum_mismatch` fails the build.
- E4: quarantine is proven structurally safe rather than asserted — `build_resolved_grain_rows_historical`
  only ever emits rows for `category == "resolved"`, and the build additionally asserts no
  quarantined field appears in the resolved rows before writing anything. A quarantine that cannot
  be proven safe this way would fail the build per the "choose the stricter behaviour" instruction;
  none has been encountered live.
- E5: every published field-month's resolution categories are asserted to sum to the total
  published field-month count before writing (no field-month can silently disappear from
  classification).
- E7: `start_date <= end_date` across the full workbook (not period-scoped — a structural property
  of the source).
- E8: per-stream, per-month conservation over fully-resolved fields within the published window.
- Coverage policy: no period before `2013-03` enters the published dataset (asserted, not just
  filtered); every published value carries `coverage_pct`; `complete`/`warning`/`unavailable`
  status is set per the approved thresholds.
- Artifact conservation: company totals equal field-based equity totals (verified live and by a
  committed test); a deterministic rebuild of unchanged input is byte-identical apart from
  `built_at`; a failed build leaves the existing `docs/data/` tree completely untouched (writes
  happen only after every check above passes, mirroring the existing production pipeline's own
  discipline).

**Weekly build behaviour**: `.github/workflows/build-data.yml` now diffs `docs/data/equity` and the
production artifacts independently, and the commit message names which source(s) actually changed
(`data: refresh NSTA equity shares` / `data: refresh NSTA PPRS and equity shares (period …)` /
the existing PPRS-only message) rather than always saying "NSTA refresh" — the two sources update
on independent schedules (spec section 15.2) and neither should be silently folded into the other's
commit. A single commit per run is preserved; the raw equity workbook is uploaded as a 90-day
GitHub Actions build artifact for traceability (spec section 15.2), separate from git history.

**Not done in this step, deliberately**: no equity charts, controls, or company-equity view were
added to `docs/index.html` or `docs/app/*` — the frontend is completely unchanged. No company alias
or parent-group mapping exists; every company name in the published artifacts is the legal entity
exactly as recorded by NSTA. `docs/methodology.html` exists and documents the approved policy but
is not yet linked from the main site navigation.

**Status: equity artifacts are live, validated, and committed to the unattended weekly build.**
Whether they are ready for **frontend integration** (charts, controls, a company-equity view) is a
separate decision, not addressed by this section — see the recommendation accompanying this
checkpoint.

---

### 15.13 Equity frontend checkpoint (v2.9, 2026-09-09) — COMPANY EQUITY VIEW IMPLEMENTED

Adds the user-facing frontend on top of the artifacts published in 15.12. No parent-company
mapping, no legal-entity merging, no boe/d calculation, no change to the March 2013 publication
start, the 95%/99.5% thresholds, or interval-resolution policy — none of those were touched, and
none is described as implemented below.

**New frontend modules** (`docs/app/`): `equity.js` (data loading — lazy, cached, same discipline as
`state.js`: `meta.json`/`index.json` loaded once at startup, `companies/{slug}.json` and
`fields/{slug}.json` fetched at most once each, only on selection, never preloaded in bulk);
`equity-ui.js` (company equity panel, field ownership section, MURLACH note); `search.js` (global
search index and keyboard-accessible combobox); `urlstate.js` (hash-based shareable state via
`history.replaceState`). `charts.js` gained `renderEquityStreamChart` (one stream, one chart, one
unit — never shares an axis with another stream). `main.js` and `docs/index.html`/`styles.css` were
extended, not rewritten: the existing map/field/operator code paths are unchanged.

**Equity is the default company metric.** On load, `#mode-equity` is pressed and the legal-entity
selector is shown; operator production is a separate, explicitly-labelled toggle
(`#mode-operator`), never sharing a chart series, axis, or total with the equity view, and
retaining its existing retrospective-attribution caveat unchanged. Switching mode never carries a
selection across — each mode's selector starts empty unless the URL names an entity for that mode.
Legal-entity names are used and displayed exactly as recorded by NSTA (label:
`"Legal entity as recorded by NSTA"`, never "parent company", "corporate group", or "ultimate
owner"), listed in deterministic alphabetical order with no grouping or fuzzy reassignment.

**Coverage-state display.** Every stream-month renders one of three states, read from the artifact
(never hardcoded): `complete` (≥99.5%, value + coverage shown, icon `✓`), `warning` (≥95%, <99.5%,
value shown plus a visible textual explanation naming the actual coverage % and that some producing
field volumes were excluded because current equity interests could not be resolved), `unavailable`
(<95%, rendered as "Not available" — never a numeric zero — and as a genuine gap in the chart line,
via ECharts `connectNulls: false`). Status is communicated by icon + text together, never colour
alone. Two streams in the same period can independently carry different statuses (verified in the
committed tests using a synthetic month where oil/associated gas are `unavailable` while dry
gas/condensate are `complete`, since no month in the live published data currently falls below 95%).

**MURLACH.** Its excluded production affects coverage exactly as already encoded in the artifacts —
nothing about the calculation changed. The frontend does not use `company.fields` to decide whether
to show the MURLACH note (that list only ever contains RESOLVED field-months, and MURLACH's are
always `future_only`, so it never appears there for any company, holders included). Instead
`equity-ui.js`'s `isMurlachAffected()` fetches MURLACH's own `fields/{slug}.json` and checks whether
the company's exact name appears in its `ownership_intervals` — a small, cached, purely data-driven
lookup with no hardcoded company names. When affected, the panel shows the exact required text:
*"Some recent production is excluded because NSTA records MURLACH production before the effective
date of its available equity interests."*, labelled "Unresolved source-data case", linking to
`methodology.html`. The frontend does not speculate about the 2050 effective date.

**Field ownership.** The existing field panel gained a Production/Ownership tab pair;
`fields/{slug}.json` is fetched only when the Ownership tab is opened. It shows legal entity,
interest %, effective from/to (open-ended intervals show "Current", never a fabricated end date),
operator flag (labelled explicitly as source metadata only, never implying equity), field-match
method, and excluded/unresolved periods. Zero-interest rows (0% economic interest, a real dated
interval) are shown but visually and textually distinguished (`.zero-interest-badge`). Zero-duration
rows (`start_date === end_date` — source event records, not ownership periods) never render as
ownership rows; they appear only inside a collapsed `<details>` block labelled "N source event
record(s) (not ownership periods)".

**Search and URL state.** A single global search box covers fields, equity legal entities, and
current operators (closing the Phase 1 closeout note that field search was unfinished),
deterministic case-insensitive substring matching only, each result explicitly typed (Field / Legal
entity / Operator), full keyboard operation (ArrowUp/Down/Enter/Escape, ARIA
combobox/listbox/activedescendant). Selected field/entity/operator, metric mode, and stream are
encoded in `location.hash` via `history.replaceState` (no full reload on ordinary interaction, no
internal file paths in the URL, `/ukcs/` subpath-safe since `location.pathname` is never touched).
An invalid or stale slug in the URL shows a specific, named error in the existing status banner and
leaves the rest of the site usable — it never crashes silently or guesses.

**Error isolation.** The equity startup fetch (`meta.json` + `index.json`) is wrapped in its own
try/catch in `main.js`, separate from the production-map startup fetch: a failure there surfaces in
a dedicated `#equity-status-banner`, and the map, field search, and operator view all remain fully
usable. Company-file, field-file, and malformed-JSON failures are each caught and shown with their
real failure category (`DataLoadError` distinguishes network/HTTP/parse failures, matching
`state.js`'s existing discipline) — never a guessed message, never a silent fallback to zero.

**Tests.** `tests/frontend/` is a new, committed, CI-compatible pytest + Playwright suite (31 tests,
its own GitHub Actions workflow, `.github/workflows/frontend-tests.yml`, confirmed green on a real
run, not just locally) that runs the real `docs/app/*.js` modules against small synthetic fixtures
under `tests/frontend/fixtures/` — including a deliberately synthetic below-95%-coverage month, since
the live published data currently has none, so the `unavailable` path would otherwise be untestable.
maplibre-gl and echarts are replaced with small hand-written stub files (no live CDN fetch, no
sandbox-only cached bytes); the suite asserts zero requests to any NSTA/ArcGIS/blob-storage host on
every interaction path. Coverage includes: lazy-loading (no startup preload of company/field files),
distinct legal entities, equity-as-default metric, mode/caveat separation, all three coverage
statuses including same-month divergence across streams, the MURLACH note (both presence for a real
recorded holder and, separately, absence for a company with no recorded interest — proving it's
data-driven, not unconditional), methodology linking, typed search results, URL-state round-trip and
invalid-slug handling, keyboard search operation, six distinct fetch-failure categories (equity meta,
equity index, missing company file, missing field file, malformed JSON — each isolated from the rest
of the site), and deterministic re-rendering. `tests/test_*.py` (the existing 159 ETL tests) are
unaffected and still pass; `build-data.yml`'s test step now excludes `tests/frontend` (different
dependencies — Playwright/Chromium — and a different concern) rather than importing it and failing.

**Performance** (measured locally: `docs/` served over plain HTTP, MapLibre/ECharts/OSM-tile bytes
served from cached copies of the real CDN responses via request interception, since this sandbox
cannot sustain direct outbound HTTPS to arbitrary hosts — **not a substitute for a real GitHub Pages
CDN measurement**, which this checkpoint could not perform: doing so would require deploying to
`main`, which was not authorized during this checkpoint; see Deviations below):
`domContentLoaded` ≈ 324 ms, `load` ≈ 326 ms, 41 requests and ≈1.81 MB transferred by the time
startup settles (real production `fields.geojson`/`history/index.json` plus the full MapLibre
bundle and OSM tiles for the initial view — `equity/index.json` alone is 113 KB, `equity/meta.json`
1.3 KB), and 332 ms from filling the equity company selector to the panel's data table being
present in the DOM (includes the company-file fetch, the MURLACH-interval check fetch, and ECharts'
first render). All comfortably under the existing 3-second cold-cache reference from Phase 1,
though that reference and this measurement are not directly comparable (different network
conditions) — see Deviations.

**Deviations from full compliance with this checkpoint's instructions, reported explicitly:**

- **No live GitHub Pages verification was performed.** The standing branch policy prohibits pushing
  to any branch other than `claude/ukcs-equity-production-tyjna2`, and merging to `main` — required
  for an actual GitHub Pages deployment — was not authorized during this checkpoint. Verification was
  instead done via a real browser (Playwright/Chromium), real static file serving, and cached real
  CDN response bytes with zero mocking of application logic — the strongest available substitute
  short of a live deployment, but not the live deployment itself. Live GitHub Pages verification
  (equity selector, panel loading, operator/field views, ownership lazy-load, MURLACH warning,
  coverage display, methodology link, URL-state sharing, console/network cleanliness, cold-cache
  performance) remains outstanding and needs either explicit authorization to merge, or a separate
  Pages-preview mechanism this project does not currently have.
- Performance figures above are from local static serving with cached CDN bytes, not a live CDN —
  reported as an approximation, not a substitute for the required live measurement.

**Not done, deliberately, matching this checkpoint's constraints:** no parent-company mapping or
legal-entity merging was added; no boe/d figure was added to the equity view (the existing map-only
boe/d sizing convention is untouched); the March 2013 publication start and the 95%/99.5%
thresholds are unchanged; no new external data source was added; interval-resolution policy is
unchanged.

**Status: the company equity view, coverage display, field ownership detail, methodology linking,
global search, and URL state all work and are covered by a real, CI-green test suite.** Live GitHub
Pages verification is the one explicitly outstanding item, for the branch-policy reason stated
above — not a defect in the implementation, but a deployment-authorization gap this checkpoint could
not close on its own.

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
