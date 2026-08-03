# 股票投资助手｜R6 Production Acceptance Runbook CURRENT

## 1. 当前判断

R6已经启动，但不能在同一天宣称完成。完整生产验收至少需要一个完整自然月，即`2026-08-01`至`2026-08-31`，并在月末收盘、基金净值和交易/资金流Ledger齐备后完成最终验收。

## 2. 验收期运行顺序

1. 月初建立真实账户、模拟盘、Candidate、现金、交易和Benchmark基线；
2. 每个有效收盘周期检查市场数据、基金净值和用户Delta连续性；
3. 运行日度状态与异常检查；
4. 每周运行组合、Candidate和研究缺口审查；
5. 月中执行跨对话恢复、漏跑补跑和重复运行去重测试；
6. 月末冻结期末水位，完成期间收益、资金流和R5归因桥接；
7. 审计全部证据路径、状态变化及零越权记录；
8. 只有全部Checkpoint通过，才可将Operating Activation改为`true`。

## 3. 运营期产品节奏

- 日度：状态变化、重大事件、数据陈旧、风险触发和下一检查；
- 周度：袖套偏离、持仓例外、Candidate生命周期和研究优先级；
- 月度：期间收益、组合结构、逐仓复盘、Candidate结果和规则校准；
- 季度：财务、估值、组合角色和Candidate晋级/退出重估；
- 年度：策略绩效、研究质量、决策治理和规则升级。

## 4. 永久边界

R6完成也不会授予自动交易权限。系统可以自主搜集、分析、刷新、报告、归因和形成Proposal，但真实账户、模拟盘、Candidate、正式规则和订单的改变仍必须由用户明确批准。

## 5. P0-I1最低必要工作流接入

P0-I1不替换WP2-R行情与基金NAV刷新，也不新增行情刷新Schedule。`P0-I1 Operating Observation`在现有WP2-R工作流完成后运行：

1. 读取上游完成后的GitHub `main`；
2. 保存Canonical Run Manifest；
3. 上游成功时生成Real与Simulation不可变EOD快照；
4. 生成STATUS与DAILY观察产品及Report Manifest；
5. 将成功、失败、异常、重复运行和幂等键写入集中Operating Run Ledger；
6. 上游失败、持仓连续性落后或资产核对失败时显式降级或阻断；
7. 不修改持仓、Candidate、Decision、规则或订单。

PR中的临时测试结果不构成R6生产证据。只有合并后由真实WP2-R运行触发并写回`main`的观察记录，才可作为后续Checkpoint验收候选；Checkpoint仍需独立审查后晋级。
