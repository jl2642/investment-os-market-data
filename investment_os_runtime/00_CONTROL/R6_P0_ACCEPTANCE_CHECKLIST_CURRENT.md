# R6 P0 Acceptance Checklist — Current

## 本PR可验收

- [x] 不重建或覆盖现有CORE；新增治理索引和可变政策成熟度映射。
- [x] Canonical Run Manifest和Report Manifest Schema进入现有`20_SCHEMAS_AND_INTERFACES`。
- [x] 安装确定性Manifest构建工具与集成验证器。
- [x] 安装只读GitHub Actions门禁，不激活Schedule、不写入经济状态。
- [x] 对Real、Simulation、Candidate和订单文件执行零变更保护。
- [x] 删除补丁中的`__pycache__`并拒绝平行`05_SCHEMAS`体系。
- [x] `trade_authority = NONE`。

## 合并后仍需完成

- [ ] WP2-R/WP3-R/R4/R5实际运行全部写入Canonical Run Manifest。
- [ ] 行情、基金NAV、FX、Benchmark和公司行为进入同一日终门禁。
- [ ] Real和Simulation形成不可变日终快照序列并通过现金流/公司行为/tie-out。
- [ ] 日报、周报、月报、季报、年报消费同一Report Manifest。
- [ ] 全市场筛选输出统一Funnel Manifest及逐层拒绝分布。
- [ ] 建立集中运行Ledger、漏跑/失败告警、重试和恢复SLA。
- [ ] 至少五个连续交易日预验收通过。
- [ ] 完成2026-08-01至2026-08-31完整R6观察窗口及10/10 Checkpoint。

## 生产结论

本PR完成P0合同与验证层，不等于生产接入完成。R6继续保持`IN_PROGRESS`。
