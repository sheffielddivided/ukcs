# Attribution

## Data sources

**UKCS hydrocarbon field production reports (PPRS)**
- Publisher: North Sea Transition Authority (NSTA)
- Dataset: "UKCS hydrocarbon field production reports PPRS points (WGS84)"
- ArcGIS Online item ID: `dd38204275a04618ab7ddd00f87224e3`
- Companion polygon dataset item ID: `b51887ab2c8547cfb6807cca0ca5fb88`
- Source: `https://www.nstauthority.co.uk/data-and-insights/data/themes/fields/`

**NSTA Field Equity Shares** (Phase 2, not yet built)
- Publisher: North Sea Transition Authority (NSTA)
- Source: `https://www.nstauthority.co.uk/data-and-insights/data/themes/fields/`

The resolved service URL, file hashes and last-modified timestamps for each build are recorded in
`docs/data/meta.json` under `sources`.

## Required attribution statement

Contains information provided by the North Sea Transition Authority and/or other third parties.

This is the verbatim attribution statement required by the operative licence terms (see below). It
appears in the site footer alongside a link to those terms.

## Licence basis

The operative licence terms are the **North Sea Transition Authority User Agreement, dated June
2023**, published at `https://www.nstauthority.co.uk/site-tools/terms-and-conditions/` (PDF:
`nsta-user-agreeement-june-2023.pdf`).

This project's use of NSTA data has been assessed as **non-commercial** under that User Agreement.
This assessment was made on **9 September 2026**, against the June 2023 document specifically. It
is a factual record of the basis for use, not a defence of it: if the nature or context of use
changes, this assessment must be redone against whatever version of the User Agreement is then
current.

Key terms of the June 2023 User Agreement, as read at assessment time:
- Permitted: copying, publishing, distributing, transmitting, and adapting the Information
  (including building and republishing derived aggregates, which is what this project does).
- Permitted exploitation is **non-commercial only** — the June 2023 document does not include a
  right to exploit the Information commercially.
- Required attribution (verbatim, reproduced above), on pain of automatic termination of the
  rights granted if omitted.
- Does not cover: personal data; information not published/disclosed by the NSTA; the NSTA logo or
  any third-party logo; third-party rights the NSTA is not authorised to grant; other IP rights
  (patents, trade marks, design rights).
- Non-endorsement: use of the Information must not suggest official status or NSTA endorsement.
  (The site states "not an official NSTA product" for this reason.)
- No warranty; the NSTA does not guarantee continued supply of the Information.
- Governed by the law of England and Wales.

**A materially different, older document — the "OGA Open User Licence" (version 1.0) — is still
mirrored by third parties** (for example marine.gov.scot). That older text permits commercial
exploitation and uses a different attribution string ("Contains information provided by the
OGA."). It has been superseded by the June 2023 User Agreement on NSTA's own site and must not be
relied on. See `UKCS_DESIGN_v2.md` section 12 for the full comparison.

## Map tiles

Base map tiles are © OpenStreetMap contributors, used under the Open Database Licence. Attribution
is rendered in the map's own attribution control at runtime.

## Software

MapLibre GL JS and ECharts are used under their respective open-source licences (BSD-3-Clause and
Apache-2.0). Both are loaded from jsDelivr with pinned versions and Subresource Integrity hashes;
see `docs/index.html` and `docs/app/charts.js`.
