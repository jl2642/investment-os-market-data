# HKCU P5C｜User Decision Gate

## Objective

P5C consumes the accepted P5B REAL Pre-trade Memo and prepares a reproducible user-decision packet. It does not infer or record the user's approval.

## Price gate

The three P5B-advanced securities must be priced from the official HKEX Main Board Daily Quotations sheet for 2026-08-07:

- HKEX:03698 HUISHANG BANK
- HKEX:01308 SITC
- HKEX:00669 TECHTRONIC IND

Third-party prices, ambiguous DD/MM dates and fabricated closes cannot satisfy this gate. The workflow downloads the HKEX quotation sheet in the runner and extracts only the required securities.

## Valuation context

P5C calculates decision-context valuation multiples without creating undocumented fixed ceilings:

- HUISHANG BANK: P/TBV proxy using the official HKEX close and a documented tangible-book reference; compare with own 10-year median and bank-industry context.
- SITC: trailing FY2025 P/E using official FY2025 EPS and the HKD7.80 linked-rate anchor; compare with documented own-history and 2026/cyclical-shipping context.
- TECHTRONIC IND: annualized 1H2026 run-rate P/E using official interim EPS and the HKD7.80 linked-rate anchor; compare with documented own-history and 2026 industrial quality-growth context.

These metrics are decision support, not forecasts or automatic buy thresholds.

## User authority

Eligible securities expose exactly four choices:

`APPROVE_AS_PROPOSED | MODIFY | DEFER | REJECT`

`MODIFY` requires the user to specify a weight. P5C initializes every user-decision field blank.

Softcare remains `DEFERRED_NOT_ELIGIBLE` until its P5B evidence trigger—published 1H2026 interim results and review—has been satisfied.

A P5C technical PASS means `READY_AWAITING_EXPLICIT_USER_DECISION`. It does not mean approval. Only after explicit user decisions can the business sequence proceed to `P5D_MANUAL_STAGED_EXECUTION_SUPPORT`.

## Governance

P5C:
- produces no manual execution checklist;
- writes no target portfolio;
- mutates no Candidate, SIMULATION or REAL Current state;
- creates no order;
- performs no broker execution;
- records no user trade confirmation;
- keeps `trade_authority=NONE`.
