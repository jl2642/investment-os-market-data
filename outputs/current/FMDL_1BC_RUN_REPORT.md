# FMDL-1B/C Candidate Data Report

- Run ID: `FMDL1BC_20260908T214947+0800`
- As-of date: `2026-09-08`
- Generated at: `2026-09-08T21:49:47+08:00`
- Market-wide source: `stock_zh_a_spot`
- Universe QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Snapshot QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Promotion state: `CANDIDATE_ONLY`

## Universe metrics

- row_count: `5557`
- duplicate_count: `0`
- symbol_valid_ratio: `1.0`
- identity_fill_ratio: `1.0`
- industry_fill_ratio: `0.5832283606262372`
- listing_date_fill_ratio: `0.5832283606262372`
- lkg_row_ratio: `1.0032496840584944`

## Snapshot metrics

- row_count: `5557`
- universe_coverage_ratio: `1.0`
- traded_row_count: `5552`
- positive_close_ratio_for_traded_rows: `1.0`
- negative_volume_rows: `0`
- negative_turnover_rows: `0`
- maximum_return_reconciliation_difference_pp: `0.0005000000000023874`
- market_cap_fill_ratio: `0.0`
- valuation_fill_ratio: `0.0`
- zero_turnover_ratio: `0.0016195789094835343`
- maximum_absolute_return_pct: `29.911`

## Source warnings

- attempt_1: ConnectionError: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))
- attempt_2: ConnectionError: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))
- attempt_3: ConnectionError: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))
- optional_source_unavailable
- attempt_1: ConnectionError: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))
- attempt_2: ConnectionError: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))
- attempt_3: ConnectionError: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))
- optional_source_unavailable
- primary_provider_unavailable: stock_zh_a_spot_em
- attempt_1: ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- optional_source_unavailable
- volume_unit_source=SHARES; no lot multiplier applied
- source_zero_price_rows_classified_as_suspended=000016.SZ,002731.SZ,002870.SZ,002998.SZ,301139.SZ

## Boundary

These files prove real A-share universe and market-snapshot ingestion. They are not yet stable Investment OS current outputs; FMDL-1D/E/F own hardening, scheduled publication and downstream promotion.
