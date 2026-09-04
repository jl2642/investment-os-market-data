# FMDL-1B/C Candidate Data Report

- Run ID: `FMDL1BC_20260904T203249+0800`
- As-of date: `2026-09-04`
- Generated at: `2026-09-04T20:32:49+08:00`
- Market-wide source: `stock_zh_a_spot`
- Universe QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Snapshot QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Promotion state: `CANDIDATE_ONLY`

## Universe metrics

- row_count: `5555`
- duplicate_count: `0`
- symbol_valid_ratio: `1.0`
- identity_fill_ratio: `1.0`
- industry_fill_ratio: `0.5832583258325833`
- listing_date_fill_ratio: `0.5832583258325833`
- lkg_row_ratio: `1.002888608051995`

## Snapshot metrics

- row_count: `5555`
- universe_coverage_ratio: `1.0`
- traded_row_count: `5549`
- positive_close_ratio_for_traded_rows: `1.0`
- negative_volume_rows: `0`
- negative_turnover_rows: `0`
- maximum_return_reconciliation_difference_pp: `0.0004999999999999449`
- market_cap_fill_ratio: `0.0`
- valuation_fill_ratio: `0.0`
- zero_turnover_ratio: `0.00144014401440144`
- maximum_absolute_return_pct: `111.745`

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
- source_zero_price_rows_classified_as_suspended=000016.SZ,002731.SZ,002870.SZ,002998.SZ,301139.SZ,301266.SZ

## Boundary

These files prove real A-share universe and market-snapshot ingestion. They are not yet stable Investment OS current outputs; FMDL-1D/E/F own hardening, scheduled publication and downstream promotion.
