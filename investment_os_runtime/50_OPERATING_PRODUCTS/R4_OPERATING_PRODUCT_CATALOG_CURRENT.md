# 股票投资助手｜R4 Operating Product Catalog CURRENT

- 状态：`DEVELOPMENT_PRODUCT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN_NO_ACTIVATION`
- 来源PR：`#158`
- 时区：`Asia/Shanghai`
- 产品数量：`7`
- Operating Activation：`false`
- 下一阶段：`R5_ATTRIBUTION_AND_CALIBRATION_DEVELOPMENT_AFTER_R4_PRESENT_ON_MAIN`
- 当前口径修订：`2026-08-13 USER_CONFIRMED_DAILY_SCOPE_PATCH`

| 产品 | 开发默认节奏 | 核心职责 |
|---|---|---|
| 统一运营状态页 | Whenever any upstream Current changes; no schedule is activated in R4 | Show authoritative watermarks, product readiness, blockers and the sole next operating step. |
| 日度运营简报 | Development default: trading days 23:15 Asia/Shanghai after portfolio/NAV refresh | Surface state changes, material events, abnormal moves, stale inputs and required follow-up without full attribution. |
| 周度组合与候选池审查 | Development default: Saturday 09:30 Asia/Shanghai after Friday close and NAV completion | Review sleeve drift, position exceptions, Candidate lifecycle changes and unresolved evidence gaps. |
| 月度投资复盘 | Development default: T+1 10:00 after month-end close, NAV and transaction continuity are complete | Provide portfolio performance, structural drift, decision history and a clearly separated R5 attribution placeholder. |
| 季度组合与候选池重估 | Development default: after quarter-end portfolio/NAV close and required financial refresh; target T+5 10:00 | Re-underwrite portfolio roles, financial evidence, valuation ranges and Candidate promotions or removals. |
| 年度策略复盘 | Development default: within the first ten trading days after year-end data completeness | Review annual portfolio outcomes, research process, Candidate conversion and strategy governance; R5 supplies final attribution. |
| 事件与异常警报 | On evidence ingest; development fallback is no more frequent than hourly when later activated | Classify material company, portfolio, market and data-quality events and route them to the correct review gate. |

## 日度持仓与估值范围

- 日度运营核心范围为真实证券账户中的股票、上市ETF/场内基金、其他可通过稳定公开行情取得当日价格的证券，以及模拟盘；这些资产用于日度表现、异常波动、持仓风险和动作建议。
- `AF5546`、`E10484`、`AB5609` 属于支付宝渠道的低频理财/资管资产，设为 `MANUAL_LOW_FREQUENCY`：不要求日度自动估值，不参与日度运营简报的完整性阻断，也不因未更新而把股票/ETF日度分析标记为 `BLOCKED`。
- 上述低频资产继续属于总投资资产范围；月末、季度末、年度复盘、家庭资产/投资收益核账，或用户主动提供新估值时，使用最近一次已确认值，并必须同时展示其实际估值日期。
- 日度组合收益率若未包含低频资产，必须明确标注分母为“日度监控资产”或等效表述；不得把局部日度收益率冒充全投资资产收益率。
- 公开净值可稳定取得但非交易核心的场外基金，可按披露周期低频刷新；其延迟不得阻塞股票/ETF日度运营，除非当期产品明确要求完整总资产估值。

## 产品边界

- R4只定义产品、输入、输出、门禁和开发样例；不激活Schedule。
- R5提供完整收益归因与策略校准。
- R6完成连续运行、恢复、重跑和正式激活验收。
- 仅“当期产品定义为关键”的输入过期时，产品才必须显示`BLOCKED`及具体原因；对日度运营而言，`MANUAL_LOW_FREQUENCY`资产不属于阻断性关键输入，不能用推测填充其估值。
