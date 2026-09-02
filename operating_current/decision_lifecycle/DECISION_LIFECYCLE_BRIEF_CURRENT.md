# 股票投资助手｜Decision Lifecycle Watch CURRENT

- 数据水位：`2026-09-01`
- Thesis subjects：`25`
- 持仓 / 非持仓：`22 / 3`
- 当前复核队列：`6`
- 需要重新D2：`4`
- 需要用户动作复核：`1`
- 组合风险复核：`1`
- 自动交易：`false`；Orders：`0`；trade_authority：`NONE`

## 当前复核队列

- **标普500ETF国泰 (159612.SZ)** — `USER_ACTION_REVIEW` / `HIGH`：Current decision-grade holding action is TRIM. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **长江电力 (600900.SH)** — `REUNDERWRITE_REQUIRED` / `HIGH`：Latest price 28.4000 has exhausted the current valuation margin; mark-to-weighted-value expected return is 2.82%. 下一步：`FRESH_D2_FOR_HOLD_TRIM_OR_EXIT`。
- **中国海油 (600938.SH)** — `REUNDERWRITE_REQUIRED` / `HIGH`：Latest price 34.5100 has exhausted the current valuation margin; mark-to-weighted-value expected return is 4.32%. 下一步：`FRESH_D2_FOR_HOLD_TRIM_OR_EXIT`。
- **中国移动 (600941.SH)** — `REUNDERWRITE_REQUIRED` / `HIGH`：Latest price 99.8900 has exhausted the current valuation margin; mark-to-weighted-value expected return is 3.61%. 下一步：`FRESH_D2_FOR_HOLD_TRIM_OR_EXIT`。
- **紫金矿业 (601899.SH)** — `REUNDERWRITE_REQUIRED` / `HIGH`：Latest price 33.7300 has exhausted the current valuation margin; mark-to-weighted-value expected return is 4.51%. 下一步：`FRESH_D2_FOR_HOLD_TRIM_OR_EXIT`。
- **九丰能源 (605090.SH)** — `PORTFOLIO_REVIEW_REQUIRED` / `HIGH`：Current account weight is at/above the governed 15% concentration flag. 下一步：`PHASE3_TARGET_WEIGHT_AND_SIZING_REVIEW`。

## 语义触发边界

- Catalyst / kill-thesis 只登记监控条款；GitHub 不做关键词推断。
- 价格条件命中只会要求重新D2；不得直接转换成BUY/ADD。
- 浮亏本身不是卖出条件；TRIM/EXIT 必须来自当前 decision-grade Recommendation。
