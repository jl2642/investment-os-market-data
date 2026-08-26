# Strategy Kernel v2 — Overall Development Roadmap

## Master-program authority
`MASTER_PROGRAM_CHARTER.md` and `PROGRAM_CONTRACT.json` define the macro lifecycle. This roadmap may refine execution but may not silently delete, reorder, bypass, or reinterpret a macro phase. Controlled-plan changes must keep Charter, Contract, State, Roadmap, Execution Plan, Changelog and Current Status synchronized.

Hard boundaries through Phase 4: no live trading, no order creation, no automatic Candidate mutation, no Real/Simulation economic mutation, no target-portfolio writeback; `orders=0`, `trade_authority=NONE`.

## Macro roadmap
### Phase 0 — System Audit — COMPLETE
Legacy/Core Static semantics inventoried and preserved as the baseline.

### Phase 1 — Decision & Underwriting — COMPLETE SHADOW
- 1B Decision Object v2 — COMPLETE / PR #298.
- 1C Underwriting Extraction — VALIDATED SHADOW-ONLY / PR #299.
No missing evidence, valuation, probability or confidence is synthesized merely to complete a schema.

### Phase 2 — Capital Comparison Infrastructure — COMPLETE SHADOW
- 2A Comparator Contract / Engine — VALIDATED / PR #300: transparent multi-dimensional vectors + Pareto; no scalar policy score.
- 2B Governed Refresh Adapters — VALIDATED / PR #301: readiness requires exact governed evidence coverage.
- 2C Current Shadow Comparison Pack — VALIDATED / PR #302: `NO_COMPARISON`, 0 eligible / 8 blocked, no fabricated refresh packets.
- Program Governance Correction — VALIDATED / PR #303: restored mandatory Phase 4 and prohibited direct Phase 3→5 promotion.

### Phase 3 — Historical Replay & Calibration — IN PROGRESS
Internal sequence remains exactly `3A → 3B → 3C → 3D → 3E → 3F`.

#### 3A Point-in-time Evidence Ledger — VALIDATED COMPLETE_SCOPE_BOUNDED / PR #304
29 Canonical evidence records, 7 checkpoints, 8 securities, exact availability/commit provenance, no-hindsight selection. This engineering seed is not statistically sufficient for 3F.

#### 3B Competing Model Forms — VALIDATED COMPLETE_CONTRACT_ONLY / PR #305
Fixed forms:
1. `LEGACY_POLICY_BASELINE`
2. `PHASE2_PROBABILISTIC_VECTOR`
3. `SIMPLE_NON_PROBABILISTIC_PARETO`

Every form consumes the same immutable shared packet. Missing inputs fail closed; model-specific evidence fetch and retrospective input creation are forbidden.

#### 3C Decision / Capital Replay — VALIDATED COMPLETE_TERMINAL_NONREPLAYABILITY / PR #306
- exact registered historical source reads: 29/29 across 7 checkpoints;
- Legacy evaluable security×checkpoint instances: 29;
- Phase-2 probabilistic/vector evaluable instances: 0;
- simple-Pareto evaluable instances: 0;
- probability/scenario backfills, subjective fills and model-specific fetches: 0.

A full Canonical-tree recovery audit inspected 673 keyword-candidate file occurrences, including 114 exact-model-field and 147 proxy-like-field occurrences. Complete Phase-2 packets = 0; complete simple-Pareto packets = 0; unregistered complete packets omitted by 3A = 0 for both forms.

Therefore both candidate forms are historically non-replayable on the bounded corpus under their fixed 3B contracts. This is a model-form/input-burden finding, not comparative performance evidence.

#### Governed Post-3C Evaluation Path — APPROVED
The governance gate does not create a new subphase. Approved path:
- reject retrospective input synthesis;
- reject silent 3B contract rewrite;
- reject skipping 3D;
- allow 3D to start only as `NEGATIVE_RESULT_MEASURABILITY_AND_REGRET_OBSERVABILITY`.

Before realized outcomes are loaded, 3D must pre-register outcome horizons and reference definitions. Legacy metrics may be measured where evidence supports them. Candidate metrics requiring nonexistent contemporaneous outputs must be `NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS`. Hypothetical candidate decisions, synthetic candidate returns/regret and cross-model winner selection are forbidden.

#### 3D Calibration & Regret Analysis — READY TO START / NOT STARTED
Authorized scope is negative-result/measurability analysis only. Outcome data are evaluation targets and may not feed back into historical inputs or model parameters.

#### 3E Ablation / Robustness — NOT STARTED
Test probability, confidence, concentration cost, execution friction and later transformations one component at a time. Phase 3C non-replayability is accepted complexity/usability evidence.

Any materially revised model form must be versioned and must return through governed 3B contract definition and 3C replay. It may not overwrite the historical 3B candidate identity. Same-seed outcome-tuned redesign is forbidden; broader or holdout historical validation is required.

#### 3F Historical Promotion Gate — NOT ELIGIBLE
Allowed outcomes remain `REJECT_V2_FORM`, `CONTINUE_SHADOW_RESEARCH`, or `PROMOTE_TO_PHASE_4_FORWARD_VALIDATION`.

Promotion to Phase 4 requires at least one candidate with valid point-in-time historical replay, measurable 3D evidence, accepted 3E robustness evidence and broader historical coverage. If no candidate becomes historically evaluable, only `REJECT_V2_FORM` or `CONTINUE_SHADOW_RESEARCH` are allowed.

### Phase 4 — Forward Parallel Shadow Validation — MANDATORY / NOT STARTED
Run Legacy and surviving candidate model(s) in parallel on genuinely future, unseen evidence for multiple complete cycles. Measure usefulness, calibration, stability, regret, turnover, downside behavior, operational robustness and explainability without hindsight.

Exit only: `REJECT_OR_REVISE`, `EXTEND_FORWARD_VALIDATION`, or `ELIGIBLE_FOR_PHASE_5_GOVERNED_MIGRATION_PROPOSAL`.

### Phase 5 — Governed Migration — NOT STARTED / NOT AUTHORIZED
Requires separately accepted Phase 3 historical evidence, Phase 4 forward evidence and a governed migration proposal. Planned sequence: 5A Proposal → 5B Rule Map → 5C Limited Activation → 5D Rollback Observation → 5E Final Acceptance.

## Current program state
Phase 3C is complete as a terminal bounded negative replayability finding. The governed post-3C path decision is approved, so Phase 3D is now eligible to start only in negative-result/measurability mode; Phase 3D has not started. Phase 3 historical validation remains incomplete, 3F is not eligible, Phase 4 is mandatory but unavailable, and Phase 5 is unauthorized. Canonical `main` remains unchanged.
