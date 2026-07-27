# 股票投资助手｜Work Package Master Plan CURRENT

- 状态日期：2026-07-27
- 产品权威：`INVESTMENT_ASSISTANT_PRODUCT_CHARTER_CURRENT.md`
- Canonical状态源：`EXECUTION_REGISTER_CURRENT.json`
- 最新已完成main合并：PR #157 / `2fbcb84d7a23d5804975fd8319781464c2a18ab2`
- R0治理来源：PR #152 / `ee9cd9af5122af9506a0da844d837cfce6c57c44`
- 本轮状态：`CURRENT_IF_PRESENT_ON_MAIN`
- File Library：`RECOVERY_DISTRIBUTION_ONLY_PENDING_EXPLICIT_PROMOTION`
- 交易权限：`NONE`

## 一、固定产品架构

| Work Package | 产品职责 | 当前真实成熟度 |
|---|---|---|
| WP1 | 规则、Canonical、Schema、Runtime和恢复 | `COMPLETED` |
| WP2 | 真实账户、模拟盘、行情、基金净值和用户交易Delta | `CAPABILITY_ACCEPTED_OPERATING_HISTORY_NOT_YET_VALIDATED` |
| WP3 | 全市场筛选、Candidate生命周期和效果评价 | `ENGINE_ACCEPTED_OUTCOME_WINDOWS_INCOMPLETE` |
| WP4 | 公司研究、估值、组合适配和事件监控 | `METHOD_ACCEPTED_COVERAGE_PARTIAL` |
| WP5 | 组合构建、动作矩阵和用户决策包 | `USER_DECISION_PACK_READY_NO_IMPLEMENTATION` |
| WP6 | 日报、周报、月报、季报和年度运营产品 | `NOT_STARTED_AS_FORMAL_PRODUCT` |
| WP7 | 收益归因、决策复盘和策略校准 | `NOT_STARTED_AS_FORMAL_PRODUCT` |

## 二、截至R0的实际能力

- 真实账户：7个持仓Current；第一轮产品结构审查已完成；三只债基完整穿透未完成。
- 模拟盘：16个持仓Current；2只Core2和3只P0具备较高等级研究；其余11只缺统一决策级覆盖。
- Candidate：2只Core、38只Shadow、33只Research Queue、0只Ready。
- 全市场：5,530只A股Canonical范围；Candidate刷新能力已安装，但20/60/120日效果窗口未成熟。
- 用户决策：当前Ready为0；不存在已授权调仓或订单。

## 三、历史执行映射

| 历史PR/标签 | 实际交付 | 映射后的正式位置 |
|---|---|---|
| PR #141 | WP3 Research Objects、Entry Baseline和Candidate重建 | WP3已完成初始Candidate基线 |
| PR #143 | 美的、长江电力Core2初始研究和Decision Interface | WP4部分覆盖 |
| PR #144 | R1成熟度纠偏和缺口登记 | 历史审计，不是产品阶段 |
| PR #145–#146 | WP2-R、WP3-R、WP4-B能力补强及R2收口 | WP2–WP4能力硬化 |
| PR #147 / WP5-A–C | WP5启动、全持仓初审、P0研究准备 | WP5-1及WP5-2启动 |
| PR #148 / WP5-D | 汇川、宁德、工业富联P0重审 | WP5-2部分完成 |
| PR #149 / WP5-E | 完成收盘及条件动作门禁 | 横向运营控制，不是阶段 |
| PR #150 / WP5-F | 用户持仓连续性接口 | 横向数据控制，不是阶段 |
| PR #151 / WP5-G | 真实账户第一轮结构审查及晋级语义修复 | WP5-2部分完成 |
| WP5-H | 未经计划冻结的临时名称 | `VOID_NOT_STARTED` |

## 四、冻结后的有限开发路线

### R0｜Product Authority Freeze

- 状态：`COMPLETED_ON_MAIN`
- 交付：Product Charter、Master Plan、Capability Reality Matrix、Execution Register、User Operating Guide。
- 禁止：新研究、调仓、Candidate变化、订单和架构扩张。

### R1｜Decision Coverage Completion

- 状态：`COMPLETED_ON_MAIN`；来源PR：`#153`。

- 刷新2只Core2和3只P0，不从头重建；
- 补齐其余11只模拟盘持仓的基本面、估值、组合角色和退出条件；
- 完成三只债基穿透、两只标普500ETF执行质量比较及A500/中证500角色确认；
- 交付全部当前持仓的统一Decision Coverage Pack。

### R2｜Portfolio Construction Synthesis

- 状态：`COMPLETED_ON_MAIN`；来源PR：`#154`。


- 汇总真实账户和模拟盘的风险袖套、行业/风格暴露、集中度、重复暴露、现金用途和替代关系；
- 形成核心—卫星结构和新资金优先顺序；
- 回答“为什么这些资产应当放在同一个组合中”。

### R3｜Position Action Matrix & User Decision Pack

- 状态：`CURRENT_IF_PRESENT_ON_MAIN`；来源PR：`#155`。

- 每个持仓必须归入：增持、持有、减持、退出、观察或等待证据；
- 明确建议仓位区间、价格条件、基本面条件、风险条件、优先级和不执行后果；
- 交付用户可直接审阅的《真实账户与模拟盘投资决策报告》；
- 只有用户明确选择后，才可建立独立状态变更Proposal。

### R4｜Operating Products

- 固化日报、周报、月报、季报和年度复盘；
- 只产品化现有能力，不继续扩张架构。

### R5｜Attribution & Calibration

- 完成个股、行业、仓位、时点、现金、Candidate及规则层归因；
- 解释模拟盘赚钱或亏钱的原因并形成规则升级建议。

### R6｜Production Acceptance

- 完整自然月实跑；
- 验收自动刷新、用户Delta、跨对话恢复、周期报告、故障重跑、证据追溯和零越权交易。

## 五、阶段门禁

- 未完成当前阶段的用户可读交付，不得进入下一阶段；
- 新阶段必须先在本Master Plan中出现并经用户明确同意；
- 临时缺陷修复归入当前阶段或横向控制，不另起字母轮次；
- R1完成前不进入R2；R3完成前不得宣称WP5完成；R6完成前不得宣称系统已生产化。

## 六、下一任务

`R5_ATTRIBUTION_AND_CALIBRATION_DEVELOPMENT_AFTER_R4_PRESENT_ON_MAIN`

## 七、历史兼容状态

`WP3 | INITIAL CANDIDATE BASELINE COMPLETED`

该标记仅证明WP3初始Candidate基线历史已完成；当前更高层成熟度仍以本计划中的`ENGINE_ACCEPTED_OUTCOME_WINDOWS_INCOMPLETE`为准。


## 八、R1验收结果

- 模拟盘决策覆盖：`16/16`；其中Core2复用2只、P0复用3只、R1新增标准化覆盖11只。
- 真实账户产品覆盖：`7/7`；三只债基形成差异化风险穿透，两只标普500ETF完成条件性单一载体选择，A500/中证500角色确认。
- R1完成不代表可交易；R2组合构建、R3动作矩阵与用户决策包仍未开始。
- 实际持仓、Candidate、旧决策和订单变更均为0。

## 九、R2验收结果

- 真实账户形成风险调整后的四袖套结构与三种情景；默认长期稳健成长参考架构为纯防御45%、混合增强债15%、A股25%、美股15%、战略现金0%。
- 模拟盘五类投资袖套均处于R2参考区间；当前问题集中在成长创新组和中证500Beta的负贡献，而非全组合权重失控。
- 建立单一持仓、主题簇、现金、A股核心—卫星及标普500单一载体约束。
- R2不生成R3逐仓动作矩阵，不改变持仓、Candidate、旧决策或订单。


## 十、R3验收结果

- 真实账户7/7、模拟盘16/16形成逐仓动作矩阵。
- 默认真实账户第一阶段采用自筹资金结构修复：增强债与中证500减持资金转向A500与单一标普500载体。
- 模拟盘维持袖套结构，冻结沪电、汇川、宁德、工业富联新增资金；研究现金维持15%–25%。
- 用户决策项7项，Implementation Ready为0；任何持仓、Candidate、旧决策或订单变更均为0。


## R3阶段边界纠正

- R3仅为开发验收产品，7项决策为能力验证场景，不构成当前真实调仓请求。
- 当前Ready for User Decision为`0`，Implementation Ready为`0`，Operating Activation为`false`。
- 下一阶段固定为`R4_OPERATING_PRODUCTS_DEVELOPMENT`；R4、R5、R6完成并通过生产验收后，才进入运营观察期。

## R4开发验收结果

- 状态：`CURRENT_IF_PRESENT_ON_MAIN`；来源PR：`#158`。
- 已固化统一状态、日报、周报、月报、季报、年度复盘和事件警报共7类产品。
- 每类产品具备固定节奏、必填输入、必备章节、Fail-Closed规则和开发验收样例。
- R4不启动Schedule；Operating Activation为`false`。
- 收益归因仍由R5完成，连续运行和自动激活仍由R6验收。
- 真实账户、模拟盘、Candidate、旧决策和订单变更均为`0`。
