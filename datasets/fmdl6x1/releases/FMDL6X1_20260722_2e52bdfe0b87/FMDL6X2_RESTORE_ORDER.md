# FMDL-6X2 Clean-Room Restore Order

1. Read `outputs/status/FMDL6X1_LAST_SUCCESS.json`.
2. Verify status `FMDL6X1_FINAL_ACCEPTED` and next gate `FMDL-6X2-A_CURRENT_SECURITY_MASTER_PRODUCTION`.
3. Read `FMDL6X2_START_HERE.md`.
4. Restore `FMDL6X2_BUILD_CONTRACT.json`.
5. Restore `FMDL6X2_SOURCE_EXECUTION_REGISTRY.json`.
6. Restore `FMDL6X2_DOMAIN_SCHEMA_REGISTRY.json`.
7. Restore `FMDL6X2_SHARD_PLAN.json`.
8. Restore `FMDL6X2_QUALITY_GATE_REGISTRY.json`.
9. Restore the latest domain Last-known-good pointers when they exist.
10. Verify immutable Release manifests before promoting any Current output.

A failed, partial or hash-mismatched run must not replace Current or Last-known-good.
