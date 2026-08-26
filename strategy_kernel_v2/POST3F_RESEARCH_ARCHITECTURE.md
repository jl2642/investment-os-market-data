# Strategy Kernel v2 — Post-3F Research Architecture

## Decision

Phase 3F completed with `CONTINUE_SHADOW_RESEARCH`, not Phase 4 promotion and not terminal rejection. The fixed Phase 3B candidate forms remain preserved for audit and are not promotable in their current form.

The governed continuation is a dual-track Phase 3 loopback:

1. **Primary track — new-identity R2 model architecture and contract redesign**;
2. **Mandatory parallel track — independent point-in-time holdout / broader historical coverage expansion**.

History-only expansion is not the primary repair because Phase 3E showed a multi-input schema mismatch: nine single-component ablations restored zero replay coverage. More of the same historical schema would not resolve an all-or-nothing candidate contract.

## R2 architecture direction

Working design identity: `EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2_DESIGN`.

This is a design direction, not yet an executable model identity and not a recommendation engine.

The architecture should prefer contemporaneously recorded observables and deterministic, pre-frozen transformations over retrospectively synthesized probability/confidence/cost scores. It should preserve missingness explicitly and distinguish universal decision evidence from context-specific portfolio/execution overlays.

Phase 3E observed related point-in-time information in the development corpus:

- evidence-quality context: 26 security instances;
- downside context: 26;
- return context: 20;
- confidence context: 20;
- concentration context: 8;
- execution context: 8;
- scenario context: 5.

These counts are **design evidence only**. They do not authorize relabelling any legacy field as a new model input. Every R2 field must have an explicit extraction/transformation contract, provenance rule and applicability rule before execution.

### Design principles

- No universal probability requirement.
- No scalar policy score.
- No silent proxy substitution.
- No subjective analyst fill.
- No retrospective probability/confidence/cost-score creation.
- No Phase 3D realized-outcome tuning.
- Missing inputs remain explicit.
- Context-dependent concentration/execution concepts may be applicability-aware rather than universal hard requirements.
- Prefer weight-free/Pareto comparison semantics unless a future governed contract separately justifies weights.
- Original `PHASE2_PROBABILISTIC_VECTOR` and `SIMPLE_NON_PROBABILISTIC_PARETO` remain immutable historical reference forms.

## Development-corpus firewall

The seven existing Phase 3A checkpoints are a **development corpus**, not an independent holdout.

They may be used to understand schema availability and to test whether a frozen R2 contract is mechanically replayable, but:

- Phase 3D realized returns may not select R2 fields, thresholds or mappings;
- same-seed tuning may not be presented as validation;
- the seven seed checkpoints may not count as independent holdout evidence;
- all claimed holdout transformations and model rules must be frozen before holdout evaluation.

## Independent holdout / coverage track

A separate coverage contract must be frozen before holdout results are used. It must require:

- checkpoints disjoint from the seven seed checkpoints;
- no checkpoint selection based on realized outcomes;
- exact point-in-time availability provenance and exact source identity;
- no later-evidence backfill;
- genuinely broader dates and/or regimes than the bounded seed;
- quantitative sufficiency criteria frozen before results are observed.

The objective is not to maximize favorable model outcomes. It is to test whether a new R2 form remains replayable and economically measurable on unseen historical evidence.

## Required loopback sequence

`Post-3F Decision → Phase 3B-R2 Contract Freeze → Phase 3C-R2 Point-in-time Replay → Independent Holdout Coverage → Phase 3D-R2 Measurability/Performance if supported → Phase 3E-R2 Robustness if supported → repeat Phase 3F`.

No step in this loop authorizes Phase 4. `PROMOTE_TO_PHASE_4_FORWARD_VALIDATION` remains blocked until a later Phase 3F gate passes every mandatory historical requirement.

## Authority

This research architecture creates no Core Static change, Candidate mutation, Real/Simulation position mutation, target portfolio writeback, user decision, recommendation, order or trade authority. `orders=0`; `trade_authority=NONE`.
