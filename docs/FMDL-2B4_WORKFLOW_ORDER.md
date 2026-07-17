# FMDL-2B-4 Workflow Order

1. FMDL-1 Current is produced and validated.
2. `validate_fmdl2b4_freshness` verifies the latest completed market session.
3. `run_incremental_history_refresh` builds the staged composite-history candidate.
4. `finalize_b4_history_candidate` reconciles component row hashes and manifest hashes.
5. `run_b4_factor_refresh` calculates the staged factor candidate.
6. `validate_fmdl2b4_candidate` independently reopens and validates both candidates.
7. `publish_fmdl2b4` atomically replaces both Current directories.
8. `run_fmdl2b4_operating` records LAST_RUN and LAST_SUCCESS.

The order is mandatory. Publication before independent validation is prohibited.
