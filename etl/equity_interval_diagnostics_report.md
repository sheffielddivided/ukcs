# Equity interval-semantics diagnostic report

Diagnostic only. No PPRS join, no equity-attributable production, no company production, no docs/data/equity artifacts. See etl/equity_interval_diagnostics.py.

## 1. Zero-duration intervals (start_date == end_date)

- Total: 838 rows across 253 fields and 180 companies.
- Classification: {'boundary_duplicate': 689, 'termination_marker': 42, 'boundary_transition': 91, 'standalone_snapshot': 16}
- Interest % bucket: {'partial': 746, 'hundred': 61, 'zero': 31}
- Operator Flag distribution: {'N': 561, 'Y': 277}
- Status distribution: {'900 - PRODUCTION CEASED': 347, '700 - PRODUCING': 419, '800 - PRODUCTION SUSPENDED': 1, '899 - PRODUCTION CEASED - VENT CONSENT NEEDED': 52, '799 - PRODUCTION SUSPENDED - POSSIBLE RESERVES REMAIN': 15, '600 - CONSTRUCTION-FDP APPROV': 4}
- On Offshore distribution: {'Offshore': 803, 'Onshore': 35}
- Top 15 exact dates by frequency: [('2003-05-01', 58), ('2012-12-21', 39), ('2011-02-02', 35), ('2009-01-09', 32), ('2009-08-31', 24), ('2010-12-01', 22), ('2009-02-28', 20), ('2003-11-11', 20), ('2009-12-01', 18), ('2003-11-17', 18), ('2016-05-17', 17), ('2026-07-01', 17), ('2007-12-31', 16), ('2007-06-28', 15), ('2018-11-30', 14)]

## 2. Interval policy comparison (A / B / C)

### Policy A (literal half-open, no special-casing)

- Field-months evaluated: 141254
- Zero active interests: 291
- Sum within 100% +-0.5pp: 140962
- Sum over 100.5%: 1
- Sum under 99.5%: 0
- Field-months with a same-company overlap: 1
- Zero-duration rows ever counted active: 0
- Fields excluded (only future-dated rows, entirely outside the grid): ['ALVHEIM', 'MURLACH [pt of MARNOCK-SKUA]', 'STATFJORD(CROSS BORDER)']
- Worst failures: [('ROCHELLE', '2011-08-01', 200.0, 5)]

### Policy B (zero-duration rows explicitly filtered)

- Field-months evaluated: 141254
- Zero active interests: 291
- Sum within 100% +-0.5pp: 140962
- Sum over 100.5%: 1
- Sum under 99.5%: 0
- Field-months with a same-company overlap: 1
- Zero-duration rows ever counted active: 0
- Fields excluded (only future-dated rows, entirely outside the grid): ['ALVHEIM', 'MURLACH [pt of MARNOCK-SKUA]', 'STATFJORD(CROSS BORDER)']
- Worst failures: [('ROCHELLE', '2011-08-01', 200.0, 5)]

### Policy C (Equity Share Time Period preferred on conflict)

- Field-months evaluated: 141254
- Zero active interests: 291
- Sum within 100% +-0.5pp: 140962
- Sum over 100.5%: 1
- Sum under 99.5%: 0
- Field-months with a same-company overlap: 1
- Zero-duration rows ever counted active: 0
- Fields excluded (only future-dated rows, entirely outside the grid): ['ALVHEIM', 'MURLACH [pt of MARNOCK-SKUA]', 'STATFJORD(CROSS BORDER)']
- Worst failures: [('ROCHELLE', '2011-08-01', 200.0, 5)]

**Policies A and B are numerically identical on this dataset.** A zero-duration interval `[d, d)` is empty under the half-open convention regardless of whether it is explicitly filtered first - no month can ever satisfy `start <= month < end` when `start == end`. The distinction is documentation/intent, not outcome.

**Policy C is also numerically identical to A on this dataset**, because the Equity Share Time Period label never actually disagrees with the parsed dates - see section 3.

The one genuine anomaly found (ROCHELLE, 2011-08, summing to 200% across 5 companies) is **not** a zero-duration artifact: it is a real overlapping-interval data error - two companies' rows both cover 2011-08 (one interval ends 2011-08-31, the next for the same companies starts 2011-08-01, a genuine one-month overlap, not an adjacency).

## 3. Equity Share Time Period

- 1187 rows exactly match `Current`; 6496 exactly match `Previous-YYYY to YYYY`; 0 match neither format.
- Rows where the label's year range disagrees with the parsed Start/End Date years: 0 (of 7683).

**Finding: the column is fully derived from Start Date and End Date at year granularity, with zero exceptions.** `Current` means `end_date is None`; `Previous-Y1 to Y2` means `start_date.year == Y1 and end_date.year == Y2`, always. It carries no information not already in the two date columns, cannot explain the zero-duration rows (a `Previous-Y to Y` label there is a trivial consequence of start_date == end_date, not independent corroboration), and never conflicts with the dates - there is nothing for Policy C to override on the live workbook. It should be **retained as source metadata only**, never used in interval resolution: it is strictly less precise (year, not day) than the date columns it is derived from, and parsing it would only reintroduce a risk (a future row that violates the pattern) for zero benefit.

## 4. Zero-interest rows and Operator Flag

- Zero-interest rows: 241 (62 open-ended, 179 closed).
- Of those, 218 also have Operator Flag = 'Y' (52 open-ended, 166 closed).
- 188 of those 218 rows overlap a DIFFERENT company's positive-interest row for the same field during the same period (30 do not).
- 144 of those rows belong to a company that ALSO holds a positive-interest row for the same field, in a different period.
- Status distribution: {'700 - PRODUCING': 104, '900 - PRODUCTION CEASED': 50, '899 - PRODUCTION CEASED - VENT CONSENT NEEDED': 52, '799 - PRODUCTION SUSPENDED - POSSIBLE RESERVES REMAIN': 11, '600 - CONSTRUCTION-FDP APPROV': 1}
- Top fields: [('BRITANNIA', 9), ('ELGIN', 8), ('DUART', 7), ('FRANKLIN', 7), ('DOUGLAS', 6), ('DOUGLAS WEST', 6), ('HAMILTON', 6), ('HAMILTON NORTH', 6), ('LENNOX', 6), ('BEINN', 5)]
- Top organisations: [('FUJAIRAH OIL AND GAS UK LLC', 36), ('NEO NEXT + ENERGY RESOURCES UK LIMITED', 28), ('WOODSIDE ENERGY (GREAT BRITAIN) LIMITED', 17), ('NEO NEXT+ ENERGY E&P UK LIMITED', 16), ('AMOCO (U.K.) EXPLORATION COMPANY, LLC', 15), ('CHRYSAOR PRODUCTION (U.K.) LIMITED', 14), ('ENI UK LIMITED', 12), ('CHRYSAOR (U.K.) BRITANNIA LIMITED', 9), ('NEO NEXT+ ENERGY ELF UK LIMITED', 7), ('ENTERPRISE OIL LIMITED', 6)]

**Finding: Operator Flag represents operatorship independently of economic interest.** The large majority (86%) of zero-interest, Operator Flag='Y' rows coincide with another company holding the real equity for the same period - i.e. a company can be recorded as the field's operator with a 0% ownership stake while a different company (or companies) hold the interest. This is consistent with real industry arrangements (e.g. a technical operator without an economic stake) and confirms the instruction not to infer a positive interest from Operator Flag = 'Y'. Per the milestone-1 default: zero-interest rows are retained as source records but excluded from any equity-weighted sum, since multiplying production by 0% contributes no volume regardless of Operator Flag.

## 5. Future-dated rows

### ALVHEIM / AKER BP ASA

- interest_pct=100.0, start_date=2030-05-01, end_date=None, status='700 - PRODUCING', operator_flag='Y', period_label='Current'
- Other rows for this field: (none - this is the only row this field has)
- Overlaps a currently-open interval: False

### MURLACH [pt of MARNOCK-SKUA] / BP EXPLORATION OPERATING COMPANY LIMITED

- interest_pct=80.0, start_date=2050-01-04, end_date=None, status='700 - PRODUCING', operator_flag='Y', period_label='Current'
- Other rows for this field: [{'company_name': 'NEO ENERGY (ZNS) LIMITED', 'start_date': '2050-01-04', 'end_date': None, 'interest_pct': 20.0}]
- Overlaps a currently-open interval: False

### MURLACH [pt of MARNOCK-SKUA] / NEO ENERGY (ZNS) LIMITED

- interest_pct=20.0, start_date=2050-01-04, end_date=None, status='700 - PRODUCING', operator_flag='N', period_label='Current'
- Other rows for this field: [{'company_name': 'BP EXPLORATION OPERATING COMPANY LIMITED', 'start_date': '2050-01-04', 'end_date': None, 'interest_pct': 80.0}]
- Overlaps a currently-open interval: False

### STATFJORD(CROSS BORDER) / EQUINOR UK LIMITED

- interest_pct=100.0, start_date=2030-05-01, end_date=None, status='700 - PRODUCING', operator_flag='Y', period_label='Current'
- Other rows for this field: (none - this is the only row this field has)
- Overlaps a currently-open interval: False

**Finding: all 4 future-dated rows are each the ONLY equity row for their field** (ALVHEIM, STATFJORD(CROSS BORDER)) or share the field with only the other future-dated row (MURLACH's two rows, which sum to 100% between them but both start 2050-01-04). None overlaps a currently-open interval, because none of these fields has any other row at all. **As of the diagnostic's anchor month (2026-09), these 3 fields have zero active equity coverage under any policy** - not because of a data error, but because their only recorded interval(s) genuinely start in the future.

**Recommendation: retain, but inactive until the start date, under the policy already in use** (Policy A's literal half-open test already does this correctly with no special-casing - a row with a future start_date simply never satisfies `start_date <= month_start` for any month up to and including now). Quarantining would require inventing a rule these rows don't actually need: the existing containment test already produces the correct behaviour (no current coverage) without singling them out. The only action needed is a validation rule that does not treat 'no current equity row' as build-breaking for a field whose only row(s) are future-dated (see the revised E5 proposal below) - treating it as an unresolved gap would be wrong, since the gap is real and explained, not a parse or matching error.

## 6. Open-ended interval diagnostics

- Open-ended rows: 1187 across 531 fields.
- Fields with more than one open-ended POSITIVE-interest row (multiple current partners - expected/normal): 342.
- Fields where the SAME company holds more than one open-ended row (a genuine overlap anomaly, distinct from multiple different partners): 0 ([]).
- Fields whose currently-open interests sum to 100% +-0.5pp: 528.
- Fields whose currently-open interests do NOT sum to 100% +-0.5pp: 0 (examples: []).
- Fields with no current open row at all: 3 (the 3 future-dated-only fields from section 5).
- Future-dated rows that overlap a currently-open interval: [] (none found).

## 7. Proposed corrected validation rules

See the accompanying investigation summary for full rationale. Corrected proposals:

- **E1** (interest sums to 100% for a field-month with production > 0): unchanged in intent, but must explicitly exclude zero-duration rows from the summed set (they already are, under a literal half-open test) and must not fail solely because a field's only equity row(s) are future-dated - that is E6/E5's concern (coverage), not E1's (sum correctness of whatever *is* active).
- **E4** (no overlapping intervals for the same field/company): keep, but scope it to same-(field, company) overlaps only, as the ROCHELLE case demonstrates a real violation exists (CNOOC and HARBOUR ENERGY WPUK rows for ROCHELLE overlap by one month in 2011) - this is exactly the case E4 should be catching, not an edge case to special-case away.
- **E5** (no coverage gaps): must not fire on a field whose only equity row(s) have a future start_date (ALVHEIM, MURLACH, STATFJORD(CROSS BORDER)) - that gap is real and explained, not a data problem. Should distinguish 'gap because a field genuinely has no equity row covering this month yet' from 'gap because of a parse/matching failure'.
- **E7** (start_date < end_date, strict): **cannot remain build-breaking as worded** - 838 rows violate it. Replace with a rule that accepts start_date <= end_date, and treats start_date == end_date rows as **non-interest-bearing event records** (per section 1's classification) rather than errors: they never contribute to E1's sum (they cannot, under half-open containment) and should not fail the build. A stricter start_date < end_date check should apply only to rows that are NOT zero-duration.

## 8. Not yet resolved

- The 91 'boundary_transition' zero-duration rows (pct differs from the adjacent substantive row at the same instant) are not fully explained - they may represent a genuine instantaneous same-day step-change, or a data-entry artifact. Not required to resolve for the field-matching or latest-period-coverage work already approved; flagged for whoever writes the real interval join.
- The 16 'standalone_snapshot' rows cluster by date and company across unrelated fields (e.g. CNR INTERNATIONAL at THELMA/TIFFANY/TONI, all dated 2003-05-01), suggesting a shared external event rather than field-specific activity, but the specific event is not identified from this data alone.
