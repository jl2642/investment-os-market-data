# Strategy Kernel v2 — Overall Development Roadmap

## Governance rule: the plan is a controlled development object
Any change to phase order, scope, dependencies, acceptance criteria, or economic/authority boundaries MUST update this roadmap, `PHASE_EXECUTION_PLAN.md`, `PLAN_CHANGELOG.md`, and `CURRENT_PHASE_STATUS.json` in the same governed change-set (branch/PR) as the implementation change. Implementation may not advance while plan documents lag.

Hard boundaries throughout development: no live trading, no order creation, no automatic Candidate membership/tier mutation, no Real or Simulation economic mutation, no target-portfolio writeback, `orders=0`, `trade_authority=NONE`.

## Roadmap
1. **Phase 0B — Current-main rule audit — COMPLETE**
   - Inventory existing Core Static semantics and separate investment principles from research controls, portfolio discipline, execution/data safety, and governance.
2. **Phase 1B — Decision Object v2 shadow adapter — COMPLETE / stacked base PR #298**
   - Normalize existing Canonical decision states without changing effective policy.
3. **Phase 1C — Underwriting Extraction — IMPLEMENTED SHADOW-ONLY**
   - Extract existing Canonical issuer research into a common Underwriting Object.
   - Unknown or missing evidence remains explicit; no research or valuation is synthesized merely to complete a schema.
4. **Phase 2 — Shadow Capital Comparator — NEXT, gated**
   - Compare capital uses only after each input passes the pre-comparison refresh gate.
   - The gate requires a sufficiently current completed-close valuation anchor and any issuer-specific refresh explicitly required by Phase 1C.
   - Shadow comparison eligibility is distinct from user-decision readiness and implementation readiness.
5. **Phase 3 — Point-in-time replay and calibration — MANDATORY before effective policy migration**
   - Compare legacy vs v2 false negatives, false positives, turnover, downside, and opportunity-cost regret using information available at the historical point in time.
6. **Effective Strategy/Core migration — NOT STARTED**
   - May be considered only after Phase 3 and a separate governed approval.

## Phase 1C architectural clarification
Phase 1C separates three concepts that were previously easy to conflate:
- **underwriting completeness** — whether issuer economics and risks are sufficiently understood;
- **shadow comparison readiness** — whether the object can enter a research-only relative capital comparison after required freshness gates;
- **decision/implementation readiness** — whether a user action can be requested or executed.

Passing a shadow comparison gate never authorizes a Candidate mutation, portfolio mutation, order, or trade.
