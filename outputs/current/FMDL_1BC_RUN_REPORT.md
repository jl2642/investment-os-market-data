# FMDL-1B/C Candidate Data Report

- Run ID: `FMDL1BC_20261027T001925+0800`
- As-of date: `2026-10-26`
- Generated at: `2026-10-27T00:19:25+08:00`
- Market-wide source: `stock_zh_a_spot`
- Universe QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Snapshot QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Promotion state: `CANDIDATE_ONLY`

## Universe metrics

- row_count: `5577`
- duplicate_count: `0`
- symbol_valid_ratio: `1.0`
- identity_fill_ratio: `1.0`
- industry_fill_ratio: `0.5843643535951228`
- listing_date_fill_ratio: `1.0`
- lkg_row_ratio: `1.0`

## Snapshot metrics

- row_count: `5577`
- universe_coverage_ratio: `1.0`
- traded_row_count: `5573`
- positive_close_ratio_for_traded_rows: `1.0`
- negative_volume_rows: `0`
- negative_turnover_rows: `0`
- maximum_return_reconciliation_difference_pp: `0.0005000000000046079`
- market_cap_fill_ratio: `0.0`
- valuation_fill_ratio: `0.0`
- zero_turnover_ratio: `0.0014344629729245114`
- maximum_absolute_return_pct: `29.19`

## Source warnings

- primary_provider_unavailable: stock_zh_a_spot_em
- attempt_1: ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- optional_source_unavailable
- volume_unit_source=SHARES; no lot multiplier applied
- source_zero_price_rows_classified_as_suspended=002717.SZ,002827.SZ,301468.SZ

## Boundary

These files prove real A-share universe and market-snapshot ingestion. They are not yet stable Investment OS current outputs; FMDL-1D/E/F own hardening, scheduled publication and downstream promotion.
