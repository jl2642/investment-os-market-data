# 股票投资助手｜Decision Lifecycle Watch CURRENT

- 数据水位：`2026-11-23`
- Thesis subjects：`66`
- 持仓 / 非持仓：`23 / 43`
- 当前复核队列：`14`
- 需要重新D2：`5`
- 需要用户动作复核：`7`
- 组合风险复核：`2`
- 自动交易：`false`；Orders：`0`；trade_authority：`NONE`

## 当前复核队列

- **美的集团 (000333.SZ)** — `REUNDERWRITE_REQUIRED` / `HIGH`：Latest price 94.1300 has exhausted the current valuation margin; mark-to-weighted-value expected return is 3.10%. 下一步：`FRESH_D2_FOR_HOLD_TRIM_OR_EXIT`。
- **兰州银行 (001227.SZ)** — `USER_ACTION_REVIEW` / `HIGH`：Current decision-grade new-capital action is BUY. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **富国天利增长债券C (017534.OF)** — `PORTFOLIO_REVIEW_REQUIRED` / `HIGH`：Current account weight is at/above the governed 15% concentration flag. 下一步：`PHASE3_TARGET_WEIGHT_AND_SIZING_REVIEW`。
- **中科环保 (301175.SZ)** — `REUNDERWRITE_REQUIRED` / `HIGH`：Latest price 5.4300 is at/below formal buy hurdle 5.5682; fresh D2 must revalidate valuation, bear downside and thesis. 下一步：`FRESH_D2_BEFORE_ANY_BUY`。
- **招商银行 (600036.SH)** — `REUNDERWRITE_REQUIRED` / `HIGH`：Latest price 43.2600 has exhausted the current valuation margin; mark-to-weighted-value expected return is 4.02%. 下一步：`FRESH_D2_FOR_HOLD_TRIM_OR_EXIT`。
- **国电南瑞 (600406.SH)** — `USER_ACTION_REVIEW` / `HIGH`：Current decision-grade holding action is TRIM. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **海尔智家 (600690.SH)** — `REUNDERWRITE_REQUIRED` / `HIGH`：Latest price 22.7200 has exhausted the current valuation margin; mark-to-weighted-value expected return is 3.43%. 下一步：`FRESH_D2_FOR_HOLD_TRIM_OR_EXIT`。
- **长江电力 (600900.SH)** — `USER_ACTION_REVIEW` / `HIGH`：Current decision-grade holding action is TRIM. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **中国移动 (600941.SH)** — `USER_ACTION_REVIEW` / `HIGH`：Current decision-grade holding action is TRIM. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **九丰能源 (605090.SH)** — `PORTFOLIO_REVIEW_REQUIRED` / `HIGH`：Current account weight is at/above the governed 15% concentration flag. 下一步：`PHASE3_TARGET_WEIGHT_AND_SIZING_REVIEW`。
- **招商安泰债券A (217003.OF)** — `REUNDERWRITE_REQUIRED` / `MEDIUM_HIGH`：Holding price 1.3601 is at/below research entry threshold 1.3700. 下一步：`FRESH_D2_AND_PORTFOLIO_FIT_BEFORE_ADD`。
- **汇川技术 (300124.SZ)** — `USER_ACTION_REVIEW` / `MEDIUM_HIGH`：Current decision-grade holding action is ADD. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **万华化学 (600309.SH)** — `USER_ACTION_REVIEW` / `MEDIUM_HIGH`：Current decision-grade holding action is ADD. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **工业富联 (601138.SH)** — `USER_ACTION_REVIEW` / `MEDIUM_HIGH`：Current decision-grade holding action is ADD. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。

## 语义触发边界

- Catalyst / kill-thesis 只登记监控条款；GitHub 不做关键词推断。
- 价格条件命中只会要求重新D2；不得直接转换成BUY/ADD。
- 浮亏本身不是卖出条件；TRIM/EXIT 必须来自当前 decision-grade Recommendation。
