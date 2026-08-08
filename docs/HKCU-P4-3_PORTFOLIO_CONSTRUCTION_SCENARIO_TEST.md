# HKCU P4-3 Portfolio Construction Scenario Test

## Purpose

P4-3 converts accepted P4-2 single-security analytical envelopes into complete hypothetical Hong Kong sleeve scenarios. It tests whether a portfolio can be assembled under aggregate constraints without turning the scenario into a target portfolio, trade instruction or state mutation.

## Entry

A valid run requires:

- P4-2 = `PASS_P4_2_PORTFOLIO_CONSTRUCTION_REVIEW`;
- 140 Account × Security construction-review rows;
- current REAL and SIMULATION position states;
- `trade_authority=NONE`.

The workflow rebuilds P4-1R, P4-1 and P4-2 from Canonical inputs before P4-3 runs.

## Scenario surface

REAL base scenarios:

- `REAL_CONSERVATIVE`: 5% HK sleeve;
- `REAL_BALANCED`: 10% HK sleeve;
- `REAL_EXPANDED`: 15% HK sleeve.

SIMULATION base scenarios:

- `SIM_CONSERVATIVE`: 10% HK sleeve;
- `SIM_BALANCED`: 15% HK sleeve;
- `SIM_EXPANDED`: 20% HK sleeve.

SIMULATION also runs three `MAX_AH_SUBSTITUTION_STRESS` variants at the same sleeve targets. These variants use the P4-2 replacement-equivalent caps for Midea H / CM Bank H or any later accepted exact-A/H substitution rows, require equal-weight reduction of the existing same-issuer A-share, and authorize zero net-new capital for the substitution leg.

## Allocation method

P4-3 does not use a weighted alpha score, fixed Top-N or Candidate rank as allocation authority.

Eligible P4-2 rows are consumed lexicographically by:

1. construction state: Primary → Secondary → Probe;
2. marginal-risk state: diversification improvement before higher risk contribution;
3. opportunity-cost state: low before moderate;
4. remaining P4-2 suggested maximum capacity;
5. security ID only as a deterministic tie-breaker.

A row can receive scenario weight only within its accepted P4-2 `suggested_weight_max`.

## Aggregate constraints

Every scenario must satisfy all of the following simultaneously:

- total HK sleeve does not exceed the scenario target;
- residual underfill is less than one minimum scenario position (0.5%);
- direct-sector total portfolio weight remains at or below 20%;
- direct-style total portfolio weight remains at or below 30%;
- no single sector exceeds 35% of the HK sleeve;
- no single style exceeds 45% of the HK sleeve;
- gross 120-day historical-drawdown stress is capped at 35% of the HK sleeve weight;
- each new position is at least 0.5%;
- exact A/H substitution is net-capital-neutral and cannot exceed the P4-2 replacement-equivalent cap or existing same-issuer exposure.

These are bounded scenario-test parameters, not permanent strategic asset-allocation targets.

## Funding semantics

REAL broker cash remains execution balance only and is not a strategic asset bucket. Because current REAL execution cash is zero, positive REAL new-build scenarios are classified as feasible only with an explicit external-liquidity or separate capital decision dependency. P4-3 does not auto-reduce any current holding to fund the scenario.

SIMULATION new-build legs may use current simulation cash. A SIMULATION scenario fails if its net-new build requirement exceeds available simulation cash.

A/H substitution legs are funded only by an equal-weight same-issuer A-share reduction in the hypothetical stress variant and do not consume net-new capital.

## Governance boundary

P4-3 may produce aggregate hypothetical scenario allocations for testing. It does not:

- choose a preferred scenario;
- create a portfolio proposal;
- write target positions;
- mutate Candidate membership;
- mutate REAL or SIMULATION current state;
- create a Pre-trade Memo;
- record user trade approval;
- create orders;
- grant trade authority.

`trade_authority=NONE` throughout.

A clean PASS advances only to `P4_4_PORTFOLIO_PROPOSAL_REVIEW`.
