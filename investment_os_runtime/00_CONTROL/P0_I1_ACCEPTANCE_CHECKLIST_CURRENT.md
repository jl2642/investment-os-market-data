# P0-I1｜R6最低必要工作流接入验收清单

## 本轮实施

- [x] 不修改WP2-R行情与基金NAV核心刷新逻辑。
- [x] 使用`workflow_run.completed`跟随现有WP2-R工作流，不增加新的行情刷新Schedule。
- [x] 每次上游运行生成Canonical Run Manifest。
- [x] 上游成功时生成Real与Simulation不可变EOD快照。
- [x] 生成STATUS与DAILY观察产品及对应Report Manifest。
- [x] 建立集中Operating Run Ledger，记录成功、失败、异常和幂等键。
- [x] 上游失败时保留失败证据但不生成伪快照。
- [x] 持仓连续性落后、tie-out失败及公司行为等缺口必须显式降级或阻断。
- [x] Real、Simulation、Candidate、Decision和订单零变更。
- [x] `trade_authority = NONE`。

## 合并后自动发生

新观察工作流只在WP2-R完成后运行。首个真实Run Manifest、EOD快照和Ledger条目，需要等待合并后的下一次WP2-R实际完成；PR测试生成的`/tmp`结果不属于生产证据。

## 仍未完成

- [ ] 交易所日历驱动的漏跑识别与恢复SLA。
- [ ] FX、Benchmark、公司行为、收入和费用统一门禁。
- [ ] R4周报、月报、季报和年报正式运行接入。
- [ ] R5严格期间收益与归因接入。
- [ ] 连续5个交易日预验收。
- [ ] 2026年8月完整R6自然月验收。
