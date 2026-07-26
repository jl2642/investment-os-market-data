# 股票投资助手｜Work Package Master Plan CURRENT

- 状态日期：2026-07-26
- Canonical状态源：`investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json`
- 市场数据Current：`investment_os_runtime/50_MARKET_CAPABILITY_BINDINGS/A_SHARE_CURRENT.json`
- 交易权限：`NONE`

## 当前阶段

| Work Package | 状态 | 当前结论 |
|---|---|---|
| WP1 | COMPLETED | Canonical、规则、Runtime与独立Clean-Room验收完成 |
| WP2 | COMPLETED | 真实账户、模拟盘、历史Candidate与市场状态诊断完成；无交易变更 |
| WP3-1 | COMPLETED | 稳健成长策略、Candidate准入、生命周期、Entry Baseline与Research Readiness Gate完成 |
| WP3-2A | COMPLETED | 2026-07-24普通A股5530只Current已在main接受；定时刷新、有限重试、Lineage Gate v3、Proposal与受保护Acceptance已上线 |
| WP3-2B | ACTIVE / READY | 基于已接受Current形成Eligible Universe、Exclusions与Research Workload Queue；仅Proposal，不是投资排名 |
| WP3-3 | PLANNED | 多维筛选、行业Longlist与研究优先级，在WP3-2B人工验收后进入 |
| WP3-4 | PLANNED | 研究对象、Candidate重建与Entry Baseline补齐 |
| WP4–WP7 | PLANNED | 组合决策、运营、归因、复盘与持续校准 |

## WP3-2A运营模式

工作日定时运行：

```text
免费公开数据源抓取
→ 有限重试
→ 原始证据保存
→ 新交易日/重复Proposal判断
→ Gate v3
→ Runtime回归
→ 数据Proposal PR
→ 人工合并Proposal
→ 受保护Acceptance
→ 人工合并Current
```

同一交易日或已有未关闭Proposal时，运行必须以`NO_OP`成功结束，不得生成重复PR，不得创建阻断Issue。

未来Current晋级PR在被人工合并后即形成最终`ACCEPTED_ON_MAIN`状态，不再需要单独的运营收口PR。

## WP3-2B边界

WP3-2B只执行：

1. 全市场数据与流动性资格判断；
2. `ELIGIBLE_UNIVERSE.csv`；
3. `SCREENING_EXCLUSIONS.csv`；
4. 最多100行的`RESEARCH_WORKLOAD_QUEUE.csv`；
5. 可审计Manifest与证据Artifact。

WP3-2B明确不执行：

- 投资吸引力排名；
- 自动创建Research Object；
- Candidate准入、剔除或权重调整；
- 模拟盘或真实账户交易；
- 订单生成；
- 自动规则修改。

## 人工治理门禁

仅以下动作需要用户介入：

1. 合并受治理的数据或筛选Proposal PR；
2. 批准受保护Environment；
3. 合并最终Current或后续投资状态变更PR。

其余抓取、重试、测试、差异检查、Artifact和故障诊断由GitHub工作流与ChatGPT执行。
