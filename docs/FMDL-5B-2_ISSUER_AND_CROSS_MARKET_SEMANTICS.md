# FMDL-5B-2 — Issuer & Cross-Market Semantics

## Purpose

FMDL-5B-2 upgrades the accepted 644-row Hong Kong security master from security-level provisional identities to an evidence-tiered issuer and market-semantics layer.

It does not create investment recommendations, candidate admissions, simulation entries, real-account actions or orders.

## Authoritative inputs

- `FMDL5B1_20260720_d31e787a3ccd` — accepted Southbound security master.
- HKEX Full List of Securities — official category, sub-category, board lot, ISIN, trading currency and RMB-counter field.
- HKEX Dual Counter Security List — official HKD/RMB counter pairs and effective dates.
- HKEX Disclosure of Interests stock-code search — official listed-corporation name and stable DI security identifier returned for an exact stock code.
- HKEX official equity naming conventions — suffix semantics such as `-W`, `-S`, `-SW` and `-B`.

## Identity policy

Every accepted Southbound security retains its immutable `security_id` from FMDL-5B-1.

Corporate issuer objects are created from the official HKEX DI corporation name returned for the exact stock code. Only explicit terminal share-class or listing-status suffixes are removed during deterministic economic-issuer normalization. No fuzzy-name-only canonical merge is permitted.

ETF and REIT issuer objects are fund-level objects anchored by the official ISIN.

## Evidence states

- `CONFIRMED`: direct official HKEX evidence.
- `REVIEW_REQUIRED`: a relationship requires another market's official identifier before it can be confirmed.
- `UNRESOLVED`: insufficient evidence; no relationship is inferred.

## Confirmed semantics

The production overlay records:

- official security category and sub-category;
- board lot and ISIN;
- trading currency;
- HKD/RMB dual-counter relationship;
- WVR suffix;
- secondary-listing suffix;
- Chapter 18A biotech suffix;
- H-share designation found in the official corporation name;
- depositary-receipt and GEM code-range semantics;
- multiple HK share classes consolidated only through exact official issuer-name normalization.

## Deliberate limitations

- An H-share flag does not automatically establish a current A-share ticker relationship.
- A secondary listing or WVR flag does not automatically establish a US ticker or ADR relationship.
- Mainland and US ticker mappings require direct official evidence and are kept in the review queue or deferred to the relevant market adapter.
- Security semantics do not imply research graduation or portfolio admission.

## Acceptance gates

- exactly 644 semantic-overlay rows and bridge rows;
- unique security identity;
- at least 95% official DI issuer mapping coverage for equity securities;
- all official sources hashed and registered;
- all confirmed relationship rows backed by an explicit official source;
- Current, immutable Release, Archive and Last-success published only after main acceptance;
- zero candidate, simulation, real-account and order mutation;
- `trade_authority = NONE`.

## Exit

Expected status:

`FMDL5B2_ISSUER_AND_CROSS_MARKET_SEMANTICS_ACCEPTED`

Next gate:

`FMDL-5C_PRICE_VOLUME_CORPORATE_ACTION_AND_FX_STORE`
