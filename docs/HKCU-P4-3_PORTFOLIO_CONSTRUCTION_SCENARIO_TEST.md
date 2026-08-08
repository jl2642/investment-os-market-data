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

SIMULATION new-build legs may use current simulation cash. The accepted current simulation cash weight is approximately 23.85%, and all tested SIMULATION scenarios remain within that funding context with zero funding gap.

A/H substitution legs are funded only by an equal-weight same-issuer A-share reduction in the hypothetical stress variant and do not consume net-new capital.

## Accepted Canonical-input result

The first clean Canonical rerun produced 9/9 scenario PASS, 70 scenario-allocation rows, two accepted A/H substitution options, zero integrity errors, zero state mutations and zero orders.

| Scenario | HK sleeve target | Allocated | Positions | Gross drawdown stress | Funding result |
| --- | ---: | ---: | ---: | ---: | --- |
| REAL_CONSERVATIVE | 5.00% | 5.00% | 4 | 0.9501% | External funding dependency |
| REAL_BALANCED | 10.00% | 10.00% | 5 | 2.2312% | External funding dependency |
| REAL_EXPANDED | 15.00% | 15.00% | 7 | 3.6073% | External funding dependency |
| SIM_CONSERVATIVE | 10.00% | 10.00% | 6 | 2.1349% | Simulation cash, zero gap |
| SIM_BALANCED | 15.00% | 15.00% | 9 | 2.8849% | Simulation cash, zero gap |
| SIM_EXPANDED | 20.00% | 20.00% | 12 | 3.6349% | Simulation cash, zero gap |
| SIM_CONSERVATIVE_AH_STRESS | 10.00% | 10.00% | 7 | 2.1245% | Simulation cash, zero gap |
| SIM_BALANCED_AH_STRESS | 15.00% | 14.5265% | 8 | 2.8461% | Simulation cash, zero gap |
| SIM_EXPANDED_AH_STRESS | 20.00% | 20.00% | 12 | 3.6672% | Simulation cash, zero gap |

`SIM_BALANCED_AH_STRESS` intentionally remains 0.4735% below its nominal 15% target. This is a valid PASS because the residual is below the 0.5% minimum scenario-position threshold; P4-3 does not create a sub-minimum filler position merely to report an exact target.

### REAL scenario composition

The REAL scenarios expand from 4 to 5 to 7 names rather than mechanically distributing weight across all 49 actionable REAL rows.

- 5% Conservative: Huishang Bank, SITC, Softcare and Techtronic Industries.
- 10% Balanced: Huishang Bank, SITC, Softcare, Lonking and Techtronic Industries.
- 15% Expanded: Huishang Bank, SITC, China Taiping, Softcare, Lonking, Lee & Man Paper and Techtronic Industries.

At 15%, the largest HK-sleeve sector weight is approximately 4.53% of total account assets and the largest style weight is 6.75%, both within the scenario constraints. P4-3 does not infer that the 15% Expanded scenario is preferable to the 5% or 10% scenario.

### SIMULATION base scenarios

The base scenarios expand from 6 to 9 to 12 names. The 20% Expanded scenario includes Huishang Bank, SITC, Softcare, Qunabox, CLP, PCCW, China Mobile, HK & China Gas, Power Assets, CKH, Swire Pacific A and CCB. The scenario remains fully funded by current simulation cash and stays inside accepted sector/style and stress constraints.

### Exact A/H stress variants

Every A/H stress scenario tests both accepted P4-2 substitution options at their replacement-equivalent caps:

- Midea H 00300: 1.8771%, paired with an equal 1.8771% hypothetical reduction of `000333.SZ`;
- CM Bank H 03968: 2.1709%, paired with an equal 2.1709% hypothetical reduction of `600036.SH`.

Total tested H-share substitution weight is approximately 4.0480%. Net-new capital from the substitution legs is exactly zero. These are scenario stress tests only, not a recommendation to replace either A-share holding.

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

A clean final-head PASS advances only to `P4_4_PORTFOLIO_PROPOSAL_REVIEW`.
