# FMDL-6X4-D Acceptance Criteria

FMDL-6X4-D is accepted only when all conditions below pass:

1. Accepted FMDL-6X4-C Release 44, Manifest, Decision and guardrail shards are bound.
2. The frozen roadmap is present and explicitly requires both 6X4-D and 6X4-E before FINAL.
3. All seven research benchmark-pool securities receive a simulation control and pilot-eligibility record.
4. Six issuer securities remain blocked; QQQ remains reference-only.
5. Actual position count, actual simulation-event count and executed state-transition count remain zero.
6. Exactly fifteen AAPL/MSFT/NVDA relative-to-QQQ shadow observations are consumed across five horizons.
7. All five shadow portfolio attribution windows tie out exactly.
8. All market observations retain `NON_DECISION_GRADE_FALLBACK` and sandbox-only usage.
9. Ten failure-recovery scenarios pass fail-closed validation.
10. Four recovery checkpoints are registered: Current/Release parity, Last-success, LKG and deterministic replay.
11. Six domains × 64 buckets produce exactly 384 deterministic logical shards.
12. Independent same-input replay is byte-identical.
13. Current, immutable Release, normalized output, Last-success and LKG are published.
14. Candidate Pool, simulation book, real account and order mutations remain `0/0/0/0`.
15. `trade_authority = NONE` and the only next gate is FMDL-6X4-E.
