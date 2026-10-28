# 股票投资助手｜Decision Lifecycle Watch CURRENT

- 数据水位：`2026-10-27`
- Thesis subjects：`51`
- 持仓 / 非持仓：`23 / 28`
- 当前复核队列：`16`
- 需要重新D2：`4`
- 需要用户动作复核：`10`
- 组合风险复核：`2`
- 自动交易：`false`；Orders：`0`；trade_authority：`NONE`

## 当前复核队列

- **兰州银行 (001227.SZ)** — `USER_ACTION_REVIEW` / `HIGH`：Current decision-grade new-capital action is BUY. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **富国天利增长债券C (017534.OF)** — `PORTFOLIO_REVIEW_REQUIRED` / `HIGH`：Current account weight is at/above the governed 15% concentration flag. 下一步：`PHASE3_TARGET_WEIGHT_AND_SIZING_REVIEW`。
- **中科环保 (301175.SZ)** — `USER_ACTION_REVIEW` / `HIGH`：Current decision-grade new-capital action is BUY. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **招商银行 (600036.SH)** — `REUNDERWRITE_REQUIRED` / `HIGH`：Latest price 42.9900 has exhausted the current valuation margin; mark-to-weighted-value expected return is 4.68%. 下一步：`FRESH_D2_FOR_HOLD_TRIM_OR_EXIT`。
- **国电南瑞 (600406.SH)** — `REUNDERWRITE_REQUIRED` / `HIGH`：Latest price 23.4800 has exhausted the current valuation margin; mark-to-weighted-value expected return is 2.64%. 下一步：`FRESH_D2_FOR_HOLD_TRIM_OR_EXIT`。
- **中远海特 (600428.SH)** — `USER_ACTION_REVIEW` / `HIGH`：Current decision-grade new-capital action is BUY. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **长江电力 (600900.SH)** — `REUNDERWRITE_REQUIRED` / `HIGH`：Latest price 29.8300 has exhausted the current valuation margin; mark-to-weighted-value expected return is 4.07%. 下一步：`FRESH_D2_FOR_HOLD_TRIM_OR_EXIT`。
- **中国海油 (600938.SH)** — `REUNDERWRITE_REQUIRED` / `HIGH`：Latest price 35.2600 has exhausted the current valuation margin; mark-to-weighted-value expected return is 2.10%. 下一步：`FRESH_D2_FOR_HOLD_TRIM_OR_EXIT`。
- **中国移动 (600941.SH)** — `USER_ACTION_REVIEW` / `HIGH`：Current decision-grade holding action is TRIM. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **江河集团 (601886.SH)** — `USER_ACTION_REVIEW` / `HIGH`：Current decision-grade new-capital action is BUY. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **甬金股份 (603995.SH)** — `USER_ACTION_REVIEW` / `HIGH`：Current decision-grade new-capital action is BUY. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **九丰能源 (605090.SH)** — `PORTFOLIO_REVIEW_REQUIRED` / `HIGH`：Current account weight is at/above the governed 15% concentration flag. 下一步：`PHASE3_TARGET_WEIGHT_AND_SIZING_REVIEW`。
- **汇川技术 (300124.SZ)** — `USER_ACTION_REVIEW` / `MEDIUM_HIGH`：Current decision-grade holding action is ADD. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **万华化学 (600309.SH)** — `USER_ACTION_REVIEW` / `MEDIUM_HIGH`：Current decision-grade holding action is ADD. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **福耀玻璃 (600660.SH)** — `USER_ACTION_REVIEW` / `MEDIUM_HIGH`：Current decision-grade holding action is ADD. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。
- **工业富联 (601138.SH)** — `USER_ACTION_REVIEW` / `MEDIUM_HIGH`：Current decision-grade holding action is ADD. 下一步：`PORTFOLIO_AND_EXECUTION_VALIDATION`。

## 语义触发边界

- Catalyst / kill-thesis 只登记监控条款；GitHub 不做关键词推断。
- 价格条件命中只会要求重新D2；不得直接转换成BUY/ADD。
- 浮亏本身不是卖出条件；TRIM/EXIT 必须来自当前 decision-grade Recommendation。
