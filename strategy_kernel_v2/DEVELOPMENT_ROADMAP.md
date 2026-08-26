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
- **1B Decision Object v2 shadow adapter — COMPLETE / PR #298.**
  - Normalize existing Canonical decision states without changing effective policy.
  - Preserve 601138 accepted NO_TRADE semantics, HKEX:00669 price-band-as-research-trigger semantics, and 605090 concentration as a diagnostic rather than an automatic sell signal.
- **1C Underwriting Extraction — VALIDATED SHADOW-ONLY / PR #299.**
  - Extract existing Canonical issuer research into a common Underwriting Object.
  - Unknown or missing evidence remains explicit; no research, valuation, scenario probability, or confidence is synthesized merely to complete a schema.

### Phase 2 — Capital Comparison Infrastructure — COMPLETE SHADOW / STACKED REVIEW
- **2A Comparator Contract / Engine — VALIDATED SHADOW-ONLY / PR #300.**
  - Transparent multi-dimensional vectors plus Pareto frontier; no unvalidated scalar score.
  - Expected return, downside, probability of loss, confidence, concentration cost and execution friction remain measurement fields, not effective policy weights.
  - Current Phase 1C baseline returned 0 eligible / 8 blocked absent governed refresh.
- **2B Governed Refresh Adapters — VALIDATED SHADOW-ONLY / PR #301.**
  - Exact governed refresh coverage is required.
  - `NOT_READY` cannot be cured by price/valuation alone; material fundamental gaps require governed fundamental re-underwrite.
  - Source decision readiness and Canonical authority remain unchanged.
- **2C Current Shadow Comparison Pack — VALIDATED COMPLETE / PR #302 / current pack `NO_COMPARISON`.**
  - Actual main + newer governed production evidence was inventoried for all eight objects.
  - Fresh 2026-08-25 A-share market marks exist for part of the set, but zero objects satisfy the full Phase 2B refresh plus Phase 2A probabilistic-comparison input contract without adding new assumptions.
  - Zero real refresh packets were fabricated/applied; 0 eligible / 8 blocked; no ranking manufactured.
- **Program Governance Correction — VALIDATED / PR #303.**
  - Restored mandatory Phase 4 forward validation, prohibited direct Phase 3→5 promotion, and added machine-enforced lifecycle consistency.
  - Accepted as the governed parent for continued stacked shadow development; Canonical `main` remains unchanged and protected.

### Phase 3 — Historical Replay & Calibration — IN PROGRESS / 3A + 3B COMPLETE_BOUNDED
Mandatory point-in-time validation before any forward promotion. Phase 3 tests model form as well as parameters; strong historical results do not authorize effective migration.

Internal steps:
- **3A Point-in-time Evidence Ledger — VALIDATED COMPLETE_SCOPE_BOUNDED / PR #304.**
  - Canonical-only registry contains 29 immutable evidence records across seven replay checkpoints from 2026-07-26 through 2026-08-18 and the eight current Strategy Kernel v2 objects.
  - Research, market, portfolio, Candidate and decision context are bound to Canonical commit availability rather than filename/as-of date alone.
  - The ledger selects the latest version available at each checkpoint and preserves stale embedded watermarks rather than retrospectively refreshing them.
  - 000719/301215 R1 is visible at the 2026-08-13 checkpoint; R2 becomes visible only after the 2026-08-18 Canonical merge.
  - Derived ledger output is rebuilt from the registry/checkpoints rather than committed as an authority artifact, preventing hand-maintained derived-file drift.
  - This seven-checkpoint window is sufficient to support model-form plumbing, but is **not statistically sufficient for 3F promotion**. Historical coverage/regime breadth must be expanded before the historical promotion gate can pass.
- **3B Competing Model Forms — VALIDATED COMPLETE_CONTRACT_ONLY / PR #305.**
  - Established one immutable shared observation packet: identical timestamp, opportunity set, selected Phase 3A evidence, structured observations and explicit reference asset for every model.
  - Structured observations may cite only evidence already selected by the Phase 3A checkpoint; model-specific evidence fetch is forbidden and missing model inputs fail closed as `NOT_EVALUABLE`.
  - Fixed three model forms for later replay: `LEGACY_POLICY_BASELINE`, `PHASE2_PROBABILISTIC_VECTOR`, and `SIMPLE_NON_PROBABILISTIC_PARETO`.
  - Legacy is contemporaneous state/disposition passthrough only; it may not be reconstructed through retrospective interpretation.
  - The Phase-2 form preserves explicit probability scenarios plus transparent return/downside/confidence/concentration/execution vectors and Pareto dominance; no scalar utility score is introduced.
  - The simple challenger uses explicit non-probabilistic return/downside/evidence-quality/concentration/execution dimensions and Pareto dominance, preventing complexity or probability assumptions from being treated as inherently superior.
  - Current seven Phase 3A seed checkpoints contain evidence references but no model-ready structured historical feature layer. Therefore all 21 model×checkpoint combinations correctly remain 0 evaluable in 3B. Synthetic fixtures validate mechanics only and are not historical performance evidence.
  - Phase 3B does **not** extract historical features, replay decisions, calibrate parameters, select a winning model, or produce comparative performance conclusions.
- **3C Decision / Capital Replay — NEXT / NOT STARTED.**
  - First extract model-neutral structured observations from the exact Phase 3A source path + commit for each checkpoint; every extracted field must retain provenance inside that checkpoint and later evidence must remain inaccessible.
  - Then run the three fixed 3B model forms on identical shared packets and compare admitted, blocked, prioritized, retained, reduced or `NO_ACTION` shadow outcomes.
  - Feature extraction and model execution must remain separable so a model cannot gain a richer information set through its own adapter.
- **3D Calibration & Regret Analysis:** measure false positives, false negatives, downside capture, turnover, forecast calibration and opportunity-cost regret versus cash/reference and available alternatives.
- **3E Ablation / Robustness:** remove probability, confidence, concentration cost, execution friction or other components one at a time to determine incremental value versus complexity.
- **3F Historical Promotion Gate:** allowed outcomes are `REJECT_V2_FORM`, `CONTINUE_SHADOW_RESEARCH`, or `PROMOTE_TO_PHASE_4_FORWARD_VALIDATION`. Phase 3 may never authorize Phase 5 directly. Current promotion eligibility remains false pending broader historical coverage and completion of 3C–3E.

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
Phase 2 shadow infrastructure and the Program Governance Correction are validated on the stacked development chain. Phase 3 is in progress: Phase 3A is complete for a bounded seven-checkpoint Canonical evidence window and Phase 3B has validated the three competing model-form contracts on a common fail-closed input surface. No real historical model comparison has yet been run because point-in-time structured feature extraction and decision/capital replay are Phase 3C work. Phase 3 historical validation as a whole is not complete, Phase 3F promotion eligibility is false, Phase 4 remains mandatory, and Phase 5 is not authorized. Canonical `main` remains unchanged.
