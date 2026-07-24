# 01｜权威、市场范围与账户政策

## 1. 权威次序
长期政策以用户明确确认和已发布CORE为准；状态以用户提供的账户/交易事实和已接受的原子STATE_CURRENT为准；数据以GitHub已接受Current为准。历史对话、Reference和Archive无裁决权。冲突时Fail Closed。

## 2. 单仓职责
`jl2642/investment-os-market-data`是唯一GitHub仓库。原FMDL路径负责Data Plane；`investment_os_runtime/`负责规则、状态、研究、决策、运营与恢复。目录分离不改变权威门禁。

## 3. 市场边界
A股为主投资链；港股通为受控Research Overlay并需人工重入；美股为Research Adapter Only。禁止强制跨市场统一分数和全球总排名。

## 4. 状态域
Research、Candidate、Simulation和Real Account相互独立。跨域变化必须形成Proposal并通过对应Gate。

## 5. 权限
`trade_authority = NONE`。用户是唯一投资决策人和交易执行人。审计、研究、定时任务和事件任务均不得自动修改投资状态。

## 6. 配置政策
固定资产比例不是永久规则。目标可采用区间、无目标桶和政策有效期；执行现金排除在战略权重之外。

## 规则血缘
本模块承接：GOV-001, GOV-002, GOV-003, GOV-004, GOV-005, GOV-009, GOV-012, GOV-013, GOV-014, STR-006, STR-007, STR-008, STR-010, STR-012, RES-011, ENG-009
