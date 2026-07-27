# 股票投资助手｜Capability Reality Matrix CURRENT

- 状态日期：2026-07-27
- 当前阶段：`R6_PRODUCTION_ACCEPTANCE_IN_PROGRESS_CURRENT_IF_PRESENT_ON_MAIN`
- 下一阶段：`完成完整自然月验收后进入正式运营与持续迭代`
- Operating Activation：`false`
- 交易权限：`NONE`
- 收益归因成熟度：`DEVELOPMENT_PRODUCT_COMPLETE_PRODUCTION_WINDOWS_PENDING`

| 能力 | 当前真实成熟度 | 已完成 | 关键剩余缺口 |
|---|---|---|---|
| 权威规则与恢复 | 高 | Product Charter、Master Plan、Execution Register、Clean-Room和故障注入 | File Library自动晋级与生产恢复仍待R6 |
| 真实账户Current | 中高 | 7个持仓、行情/NAV、用户Delta接口、结构与动作开发产品 | 无券商连接；完整自然月连续性未验收 |
| 模拟盘Current | 中高 | 16个持仓、成本、现金、动作矩阵和账户P&L桥接 | 完整交易/费用日历与自然月归因待R6 |
| A股全市场 | 高 | 5,530只Canonical普通A股范围和持续筛选能力 | 长期生产稳定性待R6 |
| Candidate引擎 | 中 | 2 Core、38 Shadow、33 Research Queue、Entry Baseline和20/60/120引擎 | 观察窗口未成熟，0 Ready，不得声称Alpha |
| 公司研究 | 中高 | 当前真实及模拟持仓7/7与16/16具备统一决策覆盖 | Candidate广泛深研仍需按优先级持续推进 |
| 组合构建与动作 | 中高 | 风险袖套、参考架构、23仓动作矩阵与开发决策场景 | 需R6基于届时Current重新生成Live决策包 |
| 周期运营产品 | 中高 | 统一状态、日/周/月/季/年及事件共7类合同与样例 | Schedule、连续运行和故障重跑未激活 |
| 收益归因 | 中高 | 7层合同、7+16当前贡献、模拟盘P&L桥接、8项校准提案 | 时点、期间现金和Candidate窗口需自然月数据 |
| 自动交易 | 永久不提供 | 用户最终决策和执行权已冻结 | 不适用 |

## 当前可以依赖

- 查询并恢复真实账户、模拟盘、Candidate及其数据水位；
- 分析当前个股和袖套的开放式Mark-to-Cost贡献；
- 解释模拟盘账户P&L与当前持仓未实现P&L之间的差异；
- 在输入不足时显示`BLOCKED`，不制造期间收益、Alpha或交易建议；
- 形成规则校准Proposal，但不自动应用。

## 当前不能依赖

- 不能把当前开放式未实现盈亏当作月度、年度或经现金流调整的总收益；
- 不能计算缺少交易Ledger的严格时点Alpha；
- 不能声称Candidate已经证明20/60/120日Alpha；
- 不能认为日报、周报和归因已经完成自然月生产验收；
- 不能自动改变规则、Candidate、持仓或订单。

## R6生产验收边界

- 已完成：R5 main晋级、R6验收合同、职责矩阵、观察Ledger、恢复重跑计划及Activation Gate安装。
- 尚未完成：`2026-08-01`至`2026-08-31`完整自然月运行、月末归因、跨对话恢复及漏跑重跑实证。
- 当前运行模式是监督式生产验收，不是已激活的无人值守生产。
- R6通过后系统自主完成研究、公开数据刷新、报告、归因和Proposal；用户继续负责真实账户Delta、关键约束、状态变更批准和交易执行。
