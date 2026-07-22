# FMDL-6X3-A Acceptance Criteria

1. Bind accepted FMDL-6X2-FINAL Release 35 and its five domain manifests.
2. Account for exactly 8,785 Canonical Securities and 7,419 Canonical Issuers.
3. Assign every Security one explicit research profile and one research scope.
4. Keep Universe membership separate from data readiness; missing data must block or downgrade, never neutral-fill.
5. Open FMDL-6X3-B only for supported research profiles with official SEC financial facts.
6. Treat the 64-security Yahoo history baseline as `NON_DECISION_GRADE_FALLBACK` and sandbox-only.
7. Preserve explicit SEC, market, ADR and special-profile review queues.
8. Produce 128 deterministic Security and Issuer readiness shards.
9. Pass same-input byte replay, Manifest integrity, Current/Release parity and LKG protection.
10. Candidate Pool, simulation, real account and orders remain unchanged; `trade_authority = NONE`.
