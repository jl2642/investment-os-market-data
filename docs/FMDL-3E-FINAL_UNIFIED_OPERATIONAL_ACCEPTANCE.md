# FMDL-3E-Final — Unified Operational Acceptance & Canonical Closure

## Purpose

Close the fourth and final round of FMDL-3E without rebuilding the accepted FMDL-3D baseline or re-performing FMDL-3E-A through FMDL-3E-E.

The phase binds the accepted release chain, verifies the propagated Unified Current against the independent full-rebuild reference, freezes operating watermarks and entrypoints, publishes an explicit canonical pointer and moves the program gate to FMDL-4.

## Canonical chain

1. FMDL-3D-Final — frozen valuation, capitalization and shareholder-return baseline.
2. FMDL-3E-A — incremental contract and Baseline-0.
3. FMDL-3E-B/C — market and financial PIT delta assets.
4. FMDL-3E-D/E — downstream propagation, full rebuild, idempotence, failure injection and LKG protection.
5. FMDL-3E-Final — unified operating state and canonical closure.

## Acceptance

Acceptance requires:

- all four input pointers and Current Releases have matching IDs and accepted statuses;
- one common Baseline-0 identity across A, B/C and D/E;
- exact FMDL-3D and FMDL-3E release lineage;
- 5,528 unique Unified Current symbols;
- zero trade-authority rows;
- zero incremental-versus-full-rebuild mismatch;
- semantic hashes independently reproduce;
- same-input idempotence is zero mismatch;
- duplicate-symbol, future-event and corrupt-hash injections are rejected;
- non-null Current and Last-success hashes remain unchanged after failure;
- all operational workflow and runner entrypoints exist;
- immutable Release, Current, Archive, Final Last-success and Canonical Last-success are published.

## Operating policy

- A later completed market session routes through FMDL-3E-B/C, then FMDL-3E-D/E, then FMDL-3E-Final.
- Same-date input is a no-op or semantically idempotent validation run.
- Failed candidates never move Current or Last-success.
- Manual recovery may force the operational cycle through workflow dispatch.
- The weekday scheduler is 19:45 Asia/Shanghai.

## Controlled limitations

- Until a completed session later than Baseline-0 is observed, the accepted proof remains a real completed-session replay.
- Historical financial correction cases retain document-version PIT lineage where pre-revision structured values were not retained; values are not fabricated.
- No alpha claim, candidate-pool mutation, portfolio action, order generation or trade authority is created.

## Exit

`FMDL3E_UNIFIED_OPERATIONAL_ACCEPTANCE_AND_CANONICAL_CLOSURE_ACCEPTED`

Next gate:

`FMDL-4_PUBLIC_EQUITY_INVESTING_AND_INVESTMENT_OS_INTEGRATION`
