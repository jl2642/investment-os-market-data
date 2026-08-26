# Strategy Kernel v2 — Overall Development Roadmap

## Governance rule: the plan is a controlled development object
Any change to phase order, scope, dependencies, acceptance criteria, or economic/authority boundaries MUST update this roadmap, `PHASE_EXECUTION_PLAN.md`, `PLAN_CHANGELOG.md`, and `CURRENT_PHASE_STATUS.json` in the same governed change-set as implementation.

Hard boundaries throughout development: no live trading, no order creation, no automatic Candidate membership/tier mutation, no Real or Simulation economic mutation, no target-portfolio writeback, `orders=0`, `trade_authority=NONE`.

## Roadmap
1. **Phase 0B — Current-main rule audit — COMPLETE**.
2. **Phase 1B — Decision Object v2 shadow adapter — COMPLETE / draft PR #298**.
3. **Phase 1C — Underwriting Extraction — VALIDATED SHADOW-ONLY / draft PR #299**.
4. **Phase 2 — Shadow Capital Comparator — IN DEVELOPMENT, research-only**.
   - **2A Comparator Contract / Engine — VALIDATED SHADOW-ONLY / draft PR #300**: transparent multi-dimensional vectors plus Pareto frontier; no unvalidated scalar score.
   - **2B Governed Refresh Adapters — VALIDATED SHADOW-ONLY**: refresh packets require explicit governed provenance. `READY_AFTER_REFRESH` needs exact requirement coverage; `NOT_READY` cannot be cured by price/valuation alone and needs a full fundamental re-underwrite resolving all material gaps. Decision readiness and Canonical authority are preserved.
   - **2C Current Shadow Comparison Pack — NEXT / GATED**: source real current governed refresh packets, then compare only eligible assets. `NO_COMPARISON` remains valid if evidence/freshness gates are unsatisfied.
5. **Phase 3 — Point-in-time replay and calibration — MANDATORY before effective policy migration**: compare false negatives, false positives, turnover, downside, forecast calibration and opportunity-cost regret; test any future scalar utility/sizing policy here, not in Phase 2.
6. **Effective Strategy/Core migration — NOT STARTED**: separate governed approval only after Phase 3.

## Architectural rule
Phase 2 separates **measurement, evidence refresh and policy**. A shadow comparison result cannot create Candidate membership, a user decision, a target weight, an order or a trade.
