# HKCU P5C｜User Decision Gate

## Objective

P5C consumes the accepted P5B REAL Pre-trade Memo and prepares a reproducible user-decision packet. It does not infer or record the user's approval.

## Official market surfaces

The three P5B-advanced securities must be priced from the official HKEX Main Board Daily Quotations sheet for 2026-08-07:

- HKEX:03698 HUISHANG BANK
- HKEX:01308 SITC
- HKEX:00669 TECHTRONIC IND

Third-party prices, ambiguous DD/MM dates and fabricated closes cannot satisfy this gate. The workflow downloads the HKEX quotation sheet in the runner and extracts only the required securities.

### Same-date official FX repair

The initial P5C implementation attempted to use HKMA `er-eeri-daily` for 2026-08-07. That governed query returned `success=true` with `err_code=1001` / `No result found`. DATA.GOV.HK classifies that Monthly Statistical Bulletin dataset with a monthly update frequency, so it cannot reliably satisfy a contemporaneous user-decision gate even though the underlying series contains daily observations.

P5C-R therefore replaces that implementation surface with the **European Central Bank official euro foreign exchange reference-rate time series**, which is published each working day. The gate requires the exact same date, 2026-08-07, and retrieves EUR reference rates for HKD, USD and CNY. It derives:

- `HKD per USD = ECB HKD-per-EUR / ECB USD-per-EUR`
- `HKD per CNY = ECB HKD-per-EUR / ECB CNY-per-EUR`

No stale date is accepted and no third-party FX fallback is permitted. ECB reference rates are used **only to normalize valuation denominators**; they are not transaction rates and do not authorize or price an FX execution.

## Valuation context

P5C calculates decision-context valuation multiples without creating undocumented fixed ceilings:

- **HUISHANG BANK:** current P/B common-equity proxy. Primary denominator is derived from the official 2026Q1 disclosure: RMB178,017m total owners' equity less RMB20,000m non-fixed-term capital bonds less RMB2,760m valid minority interests, divided by RMB13,890m paid-up capital. That equals about RMB11.1776 per share before conversion with the same-date official ECB-derived HKD/CNY reference rate. This is an unaudited common-equity proxy, not a substitute for audited book value. Third-party P/TBV history is comparison context only.
- **SITC:** trailing FY2025 P/E using official FY2025 basic EPS US$0.46 and the same-date official ECB-derived HKD/USD reference rate; compare with documented own-history and 2026/cyclical-shipping context.
- **TECHTRONIC IND:** annualized 1H2026 run-rate P/E using official interim EPS US$0.405 mechanically annualized to US$0.81 and the same-date official ECB-derived HKD/USD reference rate; compare with documented own-history and 2026 industrial quality-growth context.

These metrics are decision support, not forecasts, execution prices or automatic buy thresholds.

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
