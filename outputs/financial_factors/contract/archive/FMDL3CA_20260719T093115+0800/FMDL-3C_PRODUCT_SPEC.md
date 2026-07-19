# FMDL-3C — Financial Quality, Growth & Balance-Sheet Factors

## 1. Product purpose

FMDL-3C converts the accepted FMDL-3B point-in-time statement store into auditable financial factors. It answers whether reported profitability, growth, cash conversion and balance-sheet condition are economically meaningful at a given historical information timestamp.

FMDL-3C does **not** decide whether a security should be bought, promoted to a candidate pool or assigned portfolio capital. It produces research evidence only and preserves `trade_authority = NONE`.

## 2. Architecture boundary

### FMDL-3C owns

- factor definitions and immutable versions;
- PIT construction of TTM flows and average balances;
- restatement-aware factor revisions;
- comparability and denominator validity;
- sector applicability;
- factor quality and ranking-eligibility states;
- source and input lineage;
- Financial Factor Current publication.

### FMDL-3C does not own

- factor weights or composite scores;
- alpha claims or backtest conclusions;
- company research recommendations;
- candidate-pool promotion;
- valuation, WACC or shareholder-return event calculations;
- position sizing, migration or execution.

## 3. Accepted input

The sole canonical accounting input is the accepted FMDL-3B-4 Statement Current. Every factor must inherit:

- source IDs and normalized fact IDs;
- `available_from`, revision and supersession intervals;
- FMDL-3B-3 restatement and comparability controls;
- decision-grade eligibility and quarantine state;
- `trade_authority = NONE`.

A factor cannot repair, replace or neutral-fill a missing or blocked statement fact.

## 4. Factor data model

Grain:

`symbol × factor_id × as_of_timestamp × fiscal_period_end × factor_version`

Required output fields for FMDL-3C-B include:

- factor identity and version;
- value and unit;
- fiscal period and as-of timestamp;
- sector profile and applicability state;
- quality state and ranking eligibility;
- formula version;
- input fact IDs, source IDs and comparability IDs;
- derived availability timestamp;
- restatement lineage;
- warning and invalidity reason;
- authority fields.

## 5. Temporal construction

### 5.1 TTM flows

For an FY observation, use the accepted annual cumulative value. For an interim observation:

`TTM = current YTD + prior FY - prior-year matching YTD`

All components must be decision-grade, comparable and available as of the requested timestamp. Factor availability is the latest availability timestamp among every component.

### 5.2 Average balances

Average balance uses the current period-end value and the same fiscal-period-type balance one year earlier. Missing or incomparable endpoints block the factor.

### 5.3 Growth

Growth compares the same canonical field and fiscal-period type across consecutive years. Revenue growth requires a positive prior base. Profit and CFO growth require valid sign treatment; loss-to-profit and profit-to-loss transitions are not encoded as ordinary percentage growth.

### 5.4 Restatements

A later restatement produces a later factor version. When the current provider does not retain the pre-restatement structured value, historical factor replay before the correction is blocked rather than backfilled with the later value.

## 6. Sector routing

The initial general-company factor set applies to `GENERAL_NON_FINANCIAL`. Banks, insurers and securities companies may use only factors explicitly marked for those profiles. Ordinary industrial gross margin, current ratio, CFO conversion and debt/equity semantics cannot be silently applied to financial institutions.

An unresolved sector profile produces `SECTOR_PROFILE_UNRESOLVED`; it does not fall back to the general-company model.

## 7. Initial factor set

The contract freezes 29 factors:

- 5 profitability factors;
- 4 earnings-quality factors;
- 7 growth and margin-change factors;
- 6 balance-sheet factors;
- 2 efficiency factors;
- 5 diagnostics.

The factor dictionary distinguishes ranking-eligible factors from diagnostics. It deliberately defers ROIC, net-debt/EBITDA, interest coverage, ROIC-WACC spread and dividend stability because the accepted inputs or downstream contracts do not yet support them without semantic shortcuts.

## 8. Missingness and denominator policy

- Missing inputs remain missing.
- Debt components, cash and goodwill are never assumed to be zero.
- Negative or zero equity/assets invalidate return denominators.
- Zero debt does not create infinity.
- CAGR requires positive start and end values.
- Canonical factor values are not winsorized.
- Ranking transformations, when introduced later, must preserve raw values and transformation metadata.

## 9. Quality states

The factor engine must emit explicit states including `VALID`, `VALID_WITH_WARNING`, sector inapplicability, missing input, invalid denominator, sign transition, non-comparable input, replay block, stale/conflicted input and quarantine.

Only `VALID` is unconditionally rank eligible. Scoring and weighting remain outside FMDL-3C-A and FMDL-3C-B.

## 10. Phase sequence

- **FMDL-3C-A** — architecture, factor dictionary and executable contract;
- **FMDL-3C-B** — full-market factor engine MVP and historical factor store;
- **FMDL-3C-C** — validation, sector routing and hardening;
- **FMDL-3C-D** — score/interface design and Investment OS handoff.

## 11. FMDL-3C-A acceptance

The architecture is accepted only when the machine contract and CSV dictionary agree, every MVP input is available or derivable from accepted Statement Current fields, all denominator/comparability/sector rules fail closed, deferred factors are excluded from the MVP, no composite score is defined and all validation runs pass.
