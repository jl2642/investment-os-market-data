# FMDL-1B/C Candidate Data Report

- Run ID: `FMDL1BC_20261014T212353+0800`
- As-of date: `2026-10-14`
- Generated at: `2026-10-14T21:23:53+08:00`
- Market-wide source: `stock_zh_a_spot`
- Universe QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Snapshot QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Promotion state: `CANDIDATE_ONLY`

## Universe metrics

- row_count: `5574`
- duplicate_count: `0`
- symbol_valid_ratio: `1.0`
- identity_fill_ratio: `1.0`
- industry_fill_ratio: `0.5837818442770003`
- listing_date_fill_ratio: `1.0`
- lkg_row_ratio: `1.006318830113739`

## Snapshot metrics

- row_count: `5574`
- universe_coverage_ratio: `1.0`
- traded_row_count: `5567`
- positive_close_ratio_for_traded_rows: `1.0`
- negative_volume_rows: `0`
- negative_turnover_rows: `0`
- maximum_return_reconciliation_difference_pp: `0.0004999999999997229`
- market_cap_fill_ratio: `0.0`
- valuation_fill_ratio: `0.0`
- zero_turnover_ratio: `0.002152852529601722`
- maximum_absolute_return_pct: `20.165`

## Source warnings

- primary_provider_unavailable: stock_zh_a_spot_em
- attempt_1: ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- optional_source_unavailable
- volume_unit_source=SHARES; no lot multiplier applied
- source_zero_price_rows_classified_as_suspended=000016.SZ,002388.SZ,002717.SZ,002731.SZ,300773.SZ,301314.SZ

## Boundary

These files prove real A-share universe and market-snapshot ingestion. They are not yet stable Investment OS current outputs; FMDL-1D/E/F own hardening, scheduled publication and downstream promotion.
