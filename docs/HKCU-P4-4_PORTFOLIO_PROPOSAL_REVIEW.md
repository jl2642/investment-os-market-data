# HKCU P4-4 Portfolio Proposal Review

## Purpose

P4-4 is the final Phase 4 closure gate. It reviews the nine accepted P4-3 scenarios and produces one bounded preferred portfolio proposal for REAL and one for SIMULATION. It does not create a target-position writeback or authorize execution.

This gate exists because P4-3 proved that multiple complete portfolio scenarios are feasible but deliberately did not choose among them. P4-4 makes that choice under explicit non-scoring rules and then closes Phase 4.

## Important planning correction

The Phase 4 numbering was not fully frozen when P4-0 opened. P4-0 explicitly named only P4-1; later gates introduced P4-2 and P4-3, and P4-3 first named `P4_4_PORTFOLIO_PROPOSAL_REVIEW`. Therefore P4-4 is a valid portfolio-governance function, but its numbering was introduced incrementally rather than being fixed at Phase-4 inception.

This document closes that planning gap: **a passing P4-4 closes Phase 4. No P4-5 or later P4 subphase is authorized.** The next layer is the already intended higher-level Phase 5, `PHASE_5_PRETRADE_AND_STAGED_MIGRATION`.

## Proposal rules

P4-4 does not use a weighted score, fixed Top-N or Candidate rank as proposal authority.

### REAL

All three passing REAL scenarios require external liquidity or a separate capital decision. P4-3 contains no scenario-specific incremental-return evidence demonstrating that immediate 10% or 15% deployment is superior to 5%.

Therefore the initial REAL proposal follows the CORE_STATIC staged-capital-migration principle:

- preferred: `REAL_CONSERVATIVE` (5% HK sleeve);
- conditional expansion alternative: `REAL_BALANCED` (10%);
- hold expansion at current evidence: `REAL_EXPANDED` (15%).

This is a capital-at-risk and evidence decision, not a claim that the 5% portfolio has the highest expected return.

### SIMULATION

The simulation account is an observation and learning surface. `SIM_BALANCED` is fully funded, passes all P4-3 aggregate risk constraints and expands breadth without immediately using the maximum tested sleeve.

Therefore:

- preferred observation proposal: `SIM_BALANCED` (15% HK sleeve);
- conservative alternative: `SIM_CONSERVATIVE` (10%);
- conditional expanded alternative: `SIM_EXPANDED` (20%).

This is not an expected-return ranking. The expanded scenario remains useful for broader stress/learning but is not the default proposal.

### A/H substitution

All `MAX_AH_SUBSTITUTION_STRESS` scenarios remain `RESEARCH_ONLY_AH_SUBSTITUTION`. P4-3 proved implementation feasibility and net-capital neutrality, but accepted governance explicitly says A/H relative value is context rather than alpha. No Midea A/H or CMB A/H replacement is promoted into a preferred proposal without a separate relative-value evidence review.

## Required proposal fields

Every preferred proposal must preserve the CORE_STATIC portfolio-decision surface:

- current weight;
- proposed weight;
- funding source;
- maximum historical drawdown loss estimate;
- candidate/portfolio and downside correlation where available;
- sector/style Look-through;
- explicit alternative scenario;
- principal falsifier and review trigger at security level;
- exit/hold condition;
- initial analytical review date.

The initial review date is 2026-09-07. It is a review checkpoint only; it does not schedule or authorize any trade.

## Decision / permission / execution separation

REAL preferred proposal:

- `decision=BUY_PROPOSAL`;
- `permission=RESEARCH_ONLY`;
- `execution_status=NOT_AUTHORIZED_FOR_EXECUTION`.

SIMULATION preferred proposal:

- `decision=RESEARCH`;
- `permission=RESEARCH_ONLY`;
- `execution_status=NOT_AUTHORIZED_FOR_STATE_MUTATION`.

A REAL proposal can enter Phase 5 Pre-trade Memo preparation only. A technical PASS is not user approval and is not execution authority.

## Governance boundary

P4-4 may produce portfolio proposals and classify alternatives. It does not:

- write target positions into Current;
- mutate Candidate membership;
- mutate REAL or SIMULATION Current;
- create a Pre-trade Memo;
- record user approval;
- create broker orders;
- infer execution;
- grant trade authority.

`trade_authority=NONE` throughout.

A clean P4-4 PASS closes Phase 4 and advances only to `PHASE_5_PRETRADE_AND_STAGED_MIGRATION`.
