# HKCU P2B-E2 — Primary Company Evidence, Ranks 21–40

This is the second deterministic P2B-E2 primary-company-evidence tranche. It extends the already accepted ranks 1–20 state without changing any previously accepted evidence.

## Scope

- P2A ranks: **21–40**
- securities: **20**
- company-specific dimensions per security: **3**
- batch evidence slots: **60**

The three dimensions remain:

1. `GOVERNANCE_VALUE_TRAP`
2. `EARNINGS_EXPECTATION_REVISION`
3. `CATALYST`

## Evidence standard

Collected evidence uses the issuer's HKEX title-search/disclosure surface as the primary official source. Search-engine snippets are never authority.

A current annual, interim or quarterly result may support operating context but is not labelled as a consensus revision. `EVIDENCE_COMPLETE` for earnings-expectation change is reserved in this batch for explicit management expectation-change disclosures such as a profit alert, profit warning, estimated results or estimated profit increase.

Catalysts must be dated, company-specific and falsifiable. Routine filings with no unresolved forward investment implication remain `RESEARCH_REQUIRED`.

No qualitative alpha score is created in E2.

## Batch result encoded by the evidence register

Ranks 21–40 contain:

- **54 / 60** collected primary-evidence slots;
- **5** `EVIDENCE_COMPLETE` rows, all direct earnings-expectation-change evidence;
- **49** `EVIDENCE_PARTIAL` rows;
- **6** `RESEARCH_REQUIRED` rows.

Direct expectation-change evidence is recorded for:

- Huishang Bank — positive profit alert;
- JOINN — estimated H1 2026 results / profit-warning classification;
- Laopu Gold — positive profit alert;
- CSC Financial — estimated profit increase for H1 2026;
- GenScript Biotech — profit warning.

## Cumulative state after this batch

The pipeline first rebuilds and independently validates the accepted ranks 1–20 E2 state, then overlays ranks 21–40. No key overlap is allowed.

Expected cumulative state:

- **40 securities** covered by company-specific primary-evidence tranches;
- **120** cumulative batch evidence rows;
- **108** collected evidence rows;
- **8** `EVIDENCE_COMPLETE` company-specific tasks;
- **223** company-specific tasks remain open;
- **123** remain wholly unstarted / `RESEARCH_REQUIRED`.

A successful gate advances to ranks 41–60. It does not graduate any security to the formal Hong Kong Candidate Pool.

## Protected state

No A-share Candidate mutation, HK Candidate graduation, Simulation mutation, Real Portfolio mutation or order creation is permitted.

`trade_authority=NONE`.
