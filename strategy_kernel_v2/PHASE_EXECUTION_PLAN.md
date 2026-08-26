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
- explicit `security_id`, `as_of`, governed provenance and evidence-class coverage;
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

**Observed result:**
- 8/8 securities inventoried;
- zero real governed refresh packets can be constructed without inventing new assumptions;
- eligible non-reference uses = 0; blocked = 8;
- persist `NO_COMPARISON` as a successful fail-closed outcome.

**Validation:** Phase 2C pack-builder tests 10/10 pass; fabricated scenario/input count=0; user decision count=0; economic/Candidate mutations=0; `orders=0`; `trade_authority=NONE`.

## Phase 3 — HISTORICAL REPLAY & CALIBRATION — IN PROGRESS / 3A + 3B COMPLETE_BOUNDED
Mandatory before forward promotion. Phase 3 uses only contemporaneously available evidence and explicitly tests **model form** as well as parameter values. Probability-weighted scenarios, confidence/vector representation and any scalar utility/position-sizing rule remain hypotheses.

### Phase 3A — Point-in-time Evidence Ledger — VALIDATED COMPLETE_SCOPE_BOUNDED
**Objective:** build immutable historical evidence snapshots for replay timestamps without hindsight.

**Implemented contract:**
- evidence version identity is separate from `evidence_as_of`; replay eligibility is controlled by offset-aware `available_at`;
- Canonical source path + immutable commit SHA + provenance status are mandatory;
- by default only `CANONICAL_MAIN` evidence is replay-eligible;
- the latest version of each stable `evidence_key` available at or before the checkpoint is selected;
- later versions remain visible only as `future_evidence_ids` and cannot replace an earlier version;
- missing requirements are explicit and fail closed;
- retrospective probability/scenario backfill, model output, investment recommendation, user-decision generation, Candidate mutation, account mutation, target writeback and orders are disabled.

**Current bounded registry:** 29 Canonical evidence records, seven Canonical replay checkpoints from `2026-07-26T12:59:24Z` through `2026-08-18T01:46:25Z`, eight securities, and research/market/portfolio/Candidate/decision evidence classes.

**Validation:** 24/24 Phase 3A tests pass; every declared checkpoint requirement is reproducible; detected hindsight contamination=0; retrospective probability/scenario backfills=0; `orders=0`; `trade_authority=NONE`.

**Scope boundary:** this seven-checkpoint window is sufficient for 3B/3C engineering but not historical/statistical sufficiency. `phase3_historical_validation_complete=false` and `phase3f_promotion_eligible=false`; broader dates/regimes and all remaining gates are mandatory before 3F.

### Phase 3B — Competing Model Forms — VALIDATED COMPLETE_CONTRACT_ONLY
**Objective:** prevent the program from assuming the Phase-2 probabilistic/vector form is already correct, while also preventing competing models from receiving different historical information.

**Shared observation packet:** every model receives the exact same:
- checkpoint timestamp;
- opportunity-security set;
- Phase 3A selected evidence IDs and records;
- provenance-bound structured observations;
- reference asset, if one is explicitly supplied.

Structured observations may cite only evidence IDs already selected by the Phase 3A checkpoint. Model-specific evidence fetch is forbidden. Missing model-specific inputs produce `NOT_EVALUABLE`; they may not be retrospectively filled merely to make a model run.

**Fixed model forms:**
1. `LEGACY_POLICY_BASELINE` — contemporaneously recorded Legacy disposition/state passthrough. It does not reinterpret historical evidence using present-day reasoning and does not manufacture a Legacy ranking when no contemporaneous disposition is structured.
2. `PHASE2_PROBABILISTIC_VECTOR` — explicit contemporaneous scenario probabilities plus expected return, downside, probability of loss, confidence, concentration cost and execution friction, followed by weight-free Pareto dominance. It preserves the Phase 2A mathematical form but does not import Phase 2B current-refresh semantics into historical replay and introduces no scalar policy score.
3. `SIMPLE_NON_PROBABILISTIC_PARETO` — lower-complexity challenger using explicit return proxy, downside resilience, evidence quality, concentration cost and execution friction, with transparent Pareto dominance and no probability requirement.

**Acceptance boundary:** Phase 3B defines model forms and fairness rules only. It does not extract point-in-time historical features from source files, run decision/capital replay, calibrate probabilities or parameters, select a winning model, generate target weights, or produce comparative performance conclusions.

**Real-seed result:** the seven Phase 3A checkpoints currently contain immutable evidence references but not a model-neutral structured historical feature layer. Therefore the correct Phase 3B real-seed result is 0 evaluable across all 21 model×checkpoint combinations. Synthetic fixtures are used only to validate model mechanics and must not be interpreted as historical performance evidence.

**Validation:** 23/23 Phase 3B contract/regression tests pass in GitHub Actions; 24/24 Phase 3A dependency tests remain green; `PROGRAM_CONSISTENCY_PASS`; no model-specific evidence fetch, retrospective scenario/probability backfill, scalar policy score, target weight, recommendation, user decision, order or trade is produced.

### Phase 3C — Decision / Capital Replay — NEXT / NOT STARTED
**Objective:** produce the first actual historical comparison across the three fixed model forms without changing their information sets.

**Stage 3C-1 — Point-in-time structured feature extraction:**
- load only each Phase 3A evidence record's exact registered repository path at its exact registered commit;
- extract model-neutral structured observations from that contemporaneous source state;
- every extracted field must retain `provenance_evidence_ids` resolving inside the checkpoint's selected Phase 3A evidence;
- later research, filings, prices, Candidate states and decisions remain inaccessible;
- do not assign retrospective scenario probabilities merely because the probabilistic model needs them;
- do not use the present-day Phase 1C `source_registry.py` as a historical feature source unless the corresponding content is independently present at the historical checkpoint.

**Stage 3C-2 — Shared-packet model execution:**
- run Legacy, Phase-2 probabilistic/vector and simple non-probabilistic/Pareto forms on the same immutable packet;
- track `NOT_EVALUABLE`, admitted, blocked, prioritized, retained, reduced and `NO_ACTION` shadow states only where the model contract genuinely supports them;
- persist rationale, missing inputs and uncertainty without filling gaps differently by model.

**Non-output:** no Canonical Candidate mutation, portfolio mutation, target weight writeback, user decision, investment recommendation, order or trade.

### Phase 3D — Calibration & Regret Analysis
Measure forecast calibration/scenario coverage where genuinely available, false-positive cost, false-negative/missed-opportunity regret, downside behavior, turnover/decision instability and opportunity-cost regret versus contemporaneous cash/reference and alternatives. Maximum backtested return is not the success criterion.

### Phase 3E — Ablation / Robustness
Remove or simplify candidate components one at a time, including probability weights, confidence, concentration cost, execution friction and any later utility transformation. Identify which components add repeatable decision value and which are merely complexity.

### Phase 3F — Historical Promotion Gate
Allowed outcomes only:
- `REJECT_V2_FORM`;
- `CONTINUE_SHADOW_RESEARCH`;
- `PROMOTE_TO_PHASE_4_FORWARD_VALIDATION`.

`PROMOTE_TO_PHASE_5` is forbidden. Current entry eligibility is **false**: 3C–3E and broader historical/regime coverage remain mandatory first.

## Phase 4 — FORWARD PARALLEL SHADOW VALIDATION — MANDATORY / NOT STARTED
**Objective:** test surviving candidate Strategy Kernel model(s) on genuinely future evidence that was not available during design, replay, or calibration.

**Execution:** run Legacy and candidate models in parallel for multiple complete decision cycles; freeze or tightly govern model/policy changes during measurement windows; record decisions, uncertainty, blocked reasons, subsequent outcomes and operational failures prospectively; preserve `orders=0` and all economic mutation permissions=false.

**Exit outcomes only:** `REJECT_OR_REVISE`, `EXTEND_FORWARD_VALIDATION`, or `ELIGIBLE_FOR_PHASE_5_GOVERNED_MIGRATION_PROPOSAL`. Historical Phase 3 performance may not substitute for Phase 4.

## Phase 5 — GOVERNED MIGRATION — NOT STARTED / NOT AUTHORIZED
**Entry prerequisites:** Phase 3 historical validation complete and separately accepted; Phase 4 forward validation complete and separately accepted; distinct governed migration proposal approved.

**Execution sequence:** 5A Migration Proposal → 5B Rule-by-rule Treatment Map → 5C Limited Activation → 5D Rollback Observation → 5E Final Governed Acceptance.

Effective migration is never inferred automatically from shadow performance.
