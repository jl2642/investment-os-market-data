# FMDL-6X3-E Acceptance Criteria

1. Bind accepted Releases 36–39 and their Manifests.
2. Account for all 8,785 Canonical Securities.
3. Emit exactly one Research Card and one screening disposition per Security.
4. Preserve exact disposition counts: 3 core sandbox, 3 filing watch, 1 benchmark reference, 39 market/risk observation, 5,428 data backfill, 1,601 reference-only, 437 review-required and 1,273 excluded.
5. Freeze a seven-member US research benchmark pool containing AAPL, MSFT, NVDA, JPM, BRK.B, XOM and QQQ.
6. Keep the benchmark pool separate from the Investment OS candidate pool and emit zero investment recommendations.
7. Emit zero formal valuation ranks, zero formal peer ranks, zero global ranks and zero candidate promotions.
8. Preserve Yahoo-derived market inputs as non-decision-grade and use no neutral fill or silent substitution.
9. Produce 256 deterministic logical shards and pass same-input byte replay.
10. Preserve Candidate Pool, simulation, real account and order mutations at zero with `trade_authority = NONE`.
