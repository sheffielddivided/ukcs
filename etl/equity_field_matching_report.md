# PPRS <-> equity workbook field-name matching report

## Field universes

- PPRS fields with production history: 552
- Equity workbook distinct field names: 531
- Fields present in both (by any matching rule below): 500
- Fields present only in PPRS: 52
- Fields present only in the equity workbook: 31

Count differences alone are not treated as errors: the datasets can legitimately include fields of different status or scope (e.g. sub-unit partner groupings the equity workbook tracks separately, or PPRS reporting units the equity workbook does not cover under any name).

## Matching statistics

- Exact matches: 500
- Normalized matches: 0
- Alias matches: 0
- Unmatched PPRS fields: 52
- Unmatched equity fields: 31
- Ambiguous normalized keys (post-exact-match): 0
- Duplicate equity names after normalization (full universe): 0

No ambiguous normalized keys found: no case where more than one unmatched equity field name normalizes to the same key.

No duplicate equity names found after normalization across the full 531-field equity universe.

## Rename cases checked explicitly (spec section 15.5)

- **SEAN -> NORTH SEAN**: see narrative below.
- **COLUMBA B -> COLUMBA BD**: see narrative below.

- `NORTH SEAN`: PPRS's post-rename-consolidation field name (section 7.2's transform already merges the pre-2017 `SEAN` reporting unit into `NORTH SEAN` as one continuous series, so the raw pre-rename PPRS name does not appear in the 552-field universe used here). The equity workbook's `NORTH SEAN` rows start as early as 1984-03-21 - i.e. it already uses the current name for the pre-rename period too. Exact match succeeds; **no alias row needed**.
- `COLUMBA B/D`: PPRS's field name is `COLUMBA B/D` (with a slash), not `COLUMBA BD` as spec section 15.5's prose states - the spec's name for this field should be corrected. The equity workbook's `COLUMBA B/D` rows start as early as 2002-12-16, before the 200006/200007 transition mentioned in the spec. Exact match succeeds; **no alias row needed**.

## Structural mismatches investigated but not aliased

These looked like plausible near-duplicates but did not have unambiguous structural evidence of a 1:1 rename, so they were left unmatched rather than guessed at:

- `INDEFATIGABLE [SHELL]` (PPRS, 198907-200507) vs `INDEFATIGABLE [PERENCO]` (PPRS, 199004-202606, present in equity workbook): **periods overlap** (199004-200507), so this is not a rename of the same reporting unit - they were reported concurrently under different operators/interests. Left unmatched.
- `ALISON [CENTRICA]` (PPRS, 199510-201702) vs `ALISON-KX [CONOCOPHILLIPS]` (PPRS, 199510-201808): periods overlap entirely. The equity workbook's plain `ALISON` (no suffix) cannot be attributed to either without guessing. Left unmatched.
- `VIKING` (PPRS, plain) vs equity's `VIKING A`..`VIKING E [pt of VIKING GROUP]`: PPRS reports `VIKING`, `VIKING A`, `VIKING B` (3 units); equity reports `VIKING A`-`VIKING E` (5 units, A/B match exactly). No structural evidence for what PPRS's plain `VIKING` corresponds to among C/D/E. Left unmatched both ways.
- `HEWETT` group: PPRS's plain `HEWETT` matches exactly. Equity additionally tracks `BIG DOTTY [pt. of HEWETT]`, `DEBORAH [Part of HEWETT]`, `LITTLE DOTTY [Part of HEWETT]` as separate partner groupings with no PPRS counterpart under any name. Left unmatched (equity-only).
- `MARNOCK-SKUA` group: PPRS has `MARNOCK`, `MURLACH`, `SKUA` (all `[pt. of MARNOCK-SKUA]`); equity has only `MARNOCK` and `MURLACH` - `SKUA` is absent from the equity workbook under any name, not a naming variant. Left unmatched (PPRS-only).
- `BRAE` group: equity's plain `BRAE` and PPRS's `SEDGWICK [PT. OF WEST BRAE]` are each unmatched with no evidenced counterpart on the other side.

## Unmatched PPRS fields (full list)

| Field | First period | Last period | Produced in 202606 | Latest-period oil (mbd) | dry gas (mmscfd) | assoc gas (mmscfd) | condensate (mbd) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ANGUS | 199112 | 200806 | False | n/a | n/a | n/a | n/a |
| ARDMORE | 200309 | 200505 | False | n/a | n/a | n/a | n/a |
| ARGYLL | 197506 | 199209 | False | n/a | n/a | n/a | n/a |
| BLADON | 199709 | 200003 | False | n/a | n/a | n/a | n/a |
| BLAIR | 199001 | 199105 | False | n/a | n/a | n/a | n/a |
| BLENHEIM | 199504 | 200003 | False | n/a | n/a | n/a | n/a |
| CADEBY COAL MINE VENT | 201901 | 202605 | False | n/a | n/a | n/a | n/a |
| CALLISTO NORTH | 200102 | 201601 | False | n/a | n/a | n/a | n/a |
| CAMELOT CENTRAL SOUTH | 199004 | 201106 | False | n/a | n/a | n/a | n/a |
| CAMELOT NORTH | 199212 | 201106 | False | n/a | n/a | n/a | n/a |
| CAMELOT NORTH EAST | 199212 | 199812 | False | n/a | n/a | n/a | n/a |
| CRAWFORD | 198904 | 199011 | False | n/a | n/a | n/a | n/a |
| DAUNTLESS | 199708 | 199904 | False | n/a | n/a | n/a | n/a |
| DOE GREEN COAL BED METHANE | 201301 | 202506 | False | n/a | n/a | n/a | n/a |
| DONAN | 199501 | 199711 | False | n/a | n/a | n/a | n/a |
| DUNCAN | 198311 | 199209 | False | n/a | n/a | n/a | n/a |
| DURWARD | 199708 | 199904 | False | n/a | n/a | n/a | n/a |
| EMERALD | 199208 | 199602 | False | n/a | n/a | n/a | n/a |
| ESMOND | 198506 | 199502 | False | n/a | n/a | n/a | n/a |
| FERGUS | 199609 | 200806 | False | n/a | n/a | n/a | n/a |
| FIFE | 199508 | 200806 | False | n/a | n/a | n/a | n/a |
| FLORA | 199810 | 200806 | False | n/a | n/a | n/a | n/a |
| FORBES | 198509 | 199301 | False | n/a | n/a | n/a | n/a |
| FRIGG | 198412 | 200409 | False | n/a | n/a | n/a | n/a |
| GORDON | 198508 | 199502 | False | n/a | n/a | n/a | n/a |
| HAMISH | 199002 | 200902 | False | n/a | n/a | n/a | n/a |
| HUTTON | 198408 | 200206 | False | n/a | n/a | n/a | n/a |
| INDEFATIGABLE [SHELL] | 198907 | 200507 | False | n/a | n/a | n/a | n/a |
| INNES | 198503 | 199112 | False | n/a | n/a | n/a | n/a |
| IRONVILLE | 200204 | 200909 | False | n/a | n/a | n/a | n/a |
| IVANHOE | 198907 | 200902 | False | n/a | n/a | n/a | n/a |
| KIRKLINGTON | 200907 | 202404 | False | n/a | n/a | n/a | n/a |
| LEADON | 200111 | 200606 | False | n/a | n/a | n/a | n/a |
| LINNHE | 198910 | 199302 | False | n/a | n/a | n/a | n/a |
| MAUREEN | 198309 | 199909 | False | n/a | n/a | n/a | n/a |
| MOIRA | 199008 | 199906 | False | n/a | n/a | n/a | n/a |
| NORTHWEST HUTTON | 198304 | 200312 | False | n/a | n/a | n/a | n/a |
| PLAYFAIR | 200411 | 201402 | False | n/a | n/a | n/a | n/a |
| RENEE | 199902 | 200902 | False | n/a | n/a | n/a | n/a |
| ROB ROY | 199907 | 200902 | False | n/a | n/a | n/a | n/a |
| ROSE | 200401 | 201702 | False | n/a | n/a | n/a | n/a |
| RUBIE | 199905 | 200902 | False | n/a | n/a | n/a | n/a |
| SEDGWICK [PT. OF WEST BRAE] | 199710 | 200012 | False | n/a | n/a | n/a | n/a |
| SHELLEY | 200908 | 201006 | False | n/a | n/a | n/a | n/a |
| SKUA [pt. of MARNOCK-SKUA] | 200110 | 201709 | False | n/a | n/a | n/a | n/a |
| STAFFA | 199203 | 199411 | False | n/a | n/a | n/a | n/a |
| TRISTAN | 199211 | 200410 | False | n/a | n/a | n/a | n/a |
| TRISTAN NW | 200803 | 201704 | False | n/a | n/a | n/a | n/a |
| TRUMFLEET | 199803 | 200910 | False | n/a | n/a | n/a | n/a |
| VIKING | 198604 | 199003 | False | n/a | n/a | n/a | n/a |
| WELLAND NORTH WEST | 199009 | 200411 | False | n/a | n/a | n/a | n/a |
| WELLAND SOUTH | 199009 | 200409 | False | n/a | n/a | n/a | n/a |

## Unmatched equity workbook fields (full list)

- ALISON
- ALVHEIM
- BIG DOTTY [pt. of HEWETT]
- BRAE
- CADET
- CALOW
- CALVERTON COAL MINE VENT
- CLAIR
- DEBORAH [Part of HEWETT]
- DELLA
- FRICKLEY COAL MINE VENT
- GRIMETHORPE COAL MINE VENT
- HEM HEATH COAL MINE VENT
- HOUGHTON MAIN COAL MINE VENT
- JACKDAW
- KIRBY MISPERTON
- LITTLE DOTTY [Part of HEWETT]
- LLAY MAIN COAL MINE VENT
- MALTON
- MARISHES
- NUGGETS N2
- NUGGETS N3
- NUGGETS N4
- PICKERING
- POTTERIES COAL BED METHANE
- ROSEBANK
- STATFJORD(CROSS BORDER)
- SUTTON MANOR COAL MINE VENT
- VIKING C [pt of VIKING GROUP]
- VIKING D [pt of VIKING GROUP]
- VIKING E [pt of VIKING GROUP]

## Production-weighted coverage, latest period (202606)

Field-count coverage and production-weighted coverage are **not the same thing** and are reported separately. A handful of unmatched high-volume fields can outweigh many small unmatched ones. Streams are reported separately and are not combined into boe/d at this step.

| Stream | Total | Matched | Unmatched | Coverage % |
| --- | --- | --- | --- | --- |
| Oil (mbd) | 478.329 | 478.329 | 0.0 | 100.0% |
| Dry gas (mmscfd) | 875.79 | 875.79 | 0.0 | 100.0% |
| Associated gas (mmscfd) | 2029.338 | 2029.338 | 0.0 | 100.0% |
| Condensate (mbd) | 2.055 | 2.055 | 0.0 | 100.0% |

Build-breaking threshold from spec section 15.5: unmatched fields must account for no more than 2.0% of latest-period production. Worst-stream unmatched share: 0.00%. **Would PASS** if enforced today. Not enforced in build.py in this milestone.

## Historical field-period count coverage (not a volume measure)

- 500 of 552 PPRS fields (90.6%) matched by field name across their full production history.
- This is a **count of fields**, not a production-weighted figure, and must not be read as equivalent to the volume coverage above. A field matched or unmatched by name says nothing about how much it produced.

## Edge cases carried forward from milestone 1 (not resolved here)

Preserved for the interval-join review, not resolved by field-name matching:

- 4 rows with future start dates:
  - ALVHEIM / AKER BP ASA: start_date=2030-05-01, end_date=None, interest_pct=100.0
  - MURLACH [pt of MARNOCK-SKUA] / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=2050-01-04, end_date=None, interest_pct=80.0
  - MURLACH [pt of MARNOCK-SKUA] / NEO ENERGY (ZNS) LIMITED: start_date=2050-01-04, end_date=None, interest_pct=20.0
  - STATFJORD(CROSS BORDER) / EQUINOR UK LIMITED: start_date=2030-05-01, end_date=None, interest_pct=100.0
- 838 zero-duration interval(s):
  - ALBA / ARCO BRITISH LIMITED, LLC: start_date=end_date=2007-04-27, interest_pct=13.3
  - ALBA / CHRYSAOR PETROLEUM LIMITED: start_date=end_date=2007-04-27, interest_pct=11.68
  - ALBA / CHRYSAOR (U.K.) LAMBDA LIMITED: start_date=end_date=2007-04-27, interest_pct=11.75
  - ALBA / ENQUEST ENERGY LIMITED: start_date=end_date=2007-04-27, interest_pct=1.2
  - ALBA / ENQUEST PRODUCTION LIMITED: start_date=end_date=2007-04-27, interest_pct=6.8
  - ALBA / EQUINOR UK LIMITED: start_date=end_date=2007-04-27, interest_pct=17.0
  - ALBA / FINA PETROLEUM DEVELOPMENT LIMITED: start_date=end_date=2007-04-27, interest_pct=12.65
  - ALBA / HARBOUR ENERGY WPUK LIMITED: start_date=end_date=2007-04-27, interest_pct=2.25
  - ALBA / ITHACA OIL AND GAS LIMITED: start_date=end_date=2007-04-27, interest_pct=23.37
  - ALBURY / STAR ENERGY WEALD BASIN LIMITED: start_date=end_date=2007-11-13, interest_pct=100.0
  - ALISON [CENTRICA] / SPIRIT NORTH SEA GAS LIMITED: start_date=end_date=2007-08-28, interest_pct=100.0
  - ALISON [CENTRICA] / SPIRIT ENERGY NORTH SEA LIMITED: start_date=end_date=2016-05-17, interest_pct=100.0
  - ALISON [CENTRICA] / SPIRIT NORTH SEA GAS LIMITED: start_date=end_date=2016-05-17, interest_pct=0.0
  - ALWYN NORTH / NEO NEXT+ ENERGY E&P UK LIMITED: start_date=end_date=2005-07-01, interest_pct=100.0
  - AMETHYST EAST / ARCO BRITISH LIMITED, LLC: start_date=end_date=2009-08-31, interest_pct=14.1
  - AMETHYST EAST / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2009-08-31, interest_pct=48.2
  - AMETHYST EAST / BRITOIL LIMITED: start_date=end_date=2009-08-31, interest_pct=21.35
  - AMETHYST EAST / MURPHY PETROLEUM LIMITED: start_date=end_date=2009-08-31, interest_pct=7.4
  - AMETHYST EAST / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2009-08-31, interest_pct=8.95
  - AMETHYST WEST / ARCO BRITISH LIMITED, LLC: start_date=end_date=2009-08-31, interest_pct=14.1
  - AMETHYST WEST / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2009-08-31, interest_pct=48.2
  - AMETHYST WEST / BRITOIL LIMITED: start_date=end_date=2009-08-31, interest_pct=21.35
  - AMETHYST WEST / MURPHY PETROLEUM LIMITED: start_date=end_date=2009-08-31, interest_pct=7.4
  - AMETHYST WEST / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2009-08-31, interest_pct=8.95
  - ANDREW / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2009-02-28, interest_pct=62.75
  - ANDREW / ENI TNS LIMITED: start_date=end_date=2009-02-28, interest_pct=16.21
  - ANDREW / NEO NEXT + ENERGY NORTH SEA LIMITED: start_date=end_date=2009-02-28, interest_pct=9.86
  - ANDREW / NEO NEXT+ ENERGY PETROLEUM LIMITED: start_date=end_date=2009-02-28, interest_pct=11.18
  - ANGLIA / DANA PETROLEUM (E&P) LIMITED: start_date=end_date=2010-12-16, interest_pct=25.0
  - ANGLIA / FIRST OIL EXPRO LIMITED: start_date=end_date=2010-12-16, interest_pct=32.8
  - ANGLIA / INEOS UK SNS LIMITED: start_date=end_date=2010-12-16, interest_pct=12.2
  - ANGLIA / ITHACA ENERGY (UK) LIMITED: start_date=end_date=2010-12-16, interest_pct=30.0
  - ANN / SPIRIT ENERGY NORTH SEA LIMITED: start_date=end_date=2016-05-17, interest_pct=100.0
  - ANN / SPIRIT NORTH SEA GAS LIMITED: start_date=end_date=2016-05-17, interest_pct=0.0
  - APOLLO / AMOCO (U.K.) EXPLORATION COMPANY, LLC: start_date=end_date=2011-02-02, interest_pct=0.0
  - APOLLO / AMOCO U.K.PETROLEUM LIMITED: start_date=end_date=2011-02-02, interest_pct=65.0
  - APOLLO / ROCKROSE UKCS15 LIMITED: start_date=end_date=2011-02-02, interest_pct=35.0
  - ARBROATH / ITHACA MA(NS) LIMITED: start_date=end_date=2006-10-31, interest_pct=41.03
  - ARBROATH / NEO NEXT + ENERGY RESOURCES UK LIMITED: start_date=end_date=2006-10-31, interest_pct=58.97
  - ARTHUR / PERENCO UK LIMITED: start_date=end_date=2007-08-01, interest_pct=70.0
  - ARTHUR / SERICA ENERGY MISTRAL LIMITED: start_date=end_date=2007-08-01, interest_pct=30.0
  - ATLANTIC / HESS LIMITED: start_date=end_date=2002-06-13, interest_pct=25.0
  - ATLANTIC / SHELL GLOBAL LNG LIMITED: start_date=end_date=2002-06-13, interest_pct=75.0
  - AUDREY / SPIRIT NORTH SEA GAS LIMITED: start_date=end_date=2007-08-28, interest_pct=100.0
  - AUDREY / SPIRIT ENERGY NORTH SEA LIMITED: start_date=end_date=2016-05-17, interest_pct=100.0
  - AUDREY / SPIRIT NORTH SEA GAS LIMITED: start_date=end_date=2016-05-17, interest_pct=0.0
  - AUK / NEO NEXT + ENERGY RESOURCES UK LIMITED: start_date=end_date=2006-12-01, interest_pct=100.0
  - AUK NORTH / NEO NEXT + ENERGY RESOURCES UK LIMITED: start_date=end_date=2006-12-01, interest_pct=100.0
  - BABBAGE / DANA PETROLEUM (E&P) LIMITED: start_date=end_date=2006-01-30, interest_pct=40.0
  - BABBAGE / PREMIER OIL E&P UK EU LIMITED: start_date=end_date=2006-01-30, interest_pct=47.0
  - BABBAGE / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2006-01-30, interest_pct=13.0
  - BACCHUS / APACHE NORTH SEA LIMITED: start_date=end_date=2011-02-22, interest_pct=50.0
  - BACCHUS / FIRST OIL EXPRO LIMITED: start_date=end_date=2011-02-22, interest_pct=20.0
  - BACCHUS / HARBOUR ENERGY WPUK LIMITED: start_date=end_date=2011-02-22, interest_pct=30.0
  - BAIRD / BACTON STORAGE COMPANY LIMITED: start_date=end_date=2011-06-14, interest_pct=100.0
  - BAIRD / PERENCO UK LIMITED: start_date=end_date=2011-06-14, interest_pct=0.0
  - BARNACLE / EGDON RESOURCES (AURORA) LIMITED: start_date=end_date=1992-10-20, interest_pct=100.0
  - BEATRICE / ITHACA ENERGY (UK) LIMITED: start_date=end_date=2009-07-29, interest_pct=50.0
  - BEATRICE / ONE-DYAS E&P LIMITED: start_date=end_date=2009-07-29, interest_pct=50.0
  - BEATRICE / NEO NEXT + ENERGY NORTH SEA LIMITED: start_date=end_date=2015-03-16, interest_pct=12.5
  - BEATRICE / NEO NEXT + ENERGY RESOURCES UK LIMITED: start_date=end_date=2015-03-16, interest_pct=37.5
  - BEATRICE / ONE-DYAS E&P LIMITED: start_date=end_date=2015-03-16, interest_pct=50.0
  - BEAUFORT / PERENCO UK LIMITED: start_date=end_date=2011-02-02, interest_pct=76.92
  - BEAUFORT / ROCKROSE UKCS15 LIMITED: start_date=end_date=2011-02-02, interest_pct=23.08
  - BEINN / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2009-01-09, interest_pct=27.7
  - BEINN / FUJAIRAH OIL AND GAS UK 12 LIMITED: start_date=end_date=2009-01-09, interest_pct=38.0
  - BEINN / FUJAIRAH OIL AND GAS UK LLC: start_date=end_date=2009-01-09, interest_pct=0.0
  - BEINN / ITHACA (NE) UKCS LIMITED: start_date=end_date=2009-01-09, interest_pct=2.0
  - BEINN / NEO NEXT+ ENERGY PETROLEUM LIMITED: start_date=end_date=2009-01-09, interest_pct=6.3
  - BEINN / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2009-01-09, interest_pct=8.0
  - BEINN / TAQA BRATANI LIMITED: start_date=end_date=2009-01-09, interest_pct=14.0
  - BEINN / TAQA BRATANI LNS LIMITED: start_date=end_date=2009-01-09, interest_pct=4.0
  - BELL [CONOCOPHILLIPS] / EQUINOR EXPLORATION UK LIMITED: start_date=end_date=2007-06-28, interest_pct=30.0
  - BELL [CONOCOPHILLIPS] / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2007-06-28, interest_pct=50.0
  - BELL [CONOCOPHILLIPS] / PHILLIPS 66 LIMITED: start_date=end_date=2007-06-28, interest_pct=20.0
  - BELL [PERENCO] / PERENCO UK LIMITED: start_date=end_date=2011-02-02, interest_pct=64.92
  - BELL [PERENCO] / ROCKROSE UKCS15 LIMITED: start_date=end_date=2011-02-02, interest_pct=35.08
  - BERYL / APACHE BERYL I LIMITED: start_date=end_date=2003-05-01, interest_pct=50.0
  - BERYL / ENTERPRISE OIL LIMITED: start_date=end_date=2003-05-01, interest_pct=22.78
  - BERYL / HESS LIMITED: start_date=end_date=2003-05-01, interest_pct=22.22
  - BERYL / ITHACA SP E&P LIMITED: start_date=end_date=2003-05-01, interest_pct=5.0
  - BERYL / APACHE BERYL I LIMITED: start_date=end_date=2012-12-21, interest_pct=50.0
  - BERYL / BERYL NORTH SEA II LIMITED: start_date=end_date=2012-12-21, interest_pct=5.56
  - BERYL / BERYL NORTH SEA LIMITED: start_date=end_date=2012-12-21, interest_pct=16.67
  - BERYL / ENTERPRISE OIL LIMITED: start_date=end_date=2012-12-21, interest_pct=22.78
  - BERYL / ITHACA SP E&P LIMITED: start_date=end_date=2012-12-21, interest_pct=5.0
  - BESSEMER / PERENCO UK LIMITED: start_date=end_date=2011-02-02, interest_pct=76.92
  - BESSEMER / ROCKROSE UKCS15 LIMITED: start_date=end_date=2011-02-02, interest_pct=23.08
  - BIRCH / SPIRIT ENERGY NORTH SEA OIL LIMITED: start_date=end_date=2006-05-31, interest_pct=100.0
  - BITTERN / EQUINOR WOS LIMITED: start_date=end_date=2007-04-06, interest_pct=4.67
  - BITTERN / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2007-04-06, interest_pct=25.0
  - BITTERN / HARBOUR ENERGY WPUK LIMITED: start_date=end_date=2007-04-06, interest_pct=2.42
  - BITTERN / HESS LIMITED: start_date=end_date=2007-04-06, interest_pct=28.28
  - BITTERN / SHELL EP OFFSHORE VENTURES LIMITED: start_date=end_date=2007-04-06, interest_pct=14.63
  - BITTERN / SHELL U.K. LIMITED: start_date=end_date=2007-04-06, interest_pct=25.0
  - BITTERN / DANA PETROLEUM (E&P) LIMITED: start_date=end_date=2018-09-01, interest_pct=32.95
  - BITTERN / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2018-09-01, interest_pct=25.0
  - BITTERN / HARBOUR ENERGY WPUK LIMITED: start_date=end_date=2018-09-01, interest_pct=2.42
  - BITTERN / SERICA ENERGY MELTEMI LIMITED: start_date=end_date=2018-09-01, interest_pct=39.63
  - BLAKE / BG EXPLORATION AND PRODUCTION NIGERIA LIMITED: start_date=end_date=2011-02-25, interest_pct=4.4
  - BLAKE / BG UPSTREAM A NIGERIA LIMITED: start_date=end_date=2011-02-25, interest_pct=4.4
  - BLAKE / NEO NEXT + ENERGY NORTH SEA LIMITED: start_date=end_date=2011-02-25, interest_pct=2.4
  - BLAKE / NEO NEXT + ENERGY RESOURCES UK LIMITED: start_date=end_date=2011-02-25, interest_pct=33.6
  - BLAKE / RIGEL PETROLEUM UK LIMITED: start_date=end_date=2011-02-25, interest_pct=17.6
  - BLAKE / ROCKROSE UKCS4 LIMITED: start_date=end_date=2011-02-25, interest_pct=2.4
  - BLAKE / SHELL GLOBAL LNG LIMITED: start_date=end_date=2011-02-25, interest_pct=35.2
  - BLANE / DANA PETROLEUM (BVUK) LIMITED: start_date=end_date=2011-05-16, interest_pct=15.24
  - BLANE / DNO NORTH SEA (ROGB) LIMITED: start_date=end_date=2011-05-16, interest_pct=15.24
  - BLANE / DNO NORTH SEA (U.K.) LIMITED: start_date=end_date=2011-05-16, interest_pct=21.96
  - BLANE / NEO NEXT+ ENERGY PETROLEUM LIMITED: start_date=end_date=2011-05-16, interest_pct=17.07
  - BLANE / NEO NEXT + ENERGY RESOURCES UK LIMITED: start_date=end_date=2011-05-16, interest_pct=30.49
  - BOA / ITHACA SP E&P LIMITED: start_date=end_date=2010-12-31, interest_pct=13.62
  - BOA / NEO NEXT+ ENERGY E&P NORTH SEA UK LIMITED: start_date=end_date=2010-12-31, interest_pct=86.38
  - BOULTON / CHRYSAOR PRODUCTION (U.K.) LIMITED: start_date=end_date=2007-09-28, interest_pct=46.0
  - BOULTON / ITHACA (NE) UKCS LIMITED: start_date=end_date=2007-09-28, interest_pct=44.5
  - BOULTON / TULLOW OIL SK LIMITED: start_date=end_date=2007-09-28, interest_pct=9.5
  - BOYLE / PERENCO UK LIMITED: start_date=end_date=2011-02-02, interest_pct=72.22
  - BOYLE / ROCKROSE UKCS15 LIMITED: start_date=end_date=2011-02-02, interest_pct=27.78
  - BRAE / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2009-01-09, interest_pct=27.7
  - BRAE / FUJAIRAH OIL AND GAS UK 12 LIMITED: start_date=end_date=2009-01-09, interest_pct=38.0
  - BRAE / FUJAIRAH OIL AND GAS UK LLC: start_date=end_date=2009-01-09, interest_pct=0.0
  - BRAE / ITHACA (NE) UKCS LIMITED: start_date=end_date=2009-01-09, interest_pct=2.0
  - BRAE / NEO NEXT+ ENERGY PETROLEUM LIMITED: start_date=end_date=2009-01-09, interest_pct=6.3
  - BRAE / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2009-01-09, interest_pct=8.0
  - BRAE / TAQA BRATANI LIMITED: start_date=end_date=2009-01-09, interest_pct=14.0
  - BRAE / TAQA BRATANI LNS LIMITED: start_date=end_date=2009-01-09, interest_pct=4.0
  - BRAE-CENTRAL [Part of BRAE] / FUJAIRAH OIL AND GAS UK LLC: start_date=end_date=2012-05-01, interest_pct=40.0
  - BRAE-CENTRAL [Part of BRAE] / NEO NEXT+ ENERGY PETROLEUM LIMITED: start_date=end_date=2012-05-01, interest_pct=6.3
  - BRAE-CENTRAL [Part of BRAE] / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2012-05-01, interest_pct=8.0
  - BRAE-CENTRAL [Part of BRAE] / TAQA BRATANI LIMITED: start_date=end_date=2012-05-01, interest_pct=41.7
  - BRAE-CENTRAL [Part of BRAE] / TAQA BRATANI LNS LIMITED: start_date=end_date=2012-05-01, interest_pct=4.0
  - BRAEMAR / FUJAIRAH OIL AND GAS UK 12 LIMITED: start_date=end_date=2022-10-21, interest_pct=0.0
  - BRAEMAR / NEO NEXT+ ENERGY PETROLEUM LIMITED: start_date=end_date=2022-10-21, interest_pct=5.41
  - BRAEMAR / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2022-10-21, interest_pct=6.76
  - BRAEMAR / TAQA BRATANI LIMITED: start_date=end_date=2022-10-21, interest_pct=83.78
  - BRAEMAR / TAQA BRATANI LNS LIMITED: start_date=end_date=2022-10-21, interest_pct=4.05
  - BRAE-SOUTH [Part of BRAE] / FUJAIRAH OIL AND GAS UK LLC: start_date=end_date=2012-05-01, interest_pct=40.0
  - BRAE-SOUTH [Part of BRAE] / NEO NEXT+ ENERGY PETROLEUM LIMITED: start_date=end_date=2012-05-01, interest_pct=6.3
  - BRAE-SOUTH [Part of BRAE] / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2012-05-01, interest_pct=8.0
  - BRAE-SOUTH [Part of BRAE] / TAQA BRATANI LIMITED: start_date=end_date=2012-05-01, interest_pct=41.7
  - BRAE-SOUTH [Part of BRAE] / TAQA BRATANI LNS LIMITED: start_date=end_date=2012-05-01, interest_pct=4.0
  - BREAGH / INEOS UK SNS LIMITED: start_date=end_date=2009-12-31, interest_pct=70.0
  - BREAGH / ONE-DYAS UK LIMITED: start_date=end_date=2009-12-31, interest_pct=30.0
  - BRENDA / PREMIER OIL UK LIMITED: start_date=end_date=2009-12-15, interest_pct=100.0
  - BRENT / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2002-01-01, interest_pct=50.0
  - BRENT / SHELL U.K. LIMITED: start_date=end_date=2002-01-01, interest_pct=50.0
  - BRIGANTINE C / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2000-06-22, interest_pct=50.0
  - BRIGANTINE C / SHELL U.K. LIMITED: start_date=end_date=2000-06-22, interest_pct=50.0
  - BRIGANTINE D / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2001-05-07, interest_pct=50.0
  - BRIGANTINE D / SHELL U.K. LIMITED: start_date=end_date=2001-05-07, interest_pct=50.0
  - BRIMMOND / APACHE NORTH SEA LIMITED: start_date=end_date=2004-02-27, interest_pct=97.14
  - BRIMMOND / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2004-02-27, interest_pct=2.61
  - BRIMMOND / SHELL U.K. LIMITED: start_date=end_date=2004-02-27, interest_pct=0.25
  - BRITANNIA / ARCO BRITISH LIMITED, LLC: start_date=end_date=2002-03-01, interest_pct=8.97
  - BRITANNIA / CHRYSAOR PETROLEUM COMPANY U.K. LIMITED: start_date=end_date=2002-03-01, interest_pct=7.23
  - BRITANNIA / CHRYSAOR PRODUCTION (U.K.) LIMITED: start_date=end_date=2002-03-01, interest_pct=40.6
  - BRITANNIA / CHRYSAOR (U.K.) BRITANNIA LIMITED: start_date=end_date=2002-03-01, interest_pct=0.0
  - BRITANNIA / CHRYSAOR (U.K.) THETA LIMITED: start_date=end_date=2002-03-01, interest_pct=9.01
  - BRITANNIA / ITHACA OIL AND GAS LIMITED: start_date=end_date=2002-03-01, interest_pct=32.38
  - BRITANNIA / PHILLIPS 66 LIMITED: start_date=end_date=2002-03-01, interest_pct=1.81
  - BRODGAR / CHRYSAOR PRODUCTION (U.K.) LIMITED: start_date=end_date=1985-12-31, interest_pct=75.0
  - BRODGAR / ITHACA OIL AND GAS LIMITED: start_date=end_date=1985-12-31, interest_pct=25.0
  - BROWN / PERENCO UK LIMITED: start_date=end_date=2011-02-02, interest_pct=72.22
  - BROWN / ROCKROSE UKCS15 LIMITED: start_date=end_date=2011-02-02, interest_pct=27.78
  - BRUCE / BHP BILLITON PETROLEUM GREAT BRITAIN LIMITED: start_date=end_date=2009-12-21, interest_pct=16.0
  - BRUCE / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2009-12-21, interest_pct=37.0
  - BRUCE / ITHACA MA(NS) LIMITED: start_date=end_date=2009-12-21, interest_pct=3.75
  - BRUCE / NEO NEXT+ ENERGY E&P UK LIMITED: start_date=end_date=2009-12-21, interest_pct=43.25
  - BRUCE / BHP BILLITON PETROLEUM GREAT BRITAIN LIMITED: start_date=end_date=2018-11-30, interest_pct=16.0
  - BRUCE / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2018-11-30, interest_pct=1.0
  - BRUCE / ITHACA MA LIMITED: start_date=end_date=2018-11-30, interest_pct=3.75
  - BRUCE / NEO NEXT+ ENERGY E&P UK LIMITED: start_date=end_date=2018-11-30, interest_pct=1.0
  - BRUCE / NEO NEXT+ ENERGY E&P UK LIMITED: start_date=end_date=2018-11-30, interest_pct=43.25
  - BRUCE / SERICA ENERGY (UK) LIMITED: start_date=end_date=2018-11-30, interest_pct=36.0
  - BRUCE / SERICA ENERGY (UK) LIMITED: start_date=end_date=2018-11-30, interest_pct=78.25
  - BRUCE / SERICA ENERGY (UK) LIMITED: start_date=end_date=2018-11-30, interest_pct=94.25
  - BUCKLAND / APACHE BERYL I LIMITED: start_date=end_date=2005-09-30, interest_pct=35.0
  - BUCKLAND / ENTERPRISE OIL LIMITED: start_date=end_date=2005-09-30, interest_pct=14.43
  - BUCKLAND / HESS LIMITED: start_date=end_date=2005-09-30, interest_pct=14.07
  - BUCKLAND / ITHACA SP E&P LIMITED: start_date=end_date=2005-09-30, interest_pct=3.17
  - BUCKLAND / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2005-09-30, interest_pct=33.33
  - BUCKLAND / APACHE BERYL I LIMITED: start_date=end_date=2012-12-21, interest_pct=35.0
  - BUCKLAND / BERYL NORTH SEA II LIMITED: start_date=end_date=2012-12-21, interest_pct=3.52
  - BUCKLAND / BERYL NORTH SEA LIMITED: start_date=end_date=2012-12-21, interest_pct=10.56
  - BUCKLAND / ENTERPRISE OIL LIMITED: start_date=end_date=2012-12-21, interest_pct=14.43
  - BUCKLAND / ITHACA SP E&P LIMITED: start_date=end_date=2012-12-21, interest_pct=3.17
  - BUCKLAND / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2012-12-21, interest_pct=33.33
  - BURE / PERENCO UK LIMITED: start_date=end_date=2010-12-01, interest_pct=23.33
  - BURE / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2010-12-01, interest_pct=10.0
  - BURE / TULLOW OIL SK LIMITED: start_date=end_date=2010-12-01, interest_pct=66.67
  - BUZZARD / CNOOC PETROLEUM EUROPE LIMITED: start_date=end_date=2004-03-30, interest_pct=43.21
  - BUZZARD / EQUINOR WOS LIMITED: start_date=end_date=2004-03-30, interest_pct=29.9
  - BUZZARD / ONE-DYAS EOG LIMITED: start_date=end_date=2004-03-30, interest_pct=5.16
  - BUZZARD / SHELL GLOBAL LNG LIMITED: start_date=end_date=2004-03-30, interest_pct=21.73
  - CADET / EQUINOR UK LIMITED: start_date=end_date=2019-11-07, interest_pct=65.11
  - CADET / ITHACA SP O&G LIMITED: start_date=end_date=2019-11-07, interest_pct=8.89
  - CADET / NEO NEXT+ ENERGY PETROLEUM LIMITED: start_date=end_date=2019-11-07, interest_pct=20.0
  - CADET / ONE-DYAS E&P LIMITED: start_date=end_date=2019-11-07, interest_pct=6.0
  - CAISTER [BUNTER] / CHRYSAOR PRODUCTION (U.K.) LIMITED: start_date=end_date=2009-12-01, interest_pct=9.0
  - CAISTER [BUNTER] / CHRYSAOR (U.K.) BETA LIMITED: start_date=end_date=2009-12-01, interest_pct=30.0
  - CAISTER [BUNTER] / ITHACA (NE) UKCS LIMITED: start_date=end_date=2009-12-01, interest_pct=21.0
  - CAISTER [BUNTER] / PREMIER OIL E&P UK LIMITED: start_date=end_date=2009-12-01, interest_pct=40.0
  - CAISTER [CARBONIFEROUS] / CHRYSAOR PRODUCTION (U.K.) LIMITED: start_date=end_date=2009-12-01, interest_pct=9.0
  - CAISTER [CARBONIFEROUS] / CHRYSAOR (U.K.) BETA LIMITED: start_date=end_date=2009-12-01, interest_pct=30.0
  - CAISTER [CARBONIFEROUS] / ITHACA (NE) UKCS LIMITED: start_date=end_date=2009-12-01, interest_pct=21.0
  - CAISTER [CARBONIFEROUS] / PREMIER OIL E&P UK LIMITED: start_date=end_date=2009-12-01, interest_pct=40.0
  - CALLANISH / CHRYSAOR PRODUCTION (U.K.) LIMITED: start_date=end_date=2003-05-01, interest_pct=83.5
  - CALLANISH / ITHACA OIL AND GAS LIMITED: start_date=end_date=2003-05-01, interest_pct=16.5
  - CALLISTO / EQUINOR UK LIMITED: start_date=end_date=2007-06-28, interest_pct=30.0
  - CALLISTO / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2007-06-28, interest_pct=50.0
  - CALLISTO / PHILLIPS 66 LIMITED: start_date=end_date=2007-06-28, interest_pct=20.0
  - CAPTAIN / ITHACA OIL AND GAS LIMITED: start_date=end_date=2006-03-30, interest_pct=85.0
  - CAPTAIN / KOREA CAPTAIN COMPANY LIMITED: start_date=end_date=2006-03-30, interest_pct=15.0
  - CARAVEL / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2002-10-13, interest_pct=29.0
  - CARAVEL / SHELL U.K. LIMITED: start_date=end_date=2002-10-13, interest_pct=71.0
  - CARRACK / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2003-05-01, interest_pct=50.0
  - CARRACK / SHELL U.K. LIMITED: start_date=end_date=2003-05-01, interest_pct=50.0
  - CAUSEWAY / ITHACA ALPHA (N.I.) LIMITED: start_date=end_date=2010-03-30, interest_pct=30.0
  - CAUSEWAY / ITHACA CAUSEWAY LIMITED: start_date=end_date=2010-03-30, interest_pct=14.0
  - CAUSEWAY / ITHACA EPSILON LIMITED: start_date=end_date=2010-03-30, interest_pct=10.0
  - CAUSEWAY / ITHACA GAMMA LIMITED: start_date=end_date=2010-03-30, interest_pct=10.5
  - CAUSEWAY / NEO NEXT+ ENERGY (ZNI) LIMITED: start_date=end_date=2010-03-30, interest_pct=35.5
  - CAVENDISH / DANA PETROLEUM (E&P) LIMITED: start_date=end_date=2007-11-30, interest_pct=50.0
  - CAVENDISH / INEOS UK SNS LIMITED: start_date=end_date=2007-11-30, interest_pct=50.0
  - CERES / EGDON RESOURCES EUROPE LIMITED: start_date=end_date=2010-07-28, interest_pct=5.0
  - CERES / EGDON RESOURCES U.K. LIMITED: start_date=end_date=2010-07-28, interest_pct=5.0
  - CERES / SPIRIT NORTH SEA GAS LIMITED: start_date=end_date=2010-07-28, interest_pct=90.0
  - CERES / EGDON RESOURCES EUROPE LIMITED: start_date=end_date=2016-05-17, interest_pct=5.0
  - CERES / EGDON RESOURCES U.K. LIMITED: start_date=end_date=2016-05-17, interest_pct=5.0
  - CERES / SPIRIT ENERGY NORTH SEA LIMITED: start_date=end_date=2016-05-17, interest_pct=0.0
  - CERES / SPIRIT NORTH SEA GAS LIMITED: start_date=end_date=2016-05-17, interest_pct=90.0
  - CHISWICK / SPIRIT NORTH SEA GAS LIMITED: start_date=end_date=2008-12-18, interest_pct=100.0
  - CLAIR / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2010-08-04, interest_pct=28.61
  - CLAIR / CHRYSAOR PRODUCTION (U.K.) LIMITED: start_date=end_date=2010-08-04, interest_pct=24.0
  - CLAIR / ENTERPRISE OIL LIMITED: start_date=end_date=2010-08-04, interest_pct=18.68
  - CLAIR / ITHACA OIL AND GAS LIMITED: start_date=end_date=2010-08-04, interest_pct=19.42
  - CLAIR / SHELL CLAIR UK LIMITED: start_date=end_date=2010-08-04, interest_pct=9.29
  - CLAYMORE / DANA PETROLEUM (E&P) LIMITED: start_date=end_date=2005-12-31, interest_pct=7.52
  - CLAYMORE / ENI UK LIMITED: start_date=end_date=2005-12-31, interest_pct=20.0
  - CLAYMORE / NEO NEXT + ENERGY ALPHA LIMITED: start_date=end_date=2005-12-31, interest_pct=13.73
  - CLAYMORE / NEO NEXT + ENERGY NORTH SEA LIMITED: start_date=end_date=2005-12-31, interest_pct=16.67
  - CLAYMORE / NEO NEXT + ENERGY OIL TRADING LIMITED: start_date=end_date=2005-12-31, interest_pct=11.38
  - CLAYMORE / NEO NEXT + ENERGY RESOURCES UK LIMITED: start_date=end_date=2005-12-31, interest_pct=13.0
  - CLAYMORE / TRANSWORLD PETROLEUM (U.K.) LIMITED: start_date=end_date=2005-12-31, interest_pct=17.7
  - CLIPPER SOUTH / BAYERNGAS NORTH SEA LIMITED: start_date=end_date=2011-12-16, interest_pct=25.0
  - CLIPPER SOUTH / INEOS CLIPPER SOUTH B LIMITED: start_date=end_date=2011-12-16, interest_pct=24.0
  - CLIPPER SOUTH / INEOS CLIPPER SOUTH C LIMITED: start_date=end_date=2011-12-16, interest_pct=1.0
  - CLIPPER SOUTH / INEOS UK SNS LIMITED: start_date=end_date=2011-12-16, interest_pct=50.0
  - COLD HANWORTH / STAR ENERGY OIL & GAS LIMITED: start_date=end_date=2011-07-05, interest_pct=100.0
  - COLUMBA B/D / CNR INTERNATIONAL (U.K.) LIMITED: start_date=end_date=2016-11-29, interest_pct=94.4
  - COLUMBA B/D / ITHACA MA LIMITED: start_date=end_date=2016-11-29, interest_pct=5.6
  - COLUMBA E / CNR INTERNATIONAL (U.K.) LIMITED: start_date=end_date=2016-11-29, interest_pct=91.6
  - COLUMBA E / ITHACA MA LIMITED: start_date=end_date=2016-11-29, interest_pct=8.4
  - CONRIE / ENQUEST DONS LIMITED: start_date=end_date=2011-08-02, interest_pct=55.0
  - CONRIE / ENQUEST DONS OCEANIA LIMITED: start_date=end_date=2011-08-02, interest_pct=5.0
  - CONRIE / ITHACA NORTH SEA LIMITED: start_date=end_date=2011-08-02, interest_pct=40.0
  - COOK / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2011-08-25, interest_pct=12.88
  - COOK / ITHACA ENERGY (UK) LIMITED: start_date=end_date=2011-08-25, interest_pct=28.46
  - COOK / ITHACA SPL LIMITED: start_date=end_date=2011-08-25, interest_pct=20.0
  - COOK / NOBLE ENERGY (OILEX) LIMITED: start_date=end_date=2011-08-25, interest_pct=12.88
  - COOK / SHELL EP OFFSHORE VENTURES LIMITED: start_date=end_date=2011-08-25, interest_pct=25.78
  - CORMORANT NORTH / TAQA BRATANI LIMITED: start_date=end_date=2008-12-01, interest_pct=100.0
  - CORVETTE / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=1997-07-01, interest_pct=43.25
  - CORVETTE / SHELL U.K. LIMITED: start_date=end_date=1997-07-01, interest_pct=56.75
  - CULZEAN / NEO NEXT+ ENERGY E&P NORTH SEA UK LIMITED: start_date=end_date=2025-12-31, interest_pct=49.99
  - CULZEAN / NEO NEXT+ ENERGY PETROLEUM LIMITED: start_date=end_date=2025-12-31, interest_pct=50.01
  - CULZEAN / NEO NEXT + ENERGY DELTA LIMITED: start_date=end_date=2026-07-01, interest_pct=32.0
  - CULZEAN / NEO NEXT+ ENERGY E&P NORTH SEA UK LIMITED: start_date=end_date=2026-07-01, interest_pct=49.99
  - CULZEAN / NEO NEXT + ENERGY NORTH SEA LIMITED: start_date=end_date=2026-07-01, interest_pct=18.01
  - CURLEW C / SHELL U.K. LIMITED: start_date=end_date=2007-11-05, interest_pct=100.0
  - DAVY / PERENCO UK LIMITED: start_date=end_date=2011-02-02, interest_pct=72.22
  - DAVY / ROCKROSE UKCS15 LIMITED: start_date=end_date=2011-02-02, interest_pct=27.78
  - DAVY EAST / PERENCO UK LIMITED: start_date=end_date=2005-03-24, interest_pct=60.0
  - DAVY EAST / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2005-03-24, interest_pct=40.0
  - DELILAH / ENI HEWETT LIMITED: start_date=end_date=2006-07-18, interest_pct=51.69
  - DELILAH / ENI LNS LIMITED: start_date=end_date=2006-07-18, interest_pct=12.97
  - DELILAH / ENI UK LIMITED: start_date=end_date=2006-07-18, interest_pct=24.65
  - DELILAH / PERENCO GAS (UK) LIMITED: start_date=end_date=2006-07-18, interest_pct=10.69
  - DELILAH / ENI HEWETT LIMITED: start_date=end_date=2021-07-02, interest_pct=51.69
  - DELILAH / ENI LNS LIMITED: start_date=end_date=2021-07-02, interest_pct=12.96
  - DELILAH / ENI UK LIMITED: start_date=end_date=2021-07-02, interest_pct=24.66
  - DELILAH / PERENCO GAS (UK) LIMITED: start_date=end_date=2021-07-02, interest_pct=10.69
  - DELLA / ENI HEWETT LIMITED: start_date=end_date=2006-07-18, interest_pct=51.69
  - DELLA / ENI LNS LIMITED: start_date=end_date=2006-07-18, interest_pct=12.97
  - DELLA / ENI UK LIMITED: start_date=end_date=2006-07-18, interest_pct=24.65
  - DELLA / PERENCO GAS (UK) LIMITED: start_date=end_date=2006-07-18, interest_pct=10.69
  - DELLA / ENI HEWETT LIMITED: start_date=end_date=2021-07-02, interest_pct=51.69
  - DELLA / ENI LNS LIMITED: start_date=end_date=2021-07-02, interest_pct=12.96
  - DELLA / ENI UK LIMITED: start_date=end_date=2021-07-02, interest_pct=24.66
  - DELLA / PERENCO GAS (UK) LIMITED: start_date=end_date=2021-07-02, interest_pct=10.69
  - DONAN [MAERSK] / CNS (E&P) LIMITED: start_date=end_date=2012-08-09, interest_pct=17.04
  - DONAN [MAERSK] / NEO NEXT+ ENERGY E&P NORTH SEA UK LIMITED: start_date=end_date=2012-08-09, interest_pct=39.76
  - DONAN [MAERSK] / NEO NEXT+ ENERGY OFFSHORE UK LIMITED: start_date=end_date=2012-08-09, interest_pct=30.24
  - DONAN [MAERSK] / ORANJE-NASSAU ENERGIE HANZE (UK) LIMITED: start_date=end_date=2012-08-09, interest_pct=12.96
  - DON SOUTH WEST / ENQUEST DONS LIMITED: start_date=end_date=2008-12-23, interest_pct=55.0
  - DON SOUTH WEST / ENQUEST DONS OCEANIA LIMITED: start_date=end_date=2008-12-23, interest_pct=5.0
  - DON SOUTH WEST / ITHACA NORTH SEA LIMITED: start_date=end_date=2008-12-23, interest_pct=40.0
  - DON SOUTH WEST / ENQUEST DONS OCEANIA LIMITED: start_date=end_date=2013-01-01, interest_pct=5.0
  - DON SOUTH WEST / ENQUEST HEATHER LIMITED: start_date=end_date=2013-01-01, interest_pct=55.0
  - DON SOUTH WEST / ITHACA CAUSEWAY LIMITED: start_date=end_date=2013-01-01, interest_pct=40.0
  - DOUGLAS / BHP BILLITON PETROLEUM GREAT BRITAIN LIMITED: start_date=end_date=2003-11-11, interest_pct=46.1
  - DOUGLAS / ENI ULX LIMITED: start_date=end_date=2003-11-11, interest_pct=45.0
  - DOUGLAS / PRIME AEP LIMITED: start_date=end_date=2003-11-11, interest_pct=8.9
  - DOUGLAS / WOODSIDE ENERGY (GREAT BRITAIN) LIMITED: start_date=end_date=2003-11-11, interest_pct=0.0
  - DOUGLAS WEST / BHP BILLITON PETROLEUM GREAT BRITAIN LIMITED: start_date=end_date=2003-11-11, interest_pct=46.1
  - DOUGLAS WEST / ENI ULX LIMITED: start_date=end_date=2003-11-11, interest_pct=45.0
  - DOUGLAS WEST / PRIME AEP LIMITED: start_date=end_date=2003-11-11, interest_pct=8.9
  - DOUGLAS WEST / WOODSIDE ENERGY (GREAT BRITAIN) LIMITED: start_date=end_date=2003-11-11, interest_pct=0.0
  - DRAKE / CHRYSAOR NORTH SEA LIMITED: start_date=end_date=2009-08-31, interest_pct=76.42
  - DRAKE / FINA EXPLORATION LIMITED: start_date=end_date=2009-08-31, interest_pct=12.53
  - DRAKE / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2009-08-31, interest_pct=5.58
  - DRAKE / SPIRIT RESOURCES (ARMADA) LIMITED: start_date=end_date=2009-08-31, interest_pct=5.47
  - DUART / CNOOC PETROLEUM FARRAGON U.K. LIMITED: start_date=end_date=2010-11-01, interest_pct=50.0
  - DUART / NEO NEXT + ENERGY OIL TRADING LIMITED: start_date=end_date=2010-11-01, interest_pct=50.0
  - DUART / NEO NEXT + ENERGY RESOURCES UK LIMITED: start_date=end_date=2010-11-01, interest_pct=0.0
  - DUKES WOOD / EGDON RESOURCES U.K. LIMITED: start_date=end_date=2017-05-22, interest_pct=55.55
  - DUKES WOOD / NAUTICAL PETROLEUM AG: start_date=end_date=2017-05-22, interest_pct=16.67
  - DUKES WOOD / TERRAIN ENERGY LIMITED: start_date=end_date=2017-05-22, interest_pct=27.78
  - DUNBAR / NEO NEXT+ ENERGY E&P UK LIMITED: start_date=end_date=2005-07-01, interest_pct=100.0
  - DUNLIN / FAIRFIELD BETULA LIMITED: start_date=end_date=2008-04-30, interest_pct=70.0
  - DUNLIN / MCX DUNLIN (UK) LIMITED: start_date=end_date=2008-04-30, interest_pct=30.0
  - DUNLIN SOUTH WEST / FAIRFIELD BETULA LIMITED: start_date=end_date=2008-04-30, interest_pct=70.0
  - DUNLIN SOUTH WEST / MCX DUNLIN (UK) LIMITED: start_date=end_date=2008-04-30, interest_pct=30.0
  - DURANGO / PERENCO NORTH SEA LIMITED: start_date=end_date=2007-02-28, interest_pct=100.0
  - EAST BRAE / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2009-01-09, interest_pct=33.21
  - EAST BRAE / FUJAIRAH OIL AND GAS UK 12 LIMITED: start_date=end_date=2009-01-09, interest_pct=35.28
  - EAST BRAE / FUJAIRAH OIL AND GAS UK LLC: start_date=end_date=2009-01-09, interest_pct=0.0
  - EAST BRAE / ITHACA (NE) UKCS LIMITED: start_date=end_date=2009-01-09, interest_pct=1.55
  - EAST BRAE / NEO NEXT+ ENERGY PETROLEUM LIMITED: start_date=end_date=2009-01-09, interest_pct=5.78
  - EAST BRAE / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2009-01-09, interest_pct=7.32
  - EAST BRAE / TAQA BRATANI LIMITED: start_date=end_date=2009-01-09, interest_pct=13.09
  - EAST BRAE / TAQA BRATANI LNS LIMITED: start_date=end_date=2009-01-09, interest_pct=3.77
  - EAST GLENTWORTH / ISLAND GAS LIMITED: start_date=end_date=2012-03-30, interest_pct=100.0
  - EIDER / TAQA BRATANI LIMITED: start_date=end_date=2008-12-01, interest_pct=100.0
  - ELGIN / CHRYSAOR NORTH SEA LIMITED: start_date=end_date=2003-11-17, interest_pct=14.11
  - ELGIN / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2003-11-17, interest_pct=4.37
  - ELGIN / ITHACA EF LIMITED: start_date=end_date=2003-11-17, interest_pct=21.87
  - ELGIN / ITHACA OIL AND GAS LIMITED: start_date=end_date=2003-11-17, interest_pct=3.9
  - ELGIN / ITHACA SPL LIMITED: start_date=end_date=2003-11-17, interest_pct=2.19
  - ELGIN / NEO NEXT+ ENERGY E.F. LIMITED: start_date=end_date=2003-11-17, interest_pct=46.17
  - ELGIN / NEO NEXT+ ENERGY ELF UK LIMITED: start_date=end_date=2003-11-17, interest_pct=0.0
  - ELGIN / ONE-DYAS E&P LIMITED: start_date=end_date=2003-11-17, interest_pct=2.19
  - ELGIN / PREMIER OIL E&P UK LIMITED: start_date=end_date=2003-11-17, interest_pct=5.2
  - ELGIN / CHRYSAOR PRODUCTION (U.K.) LIMITED: start_date=end_date=2026-07-01, interest_pct=19.31
  - ELGIN / ITHACA SP E&P LIMITED: start_date=end_date=2026-07-01, interest_pct=27.95
  - ELGIN / NEO NEXT+ ENERGY E.F. LIMITED: start_date=end_date=2026-07-01, interest_pct=10.4
  - ELGIN / NEO NEXT+ ENERGY E&P UK LIMITED: start_date=end_date=2026-07-01, interest_pct=15.77
  - ELGIN / NEO NEXT+ ENERGY OFFSHORE UK LIMITED: start_date=end_date=2026-07-01, interest_pct=20.0
  - ELGIN / NEO NEXT+ ENERGY (ZEX) LIMITED: start_date=end_date=2026-07-01, interest_pct=4.38
  - ELGIN / ONE-DYAS E&P LIMITED: start_date=end_date=2026-07-01, interest_pct=2.19
  - ELLON / NEO NEXT+ ENERGY E&P UK LIMITED: start_date=end_date=2005-07-01, interest_pct=100.0
  - ENSIGN / SPIRIT ENERGY NORTH SEA LIMITED: start_date=end_date=2016-05-17, interest_pct=100.0
  - ENSIGN / SPIRIT NORTH SEA GAS LIMITED: start_date=end_date=2016-05-17, interest_pct=0.0
  - ERIS / ROCKROSE UKCS15 LIMITED: start_date=end_date=2011-02-02, interest_pct=44.23
  - ERIS / SPIRIT NORTH SEA GAS LIMITED: start_date=end_date=2011-02-02, interest_pct=55.77
  - ERIS / ROCKROSE UKCS15 LIMITED: start_date=end_date=2016-05-17, interest_pct=52.88
  - ERIS / SPIRIT ENERGY NORTH SEA LIMITED: start_date=end_date=2016-05-17, interest_pct=0.0
  - ERIS / SPIRIT NORTH SEA GAS LIMITED: start_date=end_date=2016-05-17, interest_pct=47.13
  - ERSKINE / BG INTERNATIONAL LIMITED: start_date=end_date=2009-08-31, interest_pct=29.3
  - ERSKINE / BG NORTH SEA HOLDINGS LIMITED: start_date=end_date=2009-08-31, interest_pct=2.7
  - ERSKINE / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2009-08-31, interest_pct=18.0
  - ERSKINE / ITHACA OIL AND GAS LIMITED: start_date=end_date=2009-08-31, interest_pct=50.0
  - EUROPA / EQUINOR UK LIMITED: start_date=end_date=2007-06-28, interest_pct=30.0
  - EUROPA / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2007-06-28, interest_pct=50.0
  - EUROPA / PHILLIPS 66 LIMITED: start_date=end_date=2007-06-28, interest_pct=20.0
  - EXCALIBUR / PERENCO UK LIMITED: start_date=end_date=2010-12-01, interest_pct=100.0
  - FALCON / TAQA BRATANI LIMITED: start_date=end_date=2011-03-31, interest_pct=100.0
  - FARRAGON / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2010-11-01, interest_pct=50.0
  - FARRAGON / CNOOC PETROLEUM FARRAGON U.K. LIMITED: start_date=end_date=2010-11-01, interest_pct=20.0
  - FARRAGON / ENI INDIA LIMITED: start_date=end_date=2010-11-01, interest_pct=30.0
  - FISKERTON AIRFIELD / CIRQUE ENERGY (UK) LIMITED: start_date=end_date=2010-03-23, interest_pct=100.0
  - FLEMING / CHRYSAOR NORTH SEA LIMITED: start_date=end_date=2009-08-31, interest_pct=76.42
  - FLEMING / FINA EXPLORATION LIMITED: start_date=end_date=2009-08-31, interest_pct=12.53
  - FLEMING / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2009-08-31, interest_pct=5.58
  - FLEMING / SPIRIT RESOURCES (ARMADA) LIMITED: start_date=end_date=2009-08-31, interest_pct=5.47
  - FOINAVEN / AMOCO (FIDDICH) LIMITED: start_date=end_date=2007-12-31, interest_pct=5.0
  - FOINAVEN / BP AMOCO EXPLORATION (FAROES) LIMITED: start_date=end_date=2007-12-31, interest_pct=5.0
  - FOINAVEN / BP BRASIL LIMITADA: start_date=end_date=2007-12-31, interest_pct=5.0
  - FOINAVEN / BP EXPLORATION (EPSILON) LIMITED: start_date=end_date=2007-12-31, interest_pct=5.0
  - FOINAVEN / BP EXPLORATION INDONESIA LIMITED: start_date=end_date=2007-12-31, interest_pct=5.0
  - FOINAVEN / BP EXPLORATION LIBYA LIMITED: start_date=end_date=2007-12-31, interest_pct=5.0
  - FOINAVEN / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2007-12-31, interest_pct=2.0
  - FOINAVEN / BRITOIL LIMITED: start_date=end_date=2007-12-31, interest_pct=40.0
  - FOINAVEN / ENTERPRISE OIL U.K. LIMITED: start_date=end_date=2007-12-31, interest_pct=5.0
  - FOINAVEN / ROCKROSE UKCS 10 LIMITED: start_date=end_date=2007-12-31, interest_pct=28.0
  - FORTIES / APACHE NORTH SEA LIMITED: start_date=end_date=2004-02-27, interest_pct=97.14
  - FORTIES / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2004-02-27, interest_pct=2.61
  - FORTIES / SHELL U.K. LIMITED: start_date=end_date=2004-02-27, interest_pct=0.25
  - FRAM / NEO NEXT+ ENERGY PETROLEUM LIMITED: start_date=end_date=2025-11-01, interest_pct=68.0
  - FRAM / SHELL U.K. LIMITED: start_date=end_date=2025-11-01, interest_pct=32.0
  - FRAM / UK NORTH SEA LIMITED: start_date=end_date=2025-11-01, interest_pct=0.0
  - FRANKLIN / CHRYSAOR NORTH SEA LIMITED: start_date=end_date=2003-11-17, interest_pct=14.11
  - FRANKLIN / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2003-11-17, interest_pct=4.38
  - FRANKLIN / ITHACA EF LIMITED: start_date=end_date=2003-11-17, interest_pct=21.86
  - FRANKLIN / ITHACA OIL AND GAS LIMITED: start_date=end_date=2003-11-17, interest_pct=3.9
  - FRANKLIN / ITHACA SPL LIMITED: start_date=end_date=2003-11-17, interest_pct=2.19
  - FRANKLIN / NEO NEXT+ ENERGY E.F. LIMITED: start_date=end_date=2003-11-17, interest_pct=46.17
  - FRANKLIN / NEO NEXT+ ENERGY ELF UK LIMITED: start_date=end_date=2003-11-17, interest_pct=0.0
  - FRANKLIN / ONE-DYAS E&P LIMITED: start_date=end_date=2003-11-17, interest_pct=2.19
  - FRANKLIN / PREMIER OIL E&P UK LIMITED: start_date=end_date=2003-11-17, interest_pct=5.2
  - FRANKLIN / CHRYSAOR PRODUCTION (U.K.) LIMITED: start_date=end_date=2026-07-01, interest_pct=19.31
  - FRANKLIN / ITHACA SP E&P LIMITED: start_date=end_date=2026-07-01, interest_pct=27.95
  - FRANKLIN / NEO NEXT+ ENERGY E.F. LIMITED: start_date=end_date=2026-07-01, interest_pct=10.4
  - FRANKLIN / NEO NEXT+ ENERGY E&P UK LIMITED: start_date=end_date=2026-07-01, interest_pct=15.77
  - FRANKLIN / NEO NEXT+ ENERGY OFFSHORE UK LIMITED: start_date=end_date=2026-07-01, interest_pct=20.0
  - FRANKLIN / NEO NEXT+ ENERGY (ZEX) LIMITED: start_date=end_date=2026-07-01, interest_pct=4.38
  - FRANKLIN / ONE-DYAS E&P LIMITED: start_date=end_date=2026-07-01, interest_pct=2.19
  - GALAHAD / FIRST OIL EXPRO LIMITED: start_date=end_date=2010-12-01, interest_pct=27.77
  - GALAHAD / PERENCO UK LIMITED: start_date=end_date=2010-12-01, interest_pct=72.23
  - GALLEON / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2003-05-01, interest_pct=41.6
  - GALLEON / PHILLIPS 66 LIMITED: start_date=end_date=2003-05-01, interest_pct=8.4
  - GALLEON / SHELL U.K. LIMITED: start_date=end_date=2003-05-01, interest_pct=41.6
  - GALLEON / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2003-05-01, interest_pct=8.4
  - GALLEY / ENI UK LIMITED: start_date=end_date=2007-09-30, interest_pct=15.17
  - GALLEY / NEO NEXT + ENERGY RESOURCES UK LIMITED: start_date=end_date=2007-09-30, interest_pct=67.42
  - GALLEY / ROCKROSE UKCS4 LIMITED: start_date=end_date=2007-09-30, interest_pct=17.42
  - GANNET E / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2018-09-01, interest_pct=50.0
  - GANNET E / SERICA ENERGY MELTEMI LIMITED: start_date=end_date=2018-09-01, interest_pct=50.0
  - GANYMEDE / EQUINOR UK LIMITED: start_date=end_date=2007-06-28, interest_pct=30.0
  - GANYMEDE / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2007-06-28, interest_pct=50.0
  - GANYMEDE / PHILLIPS 66 LIMITED: start_date=end_date=2007-06-28, interest_pct=20.0
  - GAWAIN / PERENCO UK LIMITED: start_date=end_date=2010-12-01, interest_pct=50.0
  - GAWAIN / TULLOW OIL SK LIMITED: start_date=end_date=2010-12-01, interest_pct=50.0
  - GLENELG / CHRYSAOR NORTH SEA LIMITED: start_date=end_date=2003-05-01, interest_pct=14.7
  - GLENELG / ITHACA (NE) UKCS LIMITED: start_date=end_date=2003-05-01, interest_pct=9.26
  - GLENELG / ITHACA UKCS LIMITED: start_date=end_date=2003-05-01, interest_pct=8.0
  - GLENELG / NEO NEXT+ ENERGY ELF UK LIMITED: start_date=end_date=2003-05-01, interest_pct=49.47
  - GLENELG / PREMIER OIL E&P UK LIMITED: start_date=end_date=2003-05-01, interest_pct=18.57
  - GOLDEN EAGLE / CNOOC PETROLEUM EUROPE LIMITED: start_date=end_date=2011-10-19, interest_pct=36.54
  - GOLDEN EAGLE / EQUINOR WOS LIMITED: start_date=end_date=2011-10-19, interest_pct=26.69
  - GOLDEN EAGLE / NEO NEXT+ ENERGY E&P NORTH SEA UK LIMITED: start_date=end_date=2011-10-19, interest_pct=31.56
  - GOLDEN EAGLE / ONE-DYAS EOG LIMITED: start_date=end_date=2011-10-19, interest_pct=5.21
  - GOLDENEYE / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2007-04-06, interest_pct=39.0
  - GOLDENEYE / HARBOUR ENERGY WPUK LIMITED: start_date=end_date=2007-04-06, interest_pct=7.5
  - GOLDENEYE / SHELL U.K. LIMITED: start_date=end_date=2007-04-06, interest_pct=49.0
  - GOLDENEYE / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2007-04-06, interest_pct=4.5
  - GRANT / NEO NEXT+ ENERGY E&P UK LIMITED: start_date=end_date=2005-07-01, interest_pct=100.0
  - GROVE / ROCKROSE (UKCS3) LIMITED: start_date=end_date=2007-12-31, interest_pct=15.0
  - GROVE / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2007-12-31, interest_pct=85.0
  - GRYPHON / NEO NEXT+ ENERGY E&P NORTH SEA UK LIMITED: start_date=end_date=2005-09-30, interest_pct=86.5
  - GRYPHON / ROCKROSE (UKCS3) LIMITED: start_date=end_date=2005-09-30, interest_pct=13.5
  - GUILLEMOT NORTH WEST / EQUINOR WOS LIMITED: start_date=end_date=2003-07-18, interest_pct=90.0
  - GUILLEMOT NORTH WEST / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2003-07-18, interest_pct=10.0
  - GUILLEMOT WEST / EQUINOR WOS LIMITED: start_date=end_date=2003-07-18, interest_pct=90.0
  - GUILLEMOT WEST / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2003-07-18, interest_pct=10.0
  - HAMILTON / BHP BILLITON PETROLEUM GREAT BRITAIN LIMITED: start_date=end_date=2003-11-11, interest_pct=46.1
  - HAMILTON / ENI ULX LIMITED: start_date=end_date=2003-11-11, interest_pct=45.0
  - HAMILTON / PRIME AEP LIMITED: start_date=end_date=2003-11-11, interest_pct=8.9
  - HAMILTON / WOODSIDE ENERGY (GREAT BRITAIN) LIMITED: start_date=end_date=2003-11-11, interest_pct=0.0
  - HAMILTON NORTH / BHP BILLITON PETROLEUM GREAT BRITAIN LIMITED: start_date=end_date=2003-11-11, interest_pct=46.1
  - HAMILTON NORTH / ENI ULX LIMITED: start_date=end_date=2003-11-11, interest_pct=45.0
  - HAMILTON NORTH / PRIME AEP LIMITED: start_date=end_date=2003-11-11, interest_pct=8.9
  - HAMILTON NORTH / WOODSIDE ENERGY (GREAT BRITAIN) LIMITED: start_date=end_date=2003-11-11, interest_pct=0.0
  - HARDING / BRITOIL LIMITED: start_date=end_date=2003-12-18, interest_pct=70.0
  - HARDING / NEO NEXT+ ENERGY E&P NORTH SEA UK LIMITED: start_date=end_date=2003-12-18, interest_pct=30.0
  - HATFIELD / VPI POWER LIMITED: start_date=end_date=2006-12-08, interest_pct=100.0
  - HAWKINS / CHRYSAOR NORTH SEA LIMITED: start_date=end_date=2009-08-31, interest_pct=88.33
  - HAWKINS / SPIRIT RESOURCES (ARMADA) LIMITED: start_date=end_date=2009-08-31, interest_pct=11.67
  - HELVELLYN / FIRST OIL EXPRO LIMITED: start_date=end_date=2003-04-28, interest_pct=50.0
  - HELVELLYN / HARBOUR ENERGY PETROLEUM RESOURCES LIMITED: start_date=end_date=2003-04-28, interest_pct=50.0
  - HEWETT / ENI HEWETT LIMITED: start_date=end_date=2006-07-18, interest_pct=51.69
  - HEWETT / ENI LNS LIMITED: start_date=end_date=2006-07-18, interest_pct=12.96
  - HEWETT / ENI UK LIMITED: start_date=end_date=2006-07-18, interest_pct=24.66
  - HEWETT / PERENCO GAS (UK) LIMITED: start_date=end_date=2006-07-18, interest_pct=10.69
  - HEWETT / ENI HEWETT LIMITED: start_date=end_date=2021-07-02, interest_pct=51.69
  - HEWETT / ENI LNS LIMITED: start_date=end_date=2021-07-02, interest_pct=12.96
  - HEWETT / ENI UK LIMITED: start_date=end_date=2021-07-02, interest_pct=24.66
  - HEWETT / PERENCO GAS (UK) LIMITED: start_date=end_date=2021-07-02, interest_pct=10.69
  - HUMBLY GROVE / HUMBLY GROVE ENERGY LIMITED: start_date=end_date=2011-12-08, interest_pct=100.0
  - HUNTER / ITHACA (NE) UKCS LIMITED: start_date=end_date=2009-12-01, interest_pct=21.0
  - HUNTER / PREMIER OIL E&P UK LIMITED: start_date=end_date=2009-12-01, interest_pct=79.0
  - HYDE / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2011-03-01, interest_pct=50.0
  - HYDE / BRITOIL LIMITED: start_date=end_date=2011-03-01, interest_pct=50.0
  - INDEFATIGABLE [PERENCO] / PERENCO UK LIMITED: start_date=end_date=2011-02-02, interest_pct=76.92
  - INDEFATIGABLE [PERENCO] / ROCKROSE UKCS15 LIMITED: start_date=end_date=2011-02-02, interest_pct=23.08
  - INDEFATIGABLE SOUTH WEST / PERENCO UK LIMITED: start_date=end_date=2011-02-02, interest_pct=76.92
  - INDEFATIGABLE SOUTH WEST / ROCKROSE UKCS15 LIMITED: start_date=end_date=2011-02-02, interest_pct=23.08
  - ISLAY / NEO NEXT+ ENERGY E&P UK LIMITED: start_date=end_date=2010-07-08, interest_pct=100.0
  - JADE / BG INTERNATIONAL LIMITED: start_date=end_date=2002-03-01, interest_pct=35.0
  - JADE / CHRYSAOR PETROLEUM COMPANY U.K. LIMITED: start_date=end_date=2002-03-01, interest_pct=32.5
  - JADE / ENI UK LIMITED: start_date=end_date=2002-03-01, interest_pct=7.0
  - JADE / ITHACA OIL AND GAS LIMITED: start_date=end_date=2002-03-01, interest_pct=19.93
  - JADE / ITHACA SP E&P LIMITED: start_date=end_date=2002-03-01, interest_pct=5.57
  - JAMES / NEO NEXT+ ENERGY OFFSHORE UK LIMITED: start_date=end_date=2010-03-05, interest_pct=100.0
  - JANICE / NEO NEXT+ ENERGY OFFSHORE UK LIMITED: start_date=end_date=2010-03-05, interest_pct=100.0
  - JOHNSTON / DANA PETROLEUM (E&P) LIMITED: start_date=end_date=2021-06-18, interest_pct=49.89
  - JOHNSTON / PERENCO UK LIMITED: start_date=end_date=2021-06-18, interest_pct=21.36
  - JOHNSTON / PREMIER OIL E&P UK EU LIMITED: start_date=end_date=2021-06-18, interest_pct=28.75
  - KEITH / BHP BILLITON PETROLEUM GREAT BRITAIN LIMITED: start_date=end_date=2018-11-30, interest_pct=31.83
  - KEITH / ITHACA MA LIMITED: start_date=end_date=2018-11-30, interest_pct=8.33
  - KEITH / NEO NEXT+ ENERGY E&P UK LIMITED: start_date=end_date=2018-11-30, interest_pct=25.0
  - KEITH / SERICA ENERGY (UK) LIMITED: start_date=end_date=2018-11-30, interest_pct=34.84
  - KEITH / SERICA ENERGY (UK) LIMITED: start_date=end_date=2018-11-30, interest_pct=59.84
  - KEITH / SERICA ENERGY (UK) LIMITED: start_date=end_date=2018-11-30, interest_pct=91.67
  - KELVIN / CHRYSAOR PRODUCTION (U.K.) LIMITED: start_date=end_date=2007-09-28, interest_pct=50.0
  - KELVIN / ITHACA (NE) UKCS LIMITED: start_date=end_date=2007-09-28, interest_pct=27.5
  - KELVIN / TULLOW OIL SK LIMITED: start_date=end_date=2007-09-28, interest_pct=22.5
  - KESTREL / TAQA BRATANI LIMITED: start_date=end_date=2008-12-01, interest_pct=100.0
  - KEW / SPIRIT NORTH SEA GAS LIMITED: start_date=end_date=2012-07-26, interest_pct=100.0
  - KILMAR / ENERGEAN UK LTD: start_date=end_date=2008-12-18, interest_pct=68.0
  - KILMAR / HARBOUR ENERGY PETROLEUM RESOURCES LIMITED: start_date=end_date=2008-12-18, interest_pct=17.0
  - KILMAR / ROCKROSE (UKCS3) LIMITED: start_date=end_date=2008-12-18, interest_pct=15.0
  - KIMMERIDGE / PERENCO UK LIMITED: start_date=end_date=2011-12-14, interest_pct=100.0
  - KINNOULL / ARCO BRITISH LIMITED, LLC: start_date=end_date=2009-10-15, interest_pct=60.4
  - KINNOULL / BRITOIL LIMITED: start_date=end_date=2009-10-15, interest_pct=16.67
  - KINNOULL / ENI UK LIMITED: start_date=end_date=2009-10-15, interest_pct=16.66
  - KINNOULL / ITHACA SPL LIMITED: start_date=end_date=2009-10-15, interest_pct=6.27
  - KIRBY MISPERTON / THIRD ENERGY UK GAS LIMITED: start_date=end_date=2006-08-07, interest_pct=100.0
  - KIRKLEATHAM / EGDON RESOURCES U.K. LIMITED: start_date=end_date=2010-11-26, interest_pct=40.0
  - KIRKLEATHAM / MONTROSE INDUSTRIES LIMITED: start_date=end_date=2010-11-26, interest_pct=5.0
  - KIRKLEATHAM / ONE-DYAS UK LIMITED: start_date=end_date=2010-11-26, interest_pct=47.0
  - KIRKLEATHAM / YORKSHIRE EXPLORATION LIMITED: start_date=end_date=2010-11-26, interest_pct=8.0
  - KIRKLEATHAM / DESS ENERGY LIMITED: start_date=end_date=2016-09-29, interest_pct=47.0
  - KIRKLEATHAM / EGDON RESOURCES U.K. LIMITED: start_date=end_date=2016-09-29, interest_pct=40.0
  - KIRKLEATHAM / MONTROSE INDUSTRIES LIMITED: start_date=end_date=2016-09-29, interest_pct=5.0
  - KIRKLEATHAM / YORKSHIRE EXPLORATION LIMITED: start_date=end_date=2016-09-29, interest_pct=8.0
  - KYLE / CNR INTERNATIONAL (U.K.) DEVELOPMENTS LIMITED: start_date=end_date=2009-11-18, interest_pct=20.0
  - KYLE / CNR INTERNATIONAL (U.K.) LIMITED: start_date=end_date=2009-11-18, interest_pct=25.71
  - KYLE / DANA PETROLEUM (BVUK) LIMITED: start_date=end_date=2009-11-18, interest_pct=14.29
  - KYLE / PREMIER OIL UK LIMITED: start_date=end_date=2009-11-18, interest_pct=40.0
  - LAGGAN / INEOS E&P (UK) LIMITED: start_date=end_date=2011-05-17, interest_pct=20.0
  - LAGGAN / NEO NEXT+ ENERGY E&P UK LIMITED: start_date=end_date=2011-05-17, interest_pct=80.0
  - LANCASTER / PRAX HURRICANE GLA LIMITED: start_date=end_date=2017-07-04, interest_pct=50.0
  - LANCASTER / PRAX HURRICANE HOLDINGS LIMITED: start_date=end_date=2017-07-04, interest_pct=50.0
  - LANCASTER / PRAX UPSTREAM LIMITED: start_date=end_date=2017-07-04, interest_pct=0.0
  - LANCELOT / NOBLE ENERGY (ISE) LIMITED: start_date=end_date=2010-12-01, interest_pct=1.44
  - LANCELOT / NOBLE ENERGY (OILEX) LIMITED: start_date=end_date=2010-12-01, interest_pct=0.56
  - LANCELOT / PERENCO UK LIMITED: start_date=end_date=2010-12-01, interest_pct=98.0
  - LARCH / SPIRIT ENERGY NORTH SEA OIL LIMITED: start_date=end_date=2006-05-31, interest_pct=100.0
  - LEMAN [PERENCO][pt. of LEMAN] / PERENCO UK LIMITED: start_date=end_date=2011-02-02, interest_pct=78.26
  - LEMAN [PERENCO][pt. of LEMAN] / ROCKROSE UKCS15 LIMITED: start_date=end_date=2011-02-02, interest_pct=21.74
  - LENNOX / BHP BILLITON PETROLEUM GREAT BRITAIN LIMITED: start_date=end_date=2003-11-11, interest_pct=46.1
  - LENNOX / ENI ULX LIMITED: start_date=end_date=2003-11-11, interest_pct=45.0
  - LENNOX / PRIME AEP LIMITED: start_date=end_date=2003-11-11, interest_pct=8.9
  - LENNOX / WOODSIDE ENERGY (GREAT BRITAIN) LIMITED: start_date=end_date=2003-11-11, interest_pct=0.0
  - LIDSEY / ANGUS ENERGY WEALD BASIN NO.3 LIMITED: start_date=end_date=2014-01-09, interest_pct=90.0
  - LIDSEY / AZZURO RESOURCES PLC: start_date=end_date=2014-01-09, interest_pct=10.0
  - LOCHRANZA / CNS (E&P) LIMITED: start_date=end_date=2012-08-09, interest_pct=29.24
  - LOCHRANZA / NEO NEXT+ ENERGY E&P NORTH SEA UK LIMITED: start_date=end_date=2012-08-09, interest_pct=70.0
  - LOCHRANZA / ORANJE-NASSAU ENERGIE HANZE (UK) LIMITED: start_date=end_date=2012-08-09, interest_pct=0.76
  - LOIRSTON / APACHE BERYL I LIMITED: start_date=end_date=2012-12-21, interest_pct=50.0
  - LOIRSTON / BERYL NORTH SEA II LIMITED: start_date=end_date=2012-12-21, interest_pct=5.56
  - LOIRSTON / BERYL NORTH SEA LIMITED: start_date=end_date=2012-12-21, interest_pct=16.67
  - LOIRSTON / ENTERPRISE OIL LIMITED: start_date=end_date=2012-12-21, interest_pct=22.78
  - LOIRSTON / ITHACA SP E&P LIMITED: start_date=end_date=2012-12-21, interest_pct=5.0
  - LOMOND / BG INTERNATIONAL LIMITED: start_date=end_date=2011-02-02, interest_pct=100.0
  - LOYAL [Part of SCHIEHALLION] / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2014-11-18, interest_pct=50.0
  - LOYAL [Part of SCHIEHALLION] / ENTERPRISE OIL MIDDLE EAST LIMITED: start_date=end_date=2014-11-18, interest_pct=25.0
  - LOYAL [Part of SCHIEHALLION] / SHELL U.K. NORTH ATLANTIC LIMITED: start_date=end_date=2014-11-18, interest_pct=25.0
  - LYELL / CNR INTERNATIONAL (U.K.) DEVELOPMENTS LIMITED: start_date=end_date=2003-05-01, interest_pct=100.0
  - MACLURE / APACHE BERYL I LIMITED: start_date=end_date=2005-09-30, interest_pct=16.67
  - MACLURE / BRITOIL LIMITED: start_date=end_date=2005-09-30, interest_pct=33.33
  - MACLURE / ENTERPRISE OIL LIMITED: start_date=end_date=2005-09-30, interest_pct=7.59
  - MACLURE / HESS LIMITED: start_date=end_date=2005-09-30, interest_pct=7.41
  - MACLURE / ITHACA SP E&P LIMITED: start_date=end_date=2005-09-30, interest_pct=1.67
  - MACLURE / NEO NEXT+ ENERGY E&P NORTH SEA UK LIMITED: start_date=end_date=2005-09-30, interest_pct=33.33
  - MACLURE / APACHE BERYL I LIMITED: start_date=end_date=2012-12-21, interest_pct=16.67
  - MACLURE / BRITOIL LIMITED: start_date=end_date=2012-12-21, interest_pct=37.04
  - MACLURE / ENTERPRISE OIL LIMITED: start_date=end_date=2012-12-21, interest_pct=7.59
  - MACLURE / ITHACA SP E&P LIMITED: start_date=end_date=2012-12-21, interest_pct=0.52
  - MACLURE / NEO NEXT+ ENERGY E&P NORTH SEA UK LIMITED: start_date=end_date=2012-12-21, interest_pct=38.19
  - MADOES / ARCO BRITISH LIMITED, LLC: start_date=end_date=2009-02-28, interest_pct=31.37
  - MADOES / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2009-02-28, interest_pct=6.52
  - MADOES / ENI UK LIMITED: start_date=end_date=2009-02-28, interest_pct=8.63
  - MADOES / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2009-02-28, interest_pct=25.0
  - MADOES / NEO NEXT+ ENERGY PETROLEUM LIMITED: start_date=end_date=2009-02-28, interest_pct=3.48
  - MADOES / SHELL U.K. LIMITED: start_date=end_date=2009-02-28, interest_pct=25.0
  - MALORY / NOBLE ENERGY (ISE) LIMITED: start_date=end_date=2007-08-01, interest_pct=1.0
  - MALORY / NOBLE ENERGY (OILEX) LIMITED: start_date=end_date=2007-08-01, interest_pct=0.5
  - MALORY / ORANJE-NASSAU ENERGIE HANZE (UK) LIMITED: start_date=end_date=2007-08-01, interest_pct=22.5
  - MALORY / PERENCO GAS (UK) LIMITED: start_date=end_date=2007-08-01, interest_pct=8.5
  - MALORY / PERENCO UK LIMITED: start_date=end_date=2007-08-01, interest_pct=67.5
  - MALTON / THIRD ENERGY UK GAS LIMITED: start_date=end_date=2006-08-07, interest_pct=100.0
  - MARISHES / THIRD ENERGY UK GAS LIMITED: start_date=end_date=2006-08-07, interest_pct=100.0
  - MARNOCK [pt. of MARNOCK-SKUA] / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2017-03-31, interest_pct=86.5
  - MARNOCK [pt. of MARNOCK-SKUA] / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2017-03-31, interest_pct=13.5
  - MERCURY / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2011-02-02, interest_pct=73.33
  - MERCURY / ROCKROSE UKCS15 LIMITED: start_date=end_date=2011-02-02, interest_pct=26.67
  - MERGANSER / ENI UK LIMITED: start_date=end_date=2009-02-28, interest_pct=2.03
  - MERGANSER / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2009-02-28, interest_pct=44.0
  - MERGANSER / NEO NEXT+ ENERGY PETROLEUM LIMITED: start_date=end_date=2009-02-28, interest_pct=2.05
  - MERGANSER / PREMIER OIL E&P UK LIMITED: start_date=end_date=2009-02-28, interest_pct=7.92
  - MERGANSER / SHELL U.K. LIMITED: start_date=end_date=2009-02-28, interest_pct=44.0
  - MERLIN / FAIRFIELD FAGUS LIMITED: start_date=end_date=2008-04-30, interest_pct=70.0
  - MERLIN / MCX OSPREY (UK) LIMITED: start_date=end_date=2008-04-30, interest_pct=30.0
  - MILLER / BP EXPLORATION (ALPHA) LIMITED: start_date=end_date=2007-12-31, interest_pct=40.0
  - MILLER / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2007-12-31, interest_pct=12.0
  - MILLER / CHRYSAOR PRODUCTION (U.K.) LIMITED: start_date=end_date=2007-12-31, interest_pct=30.0
  - MILLER / SHELL U.K. LIMITED: start_date=end_date=2007-12-31, interest_pct=18.0
  - MINERVA / AMOCO (U.K.) EXPLORATION COMPANY, LLC: start_date=end_date=2011-02-02, interest_pct=0.0
  - MINERVA / AMOCO U.K.PETROLEUM LIMITED: start_date=end_date=2011-02-02, interest_pct=65.0
  - MINERVA / ROCKROSE UKCS15 LIMITED: start_date=end_date=2011-02-02, interest_pct=35.0
  - MINKE / DNO NORTH SEA (U.K.) LIMITED: start_date=end_date=2009-12-01, interest_pct=5.89
  - MINKE / INEOS UK SNS LIMITED: start_date=end_date=2009-12-01, interest_pct=35.84
  - MINKE / ITHACA (NE) UKCS LIMITED: start_date=end_date=2009-12-01, interest_pct=15.6
  - MINKE / PREMIER OIL E&P UK LIMITED: start_date=end_date=2009-12-01, interest_pct=42.67
  - MIRREN / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2009-02-28, interest_pct=44.69
  - MIRREN / ENI UK LIMITED: start_date=end_date=2009-02-28, interest_pct=9.83
  - MIRREN / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2009-02-28, interest_pct=21.0
  - MIRREN / NEO NEXT+ ENERGY PETROLEUM LIMITED: start_date=end_date=2009-02-28, interest_pct=3.48
  - MIRREN / SHELL U.K. LIMITED: start_date=end_date=2009-02-28, interest_pct=21.0
  - MONTROSE / ITHACA MA(NS) LIMITED: start_date=end_date=2006-10-31, interest_pct=41.03
  - MONTROSE / NEO NEXT + ENERGY RESOURCES UK LIMITED: start_date=end_date=2006-10-31, interest_pct=58.97
  - MORDRED / FIRST OIL EXPRO LIMITED: start_date=end_date=2010-12-01, interest_pct=8.33
  - MORDRED / PERENCO UK LIMITED: start_date=end_date=2010-12-01, interest_pct=91.67
  - MURDOCH / CHRYSAOR PRODUCTION (U.K.) LIMITED: start_date=end_date=2007-09-28, interest_pct=59.5
  - MURDOCH / ITHACA (NE) UKCS LIMITED: start_date=end_date=2007-09-28, interest_pct=26.4
  - MURDOCH / TULLOW OIL SK LIMITED: start_date=end_date=2007-09-28, interest_pct=14.1
  - NELSON / APACHE NORTH SEA LIMITED: start_date=end_date=2011-05-06, interest_pct=11.53
  - NELSON / ENTERPRISE OIL LIMITED: start_date=end_date=2011-05-06, interest_pct=36.88
  - NELSON / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2011-05-06, interest_pct=21.23
  - NELSON / PREMIER OIL UK LIMITED: start_date=end_date=2011-05-06, interest_pct=1.66
  - NELSON / ROCKROSE UKCS4 LIMITED: start_date=end_date=2011-05-06, interest_pct=7.47
  - NELSON / SHELL U.K. LIMITED: start_date=end_date=2011-05-06, interest_pct=21.23
  - NEPTUNE / AMOCO (U.K.) EXPLORATION COMPANY, LLC: start_date=end_date=2011-02-03, interest_pct=0.0
  - NEPTUNE / AMOCO U.K.PETROLEUM LIMITED: start_date=end_date=2011-02-03, interest_pct=40.53
  - NEPTUNE / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2011-02-03, interest_pct=59.47
  - NESS / APACHE BERYL I LIMITED: start_date=end_date=2003-05-01, interest_pct=50.0
  - NESS / ENTERPRISE OIL LIMITED: start_date=end_date=2003-05-01, interest_pct=22.78
  - NESS / HESS LIMITED: start_date=end_date=2003-05-01, interest_pct=22.22
  - NESS / ITHACA SP E&P LIMITED: start_date=end_date=2003-05-01, interest_pct=5.0
  - NESS / APACHE BERYL I LIMITED: start_date=end_date=2012-12-21, interest_pct=50.0
  - NESS / BERYL NORTH SEA II LIMITED: start_date=end_date=2012-12-21, interest_pct=5.56
  - NESS / BERYL NORTH SEA LIMITED: start_date=end_date=2012-12-21, interest_pct=16.67
  - NESS / ENTERPRISE OIL LIMITED: start_date=end_date=2012-12-21, interest_pct=22.78
  - NESS / ITHACA SP E&P LIMITED: start_date=end_date=2012-12-21, interest_pct=5.0
  - NETTLEHAM / STAR ENERGY OIL & GAS LIMITED: start_date=end_date=2011-07-05, interest_pct=100.0
  - NEVIS / APACHE BERYL I LIMITED: start_date=end_date=2003-05-01, interest_pct=44.59
  - NEVIS / ENTERPRISE OIL LIMITED: start_date=end_date=2003-05-01, interest_pct=14.81
  - NEVIS / HESS LIMITED: start_date=end_date=2003-05-01, interest_pct=37.35
  - NEVIS / ITHACA SP E&P LIMITED: start_date=end_date=2003-05-01, interest_pct=3.25
  - NEVIS / APACHE BERYL I LIMITED: start_date=end_date=2012-12-21, interest_pct=44.59
  - NEVIS / BERYL NORTH SEA II LIMITED: start_date=end_date=2012-12-21, interest_pct=9.34
  - NEVIS / BERYL NORTH SEA LIMITED: start_date=end_date=2012-12-21, interest_pct=28.01
  - NEVIS / ENTERPRISE OIL LIMITED: start_date=end_date=2012-12-21, interest_pct=14.81
  - NEVIS / ITHACA SP E&P LIMITED: start_date=end_date=2012-12-21, interest_pct=3.25
  - NICOL / CHRYSAOR PRODUCTION (U.K.) LIMITED: start_date=end_date=2009-12-11, interest_pct=18.0
  - NICOL / ENI UK LIMITED: start_date=end_date=2009-12-11, interest_pct=12.0
  - NICOL / PREMIER OIL UK LIMITED: start_date=end_date=2009-12-11, interest_pct=70.0
  - NINIAN / CNR INTERNATIONAL (U.K.) LIMITED: start_date=end_date=2003-06-10, interest_pct=87.06
  - NINIAN / ENI UK LIMITED: start_date=end_date=2003-06-10, interest_pct=12.94
  - NORTH VALIANT / BP EXPLORATION (ALPHA) LIMITED: start_date=end_date=2003-05-01, interest_pct=38.87
  - NORTH VALIANT / CHRYSAOR DEVELOPMENTS LIMITED: start_date=end_date=2003-05-01, interest_pct=61.13
  - NUGGETS N1 / NEO NEXT+ ENERGY E&P UK LIMITED: start_date=end_date=2005-07-01, interest_pct=100.0
  - NUGGETS N4 / NEO NEXT+ ENERGY E&P UK LIMITED: start_date=end_date=2005-07-01, interest_pct=100.0
  - ORCA / DNO NORTH SEA (U.K.) LIMITED: start_date=end_date=2009-12-01, interest_pct=5.89
  - ORCA / INEOS UK SNS LIMITED: start_date=end_date=2009-12-01, interest_pct=35.84
  - ORCA / ITHACA (NE) UKCS LIMITED: start_date=end_date=2009-12-01, interest_pct=15.6
  - ORCA / PREMIER OIL E&P UK LIMITED: start_date=end_date=2009-12-01, interest_pct=42.67
  - OSPREY / FAIRFIELD FAGUS LIMITED: start_date=end_date=2008-04-30, interest_pct=70.0
  - OSPREY / MCX OSPREY (UK) LIMITED: start_date=end_date=2008-04-30, interest_pct=30.0
  - PELICAN / TAQA BRATANI LIMITED: start_date=end_date=2008-12-01, interest_pct=100.0
  - PEREGRINE / CNOOC PETROLEUM EUROPE LIMITED: start_date=end_date=2011-10-19, interest_pct=36.54
  - PEREGRINE / EQUINOR WOS LIMITED: start_date=end_date=2011-10-19, interest_pct=26.69
  - PEREGRINE / NEO NEXT+ ENERGY E&P NORTH SEA UK LIMITED: start_date=end_date=2011-10-19, interest_pct=31.56
  - PEREGRINE / ONE-DYAS EOG LIMITED: start_date=end_date=2011-10-19, interest_pct=5.21
  - PICKERILL / ITHACA MA(NS) LIMITED: start_date=end_date=2009-11-13, interest_pct=5.22
  - PICKERILL / PERENCO UK LIMITED: start_date=end_date=2009-11-13, interest_pct=94.78
  - PICKERING / THIRD ENERGY UK GAS LIMITED: start_date=end_date=2006-08-07, interest_pct=100.0
  - PIERCE / ENTERPRISE OIL LIMITED: start_date=end_date=2011-12-19, interest_pct=42.79
  - PIERCE / ITHACA SPL LIMITED: start_date=end_date=2011-12-19, interest_pct=3.73
  - PIERCE / NEO NEXT+ ENERGY PETROLEUM LIMITED: start_date=end_date=2011-12-19, interest_pct=3.75
  - PIERCE / SHELL EP OFFSHORE VENTURES LIMITED: start_date=end_date=2011-12-19, interest_pct=39.73
  - PIERCE / SHELL UPSTREAM OVERSEAS SERVICES (I) LIMITED: start_date=end_date=2011-12-19, interest_pct=10.0
  - RAVENSPURN N[pt.of RAVENSPURN] / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2012-11-01, interest_pct=0.0
  - RAVENSPURN N[pt.of RAVENSPURN] / PERENCO UK LIMITED: start_date=end_date=2012-11-01, interest_pct=53.5
  - RAVENSPURN N[pt.of RAVENSPURN] / PREMIER OIL E&P UK EU LIMITED: start_date=end_date=2012-11-01, interest_pct=28.75
  - RAVENSPURN N[pt.of RAVENSPURN] / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2012-11-01, interest_pct=17.75
  - RHUM / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=1977-09-07, interest_pct=50.0
  - RHUM / IRANIAN OIL COMPANY (U.K.) LIMITED: start_date=end_date=1977-09-07, interest_pct=50.0
  - ROSS / NEO NEXT + ENERGY ALPHA LIMITED: start_date=end_date=2005-04-06, interest_pct=13.0
  - ROSS / NEO NEXT + ENERGY RESOURCES UK LIMITED: start_date=end_date=2005-04-06, interest_pct=56.18
  - ROSS / ROCKROSE UKCS4 LIMITED: start_date=end_date=2005-04-06, interest_pct=30.82
  - SALTIRE / ENI UK LIMITED: start_date=end_date=2004-12-31, interest_pct=20.0
  - SALTIRE / NEO NEXT + ENERGY ALPHA LIMITED: start_date=end_date=2004-12-31, interest_pct=19.56
  - SALTIRE / NEO NEXT + ENERGY NORTH SEA LIMITED: start_date=end_date=2004-12-31, interest_pct=16.67
  - SALTIRE / NEO NEXT + ENERGY RESOURCES UK LIMITED: start_date=end_date=2004-12-31, interest_pct=20.28
  - SALTIRE / TRANSWORLD PETROLEUM (U.K.) LIMITED: start_date=end_date=2004-12-31, interest_pct=23.5
  - SATURN (ANNABEL) / SPIRIT NORTH SEA GAS LIMITED: start_date=end_date=2003-09-09, interest_pct=100.0
  - SATURN (ANNABEL) / SPIRIT ENERGY NORTH SEA LIMITED: start_date=end_date=2016-05-17, interest_pct=100.0
  - SATURN (ANNABEL) / SPIRIT NORTH SEA GAS LIMITED: start_date=end_date=2016-05-17, interest_pct=0.0
  - SCAMPTON / ISLAND GAS LIMITED: start_date=end_date=2012-03-30, interest_pct=100.0
  - SCAMPTON NORTH / ISLAND GAS LIMITED: start_date=end_date=2012-03-30, interest_pct=100.0
  - SCAPA / ENI UK LIMITED: start_date=end_date=2003-11-01, interest_pct=20.0
  - SCAPA / NEO NEXT + ENERGY OIL TRADING LIMITED: start_date=end_date=2003-11-01, interest_pct=60.44
  - SCAPA / NEO NEXT + ENERGY RESOURCES UK LIMITED: start_date=end_date=2003-11-01, interest_pct=0.0
  - SCAPA / RIGEL PETROLEUM (NI) LIMITED: start_date=end_date=2003-11-01, interest_pct=19.56
  - SCHIEHALLION / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2002-07-23, interest_pct=3.0
  - SCHIEHALLION / BRITOIL LIMITED: start_date=end_date=2002-07-23, interest_pct=30.35
  - SCHIEHALLION / EQUINOR UK LIMITED: start_date=end_date=2002-07-23, interest_pct=5.88
  - SCHIEHALLION / HESS LIMITED: start_date=end_date=2002-07-23, interest_pct=15.66
  - SCHIEHALLION / ITHACA SP E&P LIMITED: start_date=end_date=2002-07-23, interest_pct=5.88
  - SCHIEHALLION / MURPHY PETROLEUM LIMITED: start_date=end_date=2002-07-23, interest_pct=5.88
  - SCHIEHALLION / SHELL U.K. LIMITED: start_date=end_date=2002-07-23, interest_pct=33.35
  - SCHOONER / DNO NORTH SEA (U.K.) LIMITED: start_date=end_date=2008-03-26, interest_pct=4.83
  - SCHOONER / ITHACA (NE) UKCS LIMITED: start_date=end_date=2008-03-26, interest_pct=4.83
  - SCHOONER / TULLOW OIL SK LIMITED: start_date=end_date=2008-03-26, interest_pct=90.34
  - SCHOONER / DNO NORTH SEA (U.K.) LIMITED: start_date=end_date=2011-01-31, interest_pct=6.9
  - SCHOONER / TULLOW OIL SK LIMITED: start_date=end_date=2011-01-31, interest_pct=93.1
  - SCOTER / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2002-12-20, interest_pct=44.0
  - SCOTER / PREMIER OIL E&P UK LIMITED: start_date=end_date=2002-12-20, interest_pct=12.0
  - SCOTER / SHELL U.K. LIMITED: start_date=end_date=2002-12-20, interest_pct=44.0
  - SCOTT / APACHE BERYL I LIMITED: start_date=end_date=2007-05-17, interest_pct=10.47
  - SCOTT / CNOOC PETROLEUM EUROPE LIMITED: start_date=end_date=2007-05-17, interest_pct=41.89
  - SCOTT / EQUINOR WOS LIMITED: start_date=end_date=2007-05-17, interest_pct=20.64
  - SCOTT / NEO NEXT+ ENERGY OFFSHORE UK LIMITED: start_date=end_date=2007-05-17, interest_pct=5.16
  - SCOTT / PREMIER OIL UK LIMITED: start_date=end_date=2007-05-17, interest_pct=21.84
  - SHAMROCK / SHELL U.K. LIMITED: start_date=end_date=2007-02-05, interest_pct=100.0
  - SHEARWATER / ARCO BRITISH LIMITED, LLC: start_date=end_date=2003-12-01, interest_pct=27.5
  - SHEARWATER / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2003-12-01, interest_pct=44.5
  - SHEARWATER / SHELL U.K. LIMITED: start_date=end_date=2003-12-01, interest_pct=28.0
  - SINGLETON / ISLAND GAS (SINGLETON) LIMITED: start_date=end_date=2012-12-21, interest_pct=100.0
  - SINOPE / CHRYSAOR PRODUCTION (U.K.) LIMITED: start_date=end_date=2007-06-28, interest_pct=20.0
  - SINOPE / EQUINOR UK LIMITED: start_date=end_date=2007-06-28, interest_pct=30.0
  - SINOPE / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2007-06-28, interest_pct=50.0
  - SKENE / APACHE BERYL I LIMITED: start_date=end_date=2012-12-21, interest_pct=38.21
  - SKENE / BERYL NORTH SEA II LIMITED: start_date=end_date=2012-12-21, interest_pct=2.27
  - SKENE / BERYL NORTH SEA LIMITED: start_date=end_date=2012-12-21, interest_pct=6.81
  - SKENE / ENTERPRISE OIL LIMITED: start_date=end_date=2012-12-21, interest_pct=15.89
  - SKENE / ITHACA SP E&P LIMITED: start_date=end_date=2012-12-21, interest_pct=3.49
  - SKENE / SHELL BENIN UPSTREAM LTD: start_date=end_date=2012-12-21, interest_pct=15.89
  - SKENE / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2012-12-21, interest_pct=33.33
  - SOUTH CORMORANT / TAQA BRATANI LIMITED: start_date=end_date=2008-12-01, interest_pct=100.0
  - SOUTH SEAN / ARCO BRITISH LIMITED, LLC: start_date=end_date=2003-05-01, interest_pct=25.0
  - SOUTH SEAN / BRITOIL LIMITED: start_date=end_date=2003-05-01, interest_pct=25.0
  - SOUTH SEAN / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2003-05-01, interest_pct=25.0
  - SOUTH SEAN / SHELL U.K. LIMITED: start_date=end_date=2003-05-01, interest_pct=25.0
  - SOUTH VALIANT / ARCO BRITISH LIMITED, LLC: start_date=end_date=2004-08-23, interest_pct=12.5
  - SOUTH VALIANT / BP EXPLORATION BETA LIMITED: start_date=end_date=2004-08-23, interest_pct=37.5
  - SOUTH VALIANT / CHRYSAOR DEVELOPMENTS LIMITED: start_date=end_date=2004-08-23, interest_pct=12.5
  - SOUTH VALIANT / CHRYSAOR PETROLEUM LIMITED: start_date=end_date=2004-08-23, interest_pct=25.0
  - SOUTH VALIANT / CHRYSAOR (U.K.) ALPHA LIMITED: start_date=end_date=2004-08-23, interest_pct=12.5
  - STAINTON / ISLAND GAS LIMITED: start_date=end_date=2012-03-30, interest_pct=100.0
  - STATFJORD / PHILLIPS 66 LIMITED: start_date=end_date=2006-06-30, interest_pct=33.34
  - STATFJORD / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2006-06-30, interest_pct=66.66
  - STRATHSPEY / CNR INTERNATIONAL (U.K.) DEVELOPMENTS LIMITED: start_date=end_date=2003-05-07, interest_pct=6.5
  - STRATHSPEY / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2003-05-07, interest_pct=13.25
  - STRATHSPEY / ITHACA OIL AND GAS LIMITED: start_date=end_date=2003-05-07, interest_pct=67.0
  - STRATHSPEY / SHELL U.K. LIMITED: start_date=end_date=2003-05-07, interest_pct=13.25
  - SYCAMORE / SPIRIT ENERGY NORTH SEA OIL LIMITED: start_date=end_date=2006-05-31, interest_pct=100.0
  - TERN / TAQA BRATANI LIMITED: start_date=end_date=2008-12-01, interest_pct=100.0
  - TETHYS / INEOS UK SNS LIMITED: start_date=end_date=2008-10-31, interest_pct=75.0
  - TETHYS / PHILLIPS 66 LIMITED: start_date=end_date=2008-10-31, interest_pct=25.0
  - THAMES / PERENCO UK LIMITED: start_date=end_date=2010-12-01, interest_pct=23.33
  - THAMES / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2010-12-01, interest_pct=10.0
  - THAMES / TULLOW OIL SK LIMITED: start_date=end_date=2010-12-01, interest_pct=66.67
  - THELMA / CNR INTERNATIONAL (U.K.) LIMITED: start_date=end_date=2003-05-01, interest_pct=100.0
  - THURNE / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2008-11-18, interest_pct=13.04
  - THURNE / TULLOW OIL SK LIMITED: start_date=end_date=2008-11-18, interest_pct=86.96
  - TIFFANY / CNR INTERNATIONAL (U.K.) LIMITED: start_date=end_date=2003-05-01, interest_pct=100.0
  - TONI / CNR INTERNATIONAL (U.K.) LIMITED: start_date=end_date=2003-05-01, interest_pct=100.0
  - TORMORE / INEOS E&P (UK) LIMITED: start_date=end_date=2011-05-17, interest_pct=20.0
  - TORMORE / NEO NEXT+ ENERGY E&P UK LIMITED: start_date=end_date=2011-05-17, interest_pct=80.0
  - TWEEDSMUIR / FIRST OIL EXPRO LIMITED: start_date=end_date=2005-08-19, interest_pct=5.57
  - TWEEDSMUIR / NEO NEXT + ENERGY ALPHA LIMITED: start_date=end_date=2005-08-19, interest_pct=19.56
  - TWEEDSMUIR / NEO NEXT + ENERGY NORTH SEA LIMITED: start_date=end_date=2005-08-19, interest_pct=16.67
  - TWEEDSMUIR / NEO NEXT + ENERGY RESOURCES UK LIMITED: start_date=end_date=2005-08-19, interest_pct=34.71
  - TWEEDSMUIR / TRANSWORLD PETROLEUM (U.K.) LIMITED: start_date=end_date=2005-08-19, interest_pct=23.5
  - TYNE NORTH / PERENCO UK LIMITED: start_date=end_date=2011-05-31, interest_pct=80.0
  - TYNE NORTH / SERICA ENERGY CHINOOK LIMITED: start_date=end_date=2011-05-31, interest_pct=20.0
  - TYNE SOUTH / PERENCO UK LIMITED: start_date=end_date=2011-05-31, interest_pct=80.0
  - TYNE SOUTH / SERICA ENERGY CHINOOK LIMITED: start_date=end_date=2011-05-31, interest_pct=20.0
  - VALKYRIE / BRITOIL LIMITED: start_date=end_date=2004-01-01, interest_pct=25.0
  - VALKYRIE / CHRYSAOR PETROLEUM LIMITED: start_date=end_date=2004-01-01, interest_pct=50.0
  - VALKYRIE / SERICA ENERGY MISTRAL LIMITED: start_date=end_date=2004-01-01, interest_pct=25.0
  - VAMPIRE / BRITOIL LIMITED: start_date=end_date=2003-05-01, interest_pct=50.0
  - VAMPIRE / CHRYSAOR PETROLEUM LIMITED: start_date=end_date=2003-05-01, interest_pct=50.0
  - VANGUARD / BP EXPLORATION (ALPHA) LIMITED: start_date=end_date=2003-05-01, interest_pct=50.0
  - VANGUARD / CHRYSAOR PETROLEUM LIMITED: start_date=end_date=2003-05-01, interest_pct=50.0
  - VICTOR / CALENERGY GAS LIMITED: start_date=end_date=2007-11-30, interest_pct=5.0
  - VICTOR / CHRYSAOR (U.K.) THETA LIMITED: start_date=end_date=2007-11-30, interest_pct=20.0
  - VICTOR / DANA PETROLEUM (E&P) LIMITED: start_date=end_date=2007-11-30, interest_pct=10.0
  - VICTOR / ESSO EXPLORATION AND PRODUCTION UK LIMITED: start_date=end_date=2007-11-30, interest_pct=25.0
  - VICTOR / INEOS UK SNS LIMITED: start_date=end_date=2007-11-30, interest_pct=10.0
  - VICTOR / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2007-11-30, interest_pct=30.0
  - VICTORIA / NEO NEXT+ ENERGY (CNS) LIMITED: start_date=end_date=2010-06-30, interest_pct=25.0
  - VICTORIA / NEO NEXT+ ENERGY (SNS) LIMITED: start_date=end_date=2010-06-30, interest_pct=50.0
  - VICTORIA / PHILLIPS 66 LIMITED: start_date=end_date=2010-06-30, interest_pct=25.0
  - VIKING A [pt of VIKING GROUP] / BRITOIL LIMITED: start_date=end_date=2003-05-01, interest_pct=50.0
  - VIKING A [pt of VIKING GROUP] / CHRYSAOR PETROLEUM LIMITED: start_date=end_date=2003-05-01, interest_pct=10.0
  - VIKING A [pt of VIKING GROUP] / PHILLIPS 66 LIMITED: start_date=end_date=2003-05-01, interest_pct=40.0
  - VIKING B [pt of VIKING GROUP] / BRITOIL LIMITED: start_date=end_date=2003-05-01, interest_pct=50.0
  - VIKING B [pt of VIKING GROUP] / CHRYSAOR PETROLEUM LIMITED: start_date=end_date=2003-05-01, interest_pct=10.0
  - VIKING B [pt of VIKING GROUP] / PHILLIPS 66 LIMITED: start_date=end_date=2003-05-01, interest_pct=40.0
  - VIKING C [pt of VIKING GROUP] / BRITOIL LIMITED: start_date=end_date=2003-05-01, interest_pct=50.0
  - VIKING C [pt of VIKING GROUP] / CHRYSAOR PETROLEUM LIMITED: start_date=end_date=2003-05-01, interest_pct=10.0
  - VIKING C [pt of VIKING GROUP] / PHILLIPS 66 LIMITED: start_date=end_date=2003-05-01, interest_pct=40.0
  - VIKING D [pt of VIKING GROUP] / BRITOIL LIMITED: start_date=end_date=2003-05-01, interest_pct=50.0
  - VIKING D [pt of VIKING GROUP] / CHRYSAOR PETROLEUM LIMITED: start_date=end_date=2003-05-01, interest_pct=10.0
  - VIKING D [pt of VIKING GROUP] / PHILLIPS 66 LIMITED: start_date=end_date=2003-05-01, interest_pct=40.0
  - VIKING E [pt of VIKING GROUP] / BRITOIL LIMITED: start_date=end_date=2003-05-01, interest_pct=50.0
  - VIKING E [pt of VIKING GROUP] / CHRYSAOR PETROLEUM LIMITED: start_date=end_date=2003-05-01, interest_pct=10.0
  - VIKING E [pt of VIKING GROUP] / PHILLIPS 66 LIMITED: start_date=end_date=2003-05-01, interest_pct=40.0
  - VISCOUNT / BRITOIL LIMITED: start_date=end_date=2003-05-01, interest_pct=50.0
  - VISCOUNT / CHRYSAOR PETROLEUM LIMITED: start_date=end_date=2003-05-01, interest_pct=50.0
  - VIXEN / BRITOIL LIMITED: start_date=end_date=2003-05-01, interest_pct=50.0
  - VIXEN / PHILLIPS 66 LIMITED: start_date=end_date=2003-05-01, interest_pct=50.0
  - VULCAN / ARCO BRITISH LIMITED, LLC: start_date=end_date=2004-08-23, interest_pct=7.88
  - VULCAN / BP EXPLORATION (ALPHA) LIMITED: start_date=end_date=2004-08-23, interest_pct=42.13
  - VULCAN / CHRYSAOR DEVELOPMENTS LIMITED: start_date=end_date=2004-08-23, interest_pct=7.88
  - VULCAN / CHRYSAOR PRODUCTION (U.K.) LIMITED: start_date=end_date=2004-08-23, interest_pct=34.25
  - VULCAN / CHRYSAOR (U.K.) ALPHA LIMITED: start_date=end_date=2004-08-23, interest_pct=7.88
  - WELTON / ISLAND GAS LIMITED: start_date=end_date=2012-03-30, interest_pct=100.0
  - WENLOCK / ENERGEAN UK LTD: start_date=end_date=2008-12-18, interest_pct=80.0
  - WENLOCK / HARBOUR ENERGY PETROLEUM RESOURCES LIMITED: start_date=end_date=2008-12-18, interest_pct=20.0
  - WENSUM / PERENCO UK LIMITED: start_date=end_date=2010-12-01, interest_pct=23.33
  - WENSUM / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2010-12-01, interest_pct=10.0
  - WENSUM / TULLOW OIL SK LIMITED: start_date=end_date=2010-12-01, interest_pct=66.67
  - WEST BRAE / BP EXPLORATION OPERATING COMPANY LIMITED: start_date=end_date=2009-01-09, interest_pct=27.7
  - WEST BRAE / FUJAIRAH OIL AND GAS UK 12 LIMITED: start_date=end_date=2009-01-09, interest_pct=38.0
  - WEST BRAE / FUJAIRAH OIL AND GAS UK LLC: start_date=end_date=2009-01-09, interest_pct=0.0
  - WEST BRAE / ITHACA (NE) UKCS LIMITED: start_date=end_date=2009-01-09, interest_pct=2.0
  - WEST BRAE / NEO NEXT+ ENERGY PETROLEUM LIMITED: start_date=end_date=2009-01-09, interest_pct=6.3
  - WEST BRAE / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2009-01-09, interest_pct=8.0
  - WEST BRAE / TAQA BRATANI LIMITED: start_date=end_date=2009-01-09, interest_pct=14.0
  - WEST BRAE / TAQA BRATANI LNS LIMITED: start_date=end_date=2009-01-09, interest_pct=4.0
  - WHITTLE / AMOCO (U.K.) EXPLORATION COMPANY, LLC: start_date=end_date=2011-02-02, interest_pct=0.0
  - WHITTLE / AMOCO U.K.PETROLEUM LIMITED: start_date=end_date=2011-02-02, interest_pct=66.3
  - WHITTLE / ROCKROSE UKCS15 LIMITED: start_date=end_date=2011-02-02, interest_pct=33.7
  - WINGATE / GAS-UNION GMBH: start_date=end_date=2008-10-01, interest_pct=15.0
  - WINGATE / WINTERSHALL NOORDZEE B.V.: start_date=end_date=2008-10-01, interest_pct=49.5
  - WINGATE / XTO UK, LTD: start_date=end_date=2008-10-01, interest_pct=15.5
  - WINGATE / ZMB GMBH: start_date=end_date=2008-10-01, interest_pct=20.0
  - WISSEY / DNO NORTH SEA (U.K.) LIMITED: start_date=end_date=2008-11-18, interest_pct=18.75
  - WISSEY / FIRST OIL EXPRO LIMITED: start_date=end_date=2008-11-18, interest_pct=18.75
  - WISSEY / TULLOW OIL SK LIMITED: start_date=end_date=2008-11-18, interest_pct=62.5
  - WOLLASTON / AMOCO (U.K.) EXPLORATION COMPANY, LLC: start_date=end_date=2011-02-02, interest_pct=0.0
  - WOLLASTON / AMOCO U.K.PETROLEUM LIMITED: start_date=end_date=2011-02-02, interest_pct=66.3
  - WOLLASTON / ROCKROSE UKCS15 LIMITED: start_date=end_date=2011-02-02, interest_pct=33.7
  - WYTCH FARM / ITHACA DORSET LIMITED: start_date=end_date=2011-12-14, interest_pct=7.43
  - WYTCH FARM / NEO NEXT+ ENERGY E&P NORTH SEA UK LIMITED: start_date=end_date=2011-12-14, interest_pct=7.43
  - WYTCH FARM / NEO NEXT + ENERGY NORTH SEA LIMITED: start_date=end_date=2011-12-14, interest_pct=4.95
  - WYTCH FARM / PERENCO UK LIMITED: start_date=end_date=2011-12-14, interest_pct=67.81
  - WYTCH FARM / PREMIER OIL UK LIMITED: start_date=end_date=2011-12-14, interest_pct=12.38
  - YARE / PERENCO UK LIMITED: start_date=end_date=2010-12-01, interest_pct=23.33
  - YARE / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2010-12-01, interest_pct=10.0
  - YARE / TULLOW OIL SK LIMITED: start_date=end_date=2010-12-01, interest_pct=66.67
  - YORK / SPIRIT ENERGY RESOURCES LIMITED: start_date=end_date=2010-09-13, interest_pct=100.0
- 241 zero-interest rows, retained unfiltered (is_zero_interest=true), meaning not investigated.
- Of those, 218 also have Operator Flag = 'Y' in the raw workbook (an operator with no recorded equity interest), e.g.:
  - AFFLECK / NEO NEXT+ ENERGY PUK LIMITED: start=2026-07-01, end=None
  - AIRTH COAL BED METHANE DEVT. / DART ENERGY (EUROPE) LIMITED: start=2007-03-30, end=2014-10-13
  - AIRTH COAL BED METHANE DEVT. / IGAS ENERGY PRODUCTION LIMITED: start=2015-05-06, end=2015-07-01
  - ALISON [CENTRICA] / SPIRIT NORTH SEA GAS LIMITED: start=2016-05-17, end=2016-05-17
  - ALWYN EAST / NEO NEXT+ ENERGY E&P UK LIMITED: start=2026-07-01, end=None
- 1187 open-ended rows (end_date is null).
- 0 sentinel start-date rows in the current workbook (none found, as in milestone 1).

These issues are not blockers for field-name matching and are not resolved here; they must be addressed before interval joins begin (spec section 15.8 step 4).
