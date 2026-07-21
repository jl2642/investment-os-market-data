# FMDL-5D — HKEX Disclosure & Financial Normalization

## 1. Objective

FMDL-5D binds the accepted 644-security Southbound universe and FMDL-5C market store to an auditable Hong Kong issuer financial-evidence layer. It combines official HKEXnews disclosure identity and timing with explicitly labelled free-vendor structured statement values, while preserving point-in-time availability, revision chains, source lineage and zero trading authority.

This phase owns disclosure and financial evidence only. It does not score securities, promote candidates, mutate simulation or real-account state, generate orders, or claim investment alpha.

## 2. Input baseline

- FMDL-5C accepted decision and Hong Kong trading-date store;
- FMDL-5B-2 security / issuer semantic overlay;
- 644 accepted Southbound securities, including controlled fund exclusions;
- field registry and fail-closed acceptance contract in this release.

## 3. Source hierarchy

1. `HKEXNEWS_TITLE_SEARCH` — official-primary filing identity, title, release timestamp, document URL and revision evidence.
2. `EASTMONEY_HK_FINANCIAL_REPORT` — unofficial free-vendor structured balance-sheet, income-statement and cash-flow values through AKShare.
3. `EASTMONEY_HK_FINANCIAL_INDICATOR` — unofficial free-vendor reporting currency and fiscal-year context.

Official disclosure metadata does not validate every numeric value in a vendor export. Decision-grade eligibility therefore requires both an exact canonical field mapping and a point-in-time match to an official HKEXnews filing; source tiers remain separate in every row.

## 4. Point-in-time and revision policy

- Filing release time is retained as published by HKEXnews.
- Availability is conservative: strictly the next accepted Hong Kong trading-session open after release.
- Later supplemental, revised, updated or corrected filings append a new revision sequence.
- Earlier revisions remain auditable and receive `superseded_at`; they are never silently overwritten.
- Structured values without an official filing-period match remain `BLOCKED_NO_OFFICIAL_PIT_MATCH` and are not decision-grade.

## 5. Normalization policy

- Exact normalized aliases or explicit source codes only; no fuzzy semantic coercion.
- Missing values remain null. No zero or neutral fill is permitted.
- Reporting currency is retained from source context; unknown currency remains explicit.
- Funds and ETFs are controlled not-applicable exclusions, not data failures.
- Banking, insurance, securities and general-company profiles are inferred from statement evidence and retained for later factor routing.

## 6. Canonical outputs

- `FMDL5D_HKEX_FINANCIAL_DISCLOSURES.csv`
- `FMDL5D_MAPPED_RAW_FACTS.parquet`
- `FMDL5D_NORMALIZED_FINANCIAL_FACTS.parquet`
- `FMDL5D_ISSUER_FINANCIAL_CURRENT.csv`
- `FMDL5D_UNMAPPED_FIELD_CATALOG.csv`
- `FMDL5D_FAILURES.csv`
- `FMDL5D_QUALITY_REPORT.json`
- `FMDL5D_SOURCE_REGISTRY.json`
- `FMDL5D_R1_RUNTIME_REPORT.json`
- `FMDL5D_DECISION.json`
- `FMDL5D_MANIFEST.json`

Successful main publication creates immutable Release, Current, Archive and `outputs/status/FMDL5D_LAST_SUCCESS.json`.

## 7. Zero-tolerance gates

- accepted FMDL-5C source release must be bound;
- no future-available financial facts;
- no duplicate normalized fact keys;
- no invalid numeric values published;
- no decision-grade facts without official filing lineage;
- no missing, duplicated or out-of-bound shard security result;
- no failed candidate may replace Current or Last-success;
- no candidate-pool, simulation, real-account or order mutation;
- `trade_authority = NONE`.

## 8. FMDL-5D-R1 runtime repair

The first monolithic full-universe candidate run reached the 120-minute workflow limit before acceptance. FMDL-5D-R1 repairs orchestration without weakening the data contract:

- official HKEXnews disclosure scanning runs as an independent checkpoint;
- 613 common-equity structured-financial requests are deterministically partitioned into 12 disjoint shards;
- every shard persists raw facts, unmapped rows, per-security result metadata and a shard status report;
- shard failures do not silently disappear and successful shard artifacts remain independently inspectable;
- aggregation requires all expected shard artifacts, exact full-security coverage and no duplicate or unexpected security IDs;
- aggregate acceptance retains the original coverage, PIT, lineage and zero-mutation gates;
- the runtime report is included in the canonical manifest and the successful Last-success pointer records the repair round.

The R1 repair changes execution topology only. It does not lower FMDL-5D acceptance thresholds or authorize FMDL-5E before formal publication.

## 9. Controlled limitations

- HKEXnews is authoritative for disclosure identity and timing, while structured financial values remain vendor-tier evidence until document-level numeric extraction is separately warranted.
- Exact mapping intentionally leaves unsupported statement lines in the unmapped catalog.
- Corporate-action values from FMDL-5C remain separate; issuer-level confirmation is linked through official filing metadata rather than overwritten.
- FMDL-5D output is research evidence only. Factor computation and screening begin at FMDL-5E.

## 10. Exit gate

Expected accepted status:

`FMDL5D_HKEX_DISCLOSURE_AND_FINANCIAL_NORMALIZATION_ACCEPTED_WITH_CONTROLLED_QUARANTINE`

Next gate:

`FMDL-5E_HONG_KONG_FACTOR_AND_SCREENING_ADAPTER`
