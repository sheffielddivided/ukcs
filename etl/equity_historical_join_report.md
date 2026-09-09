# Full historical equity interval-join diagnostic

Diagnostic checkpoint only. No docs/data/equity artifacts, no build.py integration, no UI changes, no company alias or parent-group reconciliation, no historical equity production published. Company names are the legal entity exactly as recorded by NSTA.

## Scale

- PPRS field-months processed: 133608
- Normalized equity rows: 7683
- Resolved (field, company, month) rows produced: 248968
- Runtime: 4.85s

## Field-resolution statistics

- Matched fields (of 552): 500
- Unmatched fields: 52
- Production-weighted coverage before interval resolution (i.e. purely from field-name matching): {'oil_mbd': 96.663, 'dry_gas_mmscfd': 93.243, 'assoc_gas_mmscfd': 99.359, 'condensate_mbd': 98.203}

### Unmatched fields (full list, first/last period, cumulative production)

| Field | First period | Last period | Oil (mbd) | Dry gas (mmscfd) | Assoc. gas (mmscfd) | Condensate (mbd) |
| --- | --- | --- | --- | --- | --- | --- |
| ANGUS | 199112 | 200806 | 546.97 | 0.0 | 173.715 | 0.0 |
| ARDMORE | 200309 | 200505 | 170.661 | 0.0 | 54.834 | 0.0 |
| ARGYLL | 197506 | 199209 | 2451.101 | 0.0 | 686.513 | 0.0 |
| BLADON | 199709 | 200003 | 143.867 | 0.0 | 69.275 | 0.0 |
| BLAIR | 199001 | 199105 | 6.321 | 0.0 | 2.671 | 0.0 |
| BLENHEIM | 199504 | 200003 | 666.866 | 0.0 | 284.31 | 0.0 |
| CADEBY COAL MINE VENT | 201901 | 202605 | 0.0 | 13.344 | 0.0 | 0.0 |
| CALLISTO NORTH | 200102 | 201601 | 0.0 | 304.371 | 0.0 | 0.022 |
| CAMELOT CENTRAL SOUTH | 199004 | 201106 | 0.0 | 6562.428 | 0.0 | 2.188 |
| CAMELOT NORTH | 199212 | 201106 | 0.0 | 652.325 | 0.0 | 0.097 |
| CAMELOT NORTH EAST | 199212 | 199812 | 0.0 | 578.556 | 0.0 | 0.042 |
| CRAWFORD | 198904 | 199011 | 127.312 | 0.0 | 342.096 | 0.0 |
| DAUNTLESS | 199708 | 199904 | 132.688 | 0.0 | 4.81 | 0.0 |
| DOE GREEN COAL BED METHANE | 201301 | 202506 | 0.0 | 1.692 | 0.0 | 0.0 |
| DONAN | 199501 | 199711 | 206.903 | 0.0 | 70.343 | 0.0 |
| DUNCAN | 198311 | 199209 | 564.277 | 0.0 | 277.308 | 0.0 |
| DURWARD | 199708 | 199904 | 223.322 | 0.0 | 50.482 | 0.0 |
| EMERALD | 199208 | 199602 | 528.578 | 0.0 | 850.878 | 0.0 |
| ESMOND | 198506 | 199502 | 0.0 | 0.0 | 0.0 | 0.0 |
| FERGUS | 199609 | 200806 | 420.172 | 0.0 | 40.078 | 0.0 |
| FIFE | 199508 | 200806 | 1860.955 | 0.0 | 208.444 | 0.0 |
| FLORA | 199810 | 200806 | 510.195 | 0.0 | 62.288 | 0.0 |
| FORBES | 198509 | 199301 | 0.004 | 0.0 | 0.0 | 0.0 |
| FRIGG | 198412 | 200409 | 0.0 | 60139.287 | 0.0 | 9.789 |
| GORDON | 198508 | 199502 | 0.005 | 0.0 | 0.0 | 0.0 |
| HAMISH | 199002 | 200902 | 113.752 | 0.0 | 54.388 | 0.0 |
| HUTTON | 198408 | 200206 | 6346.274 | 0.0 | 1029.308 | 0.0 |
| INDEFATIGABLE [SHELL] | 198907 | 200507 | 0.0 | 11203.865 | 0.0 | 15.441 |
| INNES | 198503 | 199112 | 184.175 | 0.0 | 305.156 | 0.0 |
| IRONVILLE | 200204 | 200909 | 0.0 | 3.68 | 0.0 | 0.0 |
| IVANHOE | 198907 | 200902 | 2350.442 | 0.0 | 719.754 | 0.0 |
| KIRKLINGTON | 200907 | 202404 | 0.0 | 0.0 | 0.0 | 0.0 |
| LEADON | 200111 | 200606 | 574.553 | 0.0 | 136.313 | 0.0 |
| LINNHE | 198910 | 199302 | 25.545 | 0.0 | 114.893 | 0.0 |
| MAUREEN | 198309 | 199909 | 7318.887 | 0.0 | 2922.632 | 0.0 |
| MOIRA | 199008 | 199906 | 137.766 | 0.0 | 41.123 | 0.0 |
| NORTHWEST HUTTON | 198304 | 200312 | 4086.53 | 0.0 | 2656.237 | 0.0 |
| PLAYFAIR | 200411 | 201402 | 120.05 | 0.0 | 184.332 | 0.0 |
| RENEE | 199902 | 200902 | 293.752 | 0.0 | 235.744 | 0.0 |
| ROB ROY | 199907 | 200902 | 290.318 | 0.0 | 193.906 | 0.0 |
| ROSE | 200401 | 201702 | 0.0 | 1092.808 | 0.0 | 0.0 |
| RUBIE | 199905 | 200902 | 371.983 | 0.0 | 134.926 | 0.0 |
| SEDGWICK [PT. OF WEST BRAE] | 199710 | 200012 | 368.113 | 0.0 | 95.156 | 0.0 |
| SHELLEY | 200908 | 201006 | 33.844 | 0.0 | 22.291 | 0.0 |
| SKUA [pt. of MARNOCK-SKUA] | 200110 | 201709 | 349.711 | 0.0 | 287.964 | 0.0 |
| STAFFA | 199203 | 199411 | 139.978 | 0.0 | 212.127 | 0.0 |
| TRISTAN | 199211 | 200410 | 0.0 | 1238.263 | 0.0 | 0.902 |
| TRISTAN NW | 200803 | 201704 | 0.0 | 55.726 | 0.0 | 0.004 |
| TRUMFLEET | 199803 | 200910 | 0.0 | 25.353 | 0.0 | 0.0 |
| VIKING | 198604 | 199003 | 0.0 | 11468.419 | 0.0 | 33.7 |
| WELLAND NORTH WEST | 199009 | 200411 | 0.0 | 6256.012 | 0.0 | 5.104 |
| WELLAND SOUTH | 199009 | 200409 | 0.0 | 2590.383 | 0.0 | 1.557 |

## E1 - interest conservation (full history)

- Passing field-months (resolved): 100307
- Below 100% (not an overlap): 0
- Above 100% (not caught as an overlap - e.g. rounding near the E1/E4 boundary): 0
- Below-100 examples: []
- Above-100 examples: []

## E4 - overlap / quarantine (full history)

- Total quarantined field-months: 0
- Distinct affected fields: []
- Distinct affected companies: []
- Earliest / latest affected period: None / None
- Production excluded by stream: {'oil_mbd': 0.0, 'dry_gas_mmscfd': 0.0, 'assoc_gas_mmscfd': 0.0, 'condensate_mbd': 0.0}

Full conflicting-interval evidence for every quarantined case is in `etl/equity_historical_anomalies.json` (not repeated here in full if the list is long).

**ROCHELLE check: 0 quarantined field-month(s) found for ROCHELLE.**

## E5 - coverage classification (full history, precise categories)

- future_only: 10
- month_start_boundary: 100
- pre_equity_history: 27064
- resolved: 100307
- unmatched: 6127

## E7 - interval validity (full workbook)

- Rows checked: 7683
- start_date > end_date violations: 0
- Passed: True
- Zero-duration rows accepted as non-active source events: 838

## E8 - production conservation (monthly, per stream, resolved fields only)

- Months checked: 546
- Failures beyond tolerance: 0
- Passed: True

## Partial-month / gap diagnostics

### pre_equity_history

- Field-months: 27064
- Distinct fields: 247
- Excluded production by stream: {'oil_mbd': 603567.802, 'dry_gas_mmscfd': 561005.915, 'assoc_gas_mmscfd': 923134.681, 'condensate_mbd': 1374.34}
- Earliest / latest affected period: 197509 / 201705
- Example fields: ['ALBA', 'ALBURY', 'ALISON [CENTRICA]', 'ALISON-KX [CONOCOPHILLIPS]', 'ALWYN NORTH', 'AMETHYST EAST', 'AMETHYST WEST', 'ANDREW', 'ANGLIA', 'ANN']

### month_start_boundary

- Field-months: 100
- Distinct fields: 97
- Excluded production by stream: {'oil_mbd': 424.449, 'dry_gas_mmscfd': 480.717, 'assoc_gas_mmscfd': 639.647, 'condensate_mbd': 1.431}
- Earliest / latest affected period: 199410 / 202003
- Example fields: ['ALBA', 'ALBURY', 'APOLLO', 'ARBROATH', 'ARKWRIGHT', 'BEAUFORT', 'BELL [PERENCO]', 'BESSEMER', 'BITTERN', 'BOTHAMSALL']

### genuine_interval_gap

- Field-months: 0
- Distinct fields: 0
- Excluded production by stream: {'oil_mbd': 0.0, 'dry_gas_mmscfd': 0.0, 'assoc_gas_mmscfd': 0.0, 'condensate_mbd': 0.0}
- Earliest / latest affected period: None / None
- Example fields: []

### future_only

- Field-months: 10
- Distinct fields: 1
- Excluded production by stream: {'oil_mbd': 110.342, 'dry_gas_mmscfd': 0.0, 'assoc_gas_mmscfd': 82.734, 'condensate_mbd': 0.0}
- Earliest / latest affected period: 202509 / 202606
- Example fields: ['MURLACH [pt of MARNOCK-SKUA]']

### no_equity_history

- Field-months: 0
- Distinct fields: 0
- Excluded production by stream: {'oil_mbd': 0.0, 'dry_gas_mmscfd': 0.0, 'assoc_gas_mmscfd': 0.0, 'condensate_mbd': 0.0}
- Earliest / latest affected period: None / None
- Example fields: []

These are NOT all treated as data errors: `month_start_boundary` is a mechanical artifact of resolving ownership at the first day of the month when a real interval starts or ends mid-month; `pre_equity_history` and `future_only` reflect genuine absence of equity coverage for part or all of a field's production run; only `genuine_interval_gap` represents a real break in coverage between two dated intervals.

## Coverage by stream

Full-history production-weighted coverage: {'oil_mbd': 33.002, 'dry_gas_mmscfd': 56.115, 'assoc_gas_mmscfd': 52.096, 'condensate_mbd': 62.285}

**This is low, and must not be read as the historical model being broadly unreliable in the way that number alone suggests** - see the annual breakdown below. Coverage rises sharply once equity records begin for most fields; the low full-history average is driven by ~1975-2000, where the equity workbook simply has little or no coverage for many fields' earliest years (`pre_equity_history` - not a matching or interval-resolution failure).

### Annual production-weighted coverage by stream

| Year | Oil | Dry gas | Assoc. gas | Condensate |
| --- | --- | --- | --- | --- |
| 1975 | 0.0 | None | 0.0 | None |
| 1976 | 0.0 | None | 0.0 | None |
| 1977 | 0.0 | None | 0.0 | None |
| 1978 | 0.0 | None | 0.0 | None |
| 1979 | 0.0 | None | 0.0 | None |
| 1980 | 0.0 | None | 0.0 | None |
| 1981 | 1.822 | None | 2.337 | None |
| 1982 | 2.016 | None | 1.998 | None |
| 1983 | 2.441 | 8.667 | 2.705 | 0.0 |
| 1984 | 1.898 | 7.295 | 2.261 | 0.0 |
| 1985 | 1.718 | 6.779 | 2.033 | 0.459 |
| 1986 | 1.746 | 5.83 | 1.803 | 15.093 |
| 1987 | 2.596 | 9.654 | 3.103 | 21.892 |
| 1988 | 1.872 | 25.387 | 1.451 | 25.181 |
| 1989 | 2.3 | 20.172 | 1.651 | 19.537 |
| 1990 | 2.728 | 33.775 | 1.974 | 45.851 |
| 1991 | 2.733 | 37.166 | 1.627 | 41.908 |
| 1992 | 2.204 | 36.027 | 1.197 | 42.4 |
| 1993 | 4.545 | 37.392 | 4.62 | 33.072 |
| 1994 | 5.539 | 38.446 | 5.414 | 28.992 |
| 1995 | 5.903 | 35.712 | 5.726 | 20.639 |
| 1996 | 6.347 | 33.385 | 5.69 | 24.59 |
| 1997 | 8.316 | 32.196 | 8.045 | 23.173 |
| 1998 | 10.162 | 31.585 | 11.753 | 21.856 |
| 1999 | 7.978 | 35.55 | 10.176 | 21.61 |
| 2000 | 8.956 | 36.837 | 9.443 | 23.301 |
| 2001 | 8.35 | 43.224 | 8.892 | 29.759 |
| 2002 | 41.85 | 64.255 | 54.029 | 52.309 |
| 2003 | 64.596 | 78.981 | 70.876 | 80.257 |
| 2004 | 79.558 | 86.4 | 84.573 | 85.941 |
| 2005 | 80.215 | 89.543 | 86.543 | 89.389 |
| 2006 | 85.429 | 92.653 | 91.294 | 91.695 |
| 2007 | 92.097 | 94.542 | 92.209 | 94.836 |
| 2008 | 92.083 | 96.698 | 92.909 | 95.678 |
| 2009 | 94.484 | 96.492 | 95.727 | 95.95 |
| 2010 | 96.182 | 98.568 | 99.052 | 98.863 |
| 2011 | 96.935 | 98.468 | 99.493 | 98.249 |
| 2012 | 97.894 | 98.713 | 99.709 | 97.378 |
| 2013 | 98.406 | 98.399 | 99.671 | 97.496 |
| 2014 | 96.998 | 98.917 | 98.701 | 98.862 |
| 2015 | 97.567 | 99.14 | 98.702 | 99.067 |
| 2016 | 97.401 | 98.72 | 99.212 | 98.559 |
| 2017 | 99.503 | 99.369 | 99.64 | 99.326 |
| 2018 | 100.0 | 99.999 | 100.0 | 100.0 |
| 2019 | 100.0 | 99.987 | 100.0 | 100.0 |
| 2020 | 99.998 | 99.989 | 100.0 | 100.0 |
| 2021 | 100.0 | 99.989 | 100.0 | 100.0 |
| 2022 | 100.0 | 99.987 | 100.0 | 100.0 |
| 2023 | 100.0 | 99.984 | 100.0 | 100.0 |
| 2024 | 100.0 | 99.991 | 100.0 | 100.0 |
| 2025 | 99.5 | 99.979 | 99.901 | 100.0 |
| 2026 | 97.622 | 99.98 | 99.53 | 100.0 |

### Coverage buckets (months, by stream)

- oil_mbd: {'at_100': 98, '99.5_to_100': 6, '95_to_99.5': 100, 'below_95': 409}
- dry_gas_mmscfd: {'at_100': 28, '99.5_to_100': 90, '95_to_99.5': 108, 'below_95': 293}
- assoc_gas_mmscfd: {'at_100': 98, '99.5_to_100': 46, '95_to_99.5': 63, 'below_95': 406}
- condensate_mbd: {'at_100': 108, '99.5_to_100': 5, '95_to_99.5': 109, 'below_95': 293}

### Ten lowest-coverage months per stream

- oil_mbd: [('197506', 0.0), ('197507', 0.0), ('197508', 0.0), ('197509', 0.0), ('197510', 0.0), ('197511', 0.0), ('197512', 0.0), ('197601', 0.0), ('197602', 0.0), ('197603', 0.0)]
- dry_gas_mmscfd: [('198305', 0.0), ('198402', 0.0), ('198406', 0.0), ('198505', 0.0), ('198608', 0.0), ('198609', 0.0), ('198502', 0.697), ('198306', 1.69), ('198604', 1.835), ('198704', 2.285)]
- assoc_gas_mmscfd: [('197506', 0.0), ('197507', 0.0), ('197508', 0.0), ('197509', 0.0), ('197510', 0.0), ('197511', 0.0), ('197512', 0.0), ('197601', 0.0), ('197602', 0.0), ('197603', 0.0)]
- condensate_mbd: [('199003', 0.0), ('198305', 0.0), ('198306', 0.0), ('198307', 0.0), ('198308', 0.0), ('198309', 0.0), ('198311', 0.0), ('198401', 0.0), ('198402', 0.0), ('198403', 0.0)]

### Production excluded by category, by stream

- pre_equity_history: {'oil_mbd': 603567.802, 'dry_gas_mmscfd': 561005.915, 'assoc_gas_mmscfd': 923134.681, 'condensate_mbd': 1374.34}
- month_start_boundary: {'oil_mbd': 424.449, 'dry_gas_mmscfd': 480.717, 'assoc_gas_mmscfd': 639.647, 'condensate_mbd': 1.431}
- unmatched: {'oil_mbd': 31665.87, 'dry_gas_mmscfd': 102186.512, 'assoc_gas_mmscfd': 12524.295, 'condensate_mbd': 68.846}
- future_only: {'oil_mbd': 110.342, 'dry_gas_mmscfd': 0.0, 'assoc_gas_mmscfd': 82.734, 'condensate_mbd': 0.0}

## MURLACH [pt of MARNOCK-SKUA] investigation

- Producing months affected: 10
- Excluded production by stream: {'oil_mbd': 110.342, 'dry_gas_mmscfd': 0.0, 'assoc_gas_mmscfd': 82.734, 'condensate_mbd': 0.0}
- First / latest affected period: 202509 / 202606
- Categories seen across its history: ['future_only']
- Related equity field names found (MARNOCK/SKUA substring match): ['MARNOCK [pt. of MARNOCK-SKUA]', 'MURLACH [pt of MARNOCK-SKUA]']
- MURLACH's own equity rows (all of them): [{'company': 'BP EXPLORATION OPERATING COMPANY LIMITED', 'start': '2050-01-04', 'end': None, 'pct': 80.0}, {'company': 'NEO ENERGY (ZNS) LIMITED', 'start': '2050-01-04', 'end': None, 'pct': 20.0}]

No alias applied. The related `MARNOCK [pt. of MARNOCK-SKUA]` equity rows belong to a **different** field name and were not treated as covering MURLACH without authoritative evidence that they should. This remains an open question for a human reviewer, not resolved by this diagnostic.

## Historical company summary (legal entity as recorded by NSTA)

No parent-company or current-group rollup. No merging of similarly-named companies. This is not a corporate-group history.

| Company | First period | Last period | Fields | Oil (mbd) | Dry gas (mmscfd) | Assoc. gas (mmscfd) | Condensate (mbd) | Excluded/quarantined field-months |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ADURA OPERATIONS LIMITED | 202511 | 202606 | 20 | 426.63889 | 708.357 | 987.917608 | 0.128 | 0 |
| ALBA RESOURCES LIMITED | 200902 | 201311 | 1 | 0.3609 | 0.0 | 1.7473 | 0.0 | 0 |
| ALKANE ENERGY UK LIMITED | 201705 | 202605 | 12 | 0.0 | 176.674 | 0.924 | 0.0 | 0 |
| ALTWOOD PETROLEUM LIMITED | 200203 | 201503 | 1 | 0.0 | 0.2838 | 0.0 | 0.0 | 0 |
| AMOCO (FIDDICH) LIMITED | 200210 | 202405 | 1 | 401.5618 | 0.0 | 319.68365 | 0.0 | 0 |
| AMOCO (U.K.) EXPLORATION COMPANY | 200203 | 200309 | 4 | 31.83089 | 16.020843 | 1002.206296 | 0.002889 | 0 |
| AMOCO (U.K.) EXPLORATION COMPANY, LLC | 201103 | 201210 | 4 | 0.0 | 202.183771 | 0.0 | 0.0 | 0 |
| AMOCO U.K.PETROLEUM LIMITED | 200203 | 201207 | 22 | 193.717597 | 3387.320471 | 6740.564603 | 1.44898 | 0 |
| ANASURIA HIBISCUS UK LIMITED | 201604 | 202606 | 5 | 282.056721 | 0.0 | 334.551612 | 0.0 | 0 |
| ANGUS ENERGY EAKRING DEVELOPMENT LIMITED | 201208 | 201508 | 1 | 0.0133 | 0.0 | 0.2568 | 0.0 | 0 |
| ANGUS ENERGY WEALD BASIN NO.3 LIMITED | 200210 | 202605 | 3 | 10.2106 | 132.62754 | 0.0432 | 2.26899 | 0 |
| APACHE BERYL I LIMITED | 200203 | 202606 | 19 | 4809.212582 | 3703.164342 | 22511.714359 | 8.265268 | 0 |
| APACHE NORTH SEA LIMITED | 200304 | 202606 | 6 | 11303.080377 | 0.0 | 2429.362119 | 0.0 | 0 |
| ARCO BRITISH LIMITED, LLC | 198906 | 202606 | 19 | 2550.38925 | 7285.982771 | 9699.0433 | 10.755611 | 0 |
| ARKADIAN STRATEGIC METALS PLC | 201706 | 202106 | 1 | 0.0022 | 0.0 | 0.0 | 0.0 | 0 |
| ATLANTIC PETROLEUM NORTH SEA LIMITED | 201412 | 201608 | 3 | 24.380202 | 0.0 | 16.121356 | 0.0 | 0 |
| ATLANTIC PETROLEUM UK LIMITED | 200809 | 201412 | 3 | 150.041002 | 0.0 | 94.308172 | 0.0 | 0 |
| AURORA ENERGY RESOURCES LIMITED | 201008 | 201008 | 1 | 0.003832 | 0.0 | 8.3e-05 | 0.0 | 0 |
| AZZURO RESOURCES PLC | 201402 | 202102 | 2 | 0.1611 | 0.0 | 0.0 | 0.0 | 0 |
| BACTON STORAGE COMPANY LIMITED | 201107 | 201409 | 1 | 0.0 | 100.515 | 0.0 | 0.195 | 0 |
| BAIRD UNDERGROUND GAS STORAGE LIMITED | 200910 | 201106 | 1 | 0.0 | 36.8199 | 0.0 | 0.0756 | 0 |
| BERYL NORTH SEA II LIMITED | 201301 | 201307 | 6 | 9.068121 | 0.0 | 44.748871 | 0.0 | 0 |
| BERYL NORTH SEA LIMITED | 201301 | 201307 | 6 | 27.192534 | 0.0 | 134.189355 | 0.0 | 0 |
| BG EXPLORATION AND PRODUCTION NIGERIA LIMITED | 201103 | 201411 | 1 | 15.286436 | 0.0 | 13.18174 | 0.0 | 0 |
| BG GREAT BRITAIN LIMITED | 200305 | 202510 | 2 | 170.02979 | 0.0 | 470.674084 | 0.0 | 0 |
| BG INTERNATIONAL LIMITED | 199510 | 202606 | 27 | 3113.602856 | 2195.510699 | 45244.71845 | 9.811984 | 0 |
| BG NORGE LIMITED | 200506 | 201710 | 1 | 1.92399 | 0.0 | 55.132276 | 0.0 | 0 |
| BG NORTH SEA HOLDINGS LIMITED | 200207 | 201710 | 3 | 10.888587 | 418.691894 | 63.472761 | 3.089582 | 0 |
| BG UNITED KINGDOM,INC. | 200203 | 200309 | 2 | 0.0 | 269.718279 | 0.0 | 0.254753 | 0 |
| BG UPSTREAM A NIGERIA LIMITED | 201103 | 201411 | 1 | 15.286436 | 0.0 | 13.18174 | 0.0 | 0 |
| BHP BILLITON PETROLEUM GREAT BRITAIN LIMITED | 200203 | 201811 | 8 | 1433.669303 | 5760.498338 | 7086.879492 | 24.449596 | 0 |
| BITTERN AND TRITON (UK) LIMITED | 201207 | 201309 | 1 | 46.372695 | 0.0 | 40.162124 | 0.0 | 0 |
| BLACKLAND PARK EXPLORATION LIMITED | 199007 | 202605 | 1 | 32.063 | 0.0 | 0.317 | 0.0 | 0 |
| BLUENORD ENERGY UK LTD. | 201304 | 201709 | 1 | 120.9804 | 0.0 | 106.2566 | 0.0 | 0 |
| BOWLAND RESOURCES (NO.2) LIMITED | 201311 | 202111 | 1 | 0.0 | 363.2584 | 0.0 | 3.6424 | 0 |
| BOWLAND RESOURCES LIMITED | 201311 | 202111 | 1 | 0.0 | 363.2584 | 0.0 | 3.6424 | 0 |
| BP AMOCO EXPLORATION (FAROES) LIMITED | 200203 | 202405 | 1 | 437.68145 | 0.0 | 339.04705 | 0.0 | 0 |
| BP BRASIL LIMITADA | 200203 | 202405 | 1 | 437.68145 | 0.0 | 339.04705 | 0.0 | 0 |
| BP EXPLORATION (ALPHA) LIMITED | 200109 | 201808 | 6 | 0.0 | 2477.842967 | 0.0 | 2.020221 | 0 |
| BP EXPLORATION (AZERBAIJAN) LIMITED | 200203 | 201102 | 1 | 0.0 | 213.9928 | 0.0 | 0.3644 | 0 |
| BP EXPLORATION (DELTA) LIMITED | 200203 | 200712 | 1 | 241.35385 | 0.0 | 162.4248 | 0.0 | 0 |
| BP EXPLORATION (EPSILON) LIMITED | 200203 | 202405 | 1 | 437.68145 | 0.0 | 339.04705 | 0.0 | 0 |
| BP EXPLORATION (PSI) LIMITED | 201702 | 202606 | 2 | 986.71551 | 0.0 | 586.48557 | 0.0 | 0 |
| BP EXPLORATION BETA LIMITED | 200109 | 201804 | 4 | 140.456 | 902.837575 | 120.299 | 0.579075 | 0 |
| BP EXPLORATION INDONESIA LIMITED | 200203 | 202405 | 1 | 437.68145 | 0.0 | 339.04705 | 0.0 | 0 |
| BP EXPLORATION LIBYA LIMITED | 200801 | 202405 | 1 | 196.3276 | 0.0 | 176.62225 | 0.0 | 0 |
| BP EXPLORATION OPERATING COMPANY LIMITED | 198304 | 202606 | 50 | 21245.155544 | 69778.073291 | 63656.993976 | 64.069373 | 0 |
| BP EXPLORATION SERVICES LIMITED | 200203 | 200408 | 1 | 0.0 | 117.842169 | 0.0 | 0.033885 | 0 |
| BP P.L.C. | 200111 | 200307 | 2 | 0.0 | 1147.04 | 0.0 | 0.281 | 0 |
| BRIDGE PETROLEUM 1 LIMITED | 201610 | 202606 | 2 | 38.55938 | 0.0 | 95.41978 | 0.0 | 0 |

(... 327 more companies; full table available by re-running `python etl/equity_join_historical.py`.)

## Confirmations

- No parent-company rollup was performed. Every `company_name` above is the legal entity string exactly as recorded in the workbook's `Organisation Name` column.
- No public artifacts were written (nothing under docs/data/equity/*), `etl/build.py` was not modified, and no UI changes were made. This report and `etl/equity_historical_anomalies.json` are the only outputs, both under `etl/`.
