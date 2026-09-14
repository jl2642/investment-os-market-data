# 股票投资助手｜Decision Lifecycle Watch CURRENT

- 数据水位：`2026-09-14`
- Thesis subjects：`33`
- 持仓 / 非持仓：`22 / 11`
- 当前复核队列：`8`
- 需要重新D2：`2`
- 需要用户动作复核：`5`
- 组合风险复核：`1`
- 自动交易：`false`；Orders：`0`；trade_authority：`NONE`

## 当前复核队列

- **江阴银行 (002807.SZ)** — `USER_ACTION_REVIEW` / `HIGH`：Current decision-grade new-capital action is BUY. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **中国移动 (600941.SH)** — `USER_ACTION_REVIEW` / `HIGH`：Current decision-grade holding action is TRIM. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **九丰能源 (605090.SH)** — `PORTFOLIO_REVIEW_REQUIRED` / `HIGH`：Current account weight is at/above the governed 15% concentration flag. 下一步：`PHASE3_TARGET_WEIGHT_AND_SIZING_REVIEW`。
- **汇川技术 (300124.SZ)** — `USER_ACTION_REVIEW` / `MEDIUM_HIGH`：Current decision-grade holding action is ADD. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **宁德时代 (300750.SZ)** — `USER_ACTION_REVIEW` / `MEDIUM_HIGH`：Current decision-grade holding action is ADD. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **恒瑞医药 (600276.SH)** — `USER_ACTION_REVIEW` / `MEDIUM_HIGH`：Current decision-grade holding action is ADD. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **福耀玻璃 (600660.SH)** — `REUNDERWRITE_REQUIRED` / `MEDIUM_HIGH`：Holding price 53.8800 is at/below research entry threshold 54.0000. 下一步：`FRESH_D2_AND_PORTFOLIO_FIT_BEFORE_ADD`。
- **工业富联 (601138.SH)** — `REUNDERWRITE_REQUIRED` / `MEDIUM_HIGH`：Holding price 61.5700 is at/below research entry threshold 63.4600. 下一步：`FRESH_D2_AND_PORTFOLIO_FIT_BEFORE_ADD`。

## 语义触发边界

- Catalyst / kill-thesis 只登记监控条款；GitHub 不做关键词推断。
- 价格条件命中只会要求重新D2；不得直接转换成BUY/ADD。
- 浮亏本身不是卖出条件；TRIM/EXIT 必须来自当前 decision-grade Recommendation。
