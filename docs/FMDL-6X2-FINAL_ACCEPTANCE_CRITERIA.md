# FMDL-6X2-FINAL Acceptance Criteria

1. Bind the accepted FMDL-6X2-A through FMDL-6X2-E Releases 30–34.
2. Verify every Current Manifest and Decision is byte-identical to its immutable Release counterpart.
3. Verify every pointer Manifest SHA-256 and every domain Quality Report.
4. Reconcile 8,807 Listings, 8,785 Securities and 7,419 Issuers across all five stores.
5. Preserve listing-history, market-history and SEC coverage limitations without escalation or neutral fill.
6. Preserve Yahoo market history as `NON_DECISION_GRADE_FALLBACK`.
7. Publish a machine-readable Domain Registry, Cross-domain Reconciliation, Coverage Boundary and Operational Gate record.
8. Freeze an explicit FMDL-6X3 and FMDL-6X4 handoff without mutating the Investment OS Candidate Pool.
9. Require captured-input byte replay, Manifest validation, Current/Release parity and LKG protection.
10. Publish Current, immutable Release, normalized, Last-success and Full Store LKG atomically.
11. Candidate Pool, simulation, real account and order mutations remain zero.
12. `trade_authority` remains `NONE`.
