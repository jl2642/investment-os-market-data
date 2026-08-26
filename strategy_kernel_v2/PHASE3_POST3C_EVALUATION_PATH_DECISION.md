# Strategy Kernel v2 — Governed Post-3C Evaluation Path Decision

## Decision status
`APPROVED_PHASE3D_NEGATIVE_RESULT_MEASURABILITY_PATH`

This is a governance gate between completed Phase 3C and not-yet-started Phase 3D. It does **not** add a new Phase 3 subphase. The internal sequence remains `3A → 3B → 3C → 3D → 3E → 3F`, and the macro lifecycle remains `Phase 0 → 1 → 2 → 3 → 4 → 5`.

## Triggering evidence
Phase 3C proved that the replay infrastructure is operational and that 29 Legacy security×checkpoint instances are mechanically reproducible. It also proved, through a full Canonical checkpoint-tree audit, that neither fixed candidate model has a complete contemporaneous input packet on the current bounded historical corpus, and that this is not a Phase 3A registry omission.

Therefore candidate historical outputs do not exist under the governed Phase 3B contracts. Missing outputs are evidence about model-form/input burden; they are not permission to create retrospective model outputs.

## Alternatives considered
1. **Retrospective input synthesis — REJECTED.** No backfilled probabilities, confidence, concentration/execution values, or simple-Pareto dimensions.
2. **Silent Phase 3B rewrite — REJECTED.** Existing model forms remain historically fixed.
3. **Skip Phase 3D and jump to 3E — REJECTED.** This would violate the governed A→F sequence and hide the measurability consequence of 3C.
4. **Phase 3D negative-result/measurability path — APPROVED.** Phase 3D may now formally analyze what is measurable and explicitly mark what is not.

## Phase 3D authorized scope
Phase 3D may start only after this decision passes its governance acceptance checks. Its mode is:

`NEGATIVE_RESULT_MEASURABILITY_AND_REGRET_OBSERVABILITY`

Before loading realized post-checkpoint outcomes, Phase 3D must pre-register evaluation horizons, outcome definitions and reference conventions. Realized outcomes are evaluation targets only; they may not feed back into replay inputs, model parameters or reconstructed decisions.

For Legacy, metrics may be calculated where both contemporaneous decision state and governed outcome data support them. For either candidate model, any metric that requires a contemporaneous candidate output must be recorded as:

`NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS`

Phase 3D is forbidden from generating hypothetical candidate decisions, synthetic candidate returns, counterfactual regret values, candidate calibration statistics, or a cross-model winner merely to fill the table.

## Phase 3E required role
Phase 3E remains the ablation / robustness stage and must explicitly use Phase 3C non-replayability as complexity/usability evidence. It may remove or simplify probability, confidence, concentration cost, execution friction, or later transformations one component at a time.

If 3E proposes a materially revised model form, that form must receive a new version/identity. It may not overwrite the fixed Phase 3B historical forms. A revised form must return through governed Phase 3B contract definition and Phase 3C replay before it can support Phase 3F promotion. Validation must use broader or holdout historical coverage; the same seven seed checkpoints may not be used for outcome-tuned redesign and then represented as independent validation.

## Phase 3F consequence
`PROMOTE_TO_PHASE_4_FORWARD_VALIDATION` remains unavailable unless at least one candidate model ultimately has:
- valid point-in-time historical replay;
- measurable Phase 3D evidence;
- accepted Phase 3E robustness evidence; and
- broader historical coverage beyond the current seven-checkpoint engineering seed.

If no candidate becomes historically evaluable, the only Phase 3F outcomes are `REJECT_V2_FORM` or `CONTINUE_SHADOW_RESEARCH`.

`PROMOTE_TO_PHASE_5` remains forbidden.

## Authority
No Core Static change, Candidate mutation, Real/Simulation mutation, target-portfolio writeback, user investment decision, recommendation, order or trade is authorized. `orders=0`; `trade_authority=NONE`.
