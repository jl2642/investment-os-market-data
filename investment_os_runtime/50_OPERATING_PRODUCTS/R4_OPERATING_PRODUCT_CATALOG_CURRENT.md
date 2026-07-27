# 股票投资助手｜R4 Operating Product Catalog CURRENT

- 状态：`DEVELOPMENT_PRODUCT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN_NO_ACTIVATION`
- 来源PR：`#158`
- 时区：`Asia/Shanghai`
- 产品数量：`7`
- Operating Activation：`false`
- 下一阶段：`R5_ATTRIBUTION_AND_CALIBRATION_DEVELOPMENT_AFTER_R4_PRESENT_ON_MAIN`

| 产品 | 开发默认节奏 | 核心职责 |
|---|---|---|
| 统一运营状态页 | Whenever any upstream Current changes; no schedule is activated in R4 | Show authoritative watermarks, product readiness, blockers and the sole next operating step. |
| 日度运营简报 | Development default: trading days 23:15 Asia/Shanghai after portfolio/NAV refresh | Surface state changes, material events, abnormal moves, stale inputs and required follow-up without full attribution. |
| 周度组合与候选池审查 | Development default: Saturday 09:30 Asia/Shanghai after Friday close and NAV completion | Review sleeve drift, position exceptions, Candidate lifecycle changes and unresolved evidence gaps. |
| 月度投资复盘 | Development default: T+1 10:00 after month-end close, NAV and transaction continuity are complete | Provide portfolio performance, structural drift, decision history and a clearly separated R5 attribution placeholder. |
| 季度组合与候选池重估 | Development default: after quarter-end portfolio/NAV close and required financial refresh; target T+5 10:00 | Re-underwrite portfolio roles, financial evidence, valuation ranges and Candidate promotions or removals. |
| 年度策略复盘 | Development default: within the first ten trading days after year-end data completeness | Review annual portfolio outcomes, research process, Candidate conversion and strategy governance; R5 supplies final attribution. |
| 事件与异常警报 | On evidence ingest; development fallback is no more frequent than hourly when later activated | Classify material company, portfolio, market and data-quality events and route them to the correct review gate. |

## 产品边界

- R4只定义产品、输入、输出、门禁和开发样例；不激活Schedule。
- R5提供完整收益归因与策略校准。
- R6完成连续运行、恢复、重跑和正式激活验收。
- 任一关键输入过期时，产品必须显示`BLOCKED`及具体原因，不能用推测填充。
