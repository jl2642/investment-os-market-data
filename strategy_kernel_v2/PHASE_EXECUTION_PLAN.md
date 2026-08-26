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
- `NOT_READY` objects remain blocked absent a later governed fundamental refresh;
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

#### Phase 2B — Governed Refresh Adapters — VALIDATED SHADOW-ONLY
**Objective:** map future governed issuer/valuation/market evidence into comparison-ready shadow inputs without loosening the Phase 1C evidence contract.

**Refresh packet contract:**
- explicit `security_id`, `as_of`, `governed=true` and non-empty provenance;
- explicit evidence classes (`PRICE_MARK`, `FX`, `VALUATION`, `FUNDAMENTAL_REUNDERWRITE`, `PORTFOLIO_CONTEXT`, `EXECUTION_FEASIBILITY`, `GOVERNANCE_CHECK`);
- exact lists of satisfied Phase 1C refresh requirements and resolved material evidence gaps;
- explicit probability-weighted valuation scenarios;
- explicit confidence, portfolio concentration cost and execution friction.

**Gate semantics:**
- `READY_AFTER_REFRESH` becomes shadow comparison-ready only when every recorded refresh requirement is explicitly satisfied;
- `NOT_READY` cannot be cured by price/valuation refresh alone;
- `NOT_READY` requires `FUNDAMENTAL_REUNDERWRITE`, every original refresh requirement and every material evidence gap explicitly resolved;
- the adapter may set only the shadow copy's `comparison_readiness=READY_NOW`; source `decision_readiness` is preserved verbatim and no Canonical state is changed.

**Security-specific invariants:**
1. 601138 accepted `HOLD_600_SHARES_NO_ADD_NO_TRADE` remains unchanged;
2. HKEX:00669 `WATCH_NO_TRADE_WAIT_FOR_PRICE_OR_POSITION_SIZING_GATE` and price-band-as-research-trigger semantics remain unchanged;
3. 605090 concentration remains a re-underwrite diagnostic, never an automatic sell signal;
4. 301215 remains blocked until project-level utilization/economics gaps are actually resolved by governed fundamental evidence.

**Validation:** 13/13 Phase 2B unit tests pass; governed refresh packet schema validates; price-only material-gap overrides=0; decision-readiness mutations=0; Canonical/economic mutations=0.

#### Phase 2C — Current Shadow Comparison Pack — VALIDATED COMPLETE / NO_COMPARISON
**Objective:** test the Phase 2A/2B contract against real currently stored governed evidence rather than synthetic or analyst-filled inputs.

**Evidence sources actually inspected:**
- Canonical `main` SHA `5c5df9082688f65332c79fef3b9cbfa893a06908`;
- WP4/WP4B Core research;
- D2 research for 000719/002039/301215;
- 601138 WP5 P0 primary-source re-underwrite and Canonical decision semantics;
- HKEX:00669 Canonical BUY REVIEW and P5C valuation context;
- latest validated governed WP2-R 2026-08-25 marks in PR #296;
- latest governed FMDL 2026-08-25 market release.

**Observed result:**
- 8/8 securities inventoried;
- fresh completed closes exist for 000333, 600900, 601138 and 605090 in the governed 2026-08-25 portfolio-mark production;
- 601138 legacy bear/base/bull scenario values exist but no scenario probabilities are stored; the current Phase 1C fundamental refresh requirement is not fully cleared;
- 000333/600900 WP4B says driver-based scenarios are complete, but Current exposes only completion status, not the scenario payload/probabilities needed by Phase 2A;
- 00669 has official H1 evidence and a governed research price framework, but no newly bound completed-close+FX probabilistic refresh packet;
- 000719/002039 have valuation frameworks/ranges, not probability-weighted annualized-return scenarios;
- 605090 and 301215 retain material fundamental evidence gaps and are not curable by price refresh;
- explicit confidence, portfolio concentration cost and execution friction inputs are not available as a complete governed current packet for any object.

**Acceptance result:** zero real governed refresh packets can be constructed without inventing new assumptions; eligible non-reference uses = 0; blocked = 8. Persist `NO_COMPARISON`. This is a successful fail-closed Phase 2C outcome, not a failed run.

**Validation:** Phase 2C pack-builder tests 10/10 pass; fabricated scenario/input count=0; user decision count=0; economic/Candidate mutations=0; `orders=0`; `trade_authority=NONE`.

### Phase 3 — POINT-IN-TIME REPLAY / CALIBRATION — NEXT
Mandatory before any effective policy relaxation or migration. Replay using only contemporaneously available evidence; assess forecast calibration, false-negative reduction, false-positive cost, downside capture, turnover and opportunity-cost regret.

Phase 3 must explicitly test the **model form** as well as parameter values. Probability-weighted scenarios, confidence/vector representation and any scalar utility/position-sizing rule remain hypotheses. The fact that the current legacy research objects do not store those fields is evidence about the existing process, not permission to backfill them retrospectively without point-in-time provenance.

### Effective migration
Separate governed proposal only after Phase 3. Never inferred from shadow research performance alone.
