# FMDL-3C-B — Financial Factor Engine MVP

## Purpose

FMDL-3C-B executes the accepted FMDL-3C-A factor contract over the accepted FMDL-3B Statement Current. It creates a point-in-time factor history and a compact full-Universe Factor Current without creating a composite score, research conclusion, portfolio instruction or trade authority.

## Entry gates

- `FMDL3B4_POINT_IN_TIME_STATEMENT_STORE_ACCEPTED`
- `FMDL3CA_FACTOR_ARCHITECTURE_AND_CONTRACT_ACCEPTED`

## Engine outputs

The immutable Release contains:

- 32 factor-history Parquet shards;
- 32 derived-input Parquet shards;
- a full-Universe latest factor Current with one row per symbol and factor;
- statement-signature sector profiles;
- factor coverage and quality summaries;
- decision, independent validation and manifest evidence.

The latest Factor Current includes all Universe symbols, including unsupported or quarantined symbols. Missing inputs are represented by explicit quality states and null values; they are never filled with zero or neutral values.

## Point-in-time construction

Annual flows use accepted FY cumulative values. Interim TTM flows use:

`current YTD + prior FY - prior-year matching YTD`.

Factor availability is the latest availability timestamp among all required inputs. Restated values become visible only at the latest authoritative revision timestamp. Pre-restatement replay remains blocked.

Average balance factors use the current period-end balance and the prior-year matching fiscal-period-type balance. Growth factors use the same fiscal-period type and inherit FMDL-3B-3 comparability controls.

## Sector routing

The MVP infers a controlled sector profile from accepted statement field signatures:

- `GENERAL_NON_FINANCIAL`
- `BANK`
- `INSURANCE`
- `SECURITIES_AND_BROKERAGE`
- `UNRESOLVED`

This is an interim evidence-based routing layer. FMDL-3C-C must compare it with a canonical industry/security master and harden any disagreements. Industrial factors are not silently applied to financial institutions.

## Quality states

Every factor row has one explicit state. Only `VALID` is ranking-eligible. `VALID_WITH_WARNING` is conditionally eligible. All other states are ineligible and must retain a null factor value.

## Exit gate

`FMDL3CB_FINANCIAL_FACTOR_ENGINE_MVP_ACCEPTED`

## Next gate

`FMDL-3C-C_VALIDATION_AND_HARDENING`

## Authority

`DATA_AND_RESEARCH_EVIDENCE_ONLY`; `trade_authority = NONE`.
