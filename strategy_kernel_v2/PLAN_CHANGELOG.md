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
