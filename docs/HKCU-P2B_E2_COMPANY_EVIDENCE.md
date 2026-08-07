# HKCU Phase 2B-E2 — Company-Specific Evidence Intake

## Purpose

P2B-E2 starts from the accepted 77-name P2A Research Longlist after P2B-E1 has already closed common transaction/tax evidence and A/H applicability. This stage collects company-specific evidence for the three remaining dimensions:

1. `GOVERNANCE_VALUE_TRAP`
2. `EARNINGS_EXPECTATION_REVISION`
3. `CATALYST`

The first E2 gate is a **full-77 structured evidence intake**, not a final qualitative scoring pass.

## Why this gate exists

The repository already depends on AKShare and can retrieve structured Hong Kong company profile, financial-indicator and dividend data. Reusing these interfaces is preferable to manually rebuilding the same factual context for every company.

However, the source authority is explicitly `SECONDARY_STRUCTURED_PUBLIC_DATA`. Therefore:

- company profile and financial context can generate governance/value-trap **research leads**, but cannot close the primary governance review;
- rolling revenue or profit growth is **not** earnings-expectation revision and may never be substituted for consensus revision or dated management guidance;
- dividend events are dated catalyst leads only and still require issuer/HKEX confirmation before becoming final catalyst evidence;
- no qualitative alpha score is generated in this gate.

## Live source interfaces

The workflow calls, for each of the 77 accepted names:

- `akshare.stock_hk_company_profile_em`
- `akshare.stock_hk_financial_indicator_em`
- `akshare.stock_hk_dividend_payout_em`

The company-profile feed is also used to capture the issuer website as a **primary-source lead URL** for the next primary-evidence review.

## Outputs

A successful live run emits:

- `HKCU_P2B_E2_COMPANY_EVIDENCE_INTAKE.csv` — one company evidence packet per accepted security;
- `HKCU_P2B_E2_DIMENSION_EVIDENCE.csv` — 77 × 3 company-specific dimension records;
- `HKCU_P2B_E2_PRIMARY_RESEARCH_QUEUE.csv` — the controlled primary-evidence queue, bucketed by P2A rank;
- `HKCU_P2B_E2_FETCH_ERRORS.csv` — explicit network/data gaps;
- `HKCU_P2B_E2_QUALITY_REPORT.json`;
- `HKCU_P2B_E2_DECISION.json`;
- `HKCU_P2B_E2_MANIFEST.json`.

The top 20 P2A names form the first primary-evidence priority bucket: 20 securities × 3 dimensions = 60 tasks. This is a **research priority only**, not a Candidate graduation rule.

## Acceptance boundary

This gate passes only when all 77 securities and all 231 company-dimension rows are represented, no unsupported score is present, and structured company-profile/financial coverage remains above the fail-closed minimum. Missing company data is recorded rather than fabricated.

A PASS advances to `P2B_E2_PRIMARY_COMPANY_EVIDENCE_TOP20`.

## Protected state

P2B-E2 does not modify A-share Candidate state, formal Hong Kong Candidate membership, Simulation, Real Portfolio, orders, or trade authority.

`trade_authority=NONE`.
