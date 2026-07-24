# START HERE｜股票投资助手R10冻结晋级候选

- Release：`INVESTMENT_OS_R10_20260724_d5bbfa2f0a36`
- Runtime：`1.0.1`
- 状态：`FROZEN_PROMOTION_CANDIDATE_NOT_ACTIVE`
- Runtime基线：`3ee7be7912377c002ebeb7292e35e679f79ae8b3`
- trade_authority：`NONE`

## 恢复与验收顺序

1. 校验外部Current Pointer中的ZIP SHA；
2. 校验内部Release Manifest和Content Tree；
3. 运行35项测试；
4. 分别使用陈旧日期和新鲜日期运行Runtime Acceptance；
5. 核对13项故障注入；
6. 核对State Manifest和零变更证明；
7. 核对Control Capsule只能作为入口，不能代替完整包；
8. 只有WP1-6独立Clean-room通过后才能晋级Active。

State仍为2026-07-20 LKG；A股行情仍为2026-07-17，当前行动继续阻断。
