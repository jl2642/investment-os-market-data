# FMDL-3A — Source Benchmark, Point-in-Time Contract & Coverage Map

## 1. Purpose

FMDL-3A converts the accepted FMDL-3 architecture into measured source decisions.

This phase must not claim that a source is usable because an API name exists. Every proposed route is executed on GitHub-hosted infrastructure against a deterministic cross-sector and cross-board A-share sample. The output freezes:

- primary and fallback routes;
- measured success and coverage thresholds;
- announcement-date and revision semantics;
- runtime and field completeness;
- sector and board gaps;
- conditions that block FMDL-3B.

## 2. Scope

### In scope

- official filing and announcement metadata;
- structured balance-sheet, income-statement and cash-flow candidates;
- financial-indicator cross-check candidates;
- current and historical valuation candidates;
- share-capital, dividend and buyback candidates;
- daily-resolution point-in-time availability;
- revision and correction identification;
- numeric acceptance gates and coverage maps.

### Out of scope

- full-market financial statement backfill;
- final line-item normalization;
- factor construction;
- investment conclusions or candidate promotion;
- simulation or real-portfolio changes;
- trade authority.

## 3. Deterministic stress sample

The benchmark sample is frozen in `config/fmdl3a_benchmark.json`.

It covers:

- Shanghai Main Board;
- Shenzhen Main Board;
- ChiNext;
- STAR Market;
- Beijing Stock Exchange;
- general non-financial companies;
- banks;
- insurance;
- securities firms;
- pre-profit or negative-earnings issuers.

The sample includes both mature large issuers and structurally difficult cases. It is not a statistical backtest and must not be presented as full-market coverage. It is a source capability and failure-mode test.

## 4. Candidate source hierarchy

### 4.1 Filing availability and revisions

Primary candidate:

- `CNINFO_OFFICIAL_DISCLOSURE`
- AKShare adapter: `stock_zh_a_disclosure_report_cninfo`
- intended role: official announcement date, filing link and revision sequence.

Fallback candidate:

- `EASTMONEY_NOTICE_FALLBACK`
- AKShare adapter: `stock_individual_notice_report`
- intended role: degraded metadata continuity only.

The fallback may not silently upgrade itself to official evidence.

### 4.2 Structured financial statements

Primary candidate:

- `EASTMONEY_STATEMENTS`
- three report-period adapters for balance sheet, income statement and cash flow.

Fallback candidate:

- `SINA_STATEMENTS`
- `stock_financial_report_sina`.

A statement source is considered bundle-successful only when all three statements return usable report-period data for the issuer.

### 4.3 Financial indicators

- `EASTMONEY_FINANCIAL_INDICATORS`
- cross-check and factor-support role only;
- provider-calculated ratios never replace source-reported statement facts.

### 4.4 Valuation and capitalization

- `EASTMONEY_CURRENT_VALUATION`: current price, market capitalization, PE and PB snapshot;
- `EASTMONEY_HISTORICAL_VALUATION`: conditional historical series;
- `EASTMONEY_SHARE_CAPITAL`: share-count history.

Provider PE or other ratios are raw evidence in FMDL-3A. Denominator validity must be recomputed and classified in FMDL-3D.

### 4.5 Shareholder return

- `EASTMONEY_DIVIDENDS`;
- `EASTMONEY_BUYBACKS`.

These routes provide event evidence, not an investment-quality conclusion.

## 5. Point-in-time benchmark

For each structured statement report period available from the primary statement candidate, the benchmark attempts to identify the corresponding filing metadata.

At daily resolution:

1. `report_period_end` is never treated as public availability;
2. the filing announcement date is sourced separately;
3. the earliest usable time is the next verified A-share trading session at 09:30 Asia/Shanghai;
4. later corrections or revised reports receive a higher `revision_sequence`;
5. historical values are never overwritten silently.

A source row without an official filing match remains blocked or degraded, even when the statement value itself is available.

## 6. Measured outputs

Candidate outputs:

- `FMDL3A_BENCHMARK_ROWS.csv`
- `FMDL3A_SOURCE_SUMMARY.csv`
- `FMDL3A_COVERAGE_MAP.csv`
- `FMDL3A_POINT_IN_TIME_EVIDENCE.csv`
- `FMDL3_SOURCE_INDEX.csv`
- `FMDL3A_SOURCE_DECISION.json`
- `FMDL3A_VALIDATION.json`
- `FMDL3A_MANIFEST.json`

Accepted outputs are published to:

- `outputs/financials/benchmark/current/`
- `outputs/financials/source_index/current/`
- `outputs/status/FMDL3A_LAST_SUCCESS.json`

## 7. Acceptance gates

The benchmark freezes numeric gates only from measured results.

Initial minimum gates are defined in the machine-readable config and include:

- official disclosure route success;
- primary three-statement bundle success;
- fallback three-statement bundle success;
- official filing-to-report-period match rate;
- current valuation sample coverage;
- at least one primary statement success in every required sector profile;
- a valid trading calendar;
- zero future-information leakage;
- zero trade authority.

If a hard gate fails, the candidate remains evidence for remediation and cannot replace Current.

## 8. FMDL-3B entry condition

FMDL-3B is authorized only when the final decision status is:

`FMDL3A_ACCEPTED_SOURCE_ROUTE_AND_COVERAGE_GATES_FROZEN`

FMDL-3B must then implement the accepted source routes and preserve the source-specific limitations found here.
