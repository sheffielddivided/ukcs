# NSTA field equity workbook - schema report

- Workbook file: `equity_workbook.xlsx`
- Sheet names: ['Report 1']
- Column names (in order): ['Field Name', 'On Offshore', 'Median Line Flag', 'Status', 'Organisation Name', 'Percentage Holding', 'Operator Flag', 'Start Date', 'End Date', 'Equity Share Time Period']
- Data row count: 7683
- Distinct field names: 531
- Distinct company (organisation) names: 419
- Start date range: 1968-08-01 to 2050-01-04
- End date range (closed intervals only): 1977-09-07 to 2026-08-26
- Open-ended rows (End Date blank): 1187
- Sentinel start-date rows (< 1960): 0
- Zero-interest rows (Percentage Holding = 0): 241

## Columns not carried into the normalized table

The live workbook has 5 columns beyond the milestone's required set (field name, company name, interest %, start date, end date): `On Offshore`, `Median Line Flag`, `Status`, `Operator Flag`, `Equity Share Time Period`. These are present in the source and recorded here for visibility, but are not part of this milestone's normalized output.

## Deviations from spec section 15 assumptions

1. **Section 15.1 assumes two separate NSTA datasets** - a time-series "Field Equity Shares" dataset (the correct primary source) and a present-day-only "Field Partners" snapshot (forbidden for time series, cross-check only). Live discovery found only **one** dataset in the NSTA ArcGIS org (`OZMfUznmLTnWccBc`): an item titled **"Field Partners"** (id `40fb75005dca48e886891350da9dedd8`). Searching that org for the exact phrase "field equity shares" returns zero results. The NSTA Fields page's own link, labelled "Current and historical field equity shares", resolves to this same item. Its actual content is full interval history (Start Date back to 1968-08-01, 277 distinct "Equity Share Time Period" labels such as "Previous-2005 to 2020" and "Current"), not a present-day snapshot. Section 15.1's snapshot description does not match what this item currently contains. This is the only live source available and it satisfies section 15.1's structural requirements (interest %, start date, end date, records to the late 1960s) despite not being named "Field Equity Shares".

2. **Section 15.2 assumes a single-page scrape to a direct file link.** In reality, resolution is two-hop: NSTA page -> ArcGIS Hub search page (client-rendered SPA, no server-side link to scrape) -> ArcGIS Online search API scoped to org `OZMfUznmLTnWccBc` -> resolved item -> direct `.xlsx` URL on Azure Blob Storage (`datanstauthority.blob.core.windows.net`, not `nstauthority.co.uk`). `etl/equity_fetch.py` implements this two-hop resolution.

3. **No sentinel (`1900-01-01`-style) start dates found.** Section 15.2/15.3/15.4 describe such rows based on the archived 2014-2020 file. Zero rows in the live 7683-row dataset have a start date before 1960 (earliest observed: 1968-08-01). The parser still detects them defensively; it currently never fires.

4. **4 rows have a future Start Date** relative to today (2026-09-09): two starting 2030-05-01 (ALVHEIM / AKER BP ASA; STATFJORD(CROSS BORDER) / EQUINOR UK LIMITED) and two starting 2050-01-04 (MURLACH [pt of MARNOCK-SKUA] / BP EXPLORATION OPERATING COMPANY LIMITED and NEO ENERGY (ZNS) LIMITED). Not addressed by any rule in section 15.4. Not resolved in this milestone.

5. **Zero-interest rows confirmed to exist**: 241 of 7683 rows (3.1%). Section 15.4 asks that their meaning be investigated before deciding how to treat them. Not investigated here per this milestone's explicit scope; rows are retained, unfiltered, with `is_zero_interest=true`. Notably, some zero-interest rows have `Operator Flag = 'Y'` (e.g. AFFLECK / NEO NEXT+ ENERGY PUK LIMITED, current row) - an operator with no recorded equity interest, reinforcing that these rows should not be assumed to mean "relinquished" or "nulled" without further investigation.

6. **At least one zero-duration interval exists** (Start Date == End Date, e.g. ALISON [CENTRICA] / SPIRIT NORTH SEA GAS LIMITED, both dated 2016-05-17). Section 15.4's proposed rule E7 (`start_date < end_date`, strict) would fail this row. Not fixed here - flagged for whoever implements E7.

7. **Scale for later name reconciliation (not attempted here)**: 531 distinct field names and 419 distinct organisation names in the live workbook, versus 552 fields in PPRS full history (per README). Field/company matching is explicitly out of scope for this milestone (spec section 15.8 step 3).
