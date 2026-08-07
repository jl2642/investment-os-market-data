# HKCU P2B-E2 Ranks 21-40 Decision Synthesis

## Purpose

This gate continues Company Evidence Deepening after the accepted Top20 S1 decision surface. It does **not** reproduce the Top20 D1-D4 chain for another twenty names. Instead it introduces a reusable rank-window decision engine and applies the already accepted evidence semantics to P2A ranks 21-40.

## Accepted input state

After the global D1 closure, ranks 21-40 contain 60 company-specific decision dimensions across 20 securities:

- 47 `EVIDENCE_PARTIAL` rows;
- 13 non-partial / complete rows;
- 0 `RESEARCH_REQUIRED` rows.

The reusable engine rebuilds and independently validates D1, then converts the 47 Partial rows into decision semantics. Missing consensus/current results are confidence limitations, not bearish findings. Ordinary connected transactions, governance-process changes and unresolved positive optionality are not automatic blockers.

## Fresh primary-official targeted reconciliation

Five rows receive newer or decision-critical HKEX primary evidence before the security-level synthesis is frozen.

### UNI MEDICAL (`02666`)

The March connected-procurement cap exceedance is real, but the issuer disclosed monitoring thresholds, training, auditor/INED review and related remediation. It therefore remains a governance confidence cap rather than an automatic security blocker. Q1 2026 is mixed current operating evidence: revenue declined while attributable profit increased.

### JF SMARTINVEST (`09636`)

The February regulatory action identified material compliance failures and imposed a three-month suspension of new-customer acquisition. More importantly, the 29 July H1 2026 Profit Warning reported a very large decline in revenue and profit and linked the deterioration principally to that suspension. The fresh July negative signal supersedes the stale February positive-profit direction for current decision readiness.

Governance and earnings rows share one `event_id`, so the same regulatory/customer-acquisition chain is represented once at security-level blocker count rather than double-penalised across dimensions.

### JOINN (`06127`)

Q1 2026 shows revenue/order/backlog recovery, but reported profit growth is materially affected by biological-asset fair-value gains while laboratory services remain loss-making. The stale FY2025 Profit Warning therefore does not remain a permanent blocker; the company advances only with a confidence cap pending cleaner core-margin evidence.

## Expected decision surface

- 20 securities / 60 decision-dimension rows;
- 19 advance to P2B cross-sectional synthesis with confidence caps;
- JF SMARTINVEST (`09636`) remains held on one deduplicated current negative earnings/regulatory event;
- 0 alpha scores;
- 0 formal Candidate graduations.

## Engineering boundary

This gate is intentionally the first reusable window implementation. The same engine should be reused for ranks 41-60 and 61-77 with new contracts/evidence overlays, rather than creating another D2/D3/D4 pipeline family.

No A-share Candidate, Simulation or Real Portfolio mutation is allowed. No orders are created. `trade_authority=NONE`.

PASS advances to `P2B_E2_RANKS41_60_DECISION_SYNTHESIS`.
