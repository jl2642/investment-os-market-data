# Strategy Kernel v2 — Phase Execution Plan

## Program hierarchy
This document executes, but cannot override, `MASTER_PROGRAM_CHARTER.md` / `PROGRAM_CONTRACT.json`. Macro lifecycle is fixed at Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 unless an explicit governed PROGRAM_AMENDMENT is approved.

## Global acceptance controls
Every phase through Phase 4 preserves `orders=0`, `trade_authority=NONE`, mutation permissions false, Canonical provenance and no direct protected-main write.

## Phase 0 — SYSTEM AUDIT — COMPLETE
Legacy/Core Static baseline inventoried.

## Phase 1 — DECISION & UNDERWRITING — COMPLETE SHADOW
1B Decision Object v2 and 1C Underwriting Extraction complete/validated shadow-only. Missing evidence remains explicit.

## Phase 2 — CAPITAL COMPARISON INFRASTRUCTURE — COMPLETE SHADOW
2A comparator, 2B governed refresh and 2C real-evidence pack are validated. Current real pack remains `NO_COMPARISON`, 0 eligible / 8 blocked, with no fabricated refresh packets.

## Phase 3 — HISTORICAL REPLAY & CALIBRATION — IN PROGRESS / R2 DEVELOPMENT REPLAY COMPLETE / HOLDOUT NEXT / PHASE 4 BLOCKED
Internal order remains exactly `3A → 3B → 3C → 3D → 3E → 3F`. A negative 3F gate may reopen governed Phase 3 research, but may not bypass the fixed macro lifecycle or directly enter Phase 4.

### Phase 3A — Point-in-time Evidence Ledger — COMPLETE_SCOPE_BOUNDED
29 Canonical evidence records, 7 checkpoints, 8 securities, exact commit/availability provenance, no hindsight. Broader history remains required before promotion to Phase 4.

### Phase 3B — Competing Model Forms — COMPLETE_CONTRACT_ONLY
Fixed Legacy, Phase-2 probabilistic/vector and simple non-probabilistic Pareto forms consume the same shared packet. Missing inputs fail closed; retrospective input creation and model-specific evidence fetch are forbidden.

### Phase 3C — Decision / Capital Replay — COMPLETE_TERMINAL_NONREPLAYABILITY
29/29 historical sources read; Legacy produced 29 evaluable instances; both candidate forms produced 0. Full Canonical-tree audit found no complete candidate packet. Non-replayability is an input-burden finding, not comparative performance.

### Governed Post-3C Evaluation Path Gate — ACCEPTED
Approved `PHASE3D_NEGATIVE_RESULT_MEASURABILITY_THEN_PHASE3E_ABLATION`. Retrospective input synthesis, silent 3B rewrite and skipping 3D are rejected.

### Phase 3D — Calibration & Regret Analysis — COMPLETE_BOUNDED_NEGATIVE_RESULT_MEASURABILITY
Mode: `NEGATIVE_RESULT_MEASURABILITY_AND_REGRET_OBSERVABILITY`.

#### 3D-0 Contract freeze — COMPLETE
Before any realized outcome was loaded, fixed:
1. 1/3/5 exchange-trading-session horizons;
2. entry/outcome close-price conventions;
3. source fallback and missing-data treatment;
4. candidate `NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS` sentinel;
5. no winner / no retrospective candidate output / no synthetic regret rules.

#### 3D-1 Outcome source audit — COMPLETE
Repository governed market data were inspected first. The governed 2026-08-25 EOD snapshot did not provide the full daily history needed by the frozen horizons, so reputable historical daily-close data were used under the already-frozen fallback policy. Horizon changes after outcome loading = 0.

#### 3D-2 Deterministic realized-outcome build — COMPLETE
- 29 Legacy instance observations;
- 100 candidate security×model×checkpoint records remain performance-nonmeasurable;
- 14 grouped candidate nonmeasurability records;
- 5 Legacy `RETAINED` forward-price observations;
- 16 `NO_ACTION` and 7 `PRIORITIZED` opportunity-only observations;
- 1 simulation `REDUCED` posture observation only;
- measurable regret = 0;
- measurable calibration = 0.

The five retained rows are repeated 601138 checkpoints, not independent trials. Their descriptive mean price returns are about -0.11% / -2.52% / -5.15% at 1/3/5 sessions. These values are diagnostics only: candidate performance is absent, cross-model comparison is unavailable, statistical significance is not claimed, and no model winner is selected.

Phase 3D completion means the measurability question was answered, not that candidate-vs-Legacy calibration/regret was successfully compared.

### Phase 3E — Ablation / Robustness — COMPLETE_STRUCTURAL_ABLATION
Mode: `STRUCTURAL_INPUT_BURDEN_ABLATION_AND_ROBUSTNESS`.

#### 3E-0 Contract freeze — COMPLETE
Ablation design was fixed independently of Phase 3D realized returns:
1. reuse the exact Phase 3A/3C point-in-time corpus;
2. remove exactly one candidate requirement at a time;
3. preserve fixed Phase 3B model identities;
4. forbid proxy substitution and subjective remapping;
5. forbid retrospective probability/confidence/cost-score creation;
6. forbid revised-model execution, same-seed performance claims and winner selection.

#### 3E-1 Single-component ablation — COMPLETE
Across 7 checkpoints, 33 feature-security instances and 29 exact historical source reads:
- Phase-2 baseline = 0 evaluable;
- drop probability = 0;
- drop confidence = 0;
- drop portfolio concentration cost = 0;
- drop execution friction = 0;
- Simple baseline = 0 evaluable;
- drop return proxy = 0;
- drop downside resilience = 0;
- drop evidence quality = 0;
- drop concentration cost = 0;
- drop execution friction = 0.

Total single-component ablations = **9**; historical-replay unlocks = **0**. Finding: `NO_SINGLE_COMPONENT_ABLATION_RESTORES_HISTORICAL_REPLAY`.

#### 3E-2 Adjacent-observable robustness inventory — COMPLETE
Contemporaneous related information is present without being silently mapped into contract fields:
- scenario context: 5 instances;
- return context: 20;
- confidence context: 20;
- concentration context: 8;
- execution context: 8;
- evidence-quality context: 26;
- downside context: 26.

The result is structural: historical candidate non-replayability reflects a multi-input schema/contract mismatch, not one isolated missing field and not total absence of useful historical information. Adjacent observables are design evidence only and remain non-substitutable.

#### 3E-3 Revision loopback guard — COMPLETE
No revised candidate model is created or executed in 3E. If a materially revised form is later proposed:
- assign a new model/version identity;
- do not overwrite any fixed 3B historical form;
- the revised form must return through governed 3B contract definition and 3C replay before any promotion;
- same-seed outcome tuning cannot be presented as independent validation;
- broader or holdout historical validation is required.

### Phase 3F — Historical Promotion Gate — COMPLETE / CONTINUE_SHADOW_RESEARCH
3F executed the formal gate after 3A–3E completion. Procedural gate completion is not historical validation completion.

#### 3F-0 Gate contract — FROZEN
The gate distinguishes three concepts:
1. qualification for Phase 4;
2. terminal rejection of a candidate family;
3. continued governed research.

Nonmeasurability is explicitly not equivalent to economic underperformance. Candidate non-replayability by itself is not terminal rejection evidence.

#### 3F-1 Mandatory promotion requirements — EVALUATED
For `PROMOTE_TO_PHASE_4_FORWARD_VALIDATION`, all four requirements must pass:
1. at least one candidate has valid point-in-time historical replay — **FAIL**, observed replayable candidate instances = 0;
2. candidate Phase 3D evidence is measurable — **FAIL**, comparative performance unavailable and measurable candidate metric count = 0;
3. Phase 3E robustness is accepted — **PASS**, 9 ablations / 0 unlocks under frozen no-outcome-tuning contract;
4. broader historical coverage exists — **FAIL**, current history remains 7 bounded checkpoints.

Gate result = **1/4 PASS**. `phase3f_promotion_eligible=false`; `phase4_entry_allowed=false`.

#### 3F-2 Terminal rejection test — NOT MET
`REJECT_V2_FORM` requires affirmative terminal evidence such as measurable candidate economic failure, validated structural incoherence with no governed redesign path, or an explicit governed decision to abandon the candidate family.

Current evidence provides none of those:
- candidate economics are not measurable;
- no candidate winner/loser or underperformance conclusion exists;
- Phase 3E found adjacent contemporaneous information and preserves a governed redesign loopback.

Therefore the formal outcome is:

`CONTINUE_SHADOW_RESEARCH`

Current fixed Phase 3B forms are `NOT_PROMOTABLE_IN_CURRENT_FORM`; this is not an authorization to run them in Phase 4.

#### 3F-3 Governed continuation path — REQUIRED
Before any later promotion attempt, one or both of the following must produce genuinely new evidence:
- **model revision path:** create a new model/version identity and loop back through governed `Phase 3B contract definition → Phase 3C replay`; then repeat downstream 3D/3E evidence as applicable;
- **historical coverage path:** add legitimate point-in-time / holdout history without retrospective input creation.

The seven seed checkpoints may not be outcome-tuned and then represented as independent validation. A later 3F re-evaluation is required after missing evidence is produced.

`PROMOTE_TO_PHASE_4_FORWARD_VALIDATION` remains blocked.

`PROMOTE_TO_PHASE_5` is forbidden.

### Governed R2 loopback execution — B/C COMPLETE / HOLDOUT NEXT

#### R2-0 Post-3F path decision — COMPLETE / PR #311
Approved path:
`NEW_IDENTITY_EVIDENCE_NATIVE_R2_PLUS_INDEPENDENT_HOLDOUT_EXPANSION`.

Frozen execution order:
1. R2 architecture/contract freeze;
2. 3B-R2 contract definition;
3. 3C-R2 development-corpus PIT replay;
4. Independent Point-in-Time Holdout Coverage;
5. 3D-R2 measurability/performance if supported;
6. 3E-R2 robustness if supported;
7. Repeat Phase 3F promotion gate.

The seven original checkpoints remain development corpus and may not be relabeled as holdout.

#### R2-1 Phase 3B-R2 — COMPLETE / PR #312
Model identity: `EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2`.

Current research version: `R2.0.1_RESEARCH`.
- frozen transform rules = 20;
- exact-signature Pareto only;
- missingness remains explicit;
- no scalar policy score, weights, ranking or global winner;
- no realized-outcome tuning;
- no Phase 4 authority.

#### R2-2 Phase 3C-R2 — COMPLETE / PR #316 + #318
Phase 3C-R2 has exactly two execution rounds:
- **3C-R2A:** PIT reconstruction only, no Pareto/outcomes/holdout;
- **3C-R2B:** mechanical exact-signature replay + full audit + final acceptance.

Accepted R2B development-corpus result:
- checkpoints = **7**;
- exact source reads = **29**;
- R2 profiles = **33**;
- comparison-contract-evaluable profiles = **26**;
- exact-signature groups = **15**;
- comparable groups = **9**;
- singleton groups = **6**;
- comparable profile instances = **20**;
- directional Pareto pair checks = **26**;
- dominance edges = **4**;
- local frontier instances = **17**;
- dominated instances = **3**;
- transform failures = **0**;
- outcomes = **0**;
- holdout = **0**.

Classification: `PASS_MECHANICAL_REPLAY_OPERATIONAL`.

This closes development-corpus R2 replay only. It does not claim historical performance, independent validation, a global model winner, Phase 3 completion or Phase 4 eligibility.

#### R2-3 Independent Point-in-Time Holdout Coverage — IN PROGRESS / H1 FAILS SUFFICIENCY / COVERAGE EXPANSION NEXT
Before any holdout result is observed, freeze:
1. quantitative sufficiency threshold;
2. checkpoint/date/regime selection rules;
3. disjointness from the seven development checkpoints;
4. outcome-blind selection;
5. exact PIT availability/source provenance requirements;
6. no-later-backfill rule;
7. broader date/regime coverage requirement.

H0 contract freeze is **COMPLETE**:
- frozen protected-main universe: `6323f4c... → 5c5df908...`;
- all seven Phase 3A seed checkpoint commits excluded;
- selector = census of all eligible distinct decision-evidence fingerprints;
- discretionary/random/manual subsampling forbidden;
- realized outcomes, Phase 3D results and R2 replayability/results forbidden during selection;
- minimum coverage = 12 checkpoints / 6 UTC dates / 4 ISO weeks / 4 evidence-regime signatures / 6 securities / 48 opportunity-profile instances;
- at least 1 checkpoint must fall strictly outside the original seed time span; H0.1 corrected the prior impossible value of 2 before H1 selection began, because the frozen universe ends at the last seed and only one eligible pre-first-seed research fingerprint exists;
- no single UTC date may exceed 40% and no single evidence regime may exceed 50% of accepted Holdout checkpoints.

H1 deterministic candidate ledger is **COMPLETE**:
- canonical first-parent Holdout checkpoints = **8**;
- distinct UTC dates = **8**;
- distinct ISO weeks = **5**;
- distinct evidence regimes = **6**;
- unique securities = **8**;
- opportunity-profile instances = **64**;
- outside-seed checkpoints = **1**;
- maximum single-date concentration = **12.5%**;
- maximum single-regime concentration = **37.5%**;
- failed threshold = **minimum_holdout_checkpoints (8 < 12)**;
- all other frozen thresholds = PASS;
- realized outcomes read = 0;
- R2 Holdout replay count = 0.

Therefore H2 is **BLOCKED**.

Coverage Expansion V2 pre-result contract is now **FROZEN**:
- protected-main time universe unchanged: `6323f4c... → 5c5df908...`;
- first-parent census selector unchanged;
- seven development seeds remain excluded;
- minimum checkpoint threshold remains **12** and every other H0.1 threshold is unchanged;
- V1 evidence-family catalog is preserved;
- added substantive model-neutral families = **4**: `RESEARCH_OBJECTS_CURRENT`, `R1_DECISION_COVERAGE_PACK_CURRENT` (context only), `RESEARCH_QUEUE_D1_CURRENT`, `RESEARCH_QUEUE_D2_CURRENT`;
- pure D2 liveness, lineage-only metadata, prior Holdout results, Phase 3D outcomes, future returns, regret/calibration and R2 result artifacts are excluded;
- research-security scope expands deterministically from **8 → 18**, without importing mixed fund/ETF security IDs from the R1 decision-coverage pack;
V2 deterministic selection is **COMPLETE / PASS_SELECTION_SUFFICIENCY**:
- canonical first-parent Holdout checkpoints = **14**;
- distinct UTC dates = **10**;
- distinct ISO weeks = **5**;
- distinct evidence regimes = **9**;
- unique securities = **18**;
- opportunity-profile instances = **252**;
- outside-seed checkpoints = **4**;
- maximum single-date concentration = **21.43%**;
- maximum single-regime concentration = **28.57%**;
- failed thresholds = **none**;
- R2 Holdout replay = **0**;
- realized outcomes read = **0**.

All unchanged H0.1 thresholds pass.

Independent Holdout Frozen R2 Replay is now **COMPLETE / PASS_INDEPENDENT_HOLDOUT_REPLAY_OPERATIONAL**:
- checkpoints reconstructed = **14 / 14**;
- exact source identities = **26 / 26**;
- R2 profile instances = **105**;
- comparison-contract-evaluable profiles = **94**;
- present dimensions = **561**;
- explicit missing dimensions = **1539**;
- transform failures = **0**;
- distinct comparison signatures = **8**;
- exact-signature groups = **36**;
- comparable groups = **27**;
- singleton groups = **9**;
- comparable profiles = **85**;
- directional pair checks = **220**;
- dominance edges = **54**;
- local frontier profiles = **57**;
- dominated profiles = **28**;
- audit errors = **0**;
- realized outcomes = **0**;
- historical performance metrics = **0**.

Therefore **Phase 3D-R2 is AUTHORIZED / NOT STARTED**. The replay result does not itself satisfy Phase 3D-R2, Phase 3E-R2, repeat Phase 3F, Phase 3 completion or Phase 4 entry.

Holdout is not a Phase 3G and is not a direct Phase 4 gate.

#### R2-4 Phase 3D-R2 — IN PROGRESS / ROUND 1 COMPLETE / PERFORMANCE BLOCKED
Round 1 froze the R2-specific measurability contract before any R2 outcome calculation and rebuilt the full accepted Holdout relation population.

Observed Round 1 result:
- status = `PARTIAL_R2_MEASURABILITY_OUTCOME_EVIDENCE_ACQUISITION_REQUIRED`;
- structurally measurable = **true**;
- frozen dominance edges = **54**;
- distinct endpoint securities = **7**;
- checkpoint-security endpoint instances = **55**;
- endpoint securities with any pre-existing governed price observation = **3/7**;
- endpoint securities with a frozen exchange-session schedule = **0/7**;
- endpoint securities with explicit corporate-action status = **0/7**;
- complete evidence edges = **0/54**;
- R2 return calculations = **0**;
- R2 performance metrics = **0**.

The next authorized substep is **Phase 3D-R2 Outcome Evidence Acquisition**. It must fill the frozen 1/3/5-session evidence requirements for the entire 54-edge population without dropping edges based on realized results, changing R2 transforms/signatures, or treating dominance as a trade. Performance calculation remains unauthorized until all evidence-readiness requirements pass. A PARTIAL evidence result is not economic underperformance.

#### R2-5 Phase 3E-R2 — REQUIRED IF SUPPORTED / NOT STARTED
Evaluate R2-specific robustness without using realized outcomes to tune fields, thresholds, mappings or comparison rules. The old 3E result for the original candidate forms is preserved as historical evidence but does not automatically satisfy R2 robustness.

#### R2-6 Repeat Phase 3F — MANDATORY / NOT STARTED
Re-evaluate all four Phase 4 promotion requirements:
1. valid R2 point-in-time historical replay;
2. measurable R2 Phase 3D evidence;
3. accepted R2 Phase 3E robustness;
4. broader independent historical coverage.

Only a later **4/4 PASS** may authorize `PROMOTE_TO_PHASE_4_FORWARD_VALIDATION`.

Current boundaries remain:
`phase3_historical_validation_complete=false`;
`phase4_entry_allowed=false`;
`orders=0`;
`trade_authority=NONE`.

## Phase 4 — FORWARD PARALLEL SHADOW VALIDATION — MANDATORY / NOT STARTED / BLOCKED
Run Legacy and surviving candidate model(s) in parallel on genuinely future evidence across multiple complete cycles. Historical replay cannot substitute for Phase 4. Phase 4 cannot start until a later 3F gate passes all mandatory historical requirements.

## Phase 5 — GOVERNED MIGRATION — NOT STARTED / NOT AUTHORIZED
Requires accepted Phase 3 and Phase 4 evidence plus a separate governed migration proposal. Effective migration is never inferred automatically from shadow performance.
