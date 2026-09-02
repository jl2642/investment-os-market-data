# 股票投资助手｜Decision Lifecycle Watch CURRENT

- 数据水位：`2026-09-02`
- Thesis subjects：`25`
- 持仓 / 非持仓：`22 / 3`
- 当前复核队列：`4`
- 需要重新D2：`2`
- 需要用户动作复核：`1`
- 组合风险复核：`1`
- 自动交易：`false`；Orders：`0`；trade_authority：`NONE`

## 当前复核队列

- **标普500ETF国泰 (159612.SZ)** — `USER_ACTION_REVIEW` / `HIGH`：Current decision-grade holding action is TRIM. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **长江电力 (600900.SH)** — `REUNDERWRITE_REQUIRED` / `HIGH`：Latest price 28.7200 has exhausted the current valuation margin; mark-to-weighted-value expected return is 1.67%. 下一步：`FRESH_D2_FOR_HOLD_TRIM_OR_EXIT`。
- **中国移动 (600941.SH)** — `REUNDERWRITE_REQUIRED` / `HIGH`：Latest price 100.8000 has exhausted the current valuation margin; mark-to-weighted-value expected return is 2.68%. 下一步：`FRESH_D2_FOR_HOLD_TRIM_OR_EXIT`。
- **九丰能源 (605090.SH)** — `PORTFOLIO_REVIEW_REQUIRED` / `HIGH`：Current account weight is at/above the governed 15% concentration flag. 下一步：`PHASE3_TARGET_WEIGHT_AND_SIZING_REVIEW`。

## 语义触发边界

- Catalyst / kill-thesis 只登记监控条款；GitHub 不做关键词推断。
- 价格条件命中只会要求重新D2；不得直接转换成BUY/ADD。
- 浮亏本身不是卖出条件；TRIM/EXIT 必须来自当前 decision-grade Recommendation。
