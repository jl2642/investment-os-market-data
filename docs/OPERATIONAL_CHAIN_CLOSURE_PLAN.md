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
- OCC-R2: financial and valuation live wiring. **IN PROGRESS**
- OCC-R3: Opportunity -> D1/D2 -> Recommendation -> Forward closure.
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

### OCC-R2A — Market-driven Valuation Live Wiring

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

TRADE_AUTHORITY = NONE.
