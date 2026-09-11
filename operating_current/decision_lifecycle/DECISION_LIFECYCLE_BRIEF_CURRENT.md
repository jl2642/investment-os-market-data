# 股票投资助手｜Decision Lifecycle Watch CURRENT

- 数据水位：`2026-09-10`
- Thesis subjects：`30`
- 持仓 / 非持仓：`22 / 8`
- 当前复核队列：`7`
- 需要重新D2：`0`
- 需要用户动作复核：`6`
- 组合风险复核：`1`
- 自动交易：`false`；Orders：`0`；trade_authority：`NONE`

## 当前复核队列

- **江阴银行 (002807.SZ)** — `USER_ACTION_REVIEW` / `HIGH`：Current decision-grade new-capital action is BUY. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **中国移动 (600941.SH)** — `USER_ACTION_REVIEW` / `HIGH`：Current decision-grade holding action is TRIM. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **九丰能源 (605090.SH)** — `PORTFOLIO_REVIEW_REQUIRED` / `HIGH`：Current account weight is at/above the governed 15% concentration flag. 下一步：`PHASE3_TARGET_WEIGHT_AND_SIZING_REVIEW`。
- **华测检测 (300012.SZ)** — `USER_ACTION_REVIEW` / `MEDIUM_HIGH`：Current decision-grade holding action is ADD. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **汇川技术 (300124.SZ)** — `USER_ACTION_REVIEW` / `MEDIUM_HIGH`：Current decision-grade holding action is ADD. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **宁德时代 (300750.SZ)** — `USER_ACTION_REVIEW` / `MEDIUM_HIGH`：Current decision-grade holding action is ADD. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **恒瑞医药 (600276.SH)** — `USER_ACTION_REVIEW` / `MEDIUM_HIGH`：Current decision-grade holding action is ADD. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。

## 语义触发边界

- Catalyst / kill-thesis 只登记监控条款；GitHub 不做关键词推断。
- 价格条件命中只会要求重新D2；不得直接转换成BUY/ADD。
- 浮亏本身不是卖出条件；TRIM/EXIT 必须来自当前 decision-grade Recommendation。
