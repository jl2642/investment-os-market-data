# FMDL-5E｜Hong Kong Factor & Screening Adapter

## Status

FMDL-5E is currently in targeted repair round `FMDL-5E-R1`.

The original candidate established the Hong Kong factor and screening pipeline but failed independent investment-research review because issuer profile semantics were unreliable for a material subset of financial and non-financial companies and because 57 of 100 Longlist names were inserted through `BALANCED_FALLBACK` rather than a formal sleeve.

R1 is therefore the only active implementation path.

## Inputs

- FMDL-5B-2 Hong Kong security and issuer semantic overlay;
- FMDL-5C price, volume, corporate-action and HKMA FX Current;
- FMDL-5D HKEX disclosure and point-in-time normalized financial Current.

Accepted source Releases:

- `FMDL5C_20260721_52f17b755436`
- `FMDL5D_20260721_0aee5654502c`

## Factor layer

The adapter computes 28 auditable factors across:

- market trend and momentum;
- volatility, downside risk and drawdown;
- liquidity and trading continuity;
- profitability and margins;
- balance-sheet strength;
- revenue and profit growth;
- earnings yield;
- trailing cash-dividend yield.

All future inputs are prohibited. Missing values remain null. Financial percentiles use the R1 semantic screening profile, while market factors use broad-universe percentiles.

## R1 semantic profile layer

R1 preserves the upstream FMDL-5D classification as `source_profile` and derives an auditable `profile` from official HKEX security and issuer names. The derivation basis is stored in `profile_basis`, and all changes are marked in `profile_override_applied`.

This prevents vendor line-item vocabulary from silently classifying industrial companies as banks or treating securities firms as ordinary industrial companies.

## Screening sleeves

The five formal sleeves are:

1. `QUALITY_COMPOUNDER`
2. `HIGH_DIVIDEND_VALUE`
3. `TREND_LIQUIDITY`
4. `DEFENSIVE_STABILITY`
5. `RECOVERY_WATCH`

The Longlist is built only from these formal sleeves. `BALANCED_FALLBACK` is prohibited.

The final research-priority allocation remains:

- 20 `A_IMMEDIATE_RESEARCH`
- 40 `B_WATCH_OR_TRIGGER`
- 40 `C_SCREEN_FLAG_ONLY`

## Hong Kong-specific case coverage

A separate case registry surfaces the highest-ranked available examples of:

- A-share class / H-share structures;
- WVR issuers;
- RMB dual counters;
- secondary listings;
- Chapter 18A biotech issuers;
- high-dividend securities;
- recent corporate-action securities.

Case coverage is research routing, not score inflation or forced Longlist admission.

## Canonical outputs

- `FMDL5E_FACTOR_DICTIONARY.json`
- `FMDL5E_FACTOR_TABLE.parquet`
- `FMDL5E_FACTOR_DETAIL.parquet`
- `FMDL5E_SCREENING_UNIVERSE.csv`
- `FMDL5E_SLEEVE_DETAIL.csv`
- `FMDL5E_RESEARCH_LONGLIST.csv`
- `FMDL5E_CASE_COVERAGE.csv`
- `FMDL5E_FUNNEL_COUNTS.csv`
- `FMDL5E_SOURCE_REGISTRY.json`
- `FMDL5E_QUALITY_REPORT.json`
- `FMDL5E_DECISION.json`
- `FMDL5E_MANIFEST.json`

Successful main publication creates Current, Immutable Release, Archive and `outputs/status/FMDL5E_LAST_SUCCESS.json`.

## R1 acceptance gates

- exactly 644 source securities;
- at least 600 common equities;
- at least 600 securities with sufficient market-factor coverage;
- at least 600 decision-grade financial inputs;
- at least 150 distinct formal-sleeve securities before final ranking;
- exactly 100 unique Longlist securities;
- all five formal primary sleeves represented;
- at least 10 Longlist names per primary sleeve;
- no primary sleeve above 35% of the Longlist;
- zero fallback Longlist rows;
- zero profile semantic mismatches;
- zero profile anchor mismatches;
- exact 20 / 40 / 40 research-priority buckets;
- zero future price, action or financial rows;
- zero infinite factor values;
- zero candidate-pool, simulation, real-account or order mutation;
- `trade_authority = NONE`.

## Controlled limitations

- Free price and structured financial values remain explicitly unofficial vendor-tier evidence; official HKEXnews supplies filing identity and timing.
- Market capitalization and book-value-per-share are not yet available at a sufficiently reliable Hong Kong-wide level, so P/B and enterprise-value ratios are not fabricated.
- A/H semantic identity is surfaced as a case route; relative A/H valuation requires a later cross-market price and share-class bridge.
- Screening is a research-priority mechanism, not a claim of alpha or an investment recommendation.

## Publication boundary

Only a successful PR candidate may be merged. A successful main run must then publish Current, Immutable Release, Archive and Last-success. FMDL-5F cannot begin before these publication gates are verified.

## Expected exit

`FMDL5E_HONG_KONG_FACTOR_AND_SCREENING_ADAPTER_ACCEPTED`

Repair identity:

`FMDL-5E-R1`

Next gate:

`FMDL-5F_PUBLIC_EQUITY_RESEARCH_ADAPTER`
