# FMDL-6X1-B Acceptance Criteria

The phase may be accepted only when all conditions pass:

1. FMDL-6X1-A Last-success and Release are bound exactly.
2. `XNYS`, `XNAS` and `XASE` are the only included primary venues; expansion requires change control.
3. Security Master membership is separated from issuer research eligibility.
4. No price, market-cap, liquidity, profitability or index filter is used for Security Master membership.
5. Research, channel, portfolio and listing-lifecycle statuses are orthogonal.
6. Core, special-profile, reference-only, excluded and quarantine instrument routes are explicit.
7. ADR underlying and ratio evidence are mandatory for research eligibility.
8. REIT, BDC, PTP/MLP, royalty trust and SPAC profiles cannot enter the standard industrial factor engine.
9. Active, delisted, acquired, renamed and transferred identity history is retained point-in-time.
10. Fallbacks cannot silently create decision-grade classifications.
11. Live security rows, candidate, simulation, real-account and order mutations are all zero.
12. Deterministic validation and negative regression tests pass.
13. `trade_authority = NONE`.

Required exit:

`FMDL6X1B_ANTICIPATED_RESEARCH_UNIVERSE_AND_INSTRUMENT_BOUNDARY_ACCEPTED`

Next gate:

`FMDL-6X1-C_SOURCE_COST_AND_EXECUTION_ROUTE_REVALIDATION`
