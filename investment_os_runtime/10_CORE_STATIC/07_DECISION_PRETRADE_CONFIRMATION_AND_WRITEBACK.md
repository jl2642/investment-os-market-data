# 07｜决策、预交易、确认与写回

## 1. 决策三字段
每个决策对象必须分离`decision`、`permission`和`execution_status`。允许的行动标签为NO_ACTION、WATCH、RESEARCH、AVOID、HOLD及BUY/ADD/REDUCE/EXIT_PROPOSAL。

## 2. 权限
`RESEARCH_ONLY`仅允许研究；`USER_DECISION_REQUIRED`要求用户确认；`USER_APPROVED_MANUAL_EXECUTION`只表示用户已批准手动执行，不是系统交易授权。

## 3. 预交易备忘录
真实交易前必须形成包含Evidence、Thesis、估值、组合适配、资金来源、最大损失、替代方案、触发、退出和复核日期的Pre-trade Memo。技术Gate通过只允许进入备忘录。

## 4. 用户确认
用户批准或拒绝必须单独登记。系统不连接券商、不生成订单、不推断成交。只有用户提供执行事实后，状态才进入PENDING_RECONCILIATION。

## 5. 原子写回
状态变化遵循Proposal→Gate→必要用户确认→Atomic Mutation→Validation→Current。失败保留LKG。交易、Candidate、Thesis、风险和规则变化分层写回并保留Lineage。

## 规则血缘
本模块承接：POR-010, POR-011, POR-012, ENG-008
