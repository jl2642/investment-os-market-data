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

#### 3E Ablation / Robustness — VALIDATED COMPLETE_STRUCTURAL_ABLATION / PR #309
3E uses only the same Phase 3A/3C point-in-time feature corpus. Phase 3D realized returns are explicitly excluded from ablation selection and requirement tuning.

Ablation contract:
- fixed Phase 3B model identities are preserved;
- one requirement is removed at a time;
- proxy/adjacent observables may be inventoried but may not substitute for contract fields;
- no subjective mapping, retrospective probability/confidence/cost-score creation, revised-model execution, winner selection or same-seed performance claim is allowed.

Bounded result across 7 checkpoints / 33 feature-security instances / 29 exact historical source reads:
- Phase-2 fixed baseline evaluable instances: **0**;
- Phase-2 single-component ablations: **4**, all **0** evaluable;
- Simple-Pareto fixed baseline evaluable instances: **0**;
- Simple-Pareto single-component ablations: **5**, all **0** evaluable;
- total single-component ablations: **9**;
- ablations that restore any historical replay coverage: **0**.

Finding: `NO_SINGLE_COMPONENT_ABLATION_RESTORES_HISTORICAL_REPLAY`. Historical non-replayability is therefore not attributable to one isolated required field; it reflects a multi-input contract burden / structural mismatch between the fixed candidate schemas and contemporaneous governed history.

Related contemporaneous information does exist, but is not contract-equivalent: scenario context appears in 5 security-instances, return context in 20, confidence context in 20, concentration context in 8, execution context in 8, evidence-quality context in 26 and downside context in 26. These observations are complexity-design evidence only; silent proxy substitution remains forbidden.

No revised model form is created in 3E. Any material redesign must receive a new model/version identity and **return through governed 3B contract definition and 3C replay**. The seven seed checkpoints may not be tuned and then represented as independent validation; broader or holdout history remains required.

#### 3F Historical Promotion Gate — READY TO START / PROMOTION NOT ELIGIBLE
3F is now procedurally startable because 3A–3E are complete, but current evidence does **not** satisfy promotion eligibility.

`PROMOTE_TO_PHASE_4_FORWARD_VALIDATION` requires at least one candidate with valid point-in-time historical replay, measurable 3D candidate evidence, accepted 3E robustness evidence and broader historical coverage. The fixed candidate forms still have 0 historical replayable instances and no measurable candidate regret/calibration/performance evidence, while the seven-checkpoint seed is also too narrow.

Therefore the current 3F gate may only produce `REJECT_V2_FORM` or `CONTINUE_SHADOW_RESEARCH`. Promotion to Phase 4 is not currently permitted. If a materially revised candidate is proposed, it must loop back to governed 3B→3C rather than bypass 3F evidence requirements.

### Phase 4 — Forward Parallel Shadow Validation — MANDATORY / NOT STARTED
Run Legacy and surviving candidate model(s) in parallel on genuinely future unseen evidence across multiple complete cycles. Phase 4 remains mandatory and unavailable until Phase 3 passes.

### Phase 5 — Governed Migration — NOT STARTED / NOT AUTHORIZED
Requires separately accepted Phase 3 historical evidence, Phase 4 forward evidence and a governed migration proposal. Direct Phase 3→5 remains forbidden.

## Current program state
Phase 3E is complete as bounded structural-ablation evidence: no single removed input restored candidate replayability, while adjacent contemporaneous information confirms that the problem is schema/contract fit rather than total absence of historical information. Phase 3F may now start only as a governed historical promotion gate with `phase3f_promotion_eligible=false`. Phase 3 historical validation remains incomplete, Phase 4 remains mandatory but unavailable, Phase 5 is unauthorized, and Canonical `main` remains unchanged.
