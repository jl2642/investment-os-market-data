# 股票投资助手｜事件与异常警报（R4开发验收样例）

- 产品状态：`DEVELOPMENT_SAMPLE_NOT_LIVE`
- 样例日期：`2026-07-27`
- 决策数据水位：`2026-07-24_CLOSE`
- 持仓连续性：仅确认至`2026-07-24`
- Operating Activation：`false`
- Orders：`0`
- trade_authority：`NONE`

## Alert

- Alert ID：`R4-SAMPLE-DATA-FRESHNESS-001`
- Severity：`P1`
- 类型：`DATA_FRESHNESS_AND_POSITION_CONTINUITY`
- 影响范围：真实账户、模拟盘、R3动作矩阵及全部周期报告
- 证据：决策水位为2026-07-24收盘；持仓连续性仅确认至2026-07-24

## 影响判断

任何后续价格敏感结论、目标金额或实时动作均不得被标记为Current或Implementation Ready。

## 必需处理

在未来R6运营激活后，先刷新最新完整收盘和基金净值，再取得用户零Delta确认或交易Delta。

## 禁止事项

- 不得推断用户没有交易；
- 不得把盘中价当作收盘价；
- 不得创建订单；
- 不得将R3开发场景当成真实建议。
