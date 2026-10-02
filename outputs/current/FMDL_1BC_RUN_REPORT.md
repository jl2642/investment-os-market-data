# FMDL-1B/C Candidate Data Report

- Run ID: `FMDL1BC_20261002T223102+0800`
- As-of date: `2026-09-30`
- Generated at: `2026-10-02T22:31:02+08:00`
- Market-wide source: `stock_zh_a_spot`
- Universe QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Snapshot QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Promotion state: `CANDIDATE_ONLY`

## Universe metrics

- row_count: `5571`
- duplicate_count: `0`
- symbol_valid_ratio: `1.0`
- identity_fill_ratio: `1.0`
- industry_fill_ratio: `0.5837372105546581`
- listing_date_fill_ratio: `0.5837372105546581`
- lkg_row_ratio: `1.00577721610399`

## Snapshot metrics

- row_count: `5571`
- universe_coverage_ratio: `1.0`
- traded_row_count: `5565`
- positive_close_ratio_for_traded_rows: `1.0`
- negative_volume_rows: `0`
- negative_turnover_rows: `0`
- maximum_return_reconciliation_difference_pp: `0.0004999999999977245`
- market_cap_fill_ratio: `0.0`
- valuation_fill_ratio: `0.0`
- zero_turnover_ratio: `0.001974510859809729`
- maximum_absolute_return_pct: `206.594`

## Source warnings

- attempt_1: JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- attempt_2: JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- attempt_3: JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- optional_source_unavailable
- attempt_1: JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- attempt_2: JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- attempt_3: JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- optional_source_unavailable
- primary_provider_unavailable: stock_zh_a_spot_em
- attempt_1: ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- optional_source_unavailable
- volume_unit_source=SHARES; no lot multiplier applied
- source_zero_price_rows_classified_as_suspended=000016.SZ,002667.SZ,002731.SZ,002813.SZ,002860.SZ,300082.SZ

## Boundary

These files prove real A-share universe and market-snapshot ingestion. They are not yet stable Investment OS current outputs; FMDL-1D/E/F own hardening, scheduled publication and downstream promotion.
