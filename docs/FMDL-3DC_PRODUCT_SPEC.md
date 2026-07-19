# FMDL-3D-C — Valuation Engine Current

## 1. Objective

Convert the accepted FMDL-3D-B point-in-time capitalization Current and the accepted FMDL-3C-B financial denominator layer into a full-Universe, timestamp-aligned valuation Current.

This phase produces transparent valuation evidence only. It does not produce a composite valuation score, target price, candidate-pool mutation, portfolio action or trade authority.

## 2. Entry gates

- `FMDL3DA_VALUATION_AND_SHAREHOLDER_RETURN_CONTRACT_ACCEPTED`
- `FMDL3DB_EFFECTIVE_SHARE_COUNT_AND_CAPITALIZATION_ENGINE_ACCEPTED`
- `FMDL3CB_FINANCIAL_FACTOR_ENGINE_MVP_ACCEPTED`

## 3. Production metrics

Seven valuation metrics are implemented from the frozen FMDL-3D-A registry:

1. `VAL_PE_TTM`
2. `VAL_EARNINGS_YIELD_TTM`
3. `VAL_PB`
4. `VAL_PS_TTM`
5. `VAL_FCF_YIELD_TTM`
6. `VAL_EV_SALES_TTM`
7. `VAL_EV_OPERATING_INCOME_TTM`

Dividend yield and shareholder yield remain FMDL-3D-D work.

## 4. Point-in-time alignment

For market date `T`:

- the numerator is accepted FMDL-3D-B total market capitalization based on the completed-session close at `T`;
- each financial input must have `available_from` not later than the market close cutoff at `T`;
- the engine selects the latest qualifying denominator period separately for each metric;
- later financial information remains unavailable to the earlier valuation snapshot;
- future denominators are blocked rather than backfilled.

## 5. Denominator policy

- PE and earnings yield require positive parent net income TTM;
- PB requires positive parent book equity;
- PS requires positive revenue TTM;
- FCF yield permits negative free cash flow as valid negative evidence;
- EV metrics require complete short-term debt, long-term debt, bonds payable and cash-equivalent inputs;
- EV/Sales requires positive enterprise value and revenue;
- EV/operating income requires positive enterprise value and operating income;
- missing debt or cash components are never treated as zero.

## 6. Sector applicability

- PE, earnings yield and PB are supported for general non-financial, bank, insurance and securities profiles when denominator rules pass;
- PS is limited to the general non-financial profile;
- FCF yield and both EV metrics are limited to the general non-financial profile;
- unresolved profiles fail closed;
- an ordinary-company metric is never silently forced onto a financial institution.

## 7. Outputs

Candidate and published Current contain:

- one valuation Current row for every accepted A-share Universe symbol;
- one detail row per symbol and production valuation metric;
- metric formula, input values, input states, availability timestamps and fact IDs;
- capitalization and financial-denominator lineage;
- sector and denominator validity states;
- coverage and denominator-validity maps;
- explicit capitalization quarantine;
- independent formula replay and schema validation.

## 8. Hard gates

- exact Universe × seven-metric detail matrix;
- zero future selected denominator;
- zero invalid denominator published as a valid value;
- zero non-positive earnings represented as valid PE;
- zero non-positive equity represented as valid PB;
- zero incomplete EV metric represented as valid;
- zero ordinary-company metric forced onto a financial profile;
- exact formula replay within frozen tolerance;
- Current and detail reconciliation;
- no score, target price, portfolio action or trade authority;
- independent validation PASS.

## 9. Publication

The phase uses Candidate → immutable Release → Current → Archive → Last-success publication. A failed candidate cannot replace the accepted Current.

Required exit:

`FMDL3DC_VALUATION_ENGINE_CURRENT_ACCEPTED`

Next gate:

`FMDL-3D-D_SHAREHOLDER_RETURN_EVENT_CURRENT`
