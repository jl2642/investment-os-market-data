# FMDL-1B/C Candidate Data Report

- Run ID: `FMDL1BC_20261106T002008+0800`
- As-of date: `2026-11-05`
- Generated at: `2026-11-06T00:20:08+08:00`
- Market-wide source: `stock_zh_a_spot_em`
- Universe QA: `PASS_WITH_WARNINGS` / `DEGRADED`
- Snapshot QA: `PASS` / `READY`
- Promotion state: `CANDIDATE_ONLY`

## Universe metrics

- row_count: `5927`
- duplicate_count: `0`
- symbol_valid_ratio: `1.0`
- identity_fill_ratio: `1.0`
- industry_fill_ratio: `0.5500253079129408`
- listing_date_fill_ratio: `0.5500253079129408`
- lkg_row_ratio: `1.0627577550654475`

## Snapshot metrics

- row_count: `5927`
- universe_coverage_ratio: `1.0`
- traded_row_count: `5573`
- positive_close_ratio_for_traded_rows: `1.0`
- negative_volume_rows: `0`
- negative_turnover_rows: `0`
- maximum_return_reconciliation_difference_pp: `0.005000000000004334`
- market_cap_fill_ratio: `0.9421292390754176`
- valuation_fill_ratio: `0.9414543613969968`
- zero_turnover_ratio: `0.060064113379449974`
- maximum_absolute_return_pct: `29.99`

## Source warnings

- attempt_1: ConnectionError: HTTPSConnectionPool(host='query.sse.com.cn', port=443): Max retries exceeded with url: /sseQuery/commonQuery.do?STOCK_TYPE=1&REG_PROVINCE=&CSRC_CODE=&STOCK_CODE=&sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L&COMPANY_STATUS=2%2C4%2C5%2C7%2C8&type=inParams&isPagination=true&pageHelp.cacheSize=1&pageHelp.beginPage=1&pageHelp.pageSize=10000&pageHelp.pageNo=1&pageHelp.endPage=1 (Caused by NewConnectionError("HTTPSConnection(host='query.sse.com.cn', port=443): Failed to establish a new connection: [Errno 101] Network is unreachable"))
- attempt_2: ConnectionError: HTTPSConnectionPool(host='query.sse.com.cn', port=443): Max retries exceeded with url: /sseQuery/commonQuery.do?STOCK_TYPE=1&REG_PROVINCE=&CSRC_CODE=&STOCK_CODE=&sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L&COMPANY_STATUS=2%2C4%2C5%2C7%2C8&type=inParams&isPagination=true&pageHelp.cacheSize=1&pageHelp.beginPage=1&pageHelp.pageSize=10000&pageHelp.pageNo=1&pageHelp.endPage=1 (Caused by NewConnectionError("HTTPSConnection(host='query.sse.com.cn', port=443): Failed to establish a new connection: [Errno 101] Network is unreachable"))
- attempt_3: ConnectionError: HTTPSConnectionPool(host='query.sse.com.cn', port=443): Max retries exceeded with url: /sseQuery/commonQuery.do?STOCK_TYPE=1&REG_PROVINCE=&CSRC_CODE=&STOCK_CODE=&sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L&COMPANY_STATUS=2%2C4%2C5%2C7%2C8&type=inParams&isPagination=true&pageHelp.cacheSize=1&pageHelp.beginPage=1&pageHelp.pageSize=10000&pageHelp.pageNo=1&pageHelp.endPage=1 (Caused by NewConnectionError("HTTPSConnection(host='query.sse.com.cn', port=443): Failed to establish a new connection: [Errno 101] Network is unreachable"))
- optional_source_unavailable
- attempt_1: ConnectionError: HTTPSConnectionPool(host='query.sse.com.cn', port=443): Max retries exceeded with url: /sseQuery/commonQuery.do?STOCK_TYPE=8&REG_PROVINCE=&CSRC_CODE=&STOCK_CODE=&sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L&COMPANY_STATUS=2%2C4%2C5%2C7%2C8&type=inParams&isPagination=true&pageHelp.cacheSize=1&pageHelp.beginPage=1&pageHelp.pageSize=10000&pageHelp.pageNo=1&pageHelp.endPage=1 (Caused by NewConnectionError("HTTPSConnection(host='query.sse.com.cn', port=443): Failed to establish a new connection: [Errno 101] Network is unreachable"))
- attempt_2: ConnectionError: HTTPSConnectionPool(host='query.sse.com.cn', port=443): Max retries exceeded with url: /sseQuery/commonQuery.do?STOCK_TYPE=8&REG_PROVINCE=&CSRC_CODE=&STOCK_CODE=&sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L&COMPANY_STATUS=2%2C4%2C5%2C7%2C8&type=inParams&isPagination=true&pageHelp.cacheSize=1&pageHelp.beginPage=1&pageHelp.pageSize=10000&pageHelp.pageNo=1&pageHelp.endPage=1 (Caused by NewConnectionError("HTTPSConnection(host='query.sse.com.cn', port=443): Failed to establish a new connection: [Errno 101] Network is unreachable"))
- attempt_3: ConnectionError: HTTPSConnectionPool(host='query.sse.com.cn', port=443): Max retries exceeded with url: /sseQuery/commonQuery.do?STOCK_TYPE=8&REG_PROVINCE=&CSRC_CODE=&STOCK_CODE=&sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L&COMPANY_STATUS=2%2C4%2C5%2C7%2C8&type=inParams&isPagination=true&pageHelp.cacheSize=1&pageHelp.beginPage=1&pageHelp.pageSize=10000&pageHelp.pageNo=1&pageHelp.endPage=1 (Caused by NewConnectionError("HTTPSConnection(host='query.sse.com.cn', port=443): Failed to establish a new connection: [Errno 101] Network is unreachable"))
- optional_source_unavailable

## Boundary

These files prove real A-share universe and market-snapshot ingestion. They are not yet stable Investment OS current outputs; FMDL-1D/E/F own hardening, scheduled publication and downstream promotion.
