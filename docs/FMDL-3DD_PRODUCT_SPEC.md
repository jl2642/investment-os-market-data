# FMDL-3D-D — Shareholder-Return Event Current

## Purpose

Build an auditable A-share shareholder-return event ledger and one Current row per accepted Universe symbol. The layer distinguishes implemented cash dividends, completed effective share reductions, completed dilution events, neutral rescaling events and unclassified share changes.

It does not create an investment score, target price, portfolio action or trade permission.

## Entry gates

- FMDL-3D-A valuation and event contract accepted;
- FMDL-3D-B effective share and capitalization Current accepted;
- FMDL-3D-C valuation Current accepted.

## Data sources

### Cash dividends

`akshare.stock_fhps_em` / Eastmoney report-period dividend distribution data is queried for the four bounded annual and interim report periods needed to cover the current TTM window. Each deterministic shard filters the full-market response to its own symbols. This replaces thousands of per-symbol calls while preserving one source-attempt state per Universe symbol and one report-period call ledger per shard.

Only implemented cash distributions with a positive cash ratio enter dividend yield. A proposal announcement date is not an implementation date. Implementation requires an implemented progress state or a genuine registration/ex-dividend date.

### Buyback and dilution evidence

FMDL-3D-B effective-share ledger rows are converted into canonical completed share-change events. A share-count reduction enters buyback evidence only when the source change reason identifies repurchase or cancellation. A share-count increase enters dilution evidence only when the source reason identifies private placement, rights issue, convertible conversion or equity-incentive issuance. Unclassified changes do not enter shareholder yield.

## Current formulas

- dividend yield TTM = implemented cash dividend per share during the prior 365 days / accepted latest completed-session close;
- completed buyback yield TTM = sum of verified completed share reductions / prior total shares;
- completed issuance dilution yield TTM = sum of verified completed share increases / prior total shares;
- shareholder yield TTM = dividend yield + completed buyback yield - completed issuance dilution yield.

The buyback and dilution components are effective-share-count yields, not unverified announcement cash values. Implemented cash totals use the effective share count at each dividend event date rather than the current share count.

## Event-stage safety

- proposed or approved dividend is not implemented;
- announced buyback is not completed;
- approved issuance is not effective;
- future-effective events remain in evidence but cannot enter Current;
- stock dividend, split and capital-reserve conversion are neutral share rescaling events;
- missing components remain null and never receive zero fill.

## Outputs

- `FMDL3DD_EVENT_LEDGER.parquet`;
- `FMDL3DD_SHAREHOLDER_RETURN_CURRENT.parquet`;
- dividend symbol-attempt and report-period-attempt ledgers;
- coverage, event coverage and quarantine tables;
- decision, validation and manifest;
- immutable Release, Current, Archive and Last-success pointer.

## Exit gate

`FMDL3DD_SHAREHOLDER_RETURN_EVENT_CURRENT_ACCEPTED`

## Next gate

`FMDL-3D-FINAL_UNIFIED_ACCEPTANCE_AND_PUBLICATION`

Authority: `DATA_AND_RESEARCH_EVIDENCE_ONLY`

Trade authority: `NONE`
