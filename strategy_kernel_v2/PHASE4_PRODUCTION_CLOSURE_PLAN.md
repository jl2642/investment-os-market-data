# Phase 4 Production Closure Plan — Amendment A1

## Objective
Make Strategy Kernel forward validation consume a real, continuously operating investment-assistant pipeline instead of a stale protected-main snapshot or manually accumulated PR backlog. The plan is production-first but preserves the already validated R2 historical model identity and all preregistered forward measurement semantics.

## User-visible completion target
When Phase 4 production closure is complete, the assistant must be able to show a single current operating view of: market-data watermarks, screening funnel counts, Candidate/research movement, completed research, recommendation states and triggers, autonomous shadow actions, protected real/simulation positions, and failures/staleness. A zero BUY_NOW count must be explainable by investment gates and near-misses rather than by a dead pipeline.

## P4-0 — Program Reconciliation
Inputs: #333, #337, current Strategy Kernel control artifacts, product/R6 production audit.
Deliverables: Amendment A1, synchronized plan/state, v1 audit preservation, effective forward-execution hold.
Gate: no model or protected economic mutation; validator PASS.
New user capability: one authoritative answer to “where is the program and what happens next?”.

## P4-1 — Production Backbone Repair
Inputs: current A/H/US market/research pipelines, operating PR backlog, recovery workflows, watermarks.
Deliverables: governed Operating Current design; production promotion rules; full-market A-share recovery; cross-market watermark ledger; failure/retry/recovery observability.
Gate: consecutive fresh cycles and deterministic recovery; low-risk operating evidence no longer depends on manual daily PR merging.
New user capability: trust the date and freshness of what the assistant sees.

## P4-2 — Continuous Opportunity Funnel
Inputs: fresh market/factor/screening data.
Deliverables: continuous Universe→Longlist→Research Queue→D1→D2 pipeline; bounded research-state rotation; funnel and near-miss ledger.
Gate: repeated cycles with nonzero throughput or explicit economic rejection at each gate.
New user capability: see what is entering/leaving research and why.

## P4-3 — Unified Decision & Recommendation Engine
Inputs: D2/underwriting/valuation/portfolio-fit/capital-comparison evidence.
Deliverables: cross-market Recommendation Current with BUY_NOW, BUY_ON_PRICE, BUY_ON_EVIDENCE, WATCH, HOLD, ADD/TRIM/EXIT review and AVOID states plus triggers/invalidation/portfolio role.
Gate: research-complete assets route to an explicit investment judgment; no order or protected-state mutation.
New user capability: know what the assistant would buy now, wait for, avoid, add, trim or exit-review and why.

## P4-4 — Trigger Monitor & Autonomous Shadow Book
Inputs: Recommendation Current and market/event updates.
Deliverables: trigger registry; research-only hypothetical trades; entry/exit timestamps; benchmark and attribution lineage.
Gate: reproducible shadow history; protected Simulation and Real Current unchanged.
New user capability: objectively evaluate what would have happened if the assistant followed its own recommendations.

## P4-5 — Clean-Baseline Forward Validation
Inputs: production-closed pipeline and frozen v2 cutoff.
Deliverables: genuine future shared packets, Legacy and R2 outputs, 1/3/5-session outcomes, predefined summaries and robustness tests.
Gate: #333 directional/evidence sufficiency semantics preserved; only preregistered completion outcomes allowed.
New user capability: know whether R2 actually survives unseen forward evidence strongly enough to justify Phase 5 migration.

## Phase 5 handoff
Phase 5 remains unauthorized until P4-5 passes. If authorized, Phase 5 will migrate only the validated analytical/recommendation capability, preserve explicit user control over real-money decisions, consolidate obsolete workflows/state, and activate the final operating model reversibly.

## Change discipline
Any change to stage order, stage purpose, model identity, measurement thresholds, authority boundary or clean-cutoff rule requires a new logged amendment before implementation. Defect repairs inside an existing stage must be recorded in PLAN_CHANGELOG with scope and downstream impact.
