# Investment OS Runtime Repository Boundary

- **Status**: `WP1_5A_CONTROL_FOUNDATION_CANDIDATE`
- **Date**: 2026-07-24
- **Data repository**: `jl2642/investment-os-market-data`
- **Target runtime repository**: `jl2642/investment-os-runtime` (`PRIVATE`, creation pending)
- **Trade authority**: `NONE`

## 1. Data repository authority

`jl2642/investment-os-market-data` is the authoritative **Data Plane**. It owns:

- market identity and universe;
- daily and historical prices;
- factors and screening;
- financial and valuation evidence;
- Hong Kong Stock Connect and U.S. research adapters;
- data quality, manifests, immutable releases and LKG.

It must not own:

- real-account positions or transactions;
- simulation positions or transactions;
- final Candidate membership;
- user liquidity outside the securities account;
- position sizing or capital migration;
- user trade confirmation;
- order execution.

## 2. Runtime repository authority

`jl2642/investment-os-runtime` will be the authoritative **Rule, State, Research, Decision and Operations Plane**. It will own:

- CORE_STATIC and schemas;
- STATE_CURRENT and atomic mutation ledger;
- Research, Thesis, Candidate and Event Current;
- Decision proposals and user confirmations;
- operating-product candidates and accepted products;
- Control Runtime, tests, manifests and LKG;
- Master Plan and Execution Register.

The runtime repository must remain private before any state migration.

## 3. Cross-repository rule

A new data release may trigger review, but it may not silently mutate Investment OS state.

```text
Accepted data release
→ data preflight
→ semantic-change check
→ research/state proposal
→ governed review
→ user confirmation where required
→ atomic state mutation
```

## 4. Permanent boundaries

- `trade_authority = NONE`
- no automatic Candidate admission;
- no automatic simulation or real-account admission;
- no automatic rule mutation;
- no brokerage connection or order generation;
- conversation memory has no authority.
