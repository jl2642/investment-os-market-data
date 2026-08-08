# HKCU P5B｜REAL Pre-trade Memo

## Purpose

P5B converts the P5A-frozen REAL 5% / four-security research proposal into a true pre-trade decision memo. It re-underwrites evidence maturity, thesis, valuation gate, portfolio fit, funding, historical downside contribution, alternatives, falsifiers, triggers and review conditions. It may advance, modify, defer or reject securities; it cannot approve execution.

## Evidence discipline

Company fundamental updates are pinned to official HKEX disclosures dated no later than 2026-08-07. Exact 2026-08-07 closing prices are not fabricated when a governed exact-close surface is not independently available in the transaction. Any security that remains eligible for user review therefore carries a mandatory live executable-price / valuation recheck at P5C.

## Security policy entering validation

- HKEX:03698 HUISHANG BANK — `ADVANCE_WITH_PRICE_GATE`; Q1 financial/capital evidence remains adequate, but fresh P/B and asset-quality checks are mandatory.
- HKEX:01308 SITC — `ADVANCE_WITH_PRICE_GATE`; volume growth supports the thesis while lower freight rate keeps cyclicality explicit; fresh trailing P/E and interim-data checks are mandatory.
- HKEX:00669 TECHTRONIC IND — `ADVANCE_WITH_PRICE_GATE`; 2026 interim results materially strengthen earnings, margin, FCF and balance-sheet evidence; live valuation remains mandatory.
- HKEX:02698 SOFTCARE — `DEFER_SECURITY`; the 2026 half-year profit alert is positive but preliminary and explicitly not audited/reviewed. Its frozen weight is not automatically redistributed before formal interim results are reviewed.

## Authority boundary

A P5B PASS means a complete memo exists and the surviving proposal may be shown at P5C under `USER_DECISION_REQUIRED`. It does not mean the user approved it. P5B creates no manual execution checklist, no target writeback, no Candidate/REAL/SIMULATION mutation, no order, and no broker execution. `trade_authority=NONE`.
