# FMDL-7A Acceptance Criteria

FMDL-7A is accepted only when all conditions below pass in the same deterministic run.

## Entry and source binding

1. FMDL-7-0 Release 48 Last-success is present and opens only FMDL-7A.
2. Seven frozen sources bind exactly: A-share interface, Investment OS Release 8, investment-state binding, operating-state review, FMDL-5-FINAL, FMDL-5G duplication registry and FMDL-6X4-FINAL.
3. All Release IDs, sequences, statuses and `trade_authority = NONE` values match the frozen contract.

## Canonical and market inventory

4. Release 8 is identified as the sole binary Canonical base.
5. Hong Kong and US assets are identified as immutable overlays, not falsely described as repacked into Release 8.
6. A-share, Hong Kong Stock Connect and US Equity each have an explicit capability, freshness and Decision-grade posture.
7. A-share data anchored to 2026-07-17 block new full-market decision use until refreshed.
8. US market and shadow-attribution evidence remain non-Decision-grade.

## Investment state

9. Real account, simulation book and Candidate Pool remain separate state domains.
10. The bound state is explicitly labelled Last-known-good as of 2026-07-20 close, with user confirmation required for any later change.
11. Exact bound counts remain 7 real holdings, 16 simulation holdings, Candidate Core 20 and Active Memo 6.
12. Research pools, Shadow Tracks and benchmark pools are not classified as formal candidates or positions.

## Duplication and File Library

13. The real-account duplicate S&P 500 ETF exposure `159612 / 159655` is registered without automatic consolidation.
14. Midea Group `HKEX:00300` and Wuxi AppTec `HKEX:02359` remain controlled A/H duplication reviews.
15. File Library records a discoverable matching Release 8 Pointer but does not overclaim binary ZIP verification; byte verification and single-package refresh remain deferred to FMDL-7E.

## Safety, replay and publication

16. Candidate Pool, simulation book, real account, rules and orders remain unchanged at `0 / 0 / 0 / 0 / 0`; `trade_authority = NONE`; only FMDL-7B opens next.

The producer must also pass same-input byte replay, immutable Release collision protection, Current/Release/Normalized/Archive parity, Manifest hashing and LKG pointer publication.
