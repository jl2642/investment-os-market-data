# FMDL-6X2-D Acceptance Criteria

1. Bind the accepted FMDL-6X2-C Release 32 pointer and preserve `trade_authority = NONE`.
2. Account for all 8,785 Security objects as initial cohort, queued backfill, or market-data quarantine.
3. Select exactly 64 deterministic initial-backfill securities, including available mandatory sentinels.
4. Require both Yahoo Chart routes; never promote a single-route result.
5. Reconcile normalized OHLCV, dividends and splits between both routes.
6. Label every market row `NON_DECISION_GRADE_FALLBACK`.
7. Produce official ECB-derived USD/CNY and USD/HKD histories with explicit cross-rate lineage.
8. Retain route payload hashes and publish all route failures and divergences.
9. Publish complete coverage and backfill queues; `full_universe_market_history_claimed` must remain false.
10. Enforce duplicate, OHLC, volume, date, Manifest, captured-input replay and LKG gates.
11. Publish Current, immutable Release, normalized, raw, Last-success and domain LKG atomically.
12. Candidate Pool, simulation, real account and order mutations remain zero.
