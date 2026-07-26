# WP4｜Core2 Deep Research、Portfolio Fit、Decision-grade Valuation与Decision Interface

## 结论

WP4以一个集中里程碑覆盖全部已接受Candidate Core：美的集团与长江电力。两只标的均完成来源注册、事实/假设/推断分层、组合角色分析、显式情景估值和Decision Interface。

- 美的集团：2026年一季度收入和归母利润增长放缓，扣非利润下降；当前价格接近Base情景与6.5% FCF收益率交叉验证值，安全边际不足以进入Ready。
- 长江电力：2026年上半年六座梯级电站发电量增长4.81%，但来水结构显著分化；当前价格接近Base情景和3.5%股息率交叉验证值，防御质量较强但估值补偿有限。

## 决策接口

| 标的 | 决策状态 | Ready | 交易信号 |
|---|---|---:|---|
| 美的集团 | WATCH_FOR_EVIDENCE_AND_PRICE | 否 | NO |
| 长江电力 | HOLD_FOR_EVIDENCE_OR_BETTER_ENTRY | 否 | NO |

两只标的的研究与估值可以支持明确的等待结论，但不能支持仓位设计或交易建议。真实账户Position-level Current不可用且`broker_verified=false`，因此Portfolio Fit仅达到方向性角色级，不能达到Position Sizing级。

## 权限边界

- Candidate membership mutations：0
- Real-account mutations：0
- Simulation-trade mutations：0
- Orders：0
- trade_authority：NONE

WP4完成不等于必须产生买入建议。当前正式结果是：研究完成、估值可审计、决策接口明确、0只Ready、0项交易行动。
