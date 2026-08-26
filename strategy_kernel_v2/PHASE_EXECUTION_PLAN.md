# Strategy Kernel v2 — Phase Execution Plan

## Program hierarchy
This document executes, but cannot override, `MASTER_PROGRAM_CHARTER.md` / `PROGRAM_CONTRACT.json`. The macro lifecycle is fixed at Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 unless an explicit governed `PROGRAM_AMENDMENT` is approved.

## Global acceptance controls
Every phase through Phase 4 must preserve: `orders=0`, `trade_authority=NONE`, mutation permissions false, Canonical source provenance, and no direct write to protected `main`.

## Phase 0 — SYSTEM AUDIT — COMPLETE
### Phase 0B — Current-main rule audit — COMPLETE
Input: Canonical Core Static on main. Output: semantic rule inventory and treatment map. Acceptance: no effective Core Static rewrite.

## Phase 1 — DECISION & UNDERWRITING — COMPLETE SHADOW
### Phase 1B — Decision Object v2 — COMPLETE
Input: existing Canonical decisions/research/account states. Output: Decision Object v2 shadow adapter. Acceptance: canonical no-trade decisions preserved; missing valuation never fabricated.

### Phase 1C — Underwriting Extraction — VALIDATED SHADOW-ONLY
Coverage: 601138.SH, 605090.SH, HKEX:00669, 000719.SZ, 002039.SZ, 301215.SZ, 000333.SZ, 600900.SH.
Acceptance: explicit evidence/freshness gaps, deterministic schema, zero economic authority.

## Phase 2 — CAPITAL COMPARISON INFRASTRUCTURE — COMPLETE SHADOW
### Phase 2A — Comparator Contract / Engine — VALIDATED SHADOW-ONLY
**Input gate:** probability-weighted valuation scenarios, confidence, portfolio concentration cost and execution friction must be explicit; no silent defaults.

**Comparator outputs:** expected annualized total return, worst scenario return, probability of loss, confidence, concentration cost, execution friction, optional excess return versus an explicit reference, and Pareto dominance.

**Explicit non-output:** no scalar policy score, target weight, BUY/SELL instruction, user decision, Candidate mutation, or economic writeback.

### Phase 2B — Governed Refresh Adapters — VALIDATED SHADOW-ONLY
A refreshed shadow object becomes comparison-ready only when every recorded requirement is explicitly satisfied. `NOT_READY` cannot be cured by price/valuation alone. Source decision readiness and Canonical authority are preserved.

Security invariants remain: 601138 NO_TRADE semantics unchanged; 00669 price bands remain research gates; 605090 concentration remains a diagnostic; 301215 remains blocked until fundamental evidence gaps are resolved.

### Phase 2C — Current Shadow Comparison Pack — VALIDATED COMPLETE / NO_COMPARISON
Real governed evidence produced 0 eligible / 8 blocked without fabricated refresh packets. `NO_COMPARISON` is the accepted fail-closed result.

## Phase 3 — HISTORICAL REPLAY & CALIBRATION — IN PROGRESS / PHASE 3C COMPLETE_TERMINAL_NONREPLAYABILITY / PHASE 3D BLOCKED
Phase 3 uses only contemporaneously available evidence and tests model form as well as parameters. Historical success cannot authorize migration and Phase 3 can promote only to Phase 4.

### Phase 3A — Point-in-time Evidence Ledger — VALIDATED COMPLETE_SCOPE_BOUNDED
- 29 Canonical evidence records;
- 7 Canonical replay checkpoints from 2026-07-26 through 2026-08-18;
- 8 Strategy Kernel securities;
- exact availability timestamps and immutable source commits;
- later evidence cannot leak backward;
- probability/scenario backfill forbidden;
- 24/24 tests pass.

The seven-checkpoint seed is sufficient for bounded engineering but not statistical sufficiency or Phase 3F promotion.

### Phase 3B — Competing Model Forms — VALIDATED COMPLETE_CONTRACT_ONLY
Three fixed model forms:
1. `LEGACY_POLICY_BASELINE` — contemporaneously recorded disposition/state passthrough only;
2. `PHASE2_PROBABILISTIC_VECTOR` — explicit probability scenarios + return/downside/confidence/concentration/execution vector + Pareto, no scalar score;
3. `SIMPLE_NON_PROBABILISTIC_PARETO` — explicit return proxy/downside resilience/evidence quality/concentration/execution dimensions + Pareto.

Every model receives the same immutable shared observation packet. Structured observations may cite only evidence selected by the checkpoint. Model-specific evidence fetch and model-specific hindsight are forbidden. Missing inputs produce `NOT_EVALUABLE`.

Validation: 23/23 Phase 3B tests, 24/24 Phase 3A dependency tests and program consistency passed on PR #305. Phase 3B itself does not perform historical replay.

### Phase 3C — Decision / Capital Replay — VALIDATED COMPLETE_BOUNDED_REPLAY_TERMINAL_NONREPLAYABILITY
**Objective:** produce actual point-in-time replay across the fixed model forms without changing their information sets.

#### Stage 3C-1 — Point-in-time structured feature extraction — VALIDATED
- only the Phase 3A selected evidence set is eligible;
- each registered historical source is loaded from its exact registered `commit_sha:path` using `git show` and full Git history;
- extraction occurs once, before model execution, and is model-neutral;
- every extracted field retains provenance resolving inside the checkpoint;
- present-day `source_registry.py` is not a substitute for historical state;
- unsupported source shapes remain unsupported instead of being heuristically filled;
- unweighted scenarios remain unweighted;
- missing probability, confidence, concentration, execution or simple-Pareto inputs remain missing.

#### Stage 3C-2 — Shared-packet model replay — VALIDATED WITH TERMINAL CANDIDATE NONREPLAYABILITY FINDING
Real seven-checkpoint replay result:
- registered historical sources read successfully by exact commit/path: **29/29**;
- Legacy evaluable security×checkpoint instances: **29**;
- Phase-2 probabilistic/vector evaluable instances: **0**;
- simple non-probabilistic/Pareto evaluable instances: **0**;
- model-specific evidence fetches: **0**;
- subjective feature fills: **0**;
- retrospective probability backfills: **0**;
- retrospective scenario backfills: **0**.

The replay engine and historical provenance path work. Historical unweighted Bear/Base/Bull scenarios such as 601138 remain evidence but are not assigned retrospective probabilities merely to make the probabilistic model run. Explicit `NO_DECISION`, `NOT_DECISION_GRADE`, `WATCH`, and `NO_TRADE` semantics remain `NO_ACTION`, so research holds are not rewritten as portfolio retention.

#### Phase 3C continuation gate — RESOLVED VIA HISTORICAL NONREPLAYABILITY FINDING
The gate required either recovery of genuinely contemporaneous complete model inputs or an explicit non-replayability finding. A full Canonical checkpoint-tree audit scanned `investment_os_runtime`, `evidence`, and `outputs` across all seven checkpoint commits and found:
- keyword-candidate file occurrences: **673**;
- exact-model-field file occurrences: **114**;
- proxy-like legacy-field file occurrences: **147**;
- complete Phase-2 probability/vector packet occurrences: **0**;
- complete simple-Pareto five-field packet occurrences: **0**;
- unregistered complete Phase-2 packet occurrences: **0**;
- unregistered complete simple-Pareto packet occurrences: **0**.

Conclusion: `NO_COMPLETE_CANDIDATE_MODEL_INPUT_PACKET_FOUND_IN_CANONICAL_CHECKPOINT_TREES`.

Therefore:
- Phase 3A did **not** omit an independently recoverable complete candidate-model packet;
- `PHASE2_PROBABILISTIC_VECTOR` is historically non-replayable on the bounded corpus without retrospective input creation;
- `SIMPLE_NON_PROBABILISTIC_PARETO` is historically non-replayable on the bounded corpus without adding new transformation rules;
- proxy-like historical fields remain facts and may not be relabelled into the fixed Phase 3B model dimensions.

**Acceptance status:** `phase3c_started=true`, `phase3c_complete=true`. Phase 3C is complete as a **terminal negative model replayability/input-burden finding**, not a comparative-performance finding. No model winner is selected.

**3D entry gate:** **false**. The existing 3D entry rule still requires governed candidate replay evidence suitable for comparison with Legacy. A separate governed post-3C decision must determine the subsequent evaluation path before 3D can start. Phase 3C completion does not silently revise Phase 3B or the Phase 3A→3F sequence.

**Non-output:** no Canonical Candidate mutation, portfolio mutation, target weight writeback, user decision, recommendation, order, or trade.

### Phase 3D — Calibration & Regret Analysis — BLOCKED / NOT STARTED
Requires governed candidate replay evidence or a separately governed revision of the subsequent evaluation path. No forecast calibration, false-positive cost, missed-opportunity regret, downside comparison, turnover comparison or opportunity-cost regret may be invented for candidate models that generated no contemporaneous replay outputs.

### Phase 3E — Ablation / Robustness — NOT STARTED
Remove or simplify probability weights, confidence, concentration cost, execution friction and later utility transformations one at a time. The Phase 3C non-replayability finding is now accepted evidence about complexity/usability, but Phase 3C itself does not silently rewrite the fixed Phase 3B model forms.

### Phase 3F — Historical Promotion Gate — NOT ELIGIBLE
Allowed outcomes only: `REJECT_V2_FORM`, `CONTINUE_SHADOW_RESEARCH`, or `PROMOTE_TO_PHASE_4_FORWARD_VALIDATION`. `PROMOTE_TO_PHASE_5` is forbidden. Broader historical coverage and a governed path through 3D–3E remain mandatory.

## Phase 4 — FORWARD PARALLEL SHADOW VALIDATION — MANDATORY / NOT STARTED
Run Legacy and surviving candidate models in parallel on genuinely future evidence for multiple complete cycles. Freeze or tightly govern changes during measurement windows. Measure usefulness, calibration, stability, regret, turnover, downside behavior, operational robustness and explainability. Preserve all zero-authority controls.

Exit outcomes only: `REJECT_OR_REVISE`, `EXTEND_FORWARD_VALIDATION`, or `ELIGIBLE_FOR_PHASE_5_GOVERNED_MIGRATION_PROPOSAL`.

## Phase 5 — GOVERNED MIGRATION — NOT STARTED / NOT AUTHORIZED
Entry requires accepted Phase 3 historical evidence, accepted Phase 4 forward evidence and a separate governed migration proposal.

Execution: 5A Migration Proposal → 5B Rule-by-rule Treatment Map → 5C Limited Activation → 5D Rollback Observation → 5E Final Governed Acceptance.

Effective migration is never inferred automatically from shadow performance.
