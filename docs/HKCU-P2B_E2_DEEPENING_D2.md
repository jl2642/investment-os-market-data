# HKCU P2B-E2 Deepening D2 — Top-20 Partial Evidence Synthesis

## Purpose

D1 removed the final 23 unresearched company-specific gaps. The remaining 186 open rows all contain primary evidence but remain `EVIDENCE_PARTIAL`.

D2 begins with accepted P2A ranks 1–20 because research priority must follow the accepted Longlist rather than an arbitrary new shortlist. In the accepted D1 state, ranks 1–20 contain exactly **51 Partial rows**:

- Governance / Value-Trap: **20**
- Earnings-Expectation Revision: **17**
- Catalyst: **14**

D2 does not force these rows to `EVIDENCE_COMPLETE`. It converts them into a decision-oriented synthesis surface so subsequent research can target the blockers that actually matter.

## Synthesis fields

Each Partial row receives:

- `evidence_sufficiency`
- `finding_direction`
- `materiality`
- `finding`
- `graduation_blocker`
- `counterevidence_needed`
- `monitor_trigger`

No alpha score is produced.

## Governance rules

Auditor changes and connected/related-party transactions require targeted deepening because the first-pass event establishes the existence of a governance issue but not its fairness, independence or economic materiality.

Senior CEO/CFO/chairman transitions also require targeted follow-up. Ordinary board/committee turnover is monitored but is not automatically a Candidate-graduation blocker.

## Earnings-revision rules

Ordinary annual, quarterly and operating results never masquerade as sell-side consensus revisions. All 17 Partial earnings rows therefore retain `UNKNOWN` direction.

A current-period operating update may be sufficient for preliminary monitoring with a confidence cap. Stale/annual-only evidence requires targeted deepening for current-period evidence or a reliable dated consensus-revision series.

Missing consensus data is a confidence limitation, not an automatically bearish signal.

## Catalyst rules

Material pending spin-offs, listings, acquisitions, disposals or other strategic transactions require targeted deepening because structure, conditions and economics can change the investment conclusion.

Explicit positive/negative profit alerts may supply directional catalyst evidence. Recurring operational updates, routine result-cycle notices and small capital-return signals are monitored at lower materiality.

## Security-level readiness

The 51 dimension syntheses aggregate into a 20-security readiness surface:

- `TARGETED_DEEPENING_REQUIRED` when any graduation blocker remains;
- `READY_WITH_CONFIDENCE_CAP` when no blocker remains but evidence is still limited;
- `READY_FOR_P2B_SYNTHESIS` only when no blocker or confidence limitation remains.

This is **P2B evidence readiness**, not formal Hong Kong Candidate graduation.

## Outputs

- `HKCU_P2B_E2_D2_TOP20_PARTIAL_SYNTHESIS.csv`
- `HKCU_P2B_E2_D2_TOP20_SECURITY_READINESS.csv`
- `HKCU_P2B_E2_D2_TOP20_BLOCKER_QUEUE.csv`
- `HKCU_P2B_E2_D2_DECISION.json`
- `HKCU_P2B_E2_D2_QUALITY_REPORT.json`
- `HKCU_P2B_E2_D2_MANIFEST.json`

PASS advances to `P2B_E2_TARGETED_TOP20_BLOCKER_DEEPENING`.

## Protected state

D2 changes no formal Hong Kong Candidate membership, A-share Candidate state, Simulation, Real Portfolio, orders or trade authority.

`trade_authority=NONE`.
