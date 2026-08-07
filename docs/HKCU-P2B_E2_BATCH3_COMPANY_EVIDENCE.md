# HKCU P2B-E2 — Company Evidence Batch 3 (Ranks 41–60)

Batch 3 continues the accepted P2B-E2 primary-company-evidence architecture from ranks 1–40. It does not alter any previously accepted evidence.

## Scope

- Accepted P2A ranks: **41–60**
- Securities: **20**
- Dimensions per security: **3**
- Evidence slots: **60**

Dimensions remain `GOVERNANCE_VALUE_TRAP`, `EARNINGS_EXPECTATION_REVISION`, and `CATALYST`.

## Evidence standard

Collected rows use the issuer HKEX disclosure/title-search surface as the primary official authority. Evidence dates may not exceed 2026-08-07. Search snippets are not authority.

Ordinary annual, quarterly, KPI or operating results remain partial evidence for earnings context; they do **not** become analyst-consensus revisions. Direct management expectation-change evidence is marked complete only where the issuer explicitly issued a profit alert or results forecast.

Catalyst evidence must be dated, security-specific and falsifiable. Routine updates, governance events or bank capital issuance that do not establish a directional unresolved investment catalyst remain `RESEARCH_REQUIRED`.

No qualitative alpha score is created in P2B-E2.

## Audited Batch 3 result

The evidence register contains:

- **7** `EVIDENCE_COMPLETE` rows;
- **46** `EVIDENCE_PARTIAL` rows;
- **7** `RESEARCH_REQUIRED` rows;
- **53 / 60** collected primary-evidence rows.

The seven direct earnings-expectation-change rows are:

- Wanguo Gold — Positive Profit Alert;
- WuXi Biologics — Positive Profit Alert;
- CHICMAX — Positive Profit Alert;
- Lee & Man Paper — Positive Profit Alert;
- Qunabox Group — Positive Profit Alert;
- Tianqi Lithium — 2026 Interim Results Forecast / Profit Warning classification;
- Newborn Town — Inside Information Profit Alert.

## Cumulative state after Batch 3

The pipeline first rebuilds and independently validates canonical Batch 2, then overlays ranks 41–60 only onto rows that were still `RESEARCH_REQUIRED`.

Expected cumulative state:

- **60 / 77 securities** started;
- **180** cumulative evidence rows;
- **159** evidence rows collected;
- **15** company-specific tasks `EVIDENCE_COMPLETE`;
- **144** `EVIDENCE_PARTIAL`;
- **72** still `RESEARCH_REQUIRED`;
- **216** company-specific tasks remain open;
- **72** remain wholly unstarted.

PASS advances to the final ranks 61–77 company-specific evidence tranche. It does not graduate any security to the formal Hong Kong Candidate Pool.

## Protected state

No A-share Candidate mutation, HK Candidate graduation, Simulation mutation, Real Portfolio mutation or order creation is permitted.

`trade_authority=NONE`.
