# HKCU P4-4 Portfolio Proposal Review

## Purpose

P4-4 is the final Phase 4 closure gate. It reviews the nine accepted P4-3 scenarios and produces one bounded preferred portfolio proposal for REAL and one for SIMULATION. It does not create a target-position writeback or authorize execution.

This gate exists because P4-3 proved that multiple complete portfolio scenarios are feasible but deliberately did not choose among them. P4-4 makes that choice under explicit non-scoring rules and then closes Phase 4.

## Important planning correction

The Phase 4 numbering was not fully frozen when P4-0 opened. P4-0 explicitly named only P4-1; later gates introduced P4-2 and P4-3, and P4-3 first named `P4_4_PORTFOLIO_PROPOSAL_REVIEW`. Therefore P4-4 is a valid portfolio-governance function, but its numbering was introduced incrementally rather than being fixed at Phase-4 inception.

This document closes that planning gap: **a passing P4-4 closes Phase 4. No P4-5 or later P4 subphase is authorized.** The next layer is the higher-level Phase 5, `PHASE_5_PRETRADE_AND_STAGED_MIGRATION`.

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
- portfolio role;
- funding source;
- maximum historical drawdown loss estimate;
- candidate/portfolio and downside correlation;
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

## Accepted Canonical-input result

The first full Canonical-input P4-4 run on branch head `72683184e36eee3d32f5cf0ebb933fbcfdc1ce9e` completed successfully in workflow run `31254893569`.

- P4-1R, P4-1, P4-2 and P4-3 were rebuilt and independently validated from the PR base Canonical state.
- P4-4 status: `PASS_P4_4_PORTFOLIO_PROPOSAL_REVIEW`.
- independent validator: `PASS`, `errors=[]`.
- scenario reviews: 9/9.
- preferred proposals: 2.
- proposal allocations: 13.
- Phase closure: `PHASE_4_CLOSED`.
- next phase: `PHASE_5_PRETRADE_AND_STAGED_MIGRATION`.
- Candidate / REAL / SIMULATION mutations: 0.
- target writeback: false.
- Pre-trade Memo produced: false.
- user trade confirmation recorded: false.
- orders: 0.
- `trade_authority=NONE`.

### Accepted REAL preferred proposal

`REAL_CONSERVATIVE` proposes a 5% HK sleeve across four securities, subject to external-liquidity or separate-capital-decision funding:

- HKEX:03698 HUISHANG BANK: 1.7500%;
- HKEX:01308 SITC: 1.5855%;
- HKEX:02698 SOFTCARE: 0.6645%;
- HKEX:00669 TECHTRONIC IND: 1.0000%.

Aggregate historical 120-day drawdown stress weight is approximately 0.9501% of account assets. Median candidate/portfolio correlation is approximately 0.0572 and median downside correlation approximately -0.1195. `REAL_BALANCED` and `REAL_EXPANDED` remain alternatives rather than execution instructions.

### Accepted SIMULATION preferred proposal

`SIM_BALANCED` proposes a 15% HK observation sleeve across nine securities and fits within current simulation cash:

- HKEX:03698 HUISHANG BANK: 2.3700%;
- HKEX:01308 SITC: 1.7226%;
- HKEX:02698 SOFTCARE: 1.7921%;
- HKEX:00917 QUNABOX GROUP: 0.5938%;
- HKEX:00002 CLP HOLDINGS: 2.0000%;
- HKEX:00008 PCCW: 2.0000%;
- HKEX:00941 CHINA MOBILE: 2.0000%;
- HKEX:00003 HK & CHINA GAS: 0.7500%;
- HKEX:00001 CKH HOLDINGS: 1.7715%.

Aggregate historical 120-day drawdown stress weight is approximately 2.8849% of account assets. Median candidate/portfolio correlation is approximately 0.2331 and median downside correlation approximately 0.0071. This remains an observation proposal only; SIMULATION Current is not mutated by P4-4.

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

A clean final-head P4-4 PASS closes Phase 4 and advances only to `PHASE_5_PRETRADE_AND_STAGED_MIGRATION`. No P4-5 or later P4 subphase is authorized.
