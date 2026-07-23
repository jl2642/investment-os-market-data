# FMDL-7-0 Acceptance Criteria

FMDL-7-0 is accepted only when every criterion below passes in both pull-request validation and the main-branch publication run.

## Contract and asset gates

1. The contract phase is exactly `FMDL-7-0`.
2. Exactly seven authoritative assets are registered.
3. Every registered asset exists and parses as JSON.
4. Every frozen identity, Release, status and authority check matches.
5. Every bound asset preserves `trade_authority = NONE`.
6. The Investment OS Release 8 package identity and SHA are registered without claiming that later overlays are already repacked.

## Program-shape gates

7. The exact stage order is `7-0 → 7A → 7B → 7C → 7D → 7E → 7-FINAL`.
8. There are exactly seven formal stages.
9. There are at most two targeted repair rounds.
10. The hard total-round maximum is nine.
11. FMDL-7F, FMDL-7G, FMDL-7X1, FMDL-7X2 and unbounded subphase creation are prohibited.
12. The only next gate is `FMDL-7A_CROSS_MARKET_CANONICAL_INVENTORY_AND_STATE_RECONCILIATION`.

## Authority and Canonical gates

13. GitHub, File Library, Release 8 and conversation-memory roles are explicitly separated.
14. Conversation memory is non-authoritative.
15. The single-package Canonical refresh is deferred to FMDL-7E.
16. Premature repacking is prohibited.
17. The target File Library posture is one current Canonical ZIP, one matching Pointer and one START_HERE after verification.

## Mutation and execution gates

18. New market-data refresh is not authorized.
19. Research workflow execution is not authorized.
20. Candidate Pool mutation is zero and unauthorized.
21. Simulation-book mutation is zero and unauthorized.
22. Real-account mutation is zero and unauthorized.
23. Rule mutation is zero and unauthorized.
24. Orders are zero and unauthorized.
25. `trade_authority = NONE`.

## Determinism, publication and recovery gates

26. Contract and regression tests pass.
27. Producer and tests compile.
28. The same inputs produce byte-identical candidate outputs.
29. Every candidate output is hash- and size-bound in the Manifest.
30. Publication occurs only on accepted main execution.
31. Current, immutable Release and normalized outputs are published.
32. `FMDL7_0_LAST_SUCCESS.json` and `FMDL7_MASTER_PLAN_LKG.json` are published.
33. Immutable Release collision is rejected unless the existing Release is byte-identical.

## Expected result

- authoritative assets: 7 / 7 PASS;
- formal stages: 7;
- targeted repair budget: 2;
- hard total-round cap: 9;
- acceptance gates: 12 / 12 PASS;
- logical shards: 4 domains × 64 buckets = 256;
- candidate, simulation, real-account, rule and order mutations: `0 / 0 / 0 / 0 / 0`;
- `trade_authority = NONE`.

Required exit:

`FMDL7_0_MASTER_PLAN_AUTHORITATIVE_ASSET_REGISTRY_AND_ACCEPTANCE_CONTRACT_ACCEPTED`
