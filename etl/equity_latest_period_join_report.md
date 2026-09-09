# Latest-period equity interval-join checkpoint

Diagnostic checkpoint only (spec section 15.8 step 4, latest period only). No docs/data/equity artifacts, no build.py changes, no UI changes, no company alias or parent-group reconciliation. Company names are the legal entity exactly as recorded by NSTA.

1. Period used: `202606` (month_start = 2026-06-01)
2. Producing PPRS fields (latest period): 250
3. Matched fields: 250
4. Fully resolved ownership sets: 249

## 5. Unresolved / quarantined / excluded fields, with reason

### unmatched (0)


### future_only (1)

- **MURLACH [pt of MARNOCK-SKUA]**: all equity rows for this field have a start_date after the evaluated month_start

### quarantined (0)


### unresolved_gap (0)


## 6. E1 - interest conservation

- Passing (resolved, sum 100% +-0.5pp): 249
- Failing (matched, active, sum outside tolerance, not an overlap): 0

## 7. E4 - overlap validation

- Quarantined field-months: 0

## 8. E5 - coverage validation

- resolved: 249
- unmatched: 0
- future_only: 1
- quarantined: 0
- unresolved_gap: 0

## E7 - interval validity (full workbook, not period-scoped)

- Rows checked: 7683
- Violations (start_date > end_date): 0
- Passed: True

## 9. E8 - production conservation, by stream

| Stream | Total | Included (resolved fields) | Excluded | Equity-attributable sum | Within tolerance | Coverage % |
| --- | --- | --- | --- | --- | --- | --- |
| oil_mbd | 478.329 | 463.633 | 14.696 | 463.6237 | True | 96.928 |
| dry_gas_mmscfd | 875.79 | 875.79 | 0.0 | 875.79 | True | 100.0 |
| assoc_gas_mmscfd | 2029.338 | 2018.346 | 10.992 | 2018.3407 | True | 99.458 |
| condensate_mbd | 2.055 | 2.055 | 0.0 | 2.055 | True | 100.0 |

## 10. Coverage percentage by stream

- oil_mbd: 96.928%
- dry_gas_mmscfd: 100.0%
- assoc_gas_mmscfd: 99.458%
- condensate_mbd: 100.0%

Do not read this as 100% coverage unless both matching AND interval resolution are complete: unmatched=0, quarantined=0, unresolved_gap=0, future_only=1.

## 11. Latest-period company summary

**Legal entity as recorded by NSTA.** No parent-company mapping, no rollup, no merging of similarly-named companies.

| Company | Producing fields | Oil (mbd) | Dry gas (mmscfd) | Assoc. gas (mmscfd) | Condensate (mbd) |
| --- | --- | --- | --- | --- | --- |
| ADURA OPERATIONS LIMITED | 20 | 58.338485 | 141.169 | 206.774064 | 0.006 |
| ANASURIA HIBISCUS UK LIMITED | 5 | 0.86874 | 0.0 | 0.491706 | 0.0 |
| APACHE BERYL I LIMITED | 10 | 2.458085 | 7.323 | 11.65976 | 0.0 |
| APACHE NORTH SEA LIMITED | 6 | 12.354533 | 0.0 | 1.648288 | 0.0 |
| ARCO BRITISH LIMITED, LLC | 2 | 1.659161 | 0.0 | 0.333463 | 0.0 |
| BG INTERNATIONAL LIMITED | 1 | 0.1728 | 0.0 | 0.5772 | 0.0 |
| BP EXPLORATION (PSI) LIMITED | 2 | 8.371935 | 0.0 | 6.650325 | 0.0 |
| BP EXPLORATION OPERATING COMPANY LIMITED | 18 | 38.102766 | 0.0 | 63.536 | 0.0 |
| BRIDGE PETROLEUM 1 LIMITED | 2 | 0.144 | 0.0 | 0.481 | 0.0 |
| BRIDGE PETROLEUM 3 LIMITED | 5 | 0.801558 | 0.0 | 0.471585 | 0.0 |
| BRIDGE PETROLEUM 5 LIMITED | 1 | 0.0 | 0.0 | 0.0 | 0.0 |
| BRITOIL LIMITED | 3 | 0.792042 | 0.0 | 0.394989 | 0.0 |
| CALENERGY RESOURCES (UK) LIMITED | 3 | 0.0 | 1.117 | 0.0 | 0.0105 |
| CALENERGY SNS LIMITED | 1 | 0.0 | 0.0 | 0.0 | 0.0 |
| CENTRICA OFFSHORE UK LIMITED | 1 | 0.0 | 25.439 | 0.0 | 0.008 |
| CHEVRON BRITAIN LIMITED | 2 | 9.853514 | 0.0 | 7.827231 | 0.0 |
| CHRYSAOR (U.K.) SIGMA LIMITED | 3 | 6.603825 | 0.0 | 5.808675 | 0.0 |
| CHRYSAOR (U.K.) THETA LIMITED | 1 | 0.169208 | 0.0 | 6.653164 | 0.0 |
| CHRYSAOR LIMITED | 21 | 13.313529 | 0.0 | 155.40553 | 0.0 |
| CHRYSAOR NORTH SEA LIMITED | 5 | 1.198846 | 0.0 | 16.18524 | 0.0 |
| CHRYSAOR PETROLEUM COMPANY U.K. LIMITED | 6 | 10.070674 | 0.0 | 81.522327 | 0.0 |
| CHRYSAOR PRODUCTION (U.K.) LIMITED | 10 | 16.337569 | 1.994244 | 98.446611 | 0.00378 |
| CHRYSAOR RESOURCES (IRISH SEA) LIMITED | 1 | 0.0 | 0.0 | 0.0 | 0.0 |
| CNOOC PETROLEUM EUROPE LIMITED | 6 | 21.856176 | 0.0 | 7.800458 | 0.0 |
| CNOOC PETROLEUM FARRAGON U.K. LIMITED | 1 | 0.1424 | 0.0 | 0.1434 | 0.0 |
| CNR INTERNATIONAL (U.K.) LIMITED | 4 | 7.811 | 0.0 | 11.035 | 0.0 |
| CONOCOPHILLIPS (U.K.) HOLDINGS LIMITED | 1 | 0.035806 | 0.0 | 0.32324 | 0.0 |
| DANA PETROLEUM (E&P) LIMITED | 16 | 11.656672 | 58.4372 | 8.552972 | 0.3345 |
| DNO NORTH SEA (ROGB) LIMITED | 2 | 0.107978 | 0.0 | 0.122256 | 0.0 |
| DNO NORTH SEA (U.K.) LIMITED | 2 | 0.970728 | 0.0 | 14.824213 | 0.0 |
| EGDON RESOURCES U.K. LIMITED | 1 | 0.0 | 0.1639 | 0.0 | 0.0003 |
| ENERGEAN EXPLORATION LIMITED | 1 | 0.0 | 0.0 | 0.0 | 0.0 |
| ENERGEAN UK LTD | 2 | 0.369362 | 0.0 | 0.334869 | 0.0 |
| ENI UK LIMITED | 1 | 0.0 | 0.756622 | 0.0 | 0.0 |
| ENQUEST HEATHER LIMITED | 15 | 21.641919 | 0.0 | 13.04075 | 0.0 |
| ENTERPRISE OIL LIMITED | 3 | 9.737245 | 0.0 | 8.394774 | 0.0 |
| EQUINOR UK LIMITED | 3 | 1.26 | 0.0 | 11.982 | 0.0 |
| ESSO EXPLORATION AND PRODUCTION UK LIMITED | 15 | 0.0 | 65.007338 | 0.0 | 0.132581 |
| EVERARD ENERGY LIMITED | 3 | 0.0 | 1.4092 | 0.0 | 0.00076 |
| GAZPROM INTERNATIONAL UK LTD. | 1 | 0.0 | 2.538232 | 0.0 | 0.0 |
| HARBOUR ENERGY CNS (I) LIMITED | 3 | 3.8398 | 0.0 | 2.597 | 0.0 |
| HARBOUR ENERGY CNS (II) LIMITED | 2 | 0.805 | 0.0 | 0.2725 | 0.0 |
| HARBOUR ENERGY OPERATIONS LIMITED | 2 | 0.640994 | 0.0 | 0.394316 | 0.0 |
| HARBOUR ENERGY PETROLEUM RESOURCES LIMITED | 1 | 0.079411 | 0.0 | 0.105638 | 0.0 |
| HARBOUR ENERGY WPUK LIMITED | 10 | 7.986737 | 0.0 | 6.001916 | 0.0 |
| IGAS ENERGY ENTERPRISE LIMITED | 1 | 0.0 | 0.0 | 0.0 | 0.0 |
| INEOS CLIPPER SOUTH C LIMITED | 1 | 0.0 | 0.21357 | 0.0 | 0.00018 |
| INEOS E&P (UK) LIMITED | 6 | 0.0238 | 59.19818 | 6.6822 | 0.10432 |
| INEOS UK SNS LIMITED | 1 | 0.0 | 0.0 | 0.0 | 0.0 |
| IRANIAN OIL COMPANY (U.K.) LIMITED | 1 | 0.2685 | 0.0 | 67.281 | 0.0 |
| ITHACA (NE) E&P LIMITED | 2 | 8.87915 | 139.55385 | 10.5301 | 0.2652 |
| ITHACA EF LIMITED | 4 | 4.41179 | 0.0 | 40.386892 | 0.0 |
| ITHACA ENERGY (UK) LIMITED | 3 | 1.0565 | 0.0 | 11.00475 | 0.0 |
| ITHACA GSA LIMITED | 6 | 4.313019 | 0.0 | 22.238385 | 0.0 |
| ITHACA J E&P LIMITED | 1 | 3.80535 | 0.0 | 4.5129 | 0.0 |
| ITHACA MA LIMITED | 13 | 6.392732 | 0.0 | 44.867912 | 0.0 |
| ITHACA OIL AND GAS LIMITED | 3 | 0.0 | 0.0 | 0.000367 | 0.0 |
| ITHACA SP E&P LIMITED | 8 | 32.124982 | 0.0 | 77.087863 | 0.0 |
| ITHACA SP O&G LIMITED | 2 | 6.137435 | 0.0 | 1.407388 | 0.0 |
| ITHACA UKCS LIMITED | 1 | 0.0 | 0.0 | 0.0 | 0.0 |
| KISTOS ENERGY LIMITED | 4 | 0.0238 | 0.0 | 6.6822 | 0.0 |
| NEO NEXT + ENERGY ALPHA LIMITED | 6 | 0.0 | 0.0 | 0.0 | 0.0 |
| NEO NEXT + ENERGY DELTA LIMITED | 17 | 15.976598 | 0.0 | 161.707581 | 0.0 |
| NEO NEXT + ENERGY LNS LIMITED | 1 | 0.0 | 0.0 | 0.0 | 0.0 |
| NEO NEXT + ENERGY NORTH SEA LIMITED | 8 | 3.447342 | 0.0 | 16.972663 | 0.0 |
| NEO NEXT + ENERGY OIL TRADING LIMITED | 2 | 0.0 | 0.0 | 0.0 | 0.0 |
| NEO NEXT + ENERGY RESOURCES UK LIMITED | 9 | 0.0 | 0.0 | 0.0 | 0.0 |
| NEO NEXT+ ENERGY (PRODUCTION) LIMITED | 1 | 0.0 | 0.0 | 0.0 | 0.0 |
| NEO NEXT+ ENERGY (ZEX) LIMITED | 4 | 3.098522 | 0.0 | 1.095285 | 0.0 |
| NEO NEXT+ ENERGY CENTRAL NORTH SEA LIMITED | 8 | 2.558938 | 0.0 | 2.515431 | 0.0 |
| NEO NEXT+ ENERGY E&P NORTH SEA UK LIMITED | 2 | 6.18734 | 0.0 | 196.321464 | 0.0 |
| NEO NEXT+ ENERGY E&P UK LIMITED | 14 | 11.205183 | 6.343 | 125.580777 | 0.138 |
| NEO NEXT+ ENERGY E.F. LIMITED | 2 | 2.319512 | 0.0 | 21.248032 | 0.0 |
| NEO NEXT+ ENERGY EXPLORATION UK LIMITED | 2 | 0.159768 | 0.0 | 0.11263 | 0.0 |
| NEO NEXT+ ENERGY GT LIMITED | 1 | 0.0 | 7.1358 | 0.0 | 0.0 |
| NEO NEXT+ ENERGY NATURAL RESOURCES LIMITED | 2 | 0.0 | 0.0 | 0.0 | 0.0 |
| NEO NEXT+ ENERGY OFFSHORE UK LIMITED | 2 | 4.4606 | 0.0 | 40.8616 | 0.0 |
| NEO NEXT+ ENERGY PETROLEUM LIMITED | 18 | 19.269198 | 0.0 | 172.862443 | 0.0 |
| NEO NEXT+ ENERGY PUK LIMITED | 5 | 6.614 | 0.0 | 31.52 | 0.0 |
| ONE-DYAS E&P LIMITED | 3 | 2.416895 | 0.0 | 4.951165 | 0.0 |
| ONE-DYAS UK LIMITED | 2 | 2.047849 | 1.015466 | 0.658726 | 0.0 |
| PERENCO GAS (UK) LIMITED | 6 | 0.0 | 12.5708 | 0.0 | 0.02024 |
| PERENCO NORTH SEA LIMITED | 3 | 0.0 | 10.2001 | 0.0 | 0.0189 |
| PERENCO SNS LIMITED | 2 | 0.0 | 1.117 | 0.0 | 0.0105 |
| PERENCO UK LIMITED | 25 | 0.0 | 101.597496 | 0.0 | 0.059525 |
| PING PETROLEUM UK PLC | 4 | 0.86874 | 0.0 | 0.491706 | 0.0 |
| PRAX HURRICANE (WHIRLWIND) LIMITED | 4 | 0.00476 | 0.0 | 1.33644 | 0.0 |
| PRAX HURRICANE GLA LIMITED | 4 | 0.03689 | 0.0 | 10.35741 | 0.0 |
| PRAX HURRICANE GWA LIMITED | 4 | 0.00476 | 0.0 | 1.33644 | 0.0 |
| PRAX UPSTREAM LIMITED | 4 | 0.00119 | 0.0 | 0.33411 | 0.0 |
| PREMIER OIL E&P UK EU LIMITED | 2 | 0.0 | 5.216687 | 0.0 | 0.000862 |
| PREMIER OIL E&P UK LIMITED | 2 | 0.09716 | 48.312 | 0.068558 | 0.30105 |
| PREMIER OIL UK LIMITED | 6 | 9.5995 | 5.368 | 6.4925 | 0.03345 |
| RIGEL PETROLEUM (NI) LIMITED | 3 | 0.0 | 0.0 | 0.0 | 0.0 |
| RIGEL PETROLEUM UK LIMITED | 2 | 0.0583 | 0.0 | 0.1226 | 0.0 |
| ROCKROSE (UKCS2) LIMITED | 2 | 0.0 | 0.0 | 0.0 | 0.0 |
| ROCKROSE (UKCS3) LIMITED | 1 | 0.0 | 0.9051 | 0.0 | 0.008025 |
| ROCKROSE UKCS 10 LIMITED | 20 | 0.0238 | 21.045037 | 6.6822 | 0.033553 |
| ROCKROSE UKCS4 LIMITED | 5 | 2.950085 | 0.0 | 22.607969 | 0.0 |
| SERICA ENERGY (UK) LIMITED | 3 | 1.56376 | 0.0 | 97.38794 | 0.0 |
| SERICA ENERGY CHINOOK LIMITED | 4 | 9.481 | 0.0 | 16.944 | 0.0 |
| SERICA ENERGY GEAD & CATCHER LIMITED | 6 | 2.369835 | 0.0 | 1.408327 | 0.0 |
| SERICA ENERGY MISTRAL LIMITED | 5 | 6.461774 | 0.0 | 21.392605 | 0.0 |
| SHELL CLAIR UK LIMITED | 2 | 4.713653 | 0.0 | 3.744334 | 0.0 |
| SHELL U.K. LIMITED | 18 | 0.0 | 71.161173 | 0.0 | 0.158859 |
| SPIRIT ENERGY NORTH SEA LIMITED | 5 | 0.0 | 26.65618 | 0.0 | 0.20726 |
| SPIRIT ENERGY PRODUCTION UK LIMITED | 3 | 0.0 | 0.0 | 0.0 | 0.0 |
| SPIRIT ENERGY RESOURCES LIMITED | 6 | 0.655702 | 13.157144 | 0.743807 | 0.102755 |
| SPIRIT ENERGY SOUTHERN NORTH SEA LIMITED | 2 | 0.0 | 29.9664 | 0.0 | 0.0513 |
| SPIRIT NORTH SEA GAS LIMITED | 1 | 0.0 | 5.3556 | 0.0 | 0.0446 |
| TAQA BRATANI LIMITED | 6 | 6.653405 | 0.0 | 6.635405 | 0.0 |
| TAQA BRATANI LNS LIMITED | 3 | 0.328098 | 0.0 | 0.372119 | 0.0 |
| TRANSWORLD PETROLEUM (U.K.) LIMITED | 5 | 0.0 | 0.0 | 0.0 | 0.0 |
| UK NORTH SEA LIMITED | 1 | 0.0 | 0.0 | 0.0 | 0.0 |
| WINTERSHALL NOORDZEE B.V. | 1 | 0.0 | 4.34668 | 0.0 | 0.0 |

## 12. Confirmation: no parent-company rollup performed

Confirmed. Every company_name above is the legal entity string exactly as it appears in the `Organisation Name` column of the source workbook. No `etl/mappings/company_aliases.csv` exists, none was created by this step, and no rollup logic was written.

## 13. Confirmation: no public artifacts or UI changes

Confirmed. This module writes only this report and reads already-built docs/data/history/index.json, docs/data/fields.geojson and docs/data/meta.json (Phase 1 artifacts, read-only). It does not write to docs/data/equity/*, does not modify etl/build.py, and does not touch docs/index.html or docs/app/*.

## Zero-duration classification (carried through unchanged from milestone 3)

- {'boundary_duplicate': 689, 'termination_marker': 42, 'boundary_transition': 91, 'standalone_snapshot': 16}
- The `boundary_transition` and `standalone_snapshot` categories remain unresolved source semantics; their meaning is not settled by this checkpoint.
