# FMDL-3D Final — Unified Acceptance and Publication

## Purpose

FMDL-3D Final closes the valuation, capitalization and shareholder-return data layer by reconciling the accepted FMDL-3D-A contract, FMDL-3D-B effective-share and capitalization Current, FMDL-3D-C point-in-time valuation Current and FMDL-3D-D shareholder-return event Current.

The Final stage does not add a new investment score. It proves that all four component layers refer to the same Universe, market date, component releases and authority boundary, and that the combined data can be independently replayed.

## Accepted candidate

- PR: `#26`;
- accepted head: `19a513879ea80776fe58c8b034fdcfb1bf3bbbf5`;
- accepted workflow: `29690612237`;
- artifact: `8443447842`;
- artifact digest: `sha256:b73c752f9a59d3cf02709cba2131b3175c41ab0895c7d00b8746b849f629d591`;
- candidate status: `FMDL3D_VALUATION_CAPITALIZATION_AND_SHAREHOLDER_RETURN_LAYER_ACCEPTED`;
- independent validation: `PASS`;
- hard failures: `0`;
- trade authority: `NONE`.

Measured candidate result:

- market as-of date: `2026-07-17`;
- Universe / unified Current: `5,528 / 5,528`;
- valid capitalization: `5,523` symbols;
- valid valuation metrics: `24,436` rows across `5,182` symbols;
- complete shareholder yield: `5,523` symbols;
- positive dividend / buyback / dilution components: `3,612 / 951 / 1,114` symbols;
- valuation detail / shareholder events: `38,696 / 42,140` rows;
- cross-layer numeric mismatches: `0`;
- duplicate unified, valuation-detail and event keys: `0 / 0 / 0`;
- future-selected shares, denominators and shareholder events: `0 / 0 / 0`;
- replay, schema, interface, manifest and unified row-hash errors: `0`.

## Component roles

- **FMDL-3D-A** — valuation, effective-share and shareholder-event semantics;
- **FMDL-3D-B** — effective-share ledger, total market capitalization and float A-share market capitalization;
- **FMDL-3D-C** — point-in-time PE, earnings yield, PB, PS, FCF yield and conditional EV metrics;
- **FMDL-3D-D** — implemented cash dividends, completed effective-share reductions, completed dilution and shareholder-yield component evidence.

## Unified Current

`FMDL3D_UNIFIED_CURRENT.parquet` contains one row per accepted A-share Universe symbol with:

- price, effective shares and recomputed market capitalization;
- seven valuation metrics and their explicit states;
- implemented dividend, completed buyback/share-reduction and issuance-dilution components;
- complete or partial shareholder-return state;
- component release identities and lineage;
- research-only authority and zero trade authority.

The unified Current does not fill missing or inapplicable metrics with zero.

## Unified acceptance gates

The stage requires:

1. all A–D Last-success pointers and Current releases are accepted;
2. all A–D independent validations are `PASS` with no hard failures;
3. the A→B→C→D→Final gate chain is coherent;
4. C binds the accepted A and B releases, and D binds accepted A, B and C releases;
5. B, C and D have exactly the same 5,528-symbol set and market date;
6. market capitalization is identical across B, C and D and replays from price and effective shares;
7. shareholder yield replays from implemented dividend plus completed buyback minus completed dilution;
8. no future-effective share, financial denominator or shareholder event enters Current;
9. valuation detail and shareholder-event keys are unique;
10. no valuation score, target price, investment signal, portfolio mutation or trade authority exists.

## Machine interface

`FMDL3D_UNIFIED_CURRENT_INTERFACE.json` is the single machine-readable entry point for later Public Equity Investing and Investment OS integration. Consumers must still apply later research, valuation interpretation, portfolio-fit, capital-migration and user-confirmation gates.

## Controlled limitations

- prices are latest completed-session prices, not intraday prices;
- EV metric coverage remains limited when debt or cash components are incomplete;
- shareholder buyback and dilution components use completed effective-share changes rather than unverified announcement cash amounts;
- unclassified share changes remain visible in the event ledger but do not enter shareholder yield;
- the unified layer is structured research evidence, not a claim that a security is cheap, attractive or suitable for a portfolio.

## Publication

After acceptance, the stage publishes:

- immutable Release;
- Current;
- Archive;
- unified Current and interface;
- component release matrix;
- decision, validation and manifest;
- `outputs/status/FMDL3D_LAST_SUCCESS.json`.

## Exit status

`FMDL3D_VALUATION_CAPITALIZATION_AND_SHAREHOLDER_RETURN_LAYER_ACCEPTED`

## Next gate

`FMDL-3E — Incremental Refresh, Replay & Final Acceptance`

Authority: `DATA_AND_RESEARCH_EVIDENCE_ONLY`

Trade authority: `NONE`
