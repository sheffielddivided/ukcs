# UKCS Oil & Gas Production Explorer

A static, interactive explorer of UK Continental Shelf oil and gas production, built on the
North Sea Transition Authority's open data. No backend, no database, no API keys — a GitHub
Actions workflow rebuilds the data weekly and commits it straight into the site.

**Live site:** https://sheffielddivided.github.io/ukcs/

## What it does

Three views over one pre-built dataset. The browser only ever reads `docs/data/*`; it never
calls NSTA or ArcGIS.

**Production** — the default view. Total UKCS production in mboe/d, split by commodity
(liquids vs natural gas), by company, or by field. Monthly or annual average. The company and
field splits show the ten largest and group the rest as "Other", with a footnote naming
everything in that bucket.

**Fields map** — authoritative NSTA field polygons coloured by dominant commodity, with
production-scaled bubbles for fields that have no polygon match. Selecting a field gives its
annual average production (oil and gas, stacked) and its ownership history, most recent first.

**Licence portfolio** — current licence subareas grouped by equity group holder, plus a
separate historical layer of recorded licensee and operator names over time. The historical
layer never carries an equity percentage: no NSTA source publishes a historical one, so none is
fabricated, and a build-breaking check enforces that.

## Data

Covering **1975-06 to 2026-06**, monthly:

- **552 fields** with production history (250 producing in the latest period, 302 no longer
  active). Storage volumes (e.g. Rough) and reporting-unit renames (e.g. Sean → North Sean) are
  explicitly separated out, never silently merged into production totals.
- **Equity-attributable production per company** across **292 legal entities**, weighted by each
  company's dated ownership interest in each field. This is the headline metric and the default
  in the UI. It is a *gross* equity share of reported field production — not net, not
  entitlement, not accounting production.
- **Per-operator rollup** — attributed to each field's *current* operator and labelled as such.
  It is an internal consistency check, not a headline figure.

Derived mboe/d values convert natural gas at 6,000 scf/boe, a conventional energy-equivalence
factor for cross-commodity comparability — not a claim about measured calorific value. NSTA does
not publish these directly. The constant is defined in exactly one place
(`etl/production_config.py`); a test scans the whole repository, Python and JavaScript, and fails
the build if a second one appears.

## Status

Phase 1 (field and operator exploration) and Phase 2 (equity-attributable production per
company) are both built, published and live. Phase 3 added the Production overview, field
polygons, company grouping, and the current and historical licence views.

### Known limitations

These are real and unmitigated. `docs/methodology.html` states them for the end user, and
`docs/data/*/meta.json` records them alongside the data itself.

- **Incomplete source data may not be detectable.** Every check here is an internal-consistency
  check against the data it received; none can verify that what NSTA served was itself complete.
  A silently short backing dataset that still paginates correctly, counts correctly and has no
  missing fields would pass everything.
- **No external reconciliation of totals.** Latest-period oil and gas totals have not been
  reconciled against an NSTA-published monthly aggregate — no such per-period figure was
  locatable at build-review time, only annual and multi-year ones.
- **Equity coverage starts 2013-03.** Coverage before that is structurally incomplete in the
  source workbook and is not published, so production split *by company* starts there while the
  commodity and field splits cover 1975 onward. The UI states this where a reader meets it.
- **232 of 552 fields have no polygon match** (10.2% of latest-period production). They render as
  bubbles rather than coloured polygons.
- **52 fields have no equity match** and are absent from equity-attributable figures.
- **MURLACH is excluded** from equity totals: its only recorded equity rows carry an unexplained
  2050-01-04 start date. This is neither interpreted nor corrected — it is excluded and
  explained.
- **182 of 292 legal entities are ungrouped.** Most never appear in NSTA's current-licence
  dataset, so they fall back to being their own singleton display group with status
  `unresolved`. Conservation holds either way; the fallback groups nothing, so it cannot
  fabricate a relationship.
- **No historical company grouping.** No dated, authoritative source for corporate group
  structure over time was found, so grouping historical production by *current* company group is
  labelled in the UI as a retrospective analytical view.

## Development

- `UKCS_DESIGN_v2.md` — full design and build specification, including the decision record for
  every methodology choice.
- `etl/` — the Python build pipeline. Run `pip install -r tests/requirements.txt` (which pulls in
  `etl/requirements.txt` plus pytest), then `python etl/build.py`.
- `docs/` — the static site itself (GitHub Pages root). No build step, no bundler: the browser
  loads ES modules directly.
- `tests/` — 386 tests. `tests/` covers the ETL; `tests/frontend/` drives the real frontend with
  Playwright against small offline fixtures. Run the frontend suite with
  `pip install -r tests/frontend/requirements.txt` first.
- `.github/workflows/build-data.yml` — the weekly rebuild: tests → build → validate → commit only
  if the data actually changed. Validation is build-breaking and runs before anything under
  `docs/data/` is written, so a failure means a red job, zero commits, and untouched data.
- `.github/workflows/frontend-tests.yml` — the frontend suite on every push.
- `ATTRIBUTION.md` — data sources, licence basis, and required attribution.

## Licence

Data used under the NSTA User Agreement (June 2023), assessed as non-commercial use — see
`ATTRIBUTION.md` for the full basis. No licence badge or broader claim is made anywhere in the
UI or this repository.
