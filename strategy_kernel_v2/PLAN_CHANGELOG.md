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
