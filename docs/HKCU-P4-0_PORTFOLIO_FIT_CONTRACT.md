# HKCU P4-0 Portfolio Fit Contract

## Objective

P4-0 opens HKCU Phase 4 by freezing the **Portfolio Fit Contract** that will govern how the 70 formal Hong Kong Candidate members are evaluated against the current Simulation and Real Account portfolios.

This gate defines rules only. It performs no security assessment, no sizing, no Candidate mutation, no Simulation admission, no Real Account admission, no allocation and no order creation.

## Authoritative entry

Phase 4 begins only from the accepted P3-2 Canonical surface:

- 70 formal ACTIVE Hong Kong Candidate members;
- 2 Core;
- 68 Watch;
- the exact `HK_CANDIDATE_CURRENT.csv` identity is pinned through the accepted P3-2 Manifest;
- P3-2 remains `trade_authority=NONE`.

The seven P3-2 nonmembers — Research Monitor and Blocker Monitor names — are not Phase-4 entry securities.

## Why Portfolio Fit is a separate gate

Candidate graduation answers whether a security is sufficiently investable to remain in the formal research opportunity set. It does **not** answer whether adding that security improves either portfolio now.

P4 therefore evaluates **marginal portfolio value**, not standalone company attractiveness.

A strong company can have no incremental portfolio role because the portfolio already owns the same issuer, an A/H equivalent, a highly overlapping sector/factor exposure, or a superior existing alternative. Conversely, a Watch-tier Candidate is not automatically excluded from portfolio review merely because it retains bounded research confidence caps.

Core is not automatic allocation. Watch is not automatic rejection.

## Two portfolio contexts must remain separate

P4-1 must produce an explicit fit state for both:

1. **Simulation** — current research/simulation book, including its actual available cash and current holdings;
2. **Real Account** — current user-confirmed economic positions and marks.

A security may fit one portfolio and not the other. P4 may not collapse the two into one generic score.

The current Canonical portfolio states are:

- `investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json`
- `investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json`

Both must be current, fully marked and fresh or explicitly acceptable at assessment time.

## Real Account cash semantics

The Real Account Current explicitly defines cash as:

`BROKER_EXECUTION_BALANCE_ONLY_EXTERNAL_LIQUIDITY_EXCLUDED`

Therefore P4 may **not** invent a fixed strategic cash target for the Real Account. External liquidity is outside the brokerage portfolio and may be transferred separately when the user decides to fund an action.

Simulation cash remains `SIMULATION_LEDGER_AVAILABLE_CASH` and can be used as funding context, but it is not alpha and cannot itself justify admission.

## Frozen Portfolio Fit rule families

P4-0 freezes 15 rules: 7 hard rules and 8 decision rules.

### Hard rules

A positive fit state requires every applicable hard rule to pass:

1. formal ACTIVE P3-2 Candidate lineage;
2. current investability and buy eligibility;
3. decision-grade market and valuation freshness;
4. current Real and Simulation portfolio state and marks;
5. live thesis with no triggered falsifier or new substantive blocker;
6. acceptable liquidity and execution capacity;
7. complete identity mapping for direct, A/H and economically duplicate exposure.

Missing hard-rule evidence fails closed. It is not neutral-filled.

### Decision rules

For each account, P4-1 must explicitly assess:

- intended portfolio role;
- direct and cross-listed overlap;
- sector and industry concentration;
- factor, style and thematic concentration;
- marginal diversification and downside co-movement;
- valuation, plausible expected return and opportunity cost versus existing holdings and other Candidates;
- downside budget and analytical sizing envelope;
- funding and cash semantics.

No weighted composite score, automatic waiver, neutral fill or arbitrary fixed Top-N is permitted.

## Account-specific fit states

Each security must receive one explicit state for Simulation and one for Real Account:

- `FIT`
- `FIT_WITH_CONSTRAINTS`
- `NO_INCREMENTAL_ROLE`
- `DEFER_PORTFOLIO_CONTEXT`
- `BLOCK_PORTFOLIO_FIT`

`NO_INCREMENTAL_ROLE` is not a bearish company rejection. It means the security may remain a valid Candidate while adding insufficient marginal portfolio value at the current portfolio state.

`DEFER_PORTFOLIO_CONTEXT` is required where decision-critical exposure, price, portfolio or classification context is missing or stale.

`BLOCK_PORTFOLIO_FIT` requires a substantive investment or portfolio-level blocker; it may not be used merely to force a smaller list.

## Combined routing states

The two account-specific states are then routed, without portfolio mutation, to one of:

- `ADVANCE_DUAL_CONSTRUCTION_REVIEW`
- `ADVANCE_SIMULATION_CONSTRUCTION_REVIEW`
- `ADVANCE_REAL_ACCOUNT_REVIEW`
- `HOLD_PORTFOLIO_WATCH`
- `DEFER_PORTFOLIO_CONTEXT`
- `BLOCK_PORTFOLIO_FIT`

These are review routes only. They are not admissions, target weights or orders.

## Duplicate and A/H exposure discipline

P4 must identify existing direct and economically duplicate exposures before claiming diversification.

Where an A/H pair or same-issuer exposure exists, the assessment must state whether a proposed H-share position would add, substitute or duplicate the existing exposure. A/H discount or premium remains valuation context, not alpha.

Duplicate exposure is not automatically prohibited; it must be economically justified.

## Sizing boundary

P4-1 may state an **analytical sizing envelope** because concentration, liquidity and downside cannot be evaluated without an order-of-magnitude exposure assumption.

That envelope is not a portfolio mutation. No quantity, target weight, Simulation position or Real Account position may be changed in P4-0 or P4-1.

Construction or admission requires a separate later gate.

## Reassessment triggers

Portfolio fit must be reassessed when relevant current state changes, including:

- Candidate or Southbound eligibility changes;
- stale price/valuation inputs;
- Real or Simulation position updates;
- user-confirmed position deltas;
- new direct/A-H duplicate exposure;
- material sector/style/theme concentration changes;
- liquidity deterioration;
- thesis falsifier or new investment blocker;
- material invalidation of valuation support.

Every fit-state change must be logged. `trade_authority=NONE` remains unchanged.

## P4-0 acceptance boundary

P4-0 passes only if the contract is bound to accepted P3-2 Candidate Current, the current Real and Simulation states are valid portfolio-fit inputs, the 15-rule registry and routing vocabulary are complete, and all investment-state mutation authorities remain disabled.

Expected exit:

`PASS_P4_0_PORTFOLIO_FIT_CONTRACT`

Next gate:

`P4_1_PORTFOLIO_FIT_ASSESSMENT`
