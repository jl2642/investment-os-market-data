# FMDL-3B-2 — Full-Universe Initial Statement Matrix

## Purpose

Build the first deterministic, point-in-time A-share financial-statement base across the accepted `5,528`-issuer Universe. This is the production execution step authorized by the accepted FMDL-3B-2 canary. It does not complete FMDL-3B; successful publication authorizes FMDL-3B-3 comparability and restatement hardening.

## Entry gate

The workflow must read an accepted canary Current with status:

`FMDL3B2_CANARY_ACCEPTED_FULL_UNIVERSE_MATRIX_AUTHORIZED`

No matrix job may run against an unpublished or failed canary candidate.

## Deterministic sharding

- Universe source: `outputs/current/DAILY_MARKET_SNAPSHOT.csv`;
- method: SHA-256 sort followed by round-robin assignment;
- shard count: `32`;
- maximum issuers per shard: `200`;
- workers per shard: `4`;
- GitHub matrix maximum parallelism: `16`;
- every issuer must appear exactly once;
- membership and membership hashes must be replayable from configuration and Universe alone.

## Data route

For every non-BSE issuer:

1. retrieve CNINFO official filing identity and market-availability evidence;
2. retrieve Eastmoney balance sheet, income statement and cash-flow statement;
3. invoke Sina only for a failed or missing primary statement component;
4. retain all extracted numeric provider fields in the raw fact shard;
5. map only exact accepted aliases into the normalized long-form shard;
6. create source lineage, revision identity, QA and conflict evidence;
7. quarantine unresolved issuers and place them in the retry ledger.

BSE issuers remain controlled quarantine until CNINFO official-document extraction is implemented. They may not receive fabricated or SH/SZ-derived structured facts.

## Shard outputs

Each shard produces:

- immutable raw-fact Parquet;
- normalized long-form Parquet;
- revision-ledger Parquet;
- source-index Parquet;
- support map;
- retry ledger;
- conflict log;
- ambiguous-mapping report;
- performed statement checks;
- QA flags;
- comparability bridge;
- provider-field frequency report;
- decision, independent validation and manifest.

A shard is accepted only when all membership, source-lineage, PIT, arithmetic, ambiguity, conflict and authority checks pass.

## Storage and publication

### Raw facts

Raw facts are stored as `32` immutable GitHub Actions artifacts named:

`fmdl3b2-raw-shard-00` through `fmdl3b2-raw-shard-31`

Retention is `90` days. The formal Release contains an index with workflow-run ID, artifact name, shard validation status, raw-file hash and byte size.

### Normalized statement base

Accepted normalized, revision and source-index shards are stored once under:

`datasets/financials/releases/<release_id>/`

The Current directory contains compact pointers and quality maps rather than duplicate Parquet copies. Each file must remain below GitHub's `100 MiB` hard limit; the aggregate normalized store must remain below the frozen `750 MiB` ceiling.

### Current and Last-known-good

Publication occurs only after all 32 shard validations and the independent aggregate validation pass. A failed candidate cannot replace Current. Successful publication creates:

- immutable dataset Release;
- compact `outputs/financials/full_build/current/` interface;
- compact immutable Archive snapshot;
- `outputs/status/FMDL3B2_LAST_SUCCESS.json`.

## Aggregate exit gates

The aggregate must prove:

- all 32 shards exist and independently pass;
- all 5,528 Universe issuers appear exactly once;
- non-BSE support is at least 95%;
- non-BSE quarantine is no more than 5%;
- official PIT match is at least 90%;
- zero future facts;
- zero ambiguous canonical mappings;
- zero source-less decision-grade facts;
- zero duplicate effective intervals;
- zero unclassified conflicts;
- zero failed performed statement checks;
- BSE official-document indexes are present;
- normalized Parquet files are readable and within storage limits;
- raw artifact index is complete;
- trade authority remains `NONE`.

## Controlled remediation

If one or more issuers fail, they remain visible in the support map and retry ledger. Repair must be performed as a bounded overlay against the failed issuer set; accepted issuers and accepted immutable raw shards must not be silently regenerated or overwritten.

## Exit state

Successful publication status:

`FMDL3B2_FULL_UNIVERSE_INITIAL_BUILD_ACCEPTED_WITH_CONTROLLED_QUARANTINE`

Next gate:

`FMDL-3B-3_COMPARABILITY_AND_RESTATEMENT_HARDENING`

## Authority boundary

This layer owns financial-data evidence and normalization only. It does not authorize financial factors, candidate promotion, portfolio migration, position sizing or trading. Trade authority is `NONE`.
