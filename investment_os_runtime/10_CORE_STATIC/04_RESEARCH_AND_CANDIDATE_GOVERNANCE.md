# 04｜Research与Candidate治理

## 1. 生命周期
Research：IDEA→TRIAGE→ACTIVE_RESEARCH→RESEARCH_COMPLETE→GRADUATED/DEFERRED/REJECTED→ARCHIVED。
Candidate：NONE→CANDIDATE_CORE→READY_FOR_USER_DECISION→PAUSED/REMOVED→ARCHIVED。
研究毕业不得自动进入Candidate、Simulation或Real。

## 2. Candidate Entry Baseline
正式Candidate必须记录入池日期、入池价、入池估值、基准、比较窗口、Thesis、理由、证据和组合角色。缺基线时不得计算Candidate Alpha。旧Core20在WP3重建前仅作为历史LKG。

## 3. 晋级和降级
晋级需Research Object、Thesis/Falsifier、Valuation Scenario、Entry Baseline、Portfolio Fit和人工审查。降级可由证据缺失、数据陈旧、估值失效、Thesis受损、机会成本或容量约束触发。

## 4. 赛马与研究资源
候选比较使用基本面兑现、估值变化、相对表现和研究资源回报，不以短期收益单独定胜负。研究池容量与行业配额可配置，不冻结历史数字。

## 5. 写回
所有状态转换append-only、source-backed、可回放、可回滚；自动流程只能生成Proposal，不能跨域写入。

## 规则血缘
本模块承接：RES-013, RES-015, CAN-001, CAN-002, CAN-003, CAN-004, CAN-005, CAN-006, CAN-007, CAN-009, CAN-010, CAN-011, SIM-004, POR-013
