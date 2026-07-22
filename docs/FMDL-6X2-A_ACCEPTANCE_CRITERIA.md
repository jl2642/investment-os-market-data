# FMDL-6X2-A Acceptance Criteria

Acceptance requires all of the following:

1. The accepted FMDL-6X1 Final pointer authorizes FMDL-6X2-A.
2. Both official directory routes return non-empty HTTP 2xx payloads.
3. Headers exactly match the frozen contracts and each source contains exactly one official footer.
4. Every logical source data/footer row has exactly one ledger disposition: `INCLUDED`, `EXCLUDED`, `QUARANTINED`, or `ACCOUNTED_METADATA`.
5. All `XNAS`, `XNYS`, and `XASE` target rows are included or quarantined; all mapped non-target rows are excluded.
6. No silent source substitution, silent row drop, neutral fill, or fabricated identity/effective date.
7. Zero duplicate included provisional record IDs and zero duplicate active listing observation keys.
8. Canonical security IDs issued in this phase equal zero; identity remains pending FMDL-6X2-B.
9. All 192 venue/bucket shards are present in the shard manifest, including empty shards.
10. Captured-input replay is byte-identical.
11. Current and immutable Release are byte-identical before pointers advance.
12. A failed run cannot replace Current or LKG.
13. Candidate, simulation, real-account, and order mutations remain zero.
14. `trade_authority = NONE`.
15. Exit status is `FMDL6X2A_CURRENT_SECURITY_MASTER_PRODUCTION_ACCEPTED`; next gate is FMDL-6X2-B.
