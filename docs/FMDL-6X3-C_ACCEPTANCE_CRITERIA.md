# FMDL-6X3-C Acceptance Criteria

The stage is accepted only when all of the following are true:

1. Release 37 is the accepted entry point and all three upstream Manifests are hash-bound.
2. All 8,785 Canonical Securities receive one Factor Status record.
3. All 27 accepted quarterly quality metrics map without neutral fill and produce three explicitly sandbox-only quality composites.
4. All 64 accepted market-history securities are accounted for; securities without a sufficient window enter an explicit queue.
5. At least 300 market-factor and 250 risk-factor observations are produced from frozen accepted bars.
6. Every market and risk row remains `NON_DECISION_GRADE_FALLBACK` and sandbox-only.
7. Valuation observations and global factor scores remain zero while TTM/annual and sector/peer gates are closed.
8. No future-dated financial or market observation is emitted.
9. Exactly 320 logical shards are manifested and same-input byte replay passes.
10. Candidate Pool, simulation, real-account and order mutations remain `0/0/0/0`; `trade_authority = NONE`.
