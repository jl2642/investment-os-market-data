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
4. **Phase 2 — Shadow Capital Comparator — IN DEVELOPMENT, research-only**
   - **2A Comparator Contract / Engine — VALIDATED SHADOW-ONLY**: transparent multi-dimensional vectors plus Pareto frontier; no unvalidated scalar score.
   - **2B Governed Refresh Adapters — NEXT**: satisfy per-object freshness requirements only with explicit governed provenance; `NOT_READY` material evidence gaps cannot be cured by price refresh alone.
   - **2C Current Shadow Comparison Pack — GATED**: compare only eligible positions/candidates/reference assets; `NO_COMPARISON` is a valid output when refresh/evidence gates remain unsatisfied.
5. **Phase 3 — Point-in-time replay and calibration — MANDATORY before effective policy migration**
   - Compare legacy vs v2 false negatives, false positives, turnover, downside, forecast calibration and opportunity-cost regret using information available at the historical point in time.
   - Test whether any candidate scalar utility/position-sizing policy improves decisions before such weights can enter Strategy Kernel policy.
6. **Effective Strategy/Core migration — NOT STARTED**
   - May be considered only after Phase 3 and a separate governed approval.

## Phase 2 architectural rule
Phase 2 separates **measurement from policy**. Phase 2A measures expected return, downside, probability of loss, confidence, concentration cost and execution friction, and exposes Pareto dominance. It does not assign a one-number investment score because those utility weights are themselves hypotheses requiring Phase 3 calibration.

Passing a shadow comparison gate never authorizes a Candidate mutation, portfolio mutation, user decision, order, or trade.
