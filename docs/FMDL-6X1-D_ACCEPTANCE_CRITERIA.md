# FMDL-6X1-D Acceptance Criteria

FMDL-6X1-D is accepted only when all conditions below pass:

1. The accepted FMDL-6X1-C Last-success pointer is bound exactly.
2. Full-build domains cover identity, market/reference, SEC/fundamentals and controlled review.
3. The source contract preserves Nasdaq official directory routes, controlled SEC official ingress, non-decision-grade market fallback labels, ECB-first FX and no silent substitution.
4. Historical identity, market and SEC coverage targets are explicit and prohibit fabricated dates, survivorship-only backfill and neutral fill.
5. Storage, 64-bucket sharding, manifests, Current/Release/Archive, Last-success and per-domain LKG are frozen.
6. Quality gates cover identity uniqueness, point-in-time history, market gaps/events, SEC accession lineage, research-profile routing and release replay/failure protection.
7. Cost policy preserves USD 0 paid subscriptions unless the user separately approves a paid route.
8. FMDL-6X2 is fixed to exactly six stages, ending in `FMDL-6X2-FINAL`.
9. FMDL-6X2 program entry remains behind `FMDL-6X1-FINAL`; FMDL-6X2-E additionally requires proof of an official SEC execution environment.
10. Required handoff assets are enumerated.
11. Security Master, candidate, simulation, real-account and order mutations are all zero.
12. `trade_authority = NONE`.
13. Exit status is `FMDL6X1D_FULL_BUILD_CONTRACT_AND_FMDL6X2_HANDOFF_ACCEPTED`.
14. Next gate is `FMDL-6X1-FINAL_OPERATIONAL_ACCEPTANCE`.
