# FMDL-5G — Hong Kong Investment OS Integration

## Objective

Convert the accepted FMDL-5F Hong Kong Public Equity Research decisions into a governed, read-only Investment OS state overlay without mutating the accepted Release-8 canonical package, candidate pool, simulation portfolio, real account or trade register.

## Entry gates

- FMDL-5F Last-success status: `FMDL5F_PUBLIC_EQUITY_RESEARCH_ADAPTER_ACCEPTED`;
- FMDL-5F next gate: `FMDL-5G_INVESTMENT_OS_INTEGRATION`;
- canonical base: `INVESTMENT_OS_R8_20260720_501345e84562`;
- base status: `INVESTMENT_OS_CANONICAL_REFRESH_AND_STATE_RECONCILIATION_ACCEPTED`;
- trade authority: `NONE`.

## Integration model

FMDL-5G is an additive cross-market overlay. It does not repack the File Library Release-8 package. Formal repack and unified operational acceptance remain FMDL-5-FINAL work.

Accepted FMDL-5F decisions are routed as follows:

- `GRADUATED` → `HK_CANDIDATE_REENTRY_REVIEW`;
- `SHADOW_TRACK` → `HK_SHADOW_TRACK_REVIEW`;
- A/H cases → additional cross-market duplication review.

A research transition is not candidate admission. Candidate review is not simulation admission. Simulation review is not real-account admission. Any real-account action remains subject to an explicit user-confirmation gate.

## Expected state overlay

The accepted FMDL-5F cohort creates six transitions:

- four candidate re-entry review records;
- two Shadow Track records;
- at least two A/H cross-market duplication review records.

The overlay also creates explicit simulation and real-account routers. Every record is `NOT_ADMITTED`, with mutation count zero.

## Outputs

- `FMDL5G_STATE_TRANSITIONS.jsonl`;
- `FMDL5G_HK_CANDIDATE_REENTRY_REVIEW_QUEUE.csv`;
- `FMDL5G_HK_SHADOW_TRACK_QUEUE.csv`;
- `FMDL5G_CROSS_MARKET_DUPLICATION_REVIEW.csv`;
- `FMDL5G_STATE_ROUTER.csv`;
- `FMDL5G_SIMULATION_ROUTER.csv`;
- `FMDL5G_REAL_ACCOUNT_ROUTER.csv`;
- `FMDL5G_STATE_DIFF.json`;
- `FMDL5G_ROLLBACK_PROOF.json`;
- Decision, Quality Report, independent validation and Manifest.

## Acceptance gates

- exactly six unique state transitions;
- exactly four candidate re-entry review routes;
- exactly two Shadow Track routes;
- at least two cross-market duplication reviews;
- zero missing Research Object bindings or object-hash mismatches;
- zero canonical Release-8 repack;
- zero existing candidate-pool, simulation, real-account or order mutation;
- deterministic same-input replay;
- rollback proof preserves Release 8 and prior Last-known-good;
- `trade_authority = NONE`.

## Publication

After successful PR validation and main execution, the workflow publishes:

- Current: `outputs/fmdl5g/integration/current/`;
- Archive: `outputs/fmdl5g/integration/archive/<release_id>/`;
- Immutable Release: `datasets/fmdl5g/integration/releases/<release_id>/`;
- Last-success: `outputs/status/FMDL5G_LAST_SUCCESS.json`.

## Exit

`FMDL5G_INVESTMENT_OS_INTEGRATION_ACCEPTED`

Next gate: `FMDL-5-FINAL_OPERATIONAL_ACCEPTANCE`.
