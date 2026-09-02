# 股票投资助手｜Final Product Capability Matrix

- Plan: `FINAL_PRODUCT_CLOSURE_20260902_V1`
- Phase: `PHASE_4_END_TO_END_PRODUCT_ACCEPTANCE_AND_FREEZE`
- Frozen product scope: A-share full-market discovery/screening; current Real/Simulation portfolio marks and lifecycle monitoring; existing bounded cross-market support; ChatGPT-native semantic D2; human final decision/execution.
- Explicit non-goals: broker order integration, automatic real-account trading, automatic economic-state mutation, global all-market full-universe coverage.
- trade_authority: `NONE`

| # | Core capability | Final acceptance definition | Status |
|---|---|---|---|
| 1 | Market data refresh & freshness | A-share full-market session data refreshes; current portfolio marks refresh independently; stale/failure truth is fail-closed | PASS |
| 2 | Opportunity discovery & multi-layer screening | Full-market factors/screening feed an opportunity queue; D1 rolls through ranked opportunities without Candidate membership as a hard research gate | PASS |
| 3 | D1 fast triage | Rolling D1 batch routes bounded highest-priority names into D2 research readiness | PASS |
| 4 | D2 deep underwriting | Decision-grade Bear/Base/Bull, probability, normalized earnings, entry price, confidence, catalysts and kill-thesis are required before investment decisions | PASS |
| 5 | Thesis & recommendation register | Persistent current thesis/recommendation supports BUY, BUY_BELOW, WATCH_FOR_EVIDENCE, WATCH, AVOID, ADD, HOLD, TRIM and EXIT | PASS |
| 6 | Continuous trigger monitoring | Price, valuation, drawdown, financial-context and structured material-event changes can reopen fresh D2; semantic clauses are monitored without unsafe keyword auto-fire | PASS |
| 7 | Position lifecycle & portfolio construction | All current Real/Simulation holdings are in lifecycle monitoring; current weights convert to target weights subject to portfolio constraints | PASS |
| 8 | Execution validation | Listed-security actions are converted to legal quantities/lots and blocked or reduced by cash/single-name/risk-group constraints; no broker order is created | PASS |
| 9 | Portfolio monitoring & risk | Real/Simulation holdings have marks, NAV/performance monitoring, concentration/drawdown review and explicit user-decision surfaces | PASS |
| 10 | Performance attribution & learning | Real/Simulation monitoring plus isolated AI_AUTONOMOUS_1M ledger provide NAV/return/drawdown/turnover/position attribution and future review evidence | PASS |

## Current portfolio coverage

Phase 1 acceptance established **22/22 unique current holdings** with current recommendation coverage and zero uncovered holdings. Phase 2 lifecycle materialized those 22 held subjects into continuous position monitoring. Real and legacy Simulation remain read-only economic authorities; user-reported executed trades/private cash flows remain the input boundary.

## Action semantics

- New opportunity: `BUY`, `BUY_BELOW`, `WATCH_FOR_EVIDENCE`, `WATCH`, `AVOID`.
- Existing holding: `ADD`, `HOLD`, `TRIM`, `EXIT`.
- Execution layer may render actionable listed-security sides/quantities such as BUY/SELL after validation.
- `EXIT` means a full-exit recommendation and can validate to the full legal sell quantity.
- No recommendation automatically changes the Real account or creates a broker order.

## Operating responsibility

GitHub owns deterministic public-data refresh, mechanical state, routing, lifecycle triggers, portfolio calculations and failure receipts. ChatGPT owns semantic D2 underwriting, daily control synthesis and user-facing investment judgment. Decision-grade semantic D2 is condition/evidence gated and is not silently substituted by mechanical automation. The user remains the final authority for real transactions.

## Completion meaning

A PASS here means the frozen ten-capability investment lifecycle is complete and operational inside the stated scope. It does **not** mean every global market/security is covered or that real-money trading is automated.
