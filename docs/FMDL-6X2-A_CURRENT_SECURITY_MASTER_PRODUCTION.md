# FMDL-6X2-A — Current Security Master Production

## Objective

Produce the first real US-equity production data layer from the two accepted Nasdaq Trader official symbol-directory routes. The phase must account for every logical source row and publish a complete current target-venue Security Master observation layer for `XNAS`, `XNYS`, and `XASE`.

## Identity boundary

FMDL-6X2-A does **not** pretend that exchange and ticker are immutable security identity. It issues deterministic **provisional directory-observation record IDs**, leaves canonical issuer/share-class/security/listing IDs null, and routes identity resolution to FMDL-6X2-B.

A current target-venue row is included in the master when its symbol, security name, and venue are parseable and its active listing observation key is unique. Malformed, unknown-exchange, or duplicate target rows are quarantined. Non-target venues from `otherlisted.txt` are explicitly excluded but retained in row accounting.

## Preliminary statuses

- Official ETF flag `Y` → `REFERENCE_ONLY`
- Official NextShares flag `Y` → `REFERENCE_ONLY`
- Official test issue flag `Y` → `EXCLUDED`, but the security row remains retained
- All other securities → `RESEARCH_REVIEW_REQUIRED`

Every included record retains:

- `CHANNEL_ELIGIBILITY_PENDING`
- `PORTFOLIO_ADMISSION_NOT_AUTHORIZED`
- `trade_authority = NONE`

## Production outputs

The candidate and accepted release contain:

- both raw official source snapshots and metadata;
- a 100% row-accounting ledger;
- explicit exclusion and quarantine queues;
- a deterministic ZIP containing all `3 venues × 64 buckets = 192` JSONL shards;
- source snapshot report;
- quality report;
- decision;
- manifest.

On acceptance, the workflow publishes Current, immutable Release, raw archive, normalized archive, Last-success, and Security Master LKG.

## Phase boundary

This phase creates real current Security Master observations. It does not resolve issuer identity, backfill history, ingest SEC facts, calculate factors, mutate candidate/simulation/real-account state, or generate orders.
