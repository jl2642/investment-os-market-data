# HKCU P5D｜Manual Staged Execution Support — No-Execution Development Path

## Objective

P5D is being accepted in development mode. The goal is to prove that the manual staged-execution support layer behaves correctly **without pretending that the user approved a real trade**.

The accepted P5C state is `READY_AWAITING_EXPLICIT_USER_DECISION` with `user_decision_recorded_count=0`. Therefore the production path must remain blocked.

## Production path

Without explicit user trade approval, P5D must produce:

- `production_execution_state = BLOCKED_NO_USER_APPROVAL`
- zero REAL execution-checklist rows;
- zero orders;
- zero inferred fills;
- zero REAL Current mutations;
- `trade_authority = NONE`.

A generic request to continue development is **not** trade approval.

## Synthetic engine capability path

To prove that the execution-support engine is technically usable when a future user really approves a trade, P5D runs an isolated synthetic fixture using only `TEST_*` identifiers. It proves:

1. capital amount from portfolio NAV and target weight;
2. floor rounding to whole board lots;
3. multi-batch allocation using whole lots only;
4. a maximum-price-drift guard around a reference price.

The synthetic fixture is explicitly non-executable. It cannot mutate Candidate, SIMULATION or REAL Current, create an order, infer a fill or be interpreted as a user instruction.

No actual HK security is allowed in the synthetic capability report.

## Governance

P5D does not alter the P5A frozen production semantics: a real manual execution checklist still requires explicit user approval. This development acceptance only proves that the production path refuses to proceed without approval and that the isolated calculation engine behaves correctly.

On PASS, the development sequence may continue to `P5E_ZERO_EXECUTION_RECONCILIATION_AND_OBSERVATION`, where the system must prove that zero real executions result in zero REAL writeback and that operating observation can begin without fabricating trades.

`trade_authority=NONE` throughout.
