# FMDL-5E｜Hong Kong Factor & Screening Adapter

## 1. Objective

FMDL-5E converts the accepted Hong Kong market store and point-in-time financial evidence into a transparent research-priority factor and screening layer. It reuses the accepted A-share funnel architecture without pretending that A-share thresholds, board structure or liquidity units transfer unchanged to Hong Kong.

The phase ends at a governed 100-name Hong Kong research Longlist. It does not create company research conclusions, candidate-pool admission, simulation admission, real-account admission, position sizing, target prices or orders.

## 2. Bound source releases

- FMDL-5C: `FMDL5C_20260721_52f17b755436`
- FMDL-5D: `FMDL5D_20260721_0aee5654502c`
- Security semantics: accepted FMDL-5B-2 Current
- Market as-of: latest accepted FMDL-5C completed Hong Kong session

All upstream inputs must remain accepted, hash-bound and `trade_authority = NONE`.

## 3. Factor families

The adapter publishes 28 factors across:

1. Market trend and momentum;
2. Realized risk and drawdown;
3. Liquidity and active-trading continuity;
4. Profitability and margins;
5. Balance-sheet resilience;
6. Financial growth;
7. Earnings yield;
8. Trailing cash-dividend yield.

Vendor-adjusted close is used for return continuity where available, with raw close retained upstream. Turnover is expressed in HKD using non-future HKMA FX. Financial ratios are based only on FMDL-5D decision-grade Current rows whose official availability is not later than the market as-of date.

Missing factors remain null. A sleeve may renormalize weights only after a minimum-component gate and applies an explicit coverage penalty; it may never fill a missing factor with zero or a neutral percentile.

## 4. Percentile policy

- Market, risk, liquidity and shareholder-return factors use broad Hong Kong equity percentiles.
- Financial, balance-sheet, growth and earnings-yield factors use profile-neutral percentiles across general companies, banks, insurers, securities firms and REITs.
- Funds and ETFs remain controlled non-equity exclusions from issuer-factor screening.

## 5. Screening sleeves

- `QUALITY_COMPOUNDER`
- `HIGH_DIVIDEND_VALUE`
- `TREND_LIQUIDITY`
- `DEFENSIVE_STABILITY`
- `RECOVERY_WATCH`

The first four are Core research routes. Recovery is a Watch route. Cross-sleeve ranking uses within-sleeve rank percentile, raw sleeve score and a capped multi-sleeve bonus. A transparent balanced fallback is permitted only to complete the 100-name research queue after investability and minimum-factor gates.

## 6. Hong Kong-specific case coverage

A separate case registry surfaces the highest-ranked available examples of:

- A-share class / H-share structures;
- WVR issuers;
- RMB dual counters;
- secondary listings;
- Chapter 18A biotech issuers;
- high-dividend securities;
- recent corporate-action securities.

Case coverage is research routing, not score inflation or forced Longlist admission.

## 7. Canonical outputs

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

## 8. Acceptance gates

- exactly 644 source securities and at least 600 common equities;
- at least 600 equities with sufficient market-factor coverage;
- at least 600 FMDL-5D decision-grade financial inputs;
- exactly 100 unique Longlist names;
- priority buckets exactly 20 / 40 / 40;
- at least four non-fallback primary sleeves represented;
- zero future price, action or financial input rows;
- zero infinite numeric factor values;
- zero candidate, simulation, real-account or order mutation;
- `trade_authority = NONE`.

## 9. Controlled limitations

- Free price and structured financial values remain explicitly unofficial vendor-tier evidence; official HKEXnews supplies filing identity and timing.
- Market capitalization and book-value-per-share are not yet available at a sufficiently reliable Hong Kong-wide level, so P/B and enterprise-value ratios are not fabricated.
- A/H semantic identity is surfaced as a case route; relative A/H valuation requires a later cross-market price and share-class bridge.
- Screening is a research-priority mechanism, not a claim of alpha or an investment recommendation.

## 10. Exit

Expected accepted status:

`FMDL5E_HONG_KONG_FACTOR_AND_SCREENING_ADAPTER_ACCEPTED`

Next gate:

`FMDL-5F_PUBLIC_EQUITY_RESEARCH_ADAPTER`
