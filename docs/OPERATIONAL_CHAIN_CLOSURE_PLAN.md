# Operational Chain Closure (OCC)

Status: COMPLETE_ACCEPTED_2026_08_31  
Scope: defect-scoped production wiring only  
Trade authority: NONE

## Program objective

Close the already-developed investment research operating chain without reopening product architecture or adding new investment capabilities.

Target production chain:

Market -> History -> Factor -> Screening -> Financial/Valuation -> Candidate/Opportunity -> D1/D2 -> Recommendation -> Trigger/Shadow -> Forward Validation -> Portfolio -> Daily Controller.

## Confirmed defect registry

| ID | Defect | Severity | OCC round |
|---|---|---:|---|
| OCC-001 | A-share Market/History/Factor can advance while Screening remains stale; same-date Daily no-op only checks Market date | P0 | R1 |
| OCC-002 | FMDL3 financial/valuation products are developed but not live-wired to current operating refresh | P0 | R2 |
| OCC-003 | Opportunity Funnel can consume stale full-market Screening | P1 | R3 |
| OCC-004 | New Longlist members do not reliably produce governed Candidate admission/removal proposals | P1 | R3 |
| OCC-005 | Recommendation is blocked by stale/non-live valuation and capital-comparison context | P0/P1 | R2-R3 |
| OCC-006 | P4-5 forward collector is not backward-compatible with older D2 source commits | P0 | R3 |
| OCC-007 | US bounded market capture can report PASS with materially inadequate coverage | P1 | R4 |
| OCC-008 | SEC official retrieval queue is not closed by a reliable operating consumer | P1 | R4 |
| OCC-009 | Portfolio marks can be fresh while portfolio decision products remain stale | P1 | R4 |
| OCC-010 | 08:00 controller runs before several morning upstream jobs | P1 | R5 |
| OCC-011 | Legacy WP3-2A provider-session failures create recurring operational noise | P2 | R4/R5 cleanup |

## Execution rounds

- OCC-R0: freeze this repair contract and defect registry.
- OCC-R1: A-share Market -> History -> Factor -> Screening coherence. **COMPLETE (2026-08-31)**
- OCC-R2: financial and valuation live wiring. **COMPLETE (2026-08-31)**
- OCC-R3: Opportunity -> D1/D2 -> Recommendation -> Forward closure. **COMPLETE (2026-08-31)**
- OCC-R4: HK/US, SEC and portfolio freshness repair. **COMPLETE (2026-08-31)**
- OCC-R5: nightly orchestration and 08:00 controller acceptance. **COMPLETE (2026-08-31)**

## R1 acceptance contract

A Daily transaction may use NO_OP_ALREADY_CURRENT only when all four accepted layers are coherent for the target session:

1. Market Current as_of_date == target session.
2. History Current as_of_date == target session.
3. Factor Current as_of_date == target session and factor.history_release_id == history.release_id.
4. Screening Current as_of_date == target session and screening.factor_release_id == factor.release_id.

If Market is already current but any downstream layer is missing, stale or lineage-mismatched, Daily must continue and repair the downstream chain.

Full Rebase is allowed to publish recovered Market/History/Factor before Screening, but must explicitly report SCREENING_REFRESH_REQUIRED rather than implying full-chain coherence.

A completed Daily transaction must fail closed if the four-layer coherence check does not pass.

## Non-goals / anti-expansion boundary

OCC does not add:
- new markets or asset classes;
- new factor families or investment strategies;
- redesigned D1/D2 research;
- redesigned Candidate architecture;
- broker integration or order execution;
- automatic Candidate membership mutation;
- automatic portfolio mutation;
- automatic trade permission.

Any newly discovered non-blocking improvement is recorded for POST_OCC_BACKLOG and is not implemented inside the active OCC round.

TRADE_AUTHORITY = NONE.


## OCC-R1 closure evidence

OCC-001 is closed.

Accepted production evidence:
- merge #370: chain-coherence no-op and fail-closed wiring;
- screening recovery run: 33353608967;
- Operating Current source branch: automation/occ-r1-screening-recovery-33353608967-a1;
- Operating Current source commit: 7515e7d21006f144b69ae44d88a0c82a7a10f5db;
- qc_status: PASS_CHAIN_COHERENT;
- Market / History / Factor / Screening as_of_date: 2026-08-28 / 2026-08-28 / 2026-08-28 / 2026-08-28;
- Screening universe: 5,551;
- Screening sleeve-detail rows: 150;
- Screening longlist: 100;
- Screening factor lineage exactly matches the accepted factor release;
- Factor history lineage exactly matches the accepted history release;
- screening_refresh_required: false;
- candidate membership mutations: 0;
- portfolio mutations: 0;
- orders: 0;
- TRADE_AUTHORITY: NONE.

The temporary recovery workflow is retired after closure. Future same-date Daily NO_OP is permitted only when the four-layer chain remains coherent.


## OCC-R2 execution split

OCC-R2 is defect-scoped into two acceptance gates after code-level audit of the retained FMDL3E implementation.

### OCC-R2A — Market-driven Valuation Live Wiring **COMPLETE (2026-08-31)**

Purpose:
- consume the latest accepted A-share Operating Current after a successful Daily run;
- reuse the accepted FMDL3E market-to-valuation propagation formulas;
- refresh market capitalization, price multiples and inverse-price valuation yields for the frozen FMDL3 financial baseline;
- publish an explicit FINANCIAL_VALUATION_CONTEXT Operating Current.

Required status semantics:
- valuation market watermark may be current;
- financial denominators remain explicitly LAST_KNOWN_GOOD;
- financial event propagation must remain PENDING_OCC_R2B;
- the frozen FMDL3 financial baseline has 5,528 symbols and must not be represented as complete coverage of the larger current market universe;
- no Recommendation, Candidate, portfolio or order mutation.

### OCC-R2B — Financial-event Propagation Repair

Confirmed defect:
FMDL3E-BC detects and can fetch live financial notices/fact deltas, but the retained FMDL3E-DE propagation implementation consumes market_delta only. Financial fact deltas are validated and preserved as evidence but are not currently applied to downstream financial factor/valuation denominator fields.

R2B therefore must:
- bind accepted filing/fact deltas into the downstream financial factor denominator state;
- recompute affected financial factors/scores and dependent valuation metrics under PIT rules;
- preserve unaffected issuers and LKG state;
- prove no future-information leakage;
- expose a truthful fresh financial watermark only after propagation succeeds.

R2A must not be used as evidence that R2B is complete.

#### OCC-R2A closure evidence

- PR #374 merged; NaN compatibility hotfix PR #375 merged.
- accepted production run: 33357411867.
- FINANCIAL_VALUATION_CONTEXT Operating Current watermark: 2026-08-28.
- source branch: automation/occ-r2a-valuation-33357411867-a1.
- row_count: 5,528.
- source market symbols: 5,551.
- matched positive-close financial-baseline symbols: 5,522.
- market coverage ratio: 0.9989146164978292.
- full-rebuild mismatch count: 0.
- financial denominator state: LKG_NOT_REFRESHED_BY_R2A.
- financial event propagation: PENDING_OCC_R2B.
- EV/Sales and EV/Operating Income are fail-closed pending exact R2B denominator refresh.
- candidate / real / simulation / order mutations: 0.
- TRADE_AUTHORITY = NONE.

#### OCC-R2B catch-up boundary

Before propagation implementation, perform a one-time index-only backlog audit from the accepted statement baseline publication date through the latest accepted completed-session market watermark.

The backlog audit:
- queries financial-report / information-change notice indexes only;
- performs no per-symbol statement fetch;
- performs no Current mutation;
- does not cap the audit to the legacy maximum_live_symbols=8;
- determines whether catch-up can be direct incremental or requires a batched cursor.

After backlog size is measured, implement only the minimum catch-up mode required by observed backlog size.

TRADE_AUTHORITY = NONE.


### OCC-R2B implementation decision

R2B financial-event propagation uses a two-mode refresh policy:

- LOW_DENSITY_REVISION_MODE: bounded 3E-BC incremental notice/fact processing for isolated post-baseline revisions.
- REPORTING_SEASON_FULL_REFRESH_MODE: reuse the existing 32-shard FMDL3B2 full-universe statement matrix, then deterministically rebuild B3 comparability, B4 statement current, 3CB financial factors, 3CD financial score and 3DC valuation.

The full-refresh path must:
- consume the latest accepted A-share Operating Current watermark as its PIT cutoff;
- exclude facts not available by the completed-session cutoff;
- block a report period when the provider's current structured values may have been contaminated by a revision whose available_from is later than the cutoff;
- publish only through governed result branches / Operating Current, never direct-push protected main;
- preserve TRADE_AUTHORITY=NONE.

Ordinary pull-request validation must not trigger the expensive 32-shard live rebuild. Production rebuild and code validation are separate gates.


### OCC-R2B1 — Financial Baseline Rebuild **COMPLETE (2026-08-31)**

Scope:
- restore latest accepted A-share market universe/interface as the PIT cutoff;
- inject that accepted market watermark into the FMDL3B2 shard runtime as pit_cutoff_as_of_date;
- reuse the existing 32-shard FMDL3B2 full-Universe statement build;
- rebuild and locally publish FMDL3B3 comparability, FMDL3B4 Statement Current, FMDL3CB financial factors, FMDL3CC hardening and FMDL3CD financial score;
- publish a governed FINANCIAL_STATEMENT_CONTEXT Operating Current;
- expose both market scan watermark and financial report-period watermark.

R2B1 is a recovery/full-baseline transaction for reporting-season catch-up. It is not a nightly workflow.


#### OCC-R2B1 closure evidence

- PR #378 merged to main.
- accepted production run: 33366663873.
- 32 / 32 financial statement shards: SUCCESS; failures: 0.
- aggregate / Statement Base: SUCCESS.
- FMDL3B3 comparability and FMDL3B4 Statement Current: SUCCESS.
- FMDL3CB financial factors, FMDL3CC hardening and FMDL3CD financial score: SUCCESS.
- FINANCIAL_STATEMENT_CONTEXT Operating Current: PASS_FINANCIAL_BASELINE_REBUILT.
- market watermark: 2026-08-28.
- financial report-period watermark: 2026-06-30.
- source branch: automation/occ-r2b1-financial-33366663873-a1.
- source commit: cacc1ed3027a14dba8eb242a331d4163f5f6b91d.
- decision-grade fact count: 2,008,449.
- decision-grade symbol count: 5,202.
- score universe: 5,551; score available: 4,995; ranking eligible: 4,501.
- score contribution replay errors: 0.
- candidate / portfolio / order mutations: 0.
- TRADE_AUTHORITY = NONE.

### OCC-R2B2 — Capitalization + Exact Valuation Rebuild **COMPLETE (2026-08-31)**

After R2B1 acceptance:
- inject latest accepted A-share market Current into the existing 16-shard FMDL3DB capitalization engine;
- rebuild exact FMDL3DC valuation using refreshed financial denominators plus refreshed capitalization;
- replace R2A's LKG financial-denominator state and EV-multiple blockers;
- publish FINANCIAL_VALUATION_CONTEXT with financial_event_propagation=COMPLETE only after exact replay passes.

R2B2 does not reopen financial-factor or scoring methodology.

#### OCC-R2B2 closure evidence

- PR #379 merged to main; merge commit: df1f44c2d2d3982c3f9d270067f0a68cbf7b5b36.
- accepted production run: 33386156007.
- capitalization shards: 16 / 16 SUCCESS; failures: 0.
- exact capitalization aggregate / validation / publication: SUCCESS.
- exact FMDL3DC valuation rebuild / validation / publication: SUCCESS.
- FINANCIAL_VALUATION_CONTEXT Operating Current: PASS_EXACT_VALUATION_REBUILT.
- market watermark: 2026-08-28.
- financial report-period watermark: 2026-06-30.
- financial_event_propagation: COMPLETE.
- source branch: automation/occ-r2b2-valuation-33386156007-a1.
- source commit: 7270d64d36a99a86173aa43d6f81fa9a290593d5.
- capitalization release: FMDL3DB_20260831T192601+0800.
- valuation release: FMDL3DC_20260831T192625+0800.
- refreshed financial factor release: FMDL3CB_20260831T170042+0800.
- valuation universe: 5,551; valuation rows: 5,551.
- capitalization coverage ratio: 0.9990992613943434.
- core resolved ratio: 0.9333934367111432.
- future denominator blocked count: 0.
- future selected denominator count: 0.
- EV/Sales valid count: 1,059.
- EV/Operating Income valid count: 776.
- automatic action authorized count: 0.
- candidate / portfolio / order mutations: 0.
- TRADE_AUTHORITY = NONE.

#### OCC-R2 closure

OCC-002 is closed. OCC-005's financial/valuation blocker is closed for R2 scope; its Recommendation-chain portion remains governed by OCC-R3.

OCC-R2 acceptance is complete only because both R2B1 financial baseline recovery and R2B2 exact capitalization/valuation replay passed production acceptance under the same accepted 2026-08-28 market watermark.

TRADE_AUTHORITY = NONE.


## OCC-R3 execution split

R3 remains one frozen repair round and is implemented in three defect-scoped gates:

### OCC-R3A — Opportunity Funnel Screening Freshness **COMPLETE (2026-08-31)**

Close OCC-003 by forcing P4-2 to restore the exact accepted Screening inputs referenced by A_SHARE_FULL_MARKET Operating Current before every validate/operate build.

R3A must:
- resolve A_SHARE_FULL_MARKET from operating-current;
- verify PASS / PASS_CHAIN_COHERENT / TRADE_AUTHORITY=NONE;
- fetch the exact source branch and require its head to equal source_commit_sha;
- restore SCREENING_MANIFEST, FMDL2C_RUN_REPORT and SCREENING_LONGLIST from that accepted commit;
- require screening manifest as_of_date == Operating Current data_watermark;
- preserve existing Funnel logic and zero protected-state mutation.


#### OCC-R3A closure evidence

- PR #381 merged; merge commit: b3c3750e401584be00bd567efaad86657256c238.
- accepted live P4-2 run: 33391415127.
- validate: SUCCESS.
- operate: SUCCESS.
- live Funnel publication: SUCCESS.
- remote readback: SUCCESS.
- OPPORTUNITY_FUNNEL Operating Current: PASS / PASS_P4_2_FUNNEL_VALIDATED.
- accepted FULL_MARKET_SCREEN watermark consumed by Funnel: 2026-08-28.
- Funnel universe: 5,551.
- Research Longlist: 100.
- D1 bounded queue: 5; automatic D2 promotion: false.
- Candidate / real / simulation / orders mutations: 0 / 0 / 0 / 0.
- TRADE_AUTHORITY = NONE.
- OCC-003 is closed.

The accepted live Funnel truthfully remains PARTIAL_STALE_UPSTREAM because Candidate Current and Candidate operating surfaces are older than the fresh Screening source; that residual is OCC-R3B scope, not an R3A failure.

### OCC-R3B — Governed Candidate Proposal Bridge **COMPLETE (2026-08-31)**

Close OCC-004 by producing explicit admission/removal proposals from fresh Longlist/Candidate deltas without automatically mutating Candidate membership.


#### OCC-R3B closure evidence

- long-lived wiring PR #382 merged to main; merge commit: 25e12725aec1fb8ac87dc303dfb49ea8c6e9f5e6.
- accepted one-shot recovery PR #385 merged to main; merge commit: 81b75d25de8a4805304d3126f28a1750b0b5f090.
- accepted production run: 33393069738.
- exact accepted Screening watermark consumed: 2026-08-28.
- accepted Screening source branch: automation/occ-r1-screening-recovery-33353608967-a1.
- accepted Screening source commit: 7515e7d21006f144b69ae44d88a0c82a7a10f5db.
- Longlist rows consumed: 100.
- proposal id: ROUND2_CANDIDATE_DELTA_20260828.
- completed weekly Candidate observation cycles: 2.
- governed admission proposals: 3 — 002827.SZ, 603268.SH, 600664.SH.
- governed dynamic exit proposals: 0.
- legacy exit reviews: 0.
- Canonical Candidate Research Queue remained 33; proposed Candidate Research Queue is 36.
- Canonical Candidate automatic mutations: 0.
- Candidate Core / Shadow / Ready automatic mutations: 0 / 0 / 0.
- portfolio mutations: 0.
- orders: 0.
- TRADE_AUTHORITY = NONE.
- OCC-004 is closed.

R3B acceptance requires only reliable governed proposal production; it does not authorize automatic application of the proposed Candidate delta. Application remains a separate human/governed merge boundary.

### OCC-R3C — Recommendation and Forward Closure **COMPLETE (2026-08-31)**

Close the remaining Recommendation portion of OCC-005 and OCC-006 by binding fresh accepted valuation/comparison context into Recommendation and making P4-5 backward-compatible with governed historical D2 source commits.


R3C implementation contract:
- Recommendation resolves FINANCIAL_VALUATION_CONTEXT from Operating Current and restores the exact accepted FMDL3DC valuation release/detail from its source commit.
- A thin adapter merges live exact valuation evidence with the frozen Phase2C research blocker context.
- Fresh-valuation blockers may be removed only when the exact accepted valuation metrics actually prove them resolved.
- A TTM P/E must not be represented as a normalized P/E; normalization-specific blockers remain explicit unless independently proven.
- Scenario probability, comparison-vector, governance, material-evidence and portfolio-fit gates remain fail-closed.
- Recommendation route_state / BUY logic is unchanged.
- P4-5 treats the exact governed D2 source commit and its resolvable D2 state/artifacts as authority; current branch ancestry is not required.
- Unresolvable D2 commits or semantic-artifact mismatches still fail closed.
- Forward checkpoint selection, R2 model, regime definition, 1/3/5-session outcome measurement and Phase-5 gate are unchanged.
- Candidate / Real / Simulation / portfolio / order mutation authority remains zero.
- TRADE_AUTHORITY = NONE.

R3 does not redesign D1/D2, Candidate methodology, recommendation scoring, forward model methodology, portfolio policy or trade authority.

#### OCC-R3C closure evidence

- PR #387 merged to main; merge commit: a6407e501ca6ac7ffb4e33c0364c805c05291498.
- accepted P4-3 production run: 33395324343.
- P4-3 validate / operate / publication / remote readback: SUCCESS / SUCCESS / SUCCESS / SUCCESS.
- RECOMMENDATION Operating Current: PASS / PASS_P4_3_RECOMMENDATION_VALIDATED.
- Recommendation source commit: a6407e501ca6ac7ffb4e33c0364c805c05291498.
- Recommendation exact valuation source commit: 7270d64d36a99a86173aa43d6f81fa9a290593d5.
- Recommendation exact valuation release: FMDL3DC_20260831T192625+0800.
- Recommendation market valuation watermark: 2026-08-28.
- 000719.SZ stale fresh-valuation blocker removed only after exact valuation binding; remaining governance / scenario blockers preserved.
- 002039.SZ exact TTM valuation bound but normalized-valuation blocker preserved.
- 301215.SZ material-evidence blocker preserved.
- BUY_NOW / BUY_ON_PRICE / BUY_ON_EVIDENCE: 0 / 0 / 0.
- ready_for_user_decision: 0.
- Candidate / Real / Simulation / target-portfolio writebacks: 0.
- orders: 0.
- TRADE_AUTHORITY = NONE.
- remaining Recommendation portion of OCC-005 is closed.

- accepted P4-5 production run: 33395324455.
- P4-5 validate: SUCCESS.
- P4-5 operate: SUCCESS.
- active collection mode detected from accepted clean baseline.
- governed RESEARCH_D2 receipts were materialized and replay path completed without source-commit ancestry requirement.
- divergent historical D2 source commits are now resolvable by exact commit identity; unresolvable commits still fail closed.
- registered-evidence discovery / checkpoint assembly / outcome refresh / publication / remote readback: SUCCESS.
- collector result: ACTIVE_FORWARD_ACCUMULATION with new_checkpoints=0, observations=0, outcome_reads=0.
- no substantive post-cutoff semantic checkpoint was eligible; publisher truthfully returned NO_OP and preserved the accepted baseline Current rather than manufacturing advancement.
- phase5_migration_allowed: false.
- Candidate / Real / Simulation / target-portfolio writebacks: 0.
- orders: 0.
- TRADE_AUTHORITY = NONE.
- OCC-006 is closed.

#### OCC-R3 closure

OCC-003, OCC-004, the Recommendation portion of OCC-005, and OCC-006 are closed under accepted production evidence.

OCC-R3 is COMPLETE. The next frozen round is OCC-R4: HK/US honesty, SEC consumer and portfolio decision freshness repair.

TRADE_AUTHORITY = NONE.


## OCC-R4 implementation contract

OCC-R4 closes OCC-007, OCC-008 and OCC-009 without reopening cross-market research, SEC evidence semantics or portfolio methodology.

### OCC-R4A/B/C are not separate user-facing rounds

R4 remains one frozen repair round with three coordinated repair surfaces:

1. US bounded coverage honesty
   - a US bucket may close only when the daily bounded rotation success ratio meets the retained weekly-quality floor and the benchmark success count meets the retained benchmark floor;
   - materially inadequate coverage must remain retryable / blocked;
   - US_BOUNDED_COVERAGE is a status authority whose PASS means the coverage assessment itself executed successfully; its qc_status carries PASS_ADEQUATE_BOUNDED_CAPTURE or BLOCKED_INADEQUATE_BOUNDED_CAPTURE;
   - CROSS_MARKET_LIMITED retains fail-closed publication semantics.

2. SEC queue operating consumer
   - reuse the existing collect_round3_sec_official.py and apply_round3_sec_observer_results.py implementation;
   - consume each generated eight-issuer queue inside the governed production job;
   - SEC_QUEUE_CONSUMER reports whether the queue was actually consumed;
   - SEC_OFFICIAL_RETRIEVAL separately reports official retrieval success / failure truth;
   - no Candidate, account, decision or order mutation.

3. Portfolio decision freshness
   - bind accepted PORTFOLIO_MARKS and accepted RECOMMENDATION Operating Current authorities;
   - restore the exact accepted Portfolio Current from the marks source commit;
   - explicitly classify the retained July WP5 action matrix as stale when it predates the current marks;
   - publish PORTFOLIO_DECISION_FRESHNESS rather than silently treating the stale legacy action matrix as current;
   - do not rebuild WP5 portfolio methodology, infer broker verification, authorize rebalancing, or create orders.

R4 acceptance requires exact-head validation plus production evidence for all three repair surfaces.

TRADE_AUTHORITY = NONE.


## OCC-R4 closure evidence

OCC-R4 closes OCC-007, OCC-008 and OCC-009 under accepted production evidence.

### US bounded coverage honesty — OCC-007 CLOSED

- core R4 PR #389 merged to main.
- SEC collector direct-execution hotfix PR #390 merged to main.
- SEC fail-closed outage hotfix PR #391 merged to main.
- cross-market state-persistence hotfix PR #392 merged to main; merge commit: 5297c7a50a1567306d0113044e75bd57bed7c18e.
- accepted final live replay run: 33401557870.
- accepted result branch: automation/occ-r4-crossmarket-acceptance-33401557870-a1.
- accepted result commit: 5023e1408ba6d4d611818b2054a3c8d2d64634e1.
- as_of_date: 2026-08-28.
- Hong Kong bounded batch: 134 / 135 success.
- United States bounded rotation: 56 / 64 success; success ratio: 0.875.
- United States benchmark: 7 / 7 success.
- bounded coverage quality: PASS_ADEQUATE_BOUNDED_CAPTURE.
- US_BOUNDED_COVERAGE Operating Current: PASS.
- CROSS_MARKET_LIMITED Operating Current: PASS / OCC_R4_REPLAY:CAPTURED_BOTH_MARKETS:PASS_ADEQUATE_BOUNDED_CAPTURE.
- the prior 1 / 71 false-positive capture condition is no longer permitted by the daily coverage gate.
- no full-US-market coverage claim is made.

### SEC queue operating consumer — OCC-008 CLOSED

- the existing collect_round3_sec_official.py and apply_round3_sec_observer_results.py chain is now live-wired into governed production.
- accepted run 33401557870 generated and consumed an eight-issuer SEC queue.
- SEC_QUEUE_CONSUMER Operating Current: PASS / PASS_QUEUE_CONSUMED:success=0:failure=8.
- all 8 / 8 queue rows were processed; the consumer did not stall or require manual ChatGPT observer completion.
- the SEC global ticker-map endpoint returned HTTP 403 from the GitHub runner environment.
- ticker-map-dependent issuers therefore remain explicit SEC_DATA_GAP rather than fabricating official evidence.
- SEC_OFFICIAL_RETRIEVAL latest attempt: BLOCKED / PENDING_CONTROLLED_OFFICIAL_RETRIEVAL:success=0:failure=8.
- no SEC_OFFICIAL_RETRIEVAL Current pointer is manufactured while official retrieval has zero success.
- external SEC endpoint availability is a truthful data-availability boundary, not an unresolved queue-consumer wiring defect.

### Portfolio decision freshness — OCC-009 CLOSED

- accepted production run: 33399403880.
- PORTFOLIO_DECISION_FRESHNESS Operating Current: PASS.
- qc_status: PASS_FRESH_INPUTS_BOUND_STALE_LEGACY_DECISION_BLOCKED.
- portfolio marks watermark: 2026-08-28.
- accepted Recommendation source run: 33395324343.
- accepted Recommendation source commit: a6407e501ca6ac7ffb4e33c0364c805c05291498.
- Real holdings: 7.
- Simulation holdings: 16.
- required fresh marks: 22 / 22.
- legacy WP5 portfolio decision generated 2026-07-27 is explicitly classified stale against current marks.
- legacy action matrix current: false.
- implementation_ready: false.
- ready_for_user_decision: false.
- automatic rebalance / position change authority: false / false.

### Cross-market state continuity hardening

- the accepted CROSS_MARKET_LIMITED source branch now carries:
  - CROSS_MARKET_LIMITED_LEDGER_CURRENT.json;
  - CROSS_MARKET_LIMITED_RUN_CURRENT.json;
  - CROSS_MARKET_RESEARCH_PROPOSAL_CURRENT.json.
- normal Round 3 schedule / dispatch production now restores the exact accepted Operating Current source branch + commit before processing the next session.
- missing state files fail closed instead of silently restarting from empty protected main.
- accepted state source commit: 5023e1408ba6d4d611818b2054a3c8d2d64634e1.

### R4 authority boundary

- Candidate membership mutations: 0.
- Real-account mutations: 0.
- Simulation mutations: 0.
- portfolio action writebacks: 0.
- orders: 0.
- TRADE_AUTHORITY = NONE.

OCC-011 legacy WP3-2A provider-session noise remains eligible for R5 cleanup only if it materially affects final nightly/controller acceptance; it is not allowed to expand the R5 scope.

OCC-R4 is COMPLETE. The final frozen repair round is OCC-R5: nightly orchestration and 08:00 controller acceptance.

TRADE_AUTHORITY = NONE.


## OCC-R5 implementation contract

OCC-R5 is the final frozen repair round. It closes OCC-010 and retires OCC-011 scheduled noise without adding a new investment engine.

### Nightly production topology

The 08:00 Asia/Shanghai controller must read the previous completed production chain rather than racing morning upstream jobs.

Target Asia/Shanghai sequence:

- 17:30 — FMDL Daily A-share Governed Production.
- after FMDL Daily success — OCC-R2A market-driven valuation and WP3-R Dynamic Candidate Loop remain event-driven.
- 22:45 — WP2-R Portfolio Marks Refresh.
- 23:30 — Research Queue D2 Auto Consumer.
- 00:30 — P4-2 Continuous Opportunity Funnel.
- 01:15 — P4-3 Unified Decision Recommendation.
- after successful P4-3 — PORTFOLIO_DECISION_FRESHNESS refreshes by one-level workflow_run.
- 02:00 — P4-4 Trigger Monitor / Shadow Book.
- 02:45 — P4-5 Forward Validation.
- 05:30 — Round 3 HK/US Limited Production + SEC queue consumer, using the previous Asia/Shanghai date and accepted cross-market state.
- 08:00 — ChatGPT 股票投资助手每日总控 reads the completed prior chain.

The staggered schedule intentionally uses wide buffers instead of a workflow_run chain deeper than GitHub Actions permits. Any upstream failure remains fail-closed and must be reported by the controller through Current/latest-attempt semantics.

The ChatGPT-native semantic D2 deep-research consumer remains asynchronous and fail-closed. It is not allowed to fabricate completion merely to satisfy the nightly clock; pending semantic research is reported as pending.

### 08:00 controller authority contract

The controller must continue to read the existing core domains and additionally read:

- FINANCIAL_STATEMENT_CONTEXT;
- FINANCIAL_VALUATION_CONTEXT;
- US_BOUNDED_COVERAGE;
- SEC_QUEUE_CONSUMER;
- SEC_OFFICIAL_RETRIEVAL Current if present and latest attempt even when no Current exists;
- PORTFOLIO_DECISION_FRESHNESS.

Controller semantics:
- distinguish a healthy SEC queue consumer from unavailable official SEC data;
- distinguish fresh portfolio marks / decision-freshness context from the stale legacy WP5 action matrix;
- distinguish Current from LATEST_ATTEMPT_FAILED_CURRENT_PRESERVED;
- do not classify an external provider outage as a systemic investment-engine failure when the consumer and fail-closed controls operate correctly;
- do not claim full-market US coverage from the bounded US authority;
- no workflow green status alone is sufficient to declare the system healthy.

### OCC-011 cleanup

WP3-2A Universe Refresh is retained as a manual diagnostic / proposal workflow, but its five legacy provider-session schedules are retired. The current authoritative A-share production chain is FMDL Daily + Operating Current. Removing the legacy schedules reduces operational noise without deleting the historical capability.

### R5 acceptance

R5 requires:
1. exact-head contract checks;
2. merged schedule/orchestration changes;
3. an immediate controller-equivalent acceptance read using current Operating Current authorities, without waiting for the next natural 08:00;
4. confirmation that the formal 08:00 automation remains enabled and its prompt follows the controller authority contract;
5. orders=0 and TRADE_AUTHORITY=NONE.

No broker integration, automatic Candidate application, portfolio rebalance, order creation or Phase-5 migration is authorized.

TRADE_AUTHORITY = NONE.


## OCC-R5 closure evidence

OCC-R5 closes OCC-010 and OCC-011 under exact-head validation, merged orchestration changes and immediate controller-equivalent acceptance.

### Nightly orchestration — OCC-010 CLOSED

- PR #395 merged to main.
- merge commit: cb78b08d0f53dd44997492514daba9dfccb61854.
- exact-head required checks: all SUCCESS or intentionally SKIPPED.
- final required build-real-candidate run: 33405171025 / SUCCESS.
- merged main schedule readback:
  - FMDL Daily A-share: 17:30 Asia/Shanghai.
  - WP2-R Portfolio Marks: 22:45.
  - Research Queue D2 Auto Consumer: 23:30.
  - P4-2 Opportunity Funnel: 00:30.
  - P4-3 Recommendation: 01:15.
  - PORTFOLIO_DECISION_FRESHNESS: success-only workflow_run after P4-3 main success.
  - P4-4 Trigger / Shadow: 02:00.
  - P4-5 Forward Validation: 02:45.
  - Round 3 HK/US + SEC: 05:30, using previous Asia/Shanghai date semantics.
  - formal ChatGPT controller: 08:00 Asia/Shanghai.
- the formal 08:00 controller automation remains enabled on Monday-Saturday and its schedule was not moved.
- the controller prompt now explicitly reads:
  - FINANCIAL_STATEMENT_CONTEXT;
  - FINANCIAL_VALUATION_CONTEXT;
  - US_BOUNDED_COVERAGE;
  - SEC_QUEUE_CONSUMER;
  - SEC_OFFICIAL_RETRIEVAL Current if present plus latest attempt when Current is absent;
  - PORTFOLIO_DECISION_FRESHNESS;
  in addition to the retained core and Strategy Kernel domains.
- controller semantics explicitly distinguish Current from latest-attempt failure/no-op, healthy SEC consumer from unavailable SEC official data, bounded US coverage from full-market coverage, and fresh portfolio inputs from the stale legacy WP5 action matrix.

### Legacy provider-session noise — OCC-011 CLOSED

- WP3-2A Universe Refresh retains manual workflow_dispatch diagnostic/proposal capability.
- its legacy scheduled provider-session retries are removed.
- authoritative A-share production remains FMDL Daily + Operating Current.
- no historical capability was deleted.

### Immediate controller-equivalent acceptance

The post-R4 Operating Current authority surface was read directly before closure and is internally consistent:

- A_SHARE_FULL_MARKET: PASS / 2026-08-28 / PASS_CHAIN_COHERENT.
- PORTFOLIO_MARKS: PASS / 2026-08-28.
- CANDIDATE_WEEKLY_OBSERVATION: PASS / 2026-08-28.
- RESEARCH_D2: PASS / 2026-08-31T05:57:01Z.
- CROSS_MARKET_LIMITED: PASS / 2026-08-28 / adequate bounded coverage.
- FINANCIAL_STATEMENT_CONTEXT: PASS / market watermark 2026-08-28 / financial baseline rebuilt.
- FINANCIAL_VALUATION_CONTEXT: PASS / 2026-08-28 / exact valuation rebuilt.
- OPPORTUNITY_FUNNEL: PASS / 2026-08-31T12:23:39Z.
- RECOMMENDATION: PASS / 2026-08-31T13:10:23Z.
- TRIGGER_MONITOR: accepted Current retained; latest attempt is truthful semantic NO_OP.
- SHADOW_BOOK: accepted Current retained; latest attempt is truthful semantic NO_OP.
- FORWARD_VALIDATION: accepted clean baseline retained; latest attempt is NO_OP_NO_NEW_ELIGIBLE_FORWARD_CHECKPOINT.
- US_BOUNDED_COVERAGE: PASS / rotation ratio 0.875 / benchmark success 7.
- SEC_QUEUE_CONSUMER: PASS / queue consumed / success=0 / failure=8.
- SEC_OFFICIAL_RETRIEVAL: no manufactured Current; latest attempt BLOCKED because official SEC retrieval was unavailable from the GitHub runner.
- PORTFOLIO_DECISION_FRESHNESS: PASS / fresh marks + current Recommendation bound; stale July WP5 action matrix explicitly blocked.

The immediate controller-equivalent read therefore proves that the controller can distinguish healthy production, semantic no-op, preserved LKG, stale legacy decision state and external data-source unavailability without fabricating system health or investment readiness.

### Final OCC authority boundary

- Candidate membership automatic mutations: 0.
- Real-account automatic mutations: 0.
- Simulation automatic mutations: 0.
- automatic portfolio action writebacks: 0.
- broker integration: none.
- orders: 0.
- TRADE_AUTHORITY = NONE.
- Phase-5 migration remains separately governed and is not authorized by OCC closure.

## OCC final closure

OCC-001 through OCC-011 are closed within the frozen scope.

The Operational Chain Closure repair program is COMPLETE.

The retained production system now provides a governed investment-research and decision-support chain with explicit freshness, lineage, blocker, no-op and external-data-gap semantics. OCC completion does not imply that every investment candidate is actionable, every external provider is always available, or autonomous trading is permitted.

Future defects are normal operations / AUTO_RECOVERY or POST_OCC_BACKLOG unless they demonstrate a new systemic break in the accepted chain.

TRADE_AUTHORITY = NONE.
