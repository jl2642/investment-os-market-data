# Strategy Kernel v2 — Master Program Charter

**Program version:** 1.0  
**Status:** CONTROLLED MASTER PROGRAM CONTRACT

This charter defines the macro lifecycle. Sub-phase plans may refine execution inside a macro phase, but may not silently delete, reorder, bypass, or reinterpret macro phases or promotion gates.

## Program objective
Build and validate a stock-investment Strategy Kernel that can translate governed research into explainable capital-allocation judgments with a defensible investment edge, while preserving evidence honesty, opportunity-cost discipline, auditability, and explicit human authority.

The program does not assume Legacy/Core Static is too conservative, that more trading is better, or that any specific model form is correct before validation.

## Canonical macro lifecycle
### Phase 0 — System Audit
Map Legacy/Core Static and establish the baseline.
### Phase 1 — Decision & Underwriting Layer
Normalize decisions and extract underwriting without changing effective policy.
### Phase 2 — Capital Comparison Infrastructure
Build shadow-only comparison and governed refresh infrastructure; measurement remains separate from policy.
### Phase 3 — Historical Replay & Calibration
Run point-in-time, no-hindsight replay; test model form and parameters. Phase 3 may promote only to Phase 4.
### Phase 4 — Forward Parallel Shadow Validation
Run Legacy and candidate Strategy Kernel models in parallel on genuinely future, previously unseen evidence. Historical replay may not substitute for Phase 4.
### Phase 5 — Governed Migration
Only after separately accepted Phase 3 historical evidence and Phase 4 forward evidence may effective migration be proposed. Migration must be governed and reversible.

## Non-negotiable promotion gates
1. Phase 2 -> Phase 3: shadow infrastructure validated; no policy migration.
2. Phase 3 -> Phase 4: historical replay/calibration passed.
3. Phase 4 -> Phase 5: forward parallel validation passed.
4. Direct Phase 3 -> Phase 5 is forbidden.
5. No macro phase may be omitted by a sub-phase plan.
6. Any macro lifecycle change requires explicit PROGRAM_AMENDMENT, rationale, impact assessment, and synchronized program-control updates.

## Phase 3 internal evaluation governance
The internal Phase 3 sequence remains `3A → 3B → 3C → 3D → 3E → 3F`.

A genuine no-hindsight negative replayability result may complete Phase 3C when the absence of candidate inputs is independently audited rather than assumed. Such completion does not authorize fabricated historical candidate outputs.

When a candidate has no contemporaneous replay output, Phase 3D must record dependent calibration/regret measures as `NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS`. Evaluation horizons and reference conventions must be fixed before realized outcomes are loaded, and realized outcomes may not feed back into replayed inputs or model parameters.

Phase 3E may test simplification and ablation, but any materially revised model form must be versioned and return through governed Phase 3B model-contract definition and Phase 3C replay. A revised form may not overwrite the historical identity of an earlier candidate.

Phase 3F may promote to Phase 4 only if at least one candidate has valid point-in-time historical replay, measurable Phase 3D evidence, accepted Phase 3E robustness evidence, and broader historical coverage. If no candidate becomes historically evaluable, the only Phase 3F outcomes are `REJECT_V2_FORM` or `CONTINUE_SHADOW_RESEARCH`.

## Permanent authority boundaries during Phases 0–4
No live trading, orders, automatic Candidate mutation, Real/Simulation economic mutation, target-portfolio writeback or implicit user decision. `orders=0`, `trade_authority=NONE`.

## Controlled artifacts
`MASTER_PROGRAM_CHARTER.md`, `PROGRAM_CONTRACT.json`, `PROGRAM_STATE.json`, `DEVELOPMENT_ROADMAP.md`, `PHASE_EXECUTION_PLAN.md`, `PLAN_CHANGELOG.md`, and `CURRENT_PHASE_STATUS.json` must remain synchronized.

## 2026-08-26 correction record
A roadmap drift was detected: Phase 4 Forward Parallel Shadow Validation was unintentionally omitted during Phase 2 plan synchronization, making the evolving roadmap appear to allow Phase 3 to lead directly toward migration. No effective Strategy/Core migration occurred. The Phase 0–5 lifecycle is restored before Phase 3 implementation.

## 2026-08-26 post-3C governance record
Phase 3C established a terminal bounded negative replayability finding for both fixed candidate models. The governed response is not to backfill missing inputs or skip a phase: Phase 3D is authorized only as a negative-result/measurability analysis, followed by Phase 3E ablation/robustness under the version-and-return rules above. The macro lifecycle and Phase 3 A–F sequence are unchanged.

## 2026-08-28 PROGRAM_AMENDMENT_A1 — Phase 4 Production Closure and Forward Validation Realignment

A system-wide audit after the Phase 4 v1 zero-observation census found that the forward-validation source pipeline is not production-closed: protected `main` has not advanced with the operating evidence cadence, full-market and Candidate/Decision watermarks are not continuously aligned, and legacy R6 operating activation remains incomplete. Because Phase 4 v1 has consumed **0 forward observations and 0 realized outcomes**, this defect can be corrected before forward evidence without outcome-driven redesign.

This amendment **does not change the macro lifecycle** `Phase 0 → 1 → 2 → 3 → 4 → 5`, does not reopen completed Phase 0–3/R2 work, and does not change the R2.0.1 model, 20 transforms, exact-signature Pareto semantics, 1/3/5-session measurement horizons, aggregation schemes or directional thresholds.

PR #333 remains the immutable Phase 4 v1 preregistration record and PR #337 remains the immutable zero-observation canonical-main census. Their historical facts are preserved. However, their forward-start permission is now subject to a higher-level **effective execution hold**: no Phase 4 observation may be consumed until the production backbone, continuous opportunity funnel, unified recommendation layer and separate autonomous shadow-observation layer are production-ready, a clean baseline is frozen, and a new strictly-future cutoff is registered.

The controlled Phase 4 internal sequence is now:

1. **P4-0 — Program Reconciliation & Production Architecture Amendment Freeze**;
2. **P4-1 — Production Backbone Repair**;
3. **P4-2 — Continuous Opportunity Funnel**;
4. **P4-3 — Unified Decision & Recommendation Engine**;
5. **P4-4 — Trigger Monitor & Autonomous Shadow Book**;
6. **P4-5 — Clean-Baseline Forward Parallel Shadow Validation**.

Protected Real account state, protected Simulation Current, formal Candidate membership, effective Core Static, target portfolio and orders remain non-automated through this amendment. The planned autonomous shadow book is a separate research-only hypothetical ledger and is not a mutation of protected Simulation Current. `orders=0`; `trade_authority=NONE`.
