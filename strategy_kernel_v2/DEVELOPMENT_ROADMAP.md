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

### Phase 3 — Historical Replay & Calibration — IN PROGRESS / R2 DEVELOPMENT REPLAY COMPLETE / INDEPENDENT HOLDOUT NEXT / PHASE 4 BLOCKED
Internal sequence remains exactly `3A → 3B → 3C → 3D → 3E → 3F`. A completed negative 3F gate does not itself complete Phase 3; governed redesign/replay or broader historical evidence is required before a later 3F re-evaluation can pass.

#### 3A Point-in-time Evidence Ledger — VALIDATED COMPLETE_SCOPE_BOUNDED / PR #304
29 Canonical evidence records, 7 checkpoints, 8 securities, exact availability/commit provenance, no-hindsight selection. Seed remains statistically insufficient for Phase 4 promotion.

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

Bounded result across 7 checkpoints / 33 feature-security instances / 29 exact historical source reads:
- Phase-2 fixed baseline evaluable instances: **0**;
- Phase-2 single-component ablations: **4**, all **0** evaluable;
- Simple-Pareto fixed baseline evaluable instances: **0**;
- Simple-Pareto single-component ablations: **5**, all **0** evaluable;
- total single-component ablations: **9**;
- ablations that restore any historical replay coverage: **0**.

Finding: `NO_SINGLE_COMPONENT_ABLATION_RESTORES_HISTORICAL_REPLAY`. Historical non-replayability is a multi-input contract burden / structural mismatch, not one isolated missing field. Related contemporaneous information exists but is not contract-equivalent; silent proxy substitution remains forbidden.

No revised model form is created in 3E. Any material redesign must receive a new model/version identity and return through governed 3B→3C. The seven seed checkpoints may not be tuned and represented as independent validation; broader or holdout history remains required.

#### 3F Historical Promotion Gate — COMPLETE / CONTINUE_SHADOW_RESEARCH / PR #310
The gate contract distinguishes failure to qualify for Phase 4 from evidence of terminal economic model failure.

Mandatory Phase 4 promotion requirements and current result:
1. candidate point-in-time historical replay — **FAIL**: 0 candidate replayable instances;
2. measurable candidate Phase 3D evidence — **FAIL**: no candidate comparative performance, regret, calibration or return-attribution metrics;
3. accepted Phase 3E robustness — **PASS**: 9 single-component ablations, 0 replay unlocks, no outcome tuning;
4. broader historical coverage — **FAIL**: current seed remains 7 checkpoints and scope-bounded.

Gate score: **1/4 mandatory requirements passed**. Therefore `PROMOTE_TO_PHASE_4_FORWARD_VALIDATION` is forbidden.

The gate outcome is `CONTINUE_SHADOW_RESEARCH`, not `REJECT_V2_FORM`, because candidate economic performance was not measurable, no comparative underperformance/winner conclusion exists, and Phase 3E identified adjacent contemporaneous observables plus a governed redesign path. Current fixed Phase 3B candidate forms are nevertheless `NOT_PROMOTABLE_IN_CURRENT_FORM`.

Any material revision must:
- receive a new model/version identity;
- preserve the original fixed 3B forms for historical audit;
- loop back through governed `Phase 3B contract definition → Phase 3C replay`;
- not count outcome-tuned seven-seed work as independent validation;
- obtain broader or holdout historical evidence before another 3F promotion attempt.

Phase 3 remains open. A later 3F re-evaluation may occur only after the missing promotion evidence is actually produced. Phase 4 remains blocked.

#### Governed Post-3F R2 Loopback — B/C COMPLETE, HOLDOUT NEXT / PR #311 → #312 → #316 → #318
The negative 3F gate did not authorize a direct Phase 4 entry. PR #311 froze the governed research path as a new-identity evidence-native R2 redesign plus independent point-in-time holdout expansion.

Completed R2 loopback:
- **Post-3F path decision / PR #311 — COMPLETE:** approved `NEW_IDENTITY_EVIDENCE_NATIVE_R2_PLUS_INDEPENDENT_HOLDOUT_EXPANSION`; the seven seed checkpoints remain development corpus only.
- **3B-R2 / PR #312 — COMPLETE:** froze `EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2`; current patched research identity is `R2.0.1_RESEARCH`, 20 frozen transforms, exact-signature Pareto only, no scalar score, no winner, no outcome tuning.
- **3C-R2A / PR #316 — COMPLETE / ACCEPTED:** exact PIT reconstruction across 7 checkpoints / 29 registered historical source reads / 33 R2 profiles; 171 present dimensions, 489 explicit missing dimensions, 0 transform failures; no Pareto execution, outcomes or holdout use.
- **3C-R2B / PR #318 — COMPLETE / ACCEPTED:** first real R2 mechanical historical replay completed on the development corpus. Final result: 15 exact-signature groups, 9 comparable groups, 6 singleton groups, 20 comparable profiles, 26 directional Pareto pair checks, 4 dominance edges, 17 local frontier instances and 3 dominated instances; `PASS_MECHANICAL_REPLAY_OPERATIONAL`. These are local replay relations, not performance evidence or a global winner.

The remaining Phase 3 path is frozen as:
`Independent Point-in-Time Holdout Coverage → Phase 3D-R2 measurability/performance if supported → Phase 3E-R2 robustness if supported → Repeat Phase 3F Historical Promotion Gate`.

Important boundaries:
- Holdout is **not** a new macro phase and is **not** a direct Phase 4 entrance.
- No 3C-R2C round is authorized; 3C-R2 consists only of R2A reconstruction and R2B mechanical replay/final acceptance.
- Phase 3D-R2 is now **COMPLETE through deterministic performance measurement**. Outcome Evidence Acquisition remains 55/55 endpoints and 54/54 frozen edges complete. The frozen-pack-only measurement produced 165 endpoint returns and 162 edge-horizon measurements across 13 edge-bearing checkpoints / 2 exact signatures. Descriptive concordance was 34/54 (62.96%) at +1 session, 29/54 (53.70%) at +3, and 27/54 (50.00%) at +5; mean edge spreads were +0.0276%, +0.1041%, and -0.0638% respectively. Pooled across all nested horizons, 90/162 (55.56%) were concordant with mean spread +0.0226%, but this pooled figure is explicitly non-inferential because edges, securities, checkpoints and horizons overlap. Measurement SHA-256 = `a3e474745dc8074be363f3d9b8e7082923bd67adeff6c6e42431e1f6a406edad`. No statistical-significance, portfolio-PnL, Sharpe, scalar-score or global-winner claim is made. Phase 3E-R2 has not started and is not yet authorized by a numeric performance threshold.
- Repeat Phase 3F is mandatory before Phase 4. Phase 4 may start only if all promotion requirements then pass.
- `phase3_historical_validation_complete=false`, `phase4_entry_allowed=false`, `orders=0`, `trade_authority=NONE`.

### Phase 4 — Forward Parallel Shadow Validation — MANDATORY / NOT STARTED / BLOCKED BY PHASE 3F
Run Legacy and surviving candidate model(s) in parallel on genuinely future unseen evidence across multiple complete cycles. Historical replay cannot substitute for Phase 4. Entry remains forbidden until a later Phase 3F gate passes all mandatory historical requirements.

### Phase 5 — Governed Migration — NOT STARTED / NOT AUTHORIZED
Requires separately accepted Phase 3 historical evidence, Phase 4 forward evidence and a governed migration proposal. Direct Phase 3→5 remains forbidden.

## Current program state
The original Phase 3F gate remains a 1/4 negative gate with `CONTINUE_SHADOW_RESEARCH`, but the governed R2 loopback has now completed its B/C work: Post-3F path decision #311, 3B-R2 #312, 3C-R2A #316 and 3C-R2B #318 are accepted on the stacked shadow chain. R2.0.1 is mechanically replay-operational on the seven-checkpoint development corpus, but this is not independent historical validation and does not satisfy the Phase 3D/3E/broader-coverage requirements needed for promotion. The next authorized work is **Independent Point-in-Time Holdout Coverage**. H0 selection/sufficiency contract is now frozen before any Holdout replay: frozen protected-main universe, exact seven-seed firewall, census selector, no outcome/model-result access, and multi-axis sufficiency thresholds. H1 deterministic ledger construction is now complete and returned `FAIL_SELECTION_SUFFICIENCY`: 8 canonical Holdout checkpoints were found versus the frozen minimum of 12. All other coverage axes passed (8 UTC dates, 5 ISO weeks, 6 evidence regimes, 8 securities, 64 opportunity-profile instances, 1 checkpoint outside the seed span, 12.5% max date concentration, 37.5% max regime concentration). H2 R2 replay is blocked. Holdout Coverage Expansion V2 is now frozen as a **pre-result contract**: the protected-main time universe, first-parent census selector, seven-seed firewall and all H0.1 sufficiency thresholds remain unchanged; four additional substantive model-neutral research/decision state families are admitted, pure liveness/lineage/outcome/model-result artifacts remain excluded, and the research-security scope expands deterministically from 8 to 18. V2 deterministic selection is now complete and returned `PASS_SELECTION_SUFFICIENCY`: 14 canonical checkpoints, 10 UTC dates, 5 ISO weeks, 9 evidence regimes, 18 securities, 252 opportunity-profile instances, 4 checkpoints outside the seed span, 21.43% maximum date concentration and 28.57% maximum regime concentration. Every unchanged H0.1 threshold passed. Independent Holdout Frozen R2 Replay is now **COMPLETE / PASS_INDEPENDENT_HOLDOUT_REPLAY_OPERATIONAL** on all 14 accepted checkpoints: 26/26 exact source identities, 105 R2 profiles, 561 present and 1539 explicit-missing dimensions, 0 transform failures, 0 audit errors, 27 comparable exact-signature groups, 85 comparable profiles, 220 directional pair checks and 54 dominance edges. The Holdout replay itself still contains no realized outcomes or historical performance. Phase 3D-R2 Round 1 has now separately established **structural measurability but incomplete governed outcome evidence**. Outcome Evidence Acquisition and deterministic Phase 3D-R2 Performance Measurement are complete. The result-value-blind **Phase 3E-R2 Structural Support Gate** is now COMPLETE / `PASS_R2_STRUCTURAL_SUPPORT_FOR_ROBUSTNESS`: 5/5 predefined robustness axes are structurally evaluable, gate decision result-value reads = 0, and no post-result numeric threshold was created. Gate SHA-256 = `c6288bb86700af9de8089fd14e1be379bb1beef4d4eeb537cf1f2e471c37d404`. This PASS means robustness is structurally worth and able to execute; it does not mean positive economic performance or model robustness. Phase 3E-R2 Robustness Execution is now **COMPLETE / accepted as descriptive evidence** under the five frozen one-axis-at-a-time tests. Robustness SHA-256 = `6cbd096716dc577dc643577795556d765d452b50a09f2e05ee5f253bd1b7e32f`; 5/5 tests, 13 checkpoint jackknifes, 7 security jackknifes, 2 signature jackknifes and 9 weighting-scheme×horizon records completed with zero integrity errors. No positive-robustness or statistical-significance claim is made. The observed evidence is materially sensitive to predeclared security/signature/weighting axes: the two exact signatures carry 52 versus 2 edges, and +1-session equal-signature weighting changes the descriptive result from equal-edge 62.96% / +0.0276% spread to 32.69% / -0.5001%. The mandatory next step is **Repeat Phase 3F Historical Promotion Gate**, which must interpret these limitations under the already-governed promotion requirements. Phase 4 remains blocked until that gate completes. Phase 3 historical validation remains incomplete, Phase 4 remains mandatory and blocked, Phase 5 remains unauthorized, and Canonical `main` remains unchanged.
