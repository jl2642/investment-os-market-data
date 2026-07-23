# FMDL-7E Acceptance Criteria

## Required entry

FMDL-7E may run only after `FMDL7D_20260723_1b62d98ab7bb` is accepted at Release sequence 52 and opens the FMDL-7E gate with `trade_authority = NONE`.

## Required identity bindings

The build must bind and verify:

- FMDL-7-0 through FMDL-7D in strict Release sequence 48–52;
- Investment OS Release 8 identity and historical outer package hash;
- FMDL-5-FINAL Hong Kong Stock Connect Release 18;
- FMDL-6X4-FINAL US Research Adapter Release 47;
- zero investment-state mutation and zero order authority across every bound pointer.

## Canonical package acceptance

The new user-facing package must:

1. use the stable filename `股票投资助手_CURRENT.zip`;
2. identify itself as Canonical Release 9;
3. contain a self-describing Current pointer, Start Here, Manifest, Release registry, LKG state summaries, operating cadence, recovery plan, failure report, File Library promotion plan and zero-mutation proof;
4. preserve Release 8 identity without claiming that the unavailable Release 8 binary is embedded;
5. treat complete market stores as immutable GitHub Release assets rather than silently presenting the compact recovery capsule as a full offline data warehouse;
6. pass deterministic same-input replay, ZIP open/CRC checks, safe-path checks and every Manifest member hash;
7. place the outer ZIP SHA-256 in the companion pointer and package-identity product.

## Clean-room restore acceptance

A fresh checkout using Python 3.12 and no conversation memory must be able to:

- bind all authority pointers;
- open and verify the package;
- restore the 2026-07-20 Last-known-good real account, simulation and Candidate state without promoting it to current;
- restore scheduled-operation, staleness, cost and failure controls;
- keep live action blocked until post-as-of account confirmation and fresh market data are available.

## Failure-recovery acceptance

All twelve fixtures must be rejected without replacing Current or LKG:

- missing authority pointer;
- Release identity mismatch;
- Manifest hash tamper;
- partial publication;
- unsafe ZIP path;
- duplicate package member;
- corrupted ZIP;
- pointer/package SHA mismatch;
- stale LKG promoted as current;
- File Library pointer without a verified package;
- unauthorized investment-state mutation;
- trade-authority escalation.

## File Library boundary

The GitHub workflow may generate, byte-validate and publish the package, pointer and Start Here, but the available connector cannot write them into File Library. Therefore:

- `GENERATED_BYTE_VALIDATED_USER_UPLOAD_REQUIRED` is an accepted technical handoff state;
- the new package is not the active File Library Canonical until upload, open verification and outer SHA verification are complete;
- the Release 8 pointer must be retained until those checks pass;
- Project Sources remain empty.

## Zero-authority boundary

Acceptance requires:

```text
Candidate Pool mutations = 0
Simulation book mutations = 0
Real account mutations = 0
Rule mutations = 0
Orders = 0
trade_authority = NONE
```

## Required exit

`FMDL7E_FAILURE_RECOVERY_CLEAN_ROOM_RESTORE_AND_CANONICAL_REFRESH_ACCEPTED`

## Next gate

`FMDL-7-FINAL_CROSS_MARKET_AND_FULL_SYSTEM_FINAL_OPERATIONAL_ACCEPTANCE`
