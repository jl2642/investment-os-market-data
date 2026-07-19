# FMDL-3C-C — Validation & Hardening

## Purpose

FMDL-3C-C converts the accepted FMDL-3C-B raw financial-factor engine into a controlled pre-scoring layer. It validates coverage and distributions, freezes factor production eligibility, preserves raw values, creates tail-controlled values and explicit factor-level/profile-level exclusions, and blocks unsupported scoring.

This phase does not create a composite score, stock recommendation, portfolio instruction or trade authority.

## Entry gate

`FMDL3CB_FINANCIAL_FACTOR_ENGINE_MVP_ACCEPTED`

## Measured defects addressed

The accepted 3C-B engine is structurally correct, but raw outputs are not yet suitable for scoring without hardening:

- ratio and growth factors contain legitimate but very large tails caused by small denominators and low bases;
- three-year CAGR factors have no accepted current coverage because the Statement Current lacks sufficient comparable history;
- debt-component factors have low coverage under the current provider mapping;
- industrial factors are intentionally not applicable to banks, insurers and brokerages;
- the repository does not yet contain a canonical full-industry security master, so industry-neutral scoring would be misleading.

## Frozen factor policy

Each of the 29 factors receives one status:

- `PRODUCTION_CORE`: may enter a later scoring layer when row-level quality and profile gates pass;
- `DIAGNOSTIC_ONLY`: retained for research and risk interpretation but cannot contribute to a production score;
- `DEFERRED_HISTORY`: blocked until the accepted historical store satisfies the declared lookback.

FMDL-3C-C freezes 18 production-core factors, 9 diagnostic-only factors and 2 deferred-history factors.

## Hardening method

Raw values remain immutable. For every valid row in an eligible coarse peer group, the hardening layer calculates:

- factor-level/profile-level 1st and 99th percentile limits;
- a winsorized value;
- median and median absolute deviation;
- a robust z-score clipped to ±5;
- an economic-direction percentile rank where authorized;
- tail and warning flags.

The peer group in this phase is the accepted `sector_profile`, not a full industry classification. Only `GENERAL_NON_FINANCIAL` is authorized for production-core hardening. Financial institutions and unresolved profiles are controlled exclusions pending sector-specific factor packs and canonical security-master reconciliation.

## Coverage gates

A production-core factor must have valid or warning coverage of at least 60% of the accepted general non-financial profile. Failure blocks the factor from production eligibility without deleting its raw observations.

## Output assets

- hardened latest Factor Current;
- factor policy and measured coverage registry;
- factor distribution diagnostics;
- tail-event registry;
- profile reconciliation registry;
- decision, independent validation and manifest evidence;
- immutable Release, compact Current, Archive and Last-success pointer.

## Controlled limitations

- no canonical industry-neutral percentile is claimed;
- banks, insurers and brokerages remain controlled exclusions from the industrial factor pack;
- two three-year CAGR factors remain deferred until historical backfill;
- debt-component factors remain diagnostic until provider field coverage is hardened;
- no composite score or trade signal is authorized.

## Exit gate

`FMDL3CC_FINANCIAL_FACTOR_VALIDATION_AND_HARDENING_ACCEPTED`

## Next gate

`FMDL-3C-D_FINANCIAL_SCORE_AND_INVESTMENT_OS_INTERFACE`

## Authority

`DATA_AND_RESEARCH_EVIDENCE_ONLY`; `trade_authority = NONE`.
