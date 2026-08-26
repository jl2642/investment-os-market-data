# Strategy Kernel v2 — Phase Execution Plan

## Program hierarchy
This document executes, but cannot override, `MASTER_PROGRAM_CHARTER.md` / `PROGRAM_CONTRACT.json`. The macro lifecycle is fixed at Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 unless an explicit governed `PROGRAM_AMENDMENT` is approved.

## Global acceptance controls
Every phase through Phase 4 must preserve: `orders=0`, `trade_authority=NONE`, mutation permissions false, Canonical source provenance, and no direct write to protected `main`.

## Phase 0 — SYSTEM AUDIT — COMPLETE

### Phase 0B — Current-main rule audit — COMPLETE
Input: Canonical Core Static on main. Output: semantic rule inventory and treatment map. Acceptance: no effective Core Static rewrite.

## Phase 1 — DECISION & UNDERWRITING — COMPLETE SHADOW

### Phase 1B — Decision Object v2 — COMPLETE
Input: existing Canonical decisions/research/account states. Output: Decision Object v2 shadow adapter. Acceptance: canonical no-trade decisions preserved; missing valuation never fabricated.

### Phase 1C — Underwriting Extraction — VALIDATED SHADOW-ONLY
Coverage: 601138.SH, 605090.SH, HKEX:00669, 000719.SZ, 002039.SZ, 301215.SZ, 000333.SZ, 600900.SH.
Acceptance: 11/11 regression tests, 8/8 schema validations, deterministic bundle, explicit evidence/freshness gaps, zero economic authority.

## Phase 2 — CAPITAL COMPARISON INFRASTRUCTURE — COMPLETE SHADOW

### Phase 2A — Comparator Contract / Engine — VALIDATED SHADOW-ONLY
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

### Phase 2B — Governed Refresh Adapters — VALIDATED SHADOW-ONLY
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

### Phase 2C — Current Shadow Comparison Pack — VALIDATED COMPLETE / NO_COMPARISON
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

## Phase 3 — HISTORICAL REPLAY & CALIBRATION — NEXT / NOT STARTED
Mandatory before forward promotion. Phase 3 uses only contemporaneously available evidence and explicitly tests **model form** as well as parameter values. Probability-weighted scenarios, confidence/vector representation and any scalar utility/position-sizing rule remain hypotheses.

### Phase 3A — Point-in-time Evidence Ledger
**Objective:** build immutable historical evidence snapshots for each replay decision timestamp.

**Requirements:**
- only evidence available at or before the historical timestamp may be included;
- no later filing, later price, later research conclusion, or later Candidate state may leak backward;
- retrospective probability/scenario backfill is prohibited unless the probability/scenario was actually contemporaneously recorded with provenance;
- missing evidence remains explicit.

**Acceptance:** reproducible evidence ledger, point-in-time provenance, no hindsight contamination in sampled dates, and explicit unavailable-data states.

### Phase 3B — Competing Model Forms
**Objective:** prevent the program from assuming the Phase-2 model form is already correct.

Run at minimum:
1. Legacy decision baseline;
2. Phase-2 probabilistic/vector architecture;
3. a simpler non-probabilistic / Pareto alternative.

**Acceptance:** identical information set, opportunity set, reference asset and timestamp for each model; no model-specific hindsight advantage; model outputs persist rationale and uncertainty.

### Phase 3C — Decision / Capital Replay
Generate shadow-only relative capital judgments across historical opportunity sets. Track which opportunities would be admitted, blocked, prioritized, retained, reduced, or left as NO_ACTION under each model.

**Non-output:** no Canonical Candidate mutation, portfolio mutation, target weight writeback, user decision, order or trade.

### Phase 3D — Calibration & Regret Analysis
Measure:
- forecast calibration and scenario coverage where forecasts were genuinely available;
- false-positive cost;
- false-negative / missed-opportunity regret;
- downside capture and adverse-path behavior;
- turnover and decision instability;
- opportunity-cost regret versus cash/reference and contemporaneously available alternatives.

The success criterion is not maximum backtested return in isolation.

### Phase 3E — Ablation / Robustness
Remove or simplify candidate components one at a time, including probability weights, confidence, concentration cost, execution friction and any later utility transformation.

**Acceptance:** identify which components add repeatable decision value and which are merely complexity. No component enters proposed policy simply because it is theoretically attractive.

### Phase 3F — Historical Promotion Gate
Allowed outcomes only:
- `REJECT_V2_FORM`;
- `CONTINUE_SHADOW_RESEARCH`;
- `PROMOTE_TO_PHASE_4_FORWARD_VALIDATION`.

`PROMOTE_TO_PHASE_5` is forbidden.

Phase 3 passing is evidence that a candidate architecture deserves forward testing; it is not evidence sufficient for effective migration.

## Phase 4 — FORWARD PARALLEL SHADOW VALIDATION — MANDATORY / NOT STARTED
**Objective:** test surviving candidate Strategy Kernel model(s) on genuinely future evidence that was not available during design, replay, or calibration.

**Execution:**
- run Legacy and candidate model(s) in parallel for multiple complete decision cycles;
- freeze or tightly govern model/policy changes during measurement windows so forward evidence remains interpretable;
- record decisions, uncertainty, blocked reasons, subsequent outcomes and operational failures prospectively;
- preserve `orders=0` and all economic mutation permissions=false.

**Acceptance dimensions:**
- recommendation usefulness and explainability;
- calibration and stability;
- false-positive cost and missed-opportunity regret;
- turnover and decision churn;
- downside behavior;
- portfolio opportunity-cost quality;
- operational robustness and evidence integrity.

**Exit outcomes only:**
- `REJECT_OR_REVISE`;
- `EXTEND_FORWARD_VALIDATION`;
- `ELIGIBLE_FOR_PHASE_5_GOVERNED_MIGRATION_PROPOSAL`.

Historical Phase 3 performance may not substitute for Phase 4.

## Phase 5 — GOVERNED MIGRATION — NOT STARTED / NOT AUTHORIZED
**Entry prerequisites:**
- Phase 3 historical validation complete and separately accepted;
- Phase 4 forward validation complete and separately accepted;
- a distinct governed migration proposal approved.

**Execution sequence:**
- **5A Migration Proposal:** state exactly which Strategy/Core semantics are proposed for effective change and why;
- **5B Rule-by-rule Treatment Map:** KEEP / MODIFY / DELETE / ADD with Legacy compatibility and rollback mapping;
- **5C Limited Activation:** activate only the approved subset under explicit monitoring;
- **5D Rollback Observation:** maintain rollback path and observe for unintended economic/decision behavior;
- **5E Final Governed Acceptance:** only after limited activation evidence is satisfactory.

Effective migration is never inferred automatically from shadow performance.
