# Strategy Kernel v2 — Phase Execution Plan

## Global controls
Every phase preserves `orders=0`, `trade_authority=NONE`, mutation permissions false, Canonical provenance, and no direct write to protected `main`.

### Phase 0B — COMPLETE
Semantic audit of current Core Static; no effective rewrite.

### Phase 1B — COMPLETE
Decision Object v2 shadow adapter; preserve Canonical no-trade decisions and never fabricate valuation.

### Phase 1C — VALIDATED SHADOW-ONLY
Eight Underwriting Objects extracted from existing Canonical research. Material gaps remain explicit. Validation: 11/11 regression tests and 8/8 schema objects pass.

### Phase 2A — VALIDATED SHADOW-ONLY
Comparator contract/engine. Requires explicit probability-weighted scenarios and comparison vector inputs; outputs vectors plus Pareto frontier, not an uncalibrated scalar score. Validation: 12/12 tests; current real gate report remains 0 eligible / 8 blocked.

### Phase 2B — VALIDATED SHADOW-ONLY
**Objective:** safely map future governed market/research/valuation evidence into comparison-ready shadow inputs.

**Acceptance:**
- every refresh packet has `as_of`, governed provenance and explicit evidence classes;
- `READY_AFTER_REFRESH` becomes comparison-ready only when every recorded refresh requirement is explicitly satisfied;
- a Phase 1C `NOT_READY` object cannot be made ready by price/valuation refresh alone;
- `NOT_READY` requires `FUNDAMENTAL_REUNDERWRITE`, all original refresh requirements and all material evidence gaps explicitly resolved;
- explicit valuation scenarios and comparison vector inputs are required;
- source `decision_readiness`, Canonical action and all authority controls remain unchanged;
- 601138 NO_TRADE, 00669 research-only price gates, and 605090 concentration-not-auto-sell semantics remain protected;
- no user decision, economic mutation, Candidate mutation, order or trade is generated.

**Validation:** 13/13 unit tests pass; governed refresh packet schema passes. No real current refresh packet is fabricated or applied merely to advance the phase.

### Phase 2C — NEXT / GATED
Build the current shadow comparison pack only from real governed refresh packets and eligible assets. It may include a supplied reference/cash baseline with explicit provenance. `NO_COMPARISON` is valid.

### Phase 3 — MANDATORY BEFORE MIGRATION
Point-in-time replay/calibration using contemporaneously available evidence; assess forecast calibration, false negatives, false positives, downside, turnover and opportunity-cost regret.

### Effective migration
Separate governed proposal only after Phase 3; never inferred from shadow research performance alone.
