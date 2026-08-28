# 2026-08-28 — P4-1 PRODUCTION BACKBONE CONTRACT FREEZE

**Parent:** Program Amendment A1 / PR #338.

**Decision:** freeze a main-based operational repair lane before implementation. The Strategy Kernel stacked chain must not be merged into main merely to repair production.

**Authority design:** `main` remains Governance Canonical. A rebuildable `operating-current` surface may carry only QC-passed run pointers, watermarks and receipts under `operating_current/**`; inherited repository paths on that branch have no operating authority.

**Initial domains:** A-share full market; portfolio marks; Candidate weekly observation; D2 research; bounded HK/US production.

**Failure rule:** failed/stale/blocked runs never replace the current pointer. Low-risk pointer advancement does not require a daily main PR. Formal Candidate membership, Real economic state and protected Simulation economic state remain main-governed.

**Forward-validation consequence:** Phase 4 effective execution hold remains active; observations=0 and outcomes=0.

**Next:** a separate operational implementation PR based directly on protected main.

---

# 2026-08-28 — PROGRAM_AMENDMENT_A1 / PHASE4_PRODUCTION_CLOSURE_REALIGNMENT

**Trigger:** system-wide production audit after Phase 4 v1 contract freeze and zero-observation census.

**Observed defect:** protected `main` and several Canonical operating surfaces are not advancing with the actual public-data/research cadence; full-market/Candidate/Decision continuity and R6 operating activation are incomplete. A protected-main-only forward selector can therefore starve even while non-canonical operating PRs/evidence exist.

**Why amendment is allowed now:** Phase 4 v1 counted 0 observations and read 0 realized outcomes. No observed forward performance is used to revise the model, thresholds or selection logic.

**Decision:** retain #333 and #337 as immutable audit records, activate a higher-level effective forward-execution hold, and require production closure plus a clean rebaseline before any Phase 4 forward observation may count.

**Macro impact:** none. Phase 0→5 lifecycle unchanged; Phase 0–3 remain complete; Phase 5 remains unauthorized.

**Phase 4 internal plan:** P4-0 Reconciliation → P4-1 Production Backbone Repair → P4-2 Continuous Opportunity Funnel → P4-3 Unified Decision & Recommendation Engine → P4-4 Trigger Monitor & Autonomous Shadow Book → P4-5 Clean-Baseline Forward Validation.

**Model impact:** none. R2.0.1, 20 transforms, exact-signature Pareto, 1/3/5 horizons, aggregation schemes and frozen directional gate remain unchanged.

**Economic/authority impact:** none in P4-0. Formal Candidate, protected Simulation, Real account, target portfolio and orders are unchanged; `orders=0`; `trade_authority=NONE`.

**Next governed work:** `P4-1_PRODUCTION_BACKBONE_REPAIR` only after P4-0 remote acceptance.

---

# Strategy Kernel v2 — Plan Changelog

## 2026-08-26 — Phase 1C plan synchronization
Phase 1C was formalized between Decision Object normalization and capital comparison so underwriting completeness, comparison readiness and decision readiness are not conflated. No effective policy or authority changed.

## 2026-08-26 — Phase 1C validation closeout
Persisted deterministic bundle, tests and validation record; synchronized implementation status to validated shadow-only. No phase-order or authority change.

## 2026-08-26 — Phase 2 execution refinement
**Reason:** deep-research findings and Phase 1C evidence gaps show that immediately creating a single ranked score would embed unvalidated utility weights and risk confusing measurement with policy.

**Changed:**
- retained top-level Phase 2 but split execution into 2A Comparator Contract/Engine, 2B Governed Refresh Adapters, and 2C Current Shadow Comparison Pack;
- Phase 2A uses transparent return/downside/confidence/concentration/execution vectors and a weight-free Pareto frontier;
- explicitly prohibits a scalar policy score in 2A;
- requires every `READY_AFTER_REFRESH` item to satisfy all recorded refresh requirements through a governed overlay;
- requires an explicit rate/provenance for any cash/reference baseline;
- Phase 2C requires at least two meaningful non-reference eligible capital uses or emits `NO_COMPARISON`.

**Not changed:** no Core Static rule, Candidate membership, economic state, target weight, user decision, order authority or trade authority changes; `orders=0`, `trade_authority=NONE`.

## 2026-08-26 — Phase 2B governed refresh contract
**Reason:** Phase 2A correctly returned 0 eligible / 8 blocked from the current Phase 1C objects. A safe mechanism is needed to admit genuinely refreshed evidence without relaxing the evidence standard merely to generate a ranking.

**Changed:**
- added a governed refresh packet schema with explicit provenance, evidence classes, requirement coverage, material-gap resolution, scenarios and comparison inputs;
- `READY_AFTER_REFRESH` requires exact coverage of all recorded refresh requirements;
- clarified that `NOT_READY` can become comparison-ready only after a governed `FUNDAMENTAL_REUNDERWRITE` resolves all original refresh requirements and material evidence gaps;
- price/valuation-only refresh cannot override a material fundamental evidence gap;
- a refreshed shadow copy may change comparison readiness only; source decision readiness and Canonical authority are preserved.

**Validation:** 13/13 unit tests pass; no user decision, Candidate mutation, economic mutation, order or trade is generated.

## 2026-08-26 — Phase 2C real-evidence closeout
**Reason:** Phase 2C was required to test the comparison architecture against actual stored governed evidence, not to manufacture a ranking.

**Observed evidence outcome:**
- latest governed A-share market/portfolio marks are materially fresher than main research state and reach 2026-08-25;
- freshness alone does not supply probability-weighted scenarios, explicit confidence, concentration cost, execution friction or missing fundamental underwriting;
- WP4B completion flags do not expose the underlying scenario payload needed by the comparator;
- 601138 has legacy unweighted scenarios and fresh price but not the full current fundamental/probability packet;
- 605090 and 301215 remain material-evidence-gap cases;
- no object can form a complete Phase 2B packet without adding new assumptions.

**Changed:**
- persisted a source-by-source current evidence inventory for all eight objects;
- added a generic Phase 2C pack builder that accepts only real Phase 2B refresh packets and emits `NO_COMPARISON` when fewer than two non-reference uses are eligible;
- persisted the current pack as `NO_COMPARISON`: 0 eligible / 8 blocked / 0 real refresh packets applied;
- advanced the development state to the boundary before historical replay.

**Not changed:** no effective Core Static rule, Candidate state, real/simulation state, target weight, user decision or trade permission changed.

## 2026-08-26 — ROADMAP_DRIFT_CORRECTION / Program Governance Hardening
**Detected drift:** during Phase 2 plan synchronization, the macro roadmap accidentally omitted the originally required Phase 4 Forward Parallel Shadow Validation and made the documentation appear to allow Phase 3 to lead directly toward effective migration.

**Impact assessment:**
- implementation through Phase 2C remained shadow-only;
- no Core Static policy, Candidate state, real/simulation economic state, target weight, user decision, order authority or trade authority changed;
- therefore this was a program-control/documentation drift, not an effective-policy migration.

**Correction:**
- restored the explicit macro lifecycle `Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5`;
- established `MASTER_PROGRAM_CHARTER.md` as the human-readable master charter and `PROGRAM_CONTRACT.json` as its machine-readable lifecycle contract;
- added `PROGRAM_STATE.json` with Phase 2 complete-shadow state, Phase 3 next, Phase 4 mandatory, and Phase 5 migration forbidden;
- expanded Phase 3 into 3A–3F and restored Phase 4 forward parallel shadow validation plus Phase 5 governed migration sequence;
- added machine-checkable program consistency validation so future macro-phase omission or illegal Phase 3→5 promotion fails validation.

**Not changed:** Phase 0–2 implementation semantics and all authority boundaries remain unchanged; `orders=0`, `trade_authority=NONE`.

**Promotion consequence:** Phase 3 implementation may start only after this correction is governed and the program-consistency check passes. Phase 3 can promote only to Phase 4; Phase 5 requires separate Phase 3 + Phase 4 evidence.

## 2026-08-26 — Program consistency validator acceptance hardening
**Reason:** final governance acceptance review found that the first validator checked the Charter, Roadmap and Execution Plan but did not actually read `PLAN_CHANGELOG.md`, despite the Charter listing it as a controlled artifact. It also hard-coded the temporary Phase 2 → 3 state and checked only part of the machine-readable promotion contract.

**Changed:**
- `PLAN_CHANGELOG.md` is now read by the validator and must contain the roadmap-drift correction record while that correction flag is active;
- all mandatory promotion gates in `PROGRAM_CONTRACT.json` must be true;
- current macro phase must follow the contract-declared promotion edge dynamically rather than a Phase-2-specific hard code;
- Phase 3/4/5 completion and entry dependencies are machine-checked;
- `PROGRAM_STATE.json` and `CURRENT_PHASE_STATUS.json` must remain in lockstep on promotion, phase-start and authority fields;
- zero-mutation and `orders=0` / `trade_authority=NONE` invariants are checked across the controlled state surfaces;
- governance regression coverage is expanded accordingly.

**Not changed:** no macro lifecycle, investment model, Core Static rule, Candidate state, portfolio state, target weight, user decision, order authority or trade authority changed.

**Promotion consequence:** Phase 3A remains blocked until this hardened validator passes on the governed correction head.

## 2026-08-26 — Phase 3A Point-in-time Evidence Ledger / bounded acceptance
**Reason:** historical replay cannot be valid if a file's embedded `as_of` date is confused with the date the information actually became Canonical. The same problem applies to later research revisions, market marks, Candidate state and portfolio context.

**Implemented:**
- added a pure point-in-time ledger engine with offset-aware `available_at`, immutable source commit identity, explicit authority domain and stable evidence-stream keys;
- default replay authority is `CANONICAL_MAIN` only;
- later versions are excluded until their availability timestamp and remain visible only as future evidence;
- checkpoint-bound Candidate, Real Account and market/portfolio marks preserve the exact Canonical state at that checkpoint, including stale embedded watermarks;
- added a real registry of 29 Canonical evidence records and seven Canonical replay checkpoints spanning 2026-07-26 through 2026-08-18 across the eight current Strategy Kernel v2 objects;
- bound decision-relevant streams including WP4/WP4B, 601138 WP5 P0, HKCU P5C valuation, HKCU 00669 BUY REVIEW and D2 R1/R2;
- added deterministic materialization from registry + checkpoint inputs rather than treating a copied derived ledger as authority.

**Implementation correction during review:** an initially hand-materialized derived ledger accidentally listed out-of-scope 00669/601138 future evidence in the first Core2-only checkpoint. The source registry and builder were correct; the hand-derived file was deleted immediately. Real-registry tests now verify that unrelated future assets are not surfaced and the ledger is rebuilt from authority inputs. No economic or policy state was affected.

**Validation:**
- 16 generic no-hindsight/authority/validation tests pass;
- 8 real-registry acceptance tests pass;
- total local Phase 3A suite = 24/24;
- all seven declared checkpoint requirement sets are reproducible in the bounded registry;
- at the 2026-08-13 checkpoint, 000719/301215 R1 is selected while R2 remains future evidence;
- R2 becomes selectable only at the 2026-08-18 Canonical merge;
- retrospective probability backfills=0; retrospective scenario backfills=0; generated model/recommendation/user decision=0; `orders=0`; `trade_authority=NONE`.

**Scope judgment:** Phase 3A is accepted as `VALIDATED_COMPLETE_SCOPE_BOUNDED`, sufficient to start Phase 3B model-form plumbing. It is not accepted as statistically sufficient historical coverage. `phase3_historical_validation_complete=false` and `phase3f_promotion_eligible=false`; broader date/regime coverage and Phase 3B–3E remain mandatory before Phase 3F can pass.

**Not changed:** no effective Strategy/Core rule, Candidate state, Real/Simulation state, target portfolio, user investment decision, order authority or trade authority changed.

## 2026-08-26 — Phase 3B competing model forms / contract-only acceptance
**Reason:** historical replay would be biased if the Phase-2 probabilistic/vector architecture were treated as the default winner, or if competing models quietly received different evidence. A lower-complexity challenger and an immutable shared-input contract are required before any historical decision replay.

**Implemented:**
- added one `SHARED_OBSERVATION_PACKET` binding the same checkpoint timestamp, opportunity set, Phase 3A selected evidence, structured observations and optional reference asset for every model;
- structured observations must cite `provenance_evidence_ids` already inside the selected Phase 3A snapshot; model-specific evidence fetch is forbidden;
- missing model inputs fail closed as `NOT_EVALUABLE_NO_BACKFILL`;
- fixed exactly three model forms: `LEGACY_POLICY_BASELINE`, `PHASE2_PROBABILISTIC_VECTOR`, and `SIMPLE_NON_PROBABILISTIC_PARETO`;
- Legacy is contemporaneous disposition/state passthrough only and may not be retrospectively reinterpreted;
- the Phase-2 form preserves explicit scenario probabilities and transparent return/downside/confidence/concentration/execution vectors plus Pareto dominance, with no scalar policy score;
- the simple challenger uses explicit non-probabilistic return/downside/evidence-quality/concentration/execution dimensions plus Pareto dominance, so probability assignment and model complexity remain hypotheses rather than baked-in advantages.

**Phase boundary:** Phase 3B does not extract historical source features, replay decisions/capital, calibrate probabilities or parameters, select a winning model, or generate comparative performance conclusions. Those tasks remain Phase 3C/3D.

**Real-seed observation:** the seven Phase 3A checkpoints contain immutable evidence references but no model-neutral structured historical feature layer. Accordingly all 21 model×checkpoint combinations remain 0 evaluable in Phase 3B. This is the required fail-closed result, not a model-performance finding. Synthetic fixtures are used only to prove model mechanics.

**Validation:**
- 23/23 Phase 3B contract/regression tests pass in GitHub Actions;
- 24/24 Phase 3A dependency tests remain green;
- shared input fingerprints are identical across all model forms;
- model-specific evidence fetches=0; retrospective probability/scenario backfills=0;
- scalar policy scores=0; target weights=0; recommendations/user decisions=0; `orders=0`; `trade_authority=NONE`.

**Promotion consequence:** Phase 3B is accepted as `VALIDATED_COMPLETE_CONTRACT_ONLY`, sufficient to start Phase 3C point-in-time feature extraction and decision/capital replay. `phase3_historical_validation_complete=false`, `phase3f_promotion_eligible=false`, Phase 4 entry remains forbidden, and Phase 5 remains unauthorized.

**Not changed:** no effective Strategy/Core rule, Candidate state, Real/Simulation state, target portfolio, user investment decision, order authority or trade authority changed.

## 2026-08-26 — Phase 3C bounded replay / candidate-input blocker
**Reason:** Phase 3B proved only the competing model contracts. Phase 3C must determine whether those model forms can actually be replayed from contemporaneously available historical evidence without hindsight or analyst-filled inputs.

**Implemented:**
- added a model-neutral historical feature extractor that reads only exact Phase 3A registered `commit_sha:path` sources via `git show`;
- all source access occurs before model execution and every extracted field retains checkpoint-local provenance;
- added a bounded replay harness that feeds the same immutable packet to Legacy, Phase-2 probabilistic/vector and simple non-probabilistic/Pareto forms;
- added a full-history GitHub Actions workflow plus 19 Phase 3C tests and a real seven-checkpoint acceptance validator;
- fixed two implementation-only defects found by CI before real replay: the 3A wrapper-to-list API adapter and standalone validator import bootstrap. Neither defect affected historical content or model semantics.

**Real bounded result:**
- all 29 registered Phase 3A historical sources were successfully read at their exact registered commits/paths across seven checkpoints;
- Legacy evaluable security×checkpoint instances = **29**;
- Phase-2 probabilistic/vector evaluable instances = **0**;
- simple non-probabilistic/Pareto evaluable instances = **0**;
- subjective feature fills=0; model-specific evidence fetches=0; retrospective probability backfills=0; retrospective scenario backfills=0;
- Phase 3C tests 19/19 PASS; Phase 3B dependency tests 23/23 PASS; Phase 3A dependency tests 24/24 PASS; `PROGRAM_CONSISTENCY_PASS`.

**Interpretation:** the point-in-time replay infrastructure is valid and Legacy historical states are mechanically reproducible, but the registered historical corpus does not contain the complete explicit contemporaneous input packet required by either candidate model. This is a historical input availability / model replayability finding, not evidence that Legacy outperforms either candidate. No comparative return, regret, calibration or winner conclusion is permitted from a 29-vs-0/0 replay set.

**Gate consequence:** Phase 3C is **in progress**, not complete. Phase 3D remains blocked. The next 3C step is to search for independently provable contemporaneous missing inputs and register them only if they genuinely existed; if they did not exist, the affected model must be recorded as historically non-replayable for this window rather than supplied with retrospective probabilities/scores. Any new transformation from raw facts into probability/confidence or simple-Pareto dimensions would change the model/input contract and requires separate governed design treatment.

**Not changed:** the macro Phase 0→5 lifecycle and internal Phase 3A→3F sequence remain unchanged. No effective Strategy/Core rule, Candidate state, Real/Simulation state, target portfolio, user investment decision, recommendation, order authority or trade authority changed; `orders=0`, `trade_authority=NONE`.

## 2026-08-26 — Phase 3C Canonical-tree replayability audit / terminal negative closeout
**Reason:** the bounded replay showed 29 Legacy-evaluable instances but 0/0 candidate-model instances. Before treating that asymmetry as a model-form finding, Phase 3C had to rule out the simpler explanation that complete contemporaneous candidate inputs existed elsewhere in the Canonical checkpoint trees but had been omitted from the Phase 3A registry.

**Audit:**
- scanned the complete Canonical checkpoint trees for all seven replay commits under `investment_os_runtime`, `evidence`, and `outputs`;
- used exact candidate-model field signatures and separately tracked proxy-like legacy fields without remapping them;
- inspected **673** keyword-candidate file occurrences, including **114** exact-model-field file occurrences and **147** proxy-like legacy-field file occurrences;
- complete Phase-2 probability/vector packet occurrences = **0**;
- complete simple-Pareto five-field packet occurrences = **0**;
- unregistered complete Phase-2 packet occurrences = **0**;
- unregistered complete simple-Pareto packet occurrences = **0**.

**Conclusion:** `NO_COMPLETE_CANDIDATE_MODEL_INPUT_PACKET_FOUND_IN_CANONICAL_CHECKPOINT_TREES`. The candidate replay blocker is not a Phase 3A registration omission. `PHASE2_PROBABILISTIC_VECTOR` is historically non-replayable on the bounded corpus without retrospective input creation, and `SIMPLE_NON_PROBABILISTIC_PARETO` is historically non-replayable without new transformation rules. Existing proxy-like fields remain historical facts and may not be relabelled as the fixed Phase 3B model inputs.

**Phase 3C closeout:** Phase 3C is accepted as `COMPLETE_BOUNDED_REPLAY_TERMINAL_NONREPLAYABILITY_FINDING`. This completion is a negative replayability/input-burden finding, not a performance conclusion. No model winner is selected and no comparative regret/calibration result exists.

**Downstream gate:** Phase 3D remains **BLOCKED** under the existing plan because neither candidate model has a valid contemporaneous replay set. A separate governed post-3C evaluation-path decision is required before Phase 3D can start. This closeout does not silently rewrite Phase 3B or alter the Phase 3A→3F sequence.

**Workflow hygiene / corrections:** the recovery process briefly reintroduced a duplicate Phase 3C workflow; it was detected and removed, leaving `.github/workflows/strategy-kernel-phase3c-historical-replay.yml` as the single authoritative Phase 3C workflow. The first replayability-audit run also exposed a direct-execution import-path harness bug, which was fixed without changing audit semantics. The optimized tree audit then passed on GitHub Actions run #24 / `32951389195` together with 19/19 Phase 3C tests, 23/23 Phase 3B dependency tests, 24/24 Phase 3A dependency tests and `PROGRAM_CONSISTENCY_PASS`.

**Not changed:** the macro Phase 0→5 lifecycle and internal Phase 3A→3F decomposition remain unchanged. No effective Strategy/Core rule, Candidate state, Real/Simulation state, target portfolio, user investment decision, recommendation, order authority or trade authority changed; `orders=0`, `trade_authority=NONE`.

## 2026-08-26 — Governed Post-3C Evaluation Path Decision
**Trigger:** Phase 3C completed with a genuine bounded negative replayability finding: Legacy has 29 replayable instances, both fixed candidate forms have 0, and full Canonical-tree audit proved that no complete registered or unregistered candidate packet existed.

**Decision:** approve `PHASE3D_NEGATIVE_RESULT_MEASURABILITY_THEN_PHASE3E_ABLATION`.

**Rejected:** retrospective input synthesis; silent Phase 3B contract rewrite; skipping Phase 3D.

**Phase 3D treatment:** 3D may start only in `NEGATIVE_RESULT_MEASURABILITY_AND_REGRET_OBSERVABILITY` mode. Evaluation horizons, outcome definitions and reference conventions must be fixed before realized outcomes are loaded. Legacy metrics may be measured where supported. Candidate metrics dependent on absent historical outputs must be `NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS`. Hypothetical candidate decisions, synthetic candidate return/regret/calibration values and cross-model winner selection are forbidden.

**Phase 3E treatment:** Phase 3C non-replayability becomes valid complexity/input-burden evidence. Any materially revised model form must be versioned and return through governed Phase 3B contract definition and Phase 3C replay. The same seven seed checkpoints may not be outcome-tuned and then represented as independent validation; broader or holdout historical validation is required.

**Phase 3F consequence:** promotion to Phase 4 requires at least one historically replayable candidate, measurable 3D evidence, accepted 3E robustness and broader historical coverage. If no candidate becomes historically evaluable, only `REJECT_V2_FORM` or `CONTINUE_SHADOW_RESEARCH` are permitted.
**Not changed:** macro lifecycle Phase 0→5 and Phase 3 sequence 3A→3F remain unchanged. No effective policy/economic state changed; `orders=0`, `trade_authority=NONE`.

## 2026-08-26 — Phase 3D bounded negative-result measurability closeout
**Reason:** Phase 3C proved both candidate forms historically non-replayable, so 3D could not honestly fabricate candidate outcomes merely to complete calibration/regret analysis. The governed Post-3C decision therefore authorized only negative-result measurability and outcome observability.

**Contract and execution:**
- froze 1/3/5 exchange-session horizons, entry/outcome conventions, source fallback and missing-data policy before any realized outcomes were loaded;
- required absent candidate metrics to remain `NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS`;
- audited repository-governed market history first, then used reputable historical daily-close data only where the frozen horizon required missing daily observations;
- horizon changes after outcome loading = 0; retrospective candidate-output synthesis = 0.

**Result:**
- 29 Legacy instance observations were reconstructed mechanically from Phase 3C;
- 100 candidate security×model×checkpoint records remained performance-nonmeasurable;
- 5 Legacy `RETAINED` forward-price observations were measurable, all repeated 601138 checkpoints;
- 16 `NO_ACTION` plus 7 `PRIORITIZED` rows were opportunity observations only;
- one simulation `REDUCED` posture remained observation-only because no executed counterfactual existed;
- measurable regret = 0; measurable calibration = 0; candidate comparative performance unavailable; winner selection forbidden.

**Interpretation:** 3D answered the measurability question but did not establish a candidate-vs-Legacy performance ranking. Repeated 601138 retained-return observations are descriptive diagnostics, not independent trials or promotion evidence.

**Promotion consequence:** Phase 3E may start under the Post-3C loopback guard. `phase3f_promotion_eligible=false`; Phase 4 remains unavailable and Phase 5 unauthorized.

**Not changed:** no effective policy, Candidate membership, Real/Simulation position, target portfolio, user investment decision, recommendation, order authority or trade authority changed; `orders=0`, `trade_authority=NONE`.

## 2026-08-26 — Phase 3E structural ablation / robustness closeout
**Reason:** Phase 3C/3D showed that fixed candidate models could not be historically replayed or performance-compared. Phase 3E therefore tested whether that failure could be attributed to one isolated model requirement without using realized returns to tune a replacement model.

**Governed contract:**
- reused the exact Phase 3A/3C point-in-time corpus;
- excluded Phase 3D realized returns from ablation selection and requirement tuning;
- preserved fixed Phase 3B model identities;
- removed exactly one required component at a time;
- prohibited proxy substitution, subjective remapping, retrospective probability/confidence/cost-score creation, revised-model execution, same-seed performance claims and winner selection.

**Result:**
- 7 checkpoints, 33 feature-security instances and 29 exact historical source reads;
- Phase-2 baseline evaluable = 0; four single-component ablations all remained 0;
- Simple-Pareto baseline evaluable = 0; five single-component ablations all remained 0;
- total single-component ablations = 9; replay unlocks = 0;
- finding = `NO_SINGLE_COMPONENT_ABLATION_RESTORES_HISTORICAL_REPLAY`.

**Robustness interpretation:** related contemporaneous information is not absent. Scenario context appears in 5 instances, return context in 20, confidence context in 20, concentration context in 8, execution context in 8, evidence-quality context in 26 and downside context in 26. But these proxy-like observables are not contract-equivalent to the fixed Phase 3B fields and may not be silently substituted. Non-replayability is therefore best treated as a multi-input contract burden / structural schema mismatch rather than a single-field defect.

**Model-revision consequence:** no revised candidate model was created in 3E. Any material redesign requires a new model/version identity and must return through governed 3B contract definition and 3C replay. The seven seed checkpoints may not be outcome-tuned and then presented as independent validation; broader or holdout history remains required.

**Phase 3F consequence:** Phase 3F may now start procedurally, but promotion eligibility remains false. Under current evidence only `REJECT_V2_FORM` or `CONTINUE_SHADOW_RESEARCH` are valid gate outcomes; `PROMOTE_TO_PHASE_4_FORWARD_VALIDATION` remains blocked because there is no historically replayable candidate, no measurable candidate 3D performance evidence and no broader historical coverage.

**Not changed:** no effective Core Static rule, Candidate state, Real/Simulation state, target portfolio, user decision, recommendation, order authority or trade authority changed; `orders=0`, `trade_authority=NONE`.

## 2026-08-26 — Phase 3F Historical Promotion Gate / negative closeout
**Reason:** Phase 3A–3E completed the bounded historical program, but Phase 4 entry requires a separate formal gate. The gate must not equate absence of measurable candidate outputs with economic underperformance.

**Gate contract:**
- promotion requires all four mandatory requirements: valid candidate point-in-time historical replay, measurable candidate Phase 3D evidence, accepted Phase 3E robustness and broader historical coverage;
- `REJECT_V2_FORM` requires affirmative terminal rejection evidence, not merely failure to qualify for promotion;
- nonmeasurability and current-form nonreplayability are not by themselves economic rejection conclusions;
- any material model revision must receive a new identity and loop back through governed 3B→3C;
- no retrospective input creation, same-seed independent-validation claim, winner selection, economic mutation, order or trade authority is allowed.

**Gate result:**
- candidate historical replay = **FAIL**, 0 replayable candidate instances;
- candidate 3D measurability = **FAIL**, no comparative performance and 0 measurable candidate metrics;
- Phase 3E robustness = **PASS**, 9 single-component ablations / 0 replay unlocks under frozen no-outcome-tuning rules;
- broader historical coverage = **FAIL**, current evidence remains a seven-checkpoint bounded seed;
- mandatory requirements passed = **1/4**;
- `phase3f_promotion_eligible=false`; `phase4_entry_allowed=false`.

**Terminal-rejection test:** not met. Candidate economic performance is not measurable, no comparative underperformance/winner conclusion exists, and Phase 3E shows adjacent contemporaneous information plus a governed redesign path. The fixed Phase 3B candidate forms are therefore `NOT_PROMOTABLE_IN_CURRENT_FORM`, but a terminal economic rejection claim is unsupported.

**Decision:** `CONTINUE_SHADOW_RESEARCH`.

**Governed continuation:** Phase 3 remains open. A material revision must use a new model/version identity and return through `Phase 3B contract definition → Phase 3C replay`; legitimate broader/holdout historical coverage may also be added without retrospective input creation. Missing 3D/3E evidence must then be regenerated as applicable, and a later 3F gate must pass before Phase 4 begins.

**Not changed:** no effective policy, Candidate membership, Real/Simulation position, target portfolio, user decision, recommendation, order authority or trade authority changed; `orders=0`, `trade_authority=NONE`. Phase 4 remains mandatory but blocked; Phase 5 remains unauthorized.

## 2026-08-27 — Post-3F R2 loopback completion through Phase 3C-R2B and program-plan synchronization

**Reason:** the original Phase 3F promotion gate closed at 1/4 with `CONTINUE_SHADOW_RESEARCH`. Subsequent governed work actually completed the approved new-identity R2 loopback through Phase 3B-R2 and Phase 3C-R2, while the execution-oriented Roadmap and Phase Execution Plan still primarily described the pre-R2 negative-gate state. This synchronization removes that control-document lag before independent holdout work begins.

**Governed R2 path actually completed:**
- PR #311 — Post-3F research path decision approved `NEW_IDENTITY_EVIDENCE_NATIVE_R2_PLUS_INDEPENDENT_HOLDOUT_EXPANSION`;
- PR #312 — Phase 3B-R2 froze `EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2`;
- PR #316 — Phase 3C-R2A accepted exact PIT reconstruction on the seven development checkpoints; R2.0.1 canonical-prefix patch retained 20 transform rules and used no outcomes;
- PR #318 — Phase 3C-R2B accepted the first real R2 mechanical replay and full audit.

**Accepted R2B result:** 7 checkpoints, 29 exact registered historical source reads, 33 profiles, 26 comparison-contract-evaluable profiles, 15 exact-signature groups, 9 comparable groups, 6 singleton groups, 20 comparable profile instances, 26 directional Pareto pair checks, 4 dominance edges, 17 local frontier instances, 3 dominated instances, 0 transform failures, 0 outcomes and 0 holdout records. Classification = `PASS_MECHANICAL_REPLAY_OPERATIONAL`.

**Interpretation:** this proves bounded development-corpus R2 replay operability only. It is not historical performance evidence, independent validation, a global winner, Phase 3 completion or Phase 4 eligibility.

**Remaining Phase 3 execution path is frozen as:**
`Independent Point-in-Time Holdout Coverage → Phase 3D-R2 measurability/performance if supported → Phase 3E-R2 robustness if supported → Repeat Phase 3F Historical Promotion Gate`.

**Explicit anti-drift rules:**
- Holdout is not Phase 3G;
- no Phase 3C-R2C round is authorized;
- Holdout may not directly promote to Phase 4;
- the seven development checkpoints may not be relabeled as independent holdout;
- R2-specific 3D/3E evidence must be produced where measurable/supported and must otherwise remain explicitly nonmeasurable/insufficient;
- a repeat Phase 3F gate is mandatory;
- only a later 4/4 promotion PASS may authorize Phase 4;
- no macro lifecycle change is made.

**Control synchronization:** `DEVELOPMENT_ROADMAP.md` and `PHASE_EXECUTION_PLAN.md` are updated to the accepted R2B state and remaining Phase 3 path. `MASTER_PROGRAM_CHARTER.md` and `PROGRAM_CONTRACT.json` require no macro change because their Phase 0→5 lifecycle and Phase 3 loopback rules were already correct.

**Not changed:** no effective policy, Candidate membership, Real/Simulation position, target portfolio, user decision, investment recommendation, order authority or trade authority changed. `phase3_historical_validation_complete=false`, `phase4_entry_allowed=false`, `orders=0`, `trade_authority=NONE`.

## 2026-08-27 — Independent PIT Holdout H0 selection/sufficiency contract freeze

**Reason:** R2B established mechanical replayability on the seven development checkpoints, but those checkpoints cannot count as independent validation. Before building any Holdout checkpoint ledger or observing any Holdout R2 result, the selection universe, deterministic selector and quantitative sufficiency gate must be frozen.

**Frozen universe:** protected `main` ancestry from `6323f4c0617b3df3907b4e76c36b441d666fc4b0` through `5c5df9082688f65332c79fef3b9cbfa893a06908`. Open PR heads and future commits are excluded from Holdout V1. All seven Phase 3A seed checkpoint commits are explicitly excluded.

**Selector:** census of all eligible distinct decision-evidence fingerprints. Pure docs/CI/infrastructure changes without a decision-evidence fingerprint change do not become checkpoints. All eligible fingerprints must be selected; discretionary subsampling, random sampling and manual cherry-picking are forbidden.

**Outcome/model firewall:** selection may not read realized outcomes or Phase 3D results, compute R2 profile values, run R2 Pareto replay, use future returns/regret/calibration or include/exclude checkpoints based on expected R2 behavior.

**Quantitative sufficiency:** all must pass — minimum 12 checkpoints, 6 distinct UTC dates, 4 ISO weeks, 4 distinct evidence-regime signatures, 6 unique securities, 48 opportunity-profile instances, and at least 2 checkpoints outside the original seed time span; concentration caps are 40% per UTC date and 50% per evidence regime.

**Next gate:** H1 may build the deterministic Holdout candidate ledger and evaluate selection sufficiency only. R2 replay remains forbidden until H1 acceptance.

**Not changed:** Holdout is not Phase 3G, direct Holdout→Phase4 remains forbidden, Repeat Phase 3F remains mandatory, `phase3_historical_validation_complete=false`, `phase4_entry_allowed=false`, `orders=0`, `trade_authority=NONE`.

## 2026-08-27 — Holdout H0.1 pre-selection feasibility correction

**Finding before H1:** the frozen Holdout V1 universe ends exactly at the last development-seed timestamp. Availability-only source-history inspection showed that before the first seed, Candidate state plus at least one frozen research/decision family coexist at only one distinct eligible fingerprint (Core2 at 2026-07-26T11:58:08Z). Therefore the H0 requirement for at least 2 checkpoints strictly outside the full seed time span was impossible by construction.

**Correction:** `minimum_checkpoints_strictly_outside_seed_time_span: 2 → 1`.

**Why this is not result tuning:** H1 had not started, no Holdout candidate ledger existed, R2 Holdout replay count remained 0 and realized outcomes used for selection remained 0. The correction used source-availability metadata only. All other frozen gates remain unchanged: >=12 checkpoints, >=6 UTC dates, >=4 ISO weeks, >=4 evidence regimes, >=6 securities, >=48 opportunity-profile instances, <=40% single-date concentration and <=50% single-regime concentration.

**Boundary:** no selector result, R2 output, outcome, Phase 4 authority or economic/trading state changed.

## 2026-08-27 — Independent PIT Holdout H1 deterministic census result

**Result:** `FAIL_SELECTION_SUFFICIENCY`.

The H0/H0.1 selector was executed on protected-main first-parent history only. It selected **8** distinct canonical decision-evidence fingerprints. Coverage observed: 8 UTC dates, 5 ISO weeks, 6 evidence-regime signatures, 8 securities, 64 opportunity-profile instances, 1 checkpoint outside the original seed span, 12.5% maximum single-date concentration and 37.5% maximum single-regime concentration.

**Only failed frozen requirement:** `minimum_holdout_checkpoints = 12`; observed = 8. Every other H0.1 sufficiency condition passed.

**Selection integrity:** 7 seed commits were excluded; 30 first-parent commits were structurally ineligible; 99 had no frozen decision-evidence fingerprint change; no seed source-identity set was selected. R2 profile computation/replay and realized-outcome reads remained zero.

**Governed consequence:** H2 Frozen R2 Replay is blocked. The checkpoint threshold is not relaxed after observing H1. Further work must remain inside Independent Holdout Coverage and use a new pre-result coverage-expansion contract version before any new selection result. Phase 3D-R2, Phase 3E-R2, repeat Phase 3F and Phase 4 remain downstream and blocked.

**Evidence:** selection ledger SHA-256 `bc918818c6b2e59ee48c6b13769330e6a34b7cee011a3c0337efc24351be09d5`; workflow artifact ID `9631813910`, digest `sha256:13a127667aefc29c60b45433c4c8826852a35b90813a7d579a93a70c9cddd2a9`.

## 2026-08-27 — Independent PIT Holdout Coverage Expansion V2 pre-result contract freeze

**Trigger:** H1 returned `FAIL_SELECTION_SUFFICIENCY` solely because 8 canonical checkpoints were below the frozen minimum of 12. No H1 threshold is relaxed.

**Universe and selector preserved:** protected-main time universe remains `6323f4c0617b3df3907b4e76c36b441d666fc4b0 → 5c5df9082688f65332c79fef3b9cbfa893a06908`; first-parent census selection, seven-seed firewall, exact seed-source-set exclusion and all H0.1 quantitative thresholds remain unchanged.

**Coverage-only expansion:** preserve all V1 families and add exactly four substantive model-neutral governed states: `RESEARCH_OBJECTS_CURRENT`, `R1_DECISION_COVERAGE_PACK_CURRENT` as decision context only, `RESEARCH_QUEUE_D1_CURRENT`, and `RESEARCH_QUEUE_D2_CURRENT`. Pure liveness, lineage-only evidence, prior Holdout result artifacts, Phase 3D outcomes, future returns, regret/calibration and R2 result artifacts are explicitly excluded from checkpoint creation.

**Security scope:** deterministically normalize and union the V1 8-security scope with security IDs present at the frozen end commit in Research Objects, D1 Current and D2 Current. Frozen V2 research-security scope = **18 securities**. The mixed Real/Simulation fund/ETF IDs inside the R1 decision-coverage pack do not expand the security scope.

**Pre-result firewall:** V2 selection has not started; V2 candidate ledger = 0; R2 profile compute = 0; R2 Holdout replay = 0; realized outcome/future return/Phase 3D reads = 0. Result-based family/security additions, threshold relaxation and R2 transform/signature changes are forbidden.

**Next gate:** after remote acceptance of this contract, run V2 deterministic selection only. H2 remains blocked unless the unchanged 12-checkpoint/multi-axis sufficiency gate passes. Phase 3D-R2, Phase 3E-R2, repeat Phase 3F and Phase 4 remain blocked.

**Authority:** no effective-policy, Candidate, Real/Simulation, target-portfolio, user-decision, investment-recommendation, order or trade-authority mutation. `phase3_historical_validation_complete=false`, `phase4_entry_allowed=false`, `orders=0`, `trade_authority=NONE`.

## 2026-08-27 — Independent PIT Holdout V2 deterministic selection result

**Result:** `PASS_SELECTION_SUFFICIENCY` under the already accepted V2 pre-result contract.

Observed coverage: **14** canonical first-parent checkpoints, **10** UTC dates, **5** ISO weeks, **9** evidence-regime signatures, **18** research securities, **252** opportunity-profile instances, **4** checkpoints outside the original seed span, **21.43%** maximum single-date concentration and **28.57%** maximum single-regime concentration. Every unchanged H0.1 sufficiency requirement passed, including the preserved minimum checkpoint requirement of 12.

**Selection integrity:** 7 seed commits excluded; 1 structurally ineligible commit; 122 first-parent commits with no frozen fingerprint change; 14 selected. No threshold, family, security scope, model transform or comparison signature changed after the result. R2 profile compute/replay, Phase 3D result reads, realized outcomes, future returns, regret/calibration and manual/random/discretionary subsampling all remained zero.

**Evidence:** V2 selection ledger SHA-256 `241bb441a960b2ccfb46a708ae81f7b38d5b2389215362406255cd4945b337be`; workflow artifact ID `9632556105`; artifact digest `sha256:73b9bb0734848537ced9078a924020522607eff266e12bbee775d10c98b4f51d`.

**Governed consequence:** H2 Frozen R2 Holdout Replay is now authorized but not started. This is not a Phase 4 authorization and does not complete Phase 3 historical validation. Phase 3D-R2, Phase 3E-R2 and repeat Phase 3F remain downstream; Phase 4 remains blocked.

**Authority:** no effective policy, Candidate, Real/Simulation, target-portfolio, user-decision, investment-recommendation, order or trade-authority mutation. `orders=0`, `trade_authority=NONE`.

## 2026-08-27 — Independent PIT Holdout Frozen R2 Replay final acceptance

**Result:** `PASS_INDEPENDENT_HOLDOUT_REPLAY_OPERATIONAL` under the replay contract frozen before first execution.

The accepted V2 14-checkpoint selection was rebuilt deterministically. Replay used exactly **26/26** unique registered source identities and the unchanged `R2.0.1_RESEARCH` 20-rule transform catalog. V2 coverage-only families remained in the shared PIT packet but gained no new R2 feature semantics.

**Replay evidence:** 14 checkpoints, 105 R2 profiles, 94 comparison-contract-evaluable profiles, 561 present dimensions, 1539 explicit missing dimensions, 0 transform failures, 8 distinct comparison signatures, 36 exact-signature groups, 27 comparable groups, 9 singleton groups, 85 comparable profiles, 220 directional Pareto pair checks, 54 dominance edges, 57 local frontier profiles, 28 dominated profiles and 0 audit errors. Unsupported selected evidence instances retained for audit = 61.

**Outcome firewall:** realized outcomes = 0; Phase 3D result reads = 0; future returns/regret/calibration = 0; historical performance metrics = 0. No model transform, threshold, feature mapping, comparison signature, Holdout membership or security scope changed after the result.

**Evidence:** replay SHA-256 `5b66a60eabe2c294d2a396b5fbae74ba19769376d01f5fec77a012461e1a4aaa`; workflow artifact ID `9633465873`; artifact digest `sha256:17fb6fa2c122fd1542757a9cf887eb14a9ff0a99d113bce05ddb6e5e6f53f9ff`.

**Governed consequence:** Independent Holdout replay/final acceptance is complete. Phase 3D-R2 is authorized **if measurable** but has not started. Phase 3E-R2, repeat Phase 3F and Phase 4 remain blocked. `phase3_historical_validation_complete=false`, `phase4_entry_allowed=false`, `orders=0`, `trade_authority=NONE`.

## 2026-08-27 — Phase 3D-R2 Round 1 measurability contract and evidence audit

**Parent:** Independent PIT Holdout final acceptance PR #325 @ `4ac3d7d25ed65fd77747addbcbbd21ea47679332`.

**Contract freeze:** before any R2 realized-return or performance calculation, the economic evaluation unit was frozen as the checkpoint-local exact-signature dominance edge. A dominance edge is not a trade, a local Pareto frontier is not a global winner, and no position size, target weight or P&L is inferred.

**Outcome convention:** reuse the pre-existing 1/3/5 exchange-trading-session convention; endpoint metric is local-currency price return and the only pairwise economic relation eligible for later testing is dominator return minus dominated return. No benchmark adjustment, FX translation, Sharpe, assumed-trade hit rate, probability calibration, unsupported regret, scalar score or winner selection is authorized.

**Evidence-readiness gate:** all 54 frozen dominance edges and both endpoints must have valid entry/horizon closes for all fixed horizons, exchange-session schedules, explicit corporate-action status and source lineage. Result-based edge dropping and proxy filling are forbidden. Partial evidence may be described but may not support an R2 performance claim.

**Observed Round 1 result:** `PARTIAL_R2_MEASURABILITY_OUTCOME_EVIDENCE_ACQUISITION_REQUIRED`. The R2 relation population is structurally measurable: 54 frozen dominance edges, 55 checkpoint-security endpoint instances and 7 distinct endpoint securities. Existing governed outcome inventory provides any price observation for only 3/7 endpoint securities; 4/7 have none. Exchange-session schedule readiness is 0/7, explicit corporate-action-status readiness is 0/7, and complete evidence coverage is 0/54 edges. Audit errors = 0.

**Evidence:** audit SHA-256 `f1cc459b3d739afb12d55efa341783b69b8a8a647e209a020a6f8ee11662ad92`; workflow run `33044583361`; artifact ID `9635188727`; artifact digest `sha256:0ea0d78a43667099893fb0fb610b46a1c7a0797f604b8cf6ca6a7033bc115783`.

**Governed consequence:** Phase 3D-R2 has started only through its Round 1 measurability/evidence audit. Performance remains **NOT STARTED / NOT AUTHORIZED**. Next = `PHASE_3D_R2_OUTCOME_EVIDENCE_ACQUISITION`. The PARTIAL result is explicitly not economic underperformance. Phase 3E-R2 and repeat Phase 3F remain not started; Phase 3 historical validation remains incomplete; Phase 4 remains blocked.

**Authority:** no model transform/signature mutation, Holdout membership mutation, Candidate/Real/Simulation mutation, target-portfolio writeback, recommendation, order or trading authority. `orders=0`, `trade_authority=NONE`.


## 2026-08-27 — Phase 3D-R2 Outcome Evidence Acquisition final acceptance

**Parent:** Phase 3D-R2 Round 1 PR #327 @ `bfa6afe2bc0c7a349d82a7a91afe54daea82724c`.

**Result:** `PASS_R2_OUTCOME_EVIDENCE_READY_FOR_PERFORMANCE` under the acquisition contract frozen before any R2 return or performance calculation.

**Coverage:** 55/55 checkpoint-security endpoint instances complete; 54/54 frozen dominance edges complete; 7/7 endpoint securities supported by the selected `sina_daily` unadjusted CNY close route; 55/55 corporate-action windows = `NO_ADJUSTMENT_FACTOR_CHANGE_OBSERVED`; support reconciliation disagreement endpoints = 0; integrity errors = 0.

**Timing semantics:** 15:30 Asia/Shanghai conservative settled-close cutoff; fixed +1/+3/+5 exchange-session horizons. The 15:00:26 checkpoint remains bound to the prior settled close rather than same-day close.

**Evidence:** ledger SHA-256 `300db34b408e7ca2cfeb188b8c6177b62bdff70743a2cf6fb2c833bf3bda1d1b`; workflow run `33047195178`; artifact ID `9636254690`; artifact digest `sha256:ffeee9e17bde1bca96b06d8c1dccd1932e82884846f27eabbed3fc1e69dcd952`. A compact frozen pack is committed for downstream deterministic consumption; downstream performance code may not re-fetch or replace these outcome inputs.

**Governed consequence:** `phase3d_r2_performance_start_allowed=true`, `phase3d_r2_performance_started=false`; next = `PHASE_3D_R2_PERFORMANCE_MEASUREMENT`. Phase 3E-R2 and repeat Phase 3F remain not started. Phase 3 historical validation remains incomplete; Phase 4 remains blocked.

**Authority:** return calculations = 0; performance metrics = 0; no model/signature/edge/Holdout mutation; no Candidate/Real/Simulation/target-portfolio mutation; `orders=0`; `trade_authority=NONE`.


## 2026-08-27 — Phase 3D-R2 deterministic performance measurement

**Parent:** Outcome Evidence final acceptance PR #328 @ `59359979a5db17181b3fd93d6be8ef6fe5295877`.

**Pre-result contract:** PR #329 first froze the measurement population, formulas, equal-edge descriptive aggregation, tie rule, dependence warning and forbidden inference/mutation rules before the first deterministic performance result. A first implementation attempt failed before any measurement because an acquisition-module import pulled in `akshare`; the implementation was corrected to an offline-only frozen-pack consumer before the first measurement result.

**Result:** `COMPLETE_R2_DETERMINISTIC_PERFORMANCE_MEASUREMENT_DESCRIPTIVE_ONLY`.

**Coverage:** 165/165 endpoint-return records; 162/162 edge-horizon records; 54 frozen dominance edges; 13 edge-bearing checkpoints; 2 exact comparison signatures; integrity errors = 0.

**Horizon summaries:**
- +1 session: 34/54 concordant = 62.96296%; mean edge spread +0.02764%; median +0.23793%.
- +3 sessions: 29/54 concordant = 53.70370%; mean edge spread +0.10409%; median +0.42880%.
- +5 sessions: 27/54 concordant = 50.00000%; mean edge spread -0.06382%; median +0.02734%.
- pooled 1/3/5: 90/162 concordant = 55.55556%; mean spread +0.02264%. This pooled figure is descriptive only; repeated edges, securities, checkpoints, signatures and nested horizons are not independent observations.

**Evidence:** measurement SHA-256 `a3e474745dc8074be363f3d9b8e7082923bd67adeff6c6e42431e1f6a406edad`; workflow run `33049802795`; artifact ID `9637187877`; artifact digest `sha256:83033d2c3a5fb55412717d15bea99fac063f35fa8175699d2392e455662e1a8f`.

**Interpretation boundary:** this is real R2 historical performance evidence, but only in the frozen edge-association sense. It is not a trade/PnL result, statistical-significance result, scalar model score, global winner, or Phase 4 promotion result. The horizon pattern is mixed and horizon-sensitive; no numeric Phase 3E support threshold had been frozen before observation.

**Governed consequence:** Phase 3D-R2 is COMPLETE. Phase 3E-R2 remains NOT STARTED / NOT YET AUTHORIZED. Next = `PHASE_3E_R2_STRUCTURAL_SUPPORT_GATE_CONTRACT`. That gate must be result-value-blind: it may use measurement completeness/integrity and robustness evaluability, but may not invent concordance/spread cutoffs after seeing these values. Repeat Phase 3F remains mandatory; Phase 4 remains blocked.

**Authority:** no model/transform/signature/Holdout/edge mutation; no Candidate/Real/Simulation/target-portfolio mutation; no recommendations, orders or trade authority. `orders=0`, `trade_authority=NONE`.


## 2026-08-27 — Phase 3E-R2 Round 0 structural support gate

**Parent:** accepted Phase 3D-R2 performance PR #329 @ `fdd638bd100ee6ecf60eac938e852b00052c0e33`.

**Pre-execution discipline:** the support contract was frozen before any R2 robustness execution and explicitly prohibited reading observed endpoint returns, edge spreads, horizon concordance rates or horizon performance ordering. Gate decision inputs were limited to accepted parent identity/SHA, completeness counts, structural population counts, cluster multiplicity, robustness-axis feasibility and authority boundaries.

**Result:** `PASS_R2_STRUCTURAL_SUPPORT_FOR_ROBUSTNESS`; 5/5 predefined robustness axes structurally evaluable; gate result-value reads = 0; post-result numeric thresholds created = 0.

**Frozen robustness plan:** horizon stratification; 13 checkpoint jackknifes; 7 security jackknifes; 2-signature stratification/jackknife; equal-edge/equal-checkpoint/equal-signature weighting sensitivity. One axis at a time only; simultaneous multi-axis search and result-driven subset selection are forbidden.

**Evidence:** gate SHA-256 `c6288bb86700af9de8089fd14e1be379bb1beef4d4eeb537cf1f2e471c37d404`; workflow run `33051990001`; artifact ID `9638041520`; artifact digest `sha256:119fa1175720cdcf83058a8b5b2e8068c31fc0d5fcf52d0d5a1c42c9b17d9d42`.

**Meaning:** PASS authorizes execution of the frozen robustness program only. It is not an economic-performance endorsement, robustness conclusion or Phase 4 promotion.

**Governed consequence:** `phase3e_r2_start_allowed=true`; `phase3e_r2_robustness_execution_start_allowed=true`; robustness not yet started; next = `PHASE_3E_R2_ROBUSTNESS_EXECUTION`. Repeat Phase 3F remains not started and mandatory. Phase 4 remains blocked. `orders=0`, `trade_authority=NONE`.


## 2026-08-27 — Phase 3E-R2 predefined robustness execution accepted

**Parent:** accepted structural support PR #330 @ `47cf9df36f6a541a6f58ecd4487c67e91e26f1bf`.

**Execution:** all five predeclared one-axis-at-a-time robustness tests completed: 1/3/5-session horizon stratification; 13 checkpoint jackknifes; 7 security jackknifes; 2-signature stratification/jackknife; and 9 equal-edge/equal-checkpoint/equal-signature × horizon weighting records. Integrity errors = 0.

**Evidence:** robustness SHA-256 `6cbd096716dc577dc643577795556d765d452b50a09f2e05ee5f253bd1b7e32f`; workflow run `33054269550`; artifact ID `9638968464`; artifact digest `sha256:b066063b230e348e99b115efa1821e4305847caf91930852ed09ff7f3228b6ee`.

**Descriptive sensitivity carried forward:** checkpoint jackknife is comparatively bounded, while security/signature/aggregation weighting materially changes direction and magnitude. The two exact signatures contain 52 and 2 edges. At +1 session, equal-edge = 62.96% concordance / +0.0276% mean spread, equal-checkpoint = 65.38% / +0.1132%, and equal-signature = 32.69% / -0.5001%. Security jackknife ranges widen to 39.29%-73.33% concordance at +3 and +5 sessions. No post-result pass/fail threshold is invented.

**Interpretation:** Phase 3E-R2 is complete and its robustness evaluation is accepted as evidence completion only. Positive robustness, statistical significance, economic winner and Phase 4 promotion are not claimed.

**Governed consequence:** Repeat Phase 3F is mandatory and now start-allowed, but not started. Phase 3 historical validation remains incomplete; Phase 4 remains blocked; `orders=0`; `trade_authority=NONE`.


## 2026-08-27 — Repeat Phase 3F R2 historical promotion gate passed 4/4

**Inherited contract:** `PHASE3F_PROMOTION_GATE_CONTRACT.json`, git blob `4ce0d23558d0fa80cdc9f58004e7e1ab39b077f2`; four mandatory requirements unchanged.

**Result:** 4/4 PASS; `PROMOTE_TO_PHASE_4_FORWARD_VALIDATION`. Gate SHA-256 `af174d3adb0bb70afa306f26fa0c2a66eb925e04421962dcfae5573b404d22ec`; workflow run `33057016736`; artifact ID `9640103462`; digest `sha256:8c95d53459b5086dd85e4aa94af9573b8d6e44ba64ffbc331ea393c687fd9071`.

**Requirements:** independent R2 PIT replay PASS; Phase 3D-R2 measurable evidence PASS; Phase 3E-R2 robustness evaluation accepted PASS; broader independent Holdout coverage PASS.

**Interpretation:** no post-result promotion threshold was created. Phase 3E-R2 sensitivity remains material and must be carried into Phase 4 design and monitoring.

**Governed consequence:** Phase 3 historical validation complete; Phase 4 entry/start allowed; Phase 4 not started; orders=0; trade_authority=NONE.


## 2026-08-27 — Phase 4 forward-shadow validation contract frozen before execution

PR #333 candidate head `b856147e151292e7e19d59c4a0f05d07c90b4757` passed 26/26 exact-head workflows with zero failures. Dedicated Phase 4 contract workflow `33078290558` passed contract tests, contract validation, Repeat Phase 3F revalidation, historical Phase 3F revalidation and program consistency.

The semantic contract Git blob `82ddfa6967a092d971093f5855ffc80b13acd706` and candidate-head commit time `2026-08-27T13:42:29Z` are frozen. Only source evidence strictly after that timestamp may count as Phase 4 forward validation. Frozen runner set = Legacy baseline + R2.0.1. Frozen sufficiency, 1/3/5-session measurement, three aggregation schemes, per-signature directionality and security/signature jackknife requirements may not be changed after forward results.

No forward observation or realized outcome has yet been loaded. Phase 4 execution remains not started; Phase 5 remains unauthorized; orders=0; trade_authority=NONE.


## 2026-08-28 — Phase 4 P4-1 production acceptance and P4-2 funnel contract freeze

**P4-1 closeout:** main-based Operating Current implementation PR #340 and fail-closed Cross-market hotfix PR #341 were merged. The live `operating-current` branch was created and remotely read back; first real D2 producer run `33138552337` succeeded; atomic bootstrap `d019b13455d3f65cb68cd9702a9d1b110e6d0e25` exposed CURRENT / STALE / MISSING / BLOCKED honestly. Exact source-head checks passed. Simultaneous freshness of all five domains is not a P4-1 completion requirement.

**P4-2 audit:** the repository already contains full-market screening, Candidate dynamic state, Research Queue D1 and D2 capabilities. The existing research-funnel contract explicitly records `FULL_MARKET_AND_CANDIDATE_CAPABILITY_EXISTS_SINGLE_FUNNEL_MANIFEST_PENDING`. Current watermarks are fragmented: full-market screening 2026-08-07, Candidate weekly 2026-08-05, D1 2026-08-11, D2 Operating Current 2026-08-28.

**Frozen P4-2 scope:** unify existing Universe→Longlist→Research Queue→D1→D2 state into one Operating Current funnel plus near-miss ledger. Preserve source-specific watermarks; never synthesize one false as-of date. Zero throughput is allowed only with explicit rejection/hold/no-input reasons. Existing D1 batch capacity 5 and D2 batch capacity 3 are preserved. No new screening score, no R2 change, no Candidate membership automation, no recommendation engine yet, no Real/protected Simulation mutation.

**Acceptance:** at least two distinct source-fingerprint funnel cycles, deterministic rebuild semantics, every zero-output stage explained, near-miss ledger present, stale/blocked source visibility preserved. `orders=0`, `trade_authority=NONE`.

**Next:** one main-based P4-2 operational implementation PR. Phase 4 forward observation hold remains active.
