# FMDL-5B-1｜Security Identity Contract & HK Universe Canonical Security Master

## Objective

Convert the accepted FMDL-5A Southbound universe into a stable Hong Kong security identity master without claiming unverified issuer or cross-market semantics.

## Authority

`HK_SECURITY_IDENTITY_MASTER_ONLY`

This phase may create security and provisional issuer identities. It may not modify the candidate pool, simulation portfolio, real account, rules or orders.

## Identity

- `security_id = HKEX:{stock_code_5d}`
- `issuer_id = HKISSUER-PROVISIONAL:{stock_code_5d}`
- `ticker_hk = {stock_code_5d}.HK`
- market: HKEX
- default trading currency: HKD

The provisional issuer identity is intentionally security-level. Legal issuer consolidation, A+H mapping, ADR mapping, WVR, dual-primary and secondary-listing semantics belong to FMDL-5B-2.

## Conservative classification

Only explicit name markers classify ETF or REIT. All other records remain `UNKNOWN / PENDING_SEMANTIC_ENRICHMENT`; the phase does not infer common equity merely from absence of a fund marker.

## Acceptance

- exact binding to FMDL-5A release `FMDL5A_20260720_031b3430a7d0`;
- 644 input rows and 644 output rows;
- 100% unique security IDs and stock codes;
- full required-field completeness and schema validity;
- zero investment-state mutation and `trade_authority = NONE`;
- Current, Immutable, Archive and Last-success publication on main.

## Next gate

`FMDL-5B-2_ISSUER_AND_CROSS_MARKET_SEMANTICS`
