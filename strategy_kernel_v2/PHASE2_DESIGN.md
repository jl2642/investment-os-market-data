# Strategy Kernel v2 — Phase 2 Design

Phase 2 is split into three governed subphases without changing the top-level Roadmap order.

## 2A — Comparator Contract / Engine
Preserve evidence gates; require explicit probability-weighted scenarios and vector inputs; output transparent vectors and Pareto dominance; do not hard-code a scalar utility score before Phase 3 calibration.

## 2B — Governed Refresh Adapters
A refresh packet must carry `as_of`, governed provenance, evidence classes, exact satisfied requirements, explicit material-gap resolutions, valuation scenarios and comparison vector inputs. `READY_AFTER_REFRESH` needs all recorded requirements. `NOT_READY` cannot be cured by price/valuation alone: it requires `FUNDAMENTAL_REUNDERWRITE` and resolution of every material gap. The adapter creates only a refreshed shadow copy and preserves source `decision_readiness`, Canonical actions and authority controls.

This distinction is deliberate: **comparison readiness is not user-decision readiness**. A newly refreshed research object can enter a shadow comparison without becoming a Candidate, implementation plan or trade authorization.

## 2C — Current Shadow Comparison Pack
Source real current governed refresh packets from production/research evidence, apply 2B, then feed only eligible shadow objects to 2A. `NO_COMPARISON` remains a valid output. Relative frontier results remain non-authoritative until Phase 3 replay/calibration and a separate effective-policy migration.
