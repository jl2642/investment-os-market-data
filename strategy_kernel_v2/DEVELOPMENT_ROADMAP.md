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
Missing evidence remains explicit; no valuation/probability/confidence is synthesized merely to fill a schema.

### Phase 2 — Capital Comparison Infrastructure — COMPLETE SHADOW
- 2A Comparator Contract / Engine — VALIDATED / PR #300.
- 2B Governed Refresh Adapters — VALIDATED / PR #301.
- 2C Current Shadow Comparison Pack — VALIDATED / PR #302: `NO_COMPARISON`, 0 eligible / 8 blocked.
- Program Governance Correction — VALIDATED / PR #303: Phase 4 restored; direct Phase 3→5 prohibited.

### Phase 3 — Historical Replay & Calibration — IN PROGRESS
Internal sequence remains exactly `3A → 3B → 3C → 3D → 3E → 3F`.

#### 3A Point-in-time Evidence Ledger — VALIDATED COMPLETE_SCOPE_BOUNDED / PR #304
29 Canonical evidence records, 7 checkpoints, 8 securities, exact availability/commit provenance, no-hindsight selection. Seed remains statistically insufficient for 3F.

#### 3B Competing Model Forms — VALIDATED COMPLETE_CONTRACT_ONLY / PR #305
Fixed forms: `LEGACY_POLICY_BASELINE`, `PHASE2_PROBABILISTIC_VECTOR`, `SIMPLE_NON_PROBABILISTIC_PARETO`. Same immutable input packet; missing inputs fail closed.

#### 3C Decision / Capital Replay — VALIDATED COMPLETE_TERMINAL_NONREPLAYABILITY / PR #306
29/29 exact historical sources read; Legacy evaluable instances 29; both candidates 0. Full Canonical-tree audit found no complete registered or unregistered candidate packet. Candidate non-replayability is a model-form/input-burden finding, not comparative performance evidence.

#### Governed Post-3C Evaluation Path — APPROVED / PR #307
Approved `PHASE3D_NEGATIVE_RESULT_MEASURABILITY_THEN_PHASE3E_ABLATION`. Retrospective input synthesis, silent 3B rewrite and skipping 3D are rejected. Missing candidate metrics remain `NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS`; materially revised 3E forms must return through governed 3B→3C.

#### 3D Calibration & Regret Analysis — VALIDATED COMPLETE_BOUNDED_NEGATIVE_RESULT_MEASURABILITY / PR #308
3D froze its evaluation contract before loading outcomes: fixed 1/3/5 exchange-session horizons, outcome/reference conventions and missing-data treatment. Repository governed history was audited first; because it did not cover the required daily sequence, reputable historical close data were used under the pre-frozen fallback policy without changing horizons.

Mechanical replay/outcome build:
- Legacy instance observations: **29**;
- candidate security×model×checkpoint records: **100**, all `NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS` for candidate performance attribution;
- Legacy `RETAINED` forward-price observations: **5**, all repeated 601138 checkpoints;
- Legacy `NO_ACTION` opportunity-only observations: **16**;
- Legacy `PRIORITIZED` research opportunity-only observations: **7**;
- one simulation `REDUCED` posture observation: **1**;
- measurable regret instances: **0**;
- measurable calibration instances: **0**.

Descriptive retained-only price-return means are approximately -0.11% at 1 session, -2.52% at 3 sessions and -5.15% at 5 sessions. These five rows are repeated observations of the same security, are not independent trials, and cannot be compared with absent candidate outputs. No winner, statistical-significance claim or cross-model ranking is permitted.

#### 3E Ablation / Robustness — READY TO START / NOT STARTED
Test removal/simplification of probability, confidence, concentration cost, execution friction and later transformations one component at a time. 3C/3D jointly establish that current candidate forms impose an historically unmet input burden and cannot be performance-compared on the bounded seed.

Any materially revised model form must receive a new version identity and **return through governed 3B contract definition and 3C replay**; same-seed outcome tuning cannot be represented as independent validation. Broader or holdout history remains required.

#### 3F Historical Promotion Gate — NOT ELIGIBLE
Allowed outcomes remain `REJECT_V2_FORM`, `CONTINUE_SHADOW_RESEARCH`, or `PROMOTE_TO_PHASE_4_FORWARD_VALIDATION`. Promotion requires a historically replayable candidate, measurable 3D evidence, accepted 3E robustness and broader historical coverage. If no candidate becomes historically evaluable, only reject/continue-research outcomes remain.

### Phase 4 — Forward Parallel Shadow Validation — MANDATORY / NOT STARTED
Run Legacy and surviving candidate model(s) in parallel on genuinely future unseen evidence across multiple complete cycles. Phase 4 remains mandatory and unavailable until Phase 3 passes.

### Phase 5 — Governed Migration — NOT STARTED / NOT AUTHORIZED
Requires separately accepted Phase 3 historical evidence, Phase 4 forward evidence and a governed migration proposal. Direct Phase 3→5 remains forbidden.

## Current program state
Phase 3D is complete as bounded negative-result/measurability analysis. It produces descriptive Legacy outcome observations but **no candidate performance, comparative regret/calibration, model winner or promotion evidence**. Phase 3E is now eligible to start under the Post-3C loopback guard; Phase 3 historical validation remains incomplete, 3F is not eligible, Phase 4 remains mandatory but unavailable, Phase 5 is unauthorized, and Canonical `main` remains unchanged.
