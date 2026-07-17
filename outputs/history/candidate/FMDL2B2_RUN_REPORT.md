# FMDL-2B-2 Full-Universe Historical Backfill

- Release ID: `FMDL2B2_29556547410_1`
- As-of date: `2026-07-16`
- Attempted symbols: `5529`
- Usable symbols: `5525` (`99.93%`)
- Quarantined symbols: `4`
- History rows: `2494405`
- Base store size: `131.61 MiB`
- Candidate status: `CANDIDATE_ACCEPTED_WITH_QUARANTINE`
- Hard failures: `0`
- Promoted impossible-OHLC rows: `0`
- Quarantined impossible-OHLC rows: `3`

## Board results

| Board | Attempted | Usable | Ratio |
|---|---:|---:|---:|
| BSE | 328 | 328 | 100.00% |
| CHINEXT | 1398 | 1398 | 100.00% |
| SH_MAIN | 1698 | 1698 | 100.00% |
| STAR | 610 | 606 | 99.34% |
| SZ_MAIN | 1494 | 1494 | 100.00% |
| UNKNOWN | 1 | 1 | 100.00% |

## Boundary

Impossible OHLC series are excluded from promoted Parquet history and retained only as quarantine evidence. This candidate does not calculate production factors, rank securities, modify a candidate pool or create trade authority.
