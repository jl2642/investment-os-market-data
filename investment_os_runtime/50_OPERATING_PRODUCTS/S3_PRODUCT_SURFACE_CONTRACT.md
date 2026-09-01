# S3｜Portfolio + Product Surface Simplification Contract

Status: CURRENT  
Authority: `investment_os_runtime/00_CONTROL/SYSTEM_CURRENT.json`  
Canonical workflow: `.github/workflows/s3-portfolio-product-surface.yml`

## 1. Purpose

S3 removes the remaining product-layer identity mismatch after S2.

The current investment chain is:

`Market/Screening → Opportunity → D1 → D2 Underwriting → Capital Comparison → Recommendation → Portfolio/Product Surface → Human Decision`

S3 does not create another investment engine. It provides one governed read layer over current position identity, current marks and S2 outputs.

## 2. Canonical user products

Only two products are current user-facing operating surfaces:

1. **DAILY_INVESTMENT_BRIEF**
   - what changed;
   - current-position actions supported by S2 underwriting;
   - new-capital opportunities;
   - current D1/D2 research queue;
   - blockers and the next human review step.

2. **PORTFOLIO_DECISION_SURFACE**
   - machine-readable source for the brief;
   - explicitly separates existing-position decisions, new-capital opportunities and uncovered holdings;
   - continuously maintains Real/Simulation performance monitoring for every current account holding line;
   - distinguishes mechanical performance-monitoring coverage from decision-grade recommendation coverage;
   - maintains a bounded holding reunderwriting queue for uncovered positions;
   - preserves source bindings and safety controls.

The historical R3 Decision Pack, R4 seven-product development catalog and WP5 portfolio decision artifacts remain auditable development evidence only. They are not current operating authority.

## 3. Inputs

S3 may read only governed current inputs:

- `PORTFOLIO_MARKS` Operating Current;
- real-account and simulation position identity restored from the accepted Portfolio Marks source commit;
- S2 `INVESTMENT_PIPELINE` Operating Current;
- S2 `RECOMMENDATION_CURRENT.json`;
- S2 `D1_CURRENT.json`.

If a current holding has no S2 recommendation, S3 must show:

`NO_CURRENT_S2_RECOMMENDATION`

It must not reuse a stale R3/WP5 action as a substitute. The holding still remains fully present in mechanical portfolio monitoring. Missing D2/Recommendation coverage becomes an explicit reunderwriting backlog rather than a monitoring gap.

## 4. Portfolio semantics

S3 is a **decision and monitoring surface, not a target-weight engine**.

It continuously maintains current Real/Simulation performance facts including current marks, market value, unrealized P&L, account weight and monitoring flags. These mechanical facts do not constitute an investment action.

The two coverage metrics are intentionally separate:

- performance monitoring coverage should include every current Real/Simulation holding line;
- investment recommendation coverage includes only securities with current decision-grade S2 output.

Uncovered positions are prioritized into a bounded reunderwriting queue using mechanical risk/materiality signals such as drawdown and account concentration. Queue placement is a research priority, not an action recommendation.

It must not:

- create target weights or automatic rebalance instructions;
- infer a transaction from portfolio drift;
- mutate Candidate membership;
- mutate real-account holdings, quantity, cost or cash;
- mutate simulation holdings, quantity, cost or cash;
- create user decisions;
- create broker orders.

`ready_for_user_decision=true` means **review-worthy current recommendation**, not execution authority.

## 5. Refresh semantics

The S3 workflow is recalculated when either of its economic read inputs changes materially:

- successful S2 Investment Pipeline completion; or
- successful Portfolio Marks refresh.

The product surface is published to the append-only `operating-current` branch under:

- `operating_current/product_surface/PORTFOLIO_DECISION_SURFACE_CURRENT.json`
- `operating_current/product_surface/DAILY_INVESTMENT_BRIEF_CURRENT.md`
- domain: `PORTFOLIO_PRODUCT_SURFACE`.

Duplicate semantic surfaces publish NO_OP rather than rewriting Current.

## 6. Retirements

`.github/workflows/occ-r4-portfolio-decision-freshness.yml` is retired from automatic production because it binds the obsolete P4-3 recommendation to the stale WP5 action matrix.

S3 does not retire unrelated Candidate, cross-market, valuation, trigger/shadow or forward-validation runtime merely for cleanup. Remaining hygiene and natural-chain acceptance belong to S4.

## 7. Acceptance boundary

S3 deterministic acceptance requires:

- one canonical portfolio/product producer;
- exactly two canonical user products;
- S2 recommendation actions preserved without orphan legacy gates;
- existing holdings, new opportunities and uncovered holdings explicitly separated;
- every current Real/Simulation holding line mechanically monitored for performance;
- performance-monitoring coverage reported separately from investment-recommendation coverage;
- uncovered holdings produce a bounded reunderwriting queue without fabricated actions;
- no stale R3/R4/WP5 action promoted to current;
- protected economic mutations = 0;
- orders = 0;
- trade_authority = NONE.

Natural end-to-end runtime acceptance is intentionally deferred to **S4**.

S3 passing deterministic tests does not by itself prove that a fresh natural market cycle has traversed the entire system.

