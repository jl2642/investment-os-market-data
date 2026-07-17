# FMDL-2B-2 Acceptance — Full-Universe Sharded Initial Backfill

## Acceptance state

`ACCEPTED_WITH_CONTROLLED_FOUR_SYMBOL_QUARANTINE`

FMDL-2B-2 completed the initial historical backfill for the accepted 5,529-symbol A-share universe. The candidate is approved as the immutable base history input for FMDL-2B-3 factor computation. It does not rank securities, alter the Investment OS candidate pool, create alpha claims or grant trade authority.

## Release identity

- Release ID: `FMDL2B2_29556547410_1`
- As-of date: `2026-07-16`
- Source full-backfill run: `29556547410`
- Recovery aggregation: quarantine-aware `aggregate_full_backfill_v2`
- Final independent acceptance run: `29563720516` — `SUCCESS`
- Final acceptance artifact: `8400273209`
- Artifact digest: `sha256:ad80fdf701e603c43e53e17a2d4cc8ae3c6c8d321058f73f406355ba7ff6fc87`
- Trade authority: `NONE`

## Accepted full-market results

- Universe symbols attempted: `5,529`
- Usable historical series: `5,525`
- Usable ratio: `99.9277%`
- Quarantined series: `4`
- Logical Parquet shards: `24`
- Normalized history rows: `2,494,405`
- Zstandard Parquet base store: `138,001,420 bytes` (`131.6084 MiB`)
- Accepted future rows: `0`
- Accepted duplicate symbol-date pairs: `0`
- Accepted impossible-OHLC rows: `0`
- Provider lineage completeness: `100%`
- Series-hash completeness: `100%`
- Seasoned usable listings with at least 251 observations: `5,378 / 5,378`

Board usable ratios:

- SH Main: `100%`
- SZ Main: `100%`
- ChiNext: `100%`
- BSE: `100%`
- STAR: `606 / 610` (`99.3443%`)

## Why the original Run 3 displayed failure

The original aggregate counted three impossible-OHLC rows belonging to already quarantined series as though they were rows promoted into the accepted Parquet store. This caused a false aggregate hard failure after all 24 shards had completed.

The recovery aggregator applies the intended fail-closed contract:

- impossible-OHLC rows in promoted data remain a hard failure;
- a complete series containing an impossible row is excluded from promoted Parquet history;
- the excluded anomaly is retained as quarantine evidence and controlled warning;
- quarantine cannot be used to conceal any other hard failure.

The final independent validator re-opened every committed Parquet shard and verified file hashes, metadata row counts, symbol assignment, full Universe mapping, aggregate hash, accepted date integrity and accepted OHLC integrity.

## Four controlled quarantines

### `689009.SH`

- FMDL-1 status: suspended;
- initial result: Sina returned empty JSON on both attempts;
- targeted retry: same source failure persisted;
- no approved STAR fallback exists;
- decision: retain quarantine until a validated source or resumed trading produces usable history.

### `688089.SH`, `688143.SH`, `688173.SH`

Each series was successfully retrieved through Sina, but each contains one persistent source row on `2024-11-06` with `open = high = low = 0` and a non-zero close. Targeted retry reproduced the same anomaly for all three symbols.

The rows were not repaired, interpolated, dropped silently or filled with the close. The complete affected series remain quarantined because silently altering source history would violate the frozen history contract.

## Acceptance gates passed

- all 24 shard manifests present and reconciled;
- all shard Parquet files exist and match their SHA-256 hashes;
- manifest aggregate hash reproduced;
- status table contains exactly one row for every accepted Universe symbol;
- Parquet symbol set equals the 5,525 usable status symbols;
- no symbol appears in multiple shards;
- stable SHA-256 shard assignment reproduced;
- accepted row count and byte size match quality metadata;
- no accepted future rows, duplicate symbol-date rows or impossible OHLC rows;
- quarantined series are excluded from factor-ready history;
- full-market usable and board coverage gates passed;
- source lineage and series hashes are complete;
- no Investment OS, simulation-account, real-account or trade state was changed.

## Operational changes

The automatic recovery trigger has been retired. The recovery workflow is now manual-only, so later documentation or factor-engine commits cannot accidentally re-download all 24 source artifacts.

## Non-claims

1. This release is a historical-data base, not a factor table.
2. The four quarantined symbols do not have factor-ready history in this release.
3. The QFQ store does not prove a survivorship-free or point-in-time fundamental backtest.
4. No historical-data result demonstrates factor alpha or authorizes a trade.
5. Daily incremental updates, corporate-action refresh overlays and Last-known-good factor publication remain FMDL-2B-4 work.

## Authorized next phase

`FMDL-2B-3 — Basic Factor Engine`

FMDL-2B-3 may calculate only the factors frozen in FMDL-2A. It must preserve missingness for the four quarantined series, keep one factor row per Universe symbol, disclose history availability and confidence, and remain research-priority evidence with no trade authority.
