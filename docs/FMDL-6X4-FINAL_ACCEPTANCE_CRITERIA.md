# FMDL-6X4-FINAL Acceptance Criteria

FMDL-6X4-FINAL is accepted only when all conditions below pass.

1. All eight authoritative component pointers are present and bind the frozen Release IDs and statuses for FMDL-6X1-FINAL, FMDL-6X2-FINAL, FMDL-6X3-FINAL and FMDL-6X4-A through E.
2. Component Release sequences are exactly `29, 35, 41, 42, 43, 44, 45, 46` and strictly increase.
3. Every component pointer retains a valid Manifest SHA-256 and `trade_authority = NONE`.
4. Any component zero-mutation proof remains all zero.
5. Formal workflow execution, registered workflow output, Candidate Pool promotion, graduation event and investment-recommendation counts remain zero wherever those fields apply.
6. The authoritative roadmap confirms 6X4-FINAL as the FMDL-6 completion and freeze gate, followed only by FMDL-7.
7. Exactly eight component-acceptance records and eight operational-capability records are produced.
8. Exactly twelve freeze controls are active with no automatic waiver.
9. Exactly eight recovery controls are available and fail closed.
10. Exactly twelve FINAL gates pass.
11. Six domains × 64 buckets produce exactly 384 deterministic logical shards.
12. Independent same-input replay is byte-identical.
13. Current, immutable Release, normalized output, Last-success and Last Known Good pointers are published.
14. Candidate Pool, simulation book, real account and order mutations remain `0/0/0/0`.
15. No formal US simulation position, cross-market security rank, forced common factor score, neutral fill or investment recommendation is produced.
16. `trade_authority = NONE`.
17. The Decision status is `FMDL6X4_FINAL_US_RESEARCH_ADAPTER_OPERATIONAL_ACCEPTANCE_AND_FMDL6_FREEZE_ACCEPTED`.
18. The only next gate is `FMDL-7_CROSS_MARKET_AND_FULL_SYSTEM_FINAL_OPERATIONAL_ACCEPTANCE`.
