# Phase 0B Rule Inventory Summary

The working audit maps **62 semantic rules** across all Core Static modules 00–10. The full row-level CSV/JSON is kept in the Phase 0B/1B audit artifact; this repository PR intentionally persists the decision-relevant summary rather than changing any effective Core files.

Primary categories represented: Constitution, Strategy, Research, Portfolio, Execution, Governance and Data.

Highest-priority v2 migration candidates are the economic rules distributed across 00/03/04/06: underwriting scope, competence, valuation scenarios, thesis/falsifier state, Candidate promotion semantics, opportunity cost, portfolio fit and sizing diagnostics. Highest-priority rules to preserve unchanged are authority/state/PIT/writeback/execution/publication controls in 01/02/07/09/10.

Phase 3 hypotheses: binary completeness may create false negatives; Candidate attention state may differ from capital-comparability state; explicit expected-return/downside/opportunity-cost decomposition may improve NO_ACTION attribution; path-specific rules may contain redundant gates. None is treated as proven in Phase 0B.
