# FMDL-3B-2 — Full-Universe Build Canary Acceptance

## Acceptance state

`FMDL3B2_CANARY_ACCEPTED_FULL_UNIVERSE_MATRIX_AUTHORIZED`

This gate confirms that the accepted FMDL-3B statement contract can be expanded beyond the curated pilot with deterministic membership, primary-only routing, fallback-on-failure, point-in-time lineage, Parquet compression, bounded file sizes and measurable shard runtime. It authorizes the full 32-shard matrix build. It does not claim full-market publication and does not mark FMDL-3B complete.

## Accepted candidate evidence

- final Head workflow: `29630794138` — success;
- candidate run: `FMDL3B2C_20260718T123553+0800`;
- generated at: `2026-07-18T12:41:18+08:00`;
- artifact: `8425430990`;
- artifact digest: `sha256:6549b691419f2665374b267f7277735a27c2f9f5349a4758eef0c808274963fc`;
- runner gates: `15 / 15 PASS`;
- independent validation: `24 / 24 PASS`;
- actual statement tie-out checks: `796 / 796 PASS`;
- hard failures: `0`;
- authority: `DATA_AND_RESEARCH_EVIDENCE_ONLY`;
- trade authority: `NONE`.

## Measured coverage and routing

- accepted Universe: `5,528` issuers;
- deterministic canary: `32` issuers;
- supported / controlled quarantine: `30 / 2`;
- non-BSE three-statement bundle success: `100%`;
- Eastmoney primary-only share: `100%`;
- Sina fallback components invoked / used: `0 / 0`;
- official PIT fact match: `96.43695%`;
- BSE official-document index: `100%`;
- future facts: `0`;
- source-less decision-grade facts: `0`;
- duplicate effective intervals: `0`;
- ambiguous same-source canonical mappings: `0`;
- classified / unclassified conflicts: `0 / 0`;
- QA flags: `2`, both BSE controlled quarantine.

## Data volume

- raw facts: `74,599`;
- normalized facts: `10,156`;
- decision-grade facts: `9,685`;
- revision-ledger and source-index Parquet round trips: PASS;
- largest canary file: `3.3716 MiB`;
- projected full-Universe raw store: `621.28 MiB`;
- projected full-Universe normalized store: `106.90 MiB`.

The raw full-market store will therefore remain immutable workflow-artifact shards until a durable retention route is frozen. The normalized store may be published as deterministic Git Current shards because projected files remain below the `95 MiB` per-file limit and the total projection remains below the `750 MiB` normalized-store gate.

## Runtime and sharding

- canary wall time: `320.718` seconds with four workers;
- planned shard count: `32`;
- planned maximum issuers per shard: `200`;
- projected wall time per shard at the canary rate: `30.78` minutes.

Every shard must retain immutable symbol membership, source/retrieval state, raw and normalized Parquet, revision ledger, support/quarantine map, field-frequency report, retry ledger, validation and manifest hashes. A failed shard cannot replace an accepted shard.

## Defect found and closed

The first canary run produced `188` cash-flow tie-out failures. Investigation showed the exact missing term was Eastmoney's `RATE_CHANGE_EFFECT`. It is now mapped to `fx_cash_effect`, which reduced performed statement failures from `188` to `0`.

The runner itself now contains a hard gate requiring `performed_validation_failure_count = 0`; acceptance no longer relies only on the independent validator to catch arithmetic failures.

## Controlled limitations

1. The canary is not full-market coverage.
2. BSE structured facts remain unavailable until official CNINFO document extraction is implemented.
3. Non-pilot canary issuers retain `UNCLASSIFIED_FULL_UNIVERSE` profile labels; sector profiling is not inferred from price data.
4. Raw full-market storage remains artifact-sharded pending retention-policy finalization.
5. Financial factors, valuation conclusions, candidate promotion and portfolio actions remain unauthorized.

## Full matrix authorization

The next gate is `FMDL-3B-2_FULL_UNIVERSE_MATRIX_BUILD`. The matrix must preserve the accepted canary contract and publish only after every shard is either accepted or explicitly quarantined, the aggregate manifest is reproducible, and no failed shard replaces Last-known-good.