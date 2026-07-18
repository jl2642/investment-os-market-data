# FMDL-3B-2 — Full-Universe Initial Statement Build

## Purpose

Expand the accepted FMDL-3B-1 statement contract from a representative pilot to the accepted A-share Universe without creating an unbounded, non-resumable or non-auditable data dump.

## Canary before matrix build

The first FMDL-3B-2 gate is a deterministic 32-issuer canary. It contains all 13 FMDL-3A stress issuers plus SHA-256-sorted non-BSE Universe names. It measures:

- primary three-statement success;
- official PIT linkage;
- fallback invocation and use;
- runtime per issuer and projected shard runtime;
- raw and normalized Parquet compression;
- projected full-Universe storage;
- high-frequency unmapped provider fields;
- exact source lineage, revision intervals and QA performance.

The canary is not presented as full-market coverage.

## Production source policy

- CNINFO remains the official filing and availability route.
- Eastmoney remains the primary structured statement route.
- Sina is invoked only for failed or missing primary statement components. It is not duplicated across the whole Universe merely for convenience.
- BSE remains controlled quarantine until official-document extraction produces source-linked structured facts.

## Sharding and recovery

The planned initial build uses 32 deterministic issuer shards with a maximum target of 200 issuers per shard. Each accepted shard must contain:

- immutable symbol membership;
- source index and retrieval state;
- raw facts and normalized facts;
- revision ledger;
- support/quarantine map;
- field-frequency and missingness reports;
- QA and manifest hashes;
- retry ledger for failed issuers.

A failed shard cannot replace an accepted shard. Symbol-level retries create repair overlays or a new immutable shard release; they do not silently rewrite prior data.

## Storage policy

Raw full-market facts are not committed to Git as CSV. The canary measures Zstandard Parquet size first. Until a durable retention route and projected size are accepted, raw shards remain immutable workflow artifacts. Compact normalized shards may enter Git Current only when every file stays below 95 MiB and the total projected normalized store remains within the frozen limit.

CSV is reserved for compact indexes, quality reports and coverage maps.

## Canary exit gate

`FMDL3B2_CANARY_ACCEPTED_FULL_UNIVERSE_MATRIX_AUTHORIZED`

This gate authorizes the 32-shard matrix build. It does not authorize final Statement Current or mark FMDL-3B complete.