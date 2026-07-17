# FMDL-2B-4 Current Interfaces

## History Current

`outputs/history/current/`

- `HISTORY_CURRENT_RELEASE.json`
- `HISTORY_CURRENT_MANIFEST.json`
- `HISTORY_CURRENT_STATUS.csv`
- `HISTORY_REFRESH_QUALITY.json`
- `HISTORY_CONTINUITY_DIAGNOSTICS.csv`
- `FMDL2B4_HISTORY_REFRESH_REPORT.json`

The manifest resolves the immutable base, ordered incremental deltas and full-series repair overrides. Consumers must validate component hashes before reading composite history.

## Factor Current

`outputs/factors/current/`

- `FACTOR_CURRENT_RELEASE.json`
- `BASIC_FACTOR_TABLE.parquet`
- `BASIC_FACTOR_DETAIL.parquet`
- `BASIC_FACTOR_STATUS.csv`
- `BASIC_FACTOR_QUALITY.json`
- `BASIC_FACTOR_MANIFEST.json`
- `FMDL2B4_FACTOR_REFRESH_REPORT.json`

These outputs remain market-behaviour research evidence. They are not screening-sleeve results and have no trade authority.

## Operating status

- `outputs/status/FMDL2B4_LAST_RUN.json`
- `outputs/status/FMDL2B4_LAST_SUCCESS.json`

A failed run must state `FAILED_LKG_PRESERVED`. A same-date rerun must state `NO_OP_ALREADY_CURRENT`.
