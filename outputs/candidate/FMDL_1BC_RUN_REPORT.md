# FMDL-1B/C Candidate Data Report

- Run ID: `FMDL1BC_20260716T165927+0800`
- As-of date: `2026-07-16`
- Generated at: `2026-07-16T16:59:27+08:00`
- Market-wide source: `stock_zh_a_spot`
- Universe QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Snapshot QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Promotion state: `CANDIDATE_ONLY`

## Universe metrics

- row_count: `5529`
- duplicate_count: `0`
- symbol_valid_ratio: `1.0`
- identity_fill_ratio: `1.0`
- industry_fill_ratio: `0.5825646590703563`
- listing_date_fill_ratio: `1.0`
- lkg_row_ratio: `1.0`

## Snapshot metrics

- row_count: `5529`
- universe_coverage_ratio: `1.0`
- traded_row_count: `5525`
- positive_close_ratio_for_traded_rows: `1.0`
- negative_volume_rows: `0`
- negative_turnover_rows: `0`
- maximum_return_reconciliation_difference_pp: `0.0004999999999999449`
- market_cap_fill_ratio: `0.0`
- valuation_fill_ratio: `0.0`
- zero_turnover_ratio: `0.0010851871947911015`
- maximum_absolute_return_pct: `98.205`

## Source warnings

- primary_provider_unavailable: stock_zh_a_spot_em
- attempt_1: ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- optional_source_unavailable
- volume_unit_source=SHARES; no lot multiplier applied
- source_zero_price_rows_classified_as_suspended=002677.SZ,301234.SZ,920685.BJ

## Boundary

These files prove real A-share universe and market-snapshot ingestion. They are not yet stable Investment OS current outputs; FMDL-1D/E/F own hardening, scheduled publication and downstream promotion.
