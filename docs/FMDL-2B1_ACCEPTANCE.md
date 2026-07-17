# FMDL-2B-1 Acceptance — Historical Store Architecture & Full-Market Pilot

## Acceptance state

`ACCEPTED_WITH_CONTROLLED_SINGLE_SYMBOL_QUARANTINE`

FMDL-2B-1 validates the canonical Parquet storage design, deterministic cross-board pilot, source retry, quarantine, lineage, compression and runtime assumptions needed for the full 5,529-symbol initial backfill. It does not publish a full-market history Current, calculate production factors, rank securities or create trading authority.

## Release evidence

- Pilot run: `FMDL2B1_PILOT_20260717T114620+0800`
- GitHub Actions run: `29553180074` — `SUCCESS`
- Artifact ID: `8396614610`
- Artifact digest: `sha256:97d0b3868557d909ced1f091768ee98bc98576f6437f2ea9f388bb1123f6a76d`
- Accepted FMDL-1 Current: `FMDL1BC_20260716T165927+0800`
- As-of date: `2026-07-16`
- AKShare version: `1.18.64`
- Sample: `300` deterministic cross-board stress symbols
- Trade authority: `NONE`

## Real pilot results

- Usable symbols: `299/300` (`99.67%`)
- Sina primary series: `299`
- Tencent restricted fallback series: `0`
- Quarantined: `1`
- Normalized history rows: `109,602`
- Six Zstandard Parquet shards: `5.993 MiB`
- Projected 5,529-symbol initial store: `110.45 MiB`
- Runtime: `9.25 minutes`
- Median symbol latency: `1.6045 seconds`
- Estimated sequential full backfill: `147.85 minutes`
- Future rows: `0`
- Duplicate dates after normalization: `0`
- Impossible OHLC rows: `0`

Board usable ratios:

- SH Main: `100%`
- SZ Main: `100%`
- STAR: `98%`
- ChiNext: `100%`
- BSE: `100%`

All `220` usable seasoned listings in the pilot had at least `251` valid observations. The `78` usable rows below 251 observations were recent or otherwise partial-history listings and remain explicitly partial rather than being filled or rejected.

## Controlled exceptions

### Quarantined pilot symbol

`689009.SH` was already marked suspended in FMDL-1 Current. Both Sina attempts returned an empty JSON decode result. No approved STAR fallback exists, so the symbol was correctly quarantined without failing the other 299 symbols.

FMDL-2B-2 must retry this symbol as part of its non-usable-symbol recovery path. It must not silently route STAR history through Tencent.

### Suspended but valid stale histories

- `920685.BJ` latest valid history date: `2026-07-15`
- `301234.SZ` latest valid history date: `2026-07-07`

Both were marked suspended and retained as valid historical series. Their stale latest dates are status evidence, not future-filled observations or hard data failures.

## Architecture frozen from the pilot

- Storage: Parquet with Zstandard compression
- Initial base: immutable shard release
- Daily operation: immutable daily deltas
- Corporate actions: symbol-level refresh overlays
- Logical full-market shards: `24`
- Expected symbols per shard: approximately `231`
- Initial maximum parallel shards: `3`
- Processing inside each shard: sequential and retry-aware
- Checkpoint: per shard plus per-symbol status
- Resume behavior: retry only non-usable symbols
- Provider mixing: forbidden within a symbol series
- Last-known-good: incomplete shard sets cannot replace a valid Current

The initial three-way parallel design is expected to reduce elapsed backfill time to about 50 minutes while keeping total runner consumption near the measured sequential estimate. Concurrency must not be increased merely to reduce elapsed time if public-source failure rates rise.

## Acceptance gates passed

- deterministic 300-symbol sample and board quotas;
- FMDL-1 interface validation;
- contract and unit tests;
- real GitHub-hosted Sina QFQ retrieval;
- restricted fallback and board-routing enforcement;
- canonical row lineage and hashes;
- independent Parquet shard creation;
- per-symbol retry and quarantine evidence;
- compression and projected repository-size assessment;
- runtime below the frozen pilot limit;
- no trade, candidate-pool or factor-ranking authority introduced.

## Non-claims

1. The pilot is not the complete 5,529-symbol historical store.
2. The projected store size and runtime remain estimates until FMDL-2B-2 runs all shards.
3. The pilot does not prove every full-market symbol will succeed.
4. The pilot does not prove factor alpha or economic investment value.
5. No pilot result changes the existing candidate pool, simulation account or real account.

## Authorized next phase

`FMDL-2B-2 — Full-Universe Sharded Initial Backfill`

FMDL-2B-2 must follow `config/fmdl2_full_backfill_plan.json`. It may publish a historical-store candidate only after all 24 shard manifests are reconciled, failed symbols are retried or quarantined, aggregate quality gates pass and a full-store manifest and hash are produced.
