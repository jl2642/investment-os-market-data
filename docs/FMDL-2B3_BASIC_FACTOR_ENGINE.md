# FMDL-2B-3 — Basic Factor Engine

## 1. Objective

FMDL-2B-3 converts the accepted FMDL-2B-2 immutable A-share history release into a full-market basic-factor candidate. It calculates only the 26 market-behaviour factors frozen in `config/fmdl2_factor_registry.json`.

The output is research-priority evidence only. It does not prove factor alpha, promote a stock into the live candidate pool, change the simulation or real portfolio, or create trade authority.

## 2. Authorized inputs

- active FMDL-1 Investment OS interface;
- published FMDL-1 Current release with zero hard failures;
- accepted `FMDL2B2_29556547410_1` immutable history base;
- one status row for every accepted A-share Universe symbol;
- current market-event flags;
- FMDL-2A factor registry v1.0.0.

The production run is blocked when interface status, release identity, as-of date, shard hash, Universe identity or factor-registry identity fails.

## 3. Factor scope

The engine implements exactly 26 factors:

- momentum and trend: 20/60/120/250-session returns, 250-to-20 momentum, distance to 52-week high, trend consistency and positive 20-session block ratio;
- risk: 20/60-session volatility, downside volatility, 120/250-session drawdown, worst day and board-aware extreme-move count;
- liquidity: 20/60-session average turnover, median turnover, turnover stability, turnover CV and 20/60 volume ratio;
- trading stability and data risk: active-trade ratio, inferred suspension days and zero-turnover days.

Financial statements, valuation, market capitalization, dividend, analyst consensus and sector-specific financial factors remain prohibited until FMDL-3.

## 4. Formula and calendar conventions

1. Return and risk factors use QFQ adjusted close.
2. Liquidity factors use source-reported turnover amount and volume. A Tencent fallback series may calculate price and amount factors but cannot fabricate volume factors.
3. All history is sliced at or before `as_of_date` before rolling operations.
4. Rolling price factors use valid observations; missing observations are not converted to zero returns.
5. The market-session calendar is derived from the union of accepted full-market history dates and must end on the accepted as-of date.
6. `suspension_days_20/60` equals expected market sessions after listing minus accepted symbol observations in the relevant window. This is an evidence-based inferred suspension/no-valid-trade count, not an exchange status claim.
7. `active_trade_ratio_60d` uses expected market sessions as denominator and positive-close/positive-turnover observations as numerator.
8. `positive_month_ratio_12m` uses up to 12 non-overlapping 20-session return blocks, anchored at the as-of observation.
9. Extreme-move review thresholds are 5% for ST, 10% for SH/SZ Main, 20% for STAR/ChiNext and 30% for BSE.
10. Downside volatility remains missing when fewer than two negative returns exist in the 60-session window.

## 5. Missingness and quality states

Every Universe symbol receives one wide status/factor row. Every symbol-factor pair receives one long-detail row.

- `VALID`: current, single-provider QFQ history, coverage at least 95%, no missing factor and no current review flag;
- `PARTIAL`: usable history with a missing factor, restricted fallback capability, suspension/event review, stale latest observation or lower coverage;
- `SUSPECT`: mixed provider/adjustment evidence or more than five unexplained stale market sessions;
- `BLOCKED`: no accepted factor-ready history, including the four FMDL-2B-2 quarantined symbols.

Missing factors remain null and carry an explicit `missing_reason_code`. They never receive a neutral percentile or z-score.

## 6. Cross-sectional outputs

For every available factor on the same as-of date:

- broad-market percentile;
- board-neutral percentile;
- 1%/99% winsorized raw z-score.

Percentiles are direction-aware: higher values rank better for `HIGHER_BETTER`, lower values rank better for `LOWER_BETTER`, and diagnostic factors retain raw ascending percentile semantics. Z-scores remain raw diagnostic values and do not create an investment score.

## 7. Candidate outputs

`outputs/factors/candidate/` contains:

- `BASIC_FACTOR_TABLE.parquet` — one row per Universe symbol, raw factors and cross-sectional fields;
- `BASIC_FACTOR_DETAIL.parquet` — one row per symbol-factor with availability and reason codes;
- `BASIC_FACTOR_STATUS.csv` — per-symbol history readiness, quality and confidence;
- `BASIC_FACTOR_QUALITY.json` — hard gates, controlled warnings and factor coverage;
- `BASIC_FACTOR_MANIFEST.json` — release identity, hashes, row counts and aggregate hash;
- `FMDL2B3_RUN_REPORT.json` — production result and non-claims.

## 8. Acceptance gates

A candidate may proceed to FMDL-2B-3 acceptance only when:

- exactly 5,529 wide/status rows cover the accepted Universe once;
- exactly `5,529 × 26 = 143,754` symbol-factor rows exist;
- blocked symbols equal the accepted historical quarantine set;
- blocked or missing factors have no value, percentile or z-score;
- all shard and output hashes reproduce;
- factor date equals the accepted history/current as-of date;
- formula and future-data regression tests pass;
- all percentiles remain in `(0, 1]`;
- no BUY/ADD/SELL, target-weight or trade-permission field exists;
- GitHub Actions runtime remains compatible with the free-tier operating design.

FMDL-2B-3 does not become complete merely because code is committed. Completion requires a successful full-market run, independent candidate validation and a formal acceptance record.
