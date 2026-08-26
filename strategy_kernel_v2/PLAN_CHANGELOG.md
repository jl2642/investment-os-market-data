# Strategy Kernel v2 — Plan Changelog

## 2026-08-26 — Phase 1C plan synchronization
Added Underwriting Extraction before capital comparison; separated underwriting completeness, comparison readiness and decision readiness. No effective policy or authority changed.

## 2026-08-26 — Phase 1C validation closeout
Persisted deterministic eight-object bundle and regression validation; phase status aligned with actual implementation.

## 2026-08-26 — Phase 2 refinement
**Reason:** capital comparison must distinguish measurement from unvalidated utility policy and from evidence refresh.

**Changed:** Phase 2 split into 2A Comparator Engine, 2B Governed Refresh Adapters and 2C Current Shadow Comparison Pack. 2A uses transparent vectors/Pareto dominance rather than a scalar score; scalar/sizing policies are deferred to Phase 3 calibration.

## 2026-08-26 — Phase 2B validation
**Reason:** 2A correctly blocked all eight current objects; a governed mechanism is needed to satisfy refresh/evidence gates without silently loosening them.

**Changed:** added a governed refresh packet contract and pure shadow adapter. `READY_AFTER_REFRESH` needs exact requirement coverage. `NOT_READY` requires a fundamental re-underwrite plus resolution of all material evidence gaps; price-only override is forbidden. Decision readiness and Canonical authority remain unchanged.

**Not changed:** no effective Core Static rule, Candidate membership, Real/Simulation economic state, target portfolio, user decision, order authority or trade authority changed. Phase 3 remains mandatory before any effective migration.
