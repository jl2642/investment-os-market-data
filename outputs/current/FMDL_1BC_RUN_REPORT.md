# FMDL-1B/C Candidate Data Report

- Run ID: `FMDL1BC_20260925T211835+0800`
- As-of date: `2026-09-24`
- Generated at: `2026-09-25T21:18:35+08:00`
- Market-wide source: `stock_zh_a_spot`
- Universe QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Snapshot QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Promotion state: `CANDIDATE_ONLY`

## Universe metrics

- row_count: `5569`
- duplicate_count: `0`
- symbol_valid_ratio: `1.0`
- identity_fill_ratio: `1.0`
- industry_fill_ratio: `0.583408152271503`
- listing_date_fill_ratio: `1.0`
- lkg_row_ratio: `1.0054161400974906`

## Snapshot metrics

- row_count: `5569`
- universe_coverage_ratio: `1.0`
- traded_row_count: `5562`
- positive_close_ratio_for_traded_rows: `1.0`
- negative_volume_rows: `0`
- negative_turnover_rows: `0`
- maximum_return_reconciliation_difference_pp: `0.0005000000000023874`
- market_cap_fill_ratio: `0.0`
- valuation_fill_ratio: `0.0`
- zero_turnover_ratio: `0.0023343508708924404`
- maximum_absolute_return_pct: `331.425`

## Source warnings

- primary_provider_unavailable: stock_zh_a_spot_em
- attempt_1: ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- optional_source_unavailable
- volume_unit_source=SHARES; no lot multiplier applied
- source_zero_price_rows_classified_as_suspended=000016.SZ,002731.SZ,002860.SZ,300082.SZ,300096.SZ,301139.SZ

## Boundary

These files prove real A-share universe and market-snapshot ingestion. They are not yet stable Investment OS current outputs; FMDL-1D/E/F own hardening, scheduled publication and downstream promotion.
