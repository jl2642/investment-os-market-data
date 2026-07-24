# 股票投资助手｜总体开发方案与Current状态

- **版本**：`v1.5-single-repository`
- **日期**：2026-07-24
- **总体状态**：`WORK_PACKAGE_1_IN_PROGRESS`
- **当前批次**：`WP1-5B_READY`
- **仓库**：`jl2642/investment-os-market-data`
- **Runtime目录**：`investment_os_runtime/`
- **交易权限**：`NONE`

## 一、最终目标

形成完整闭环：

```text
数据与事实
→ 全市场筛选
→ Candidate治理
→ 深度研究与估值
→ 投资决策接口
→ 组合与调仓建议
→ 模拟盘和真实账户运营
→ 收益归因与复盘
→ 受控规则进化
```

系统不自动交易，用户是唯一投资决策人和交易执行人。

## 二、仓库架构

现有仓库同时承载：

- FMDL数据与技术Release；
- `investment_os_runtime/`下的规则、State、研究、决策、运营和恢复层。

职责通过目录、Schema、Manifest和晋级Gate隔离，不再新建第二个GitHub仓库。

## 三、七个工作包

| 工作包 | 名称 | 状态 |
|---|---|---|
| WP1 | Canonical审计、规则修复、资产融合与统一运营基线冻结 | IN_PROGRESS |
| WP2 | 当前状态刷新与运营激活 | PLANNED |
| WP3 | 长期稳健成长策略与Candidate重建 | PLANNED |
| WP4 | 深度研究、估值与Decision Interface | PLANNED |
| WP5 | 组合、模拟盘与真实账户决策融合 | PLANNED |
| WP6 | 标准运营节奏与事件驱动 | PLANNED |
| WP7 | 真实运营试点、最终验收与长期进化 | PLANNED |

## 四、WP1状态

| 步骤 | 状态 |
|---|---|
| WP1-1 资产盘点与审计快照 | COMPLETED_WITH_FINDINGS |
| WP1-1S Release 8取证补充 | COMPLETED |
| WP1-2 CORE_STATIC全量规则审计 | COMPLETED_WITH_FINDINGS |
| WP1-3 CORE与GitHub能力融合审计 | COMPLETED_WITH_FINDINGS |
| WP1-4 集中修复和目标Canonical设计 | COMPLETED |
| WP1-5A 控制与权威基础 | COMPLETED |
| WP1-5B 规则、Schema与State重建 | READY |
| WP1-5C Runtime、GitHub与运营接口融合 | PLANNED |
| WP1-5D 迁移、打包与File Library交付 | PLANNED |
| WP1-5E 自审、回放与晋级候选 | PLANNED |
| WP1-6 Clean-room独立验收 | PLANNED |

## 五、WP1-5A冻结结论

1. 使用单一GitHub仓库；
2. FMDL数据路径与Investment OS Runtime路径职责分离；
3. `股票投资助手_CURRENT.zip`必须是完整运行Canonical；
4. 小型恢复胶囊使用独立文件名；
5. Release 8永久保留为历史完整基线；
6. 原始券商截图、账号、凭证和无关个人信息不进入GitHub；
7. 结构化持仓、成本、Candidate和决策状态可按Schema保存；
8. 任何数据或定时任务均不得静默修改投资状态；
9. `trade_authority = NONE`。

## 六、下一任务

`WP1-5B｜规则、Schema与State重建`

WP1-5B只允许重建结构和迁移既有LKG，不允许改变真实持仓、模拟交易或Candidate成员。
