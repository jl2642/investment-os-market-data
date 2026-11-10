# FMDL-1B/C Candidate Data Report

- Run ID: `FMDL1BC_20261111T011833+0800`
- As-of date: `2026-11-10`
- Generated at: `2026-11-11T01:18:33+08:00`
- Market-wide source: `stock_zh_a_spot_em`
- Universe QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Snapshot QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Promotion state: `CANDIDATE_ONLY`

## Universe metrics

- row_count: `5928`
- duplicate_count: `0`
- symbol_valid_ratio: `1.0`
- identity_fill_ratio: `1.0`
- industry_fill_ratio: `0.5501012145748988`
- listing_date_fill_ratio: `0.5501012145748988`
- lkg_row_ratio: `1.0`

## Snapshot metrics

- row_count: `5928`
- universe_coverage_ratio: `1.0`
- traded_row_count: `5577`
- positive_close_ratio_for_traded_rows: `1.0`
- negative_volume_rows: `0`
- negative_turnover_rows: `0`
- maximum_return_reconciliation_difference_pp: `0.005000000000017657`
- market_cap_fill_ratio: `0.941970310391363`
- valuation_fill_ratio: `0.9412955465587044`
- zero_turnover_ratio: `0.059885290148448046`
- maximum_absolute_return_pct: `184.77`

## Source warnings

- attempt_1: JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- attempt_2: JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- attempt_3: JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- optional_source_unavailable
- attempt_1: JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- attempt_2: JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- attempt_3: JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- optional_source_unavailable

## Boundary

These files prove real A-share universe and market-snapshot ingestion. They are not yet stable Investment OS current outputs; FMDL-1D/E/F own hardening, scheduled publication and downstream promotion.
