# HKCU P2B-E2 — Company-Specific Evidence

## Purpose

P2B-E2 collects company-specific evidence for the three dimensions left open after P2B-E1:

1. `GOVERNANCE_VALUE_TRAP`
2. `EARNINGS_EXPECTATION_REVISION`
3. `CATALYST`

It is an evidence-collection step, not a stock-rating or Candidate-graduation step. No alpha score is assigned in E2.

## Deterministic first batch

The accepted P2A Longlist contains 77 securities. The first E2 batch is the top quartile by accepted P2A overall rank:

- selection fraction: 25%
- `ceil(77 × 25%) = 20`
- accepted ranks: 1–20
- three dimensions per security
- 60 company-specific evidence rows

The batch is therefore a deterministic research-priority tranche, not a discretionary top-20 stock pick.

## Evidence semantics

`EVIDENCE_COMPLETE` means the evidence-collection requirement for that dimension can move to later P2B synthesis. It does not mean the security is attractive and does not create an alpha score.

`EVIDENCE_PARTIAL` means at least one authoritative company-specific source has been captured but the dimension remains open.

`RESEARCH_REQUIRED` means the reviewed official material does not yet establish enough evidence.

`DATA_UNAVAILABLE` preserves an explicit gap rather than inventing a proxy.

For earnings-expectation revision, ordinary results or trading updates may provide current operating evidence but do not substitute for consensus revisions. An explicit issuer profit warning or profit-increase announcement is treated as direct management expectation-change evidence, still without an alpha score.

For catalysts, evidence must be dated, security-specific and falsifiable. Routine historical events are not automatically promoted to a live catalyst.

For governance/value-trap work, annual reports, AGM results, auditor/director changes and connected transactions establish evidence leads, but the security-type-aware risk conclusion remains a later synthesis task.

## First-batch contract

The top-quartile registry expands to 60 dimension rows:

- 3 `EVIDENCE_COMPLETE`
- 51 `EVIDENCE_PARTIAL`
- 6 `RESEARCH_REQUIRED`

Thus 54 dimension rows have at least one primary official evidence item captured, while only three management expectation-change rows are sufficiently direct to be closed for evidence collection. Partial rows remain open.

The real workflow deterministically rebuilds P2B-E1 first, verifies every E2 row remains in the 231-row E1 company-specific queue, overlays the evidence, keeps every alpha score null, and emits:

- `HKCU_P2B_E2_EVIDENCE_LEDGER.csv`
- `HKCU_P2B_E2_DIMENSION_MATRIX.csv`
- `HKCU_P2B_E2_OPEN_RESEARCH_QUEUE.csv`
- `HKCU_P2B_E2_UNSTARTED_QUEUE.csv`
- `HKCU_P2B_E2_DECISION.json`
- `HKCU_P2B_E2_QUALITY_REPORT.json`
- `HKCU_P2B_E2_MANIFEST.json`

After this first batch, P2B-E2 is **not complete**. The next gate remains `P2B_E2_CONTINUE_COMPANY_SPECIFIC_EVIDENCE` until all 77 securities have adequate company-level evidence for synthesis.

## Governance

P2B-E2 does not change the A-share Candidate Pool, create or graduate the formal HK Candidate Pool, change Simulation or Real Portfolio holdings, create orders, or grant trade authority.

`trade_authority=NONE`.
