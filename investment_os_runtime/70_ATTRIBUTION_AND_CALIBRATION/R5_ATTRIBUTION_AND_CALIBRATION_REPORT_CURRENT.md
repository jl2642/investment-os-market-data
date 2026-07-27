# 股票投资助手｜R5 Attribution & Calibration Report CURRENT

- 状态：`DEVELOPMENT_PRODUCT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN_NO_ACTIVATION`
- 数据水位：`2026-07-24_CLOSE`
- 持仓连续性：仅确认至`2026-07-24`
- 归因口径：当前持仓按记录成本的开放式贡献 + 模拟盘账户P&L桥接
- Operating Activation：`false`
- Rule Mutations：`0`
- Orders：`0`
- trade_authority：`NONE`

## 一、管理层结论

1. **模拟盘在当前水位并非亏损。** 账户总资产为¥1,007,938.48，相对原始资金的账户总P&L为¥7,938.48。
2. 当前持仓开放式未实现贡献为¥16,388.90，但账户总P&L仅为¥7,938.48，两者之间存在¥-8,450.42的已平仓、费用及其他残差。只看当前持仓会高估系统实际效果。
3. 组合层面的主要问题不是全部袖套失控，而是**成长创新组内部选股与进入价格**，以及中证500卫星的负贡献。
4. 真实账户当前按记录成本的开放式损益为¥-1,326.74，主要拖累来自中证500和A500；债基与标普500敞口形成部分对冲。
5. Candidate只有2个合格Entry Baseline，20/60/120日窗口均未成熟，当前不得声称Candidate已经证明Alpha。
6. R5形成8项校准提案，但全部为`PROPOSED_NOT_APPLIED`；不得自动改规则、持仓、Candidate或订单。

## 二、事实｜账户与收益桥接

### 真实账户

- 持仓市值：¥451,056.24
- 执行现金：¥120.49
- 总资产：¥451,176.73
- 持仓记录成本：¥452,382.98
- 当前开放式Mark-to-Cost损益：¥-1,326.74
- **限制：** 缺少完整期间期初水位、外部资金流、分红费用及已实现盈亏Ledger，因此这不是经验证的期间总收益。

### 模拟盘

- 原始资金：¥1,000,000.00
- 持仓市值：¥788,404.50
- 研究现金：¥219,533.98
- 总资产：¥1,007,938.48
- 账户总P&L：¥7,938.48
- 当前持仓未实现P&L：¥16,388.90
- 已平仓、费用及其他残差：¥-8,450.42
- 桥接：¥16,388.90 + ¥-8,450.42 = ¥7,938.48

## 三、个股层归因

### 模拟盘主要正贡献

- `600938.SH` 中国海油：¥10,170.00，当前权重5.70%。
- `600660.SH` 福耀玻璃：¥9,280.00，当前权重8.84%。
- `600036.SH` 招商银行：¥6,048.00，当前权重6.22%。
- `000333.SZ` 美的集团：¥5,696.00，当前权重6.71%。
- `600941.SH` 中国移动：¥5,404.00，当前权重6.58%。

### 模拟盘主要负贡献

- `601138.SH` 工业富联：¥-10,098.00，当前权重3.59%。
- `300124.SZ` 汇川技术：¥-7,868.00，当前权重2.36%。
- `300750.SZ` 宁德时代：¥-6,925.00，当前权重3.80%。
- `510500.SH` 南方中证500ETF：¥-5,190.10，当前权重5.31%。
- `002463.SZ` 沪电股份：¥-4,050.00，当前权重2.23%。

### 真实账户主要正贡献

- `017534.OF` 富国天利增长债券C：¥3,232.96，当前权重25.23%。
- `159655.SZ` 标普500ETF华夏：¥2,666.80，当前权重4.76%。
- `159612.SZ` 标普500ETF国泰：¥1,734.00，当前权重4.44%。
- `217003.OF` 招商安泰债券A：¥717.32，当前权重22.32%。
- `110017.OF` 易方达增强回报债券A：¥277.18，当前权重22.23%。

### 真实账户主要负贡献

- `510500.SH` 南方中证500ETF：¥-7,212.70，当前权重13.21%。
- `159352.SZ` 南方中证A500ETF：¥-2,742.30，当前权重7.78%。
- `110017.OF` 易方达增强回报债券A：¥277.18，当前权重22.23%。
- `217003.OF` 招商安泰债券A：¥717.32，当前权重22.32%。
- `159612.SZ` 标普500ETF国泰：¥1,734.00，当前权重4.44%。

## 四、袖套层归因

| 模拟盘袖套 | 当前权重 | 当前开放式贡献 |
|---|---:|---:|
| quality_core | 25.65% | ¥23,526.00 |
| cyclical_resource | 13.95% | ¥13,638.00 |
| defensive_dividend | 17.09% | ¥10,812.00 |
| research_cash | 21.78% | ¥0.00 |
| benchmark_satellite | 5.31% | ¥-5,190.10 |
| growth_innovation | 16.21% | ¥-26,397.00 |

所有模拟盘袖套仍处于R2设定区间。当前证据支持的是：优先解决成长创新组内部选股、估值和进入时点问题，而不是推倒重建整个组合。

## 五、仓位、时点与现金

- **仓位层：** 当前权重和贡献可以观察，但缺少逐时点参考权重与反事实组合，不能计算严格的Sizing Alpha。
- **时点层：** 缺少完整交易Ledger、决策时间戳和日频基线，Entry/Exit/Rebalance Timing全部`BLOCKED`。
- **现金层：** 真实账户现金仅为执行余额；模拟盘21.78%研究现金位于R2的15%–25%区间。没有期间现金序列时，不计算现金拖累或贡献。

## 六、Candidate归因

- Core：`2`
- Shadow：`38`
- Research Queue：`33`
- Ready：`0`
- 合格Entry Baseline：`2`
- 成熟20/60/120日窗口：`0`

结论：`BLOCKED_WINDOWS_NOT_MATURE`。当前不得以旧Proxy收益、单一水位或模拟盘重合度替代正式Candidate Alpha评价。

## 七、策略校准提案

1. **Current-state and completed-close gate**：Require fresh completed-close marks and explicit user zero-Delta or transaction Delta before any live action or period attribution. 状态：`PROPOSED_NOT_APPLIED`。
2. **Simulation P&L bridge is mandatory**：Every review must bridge open unrealized P&L to account P&L through realized, fee and other ledger effects; never force equality. 状态：`PROPOSED_NOT_APPLIED`。
3. **Snapshot contribution is not period return**：Label snapshot contribution separately and block monthly or annual return claims until a reconciled period ledger exists. 状态：`PROPOSED_NOT_APPLIED`。
4. **Diagnose sleeve internals before portfolio overhaul**：Review security selection and entry quality inside a sleeve before changing the entire sleeve architecture. 状态：`PROPOSED_NOT_APPLIED`。
5. **No-add and hard-review controls remain binding**：Do not add merely because a position is below cost; require thesis, cash-flow, valuation and portfolio-fit evidence. 状态：`PROPOSED_NOT_APPLIED`。
6. **Candidate Alpha claims require mature windows**：Keep Alpha claims blocked and preserve Candidate membership until governed windows mature and reconcile to benchmarks. 状态：`PROPOSED_NOT_APPLIED`。
7. **Real-account cash remains execution balance**：Exclude external liquidity from allocation and do not create a fixed strategic cash target for the Real account. 状态：`PROPOSED_NOT_APPLIED`。
8. **No single snapshot may mutate strategy rules**：Require repeated observations, failure classification, regression tests and explicit user approval before applying a rule change. 状态：`PROPOSED_NOT_APPLIED`。

## 八、R6输入要求

R6生产验收必须补齐并连续验证：

- 完整自然月期初与期末水位；
- 每笔交易、分红、费用和外部资金流；
- 日频持仓、价格、基金净值、现金与Benchmark；
- Candidate 20/60/120日成熟窗口；
- 月报和年报中的R5归因嵌入；
- 故障重跑、跨对话恢复与零越权交易。

R5完成的是归因合同、当前水位诊断、Fail-Closed边界和校准提案机制。R6完成前，系统仍不得宣称已生产化。
