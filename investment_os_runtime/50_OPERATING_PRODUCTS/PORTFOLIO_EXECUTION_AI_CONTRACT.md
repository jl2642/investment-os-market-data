# 股票投资助手｜Portfolio + Execution + AI Autonomous Contract

状态：Phase 3 implementation contract。

## 1. Portfolio Construction

Current Weight → Target Weight。

- Current Recommendation 决定 BUY / ADD / HOLD / TRIM / EXIT 方向。
- expected return、confidence、bear downside 形成研究分数，主要用于新增/加仓资本竞争。
- 单一标的默认上限 10%。
- 相关性/行业缺少完整矩阵时，使用当前 Portfolio Bucket / Asset Class / 指数暴露作为 correlation-risk proxy，风险组默认上限30%。
- HOLD 不因浮盈浮亏机械改变目标权重。
- concentration / drawdown / valuation / risk review 只形成风险诊断与复核，不得在 HOLD 下机械压低目标权重或制造 SELL。
- 单名/风险组上限只有在当前正式 ADD/TRIM/EXIT 已授权仓位变化时才可参与动作 sizing；风险目标本身不是 trade authority。
- Real 和原有 Simulation 只产出建议，不自动改仓。

## 2. Execution Validator

LLM不得输出可直接执行的原始股数。

确定性代码完成：

- Target Weight → Target Value → Target Quantity，但 protected account 只有当前正式 ADD/TRIM/EXIT 才允许进入 BUY/SELL 数量验证。
- HOLD、WATCH、风险复核或单纯超限不得生成 READY_FOR_USER_OR_VIRTUAL_EXECUTION 的 BUY/SELL。
- ADD 只能授权加仓方向，TRIM/EXIT 只能授权减仓方向；方向相反时 fail closed。
- Real / 原有 Simulation 的同一 ADD/TRIM underwriting episode 若已有用户确认且已物化的同方向成交，则后续 Phase3 重跑必须幂等：保持成交后的当前数量，不得再次机械 ADD/TRIM；只有 fresh underwriting / 新 episode 才重新打开动作验证。
- A股/上市ETF买入按100股（份）整手。
- 现金不足时缩减或BLOCK。
- 目标增量不足100股时BLOCK。
- EXIT允许完整卖出已有数量。
- 场外基金不伪造申赎规则，输出人工执行复核。

## 3. AI_AUTONOMOUS_1M

- 初始资金：RMB 1,000,000。
- 初始仓位：0。
- 与Real和原有Simulation完全隔离。
- 唯一允许自动变更的经济账本。
- 最多10只；单名10%；风险组30%；保留至少20%现金目标。
- 只有Current decision-grade BUY可建立新仓。
- BUY_BELOW必须先经Phase 2价格触发并重新D2成为BUY，不能直接买。
- HOLD / ADD / TRIM / EXIT 驱动后续再平衡。
- 固定10bps虚拟滑点。
- 持续记录NAV、累计收益、最大回撤、换手、已实现/未实现贡献。
- Deployment Discipline：第10个完整交易日若现金>80%触发部署复核；第20个交易日前累计跟踪至少5个适用于AI Book的正式 decision-grade D2。30%-50%部署目标只有在当前正式 BUY 集合按单名10%、风险组30%、现金底线20%计算后具有足够 eligible deployable capacity 时才构成欠部署诊断；若正式 BUY 已达到单名/风险组容量上限，则记录 opportunity-capacity constraint，不得把高现金误判为执行不足，也不得强制交易。第30日现金>70%触发 OPPORTUNITY_STARVATION_REVIEW_REQUIRED；第40日现金>50%触发 EXPERIMENT_INSUFFICIENT_DEPLOYMENT，仅形成 Policy Proposal。
- 正式新资本 BUY 门槛统一为概率加权预期收益至少10%且 Bear downside 不劣于-35%；15%只作为 preferred-entry 价格，不得隐性覆盖10%正式门槛。
- D1→D2 的3个研究槽位使用 bounded diversification：至少覆盖 value/recovery 与 momentum/breakout 两类，再用一个 best-remaining 槽位；不再允许三个槽位长期由同一种市场信号占满。
- 当 AI_AUTONOMOUS_1M 现金>80%时，距离 formal 10% BUY gate 3%以内、但尚未达到正式 BUY 条件的 BUY_BELOW 标的可自动反馈到下一轮 D1/D2，形成 bounded fresh semantic re-underwrite 请求；不等于直接买入，也不改变 Real/legacy Simulation 的人工执行边界。
- BUY_BELOW 达价仍不得直接买入，必须 fresh D2 后成为正式 BUY；Deployment Gate 不改变这一规则。
- Deployment Discipline 以AI账本 NAV history 的唯一完整交易日为观察时钟，同日重跑不重复计日；累计记录已观察到的 formal new-capital decision-grade D2 标的。

## 4. Safety

- Real automatic mutation：0。
- Legacy Simulation automatic mutation：0。
- Candidate mutation：0。
- Real order submission：0。
- trade_authority：NONE。
