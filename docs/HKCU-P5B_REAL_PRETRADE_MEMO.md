# HKCU P5B｜REAL Pre-trade Memo

## Purpose

P5B converts the P5A-frozen REAL 5% / four-security research proposal into a true pre-trade decision memo. It re-underwrites evidence maturity, thesis, valuation gate, portfolio fit, funding, historical downside contribution, alternatives, falsifiers, triggers and review conditions. It may advance, modify, defer or reject securities; it cannot approve execution.

## Evidence discipline

Company fundamental updates are pinned to official HKEX disclosures dated no later than 2026-08-07. SITC's 2025 profit/EPS metrics are separately pinned to its official 2025 annual-results disclosure in addition to the 2026 Q1 operating disclosure.

Exact 2026-08-07 closing prices are not fabricated when a governed exact-close surface is not independently available in the transaction. Any security that remains eligible for user review therefore carries a mandatory live executable-price / valuation recheck at P5C.

P5B does **not** invent a fixed P/E or P/B ceiling. P5C valuation review must use a live executable price, the latest official earnings/equity evidence, documented company historical valuation and relevant peer context. A plausible-looking multiple is not treated as a governance threshold unless evidence or a frozen rule explicitly authorizes it.

## Security policy

- HKEX:03698 HUISHANG BANK — `ADVANCE_WITH_PRICE_GATE`; Q1 financial/capital evidence remains adequate, but fresh P/B, asset-quality and documented historical/peer valuation checks are mandatory.
- HKEX:01308 SITC — `ADVANCE_WITH_PRICE_GATE`; official 2025 results plus Q1 operating evidence support a small portfolio role while lower freight rate keeps cyclicality explicit; fresh live-price valuation and interim-data checks are mandatory.
- HKEX:00669 TECHTRONIC IND — `ADVANCE_WITH_PRICE_GATE`; formal 2026 interim results materially strengthen earnings, margin, FCF and balance-sheet evidence; live-price valuation against documented history/peers remains mandatory.
- HKEX:02698 SOFTCARE — `DEFER_SECURITY`; the 2026 half-year profit alert is positive but preliminary and explicitly not audited/reviewed. Its frozen weight is not automatically redistributed before formal interim results are reviewed.

## Acceptance target

The bounded P5B outcome is `3 ADVANCE_WITH_PRICE_GATE + 1 DEFER_SECURITY`, with the advanced names retaining their P5A weights and Softcare's 0.6645% weight set to zero rather than redistributed. This reduces the candidate REAL sleeve from 5% to approximately 4.3355% before P5C.

The first technical P5B run is not sufficient by itself: business acceptance additionally requires complete evidence lineage and prohibits undocumented fixed valuation multiples. The final merged head must independently rerun the full Canonical chain and reproduce the same security routing and weights under those stricter rules.

## Authority boundary

A P5B PASS means a complete memo exists and the surviving proposal may be shown at P5C under `USER_DECISION_REQUIRED`. It does not mean the user approved it. P5B creates no manual execution checklist, no target writeback, no Candidate/REAL/SIMULATION mutation, no order, and no broker execution. `trade_authority=NONE`.
