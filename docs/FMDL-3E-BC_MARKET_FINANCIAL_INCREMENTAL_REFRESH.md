# FMDL-3E-B/C — Market and Financial PIT Incremental Refresh

## Purpose

Validate the first real operating deltas after the frozen FMDL-3D Baseline-0:

1. a strictly later completed A-share market session;
2. first-disclosure financial PIT arrival;
3. correction, supplement or restatement revision-chain replay;
4. explicit affected-symbol and affected-period routing;
5. immutable baseline and source-file protection.

## Phase boundary

This phase creates and accepts delta assets only. It does not yet propagate changes into financial factors, capitalization, valuation, shareholder return or FMDL-3D Unified Current. Downstream propagation, full-vs-incremental equality, failure injection and rollback are FMDL-3E-D/E.

## Operating modes

- `fixture`: deterministic PR validation. Market values are deterministic fixtures; financial revision cases use real accepted historical PIT revision chains from FMDL-3B-4.
- `live`: main-branch production. FMDL-1 Current is refreshed first, the new completed market session is compared with Baseline-0, and recent public financial notices are detected. Where no post-baseline correction/restatement exists in the bounded window, real historical revision chains are used to prove PIT version selection without fabricating old numeric values.

## Acceptance

- FMDL-3E-A pointer and Baseline-0 identity align;
- all frozen FMDL-3D source hashes remain unchanged;
- market date strictly advances and symbol coverage is at least 99%;
- event IDs are unique and every event has explicit affected scope;
- at least one first-disclosure case and one revision case exist;
- old document versions remain preserved in the version ledger;
- future information count is zero;
- authority is research evidence only and trade authority is `NONE`.

## Exit

`FMDL3EBC_MARKET_AND_FINANCIAL_INCREMENTAL_REFRESH_ACCEPTED`

Next gate:

`FMDL-3E-DE_PROPAGATION_RESILIENCE_AND_REPLAY`
