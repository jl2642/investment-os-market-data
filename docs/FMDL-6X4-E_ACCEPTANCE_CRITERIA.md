# FMDL-6X4-E Acceptance Criteria

FMDL-6X4-E is accepted only when all conditions below pass:

1. Accepted FMDL-6X4-D Release 45, status, next gate, Manifest and `trade_authority = NONE` are bound.
2. Investment OS Release 8, FMDL-5-FINAL Release 18 and FMDL-6X3-FINAL Release 41 are bound without changing their immutable identities.
3. Exactly three market capability records are produced for A-share, Hong Kong Stock Connect and US equity.
4. Exactly fourteen comparability dimensions and forty-two Market × Dimension assessments are produced.
5. Exactly fourteen normalization rules prohibit ticker-only matching, silent source substitution, neutral fill and unsupported metric conversion.
6. No forced common factor score and no cross-market security ranking are emitted.
7. The US market-data and shadow-attribution posture remains `NON_DECISION_GRADE_FALLBACK` and no formal performance claim is made.
8. Exactly twelve operating-runbook steps are frozen.
9. Exactly five cadence controls cover Daily, Weekly, Monthly, Quarterly and Event-driven operation; entry and recovery checks remain `EACH_RUN` controls.
10. Exactly ten escalation rules fail closed and preserve immutable Release and Last-known-good recovery.
11. Exactly eight final gates pass.
12. Seven domains × 64 buckets produce exactly 448 deterministic logical shards.
13. Independent same-input replay is byte-identical.
14. Current, immutable Release, normalized output, Last-success and LKG are published.
15. Candidate Pool, simulation book, real account and order mutations remain `0/0/0/0`.
16. Investment recommendation count and neutral-fill count remain zero.
17. `trade_authority = NONE` across every product.
18. The only next gate is FMDL-6X4-FINAL US Research Adapter Operational Acceptance and FMDL-6 Freeze.
