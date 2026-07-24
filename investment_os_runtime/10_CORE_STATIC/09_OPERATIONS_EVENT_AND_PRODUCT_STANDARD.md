# 09｜运营、事件与产品标准

## 1. 六类产品
Daily负责数据/状态健康、异常、公告和价格触发；Weekly负责组合、模拟、Candidate和Thesis变化；Monthly负责归因、风险和规则提案；Quarterly负责财务、估值和研究重估；Annual负责策略与系统审计；Event-driven负责重大事件影响。

## 2. Event E0—E5
E0登记；E1观察；E2研究更新；E3 Candidate/Thesis决策复核；E4紧急组合决策支持但不自动交易；E5数据、权限或系统完整性故障并Fail Closed。

## 3. 产品晋级
所有计划任务和GitHub Actions先产生CANDIDATE产品，经QC_PASSED、ACCEPTED后才可成为CURRENT；失败进入REJECTED或QUARANTINED，不能替换LKG。

## 4. 事件链
Detect→Dedupe→Evidence→Impact on earnings/valuation/thesis/portfolio→Route→User product→Required confirmation→Writeback。必须幂等。

## 5. 观察与测试
WP7至少一个自然月真实运营验收。不得为了测试系统而制造交易。Master Plan和Execution Register持续登记唯一下一入口。

## 规则血缘
本模块承接：OPS-001, OPS-002, OPS-003, OPS-004, OPS-005, OPS-007, OPS-008
