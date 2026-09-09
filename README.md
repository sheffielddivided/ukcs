# UKCS Oil & Gas Production Explorer

A static, interactive explorer of UK Continental Shelf oil and gas production, built on the
North Sea Transition Authority's PPRS open data. No backend, no database, no API keys — a
GitHub Actions workflow rebuilds the data weekly and commits it straight into the site.

**Live site:** https://sheffielddivided.github.io/ukcs/

## What it does

- Map of UKCS producing fields, sized and coloured by commodity.
- Per-field history: monthly production from 1975 to present, covering 552 fields (250
  currently producing, 302 no longer active). Storage volumes (e.g. Rough) and reporting-unit
  renames (e.g. Sean → North Sean) are explicitly separated out, never silently merged into
  production totals.
- Per-operator rollup — **operator-level production only**, attributed to each field's
  *current* operator and labelled as such. This is a stepping stone and an internal
  consistency check, not the intended headline figure.

## Status: Phase 1 complete (v0.1.0)

Phase 1 delivers field and operator exploration on top of NSTA's raw production reports.
**Phase 2 will introduce equity-attributable production per company** — production weighted by
each company's dated ownership interest in each field — which is the actual commercially
meaningful metric this project is building toward.

### Known limitation

Current data validation cannot detect NSTA's own service returning a dataset that is internally
consistent but incomplete — e.g. a silently short backing dataset that still paginates
correctly, counts correctly, and has no missing fields. Every check in this project is an
internal-consistency check against the data it received; none of them can verify that what NSTA
served was itself complete. This is an open, unmitigated gap, not a solved one. See
`UKCS_DESIGN_v2.md` and the Phase 1 closeout audit for the full detail.

## Development

- `UKCS_DESIGN_v2.md` — full design and build specification.
- `etl/` — the Python build pipeline (`python etl/build.py`; run
  `pip install -r tests/requirements.txt` first to include the test suite, or
  `pip install -r etl/requirements.txt` for the build alone).
- `docs/` — the static site itself (GitHub Pages root).
- `.github/workflows/build-data.yml` — the weekly automated rebuild: tests → build → validate →
  commit only if the data actually changed.
- `ATTRIBUTION.md` — data source, licence basis, and required attribution.

## Licence

Data used under the NSTA User Agreement (June 2023), assessed as non-commercial use — see
`ATTRIBUTION.md` for the full basis. No licence badge or broader claim is made anywhere in the
UI or this repository.
