# Data Contract v1.0.0

## 1. Purpose

This contract defines the minimum semantics, formats, lineage and publication requirements for datasets consumed by Investment OS.

A file is not a valid Investment OS dataset merely because it exists. It must conform to its schema and have a passing manifest.

## 2. Global conventions

- Business timezone: `Asia/Shanghai`.
- Trading dates: ISO `YYYY-MM-DD`.
- Timestamps: ISO 8601 with explicit offset, for example `2026-07-16T17:30:00+08:00`.
- Security key: `symbol` in canonical exchange-qualified form.
- Currency: ISO 4217; A-share MVP uses `CNY`.
- Prices: currency per share.
- Volume: shares, not lots.
- Turnover: CNY.
- Rates and returns: percentage points unless the field name explicitly ends in `_ratio` and the schema states decimal form.
- Missing numeric values: null/blank, never zero unless zero is the actual observation.
- Boolean values: true/false.
- Text encoding: UTF-8.
- CSV delimiter: comma; header required.
- Decimal separator: period; no thousands separator.

## 3. Canonical symbol format

- Shanghai: `600000.SH`, `601xxx.SH`, `603xxx.SH`, `605xxx.SH`, `688xxx.SH` and other valid exchange codes.
- Shenzhen: `000001.SZ`, `001xxx.SZ`, `002xxx.SZ`, `003xxx.SZ`, `300xxx.SZ` and other valid exchange codes.
- Beijing: `8xxxxx.BJ`, `4xxxxx.BJ` or other valid Beijing Stock Exchange A-share codes supported by the source.

Raw source codes must be retained only in source capture or an explicit `source_symbol` field.

## 4. Common lineage fields

Every published row-level dataset must include or inherit through its manifest:

- `dataset_id`
- `schema_version`
- `as_of_date`
- `generated_at`
- `source_primary`
- `source_timestamp`
- `record_quality`
- `row_hash`

`record_quality` values:

- `VALID`
- `PARTIAL`
- `STALE`
- `SUSPECT`
- `INVALID`

Rows marked `INVALID` cannot enter a published current dataset.

## 5. Dataset: a_share_universe

Grain: one row per security per `as_of_date`.

Required core fields:

- `as_of_date`
- `symbol`
- `source_symbol`
- `name`
- `exchange`
- `board`
- `currency`
- `security_type`
- `listing_status`
- `is_st`
- `is_suspended`
- `source_primary`
- `source_timestamp`
- `record_quality`
- `row_hash`

Optional fields include listing date, delisting date, industry code/name/source and lot size.

The universe dataset includes all valid A-share common stocks and flags investability conditions. ST, suspension or young-listing exclusions belong to FMDL-2 screening, not to hidden deletion at the data layer.

## 6. Dataset: daily_market_snapshot

Grain: one row per security per trading date.

Required core fields:

- `as_of_date`
- `symbol`
- `close`
- `prev_close`
- `pct_change`
- `volume_shares`
- `turnover_cny`
- `data_status`
- `source_primary`
- `source_timestamp`
- `record_quality`
- `row_hash`

Optional but targeted MVP fields:

- open, high, low
- amplitude percentage
- turnover-rate percentage
- total and float market capitalisation
- PE TTM and PB

No valuation field is imputed when unavailable. Missing valuation data is reported through QA and may be completed in FMDL-3.

## 7. Dataset: dataset_manifest

One manifest is required per dataset release. It must contain:

- dataset identity and version
- schema version
- as-of and generation times
- source list and source timestamps
- row count and column count
- file path, size and SHA-256
- QA status and failed/warned gate IDs
- parent release and last-known-good release
- publication status
- notes and known limitations

## 8. Publication states

Allowed manifest states:

- `CANDIDATE`
- `READY`
- `DEGRADED`
- `QUARANTINED`
- `FAILED`
- `PUBLISHED`

Only `READY` or policy-permitted `DEGRADED` datasets may become `PUBLISHED`.

## 9. Immutability and correction

- Dated archive releases are immutable.
- A correction creates a new run ID and manifest; it does not rewrite history silently.
- Stable `outputs/current/` files are pointers/copies to the newest accepted release.
- Every current release must be reproducible from its archived dataset, manifest, configuration version and source capture where legally and technically feasible.

## 10. Compatibility

Investment OS consumers must reject:

- unknown major schema versions;
- missing manifest;
- manifest hash mismatch;
- `QUARANTINED` or `FAILED` status;
- stale data outside the stated operating tolerance;
- row-level `INVALID` records.
