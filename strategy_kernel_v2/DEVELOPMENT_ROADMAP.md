# Strategy Kernel v2 — Overall Development Roadmap

## Master-program authority
`MASTER_PROGRAM_CHARTER.md` and `PROGRAM_CONTRACT.json` define the macro lifecycle. This roadmap expands that lifecycle; it may not silently delete, reorder, bypass, or reinterpret a macro phase. Any macro lifecycle change requires an explicit governed `PROGRAM_AMENDMENT` with rationale and impact assessment.

## Governance rule: the plan is a controlled development object
Any change to phase order, scope, dependencies, acceptance criteria, model-evaluation target, or economic/authority boundaries MUST update `MASTER_PROGRAM_CHARTER.md`, `PROGRAM_CONTRACT.json`, `PROGRAM_STATE.json`, this roadmap, `PHASE_EXECUTION_PLAN.md`, `PLAN_CHANGELOG.md`, and `CURRENT_PHASE_STATUS.json` in the same governed change-set. `program_consistency.py` must pass before implementation advances.

Hard boundaries through Phase 4: no live trading, no order creation, no automatic Candidate membership/tier mutation, no Real or Simulation economic mutation, no target-portfolio writeback, `orders=0`, `trade_authority=NONE`.

## Macro roadmap

### Phase 0 — System Audit — COMPLETE
- **0B Current-main rule audit — COMPLETE.**
- Inventory existing Core Static semantics and separate investment principles from research controls, portfolio discipline, execution/data safety, and governance.
- Preserve Legacy as the baseline to be tested rather than assuming its gates are either correct or too restrictive.

### Phase 1 — Decision & Underwriting Layer — COMPLETE SHADOW
- **1B Decision Object v2 shadow adapter — COMPLETE / draft PR #298.**
  - Normalize existing Canonical decision states without changing effective policy.
  - Preserve 601138 accepted NO_TRADE semantics, HKEX:00669 price-band-as-research-trigger semantics, and 605090 concentration as a diagnostic rather than an automatic sell signal.
- **1C Underwriting Extraction — VALIDATED SHADOW-ONLY / draft PR #299.**
  - Extract existing Canonical issuer research into a common Underwriting Object.
  - Unknown or missing evidence remains explicit; no research, valuation, scenario probability, or confidence is synthesized merely to complete a schema.

### Phase 2 — Capital Comparison Infrastructure — COMPLETE SHADOW / GOVERNED REVIEW PENDING
- **2A Comparator Contract / Engine — VALIDATED SHADOW-ONLY / draft PR #300.**
  - Transparent multi-dimensional vectors plus Pareto frontier; no unvalidated scalar score.
  - Expected return, downside, probability of loss, confidence, concentration cost and execution friction remain measurement fields, not effective policy weights.
  - Current Phase 1C baseline returned 0 eligible / 8 blocked absent governed refresh.
- **2B Governed Refresh Adapters — VALIDATED SHADOW-ONLY / draft PR #301.**
  - Exact governed refresh coverage is required.
  - `NOT_READY` cannot be cured by price/valuation alone; material fundamental gaps require governed fundamental re-underwrite.
  - Source decision readiness and Canonical authority remain unchanged.
- **2C Current Shadow Comparison Pack — VALIDATED COMPLETE / draft PR #302 / current pack `NO_COMPARISON`.**
  - Actual main + newer governed production evidence was inventoried for all eight objects.
  - Fresh 2026-08-25 A-share market marks exist for part of the set, but zero objects satisfy the full Phase 2B refresh plus Phase 2A probabilistic-comparison input contract without adding new assumptions.
  - Zero real refresh packets were fabricated/applied; 0 eligible / 8 blocked; no ranking manufactured.

### Phase 3 — Historical Replay & Calibration — NEXT / NOT STARTED
Mandatory point-in-time validation before any forward promotion. Phase 3 tests model form as well as parameters; strong historical results do not authorize effective migration.

Planned internal steps:
- **3A Point-in-time Evidence Ledger:** reconstruct exactly what research, market, portfolio and decision evidence was available at each historical decision date; prohibit hindsight and retrospective backfill without contemporaneous provenance.
- **3B Competing Model Forms:** replay the Legacy baseline, Phase-2 probabilistic/vector architecture, and at least one simpler non-probabilistic/Pareto alternative on identical information and opportunity sets.
- **3C Decision / Capital Replay:** compare shadow capital priorities, excluded opportunities, retained opportunities and rationale using only contemporaneous evidence.
- **3D Calibration & Regret Analysis:** measure false positives, false negatives, downside capture, turnover, forecast calibration and opportunity-cost regret versus cash/reference and available alternatives.
- **3E Ablation / Robustness:** remove probability, confidence, concentration cost, execution friction or other components one at a time to determine incremental value versus complexity.
- **3F Historical Promotion Gate:** allowed outcomes are `REJECT_V2_FORM`, `CONTINUE_SHADOW_RESEARCH`, or `PROMOTE_TO_PHASE_4_FORWARD_VALIDATION`. Phase 3 may never authorize Phase 5 directly.

### Phase 4 — Forward Parallel Shadow Validation — MANDATORY / NOT STARTED
- Run Legacy and surviving candidate Strategy Kernel model(s) in parallel on genuinely future, previously unseen market/research states for multiple complete decision cycles.
- Measure recommendation usefulness, stability, forecast calibration, opportunity-cost regret, false-positive cost, missed-opportunity regret, turnover, downside behavior, operational robustness and explainability without hindsight.
- Phase 4 is mandatory even if Phase 3 is strong; historical replay may not substitute for forward validation.
- Exit may only be `REJECT_OR_REVISE`, `EXTEND_FORWARD_VALIDATION`, or `ELIGIBLE_FOR_PHASE_5_GOVERNED_MIGRATION_PROPOSAL`.

### Phase 5 — Governed Migration — NOT STARTED / NOT AUTHORIZED
Requires accepted Phase 3 historical evidence, accepted Phase 4 forward evidence, and a separate governed migration approval.

Planned internal steps:
- **5A Migration Proposal**
- **5B Rule-by-rule Treatment Map**
- **5C Limited Activation**
- **5D Rollback Observation**
- **5E Final Governed Acceptance**

No Strategy/Core migration is inferred automatically from shadow research performance.

## Current program state
Phase 2 shadow infrastructure is complete but remains under stacked governed review. Program-governance correction is being reviewed before Phase 3 implementation starts. Phase 4 remains mandatory; Phase 5 is not authorized.
