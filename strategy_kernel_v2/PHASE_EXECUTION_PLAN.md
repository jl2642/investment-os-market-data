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

## Phase 3 — HISTORICAL REPLAY & CALIBRATION — IN PROGRESS
Internal order remains exactly `3A → 3B → 3C → 3D → 3E → 3F`.

### Phase 3A — Point-in-time Evidence Ledger — COMPLETE_SCOPE_BOUNDED
29 Canonical evidence records, 7 checkpoints, 8 securities, exact commit/availability provenance, no hindsight. Broader history remains required before 3F.

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

Phase 3D completion therefore means **the measurability question was answered**, not that candidate-vs-Legacy calibration/regret was successfully compared.

### Phase 3E — Ablation / Robustness — READY TO START / NOT STARTED
Test simplification/removal of probability, confidence, concentration cost, execution friction and later transformations. 3C/3D non-replayability/measurability findings are accepted evidence about complexity and input burden.

If 3E proposes a materially revised form:
- assign a new model/version identity;
- do not overwrite any fixed 3B historical form;
- the revised form must **return through governed 3B contract definition and 3C replay** before any 3F promotion;
- same-seed outcome tuning cannot be presented as independent validation;
- broader or holdout historical validation is required.

### Phase 3F — Historical Promotion Gate — NOT ELIGIBLE
`PROMOTE_TO_PHASE_4_FORWARD_VALIDATION` requires at least one candidate with valid point-in-time historical replay, measurable 3D evidence, accepted 3E robustness evidence and broader historical coverage.

If no candidate becomes historically evaluable, allowed outcomes are only `REJECT_V2_FORM` or `CONTINUE_SHADOW_RESEARCH`.

`PROMOTE_TO_PHASE_5` is forbidden.

## Phase 4 — FORWARD PARALLEL SHADOW VALIDATION — MANDATORY / NOT STARTED
Run Legacy and surviving candidate model(s) in parallel on genuinely future evidence across multiple complete cycles. Historical replay cannot substitute for Phase 4.

## Phase 5 — GOVERNED MIGRATION — NOT STARTED / NOT AUTHORIZED
Requires accepted Phase 3 and Phase 4 evidence plus a separate governed migration proposal. Effective migration is never inferred automatically from shadow performance.
