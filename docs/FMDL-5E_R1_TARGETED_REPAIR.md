# FMDL-5E-R1｜Targeted Profile and Formal-Sleeve Repair

## 1. Repair trigger

The first FMDL-5E candidate passed its original machine gates but failed independent investment-research review for two material reasons:

1. the FMDL-5D source profile was inferred partly from vendor statement-item tokens, causing non-financial issuers such as Midea Group and First Tractor to be classified as banks while securities firms such as CITIC Securities, CICC and CSC Financial remained general non-financial issuers;
2. only 43 of the 100 Longlist names had a formal primary sleeve, while 57 names were inserted through `BALANCED_FALLBACK`.

These were not cosmetic labels. Financial percentiles were grouped by profile, and the fallback population weakened the claim that the 100-name Longlist was produced by the five stated Hong Kong strategies.

## 2. Profile repair

R1 preserves the upstream FMDL-5D profile as `source_profile` and derives a separate screening profile from official HKEX security and issuer names.

The derived profiles are:

- `GENERAL_NON_FINANCIAL`
- `BANK`
- `INSURANCE`
- `SECURITIES_AND_BROKERAGE`
- `REIT`
- `CONTROLLED_NON_FINANCIAL`

Non-equities and common equities without decision-grade financial Current fail closed to `CONTROLLED_NON_FINANCIAL`. Every derived profile carries a `profile_basis` and `profile_override_applied` flag.

Regression anchors include HSBC, Midea Group, First Tractor, China Taiping, Ping An, CICC, CITIC Securities and CSC Financial.

## 3. Formal-sleeve repair

R1 retains the five accepted sleeve definitions but expands their candidate breadth and lowers only the pre-Longlist score floors required to create a sufficiently diverse research universe:

- Quality Compounder: maximum 90;
- High Dividend Value: maximum 80;
- Trend Liquidity: maximum 90;
- Defensive Stability: maximum 80;
- Recovery Watch: maximum 60.

The component weights, minimum component gates, null preservation and explicit coverage penalty remain in force.

`BALANCED_FALLBACK` is prohibited. The engine must have at least 100 distinct formal-sleeve securities before constructing the Longlist. All 100 Longlist rows must have one of the five formal primary sleeves.

## 4. Hardened acceptance gates

In addition to the original FMDL-5E gates, R1 requires:

- at least 150 distinct formal-sleeve securities before final ranking;
- exactly zero fallback Longlist rows;
- all five formal sleeves represented as primary sleeves;
- at least 10 Longlist names from each primary sleeve;
- no single primary sleeve above 35% of the Longlist;
- zero semantic profile mismatches;
- zero profile-anchor mismatches;
- all 100 rows marked `FORMAL_SLEEVE_ONLY`;
- unchanged zero future-input, zero state-mutation and zero-trade-authority controls.

## 5. Boundary

FMDL-5E-R1 produces a research-priority Longlist only. It does not promote securities to the Investment OS candidate pool, simulation portfolio or real account, and it does not create orders.

`trade_authority = NONE`.

## 6. Exit

Expected status:

`FMDL5E_HONG_KONG_FACTOR_AND_SCREENING_ADAPTER_ACCEPTED`

Repair identity:

`FMDL-5E-R1`

Next gate after PR validation, merge and main publication:

`FMDL-5F_PUBLIC_EQUITY_RESEARCH_ADAPTER`
