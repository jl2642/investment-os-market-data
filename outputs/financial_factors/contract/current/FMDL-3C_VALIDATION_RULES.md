# FMDL-3C Validation Rules

## 1. Zero-tolerance failures

The following conditions fail a candidate:

1. FMDL-3B-4 entry status is not accepted.
2. A factor is visible before any required input.
3. A later restatement is inserted into an earlier as-of timestamp.
4. A blocked or quarantined input produces a valid factor.
5. A missing value is converted to zero, a peer median or a neutral score.
6. A factor lacks input fact/source lineage.
7. A sector-sensitive factor is calculated with an unresolved profile.
8. A financial institution receives an ordinary industrial factor not explicitly permitted by contract.
9. An invalid denominator produces a numeric valid factor.
10. Growth is calculated across different fiscal-period types or non-consecutive years.
11. Loss/profit sign transitions are represented as ordinary percentage growth.
12. A deferred factor is published as an MVP factor.
13. A composite score, investment recommendation or trade authority is created.

## 2. PIT and revision tests

For each factor row:

- `factor_available_from = max(input_available_from)`;
- all inputs must be effective at the factor as-of timestamp;
- superseded inputs are used only inside their valid historical intervals;
- factor revisions are unique and preserve prior versions;
- pre-restatement replay blocks inherited from FMDL-3B-3 remain blocks.

## 3. Comparability tests

TTM, YoY, CAGR, margin changes and average-balance returns require accepted comparison bridges. A `NOT_COMPARABLE` transition blocks the factor. A permitted warning produces `VALID_WITH_WARNING` only when the contract explicitly allows it; the warning remains visible and cannot be silently ranked as fully valid.

## 4. Denominator tests

- Revenue margins require positive revenue.
- ROE requires positive average parent equity.
- ROA and accrual ratios require positive average assets.
- CAGR requires positive start and end values.
- Profit and CFO percentage growth require valid same-sign bases.
- Current ratio requires positive current liabilities.
- Debt coverage requires positive debt.
- Zero debt is a structured non-applicable state, not infinity.

## 5. Sector tests

The engine must resolve one of the frozen profiles before calculating sector-sensitive factors. Shared factors such as ROE, ROA and parent-profit growth still require all ordinary denominator, PIT and comparability gates.

## 6. Distribution and economic sanity tests

FMDL-3C-C will inspect, by factor and sector profile:

- valid/missing/invalid shares;
- extreme tails and sign distributions;
- temporal discontinuities;
- duplicate factor intervals;
- coverage changes by board and reporting period;
- suspicious clustering at zero or provider sentinel values;
- consistency between related factors, such as margin and cash-conversion families.

Distribution tests flag evidence; they never overwrite canonical raw factor values.

## 7. Publication gates

A Current release requires:

- schema-valid contract and factor rows;
- unique factor IDs and row keys;
- complete manifest hashes;
- accepted Statement Current lineage;
- zero future information;
- zero silent restatement overwrite;
- zero source-less factor rows;
- zero unresolved sector routing for rows marked valid;
- zero trade authority.
