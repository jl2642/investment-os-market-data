# 股票投资助手｜Portfolio + Execution + AI Autonomous Contract

状态：Phase 3 implementation contract。

## 1. Portfolio Construction

Current Weight → Target Weight。

- Current Recommendation 决定 BUY / ADD / HOLD / TRIM / EXIT 方向。
- expected return、confidence、bear downside 形成研究分数，主要用于新增/加仓资本竞争。
- 单一标的默认上限 10%。
- 相关性/行业缺少完整矩阵时，使用当前 Portfolio Bucket / Asset Class / 指数暴露作为 correlation-risk proxy，风险组默认上限30%。
- HOLD 不因浮盈浮亏机械改变目标权重。
- concentration review 可以把目标权重压回单一标的上限。
- Real 和原有 Simulation 只产出建议，不自动改仓。

## 2. Execution Validator

LLM不得输出可直接执行的原始股数。

确定性代码完成：

- Target Weight → Target Value → Target Quantity。
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

## 4. Safety

- Real automatic mutation：0。
- Legacy Simulation automatic mutation：0。
- Candidate mutation：0。
- Real order submission：0。
- trade_authority：NONE。
