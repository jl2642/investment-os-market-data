# FMDL-1B/C Candidate Data Report

- Run ID: `FMDL1BC_20261127T031807+0800`
- As-of date: `2026-11-26`
- Generated at: `2026-11-27T03:18:07+08:00`
- Market-wide source: `stock_zh_a_spot`
- Universe QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Snapshot QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Promotion state: `CANDIDATE_ONLY`

## Universe metrics

- row_count: `5581`
- duplicate_count: `0`
- symbol_valid_ratio: `1.0`
- identity_fill_ratio: `1.0`
- industry_fill_ratio: `0.5844830675506182`
- listing_date_fill_ratio: `1.0`
- lkg_row_ratio: `1.0`
- lkg_identity_retention: `1.0`

## Snapshot metrics

- row_count: `5581`
- universe_coverage_ratio: `0.9996416412829242`
- snapshot_symbol_coverage_ratio: `1.0`
- priced_universe_symbol_count: `5579`
- unpriced_universe_symbol_count: `2`
- traded_row_count: `5579`
- positive_close_ratio_for_traded_rows: `1.0`
- negative_volume_rows: `0`
- negative_turnover_rows: `0`
- maximum_return_reconciliation_difference_pp: `0.0004999999999999449`
- market_cap_fill_ratio: `0.0`
- valuation_fill_ratio: `0.0`
- zero_turnover_ratio: `0.0007167174341515857`
- maximum_absolute_return_pct: `30.0`

## Source warnings

- primary_provider_unavailable: stock_zh_a_spot_em
- attempt_1: Push2RateLimitError: 东方财富 push2 行情服务器断开了连接，通常是短时间内请求过多，当前 IP 被临时限流。首次限流一般约 5 分钟后恢复，反复触发后可能需要 40 分钟以上；等待期间不要重复调用东方财富的行情接口，否则会延长限流。
- explicit_rate_limit_no_immediate_retry
- optional_source_unavailable
- volume_unit_source=SHARES; no lot multiplier applied
- unpriced_rows_not_confirmed_suspended=2
- unpriced_symbol_examples=002717.SZ,689009.SH

## Boundary

These files prove real A-share universe and market-snapshot ingestion. They are not yet stable Investment OS current outputs; FMDL-1D/E/F own hardening, scheduled publication and downstream promotion.
