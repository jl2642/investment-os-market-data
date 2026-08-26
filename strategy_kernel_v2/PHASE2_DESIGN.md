# Strategy Kernel v2 — Phase 2 Design

Phase 2 is refined into three governed subphases without changing the top-level Roadmap order.

## Phase 2A — Comparator Contract / Engine
Build the research-only comparison contract. It must:
- preserve every Phase 1C refresh/evidence gate;
- require explicit probability-weighted valuation scenarios and explicit confidence/portfolio-cost/execution-friction inputs;
- output a transparent vector rather than an unvalidated one-number score;
- compute a Pareto frontier as a weight-free dominance diagnostic;
- allow an explicit cash/reference baseline only when the caller supplies its rate and provenance;
- never generate a user decision, target weight, Candidate mutation, order, or economic writeback.

### Why no scalar score in 2A
A scalar score would silently encode utility weights between return, downside, confidence, concentration and execution friction before Phase 3 has calibrated them. Phase 2A therefore persists the components and dominance relationships. Phase 3 may later test candidate scoring/sizing policies against point-in-time outcomes.

## Phase 2B — Governed Refresh Adapters
Map fresh governed research/valuation artifacts into comparator inputs. The adapter may satisfy an existing Phase 1C refresh requirement only with explicit provenance; it may not cure a `NOT_READY` material evidence gap with price data alone.

## Phase 2C — Current Shadow Comparison Pack
When enough objects are eligible, produce an auditable research-only comparison pack across positions/candidates/reference assets. `NO_COMPARISON` is valid if refresh requirements are not met. Any relative frontier result remains non-authoritative until Phase 3 replay/calibration and a separate effective-policy migration.
