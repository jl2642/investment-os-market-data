# FMDL-3D-A — Valuation, Capitalization & Shareholder-Return Architecture

## 1. Purpose

FMDL-3D-A freezes the machine contracts required to convert accepted prices, point-in-time financial denominators, effective share counts and corporate actions into auditable valuation and shareholder-return evidence.

This phase is an architecture and representative real-data pilot. It does not publish a full-market valuation Current and does not create a valuation score, target price, portfolio action or trade authority.

## 2. Entry gates

- `FMDL3CD_FINANCIAL_SCORE_AND_INVESTMENT_OS_INTERFACE_ACCEPTED`
- `FMDL3A_ACCEPTED_SOURCE_ROUTE_AND_COVERAGE_GATES_FROZEN`
- `FMDL3CB_FINANCIAL_FACTOR_ENGINE_MVP_ACCEPTED`

## 3. Data architecture

### 3.1 Capitalization snapshot

One row per issuer and market as-of date, preserving:

- accepted latest completed-session close;
- price source and timestamp;
- total shares and float A-shares;
- share-count effective date and source;
- total and float A-share market capitalization;
- explicit valid, warning, quarantine or blocked state;
- complete lineage.

`total_market_cap = close × PIT-effective total shares`

`float_A_market_cap = close × PIT-effective float A-shares`

A share-count record is eligible only when its effective date is not later than the price as-of date. An announced, approved or pending issuance is not effective share count.

### 3.2 Valuation metric detail

One row per issuer, metric and market as-of date. Every metric records:

- formula and required inputs;
- sector applicability;
- market numerator timestamp;
- financial denominator period and availability timestamp;
- input quality states and source fact IDs;
- denominator validity;
- decision-grade eligibility;
- warning and controlled failure reason.

Provider-supplied PE, PB or PS is cross-check evidence only. Decision-grade ratios are recomputed from accepted market capitalization and accepted point-in-time denominators.

### 3.3 Shareholder-return event

One row per canonical event and stage. The event model separates:

- event type;
- event stage;
- announcement date;
- implementation, completion or effective date;
- source document identity;
- cash and share-count impact;
- eligibility for share-count updates;
- eligibility for shareholder-yield calculation.

An announcement is evidence of intent, not evidence of completion.

## 4. Valuation metric registry

### Capitalization

- total market capitalization;
- float A-share market capitalization.

### Core valuation pilot

- PE TTM;
- earnings yield TTM;
- PB;
- PS TTM for general and pre-profit issuers;
- free-cash-flow yield TTM for general non-financial issuers;
- EV/Sales and EV/operating income only when debt and cash components are complete.

### Deferred to FMDL-3D-D

- implemented dividend yield TTM;
- verified shareholder yield TTM.

## 5. Sector and denominator rules

### General non-financial

PE, earnings yield, PB, PS, FCF yield and supported EV metrics may be calculated when inputs pass PIT and denominator gates.

### Banks, insurers and securities firms

PE and PB may be calculated when meaningful. PS, industrial FCF yield and industrial EV ratios are not applied.

### Pre-profit or negative-earnings issuers

Negative or zero earnings produces `NON_POSITIVE_EARNINGS`, not a negative PE and not a low-valuation signal. PB or PS may remain available when their own denominators are positive and applicable.

### Missing or invalid inputs

Missing values remain null. No zero, median, peer or neutral fill is permitted.

## 6. Shareholder-return event stages

The canonical model covers:

- cash dividends;
- buybacks;
- share cancellations;
- private placements;
- rights issues;
- convertible-bond conversion;
- equity-incentive issuance;
- stock dividends and splits.

Only implemented cash dividends enter dividend yield. Only completed buybacks enter buyback yield. Only completed issuances or conversions enter dilution. Partial component coverage cannot be labeled complete shareholder yield.

## 7. Pilot design

The deterministic 13-issuer pilot covers:

- Shanghai and Shenzhen Main Boards;
- ChiNext, STAR and BSE;
- general non-financial issuers;
- banks, insurance and securities firms;
- negative-earnings issuers;
- high-margin, capital-intensive, growth, energy and high-dividend archetypes.

Eleven issuers use accepted real capitalization evidence. Two BSE controls remain explicit quarantine rather than receiving fabricated values.

## 8. Outputs

- `FMDL3DA_CAPITALIZATION_PILOT.csv`
- `FMDL3DA_VALUATION_METRIC_DETAIL.parquet`
- `FMDL3DA_VALUATION_PILOT_CURRENT.parquet`
- `FMDL3DA_SHAREHOLDER_EVENT_CONTRACT_SAMPLES.csv`
- `FMDL3DA_PILOT_COVERAGE.csv`
- source support snapshot, decision, validation and manifest;
- immutable Release, Current, Archive and Last-success pointer after main acceptance.

## 9. Hard gates

- zero future financial denominator use;
- zero future-effective share-count use;
- zero non-positive earnings represented as valid PE;
- zero non-positive equity represented as valid PB;
- zero financial-sector PS or industrial EV metric forced as valid;
- zero announced buyback treated as completed;
- zero approved issuance treated as effective;
- zero provider ratio treated as decision-grade;
- zero missing-value fill;
- zero valuation score, target price, portfolio action or trade authority.

## 10. Exit and next gate

Exit:

`FMDL3DA_VALUATION_AND_SHAREHOLDER_RETURN_CONTRACT_ACCEPTED`

Next:

`FMDL-3D-B — Effective Share Count & Capitalization Engine`

Authority:

`DATA_AND_RESEARCH_EVIDENCE_ONLY`

`trade_authority = NONE`
