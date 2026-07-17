# FMDL-2B-2 — Full-Universe Sharded Initial Backfill

## Purpose

Build one complete historical-data candidate for every symbol in the accepted FMDL-1 A-share universe. This phase stores historical evidence only. It does not calculate production factor ranks, create a screening list, change a portfolio or create trading authority.

## Frozen inputs

- Universe: `outputs/current/A_SHARE_UNIVERSE.csv`
- Current release: `outputs/current/CURRENT_RELEASE.json`
- Historical source route: `config/fmdl2_historical_source_routes.json`
- Full-backfill plan: `config/fmdl2_full_backfill_plan.json`
- Canonical history contract: `config/fmdl2_history_store.json`

## Execution model

1. Assign every canonical symbol to one of 24 logical shards using `SHA256(symbol) mod 24`.
2. Run at most three shards in parallel.
3. Process symbols sequentially inside each shard.
4. Use Sina QFQ history as the primary route with two attempts.
5. Permit Tencent only for SH/SZ Main price-and-amount fallback; historical volume remains null.
6. Quarantine unresolved symbols without aborting completed symbols or other shards.
7. Upload each shard as an independent immutable artifact.
8. Aggregate only after all 24 shard jobs complete.
9. Verify symbol coverage, deterministic assignment, hashes, dates, OHLC, provider lineage and market/board quality gates.
10. Write an immutable base release and a metadata-only Historical Store Candidate.

## Stored assets

Historical rows:

```text
datasets/history/base/<release_id>/shards/shard_00.parquet
...
datasets/history/base/<release_id>/shards/shard_23.parquet
```

Shard evidence:

```text
datasets/history/base/<release_id>/manifests/
```

Candidate control plane:

```text
outputs/history/candidate/
├── HISTORICAL_STORE_RELEASE.json
├── HISTORICAL_STORE_MANIFEST.json
├── HISTORICAL_STORE_QUALITY.json
├── HISTORICAL_SYMBOL_STATUS.csv
├── HISTORICAL_QUARANTINE.csv
├── FMDL2B2_RUN_REPORT.json
└── FMDL2B2_RUN_REPORT.md
```

## Promotion boundary

The aggregate output remains `FULL_MARKET_HISTORICAL_STORE_CANDIDATE`. It is not promoted to `outputs/history/current/` during FMDL-2B-2. Current promotion, incremental append and last-known-good operational tests remain FMDL-2B-4.

## Hard gates

- all 5,529 accepted Universe symbols attempted exactly once;
- all 24 shard manifests present and hash-valid;
- deterministic shard assignment error count zero;
- market usable ratio at least 95%, with 97% as the acceptance target;
- each board usable ratio at least 90%;
- future rows, duplicate dates and impossible OHLC rows all zero;
- at least 99% of usable seasoned listings have 251 observations;
- provider lineage and series hashes complete for every usable symbol;
- no missing value filled with zero;
- no provider series silently stitched.

## One-shot workflow control

The production workflow is triggered once by `triggers/FMDL2B2_RUN.md` on the dedicated branch. The workflow's own output commit does not match the trigger path and therefore cannot start a second full-market backfill. After acceptance the trigger is retired and the workflow is reduced to manual recovery use.
