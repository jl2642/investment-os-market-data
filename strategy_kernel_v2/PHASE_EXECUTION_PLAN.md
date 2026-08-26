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

## Phase 3 — HISTORICAL REPLAY & CALIBRATION — IN PROGRESS / 3F GATE COMPLETE / LOOPBACK REQUIRED
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

## Phase 4 — FORWARD PARALLEL SHADOW VALIDATION — MANDATORY / NOT STARTED / BLOCKED
Run Legacy and surviving candidate model(s) in parallel on genuinely future evidence across multiple complete cycles. Historical replay cannot substitute for Phase 4. Phase 4 cannot start until a later 3F gate passes all mandatory historical requirements.

## Phase 5 — GOVERNED MIGRATION — NOT STARTED / NOT AUTHORIZED
Requires accepted Phase 3 and Phase 4 evidence plus a separate governed migration proposal. Effective migration is never inferred automatically from shadow performance.
