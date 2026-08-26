# Strategy Kernel v2 — Overall Development Roadmap

## Governance rule: the plan is a controlled development object
Any change to phase order, scope, dependencies, acceptance criteria, or economic/authority boundaries MUST update this roadmap, `PHASE_EXECUTION_PLAN.md`, `PLAN_CHANGELOG.md`, and `CURRENT_PHASE_STATUS.json` in the same governed change-set (branch/PR) as the implementation change. Implementation may not advance while plan documents lag.

Hard boundaries throughout development: no live trading, no order creation, no automatic Candidate membership/tier mutation, no Real or Simulation economic mutation, no target-portfolio writeback, `orders=0`, `trade_authority=NONE`.

## Roadmap
1. **Phase 0B — Current-main rule audit — COMPLETE**
   - Inventory existing Core Static semantics and separate investment principles from research controls, portfolio discipline, execution/data safety, and governance.
2. **Phase 1B — Decision Object v2 shadow adapter — COMPLETE / draft PR #298**
   - Normalize existing Canonical decision states without changing effective policy.
3. **Phase 1C — Underwriting Extraction — VALIDATED SHADOW-ONLY / draft PR #299**
   - Extract existing Canonical issuer research into a common Underwriting Object.
   - Unknown or missing evidence remains explicit; no research or valuation is synthesized merely to complete a schema.
4. **Phase 2 — Shadow Capital Comparator — COMPLETE AS SHADOW INFRASTRUCTURE, current pack = NO_COMPARISON**
   - **2A Comparator Contract / Engine — VALIDATED SHADOW-ONLY / draft PR #300**: transparent multi-dimensional vectors plus Pareto frontier; no unvalidated scalar score. Current Phase 1C baseline returned 0 eligible / 8 blocked absent governed refresh.
   - **2B Governed Refresh Adapters — VALIDATED SHADOW-ONLY / draft PR #301**: exact governed refresh coverage; `NOT_READY` cannot be cured by price/valuation alone and source decision readiness remains unchanged.
   - **2C Current Shadow Comparison Pack — VALIDATED COMPLETE / NO_COMPARISON**: actual main + newer governed production evidence was inventoried for all eight objects. Fresh 2026-08-25 A-share market marks exist for part of the set, but zero objects satisfy the full Phase 2B refresh plus Phase 2A probabilistic-comparison input contract without adding new assumptions. Zero real refresh packets were fabricated/applied; the correct current output is `NO_COMPARISON`.
5. **Phase 3 — Point-in-time replay and calibration — NEXT / MANDATORY before effective policy migration**
   - Compare legacy vs v2 false negatives, false positives, turnover, downside, forecast calibration and opportunity-cost regret using information available at each historical point.
   - Explicitly test whether probability-weighted underwriting, confidence representation, relative capital comparison, candidate utility/sizing policies, or simpler non-probabilistic alternatives improve decisions.
   - The Phase 2C inability to form a current comparison is an empirical input to Phase 3, not proof that a particular new policy should be hard-coded.
6. **Effective Strategy/Core migration — NOT STARTED**
   - May be considered only after Phase 3 and a separate governed approval.

## Phase 2 architectural rule
Phase 2 separates **measurement, governed evidence refresh and policy**. Phase 2A measures expected return, downside, probability of loss, confidence, concentration cost and execution friction and exposes Pareto dominance. Phase 2B governs how new evidence can make an object comparison-ready without mutating the source decision state. Phase 2C proved that fresh market prices alone do not make the current research set economically comparable under this contract.

Passing a shadow comparison gate never authorizes a Candidate mutation, portfolio mutation, user decision, order or trade.
