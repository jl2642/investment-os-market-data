# HKCU P2B-E2 Ranks 61-77 Decision Synthesis

## Objective

Complete the final P2B-E2 rank window by converting accepted company-specific evidence for P2A ranks 61-77 into an auditable security-level decision-readiness surface. This gate reuses the parameterized rank-window engine installed in S2; it does not create another D1-D4 pipeline family.

## Authoritative upstream

- Canonical `main` after S3.
- Global D1 company-evidence ledger with all 77 securities started and no `RESEARCH_REQUIRED` company-specific dimensions.
- Reusable engine: `pipeline/hkcu_p2b_e2_window_decision_synthesis.py`.
- Accepted D2 evidence-to-decision semantics.
- S4 targeted HKEX-primary overrides for decision-critical stale or ambiguous signals.

## Deterministic scope

Ranks 61-77 contain 17 securities and 51 company-specific dimensions:

- `GOVERNANCE_VALUE_TRAP`
- `EARNINGS_EXPECTATION_REVISION`
- `CATALYST`

After D1 closure the expected upstream mix is 43 `EVIDENCE_PARTIAL` rows and 8 non-Partial rows, with zero `RESEARCH_REQUIRED` rows.

## Decision semantics

The gate preserves these rules:

1. Evidence completeness is not investment merit.
2. Missing consensus or explicit profit guidance is an information-confidence limit, not automatically bearish.
3. Ordinary connected transactions, leadership changes and positive optionality are not automatic blockers.
4. Fresh primary-official HKEX evidence can replace stale first-pass direction.
5. Economic content overrides misleading document-category labels.
6. One economic event must not be penalized multiple times across dimensions; `event_id` lineage is retained for deduplication.
7. No alpha score is assigned in P2B-E2.
8. No formal Candidate graduation, portfolio mutation or order is allowed.

## Targeted reconciliations

### MMG — stale impairment warning versus current 2026 operating outlook

The January profit warning reflected a non-cash impairment associated with the prior reporting period. The 21 July Q2 production report is the more relevant current-period evidence: all five mines remained on track for full-year production guidance and C1 cost guidance for Las Bambas, Khoemacau and Rosebery was revised downward. This supports a positive current operating direction but remains confidence-capped until financial results or a reliable earnings-revision series are available.

### Pharmaron — HKEX category label versus economic content

The 13 July H1 2026 estimate is economically positive despite the HKEX category including `Profit Warning`. The issuer estimated revenue growth of 16%-19%, attributable net profit growth of 4%-10%, attributable net profit excluding non-recurring items growth of 6%-11%, and non-IFRS adjusted attributable net profit growth of 17%-22%. Both the earnings and catalyst dimensions share one positive event lineage.

### Shenzhou International — current direct negative earnings blocker

The 7 August H1 2026 profit warning expects attributable profit to fall approximately 38%-43% year on year. The issuer identifies RMB appreciation, rising labour and raw-material costs, production ramp-up inefficiency, weak demand, tariff effects and foreign-exchange losses. The earnings dimension retains the blocker. The catalyst dimension references the same event but does not create a second blocker event.

### Topsports — material Nike online-channel termination

The 22 July inside-information announcement states that Nike online sales in mainland China will terminate completely from 1 January 2027. The board expects significant short-term negative impact and disclosed that those sales represented approximately 22% of FY2025/26 revenue. This remains a current investment blocker until channel migration and earnings impact are quantified.

## Acceptance hypothesis

The pre-run governed expectation is:

- 17 securities / 51 decision-dimension rows;
- 15 securities advance to P2B final cross-sectional synthesis with confidence caps;
- 2 securities remain held on substantive blockers: Shenzhou International (`02313`) and Topsports (`06110`);
- 2 retained blocker events after event-lineage deduplication;
- 0 alpha scores;
- 0 formal Candidate graduations;
- 0 Candidate, Simulation, Real Portfolio or order mutations;
- `trade_authority=NONE`.

These counts are acceptance hypotheses, not targets to be forced. If the real workflow or independent validator exposes different audited facts, the contract must be corrected to those facts rather than changing evidence merely to pass.

## Next gate

A PASS advances to `P2B_FINAL_CROSS_SECTIONAL_SYNTHESIS`. No rank-window deepening gate remains after S4.
