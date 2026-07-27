# WP2-R｜Recurring Portfolio Current

WP2-R把历史仓位、用户交易Delta和自动市场标记拆成三个独立层，再生成可供WP3-R、WP4-B和后续WP5消费的Position-level Current。

## 权威边界

- `USER_TRANSACTION_DELTA_LEDGER_CURRENT.json`是数量与成本变化的唯一增量入口；
- 只有`confirmation_authority=USER`且状态为`CONFIRMED_BY_USER`或`APPLIED_TO_POSITION_CURRENT`的Delta可改变仓位；
- 自动行情刷新只更新价格、净值、市值和浮动盈亏，不得改变数量、成本、Candidate或订单；
- 数据水位与Broker Verification永久分开；
- Broker未连接不阻断组合监控和Position-level Portfolio Fit，但阻断真实交易行动；
- `trade_authority=NONE`。

## 主要产品

- `REAL_ACCOUNT_POSITIONS_CURRENT.json`
- `SIMULATION_POSITIONS_CURRENT.json`
- `PORTFOLIO_MARKS_CURRENT.json`
- `PORTFOLIO_CURRENT_RUN_CURRENT.json`
- `WP2_R_PORTFOLIO_CURRENT_ACCEPTANCE_RECORD.json`

## 行情来源

- 上市证券：Sina公开跟踪报价；
- 公募基金：Eastmoney公开单位净值序列；
- 任一必需标的缺失、非正价格或过期时，刷新失败关闭，不把部分数据晋级为Current。

## 用户运营方式

用户只需在真实账户或模拟盘发生买入、卖出、转入、转出或成本调整时提供交易Delta。没有交易时，行情和净值由自动刷新流程维护，不要求用户每日上传截图。
