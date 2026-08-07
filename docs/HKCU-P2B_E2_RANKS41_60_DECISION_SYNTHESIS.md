# HKCU P2B-E2 Ranks 41-60 Decision Synthesis

## Purpose

Apply the reusable P2B-E2 rank-window decision engine installed by S2 to accepted P2A ranks 41-60. This gate converts the existing company-evidence surface into security-level decision readiness without creating alpha scores, formal HK Candidate graduation, portfolio mutations or orders.

## Input boundary

After the accepted global D1 closure, ranks 41-60 contain:

- 20 securities;
- 60 company-specific decision dimensions;
- 45 `EVIDENCE_PARTIAL` rows;
- 15 non-Partial rows;
- 0 `RESEARCH_REQUIRED` rows.

The three dimensions remain Governance / Value Trap, Earnings Expectation Revision and Catalyst.

## Reusable decision discipline

S3 does not recreate a D1-D4 pipeline family. It reuses `pipeline/hkcu_p2b_e2_window_decision_synthesis.py`, which:

1. rebuilds and independently validates accepted D1;
2. applies the accepted D2 evidence-to-decision semantics to Partial rows;
3. treats missing consensus or current profit guidance as a confidence limit rather than a bearish conclusion;
4. treats ordinary governance process, connected transactions and unresolved positive optionality as monitor/confidence-cap states unless evidence shows a substantive investment risk;
5. allows fresh primary-official HKEX evidence to supersede stale first-pass direction;
6. deduplicates retained blockers by economic `event_id` across dimensions;
7. preserves P2A rank and prohibits alpha scoring or Candidate graduation.

## Fresh primary-official reconciliations

Four targeted rows are refreshed before security synthesis:

- **Wanguo Gold Group / earnings** — the 4 August 2026 Positive Profit Alert expects H1 attributable profit of about RMB880-920 million, up about 46.4%-53.1% year on year, superseding the older January evidence.
- **Wanguo Gold Group / catalyst** — the 27 July Gold Ridge Mine slope failure occurred on a non-operational bench; the issuer reported no injuries, property/equipment damage or interruption to mining/construction. Remediation remains a monitor, not a retained blocker on current evidence.
- **Tianqi Lithium / earnings** — the 14 July interim forecast is economically strongly positive despite the HKEX filing category: H1 attributable net profit is forecast at RMB2.85-4.25 billion versus about RMB84.41 million a year earlier, with higher lithium pricing/revenue and higher expected SQM contribution.
- **Newborn Town / earnings** — the 22 July H1 operating update expects total revenue of about USD595-615 million, up 34.3%-38.8% year on year, with social-networking and innovative-business revenue also growing strongly. Because the update does not provide H1 profit guidance, the earnings view remains confidence-capped rather than upgraded to a full profit conclusion.

## Expected decision hypothesis

The pre-run hypothesis is 20 advance / 0 retained blockers after the fresh reconciliations. This is not an acceptance shortcut: the real workflow and independent validator must confirm the result. If actual evidence semantics differ, the contract must be corrected to the evidence rather than altering evidence classifications to fit expected counts.

## Governance

- Alpha score: prohibited in P2B-E2.
- Formal HK Candidate graduation: prohibited.
- A-share Candidate mutation: 0.
- Simulation mutation: 0.
- Real Portfolio mutation: 0.
- Orders: 0.
- `trade_authority=NONE`.

A PASS advances only to `P2B_E2_RANKS61_77_DECISION_SYNTHESIS`.
