# FMDL-3C-D — Financial Score & Investment OS Interface

## Purpose

FMDL-3C-D converts the accepted FMDL-3C-C hardened factor layer into a transparent financial-research score and a machine-readable Investment OS interface. It does not create a stock recommendation, portfolio action or trade permission.

## Entry gate

`FMDL3CC_FINANCIAL_FACTOR_VALIDATION_AND_HARDENING_ACCEPTED`

## Score architecture

The score uses 18 accepted Production Core factors grouped into four non-overlapping families:

1. Profitability & Returns — 30%
2. Growth & Momentum — 25%
3. Cash & Earnings Quality — 25%
4. Balance Sheet & Efficiency — 20%

Within each family, factor weights are explicit in `config/fmdl3cd_factor_weights.csv`. Hardened directional percentiles are used so a larger percentile consistently means better financial evidence. Raw factor values remain unchanged in FMDL-3C-C.

## Missing data and warning treatment

Missing data is not zero-filled and is not automatically treated as poor quality.

- A family score is produced only after its minimum factor-count and factor-weight coverage gates pass.
- An overall score requires at least three available families, at least 70% available family weight and at least 70% global factor-weight coverage.
- Available family and factor weights are re-normalized only after those gates pass.
- Conditional factor rows may contribute to the score but reduce confidence.
- A score with low confidence is not ranking eligible.
- Financial-sector and unresolved profiles remain controlled exclusions rather than zero scores.

## Confidence

The score and confidence are separate:

- `HIGH`: all four families, at least 90% factor-weight coverage and no more than 10% conditional weight.
- `MEDIUM`: at least three families, at least 75% factor-weight coverage and no more than 30% conditional weight.
- `LOW`: the minimum score gate passes but the higher confidence conditions do not.
- `UNAVAILABLE`: no score is produced.

The numeric confidence field summarizes factor coverage, family coverage and warning weight. It does not alter the financial score.

## Role separation

### Candidate pool

The score may raise or lower research priority, but candidate-pool membership remains a broader discovery and observation decision. Automatic promotion or deletion is prohibited.

### Simulation lab

The simulation portfolio remains a strategy experiment and error-exposure environment. Lower-score or lower-confidence companies may remain for controlled contrarian, cyclical, turnaround or failure-mode tests. Simulation is not a simple queue for the real account.

### Real account

A score of at least 85, `HIGH` confidence and all four families can satisfy only the strict financial-evidence review floor. It does not satisfy the complete real-account gate.

The downstream chain remains:

`FINANCIAL_RESEARCH_EVIDENCE -> PUBLIC_EQUITY_RESEARCH -> OWNER_QUALITY -> INVESTMENT_ATTRACTIVENESS -> ETF_ALTERNATIVE -> CANDIDATE_RACE -> SIMULATION_OR_SHADOW_TRACK -> PORTFOLIO_FIT -> CAPITAL_MIGRATION -> PRE_TRADE_MEMO -> USER_CONFIRMATION`

## Outputs

- `FMDL3CD_FINANCIAL_SCORE_CURRENT.parquet`
- `FMDL3CD_FAMILY_SCORES.parquet`
- `FMDL3CD_FACTOR_CONTRIBUTIONS.parquet`
- `FMDL3CD_INVESTMENT_OS_EVIDENCE.parquet`
- `FMDL3CD_INVESTMENT_OS_INTERFACE.json`
- `FMDL3CD_SCORE_DISTRIBUTION.csv`
- `FMDL3CD_SCORE_WEIGHTS.csv`
- Decision, validation, manifest, immutable Release, Current, Archive and Last-success pointer

## Controlled limitations

- The score currently applies only to the coarse `GENERAL_NON_FINANCIAL` profile.
- It is cross-sectional across the broad non-financial universe and is not industry neutral.
- Bank, insurance and brokerage score packs are not yet available.
- Two three-year CAGR factors remain deferred pending historical backfill.
- Nine diagnostic factors remain visible for research but do not enter the score.
- Valuation, owner quality, competitive position, catalysts, governance, portfolio fit and ETF alternatives are outside this score.

## Authority

`DATA_AND_RESEARCH_EVIDENCE_ONLY`

`trade_authority = NONE`

## Exit gate

`FMDL3CD_FINANCIAL_SCORE_AND_INVESTMENT_OS_INTERFACE_ACCEPTED`

## Next gate

`FMDL-3D — Valuation, Capitalization & Dividend`
