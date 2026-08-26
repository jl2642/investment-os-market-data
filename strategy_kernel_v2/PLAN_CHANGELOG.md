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

**Not changed:**
- top-level order remains Phase 2 then mandatory Phase 3 before any effective migration;
- no Core Static rule, Candidate membership, economic state, target weight, user decision, order authority or trade authority changes;
- `orders=0`, `trade_authority=NONE` remain invariant.

## 2026-08-26 — Phase 2B governed refresh contract
**Reason:** Phase 2A correctly returned 0 eligible / 8 blocked from the current Phase 1C objects. A safe mechanism is needed to admit genuinely refreshed evidence without relaxing the evidence standard merely to generate a ranking.

**Changed:**
- added a governed refresh packet schema with explicit provenance, evidence classes, requirement coverage, material-gap resolution, scenarios and comparison inputs;
- `READY_AFTER_REFRESH` requires exact coverage of all recorded refresh requirements;
- clarified that `NOT_READY` is not permanently immutable in shadow research, but can become comparison-ready only after a governed `FUNDAMENTAL_REUNDERWRITE` resolves all original refresh requirements and material evidence gaps;
- price/valuation-only refresh cannot override a material fundamental evidence gap;
- a refreshed shadow copy may change comparison readiness only; source decision readiness and Canonical authority are preserved;
- current real refresh packet count remains zero, so the 0/8 current comparison baseline is not artificially changed.

**Validation:** 13/13 unit tests pass; governed-refresh schema passes; no user decision, Candidate mutation, economic mutation, order or trade is generated.

**Not changed:**
- no effective Strategy/Core migration;
- no existing 601138/00669/605090 Canonical action semantics changed;
- Phase 3 remains mandatory before any effective policy or sizing migration.
