# FMDL-2A — Historical Source Benchmark Plan

This document governs the free-source benchmark used to select the historical daily-data adapter for FMDL-2B.

## Candidate adapters

The benchmark probes only functions present in the installed AKShare build:

1. `stock_zh_a_hist` — Eastmoney daily history;
2. `stock_zh_a_daily` — Sina daily history;
3. `stock_zh_a_hist_tx` — Tencent daily history, when exposed by the installed version.

No paid endpoint, API key or trial credit is permitted.

## Deterministic sample

The scale sample contains 120 symbols drawn from the accepted Current universe with board targets:

- Shanghai Main: 30;
- Shenzhen Main: 30;
- STAR: 20;
- ChiNext: 20;
- Beijing Stock Exchange: 20.

The selector prioritizes inclusion of ST and suspended rows when available, then fills each board quota by a stable SHA-256 ordering. The sample and its hash are written with the benchmark output.

## Two-stage benchmark

1. **Smoke stage:** 15 cross-board symbols against every installed candidate adapter.
2. **Scale stage:** the best two smoke-stage adapters are tested. The leading adapter receives all 120 symbols; the fallback receives at least 40 symbols.

An adapter is ineligible for scale when smoke success is below 60%, its normalized schema is unusable, or it cannot return adjusted daily close.

## Per-series checks

- request success and latency;
- non-empty result;
- recognized date/OHLC/volume/amount columns;
- unique and ascending dates after normalization;
- positive OHLC values;
- no future date beyond requested end date;
- latest-date freshness;
- at least 251 valid observations for seasoned listings, with new listings explicitly separated;
- adjustment mode recorded;
- duplicate-date and impossible-OHLC counts;
- source error and timeout evidence retained.

## Selection policy

The production recommendation is based on:

1. scale success rate;
2. latest-session coverage;
3. schema completeness;
4. adjusted-series availability;
5. median and p95 latency;
6. board coverage, especially BSE;
7. operational stability on GitHub-hosted Linux runners.

No adapter is promoted merely because a small smoke sample succeeds. The result may select a primary plus an explicit fallback, or block FMDL-2B if no free source is sufficiently reliable.

## Acceptance

FMDL-2A is accepted only when:

- the factor contract is machine-readable and documented;
- the deterministic sample is generated from accepted Current;
- GitHub-hosted real-source benchmark evidence exists;
- a primary/fallback decision is recorded with limitations;
- FMDL-2B ingestion, cache and incremental-update requirements are frozen;
- no claim is made that factor alpha has been demonstrated.
