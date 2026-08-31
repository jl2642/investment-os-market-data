# Operational Chain Closure (OCC)

Status: ACTIVE_REPAIR_PROGRAM  
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
- OCC-R3: Opportunity -> D1/D2 -> Recommendation -> Forward closure. **IN PROGRESS**
- OCC-R4: HK/US, SEC and portfolio freshness repair.
- OCC-R5: nightly orchestration and 08:00 controller acceptance.

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

### OCC-R3C — Recommendation and Forward Closure

Close the remaining Recommendation portion of OCC-005 and OCC-006 by binding fresh accepted valuation/comparison context into Recommendation and making P4-5 backward-compatible with governed historical D2 source commits.

R3 does not redesign D1/D2, Candidate methodology, recommendation scoring, forward model methodology, portfolio policy or trade authority.

TRADE_AUTHORITY = NONE.
