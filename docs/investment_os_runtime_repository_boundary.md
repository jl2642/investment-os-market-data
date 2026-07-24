# Investment OS Single-Repository Boundary

- **Status**: `WP1_5A_CONTROL_FOUNDATION_COMPLETED`
- **Date**: 2026-07-24
- **Repository**: `jl2642/investment-os-market-data`
- **Visibility**: `public`
- **Trade authority**: `NONE`

## 1. Architecture decision

The existing repository is the single GitHub repository for the Stock Investment Assistant. Responsibility separation is implemented through directory, manifest, schema and promotion boundaries rather than a second repository.

Top-level responsibility split:

```text
existing FMDL data, outputs, workflows and releases
investment_os_runtime/00_CONTROL
investment_os_runtime/10_CORE_STATIC
investment_os_runtime/20_SCHEMAS_AND_INTERFACES
investment_os_runtime/30_STATE_CURRENT
investment_os_runtime/40_EVIDENCE_AND_LINEAGE
investment_os_runtime/50_MARKET_CAPABILITY_BINDINGS
investment_os_runtime/60_OPERATIONS_AND_EVENT
investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION
investment_os_runtime/80_EXECUTABLE_RUNTIME
investment_os_runtime/90_RECOVERY_AND_ARCHIVE
```

## 2. Data Plane

The existing FMDL paths remain authoritative for:

- market identity and universe;
- daily and historical prices;
- factors and screening;
- financial and valuation evidence;
- Hong Kong Stock Connect and U.S. research adapters;
- data quality, manifests, immutable releases and LKG.

## 3. Investment OS runtime paths

`investment_os_runtime/` will own:

- CORE_STATIC and schemas;
- STATE_CURRENT and atomic mutation records;
- Research, Thesis, Candidate and Event Current;
- Decision proposals and user confirmations;
- operating-product candidates and accepted products;
- Control Runtime, tests, manifests and LKG;
- Master Plan and Execution Register.

## 4. Public-repository content boundary

Raw brokerage screenshots, account numbers, credentials, tokens, private keys and unrelated personal records are not committed because they are unnecessary for operation. Structured holdings, cost, Candidate and decision state may be committed under accepted schemas when required by the user-approved operating model.

## 5. Promotion rule

A data release may trigger review but may not silently mutate Investment OS state.

```text
accepted data release
→ data preflight
→ semantic-change check
→ research/state proposal
→ governed review
→ user confirmation where required
→ atomic state mutation
```

## 6. Permanent controls

- `trade_authority = NONE`;
- no automatic Candidate admission;
- no automatic simulation or real-account admission;
- no automatic rule mutation;
- no brokerage connection or order generation;
- conversation memory has no authority.
