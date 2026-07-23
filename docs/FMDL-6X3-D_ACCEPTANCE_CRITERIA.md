# FMDL-6X3-D Acceptance Criteria

1. Bind accepted FMDL-6X3-A and FMDL-6X3-C Manifests.
2. Account for all 8,785 Canonical Securities.
3. Validate six SEC-official SIC evidence rows against Canonical Security, Issuer and CIK identity.
4. Keep internal sector/industry labels distinct from official SIC and make no GICS/ICB claim.
5. Emit zero formal peer groups when the same-industry minimum is not met.
6. Register only evidence-backed QQQ/Nasdaq-100 as the available benchmark security.
7. Keep all benchmark-relative observations non-decision-grade and sandbox-only.
8. Emit zero sector-neutral factors, zero formal peer ranks and zero global factor score.
9. Produce 320 deterministic logical shards and pass same-input byte replay.
10. Preserve Candidate Pool, simulation, real account and order mutations at zero with `trade_authority = NONE`.
