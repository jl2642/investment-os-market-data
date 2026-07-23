# FMDL-7E — Failure Recovery, Clean-room Restore & Canonical Refresh

## Objective

FMDL-7E converts the accepted FMDL-7-0 through FMDL-7D operating state into one deterministic recovery and user-facing Canonical package. It proves that the system can recover from pointer, package, Manifest, publication, staleness and authority failures without relying on conversation memory.

This stage also replaces the Release 8-only File Library architecture with a Release 9 control-plane, state and recovery capsule that references the accepted A-share, Hong Kong Stock Connect and US immutable GitHub Releases.

## Authoritative entry state

- FMDL-7D Release 52 is the entry gate.
- FMDL-7-0 through FMDL-7D remain strictly ordered at Releases 48–52.
- Investment OS Release 8 remains the historical A-share binary identity.
- FMDL-5-FINAL Release 18 remains the accepted Hong Kong Stock Connect overlay.
- FMDL-6X4-FINAL Release 47 remains the accepted US Research Adapter baseline.
- `trade_authority = NONE` throughout.

## Release 8 truth boundary

File Library search can identify the Release 8 companion pointer and its package identity, but the Release 8 ZIP is not independently available to the GitHub runtime or file-search interface for byte replay. FMDL-7E therefore:

- preserves Release 8 identity, package SHA, size and state date;
- does not falsely claim to embed or revalidate the missing legacy binary;
- generates a new deterministic Release 9 package from currently accepted GitHub authority records;
- keeps full market data stores under immutable GitHub Release and pointer authority.

## Release 9 package architecture

`股票投资助手_CURRENT.zip` contains:

- `00_CONTROL` — Start Here, Current pointer, Manifest, Release registry and Release 8 binding;
- `10_STATE` — accepted real-account, simulation, Candidate and state-binding records;
- `20_CANONICAL_BINDINGS` — Release 8, Hong Kong, US and FMDL-7 authority pointers;
- `30_OPERATIONS` — scheduled-operation cadence and quality state;
- `40_RECOVERY` — clean-room restore plan, restore report and failure-injection report;
- `50_FILE_LIBRARY` — promotion and safe-cleanup procedure;
- `90_GOVERNANCE` — explicit zero-mutation and no-trade-authority proof.

The package is deliberately a compact operational capsule, not a duplicate offline warehouse containing every A-share, Hong Kong and US historical shard.

## Clean-room restore

The accepted restore order is:

1. reject unsafe, duplicate or corrupted ZIP members;
2. verify all Manifest member hashes;
3. bind the package pointer and companion pointer;
4. bind Release 8, Hong Kong, US and FMDL-7 immutable authorities;
5. restore the 2026-07-20 Last-known-good state without calling it current;
6. restore cadence, staleness, cost and escalation controls;
7. keep live action closed until the user confirms later account changes and fresh market data is available.

Conversation memory is not an authority source.

## Publication products

FMDL-7E publishes:

- `股票投资助手_CURRENT.zip`;
- `股票投资助手_CURRENT_POINTER.md`;
- `股票投资助手_START_HERE_CURRENT.md`;
- package identity and Source Binding;
- clean-room restore acceptance;
- File Library promotion plan;
- failure-injection report;
- Quality Report, Decision, artifact Manifest and 576 logical shard records;
- Current, immutable Release, normalized, archive, Last-success and LKG pointers.

## File Library promotion boundary

The generated package is not active merely because GitHub production succeeds. Activation requires the user-facing package, pointer and Start Here to be uploaded to File Library, opened and checked against the companion pointer SHA.

Until that transaction is complete:

- the Release 8 pointer remains retained;
- Release 9 status is `GENERATED_BYTE_VALIDATED_USER_UPLOAD_REQUIRED`;
- File Library has no active Release 9 Canonical claim;
- Project Sources remain empty.

## Completion boundary

FMDL-7E accepts package generation, byte validation, clean-room recovery, failure rejection and promotion readiness. It does not refresh market data, confirm post-2026-07-20 holdings, generate a live investment recommendation, mutate Candidate Pool, simulation, real account or rules, connect brokerage, or create an order.

## Required exit

`FMDL7E_FAILURE_RECOVERY_CLEAN_ROOM_RESTORE_AND_CANONICAL_REFRESH_ACCEPTED`

## Next gate

`FMDL-7-FINAL_CROSS_MARKET_AND_FULL_SYSTEM_FINAL_OPERATIONAL_ACCEPTANCE`
