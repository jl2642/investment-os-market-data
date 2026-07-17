# FMDL-2B-1 — Historical Store Architecture & Full-Market Pilot

## Purpose

This subphase validates the storage, ingestion, retry, quarantine and runtime design required before the 5,529-symbol initial historical backfill. It does not publish a full-market historical store, calculate production factor tables, rank stocks or create trade authority.

## Inputs

- accepted `outputs/current/A_SHARE_UNIVERSE.csv`;
- accepted `outputs/current/CURRENT_RELEASE.json`;
- FMDL-2A source route in `config/fmdl2_historical_source_routes.json`;
- history contract in `config/fmdl2_history_store.json`;
- canonical row schema in `schemas/a_share_daily_history.schema.json`.

## Deterministic 300-symbol pilot

The pilot uses a fixed, hash-stable sample:

- Shanghai Main: 75;
- Shenzhen Main: 75;
- STAR: 50;
- ChiNext: 50;
- Beijing Stock Exchange: 50.

Within every board, ST, suspended, recent-listing and missing-list-date records are deliberately prioritized before hash-stable filling. This makes the pilot a stress sample rather than an easy random sample.

## Source route

1. Primary: `Sina / stock_zh_a_daily`, QFQ, two attempts with backoff.
2. Restricted fallback: `Tencent / stock_zh_a_hist_tx`, SH/SZ Main only, QFQ price and amount only.
3. Tencent volume is always null and cannot be used for volume factors.
4. Provider series cannot be silently stitched for a symbol.
5. STAR, ChiNext and BSE rows are quarantined when Sina fails because no board-approved fallback exists.

## Canonical storage

Pilot shards are written as Parquet with Zstandard compression. Canonical rows contain:

- trade date and canonical symbol;
- QFQ OHLC;
- source-reported volume and turnover where supported;
- provider, AKShare function and adjustment lineage;
- retrieval timestamp, quality state and row hash.

The pilot writes six 50-symbol logical shards. Data remains under `outputs/pilot/fmdl2b1/` and is never promoted to `outputs/history/current/`.

## Per-symbol state

- `READY`: validated Sina series with price, volume and amount capabilities;
- `PARTIAL_FALLBACK_PRICE_AMOUNT`: approved Tencent fallback without volume;
- `QUARANTINED`: all allowed sources failed or a hard series gate failed.

The status table records attempts, latency, source errors, valid date range, observations, capability flags, series hash and quarantine reason.

## Pilot acceptance gates

- usable symbols at least 95%;
- every board usable ratio at least 90%;
- no future rows;
- no duplicate dates after normalization;
- no impossible OHLC rows;
- runtime no more than 35 minutes;
- projected compressed full-market store no more than 512 MiB.

Warnings do not become zeros or neutral factor values. New listings and restricted fallback records remain explicitly partial.

## Pilot evidence

The GitHub workflow must retain:

- deterministic sample CSV;
- per-symbol status CSV;
- six Parquet shards;
- quarantine records;
- JSON and Markdown run reports;
- pilot release marker;
- workflow log.

## Decision after pilot

Only real GitHub-hosted measurements may freeze:

- storage format and compression;
- logical shard count and symbols per shard;
- initial worker concurrency;
- projected repository footprint;
- projected initial-backfill runtime;
- whether FMDL-2B-2 may begin.

No pilot result demonstrates factor alpha or changes any Investment OS portfolio, candidate pool or trade state.
