# 股票投资助手｜Product Charter CURRENT

- 状态日期：2026-07-27
- 状态：`CURRENT_IF_PRESENT_ON_MAIN`
- 来源PR：`#152`
- 来源Head：`ee9cd9af5122af9506a0da844d837cfce6c57c44`
- 权威仓库：`jl2642/investment-os-market-data`
- 交易权限：`NONE`

## 1. 产品使命

股票投资助手的目标不是生成更多工程文件，而是形成一个可持续运行、证据可追溯、由用户最终决策的股票投资闭环：

`市场与公司数据 → 全市场筛选 → Candidate分层 → 深入研究与估值 → 组合构建 → 持仓动作建议 → 周期运营 → 收益归因与策略校准`

## 2. 用户最终产品

系统完成后必须稳定交付：

1. 真实账户Current、模拟盘Current及持仓连续性状态；
2. Candidate新增、升级、降级和退出原因；
3. 统一口径的公司研究、估值、组合角色和风险触发条件；
4. 覆盖全部持仓的增持、持有、减持、退出、观察或等待证据动作矩阵；
5. 日报、周报、月报、季报和年度策略复盘；
6. 个股、行业、仓位、时点、现金和规则层面的收益归因；
7. 用户批准后的受治理状态更新，但不自动下单。

## 3. 永久安全边界

- 不自动改变真实账户持仓；
- 不自动改变模拟盘持仓；
- 不自动改变Candidate成员；
- 不自动创建订单；
- 不从沉默推断用户没有交易；
- 不把盘中价格当作正式收盘价格；
- 不因存在现金而强制投资；
- 不在证据不足时强制生成买卖建议；
- `trade_authority=NONE`。

## 4. 权威顺序

1. 本Product Charter；
2. `WORK_PACKAGE_MASTER_PLAN_CURRENT.md`；
3. `EXECUTION_REGISTER_CURRENT.json`；
4. `AUTHORITATIVE_ASSET_REGISTRY.json`；
5. 各领域Canonical Current与验收记录；
6. GitHub受治理合并历史；
7. File Library中的明确晋级副本；
8. 对话记忆不具备权威性。

发生冲突时，必须停止推进并按上述顺序修复，不得临时发明新阶段。

## 5. 完成定义

Work Package完成必须同时满足：

- 功能和数据资产可用；
- 用户可读产品已交付；
- 输入、证据、限制和置信度明确；
- 对下游阶段的接口稳定；
- 安全边界和回归验收通过；
- Master Plan和Execution Register同步更新；
- 不得仅因JSON、Workflow、Schema或测试通过而宣称产品完成。

## 6. 阶段变更规则

- 只有Master Plan列出的阶段才可执行；
- 新阶段或拆分必须先修改Master Plan并经用户明确同意；
- PR标题、临时分支名和Execution Register中的临时Next Task不构成新阶段授权；
- 历史`WP5-A`至`WP5-G`仅作为执行标签保留，不再作为未来路线；
- `WP5-H`从未获得冻结授权，状态为`VOID_NOT_STARTED`。

## 7. 当前产品判断

当前系统是：

`具备较强数据治理、Candidate筛选和部分研究/组合控制能力的投资研究Beta`

当前系统不是：

`已经完成并稳定运行的全闭环投资决策系统`

R0之后的固定开发顺序为：

`R1 Decision Coverage Completion → R2 Portfolio Construction Synthesis → R3 Position Action Matrix & User Decision Pack → R4 Operating Products → R5 Attribution & Calibration → R6 Production Acceptance`
