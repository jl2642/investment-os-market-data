# FMDL-6X3-B Acceptance Criteria

The stage is accepted only when:

1. The FMDL-6X3-A Release 36 entry pointer and upstream Manifest hashes match.
2. Every opened Security has a supported research profile and official SEC facts.
3. Every source fact maps to a canonical metric and preserves source lineage.
4. Reported and derived statement rows remain distinguishable.
5. Gross profit, operating income, operating-expense components and net-income equations pass for every opened issuer.
6. TTM and annual rows are not emitted unless their period requirements are met.
7. Missing balance-sheet, cash-flow, TTM and annual inputs remain explicit issues.
8. All 256 logical shards are present and deterministic.
9. Independent same-input replay is byte-identical.
10. Current and immutable Release Decision/Manifest files are identical after publication.
11. Candidate Pool, simulation, real-account and order mutations remain zero with `trade_authority = NONE`.

Required exit:

`FMDL6X3B_FINANCIAL_NORMALIZATION_TTM_AND_ANNUAL_METRIC_LAYER_ACCEPTED`

Next gate:

`FMDL-6X3-C_FACTOR_VALUATION_QUALITY_AND_RISK_ENGINE`
