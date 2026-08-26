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

## Permanent authority boundaries during Phases 0–4
No live trading, orders, automatic Candidate mutation, Real/Simulation economic mutation, target-portfolio writeback or implicit user decision. `orders=0`, `trade_authority=NONE`.

## Controlled artifacts
`MASTER_PROGRAM_CHARTER.md`, `PROGRAM_CONTRACT.json`, `PROGRAM_STATE.json`, `DEVELOPMENT_ROADMAP.md`, `PHASE_EXECUTION_PLAN.md`, `PLAN_CHANGELOG.md`, and `CURRENT_PHASE_STATUS.json` must remain synchronized.

## 2026-08-26 correction record
A roadmap drift was detected: Phase 4 Forward Parallel Shadow Validation was unintentionally omitted during Phase 2 plan synchronization, making the evolving roadmap appear to allow Phase 3 to lead directly toward migration. No effective Strategy/Core migration occurred. The Phase 0–5 lifecycle is restored before Phase 3 implementation.
