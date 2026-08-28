# FMDL-1B/C Candidate Data Report

- Run ID: `FMDL1BC_20260828T171122+0800`
- As-of date: `2026-08-28`
- Generated at: `2026-08-28T17:11:22+08:00`
- Market-wide source: `stock_zh_a_spot`
- Universe QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Snapshot QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Promotion state: `CANDIDATE_ONLY`

## Universe metrics

- row_count: `5550`
- duplicate_count: `0`
- symbol_valid_ratio: `1.0`
- identity_fill_ratio: `1.0`
- industry_fill_ratio: `0.5830630630630631`
- listing_date_fill_ratio: `0.5830630630630631`
- lkg_row_ratio: `1.0019859180357464`

## Snapshot metrics

- row_count: `5550`
- universe_coverage_ratio: `1.0`
- traded_row_count: `5546`
- positive_close_ratio_for_traded_rows: `1.0`
- negative_volume_rows: `0`
- negative_turnover_rows: `0`
- maximum_return_reconciliation_difference_pp: `0.0004999999999999449`
- market_cap_fill_ratio: `0.0`
- valuation_fill_ratio: `0.0`
- zero_turnover_ratio: `0.0007207207207207207`
- maximum_absolute_return_pct: `126.81`

## Source warnings

- attempt_1: ConnectionError: HTTPSConnectionPool(host='query.sse.com.cn', port=443): Max retries exceeded with url: /sseQuery/commonQuery.do?STOCK_TYPE=1&REG_PROVINCE=&CSRC_CODE=&STOCK_CODE=&sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L&COMPANY_STATUS=2%2C4%2C5%2C7%2C8&type=inParams&isPagination=true&pageHelp.cacheSize=1&pageHelp.beginPage=1&pageHelp.pageSize=10000&pageHelp.pageNo=1&pageHelp.endPage=1 (Caused by NewConnectionError("HTTPSConnection(host='query.sse.com.cn', port=443): Failed to establish a new connection: [Errno 101] Network is unreachable"))
- attempt_2: ConnectionError: HTTPSConnectionPool(host='query.sse.com.cn', port=443): Max retries exceeded with url: /sseQuery/commonQuery.do?STOCK_TYPE=1&REG_PROVINCE=&CSRC_CODE=&STOCK_CODE=&sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L&COMPANY_STATUS=2%2C4%2C5%2C7%2C8&type=inParams&isPagination=true&pageHelp.cacheSize=1&pageHelp.beginPage=1&pageHelp.pageSize=10000&pageHelp.pageNo=1&pageHelp.endPage=1 (Caused by NewConnectionError("HTTPSConnection(host='query.sse.com.cn', port=443): Failed to establish a new connection: [Errno 101] Network is unreachable"))
- attempt_3: ConnectionError: HTTPSConnectionPool(host='query.sse.com.cn', port=443): Max retries exceeded with url: /sseQuery/commonQuery.do?STOCK_TYPE=1&REG_PROVINCE=&CSRC_CODE=&STOCK_CODE=&sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L&COMPANY_STATUS=2%2C4%2C5%2C7%2C8&type=inParams&isPagination=true&pageHelp.cacheSize=1&pageHelp.beginPage=1&pageHelp.pageSize=10000&pageHelp.pageNo=1&pageHelp.endPage=1 (Caused by NewConnectionError("HTTPSConnection(host='query.sse.com.cn', port=443): Failed to establish a new connection: [Errno 101] Network is unreachable"))
- optional_source_unavailable
- attempt_1: ConnectionError: HTTPSConnectionPool(host='query.sse.com.cn', port=443): Max retries exceeded with url: /sseQuery/commonQuery.do?STOCK_TYPE=8&REG_PROVINCE=&CSRC_CODE=&STOCK_CODE=&sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L&COMPANY_STATUS=2%2C4%2C5%2C7%2C8&type=inParams&isPagination=true&pageHelp.cacheSize=1&pageHelp.beginPage=1&pageHelp.pageSize=10000&pageHelp.pageNo=1&pageHelp.endPage=1 (Caused by NewConnectionError("HTTPSConnection(host='query.sse.com.cn', port=443): Failed to establish a new connection: [Errno 101] Network is unreachable"))
- attempt_2: ConnectionError: HTTPSConnectionPool(host='query.sse.com.cn', port=443): Max retries exceeded with url: /sseQuery/commonQuery.do?STOCK_TYPE=8&REG_PROVINCE=&CSRC_CODE=&STOCK_CODE=&sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L&COMPANY_STATUS=2%2C4%2C5%2C7%2C8&type=inParams&isPagination=true&pageHelp.cacheSize=1&pageHelp.beginPage=1&pageHelp.pageSize=10000&pageHelp.pageNo=1&pageHelp.endPage=1 (Caused by NewConnectionError("HTTPSConnection(host='query.sse.com.cn', port=443): Failed to establish a new connection: [Errno 101] Network is unreachable"))
- attempt_3: ConnectionError: HTTPSConnectionPool(host='query.sse.com.cn', port=443): Max retries exceeded with url: /sseQuery/commonQuery.do?STOCK_TYPE=8&REG_PROVINCE=&CSRC_CODE=&STOCK_CODE=&sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L&COMPANY_STATUS=2%2C4%2C5%2C7%2C8&type=inParams&isPagination=true&pageHelp.cacheSize=1&pageHelp.beginPage=1&pageHelp.pageSize=10000&pageHelp.pageNo=1&pageHelp.endPage=1 (Caused by NewConnectionError("HTTPSConnection(host='query.sse.com.cn', port=443): Failed to establish a new connection: [Errno 101] Network is unreachable"))
- optional_source_unavailable
- primary_provider_unavailable: stock_zh_a_spot_em
- attempt_1: ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- optional_source_unavailable
- volume_unit_source=SHARES; no lot multiplier applied
- source_zero_price_rows_classified_as_suspended=000635.SZ,000711.SZ,002274.SZ,002586.SZ

## Boundary

These files prove real A-share universe and market-snapshot ingestion. They are not yet stable Investment OS current outputs; FMDL-1D/E/F own hardening, scheduled publication and downstream promotion.
