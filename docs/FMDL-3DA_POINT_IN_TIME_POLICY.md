# FMDL-3D-A — Valuation Point-in-Time Policy

## 1. Objective

A valuation observation is valid only when the price, effective share count and every financial denominator could all have been known at the valuation as-of time.

## 2. Market numerator

The market numerator uses the accepted FMDL-1 latest completed-session close. The row must retain:

- price as-of date;
- source timestamp;
- price source identity;
- row hash or equivalent lineage.

Intraday valuation is not authorized in FMDL-3D-A.

## 3. Effective share count

For a price as-of date `T`, the eligible share-count version is the latest positive record whose effective date is no later than `T`.

The following do not change effective share count until completion or implementation evidence exists:

- announced or approved private placement;
- announced or approved rights issue;
- unconverted convertible bond balance;
- announced buyback;
- repurchased shares not yet cancelled when total issued shares remain unchanged;
- proposed stock dividend or split.

Historical market capitalization may never use current share count unless that share-count version was already effective at the historical date.

## 4. Financial denominator

For each valuation metric, the engine selects the latest accepted denominator row for which:

1. all required input states are `VALID` or `VALID_WITH_WARNING`;
2. all required values are present;
3. each input `available_from` is not later than the market cutoff timestamp;
4. the accepted revision version is effective at that timestamp;
5. comparability restrictions are preserved.

A later correction or restatement creates a later valuation version. It does not rewrite the valuation visible before the correction became available.

## 5. Denominator validity

- PE and earnings yield require positive parent net income TTM;
- PB requires positive parent equity;
- PS requires positive revenue and an applicable sector profile;
- FCF yield permits negative FCF as valid negative evidence when all inputs are valid;
- EV metrics require complete debt and cash components and positive enterprise value;
- financial-sector issuers do not receive ordinary-company PS, FCF or industrial EV metrics unless a later specialized contract explicitly authorizes them.

An invalid denominator produces a null metric and an explicit state. It never produces an artificial ratio.

## 6. Corporate actions and shareholder return

Announcement time and economic completion time are distinct.

- cash dividend yield uses implemented dividends only;
- buyback yield uses completed cash repurchases only;
- share-count reduction uses effective cancellation evidence;
- dilution uses completed issuance or conversion only;
- shareholder yield requires complete verified component coverage or is labeled partial.

## 7. Source role

- FMDL-1 accepted close: market numerator;
- accepted effective-share source: capitalization denominator;
- FMDL-3B/3C accepted facts: financial denominators;
- CNINFO and accepted public event sources: corporate-action identity and effective dates;
- provider PE/PB/PS: cross-check only.

## 8. Controlled failure states

- `CONTROLLED_CAPITALIZATION_QUARANTINE`
- `MISSING_REQUIRED_INPUT`
- `FUTURE_DENOMINATOR_BLOCKED`
- `NON_POSITIVE_EARNINGS`
- `NON_POSITIVE_BOOK_EQUITY`
- `NON_POSITIVE_REVENUE`
- `INVALID_ENTERPRISE_VALUE`
- `NOT_APPLICABLE_SECTOR`
- `DEFERRED_TO_SHAREHOLDER_RETURN_LAYER`

## 9. Replay requirement

Every accepted metric must be reproducible from:

- market numerator lineage;
- share-count lineage;
- financial fact IDs;
- formula version;
- sector applicability contract;
- as-of timestamp.

FMDL-3E will later validate historical replay, restatement replay, incremental refresh and Last-known-good preservation across multiple operating runs.
