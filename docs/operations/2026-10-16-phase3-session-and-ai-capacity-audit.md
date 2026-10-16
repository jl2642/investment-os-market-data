# 2026-10-16｜Phase 3交易日门禁与AI 100万模拟盘仓位容量审计

## Authority / 边界
- 系统级 Authority: `main:investment_os_runtime/00_CONTROL/SYSTEM_CURRENT.json`。
- Runtime: `operating-current/OPERATING_CURRENT_INDEX.json`；本次取 2026-10-15 完整交易日。
- 本轮仅提出 Phase 3 date-coherence preflight；**不更改投资策略、风险限额、真实盘及原模拟盘账本，不产生订单**。

## 1. 故障归因（确定事实）

2026-10-15 Phase 3 生产在 GitHub Actions runs [38761494506](https://github.com/jl2642/investment-os-market-data/actions/runs/38761494506) 和 [38763026371](https://github.com/jl2642/investment-os-market-data/actions/runs/38763026371) 失败。日志为：

- `AI_LISTED_PRICE_SESSION_MISMATCH:000001.SZ:2026-10-15:2026-10-14`
- `AI_LISTED_PRICE_SESSION_MISMATCH:000333.SZ:2026-10-15:2026-10-14`

直接原因：Phase 3将 `PORTFOLIO_MARKS` 的新交易日当作 as-of，但从运行分支读取的 `DECISION_LIFECYCLE` 与 `PORTFOLIO_PRODUCT_SURFACE` 当时仍属上一交易日。建账函数的严格会话校验正确地 fail-closed，但工作流缺少在调用建账前识别依赖未完成并延后运行的预检。随后 run [38788758349](https://github.com/jl2642/investment-os-market-data/actions/runs/38788758349) 完成生产且账本 Current=2026-10-15。

### 实施方案
- 对生产入口增加 date-coherence 门禁：`PORTFOLIO_MARKS.data_watermark`、`DECISION_LIFECYCLE.as_of_date`、其 `input_identity.market_date` 与 `surface_as_of_date`、以及所有正式A股报价会话一致时才允许 build / publish。
- 尚未对齐：明确 `DEFERRED_UPSTREAM_SESSION_MISMATCH`，写 GitHub step summary，不读写经济账本、不发布旧数据、不掩盖为新 Current。
- 严重权限、输入状态异常仍 fail closed；继续保留原建账函数的严格 `AI_LISTED_PRICE_SESSION_MISMATCH` 防线。
- Phase 2在后续成功发布新 lifecycle 时现有工作流会再次 dispatch Phase 3；不得新增固定时钟任务。下一完整交易日需观察自然运行确认端到端稳定。

## 2. 自建模拟盘截至10月15日

- Initial NAV：¥1,000,000；Current NAV：¥1,001,599.496；Return：+0.15995%；现金¥701,507.496（70.04%）；已投资约29.96%；第27个观察交易日；最大回撤-0.667%。
- 持仓：兰州银行约¥99,960；江阴银行约¥100,040；军信股份约¥100,092。
- 累计 decision-grade D2：23只；当前有正式新资本BUY的仅兰州银行、军信股份，两者都在仓且接近单股10%上限。
- `DEFAULT_SINGLE_NAME_CAP=10%`；`DEFAULT_GROUP_CAP=30%`；`AI_CASH_FLOOR=20%`；`MAX_AI_POSITIONS=10`。
- `risk_group(None, rec)` 对没有 `asset_class` / `portfolio_bucket` 的新A股标的回落为 `A_SHARE_STOCK`；AI三只股票因此共享30%上限。剩余可以买的额度约0.0267% NAV，当前价格/整手限制意味着不具备有意义新增仓位空间。

### 诊断：两个不同约束，不能混淆
**机会不足**：formal `BUY` 仅两只且均已持有，未有待配置的新第三只。放宽风险组也不会凭空制造新的正式BUY研究结论。另有7只 `BUY_BELOW` 必须经fresh D2转成BUY，不能见价直接买。

**分类粗糙**：`A_SHARE_STOCK` 是宽泛资产类别，并非行业/相关性风险组。将银行和环保公用服务都视为单一相关风险组，不足以刻画集中度，降低策略识别有效分散机会的能力。与此同时两家银行同处金融信用风险链，应另行监控金融行业集中度。

### 下一步（只提案、不改生产参数）
1. 将权益总敞口、单股、行业/信用关联风险、风格与因子敞口分成独立层级；`A_SHARE_STOCK`只能作为资产类标签，不能直接替代行业相关性。
2. 必须在已有23份D2中按资格筛选：当前有效BUY、正式BUY_BELOW达价需重承销、研究过时待复核，明示决策有效期。
3. 做原策略 vs 多层上限策略 **shadow replay**：固定同一历史时点标的池、费用、行情、决策门槛，报告收益、最大回撤、集中度、空仓率和换手；不要用未来信息重排。
4. 审计通过并经明确批准后才允许调整风险组映射或组限；不得强制买入、不得影响 REAL/legacy SIMULATION。

## 3. Gate / 验收
- 日期一致：允许 Phase 3。
- 上游晚一天/报价有混合交易日：延后且不发布。
- S3已滞后但 lifecycle header已前推：延后。
- 非上市基金 NAV 日期不同：不误阻断正式A股日终账本。
- 严重Authority异常：报错 fail-closed。
- Github CI通过、PR审查后方可合并；自然日终重跑是稳定性最终验收。
