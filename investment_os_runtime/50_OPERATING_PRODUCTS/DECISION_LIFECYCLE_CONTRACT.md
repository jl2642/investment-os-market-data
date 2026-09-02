# 股票投资助手｜Decision Lifecycle Contract

状态：Phase 2 implementation contract。

## 目的

把 Phase 1 的持久 Thesis / Recommendation Register 转成可持续监控的持仓与非持仓生命周期，而不是重新建立一套 P4-4。

## 机械可判定

- `BUY_BELOW`：最新完成交易日价格达到 entry threshold → `REUNDERWRITE_REQUIRED`。
- 当前持仓 `TRIM / EXIT / ADD` → 用户动作复核队列。
- 当前组合集中度、回撤 flag → 生命周期风险状态。
- 同一触发状态保持持久化，记录 NEW / PERSISTING / CLEARED transition。

## 语义不可机械判定

Catalyst 与 kill-thesis 只登记为监控条款。GitHub 不允许用关键词命中直接改变 Recommendation；必须重新 D2。

## 卖出机制

卖出不是“止损规则”。只有当前 decision-grade Recommendation 为 `TRIM / EXIT`，或新的基本面/估值/组合约束触发重新承销后得出 `TRIM / EXIT`，才进入执行验证。

## 安全边界

- 价格触发不直接 BUY / ADD。
- 浮亏不直接 TRIM / EXIT。
- 自动语义关键词推断：0。
- Real / Simulation / Candidate mutation：0。
- Orders：0。
- trade_authority：`NONE`。
