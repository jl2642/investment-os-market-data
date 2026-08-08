# HKCU P4-1 Portfolio Fit Reassessment

## Purpose

This gate re-executes the frozen P4-0 Portfolio Fit framework after P4-1R closed the decision-critical context gaps that forced the first P4-1 run to fail closed.

The reassessment evaluates the same 70 formal active Hong Kong Candidates separately against REAL and SIMULATION. It materializes the same 15 P4-0 rules for every Account×Security pair, but P4R07 through P4R13 now consume the accepted P4-1R runtime context rather than hard-coded missing-context deferrals.

## Entry

The transaction requires a fresh runtime rebuild of P4-1R and independently validates it before reassessment. A positive reassessment requires:

- P4-1R status `PASS_P4_1R_PORTFOLIO_CONTEXT_COMPLETION`;
- 70 Candidate context rows;
- 24 current holding context rows;
- 140 Account×Security context rows;
- 140/140 context-ready rows;
- 70/70 Candidate industry coverage;
- 13/13 exact A/H mappings;
- zero P4-1R residual decision-critical gaps;
- `trade_authority=NONE`.

If this runtime context gate fails, reassessment routes back to P4-1R rather than neutral-filling missing evidence.

## Reassessment semantics

The original P4-0 hard rules remain binding. Candidate lineage, current investability, decision-grade market/valuation freshness, current portfolio state, thesis/falsifier presence, liquidity/capacity and exposure-identity completeness must all pass before a positive or `NO_INCREMENTAL_ROLE` account state can be issued.

The decision rules use the accepted P4-1R evidence surface:

- P4R08: explicit portfolio role from common style context;
- P4R09: direct and exact A/H overlap review, while pooled vehicles remain explicit review context rather than candidate-specific duplicate evidence merely because a pooled vehicle exists;
- P4R10: marginal direct-sector concentration impact;
- P4R11: marginal style concentration impact;
- P4R12: correlation, downside correlation, volatility and governed marginal-risk state;
- P4R13: unweighted Pareto opportunity-cost context using accepted valuation anchor, trailing return and drawdown semantics;
- P4R14: analytical no-size or construction-review-only envelope; no numeric target weight is authorized;
- P4R15: REAL broker cash and SIMULATION cash semantics remain unchanged.

Three governance-wide facts are deliberately not treated as security-specific fit constraints: numeric sizing belongs to the later construction gate, REAL funding can be decided separately from current broker cash because external liquidity is excluded from the portfolio-fit cash target, and generic pooled-vehicle presence does not by itself prove economic duplication with a particular Candidate. These facts remain recorded in rule evidence and phase boundaries.

## `NO_INCREMENTAL_ROLE`

`NO_INCREMENTAL_ROLE` is a portfolio-role conclusion, not a bearish company rejection and not Candidate removal.

It is issued in two bounded cases:

1. the exact security is already held in the account and no incremental role is demonstrated at this gate; or
2. for a non-direct holding, accepted evidence jointly shows all four of: `HIGH_RELATIVE_OPPORTUNITY_COST`, `INCREASES_EXISTING_DIRECT_SECTOR`, `INCREASES_EXISTING_STYLE`, and a marginal-risk state other than `IMPROVES_DIVERSIFICATION`.

The fourth condition prevents opportunity cost or concentration alone from becoming an automatic rejection. Conversely, the test does not require the narrowest `ADDS_CORRELATED_RISK` label if the accepted marginal-risk evidence is mixed or raises the risk budget and therefore does not affirmatively improve diversification.

No weighted score or fixed Top-N is used to create this state.

Exact A/H overlap remains a named substitution/duplication constraint. Pooled ETF/fund exposure remains visible as portfolio context but is not called a duplicate-exposure constraint without security-specific evidence.

## Routing

REAL and SIMULATION fit states remain separate and are combined only through the frozen route vocabulary:

- `ADVANCE_DUAL_CONSTRUCTION_REVIEW`
- `ADVANCE_REAL_ACCOUNT_REVIEW`
- `ADVANCE_SIMULATION_CONSTRUCTION_REVIEW`
- `HOLD_PORTFOLIO_WATCH`
- `DEFER_PORTFOLIO_CONTEXT`
- `BLOCK_PORTFOLIO_FIT`

A clean PASS advances to `P4_2_PORTFOLIO_CONSTRUCTION_REVIEW`.

## Governance boundary

This transaction is assessment-only. It does not:

- change the 70-member Candidate pool;
- admit or remove Simulation positions;
- change Real Account positions;
- set numeric target weights;
- allocate capital;
- create orders;
- change cash policy;
- grant trade authority.

`trade_authority=NONE` throughout.
