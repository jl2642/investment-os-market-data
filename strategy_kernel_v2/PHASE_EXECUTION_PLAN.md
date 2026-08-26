# Strategy Kernel v2 — Phase Execution Plan

## Program hierarchy
This document executes, but cannot override, `MASTER_PROGRAM_CHARTER.md` / `PROGRAM_CONTRACT.json`. Macro lifecycle is fixed at Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 unless an explicit governed PROGRAM_AMENDMENT is approved.

## Global acceptance controls
Every phase through Phase 4 preserves `orders=0`, `trade_authority=NONE`, mutation permissions false, Canonical provenance and no direct protected-main write.

## Phase 0 — SYSTEM AUDIT — COMPLETE
Legacy/Core Static baseline inventoried.

## Phase 1 — DECISION & UNDERWRITING — COMPLETE SHADOW
1B Decision Object v2 and 1C Underwriting Extraction are complete/validated shadow-only. Missing evidence remains explicit.

## Phase 2 — CAPITAL COMPARISON INFRASTRUCTURE — COMPLETE SHADOW
2A comparator, 2B governed refresh and 2C real-evidence pack are validated. Current real pack remains `NO_COMPARISON`, 0 eligible / 8 blocked, with no fabricated refresh packets.

## Phase 3 — HISTORICAL REPLAY & CALIBRATION — IN PROGRESS
Internal order remains exactly `3A → 3B → 3C → 3D → 3E → 3F`.

### Phase 3A — Point-in-time Evidence Ledger — COMPLETE_SCOPE_BOUNDED
29 Canonical evidence records, 7 checkpoints, 8 securities, exact commit/availability provenance, no hindsight. Broader history remains required before 3F.

### Phase 3B — Competing Model Forms — COMPLETE_CONTRACT_ONLY
Fixed forms: Legacy baseline, Phase-2 probabilistic/vector, simple non-probabilistic Pareto. All consume the same shared packet. Missing inputs fail closed; retrospective input creation and model-specific evidence fetch are forbidden.

### Phase 3C — Decision / Capital Replay — COMPLETE_TERMINAL_NONREPLAYABILITY
29/29 historical sources were read; Legacy produced 29 evaluable security×checkpoint instances; both candidate forms produced 0. Full Canonical-tree audit found no complete registered or unregistered candidate packet. Candidate non-replayability is therefore a valid model-form/input-burden finding, not a performance conclusion.

### Governed Post-3C Evaluation Path Gate — ACCEPTED
This gate is not a new subphase.

Rejected paths:
- retrospective input synthesis;
- silent Phase 3B contract rewrite;
- skipping Phase 3D.

Approved path:
`PHASE3D_NEGATIVE_RESULT_MEASURABILITY_THEN_PHASE3E_ABLATION`

### Phase 3D — Calibration & Regret Analysis — READY TO START / NOT STARTED
Mode: `NEGATIVE_RESULT_MEASURABILITY_AND_REGRET_OBSERVABILITY`.

Before reading realized post-checkpoint outcomes, 3D MUST pre-register:
1. fixed evaluation horizon(s);
2. outcome definition(s);
3. reference/baseline convention(s);
4. missing-data treatment.

Rules:
- realized outcomes are evaluation targets only and cannot feed back into replay inputs, parameters or reconstructed decisions;
- Legacy metrics may be measured only where contemporaneous Legacy state and governed outcome data both exist;
- candidate metrics requiring nonexistent candidate outputs MUST be `NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS`;
- hypothetical candidate decisions are forbidden;
- retrospective candidate-output generation is forbidden;
- synthetic candidate return/regret/calibration values are forbidden;
- cross-model winner selection is forbidden while candidate outputs are absent;
- maximum backtested return is not the success criterion.

3D may therefore produce a complete **measurability/observability matrix** and Legacy-only diagnostics without pretending to have candidate performance results.

### Phase 3E — Ablation / Robustness — NOT STARTED
Test removal/simplification of probability, confidence, concentration cost, execution friction and later transformations one component at a time. 3C non-replayability is accepted evidence about operational complexity and input burden.

If 3E proposes a materially revised form:
- assign a new model/version identity;
- do not overwrite any fixed 3B historical form;
- the revised form must **return through governed 3B contract definition and 3C replay** before any 3F promotion;
- forbid tuning on the same seven seed checkpoints and then presenting that seed as independent validation;
- require broader or holdout historical validation.

### Phase 3F — Historical Promotion Gate — NOT ELIGIBLE
`PROMOTE_TO_PHASE_4_FORWARD_VALIDATION` requires at least one candidate with valid point-in-time historical replay, measurable 3D evidence, accepted 3E robustness evidence and broader historical coverage.

If no candidate becomes historically evaluable, allowed outcomes are only:
- `REJECT_V2_FORM`
- `CONTINUE_SHADOW_RESEARCH`

`PROMOTE_TO_PHASE_5` is forbidden.

## Phase 4 — FORWARD PARALLEL SHADOW VALIDATION — MANDATORY / NOT STARTED
Run Legacy and surviving candidate model(s) in parallel on genuinely future evidence across multiple complete cycles. Historical replay cannot substitute for Phase 4.

## Phase 5 — GOVERNED MIGRATION — NOT STARTED / NOT AUTHORIZED
Requires accepted Phase 3 and Phase 4 evidence plus a separate governed migration proposal. Effective migration is never inferred automatically from shadow performance.
