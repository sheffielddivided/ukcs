# Equity publication-window and coverage-policy decision checkpoint

Diagnostic checkpoint only. No build.py integration, no docs/data/equity artifacts, no UI changes, no company aliases, no equity-attributable production published. This report computes evidence for a human decision; it does not make the decision.

## 1. Candidate publication window comparison

### Window starting 200001

| Stream | Overall coverage | Lowest month | Median month | At 100% | 99.5-100% | 95-99.5% | Below 95% | Longest run <95% | Months |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| oil_mbd | 76.027% | 6.512% | 97.146% | 98 | 6 | 100 | 114 | 103 | 318 |
| dry_gas_mmscfd | 83.038% | 23.827% | 98.736% | 25 | 90 | 108 | 95 | 87 | 318 |
| assoc_gas_mmscfd | 78.99% | 6.842% | 99.167% | 98 | 46 | 63 | 111 | 102 | 318 |
| condensate_mbd | 83.67% | 11.004% | 98.674% | 108 | 5 | 109 | 96 | 66 | 318 |

- oil_mbd excluded production by category: {'pre_equity_history': 87693.971, 'unmatched': 4021.277, 'month_start_boundary': 406.784, 'future_only': 110.342}
- dry_gas_mmscfd excluded production by category: {'pre_equity_history': 122582.208, 'unmatched': 7468.756, 'month_start_boundary': 480.717, 'future_only': 0.0}
- assoc_gas_mmscfd excluded production by category: {'pre_equity_history': 258505.737, 'unmatched': 1483.105, 'month_start_boundary': 632.755, 'future_only': 82.734}
- condensate_mbd excluded production by category: {'pre_equity_history': 385.846, 'unmatched': 4.053, 'month_start_boundary': 1.431, 'future_only': 0.0}

### Window starting 200501

| Stream | Overall coverage | Lowest month | Median month | At 100% | 99.5-100% | 95-99.5% | Below 95% | Longest run <95% | Months |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| oil_mbd | 95.172% | 78.242% | 98.034% | 98 | 6 | 100 | 54 | 43 | 258 |
| dry_gas_mmscfd | 97.049% | 86.488% | 99.071% | 25 | 90 | 108 | 35 | 27 | 258 |
| assoc_gas_mmscfd | 96.583% | 83.274% | 99.635% | 98 | 46 | 63 | 51 | 42 | 258 |
| condensate_mbd | 96.641% | 78.709% | 99.042% | 108 | 5 | 109 | 36 | 19 | 258 |

- oil_mbd excluded production by category: {'pre_equity_history': 11318.03, 'unmatched': 708.195, 'month_start_boundary': 187.912, 'future_only': 110.342}
- dry_gas_mmscfd excluded production by category: {'pre_equity_history': 12693.768, 'unmatched': 1147.75, 'month_start_boundary': 284.957, 'future_only': 0.0}
- assoc_gas_mmscfd excluded production by category: {'pre_equity_history': 27357.077, 'unmatched': 338.595, 'month_start_boundary': 258.227, 'future_only': 82.734}
- condensate_mbd excluded production by category: {'pre_equity_history': 55.026, 'unmatched': 0.327, 'month_start_boundary': 0.718, 'future_only': 0.0}

### Window starting 200701

| Stream | Overall coverage | Lowest month | Median month | At 100% | 99.5-100% | 95-99.5% | Below 95% | Longest run <95% | Months |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| oil_mbd | 97.303% | 90.496% | 98.715% | 98 | 6 | 100 | 30 | 19 | 234 |
| dry_gas_mmscfd | 98.375% | 91.887% | 99.243% | 25 | 90 | 108 | 11 | 5 | 234 |
| assoc_gas_mmscfd | 98.144% | 90.253% | 99.771% | 98 | 46 | 63 | 27 | 18 | 234 |
| condensate_mbd | 97.936% | 78.709% | 99.255% | 108 | 5 | 108 | 13 | 5 | 234 |

- oil_mbd excluded production by category: {'unmatched': 192.123, 'pre_equity_history': 5514.979, 'month_start_boundary': 62.198, 'future_only': 110.342}
- dry_gas_mmscfd excluded production by category: {'unmatched': 550.866, 'pre_equity_history': 5571.812, 'month_start_boundary': 261.309, 'future_only': 0.0}
- assoc_gas_mmscfd excluded production by category: {'unmatched': 140.576, 'pre_equity_history': 12236.329, 'month_start_boundary': 221.129, 'future_only': 82.734}
- condensate_mbd excluded production by category: {'unmatched': 0.163, 'pre_equity_history': 27.702, 'month_start_boundary': 0.46, 'future_only': 0.0}

### Window starting 200901

| Stream | Overall coverage | Lowest month | Median month | At 100% | 99.5-100% | 95-99.5% | Below 95% | Longest run <95% | Months |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| oil_mbd | 98.271% | 92.263% | 99.493% | 98 | 6 | 99 | 7 | 3 | 210 |
| dry_gas_mmscfd | 99.001% | 91.887% | 99.97% | 25 | 90 | 92 | 3 | 2 | 210 |
| assoc_gas_mmscfd | 99.285% | 92.565% | 99.887% | 98 | 46 | 61 | 5 | 3 | 210 |
| condensate_mbd | 98.65% | 91.585% | 100.0% | 108 | 5 | 92 | 5 | 2 | 210 |

- oil_mbd excluded production by category: {'pre_equity_history': 2982.748, 'unmatched': 51.081, 'month_start_boundary': 36.289, 'future_only': 110.342}
- dry_gas_mmscfd excluded production by category: {'pre_equity_history': 2890.869, 'unmatched': 125.562, 'month_start_boundary': 181.463, 'future_only': 0.0}
- assoc_gas_mmscfd excluded production by category: {'pre_equity_history': 3716.819, 'unmatched': 58.761, 'month_start_boundary': 198.17, 'future_only': 82.734}
- condensate_mbd excluded production by category: {'pre_equity_history': 14.368, 'unmatched': 0.048, 'month_start_boundary': 0.266, 'future_only': 0.0}

### Window starting 201001

| Stream | Overall coverage | Lowest month | Median month | At 100% | 99.5-100% | 95-99.5% | Below 95% | Longest run <95% | Months |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| oil_mbd | 98.624% | 95.142% | 99.96% | 98 | 6 | 94 | 0 | 0 | 198 |
| dry_gas_mmscfd | 99.25% | 92.416% | 99.972% | 25 | 90 | 82 | 1 | 1 | 198 |
| assoc_gas_mmscfd | 99.619% | 97.948% | 99.994% | 98 | 46 | 54 | 0 | 0 | 198 |
| condensate_mbd | 98.958% | 94.572% | 100.0% | 108 | 5 | 84 | 1 | 1 | 198 |

- oil_mbd excluded production by category: {'unmatched': 18.03, 'pre_equity_history': 2161.196, 'month_start_boundary': 24.385, 'future_only': 110.342}
- dry_gas_mmscfd excluded production by category: {'unmatched': 40.85, 'pre_equity_history': 1962.878, 'month_start_boundary': 181.463, 'future_only': 0.0}
- assoc_gas_mmscfd excluded production by category: {'unmatched': 30.822, 'pre_equity_history': 1808.759, 'month_start_boundary': 54.345, 'future_only': 82.734}
- condensate_mbd excluded production by category: {'unmatched': 0.003, 'pre_equity_history': 9.898, 'month_start_boundary': 0.266, 'future_only': 0.0}

### Window starting 201201

| Stream | Overall coverage | Lowest month | Median month | At 100% | 99.5-100% | 95-99.5% | Below 95% | Longest run <95% | Months |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| oil_mbd | 99.025% | 95.527% | 100.0% | 98 | 6 | 70 | 0 | 0 | 174 |
| dry_gas_mmscfd | 99.408% | 98.03% | 99.977% | 24 | 88 | 62 | 0 | 0 | 174 |
| assoc_gas_mmscfd | 99.688% | 97.948% | 100.0% | 98 | 37 | 39 | 0 | 0 | 174 |
| condensate_mbd | 99.078% | 94.572% | 100.0% | 108 | 3 | 62 | 1 | 1 | 174 |

- oil_mbd excluded production by category: {'pre_equity_history': 1242.689, 'unmatched': 4.327, 'month_start_boundary': 20.852, 'future_only': 110.342}
- dry_gas_mmscfd excluded production by category: {'pre_equity_history': 1380.389, 'unmatched': 15.036, 'month_start_boundary': 19.09, 'future_only': 0.0}
- assoc_gas_mmscfd excluded production by category: {'pre_equity_history': 1266.215, 'unmatched': 11.703, 'month_start_boundary': 7.025, 'future_only': 82.734}
- condensate_mbd excluded production by category: {'pre_equity_history': 6.595, 'unmatched': 0.0, 'month_start_boundary': 0.083, 'future_only': 0.0}

### Window starting 201501

| Stream | Overall coverage | Lowest month | Median month | At 100% | 99.5-100% | 95-99.5% | Below 95% | Longest run <95% | Months |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| oil_mbd | 99.348% | 96.637% | 100.0% | 98 | 3 | 37 | 0 | 0 | 138 |
| dry_gas_mmscfd | 99.693% | 98.389% | 99.984% | 24 | 86 | 28 | 0 | 0 | 138 |
| assoc_gas_mmscfd | 99.757% | 97.948% | 100.0% | 98 | 14 | 26 | 0 | 0 | 138 |
| condensate_mbd | 99.615% | 97.429% | 100.0% | 108 | 2 | 28 | 0 | 0 | 138 |

- oil_mbd excluded production by category: {'unmatched': 0.0, 'pre_equity_history': 602.432, 'month_start_boundary': 18.603, 'future_only': 110.342}
- dry_gas_mmscfd excluded production by category: {'unmatched': 14.404, 'pre_equity_history': 493.991, 'month_start_boundary': 19.09, 'future_only': 0.0}
- assoc_gas_mmscfd excluded production by category: {'unmatched': 0.0, 'pre_equity_history': 788.642, 'month_start_boundary': 5.978, 'future_only': 82.734}
- condensate_mbd excluded production by category: {'unmatched': 0.0, 'pre_equity_history': 1.822, 'month_start_boundary': 0.083, 'future_only': 0.0}

## 2. Stability thresholds by stream

First month after which coverage never again falls below the threshold (None = no such month exists in the observed data):

| Stream | Never below 95% from... | Never below 99% from... | Never below 99.5% from... |
| --- | --- | --- | --- |
| oil_mbd | 200911 | None | None |
| dry_gas_mmscfd | 201103 | 201707 | 201707 |
| assoc_gas_mmscfd | 200907 | 201703 | None |
| condensate_mbd | 201303 | 201707 | 201707 |

### Breach cause analysis (dominant excluded category per below-threshold month)

- oil_mbd (months below 95%): {'pre_equity_history': 405, 'unmatched': 4}
- dry_gas_mmscfd (months below 95%): {'pre_equity_history': 276, 'unmatched': 16, 'month_start_boundary': 1}
- assoc_gas_mmscfd (months below 95%): {'pre_equity_history': 402, 'unmatched': 4}
- condensate_mbd (months below 95%): {'pre_equity_history': 264, 'unmatched': 29}

Across every stream, `pre_equity_history` dominates almost every below-threshold month before the 2000s (see UKCS_DESIGN_v2.md section 15.10) - low coverage is caused by the source genuinely lacking equity records for that era, not by unmatched fields, boundary effects, future-only equity, or quarantined overlaps, all of which are minor contributors by comparison.

## 3. Candidate publication policy assessment

### Policy A: Fixed start date

- Comparability across time: High - every published month has the same coverage floor, so period-over-period comparison is safe by construction.
- Risk of misleading users: Low, provided the start date is chosen from persistent (not one-off) coverage.
- Implementation complexity: Low - a single constant date gate in the build.
- Transparency: Moderate - excludes data outright rather than showing it with a caveat; must be documented prominently so 'no data before X' is not read as 'no production before X'.
- Suitability for investor-relations analysis: High - investor-relations users need a stable, comparable series more than they need every available data point.

### Policy B: Dynamic coverage threshold

- Comparability across time: Low - a stream could gain or lose months as coverage crosses 95% in either direction between builds if the underlying source data changes, silently changing which periods are comparable.
- Risk of misleading users: High - a user comparing two builds could see a formerly-published month disappear, or a previously-missing month reappear, with no visible reason.
- Implementation complexity: Moderate - needs per-month, per-stream gating logic and a way to signal 'this month exists in principle but coverage dropped below the bar'.
- Transparency: n/a
- Suitability for investor-relations analysis: Low - instability in what is published is the opposite of what an investor-relations audience needs.

### Policy C: Publish all periods with coverage warnings

- Comparability across time: Very low for early periods - showing coverage_pct honestly does not fix the fact that 0-10% coverage in the 1970s-1990s is not a usable equity-attributable production series, only a labelled unusable one.
- Risk of misleading users: High despite the labelling - a chart that visually shows a full multi-decade series, with a small coverage indicator, invites exactly the kind of quick misread this project exists to avoid. Technical transparency (coverage_pct is present) does not equal analytical usability.
- Implementation complexity: Low - no gating logic needed.
- Transparency: n/a
- Suitability for investor-relations analysis: Low, for the same reason - an investor-relations user skimming a chart will see a full historical series and reasonably assume it means something, coverage caveat or not.

### Policy D: Hybrid: fixed start date + monthly coverage + warning threshold

- Comparability across time: High within the published window (same floor as Policy A), plus a finer-grained warning signal for the (rare, within-window) months that dip between 95% and 99.5%.
- Risk of misleading users: Low - the published window is stable and gated, and the warning threshold catches genuine within-window softness (e.g. a field temporarily quarantined) without hiding it or excluding the whole month.
- Implementation complexity: Moderate - both a fixed gate and a per-month warning need implementing, but each is simple on its own.
- Transparency: n/a
- Suitability for investor-relations analysis: High - combines a stable, comparable series with visible, month-level honesty about residual imperfection inside that series.

**Recommendation: Policy D (hybrid).** Policy B is rejected outright - an unstable publication set (months appearing/disappearing as coverage crosses a threshold between builds) is close to the worst possible failure mode for an audience that needs to compare periods reliably. Policy C is rejected for the reason the brief specifically warns against: a coverage_pct label does not make a 0-10%-covered decade analytically usable, and presenting a full multi-decade series invites exactly the kind of quick, wrong read this project exists to avoid. Policy A is a reasonable floor but discards useful information about softness *within* the published window. Policy D keeps A's stability guarantee and adds C's transparency where it is actually informative - inside a window already known to be reliable.

## 4. Proposed publication threshold

- Publication threshold: **95.0%** (a month within the published window is included if its stream coverage is at least this)
- Warning threshold: **99.5%** (a visible warning is shown for any published month whose stream coverage falls below this, without excluding it)
- Applied **separately by production stream, at field-month resolution, before stream aggregation**: a field-month is either fully resolved or excluded (quarantined/unresolved categories are never partially counted - see etl/equity_join_historical.py's E5 categories), and stream-level coverage_pct is the aggregate of those binary field-month outcomes for that stream and month. The alternative - a single combined threshold across all four streams - would hide a stream-specific problem (e.g. a field with resolved oil but quarantined gas) behind an averaged number, which section 15.5 and the milestone-2/3 work already established this project should not do.

Fixed start date: **left for your review below (section 6/'Recommended publication start' of the accompanying answer) - see the stability-threshold table in section 2 above. This report does not assert a specific month as approved.**

## 5. MURLACH [pt of MARNOCK-SKUA] source review

### All PPRS production records

[{'period': '202509', 'oil_mbd': 0.286, 'dry_gas_mmscfd': 0.0, 'assoc_gas_mmscfd': 0.221, 'condensate_mbd': 0.0}, {'period': '202510', 'oil_mbd': 8.254, 'dry_gas_mmscfd': 0.0, 'assoc_gas_mmscfd': 6.179, 'condensate_mbd': 0.0}, {'period': '202511', 'oil_mbd': 9.214, 'dry_gas_mmscfd': 0.0, 'assoc_gas_mmscfd': 6.522, 'condensate_mbd': 0.0}, {'period': '202512', 'oil_mbd': 16.354, 'dry_gas_mmscfd': 0.0, 'assoc_gas_mmscfd': 11.84, 'condensate_mbd': 0.0}, {'period': '202601', 'oil_mbd': 10.926, 'dry_gas_mmscfd': 0.0, 'assoc_gas_mmscfd': 7.86, 'condensate_mbd': 0.0}, {'period': '202602', 'oil_mbd': 13.727, 'dry_gas_mmscfd': 0.0, 'assoc_gas_mmscfd': 10.501, 'condensate_mbd': 0.0}, {'period': '202603', 'oil_mbd': 13.601, 'dry_gas_mmscfd': 0.0, 'assoc_gas_mmscfd': 10.679, 'condensate_mbd': 0.0}, {'period': '202604', 'oil_mbd': 11.072, 'dry_gas_mmscfd': 0.0, 'assoc_gas_mmscfd': 8.447, 'condensate_mbd': 0.0}, {'period': '202605', 'oil_mbd': 12.212, 'dry_gas_mmscfd': 0.0, 'assoc_gas_mmscfd': 9.493, 'condensate_mbd': 0.0}, {'period': '202606', 'oil_mbd': 14.696, 'dry_gas_mmscfd': 0.0, 'assoc_gas_mmscfd': 10.992, 'condensate_mbd': 0.0}]

### All Field Partners equity rows for MURLACH

[{'company': 'BP EXPLORATION OPERATING COMPANY LIMITED', 'start': '2050-01-04', 'end': None, 'pct': 80.0, 'status': '700 - PRODUCING', 'operator_flag': 'Y', 'period_label': 'Current'}, {'company': 'NEO ENERGY (ZNS) LIMITED', 'start': '2050-01-04', 'end': None, 'pct': 20.0, 'status': '700 - PRODUCING', 'operator_flag': 'N', 'period_label': 'Current'}]

### All rows containing MURLACH, MARNOCK or SKUA in the field name

- {'field': 'MARNOCK [pt. of MARNOCK-SKUA]', 'company': 'BP EXPLORATION OPERATING COMPANY LIMITED', 'start': '2002-07-01', 'end': '2013-12-23', 'pct': 62.05, 'status': '700 - PRODUCING', 'operator_flag': 'Y'}
- {'field': 'MARNOCK [pt. of MARNOCK-SKUA]', 'company': 'ENI UK LIMITED', 'start': '2002-07-01', 'end': '2013-12-23', 'pct': 10.95, 'status': '700 - PRODUCING', 'operator_flag': 'N'}
- {'field': 'MARNOCK [pt. of MARNOCK-SKUA]', 'company': 'ESSO EXPLORATION AND PRODUCTION UK LIMITED', 'start': '2002-07-01', 'end': '2013-12-23', 'pct': 13.5, 'status': '700 - PRODUCING', 'operator_flag': 'N'}
- {'field': 'MARNOCK [pt. of MARNOCK-SKUA]', 'company': 'SHELL U.K. LIMITED', 'start': '2002-07-01', 'end': '2013-12-23', 'pct': 13.5, 'status': '700 - PRODUCING', 'operator_flag': 'N'}
- {'field': 'MARNOCK [pt. of MARNOCK-SKUA]', 'company': 'BP EXPLORATION OPERATING COMPANY LIMITED', 'start': '2013-12-23', 'end': '2017-03-31', 'pct': 73.0, 'status': '700 - PRODUCING', 'operator_flag': 'Y'}
- {'field': 'MARNOCK [pt. of MARNOCK-SKUA]', 'company': 'ESSO EXPLORATION AND PRODUCTION UK LIMITED', 'start': '2013-12-23', 'end': '2017-03-31', 'pct': 13.5, 'status': '700 - PRODUCING', 'operator_flag': 'N'}
- {'field': 'MARNOCK [pt. of MARNOCK-SKUA]', 'company': 'SHELL U.K. LIMITED', 'start': '2013-12-23', 'end': '2017-03-31', 'pct': 13.5, 'status': '700 - PRODUCING', 'operator_flag': 'N'}
- {'field': 'MARNOCK [pt. of MARNOCK-SKUA]', 'company': 'BP EXPLORATION OPERATING COMPANY LIMITED', 'start': '2017-03-31', 'end': '2017-03-31', 'pct': 86.5, 'status': '700 - PRODUCING', 'operator_flag': 'Y'}
- {'field': 'MARNOCK [pt. of MARNOCK-SKUA]', 'company': 'BP EXPLORATION OPERATING COMPANY LIMITED', 'start': '2017-03-31', 'end': None, 'pct': 100.0, 'status': '700 - PRODUCING', 'operator_flag': 'Y'}
- {'field': 'MARNOCK [pt. of MARNOCK-SKUA]', 'company': 'ESSO EXPLORATION AND PRODUCTION UK LIMITED', 'start': '2017-03-31', 'end': '2017-03-31', 'pct': 13.5, 'status': '700 - PRODUCING', 'operator_flag': 'N'}
- {'field': 'MURLACH [pt of MARNOCK-SKUA]', 'company': 'BP EXPLORATION OPERATING COMPANY LIMITED', 'start': '2050-01-04', 'end': None, 'pct': 80.0, 'status': '700 - PRODUCING', 'operator_flag': 'Y'}
- {'field': 'MURLACH [pt of MARNOCK-SKUA]', 'company': 'NEO ENERGY (ZNS) LIMITED', 'start': '2050-01-04', 'end': None, 'pct': 20.0, 'status': '700 - PRODUCING', 'operator_flag': 'N'}

**Finding**: MURLACH's own equity rows (both partners, BP 80% / NEO ENERGY 20%) share an identical start date, 2050-01-04, with no preceding record of any kind for MURLACH under that name. The related `MARNOCK [pt. of MARNOCK-SKUA]` rows are a **separate field entry** in the source with its own distinct company/interest/date history, not a parent record MURLACH derives from - the source provides no explicit relationship (no shared row, no cross-reference field, no note) linking MURLACH's ownership to MARNOCK's. `SKUA [pt. of MARNOCK-SKUA]` (the third PPRS sub-unit of this group) has no equity rows under any name at all - not even a future-dated one.

**On the 2050 date**: nothing in the source distinguishes a transcription error from a genuinely scheduled future transfer. Both partners share the exact same date, which is more consistent with a real scheduled event (e.g. a licence or unitisation milestone) than with two independent transcription errors landing on the same day - but this is an inference, not evidence, and is reported as such rather than asserted. **No authoritative resolution exists in the data available to this project. MURLACH remains future-only and unresolved**, per the instruction not to assign MARNOCK or SKUA ownership without explicit evidence.

## 6. Pre-2000 older-equity-source inventory

### NSTA/OGA "Field Partners" workbook itself (this project's current source)

- publisher: North Sea Transition Authority
- period_covered: Earliest observed row: 1968-08-01, but per-field coverage is sparse before ~2000 (see section 15.10)
- grain: Field-level, dated intervals with percentage and effective dates
- has_pct_and_dates: True
- format: Excel (.xlsx)
- licence_reuse_terms: NSTA User Agreement (June 2023) - see ATTRIBUTION.md; same basis already used for this project's other NSTA data
- could_improve_pre_2000_coverage: No - this IS the source with the coverage gap. Re-checking it does not add data it does not have.

### NSTA Licences / Licence Blocks / Sub Areas (PEARS-derived)

- publisher: North Sea Transition Authority
- period_covered: Offshore licensing back to the 1960s-70s (exact per-licence start dates vary)
- grain: Licence-level (who holds which licence/block), not field-level production-equity percentage
- has_pct_and_dates: False
- format: GIS layers / data.gov.uk downloads
- licence_reuse_terms: Government/NSTA open data terms (not independently re-verified in this checkpoint)
- could_improve_pre_2000_coverage: No, for this project's purpose. This is the same 'licence blocks history' dataset already identified in spec section 15.1 as a company-name-history source, not an equity-interest source: it records licensee-of-record, not what share of a field's reported production a company is entitled to. Confirmed by web search (see queries below), not merely assumed from the spec.

### "Field Data" GOV.UK page (withdrawn)

- publisher: gov.uk / DECC-predecessor department
- period_covered: Referenced 'offshore field consents since 1976' in search result summary; page itself is withdrawn/archived
- grain: Unclear at time of search - page is withdrawn and was not fetched in full (out of scope: this checkpoint catalogues sources, it does not ingest them)
- has_pct_and_dates: Unknown - not verifiable without fetching the withdrawn page's archived content, which was not done here
- format: Unknown
- licence_reuse_terms: Unknown
- could_improve_pre_2000_coverage: Possibly, but unverified - this is the one lead from the search that is not clearly ruled out. If pursued, it should be checked for field-level percentage-and-date structure before being treated as usable, per the same standard applied to the current source in milestone 1.

A bounded web search (two queries, listed below) did not surface a distinct, citable, field-level dated-equity dataset from NSTA/OGA or another regulator covering the pre-2000 UKCS period at the percentage-and-effective-date grain this project needs. What exists publicly and was found is mostly licence-level (who holds which licence, not what percentage of a field's production they are entitled to) or the current 'Field Partners' workbook itself - the source with the known gap. One unverified lead (a withdrawn GOV.UK 'field data' page referencing 'offshore field consents since 1976') was found and is listed but not pursued further, since fetching and assessing it is ingestion-adjacent work this checkpoint is scoped not to do. Per the explicit instruction for this checkpoint, no narrative or company-history material is treated as a usable source here, however specific it sounds, and general web search was not used to reconstruct actual historical equity figures - only to catalogue what citable datasets exist.

Search queries used (2026-09-09):
- `NSTA OGA "field equity" OR "field partners" historical archive UKCS pre-2000 percentage ownership dataset`
- `NSTA "licensee" OR "licence" history offshore petroleum blocks dataset dated interest percentage 1970s 1980s 1990s`

## 7. Draft methodology wording

Provided for review; `methodology.html` is not created by this checkpoint.

```markdown
## Equity-attributable production - methodology (DRAFT, not yet published)

**Source.** Equity-attributable production is calculated from the NSTA dataset whose ArcGIS item
is titled "Field Partners". The NSTA Fields data theme page describes this same dataset as
"Current and historical field equity shares". Both names are recorded as provenance; the item
title is a publisher naming choice, not a description of the data's temporal scope, and the
workbook's actual content - dated ownership intervals back to the late 1960s - has been verified
directly rather than assumed from either name.

**Interval resolution.** Ownership is resolved once per calendar month, at the first day of the
month ("month-start"), using half-open intervals: an interest is active for a given month if
`start_date <= month_start < end_date`. An open (blank) end date means the interest is still
current. This is a deliberate simplification - ownership changing mid-month is attributed entirely
to whichever interest was in force on day 1 of that month, never prorated.

**Zero-duration rows.** A small but non-trivial share of source rows record an identical start and
end date. These are retained as source records but are never treated as an active ownership
interval for any month - mathematically, a zero-duration interval cannot satisfy the half-open
test above for any month-start.

**Zero-interest rows.** Some source rows record a company's involvement in a field with a recorded
interest of 0%. These are retained as source records but contribute no equity-attributable
production, since production multiplied by a 0% share is 0 regardless of the row's other
attributes.

**Operator status.** The source separately records which company operates a field. Operator status
does not imply a positive economic interest - in fact a substantial share of 0%-interest rows
belong to the recorded operator. Operator status is never used as a proxy for ownership.

**Unresolved field-months.** Where a field's ownership records for a given month cannot be
resolved cleanly - most commonly because two records genuinely overlap and together claim more
than 100% of the field - that field-month is excluded from the calculation entirely, not repaired,
normalised back to 100%, or resolved by preferring one recorded owner over another. This is
reported, not silently absorbed into the total.

**Coverage.** Coverage is measured and shown separately for each production stream (oil, dry gas,
associated gas, condensate) as the share of that stream's total reported field production for
which ownership was cleanly resolved that month. Streams are never combined into a single boe/d
figure for this purpose.

**Publication window.** Equity ownership records are not evenly available across the production
history this site otherwise covers back to 1975. Coverage in earlier years is materially
incomplete - the underlying NSTA equity dataset was not populated retroactively to most fields'
actual production start dates. Equity-attributable production is therefore published only from
[PUBLICATION START DATE - pending review, see etl/equity_publication_window_report.md], the
earliest month for which coverage has been verified to be consistently high, not merely high in
one good year. Coverage for every published month is shown alongside the figure it belongs to.

**What this figure is not.** Equity-attributable production is a gross equity share of reported
field production - the field's reported volume multiplied by each company's recorded ownership
percentage for that month. It is not net production, not working-interest production, and not
entitlement production: it carries no adjustment for royalty, tax, or any other entitlement
mechanism. It should not be read as a substitute for those figures.

```

## Confirmations

- No build.py integration, no docs/data/equity artifacts, no UI changes, no company aliases or parent-group mappings, no equity history published. This report and its supporting module are the only outputs, both under etl/.
