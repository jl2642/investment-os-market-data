# Investment OS Runtime

This directory contains the rule, state, research, decision, operations and recovery layers of the Stock Investment Assistant within the existing `jl2642/investment-os-market-data` repository.

## Current status

`WP1-5A COMPLETED — WP1-5B READY`

Only the control foundation is active. Rules, schemas and state are rebuilt in WP1-5B. No investment state was changed during WP1-5A.

## Directory model

```text
00_CONTROL
10_CORE_STATIC
20_SCHEMAS_AND_INTERFACES
30_STATE_CURRENT
40_EVIDENCE_AND_LINEAGE
50_MARKET_CAPABILITY_BINDINGS
60_OPERATIONS_AND_EVENT
70_ATTRIBUTION_AND_CALIBRATION
80_EXECUTABLE_RUNTIME
90_RECOVERY_AND_ARCHIVE
```

## Permanent controls

- `trade_authority = NONE`;
- user is the sole investment decision-maker and trade executor;
- no automatic Candidate, simulation or real-account admission;
- no automatic rule mutation;
- no brokerage connection or order generation;
- data releases cannot silently mutate Investment OS state.
