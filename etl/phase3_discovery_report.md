# Phase 3 Discovery Report

**Status: discovery only — not approved for implementation.** This document reports findings and
proposes options. No code was changed, no calculation was implemented, no conversion factor was
selected, no data was ingested, no company groups were created, and no frontend behaviour was
altered while producing it. `etl/build.py` and `docs/data/*` are untouched.

**Date:** 2026-09-10
**Scope:** five proposed workstreams (A–E) toward a Phase 3 product direction: production-unit
aggregation to mboe/d, a new default production-analysis view, company grouping, field-determination
polygons, and licence-portfolio mapping.

**Method:** live, read-only queries against the real NSTA ArcGIS Online services (the same class of
GET-only, no-write access this project's `etl/discover.py` and `etl/arcgis.py` already use),
inspection of the already-published `docs/data/*` artifacts, and a search of this repository's
existing conventions. All figures below are from live responses captured during this discovery
session; raw responses are not committed (see "Evidence" note at the end of each workstream) but
every number is reproducible by re-running the same query.

---

## 1. Conversion-factor comparison and recommendation (Workstream A)

### 1.1 What already exists in this repository

`docs/app/map.js` already computes a derived `boe_d` figure, but **only for map-marker sizing**,
never for any reported value:

```js
const GAS_MSCF_PER_BOE = 5.8;
```

This is the only conversion factor anywhere in the codebase. `UKCS_DESIGN_v2.md` section 8.4
explicitly restricts it: *"A derived `boe_d` may be shown in the UI only if it is computed in the
frontend, the conversion factor is a named constant in one place, and the UI displays the
factor used."* No document in this repository explains **why** 5.8 was chosen, and no NSTA source
is cited for it. 5.8 numerically coincides with a commonly quoted average heat content for crude
oil (≈5.80 MMBtu/bbl) — it looks like that oil-side figure was reused directly as the Mscf-per-boe
ratio, which is only correct if natural gas is assumed to carry almost exactly 1.0 MMBtu/Mcf. That
assumption is never stated. **This existing constant is itself undocumented in the sense section
8.4 warns against**, and should not be carried forward into a reported (non-decorative) production
figure without re-deriving it properly.

### 1.2 What NSTA's own PPRS source records about gas units

The live PPRS points layer (`etl/schema_snapshot.json`, confirmed again live this session) carries
gas volumes as `AGASPROMMS` / `DGASPROMMS` (MMscf/d — the fields this project already uses) but
**also** carries, for a subset of gas sub-streams, real per-field-month **density** and **calorific
value** fields NSTA itself reports:

| Field | Meaning | Covers |
| --- | --- | --- |
| `AGASPRODEN`, `DGASPRODEN` | Associated/dry gas production density (kg/sm3) | produced gas |
| `GASPIPCV` | Gas to pipeline — calorific value (MJ/sm3) | pipeline gas only |
| `GASPIPDENS` | Gas to pipeline — density (kg/sm3) | pipeline gas only |
| `GASINJCV` | Gas injected — calorific value (MJ/sm3) | injected gas only |

Live sample (latest period, 202606, five real fields):

| Field | `GASPIPCV` (MJ/sm3) | `GASPIPDENS` (kg/sm3) |
| --- | --- | --- |
| AFFLECK | 45.28 | 0.886 |
| ANDREW | 42.32 | 0.842 |
| ARBROATH | 64.26 | 1.273 |
| ARKWRIGHT | 64.09 | 1.269 |
| ARRAN | 43.27 | 0.825 |

**Finding: real calorific value varies by ~50% across fields in a single period** (42.3–64.3
MJ/sm3). This is a genuine, source-confirmed methodological risk (see section 9): a single
universal conversion constant necessarily discards real, NSTA-reported field-to-field variation in
gas energy content. It is also **not a usable basis for a uniform per-field conversion** on its
own, because `GASPIPCV`/`GASINJCV` only cover the pipeline and injected sub-streams, not flared,
vented, or the produced-gas total the ETL currently reports (`AGASPROMMS` + `DGASPROMMS`) —
building a per-field-month energy-content factor from this data would require estimating CV for
gas that was flared or vented, which NSTA does not report a calorific value for. A single named,
documented constant — not a per-field-month calculation — remains the only approach that avoids
either silently guessing at missing CV data or overstating the precision of what is actually
measured.

### 1.3 Comparison of conventions

Both required conventions, applied to the fixed reference volumes, using this project's existing
`m` = thousand convention (matching `oil_mbd` = thousand barrels/day, so `mboe/d` = thousand
barrels-of-oil-equivalent per day):

| Convention | Basis | Mscf per boe | 1 MMscf/d → mboe/d | 1,000 MMscf/d → mboe/d |
| --- | --- | --- | --- | --- |
| Industry convention | 6,000 scf/bbl (a round, widely used rule of thumb, not tied to any specific gas composition) | 6.000 | 0.166667 | 166.667 |
| Energy-content convention | US EIA published average heat content: crude oil 5.80 MMBtu/bbl; natural gas 1.036 MMBtu/Mcf (EIA Monthly Energy Review, Appendix A, heat content tables — the two "explicitly documented source values" this workstream asked for) → 5.80 ÷ 1.036 × 1,000 = 5,598 scf/bbl | 5.598 | 0.178635 | 178.635 |
| *(for context only)* existing undocumented frontend constant | `GAS_MSCF_PER_BOE = 5.8` (map.js, marker sizing only, no cited source) | 5.800 | 0.172414 | 172.414 |

The three conventions differ by up to ~7% at 1,000 MMscf/d (166.7 vs 178.6 mboe/d) — not
negligible for an investor-relations comparison tool, where a reader may directly compare this
site's total mboe/d against a company's own reported boe/d (which itself may use yet another
in-house factor).

### 1.4 Assessment for an investor-relations comparison tool

- **6,000 scf/boe** is the convention most companies and analysts will recognise on sight — it is
  the de facto market convention, not because it is more physically accurate, but because it is
  what published company boe/d figures are usually built on. Using it maximises comparability with
  numbers a reader already has in front of them from other sources.
- **The energy-content convention** is more defensible as a physical quantity (a boe/d figure that
  actually represents comparable energy content between oil and gas), and has a citable, documented
  source (EIA heat-content tables) rather than an internal assumption. But it is a **less familiar**
  number to the target audience, and — as section 1.2 shows — the "true" field-level energy content
  varies enough that even this improved constant is still a simplification, just a more honestly
  documented one.
- **Recommendation:** favour the **6,000 scf/boe industry convention** as the primary, displayed
  figure, precisely because comparability with third-party company-reported boe/d is this tool's
  stated purpose (an investor-relations comparison tool) — but display the constant used
  prominently (matching the existing UI legend's own stated principle) and, if feasible, ideally
  offer the energy-content figure as a documented, labelled secondary/toggle option rather than
  silently picking one. This is a recommendation for the approval decision below, not an
  implementation.

### 1.5 Proposed named constant (not implemented)

```js
// PROPOSAL ONLY - not implemented, not approved.
const SCF_PER_BOE = 6000; // industry convention; see phase3_discovery_report.md section 1
```

No code implements this. The final choice, its exact documented source citation, and the constant's
name are listed as an unresolved decision requiring approval (section 12).

**Evidence:** live queries against
`https://services-eu1.arcgis.com/OZMfUznmLTnWccBc/arcgis/rest/services/UKCS_hydrocarbon_field_production_reports_PPRS_points_(WGS84)/FeatureServer/0`
(`GASPIPCV`/`GASPIPDENS`/`AGASPRODEN`/`DGASPRODEN` field presence and sample values, period
`202606`), `etl/schema_snapshot.json` (already-committed field catalogue), `docs/app/map.js` and
`UKCS_DESIGN_v2.md` section 8.4 (existing constant and its documented scope).

---

## 2. Derived-production data model (Workstream B)

### 2.1 Where each derived value should be generated

| Value | Recommended layer | Why |
| --- | --- | --- |
| `liquids_mboed` (oil + condensate) | **ETL** (`etl/transform.py` / `etl/build.py`), written into artifacts | Pure unit-preserving addition of two already-fetched native-unit fields (`oil_mbd` + `condensate_mbd`); no conversion factor involved, no ambiguity, cheap to compute once at build time rather than on every page load |
| `natural_gas_mboed` (dry gas + associated gas, converted) | **ETL**, written into artifacts, **only after** the conversion factor in Workstream A is approved | Requires the approved constant; computing this per-request in the browser would mean the constant lives in two places (frontend `PRODUCTION_STREAMS`-equivalent and any future comparison logic) and risks drifting the way `GAS_MSCF_PER_BOE` already has from being undocumented — ETL-derived and written once is safer and matches this project's existing rule (section 8.4) that a derived figure must have its factor in exactly one place |
| `total_mboed` (liquids + natural gas) | **ETL**, same artifact write | Trivial sum of the two values above; computing it anywhere else would risk a rounding or timing mismatch between the parts and the total |

**Recommendation: derive all three in the ETL, not the frontend.** This mirrors the existing
project discipline (production math belongs in Python where it can be tested, validated, and
computed exactly once against a single source of truth) rather than the exception carved out in
section 8.4 for the *display-only* `boe_d` marker-sizing figure, which was deliberately
frontend-only **because it was never meant to be a reported number** — the new `liquids_mboed` /
`natural_gas_mboed` / `total_mboed` values are explicitly proposed as reported, compared, filtered
figures (requirement 4: "Total production in mboe/d... Split by Liquids / Natural gas... Split by
company... Split by field"), which is a materially different bar than a marker's pixel radius.

### 2.2 Where in the current schema this would land

Inspected live (current `docs/data/` on `main`, commit `8a4fc35`):

- `docs/data/fields.geojson` (`properties`) — latest-period, per-field. Adding `liquids_mboed`,
  `natural_gas_mboed`, `total_mboed` here is the natural extension point for a map-based total/split
  view; it already carries `oil_mbd`, `condensate_mbd`, `assoc_gas_mmscfd`, `dry_gas_mmscfd` per
  field for the latest period only.
- `docs/data/history/{slug}.json` (`series[]`) — full monthly history per field. Adding the three
  derived fields to each `series` entry is the natural extension point for the field-history chart
  requirement.
- `docs/data/operators.json` / `docs/data/operators/{slug}.json` — same shape as field history,
  per operator; same extension point, same caveat as the rest of the operator view (retrospective
  attribution — see spec section 6.1, unaffected by this).
- `docs/data/equity/companies/{slug}.json` — **materially different shape**: each stream entry is
  already `{value, status, coverage_pct}`, not a bare number, because of the equity publication
  window and coverage-state policy (spec section 15.11/15.12). A derived `liquids_mboed` here would
  need its **own** coverage-state derivation — if oil's status is `warning` and condensate's is
  `complete` in the same period, what status does the combined `liquids_mboed` carry? This is not a
  simple sum-of-values question and needs its own explicit rule (see section 2.4) before any
  equity-side implementation, which is why this discovery treats the equity artifacts as a distinct,
  harder sub-problem from the plain production artifacts above.

### 2.3 ETL-derived vs frontend-calculated — explicit comparison

| | ETL-derived (recommended) | Frontend-calculated |
| --- | --- | --- |
| Single source of truth for the constant | Yes — one Python constant, covered by existing test discipline | No — would need to live in `docs/app/*.js`, duplicating the ETL's discipline in an unrelated language with a separate (thinner) test setup |
| Testability | Directly, with the existing `tests/test_*.py` pattern (deterministic, network-free) | Would need new Playwright-level tests per numeric case, more expensive to assert precisely |
| Conservation/validation at build time | Possible — a build-breaking check can assert `total_mboed == liquids_mboed + natural_gas_mboed` for every row before writing, mirroring the existing E1/E7/E8-style validation in `etl/validate.py` / `etl/equity_artifacts.py` | Not possible to validate at build time; a bug would only surface live, in the browser |
| Artifact size | Three more numeric fields per period per field/company/operator (see 2.6) | No artifact growth, but shifts the same computation to every page load, redundantly, for every viewer |
| Consistency with existing `boe_d` exception | Deliberately diverges from it (2.1 explains why the exception doesn't apply here) | Would extend the *display-only, never-reported* exception to a genuinely reported figure, which section 8.4 does not sanction |

### 2.4 Required metadata

- The exact conversion constant and its source citation (Workstream A, once approved) must be
  recorded in the same way `EQUITY_MINIMUM_COVERAGE_PCT` etc. are recorded in `etl/equity_config.py`
  — a single named Python constant, referenced from one place, and echoed into `meta.json` so the
  frontend can display which factor produced the number it's showing (matching the existing
  `equity/meta.json` pattern of publishing policy constants alongside the data they governed).
- For the **equity-artifact** case specifically: a documented rule for combining `{value, status,
  coverage_pct}` triples into a single derived triple. The two candidate rules are (a) the combined
  status is the **worst** of the component statuses (a genuinely conservative combination — if
  either input is `warning`/`unavailable`, so is the combined figure), or (b) `liquids_mboed`/
  `natural_gas_mboed` are only published when **all** contributing streams are individually
  `complete` for that period, else `unavailable`. Neither is implemented; this is listed as an
  unresolved decision (section 12).

### 2.5 Conservation tests (to design, not implemented)

- `liquids_mboed == oil_mbd + condensate_mbd` exactly, for every row, every artifact — a direct
  unit-preserving sum, no tolerance needed (unlike the gas conversion, this involves no conversion
  factor and no rounding risk).
- `total_mboed == liquids_mboed + natural_gas_mboed` exactly, for every row — same reasoning.
- `natural_gas_mboed` reproducible from `dry_gas_mmscfd + assoc_gas_mmscfd` and the published
  constant, within a small explicit tolerance if intermediate rounding is applied (see 2.6) —
  mirroring the existing `EQUITY_ROW_COUNT_TOLERANCE_FRACTION`-style explicit, named tolerance
  rather than an implicit one.
- Company-to-field and operator-to-field conservation (the existing pattern already validated for
  equity artifacts in `tests/test_equity_artifacts.py`) would need a parallel check: does a
  company's/operator's aggregate `total_mboed` equal the sum of its contributing fields'
  `total_mboed` for the same period? This is a new test class, not an extension of an existing one,
  because plain production artifacts do not currently carry any company/field conservation
  assertion at all (only the equity side does, because equity is the only place fractional
  ownership makes conservation non-trivial).

### 2.6 Rounding policy (undecided — flagged, not resolved)

Not currently specified anywhere in this repository for any numeric field (existing `oil_mbd` etc.
are stored at full source precision). Two options for the new derived fields: (a) full precision,
consistent with every other numeric field currently published, or (b) a fixed number of decimal
places for the specifically *derived, converted* fields, to avoid implying more precision than a
single blended conversion constant actually supports. This is listed as an unresolved decision
(section 12) rather than assumed.

### 2.7 Impact on company, field and operator artifacts / expected size change

Estimated field-by-field addition, based on the live artifact sizes:

- `docs/data/fields.geojson` (87,620 bytes live, 250 features, latest period only): +3 numeric
  fields per feature ≈ +8–10% file size.
- `docs/data/history/{slug}.json` (per field, one file per field, average series length varies):
  +3 numeric fields **per monthly entry**, so the relative growth is similar per-file but the
  aggregate growth across all ~552 history files is larger in absolute bytes than the single
  `fields.geojson` file, since history carries full time series rather than one period.
- `docs/data/operators.json` / `operators/{slug}.json`: same shape as history, same relative growth.
- `docs/data/equity/companies/{slug}.json` (292 files) and `docs/data/equity/index.json`
  (113,350 bytes live): growth here depends entirely on the unresolved combined-status rule (2.4) —
  if each derived stream also needs its own `{value, status, coverage_pct}` triple, the relative
  growth is larger (three extra sub-objects, not three extra numbers) than the plain production
  artifacts.

No artifact was measured with derived fields actually added (none exist yet); the estimates above
are proportional projections from the current schema, not measurements of a real change.

**Evidence:** live `docs/data/fields.geojson`, `docs/data/history/*.json`,
`docs/data/equity/index.json`, `docs/data/equity/companies/*.json` on `main` (commit `8a4fc35`);
`etl/equity_artifacts.py` and `tests/test_equity_artifacts.py` for the existing conservation-test
pattern this section extends.

---

## 3. Company-grouping inventory and proposed schema (Workstream C)

### 3.1 Inventory across sources

| Source | Distinct legal-entity-like names |
| --- | --- |
| Equity artifacts (`docs/data/equity/index.json`, live) | 292 |
| Operator artifacts (`docs/data/operators.json`, live) | 50 |
| Licence subareas-by-equity `EQORG` (live NSTA query, see 3.3) | 147 |
| Licence subareas (all) `LICORG` (live NSTA query) | 156 |
| **Union across all four sources** | **369 distinct names** |
| Equity-artifact names found verbatim in licence `EQORG` | 124 / 292 (exact string match only) |
| Equity-artifact names found verbatim in licence `LICORG` | 129 / 292 (exact string match only) |

The exact-string overlap being well under 292/292 is expected and not itself a problem: the equity
artifact spans the full `201303`–present publication window (including legacy entities no longer
holding any current licence interest), while the licence datasets are current-state snapshots; and
minor punctuation/suffix differences (`LIMITED` vs `LTD`, `(U.K.)` vs `UK`) will suppress exact
matches even for the same real entity. No fuzzy reconciliation was attempted, per instruction.

### 3.2 NSTA already maintains its own current-group taxonomy — a major finding

The live `UKCS offshore petroleum licence subareas by equity group holder (WGS84)` dataset carries
an `EQGRPHOLD` ("Equity group holder") field **alongside** the individual legal entity names in
`EQORG`. Reconstructing the entity→group pairing precisely (matching each row's `EQUITY` percentage
against the specific name in `EQORG` it corresponds to — necessary because a subarea's row is
repeated once per holder, and each repeat lists *every* co-holder in `EQORG` but only *one*
`EQGRPHOLD`) resolved cleanly for 130 of 147 distinct equity-holding entities (488 of 1,803 rows
were unresolvable this way, purely because some subareas split equity in exact ties — e.g. two
holders at 50%/50% — where percentage alone cannot disambiguate which name the row's `EQGRPHOLD`
refers to; this is a limitation of this discovery's reconstruction method, not evidence of
ambiguity in NSTA's own data). Every entity that *did* resolve mapped to **exactly one** group —
zero entities appeared under more than one `EQGRPHOLD` value once the percentage-matched pairing
was used correctly, i.e. **NSTA's live current-state grouping is internally consistent** over the
population this method could resolve.

Largest resolved groups (live, current data):

| `EQGRPHOLD` | Member legal entities (count) |
| --- | --- |
| NEO NEXT+ ENERGY | 22 |
| HARBOUR ENERGY PLC | 15 |
| ITHACA ENERGY | 12 |
| SPIRIT ENERGY | 6 |
| SERICA ENERGY | 6 |
| SHELL PLC | 4 |
| ROCKROSE ENERGY | 4 |
| PERENCO OIL & GAS | 3 |
| BP EXPLORATION | 3 |
| BRIDGE PETROLEUM GROUP | 3 |

**Implication:** any future grouping work should treat NSTA's own `EQGRPHOLD` values as a primary,
authoritative **source** for the "grouping basis" and "source" fields in the schema below — not
something this project needs to invent from scratch by name-similarity heuristics. It only covers
entities currently holding licence equity (147 of the equity artifact's 292), so it cannot cover
the whole population on its own, and it is (like `subareas_equity` generally) **current-only** — it
carries no historical grouping.

### 3.3 Obvious related-name clusters (illustrative, not exhaustive, not applied)

Beyond the NSTA-sourced groups above, plain prefix clustering on the equity artifact's 292 names
(no fuzzy matching, exact shared-prefix only, already reported in an earlier checkpoint of this
project) shows clusters like `BP EXPLORATION (ALPHA) LIMITED` / `BP EXPLORATION (EPSILON) LIMITED`
/ `BP EXPLORATION (PSI) LIMITED` / `BP EXPLORATION BETA LIMITED` / `BP EXPLORATION OPERATING
COMPANY LIMITED`, or `HARBOUR ENERGY CNS (I) LIMITED` / `HARBOUR ENERGY CNS (II) LIMITED` /
`HARBOUR ENERGY OPERATIONS LIMITED` / `HARBOUR ENERGY WPUK LIMITED`. These are **obvious** clusters
in the sense that a human reviewer would immediately recognise them, but "obvious to a human" is
exactly the boundary this project's no-fuzzy-matching discipline exists to enforce — they must
still go through the reviewed-schema process below, not an automated prefix rule.

### 3.4 Ambiguous clusters and entities that must not be grouped automatically

- Numbered/suffixed shell entities (`BRIDGE PETROLEUM 1 LIMITED`, `...3 LIMITED`, `...5 LIMITED`;
  `CHRYSAOR (U.K.) ALPHA/BETA/SIGMA/THETA LIMITED`) look mechanically groupable by prefix, but
  prefix similarity alone cannot distinguish "same group, different special-purpose vehicle" from
  "coincidentally similar name, different group" without a corroborating source (NSTA's own
  `EQGRPHOLD`, in these two examples, does confirm the grouping — but that corroboration must be
  checked per-entity, not assumed from the name shape).
  Case in point: the two apparently identical Perenco names split into **exactly** the pattern this
  project's Phase 1/2 "no fuzzy matching" rule exists to prevent someone from getting right by luck
  and wrong by inference elsewhere — `PERENCO GAS (UK) LIMITED` and `PERENCO NORTH SEA LIMITED` and
  `PERENCO UK LIMITED` are confirmed (via `EQGRPHOLD`) to be one group ("PERENCO OIL & GAS"), but
  nothing in the *name itself* distinguishes that from, say, the `BP EXPLORATION` cluster, where
  `ARCO BRITISH LIMITED, LLC` — a name with **no lexical resemblance to "BP" at all** — is also
  confirmed to be part of the same group by the same source. **Name similarity is neither necessary
  nor sufficient evidence of common grouping** — this is the single clearest piece of evidence this
  discovery found for why grouping must be sourced, reviewed, and dated, never inferred from
  spelling.
- Entities appearing in `subareas_equity` but **not** resolvable to a single group by this
  discovery's method (the 488 tied-percentage rows) must not be auto-assigned a group by falling
  back to a guess — they need either a better disambiguation source (if one exists) or manual
  review.
- Legacy/renamed entities present only in the equity artifact's full publication history (post-2013
  legal entities with no current licence interest at all) have **no** NSTA current-group signal to
  check against, and must not be grouped by inferring today's group from a similar-sounding
  currently-active entity.

### 3.5 Proposed reviewed mapping schema (proposed only, not created)

```
{
  "source_legal_entity": "PERENCO GAS (UK) LIMITED",
  "display_group": "Perenco",
  "valid_from": "2013-03",
  "valid_to": null,
  "grouping_basis": "nsta_equity_group_holder",
  "source": "UKCS offshore petroleum licence subareas by equity group holder (WGS84), item bef... (EQGRPHOLD field), retrieved 2026-09-10",
  "reviewed_by": null,
  "reviewed_on": null
}
```

Field notes:
- `source_legal_entity` — exact string as recorded by NSTA, never altered (matches the existing
  equity-frontend discipline of never normalising a legal-entity display string).
- `display_group` — the curated, human-facing group name; may differ from `EQGRPHOLD`'s exact
  casing/wording if a cleaner display form is preferred, but must record its provenance.
- `valid_from` / `valid_to` — the period range over which this specific entity→group assignment is
  asserted to hold, explicitly bounded, `null` `valid_to` meaning "still current." This is the field
  that makes the mapping capable of holding more than one row per entity over time, rather than
  collapsing an entity's whole history into today's group (see 3.6).
- `grouping_basis` — a closed vocabulary (e.g. `nsta_equity_group_holder`,
  `nsta_licensee_organisation_group`, `manual_review`), never free text, so every row's evidentiary
  strength can be audited in bulk.
- `source` — a specific, dated citation (an NSTA item ID and field name, or a named reviewer's
  note), not a vague "NSTA" or "public records."
- `reviewed_by` / `reviewed_on` — who approved this specific row and when, since this is exactly the
  kind of curated judgement call that must not be silently regenerated on a later build the way
  `field_aliases.csv` already is not silently regenerated (it is a reviewed, committed, manually
  maintained file, and this proposed mapping should follow the same discipline).

### 3.6 Legal entity vs corporate group at the time vs current display group

These are three genuinely different things, and this project has so far only ever displayed the
first:

- **Legal entity as recorded** — the exact string NSTA publishes for a specific period. This is
  what the equity frontend checkpoint's entire "no parent-company mapping" discipline protects, and
  is the only thing currently shown anywhere in this product.
- **Corporate group at the time** — which higher-level group a legal entity actually belonged to
  *during the period being displayed*. NSTA's `blocks_history` layer (Workstream E, section 5)
  shows real evidence that this is not static: e.g. a real block (`9/11`, licence `P335`) shows
  `OPHISNAMES` transitioning from `UNOCAL EXPLORATION AND PRODUCTION COMPANY (U.K.) LIMITED` to
  `UNOCAL UK LIMITED` to (in the live *current* `OPORG` for the same block) `CHEVRON BRITAIN
  LIMITED` — the same underlying registered company (number `01006065`) renamed across a real
  corporate acquisition, all within licence data this project could ingest.
- **Current display group** — a group assignment as of *today*, which is the only kind of grouping
  the proposed schema (3.5) or NSTA's own `EQGRPHOLD` snapshot can currently source with any rigor.

### 3.7 The historical-distortion risk of applying current groups retrospectively

Applying today's `display_group` to a historical production figure would silently rewrite history:
using the example above, a barrel produced by "UNOCAL EXPLORATION AND PRODUCTION COMPANY (U.K.)
LIMITED" in 2003 would, under a naive current-group rollup, be attributed to "Chevron" — a company
that did not exist under that ownership structure at the time, and had no claim on that production
when it happened. This is the exact same distortion this project's existing operator view already
carries an explicit, displayed caveat for (`RETROSPECTIVE_CAVEAT` in `docs/app/main.js`: "This
series attributes a field's ENTIRE production history to whichever company operates it today").
Any company-group feature that aggregates historical production **must** either (a) use the
period-appropriate group via `valid_from`/`valid_to`, which requires actually reconstructing
historical group membership (Workstream E shows this is only reliably possible for
licensee/operator *names*, not equity *percentages* — section 5.6), or (b) carry the same kind of
explicit, undismissable caveat the operator view already uses, naming this exact limitation.

**Evidence:** live queries against `docs/data/equity/index.json` (main, commit `8a4fc35`),
`docs/data/operators.json` (main), and the live
`UKCS offshore petroleum licence subareas by equity group holder (WGS84)` service (item
`40c65d96a1a14da8b066f2abbb345fed`, layer 0, `EQORG`/`EQGRPHOLD`/`EQUITY` fields, all 1,803 rows
retrieved, `resultRecordCount=2000` in a single page, no pagination needed); `blocks_history` sample
rows cited in section 5.

---

## 4. Field-polygon source assessment (Workstream D)

### 4.1 Item resolution

Searched `https://www.arcgis.com/sharing/rest/search` for `"UKCS petroleum field determinations"`
(the same public ArcGIS Online search endpoint `etl/discover.py`'s `resolve_service_url` already
uses to resolve items by ID — the search step itself is new to this discovery, since the item ID
was not previously known).

| | Value |
| --- | --- |
| Item ID | `bef8788b07464a7f8a18a18eb638b9f5` |
| Title | UKCS petroleum field determinations (WGS84) |
| Owner | `NSTA_GIS` |
| Type | Feature Service |
| Service URL | `https://services-eu1.arcgis.com/OZMfUznmLTnWccBc/arcgis/rest/services/Petroleum_field_determinations_(WGS84)/FeatureServer` |
| Layer | `0` — `PETROLEUM_FIELDS_DETERMINATIONS_WGS84_PROD` |
| Licence | NSTA Open User Licence (same licence family already recorded for PPRS and Field Partners) |

A companion ETRS89 item (`c8abfafcf08d428ca6104da20a98160a`) exists but WGS84 matches this
project's existing convention (the PPRS points/polygons layers and every prior discovery in this
project were resolved as WGS84) and is the one this section evaluates.

### 4.2 Schema, geometry, capabilities

| | Value |
| --- | --- |
| Geometry type | `esriGeometryPolygon` |
| Spatial reference | WGS84 (wkid 4326) |
| `maxRecordCount` | 2000 |
| `supportsPagination` | `null` (same undefined-flag situation section 3.3 of the main spec already found for PPRS — paginate defensively, never assume the flag) |
| `supportsStatistics` | `true` |
| `supportedQueryFormats` | JSON, geoJSON, PBF |
| Record count | **344** (confirmed via `returnCountOnly=true`; matches the single-page `resultRecordCount=2000` fetch exactly, no pagination required) |
| Attribute fields | `OBJECTID`, `FIELD_NO` (field number, string), `FIELDNAME` (string), `FD_STAT` (coded-value domain: `PROPOSED` / `CURRENT` / `HISTORIC`) |
| `FD_STAT` distribution (live) | 344/344 rows are `CURRENT` — this WGS84 dataset, as currently published, contains **only** current-status determinations; `PROPOSED`/`HISTORIC` values exist in the domain definition but have zero live rows |

This is a deliberately minimal attribute schema — three real fields beyond `OBJECTID` — carrying
no production, no operator, and no date information. It is purely a boundary + name + status
lookup, meant to be joined against other sources (PPRS field names, licence data) rather than used
standalone.

### 4.3 Match rate against PPRS field names

Computed live: PPRS `FIELDNAME` values from `docs/data/history/index.json` (full history, 552
distinct names) and `docs/data/fields.geojson` (latest period, 250 distinct names), both uppercased
for comparison (the determinations dataset uses Title Case, e.g. "Alwyn North", vs PPRS's ALL CAPS).

| Comparison | Match rate |
| --- | --- |
| All PPRS field names (full history, 552) | 320/552 = **58.0%** |
| Latest-period producing fields (250) | 223/250 = **89.2%** |

The lower full-history rate is expected — many historical PPRS field names correspond to
decommissioned or long-since-merged fields with no current determination polygon. The
latest-period rate (89.2%) is the more relevant figure for a live map feature.

### 4.4 Unmatched and ambiguous names — characterised, not resolved

27 latest-period PPRS field names did not match by exact uppercased string. Manually probing each
against the determination list (still no fuzzy matching — direct substring/parent-name checks only)
splits them cleanly into two categories:

**Category 1 — PPRS reporting-unit sub-parts of a single larger determination (18 of 27).** PPRS
reports at reporting-unit grain (already documented as finer than "true field" grain in spec
section 7); several of these sub-units are legitimately covered by one parent determination
polygon:

| PPRS name (unmatched) | Confirmed parent determination |
| --- | --- |
| `BRAE-CENTRAL [PART OF BRAE]`, `BRAE-SOUTH [PART OF BRAE]` | `Brae` |
| `CLAIR-PHASE 1 [PART OF CLAIR]`, `CLAIR-RIDGE [PART OF CLAIR]` | `Clair` |
| `LEMAN [PERENCO][PT. OF LEMAN]`, `LEMAN [SHELL][PT. OF LEMAN]` | `Leman` |
| `MARNOCK [PT. OF MARNOCK-SKUA]`, `MURLACH [PT OF MARNOCK-SKUA]` | `Marnock-Skua` |
| `LOYAL [PART OF SCHIEHALLION]` | `Schiehallion` |
| `RAVENSPURN N[PT.OF RAVENSPURN]`, `RAVENSPURN S[PT.OF RAVENSPURN]` | `Ravenspurn` |
| `DONAN [MAERSK]` | `Donan` |
| `FORVIE NORTH` | `Forvie` |
| `LOMOND (COLUMBUS)` | `Lomond` |
| `MAGNUS SOUTH` | `Magnus` |

This is the **same** many-reporting-units-to-one-field pattern already documented for PPRS-vs-PPRS
in spec section 7.1/7.3 — it recurs here between PPRS and the determinations dataset, and would need
the same kind of explicit, reviewed alias table this project already uses for equity name matching
(`etl/mappings/field_aliases.csv`), not a fuzzy-matched guess.

**Category 2 — genuinely unmatched, no plausible determination found (9 of 27).**
`BARNACLE`, `BEAUFORT`, `CHANTER`, `GADWALL`, `GALAHAD`, `GUINEVERE`, `IONA`, `MORDRED`, `SALTIRE`.
These fields currently have no `CURRENT`-status determination polygon in this dataset under any
name this discovery could find by direct string/substring comparison. They would need individual
manual review (are they newer fields awaiting determination, satellite tie-backs filed under a host
field's determination, or a naming mismatch not visible from substring comparison?) before any
polygon-matching logic is written.

### 4.5 Comparison with PPRS polygon geometry

The PPRS polygon layer (already recorded in `etl/schema_snapshot.json`'s `polygons_service_url`
from Phase 1 discovery, confirmed live this session at
`.../UKCS_hydrocarbon_field_production_reports_PPRS_polygons_WGS84/FeatureServer`, **layer index
6**, not 0):

| | PPRS polygons (layer 6) | Field determinations |
| --- | --- | --- |
| Record count (live) | **136,789** | 344 |
| Grain | One polygon **per reporting unit per period** (same 46-column production schema as the PPRS points layer, repeated with geometry) | One polygon per **field**, current status only |
| Fit for a formal field outline | No — reporting-unit shaped, and the existing design spec (section 16) already warned this layer is slow to download for exactly this reason, confirmed live: 136,789 rows vs 344 | Yes — this is what the dataset is for |
| Fit for a production-reporting outline (i.e. "what area does this month's number cover") | Yes, in principle — it is genuinely the reporting-unit geometry — but at 136,789 rows it needs deduplication (distinct `UNITNAME` geometries only, not one row per period) before it is usable, and still would not fix the many-units-to-one-field grain problem in section 4.4 | No — carries no production data at all |

### 4.6 Recommendation by use case

| Use case | Recommended geometry |
| --- | --- |
| Formal field outline (the boundary a reader expects when they think "this field") | Field determinations dataset |
| Production-reporting outline (explaining which physical area a given month's PPRS number covers) | PPRS polygons, deduplicated to one geometry per distinct `UNITNAME` — not implemented, and the many-to-one grain problem (4.4) still needs an explicit alias table before this is field-name-joinable |
| Low zoom (regional/UKCS-wide view) | Field determinations — 344 simple polygons (~24 vertices/feature average, see 4.7) render cheaply at low zoom without simplification |
| High zoom (single-field detail) | Field determinations, at full precision — no need for the reporting-unit layer's extra grain once a single field is in view |

### 4.7 Estimated GeoJSON size

Live measurement, not an estimate from row count alone: the full 344-feature determinations
dataset, fetched as GeoJSON with only the three real attribute fields (`FIELD_NO`, `FIELDNAME`,
`FD_STAT`), is **324,067 bytes uncompressed** (≈24 coordinate pairs per feature on average — these
are already generalised/simplified polygons, not survey-grade detail) and **90,254 bytes gzipped**
(a real gzip measurement, not a rule-of-thumb ratio). No further simplification pass was run or
estimated beyond this, since the source geometry is already simple enough that a project-side
simplification step may not be needed at all — this itself is a discovery finding, not an
assumption.

**Evidence:** live queries against
`https://services-eu1.arcgis.com/OZMfUznmLTnWccBc/arcgis/rest/services/Petroleum_field_determinations_(WGS84)/FeatureServer/0`
(schema, `returnCountOnly`, full 344-row GeoJSON fetch, gzip measurement) and
`.../UKCS_hydrocarbon_field_production_reports_PPRS_polygons_WGS84/FeatureServer/6` (schema,
`returnCountOnly`); `docs/data/history/index.json` and `docs/data/fields.geojson` (main, commit
`8a4fc35`) for the PPRS-side field-name comparison sets.

---

## 5. Current licence-portfolio source assessment (Workstream E)

### 5.1 Item resolution (all five requested WGS84 datasets found)

| Dataset | Item ID | Service URL |
| --- | --- | --- |
| UKCS offshore petroleum licences (WGS84) | `e4e489b088b44e29af1c848468403988` | `.../UKCS offshore petroleum licences WGS84/FeatureServer` |
| UKCS offshore petroleum licence blocks (WGS84) | `d01ebe9fe5da45b1a0bb285a7c5b7434` | `.../UKCS offshore petroleum licence blocks WGS84/FeatureServer` |
| UKCS offshore petroleum licence blocks history (WGS84) | `855237fb38bb44b2afc52a3ea4a48903` | `.../UKCS offshore petroleum licence blocks history WGS84/FeatureServer` |
| UKCS offshore petroleum licence subareas (WGS84) | `cd2a3f6929e14bb4b2882fec61ee9d63` | `.../UKCS offshore petroleum licence subareas WGS84/FeatureServer` |
| UKCS offshore petroleum licence subareas by equity group holder (WGS84) | `40c65d96a1a14da8b066f2abbb345fed` | `.../UKCS offshore petroleum licence subareas by equity group holder WGS84/FeatureServer` |

All five: owner `NSTA_GIS`, licence **NSTA Open User Licence** (same licence family as every other
source this project uses), layer index **0** in every case, `esriGeometryPolygon`,
`maxRecordCount` 2000, `supportsStatistics: true`, `supportedQueryFormats: JSON, geoJSON, PBF`,
`supportsPagination: null` (paginate defensively, as this project already does for PPRS).

### 5.2 Per-dataset findings

| Dataset | Record count | Geometry grain | Equity % present | Effective dates present |
| --- | --- | --- | --- | --- |
| Licences | 346 | One polygon per licence | No | `LICSTARTDT`/`LICENDDT`/`LICEXPDT` (licence-level), plus phase/term/round date fields |
| Blocks (current) | 700 | One polygon per currently-active licence block | No | `LICSTARTDT`/`INITENDDT`/`SECENDDT`/`LICENDDT` |
| Blocks history | **8,886** | One polygon per block **per historical licensing episode** (`HISTORY` flag distinguishes historic from current rows) | No | `BLCKSTRTDT`/`BLCKENDDT` **and** `LICHISNAME`/`OPHISNAMES` (historical entity names, see 5.4) |
| Subareas (current) | 900 | One polygon per current subarea | No (`EQORG`/`EQORGGRP` name the org(s) with equity but not the percentage) | Licence-level dates only |
| Subareas by equity group holder | **1,803** | One polygon per (subarea, equity holder) pair — the same subarea geometry repeated once per holder | **Yes** — `EQUITY` (double, percentage) | Licence-level dates only; **no** date range on the equity split itself |

Relevant organisation/operator/equity fields, by dataset:

- **Licences**: `LICORG` / `LICORGGRP` (licensee organisation / group, both multi-value
  comma-joined strings), `SUBOPORG` / `SUBOPGRPS` (subarea operators), `ADMORG` (administrative
  organisation).
- **Blocks / blocks history**: `LICORG`, `LICORGGRP`, `OPORG`, `OPORGGRP`, `ADMORG`, `ADMORGGRP`.
- **Subareas**: `LICORG`, `LICORGGRP`, `OPORG`, `OPORGGRP`, `EQORG`, `EQORGGRP` (equity-holder
  names/groups, no percentage).
- **Subareas by equity group holder**: everything subareas has, **plus** `EQGRPHOLD` (single
  group name for this specific row) and `EQUITY` (single percentage for this specific row) — this
  is the only dataset of the five that carries a real, numeric equity split.

### 5.3 Formats, pagination, licence terms

All five support `JSON`, `geoJSON`, and `PBF` output formats, `maxRecordCount` 2000 per page,
`supportsPagination` reported as `null` on every layer (same defensive-pagination requirement
established for PPRS). All are published under the NSTA Open User Licence.

### 5.4 Real evidence of historical-name reconstruction (blocks history)

`blocks_history` rows for `HISTORY='Y'` carry `LICHISNAME` / `OPHISNAMES` — genuinely different
strings from the row's own current-context `LICORG`/`OPORG`. Live example (block `9/11`, licence
`P335`, two consecutive historical periods on the same block):

| Period | `LICHISNAME` (licensee names, that period) | `OPHISNAMES` (operator name, that period) |
| --- | --- | --- |
| 1980-12 to 1986-12 (`BLCKSTRTDT`/`BLCKENDDT`, epoch ms) | GETTY OIL (BRITAIN) LIMITED (01006065), NORWEGIAN OIL COMPANY D.N.O. (U.K.) LIMITED (THE), ULTRAMAR EXPLORATION LIMITED (00936223), UNOCAL EXPLORATION AND PRODUCTION COMPANY (U.K.) LIMITED | UNOCAL EXPLORATION AND PRODUCTION COMPANY (U.K.) LIMITED |
| 1986-12 to 1991-12 | NORWEGIAN OIL COMPANY D.N.O. (U.K.) LIMITED (THE), TEXACO BRITAIN LIMITED (01006065), ULTRAMAR EXPLORATION LIMITED (00936223), UNOCAL UK LIMITED | UNOCAL UK LIMITED |

Company number `01006065` threads through both periods under two different names (`GETTY OIL
(BRITAIN) LIMITED` → `TEXACO BRITAIN LIMITED`), and the current-state `OPORG` for this same block
today is `CHEVRON BRITAIN LIMITED` — a real, source-confirmed illustration of exactly the
retrospective-distortion risk section 3.7 describes, using an actual company-number thread rather
than a hypothetical.

### 5.5 Estimated artifact sizes

Live measurements, sampled at 200 features and scaled linearly to the full record count (not a
rule-of-thumb — an actual gzip/byte measurement on a real sample of each):

| Dataset | Full record count | Estimated uncompressed GeoJSON |
| --- | --- | --- |
| Subareas by equity group holder | 1,803 | ≈2.60 MB (measured: 200 features / 288,735 bytes, minimal attrs) |
| Blocks (current) | 700 | ≈0.27 MB (measured: 200 features / 76,619 bytes, minimal attrs) |
| Blocks history | 8,886 | ≈3.4 MB (projected from the blocks-layer per-row rate; not separately sampled) |
| Subareas (current, no equity duplication) | 900 | ≈1.3 MB (projected: subareas-by-equity repeats the same subarea geometry once per holder, so the non-duplicated subareas layer should be roughly proportional at ~half the equity layer's per-row count) |
| Licences | 346 | Not sampled directly this session; licence polygons are typically coarser (aggregate of multiple blocks) so likely comparable to or smaller than the blocks layer per feature |

### 5.6 Answers to the five explicit questions

1. **Best dataset for a current company licence-portfolio map:** the **subareas by equity group
   holder** dataset — it is the only one of the five carrying an actual equity percentage per
   holder, at the subarea grain (finer than block, which is what a company-portfolio view actually
   needs to be accurate when a company holds equity in only *part* of a block).
2. **Best dataset for historical portfolio geometry:** **blocks history** — the only dataset with
   real historical name/date reconstruction (`BLCKSTRTDT`/`BLCKENDDT`, `LICHISNAME`/`OPHISNAMES`),
   at 8,886 rows covering real historical licensing episodes.
3. **Can historical company equity be reconstructed at subarea level, or only historical
   licence/operator names?** **Only names, not equity.** `subareas_equity` (the only source with a
   real `EQUITY` percentage) has no historical variant and no effective-date range on the equity
   split itself — it is a current-state-only snapshot. `blocks_history` reconstructs historical
   **names** (licensee and operator) with real date ranges, but never a numeric equity split. This
   is a hard limitation of the source data, not a gap in this discovery.
4. **What cannot be supported reliably from the available sources:** historical equity percentage
   by subarea (per 3 above); a fully reconciled group taxonomy across *all* 292 equity-artifact
   entities (NSTA's own `EQGRPHOLD` only resolves 130 of the 147 entities that currently hold
   licence equity at all, and says nothing about the ~145 equity-artifact entities that hold no
   current licence equity); and disambiguation of the 488 tied-percentage `subareas_equity` rows
   without a source beyond percentage-matching.
5. **Should the product show licence polygons, blocks, or subareas by default?** **Subareas** —
   they are the finest available grain that still carries organisational data (blocks do not carry
   equity-holder detail at all; licences are coarser still, often covering multiple blocks under one
   polygon). A company-portfolio view scoped to "what does this company actually hold equity in"
   needs subarea grain to avoid overstating a company's interest across an entire block when it may
   only hold equity in part of it.

**Evidence:** live item search and per-layer schema/count/sample queries against all five service
URLs listed in 5.1, captured during this discovery session; `subareas_equity` full 1,803-row
attribute fetch (no geometry) for the section 3 entity inventory; 200-feature GeoJSON samples with
geometry for the size estimates in 5.5.

---

## 6. Historical licence-portfolio feasibility assessment

Folded into section 5 above (5.6, question 3) since the live evidence for current and historical
feasibility came from inspecting the same five datasets together: **current** company portfolios,
including a real equity percentage, are well supported by `subareas_equity`. **Historical**
portfolios are supported only at the **name** level (via `blocks_history`'s `LICHISNAME`/
`OPHISNAMES` and real date ranges) — a historical equity-percentage map is not buildable from any
NSTA source discovered so far. Any future historical portfolio feature must be scoped as "who held
what, by name, when" rather than "who held what percentage, when," and must say so explicitly in
the UI rather than implying a precision the source data doesn't have.

---

## 7. New default-view architecture

**Proposal only — no UI was implemented.** Views, in the structure this checkpoint asked for:

| View | Role |
| --- | --- |
| **Production overview** | New **default** view (requirement 5 explicitly demotes the current map to secondary) |
| **Map** | Existing map/marker/field-panel interface, retained, no longer the default landing view |
| **Company detail** | Existing equity company panel (already built, already live) — would gain the new liquids/natural-gas/total split once Workstream B is approved and implemented |
| **Field detail** | Existing field panel (production + ownership tabs, already built) — same split addition |
| **Licence portfolio** | New — not designed in detail here beyond the source assessment in sections 4–6; a genuinely new view, not an extension of an existing one |
| **Methodology** | Existing `methodology.html`, extended (not replaced) to document the new conversion factor once approved, and the licence/polygon source limitations from sections 4–6 |

### 7.1 Production overview — proposed shape (not implemented)

- **Chart type:** a stacked or grouped time-series (Liquids vs Natural gas, both in mboe/d) with a
  distinct Total mboe/d line/summary — deliberately following the existing project rule of never
  silently combining incompatible units on one axis (spec section 10.2): both stacked components are
  already in the *same* derived unit (mboe/d) by this point, which is what makes a single combined
  chart legitimate here in a way it explicitly is not for raw mb/d + MMscf/d today.
- **Selectors:** company selector (reusing the existing equity legal-entity selector/search
  infrastructure, `docs/app/search.js`/`equity.js`) and a field selector, matching requirement 4's
  "split by company... split by field."
- **Split modes:** Total / Liquids-vs-Natural-gas / by-company / by-field — as separate,
  user-chosen modes rather than one maximally-dense chart, mirroring how the existing equity panel
  already uses a stream-tab selector rather than four simultaneous charts (equity frontend
  checkpoint, section 4 of that work).
- **Filters:** company and field filters, as requirement 4 specifies; likely also a period-range
  filter given this view is explicitly framed as a comparison tool.
- **URL state:** should reuse `docs/app/urlstate.js` exactly as the existing equity stream selector
  does (the same `parseUrlState`/`setUrlState` functions, extended with new recognised keys for
  split-mode and filter selections) — not a new state mechanism, matching this project's explicit,
  already-proven discipline from the most recent checkpoint.
- **Mobile behaviour:** the existing equity panel and global search are already verified mobile-safe
  (equity frontend checkpoint, live verification section); a new view should be held to the same bar
  before being called done, not assumed compatible.
- **Lazy-loading strategy:** should mirror `equity.js`'s existing lazy/cached discipline exactly —
  a small startup index (company/field totals only) loaded once, with full time series fetched only
  once a specific company/field is actually selected, never bulk-loaded. This is a direct
  continuation of the constraint that has held for every artifact in this project so far, not a new
  rule.
- **Accessibility behaviour:** should meet the same bar already established and verified for the
  equity view (keyboard-operable selectors, ARIA combobox pattern already built in `search.js`,
  icon+text status communication, visible focus states) — reuse, not reinvent.

None of the above was built. This is a proposed shape for the eventual implementation checkpoint to
work from, informed by what this project has already proven works (the equity view's lazy-loading,
URL-state, and accessibility patterns).

---

## 8. Dependencies among workstreams

- **B depends on A.** `natural_gas_mboed`/`total_mboed` cannot be computed, even provisionally,
  without an approved conversion constant. `liquids_mboed` alone has no such dependency and could in
  principle proceed independently, but shipping it alone would only support half of requirement 4's
  split.
- **The new default view (requirement 4/7) depends on B**, and B depends on A — so the whole
  headline product change (a default production-overview view showing total mboe/d) is gated behind
  the Workstream A approval decision.
- **C (company grouping) is independent of A/B**, but a company-grouped *production-overview* split
  (requirement 4's "split by company," if it were ever asked to use `display_group` rather than raw
  legal entity) would depend on both B (the values to group) and C (the grouping itself). As scoped
  in this discovery, the production overview's "split by company" uses the *existing* legal-entity
  selector, not a not-yet-approved group — so this dependency only bites if a future decision asks
  for grouped totals specifically.
- **D and E are independent of A/B/C** and of each other at the discovery level, but a future
  "licence portfolio" view that also shows production (e.g. "this company's mboe/d, by licence
  subarea") would depend on both E (portfolio geometry) and B (the production figure itself).
- **C and E share evidence but not a dependency**: E's `subareas_equity` `EQGRPHOLD` field is one of
  the *strongest available sources* for C's proposed schema (section 3.2), so an implementation of C
  should draw on E's discovery even though C does not strictly require E's polygon geometry to be
  ingested first.

---

## 9. Principal methodological risks

1. **A single boe conversion constant discards real, NSTA-reported field-to-field variation.**
   Section 1.2's live evidence (`GASPIPCV` ranging 42.3–64.3 MJ/sm3 across five real fields in one
   period) is a measured ~50% spread in actual calorific value that any single constant necessarily
   averages away. This is a real precision loss, not a hypothetical one.
2. **The existing `GAS_MSCF_PER_BOE = 5.8` constant is itself undocumented** in exactly the way
   spec section 8.4 warns against, and differs measurably (≈3.5%) from a properly sourced
   energy-content figure. If Phase 3 introduces a new, better-documented constant for reported
   values while the old undocumented one keeps sizing map markers, the product would display two
   different, silently inconsistent boe conversions in different views — a real risk to flag before
   implementation, not an abstract one.
3. **Name-based joins recur at every geometry boundary** (PPRS reporting units to field
   determinations, section 4.4; equity/operator/licence entity names to each other, section 3.1) and
   this project's own no-fuzzy-matching discipline means each of these needs its own reviewed alias
   table, not a shared heuristic — underestimating the number of these tables needed is a real
   implementation-cost risk.
4. **Retrospective company-group attribution silently rewrites history** unless explicitly dated and
   caveated (section 3.7/5.4) — this is the single risk this discovery found the strongest concrete
   evidence for (the Getty Oil → Texaco → Unocal → Chevron chain on a real block), and is the kind
   of error that would not be caught by any conservation test, since a wrong-but-internally-consistent
   attribution sums correctly — it can only be caught by explicit date-bounded sourcing.
5. **The equity artifacts' coverage-state model (`{value, status, coverage_pct}`) does not have an
   obvious combination rule** for a derived total (section 2.4) — implementing B against the equity
   side without first resolving this would risk silently inventing a policy nobody reviewed, which
   is precisely the failure mode the existing equity coverage-state design was built to prevent for
   the *un-derived* figures.
6. **`subareas_equity`'s 488 unresolvable tied-percentage rows** (section 3.2) mean a small but
   real fraction of the current equity-group population cannot be sourced from this dataset alone —
   a future implementation must not silently drop these entities from grouping or guess an
   assignment; they need to be visibly flagged as unresolved, the same way MURLACH is flagged today.

---

## 10. Recommended implementation sequence

1. **Resolve Workstream A's open decision** (section 12) — this blocks the highest-value part of the
   proposed product change (requirement 4) and nothing else in this list depends on it being fast,
   only on it being decided.
2. **Implement `liquids_mboed` in the ETL** (no A-dependency, section 2.1) as a low-risk first step
   that proves out the artifact-schema and conservation-test pattern for the derived-field work
   before the harder (A-dependent, equity-coverage-dependent) gas conversion is attempted.
3. **Implement `natural_gas_mboed`/`total_mboed`** once A is resolved, including the conservation
   tests from section 2.5, for the plain production artifacts first (fields/operators) — **not**
   the equity artifacts yet, since the equity coverage-state combination rule (2.4) is a separate,
   still-unresolved decision.
4. **Resolve the equity coverage-state combination rule**, then extend the derived fields to the
   equity artifacts.
5. **Build the production-overview view** (section 7) against the now-available derived fields,
   reusing the equity view's existing lazy-loading/URL-state/accessibility patterns as directly as
   possible rather than re-deriving them.
6. **Field determination polygons** (Workstream D) can proceed in parallel with 1–5 at any point —
   it has no dependency on A/B, only on resolving the 27 unmatched-name cases (section 4.4) with a
   reviewed alias table before publishing a join to PPRS.
7. **Company grouping** (Workstream C) — start with the NSTA-sourced `EQGRPHOFD`/`EQGRPHOLD`
   groups (section 3.2) as the first, highest-confidence reviewed batch, since they already carry a
   defensible `grouping_basis` and `source` with no manual research needed; treat the remaining
   ~145 equity-only entities as a distinctly harder, separate batch of manual review.
8. **Licence-portfolio map** (Workstream E) — current-state (`subareas_equity`) first, since it has
   a real equity percentage and no historical-reconstruction complexity; historical portfolio
   geometry is a separate, later milestone given the name-only limitation (section 5.6, question 3).

---

## 11. Tests and validation each future workstream will require

- **A (once a constant is approved):** a committed test asserting the published constant's value
  and source citation stay in sync with whatever the eventual `meta.json`-equivalent echoes, mirroring
  how `etl/equity_config.py`'s constants are already covered.
- **B:** the conservation tests in section 2.5 (`liquids_mboed` exact-sum, `total_mboed` exact-sum,
  `natural_gas_mboed` within an explicit named tolerance), plus company/field/operator aggregate
  conservation tests analogous to the existing equity artifact tests
  (`tests/test_equity_artifacts.py`), plus a specific test for whatever the equity coverage-state
  combination rule turns out to be (2.4) — including a synthetic fixture exercising the
  worst-of-component-statuses case, since (as with the recent equity-frontend checkpoint's synthetic
  below-95%-coverage fixture) the real published data may not naturally contain an example of every
  status combination.
- **C:** a test that the reviewed mapping schema (3.5) enforces its closed `grouping_basis`
  vocabulary, a test that every row has a `source` citation (no blank/vague sources), and — once any
  rows exist — a test that no `source_legal_entity` appears in two open (`valid_to: null`) rows for
  overlapping periods, which would be an internally contradictory mapping.
- **D:** a test locking in the field-determination match rate against a known baseline (so a future
  NSTA schema or naming change is caught, mirroring the existing schema-drift tests in
  `tests/test_validate.py`), and a test that every entry in the reviewed alias table (for the
  many-to-one reporting-unit cases in 4.4) actually resolves to a real `FIELDNAME` in both sources.
- **E:** a test that the equity percentages for a given subarea/holder set sum to a sane total
  (mirroring the existing equity artifacts' 100%±0.5pp E1 check), and a test that `blocks_history`'s
  historical name reconstruction is actually exercised by at least one committed fixture covering a
  real multi-period rename (the Getty Oil/Texaco/Unocal/Chevron pattern from 5.4 is a natural
  candidate for a synthetic version of this fixture).
- **Frontend (once any of A–E reach implementation):** the existing `tests/frontend/` Playwright
  suite's pattern (offline synthetic fixtures, hand-written CDN stubs, real production code under
  test) should be extended, not replaced, for the new production-overview view and any licence-map
  view — including, per the established project discipline, at least one synthetic fixture for any
  state the live data doesn't currently exercise (as was already necessary for the equity
  `unavailable` coverage state).

---

## 12. Explicit unresolved decisions requiring approval

1. **Which boe conversion convention to use** (section 1.4): 6,000 scf/boe (market-comparable) vs
   the EIA-sourced energy-content figure (≈5,598 scf/boe) vs offering both. This gates nearly
   everything else in this report.
2. **The exact constant name, value, and cited source** to record once (1), above, is decided —
   proposed as `SCF_PER_BOE` in section 1.5, not implemented.
3. **The equity-artifact coverage-state combination rule** for derived streams (section 2.4):
   worst-of-components vs all-must-be-complete.
4. **Rounding policy** for derived, converted fields (section 2.6): full precision (consistent with
   every other field today) vs a fixed decimal policy specific to converted values.
5. **Whether "split by company" in the new production-overview view uses raw legal entities (as
   today) or curated `display_group`s** (section 8) — the latter requires Workstream C to be
   materially further along first.
6. **Whether to pursue the field-determination alias table now** (section 4.4, 18 many-to-one
   reporting-unit cases) as part of Workstream D, or defer it until an actual polygon-ingestion
   milestone is scheduled.
7. **Whether the ~145 equity-artifact entities with no current NSTA licence equity** (section 3.2)
   are grouped via a separate manual-review process, left ungrouped, or excluded from the
   company-grouping feature's first release.
8. **Whether a historical licence-portfolio view is pursued at all**, given it can only ever show
   historical *names*, never historical *equity percentages* (section 5.6/6) — this is a product
   scope decision, not a technical one, since the technical limitation itself is now well
   established.
9. **Whether the production-overview view's URL state extends the existing `urlstate.js` vocabulary
   (recommended, section 7.1) or is scoped as a wholly separate view with its own state** — the
   former is recommended but not decided.
