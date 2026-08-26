# Strategy Kernel v2 — Phase Execution Plan

## Global acceptance controls
Every phase must preserve: `orders=0`, `trade_authority=NONE`, mutation permissions false, Canonical source provenance, and no direct write to protected `main`.

### Phase 0B — COMPLETE
Input: Canonical Core Static on main. Output: semantic rule inventory and treatment map. Acceptance: no effective Core Static rewrite.

### Phase 1B — COMPLETE
Input: existing Canonical decisions/research/account states. Output: Decision Object v2 shadow adapter. Acceptance: canonical no-trade decisions preserved; missing valuation never fabricated.

### Phase 1C — UNDERWRITING EXTRACTION — VALIDATED SHADOW-ONLY
Coverage: 601138.SH, 605090.SH, HKEX:00669, 000719.SZ, 002039.SZ, 301215.SZ, 000333.SZ, 600900.SH.
Acceptance: 11/11 regression tests, 8/8 schema validations, deterministic bundle, explicit evidence/freshness gaps, zero economic authority.

### Phase 2 — SHADOW CAPITAL COMPARATOR

#### Phase 2A — Comparator Contract / Engine — VALIDATED SHADOW-ONLY
**Objective:** build the auditable comparison mechanism without yet deciding a utility function.

**Input gate:**
- `NOT_READY` objects remain blocked regardless of price refresh;
- `READY_AFTER_REFRESH` objects require a governed overlay that explicitly satisfies every Phase 1C refresh requirement;
- probability-weighted valuation scenarios, confidence, portfolio concentration cost and execution friction must be explicit; no silent defaults.

**Comparator outputs:**
- probability-weighted expected annualized total return;
- worst-scenario annualized total return;
- probability of loss;
- explicit confidence;
- portfolio concentration cost;
- execution friction;
- optional excess expected return versus an explicitly supplied cash/reference baseline;
- Pareto frontier / dominance relationships.

**Explicit non-output:** no scalar policy score, no target weight, no BUY/SELL instruction, no user decision, no Candidate mutation, no economic writeback.

**Validation:** 12/12 Phase 2A unit tests pass; capital-comparison schema validation passes; current Phase 1C gate report correctly returns 0 eligible / 8 blocked absent refresh.

#### Phase 2B — Governed Refresh Adapters — NEXT
Map fresh governed issuer/valuation/market artifacts to explicit comparator overlays. The adapter must preserve source provenance and may satisfy only the requirements evidenced by the source. Price data cannot cure a material fundamental evidence gap.

Priority refresh paths:
1. 601138 issuer H1/major primary evidence + completed-close valuation;
2. HKEX:00669 completed close + FX normalization, while preserving price-band-only research semantics;
3. 000719 and 002039 fresh normalized valuation and stated issuer checks;
4. 000333 and 600900 surface/refresh scenario valuation payloads plus issuer-specific limitation refresh;
5. 605090 requires issuer-specific re-underwrite before comparison;
6. 301215 remains event/data-dependent until utilization/project-economics evidence appears.

#### Phase 2C — Current Shadow Comparison Pack — GATED
When at least two economically meaningful non-reference capital uses are eligible, build a research-only comparison pack with an explicit reference/cash alternative. If the threshold is not met, output `NO_COMPARISON` rather than manufacturing rankings.

### Phase 3 — POINT-IN-TIME REPLAY / CALIBRATION
Mandatory before any effective policy relaxation or migration. Replay using only contemporaneously available evidence; assess forecast calibration, false-negative reduction, false-positive cost, downside capture, turnover and opportunity-cost regret. Candidate scoring/sizing policies are hypotheses to be tested here, not hard-coded in Phase 2.

### Effective migration
Separate governed proposal only after Phase 3. Never inferred from shadow research performance alone.
