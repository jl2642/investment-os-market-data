# 股票投资助手｜P0 Operational Remediation Audit CURRENT

- 审计日期：`2026-08-03`
- Canonical：GitHub `jl2642/investment-os-market-data` / `main`
- 审计基准提交：`d899b815809b12d9fc5be091deb5a74c670ce853`
- 当前阶段：`R6_PRODUCTION_ACCEPTANCE_IN_PROGRESS_NOT_PRODUCTION_COMPLETE`
- `trade_authority`：`NONE`

## 结论

仓库并非缺少整体架构。CORE、全市场数据、持仓Current、Candidate、运营产品和R5归因均已有较成熟实现；真正的P0缺口集中在**跨工作流统一运行Manifest、行情/NAV之外的FX与公司行为、正式日终快照、期间收益输入、报告统一Manifest、集中可观测性以及R6连续运行证据**。

上传补丁不得整包覆盖，原因包括：

1. 新建`investment_os_runtime/05_SCHEMAS`会与现有`20_SCHEMAS_AND_INTERFACES`形成第二套Schema体系；
2. 另建四条规则目录会与现有`ACTIVE_RULE_REGISTRY.csv`的118条规则治理形成平行权威；
3. 通用`MARKET_DATA_FETCH_COMMAND`工作流弱于现有Sina行情、Eastmoney基金NAV和收盘判断实现；
4. 补丁包含`__pycache__`，不应进入Canonical；
5. 本地Fixture通过不能替代GitHub定时运行、写回、补跑和完整自然月验收。

## 证据化现状

| P0域 | 审计状态 | GitHub证据 | 主要缺口 |
|---|---|---|---|
| CORE治理 | 已完成主体 / 需有限补强 | `10_CORE_STATIC/00–10`、`ACTIVE_RULE_REGISTRY.csv` | 缺少对可变政策成熟度、复核日和退役条件的统一机器映射 |
| Canonical读写 | 部分完成 | Execution Register、Asset Registry、受治理PR/Current晋级 | 各运行没有统一before/after commit、输入输出、水位、异常与幂等Manifest |
| 市场数据 | 部分完成 | FMDL；`wp2_r_market_marks_refresh.yml`；`refresh_market_marks.py` | 持仓行情/NAV已覆盖，但FX、公司行为、统一交易日历和异常值控制未形成同一日终门禁 |
| 账户快照 | 部分完成 | Real 7项、Simulation 16项Current及独立水位 | 无券商连接；未形成包含现金流、分红、公司行为和完整tie-out的正式日终快照序列 |
| 绩效归因 | 部分完成 | R5七层归因、7+16贡献和模拟盘P&L桥 | 严格期间收益、MWR/TWR、时点、现金和Candidate成熟窗口仍被正确阻断 |
| 报告体系 | 部分完成 | R4七类产品合同及样例 | 尚无所有日报至年报共同消费并持久化的Report Manifest |
| 研究漏斗 | 部分完成 | A股5,530范围、5,525 eligible、73项研究运营池 | 零推荐时的全覆盖与逐层拒绝分布未统一到单一Funnel Manifest |
| 调度与补跑 | 部分完成 | 多个GitHub Actions定时与手动工作流 | 缺少集中运行登记、重试结果、漏跑识别、恢复SLA和跨工作流幂等审计 |
| R6验收 | 未完成 | 观察窗口2026-08-01至2026-08-31，当前1/10 | 完整自然月、月末归因、跨对话恢复、漏跑/重复运行和零越权审计尚未完成 |

## 本PR实施边界

本PR只安装P0治理合同、Schema、确定性Manifest工具、集成验证器和只读CI门禁。它：

- 不修改真实账户、模拟盘、Candidate或订单状态；
- 不替换现有FMDL/WP2-R/WP3-R/R4/R5实现；
- 不激活新Schedule；
- 不将本地测试表述为生产完成；
- 不关闭R6观察Ledger中的任何待验收Checkpoint。

## 后续生产接入顺序

1. 将Canonical Run Manifest接入WP2-R、WP3-R、R4和R5实际工作流；
2. 在现有行情/NAV链路上补FX、公司行为和交易日历，而不是改用通用Provider占位；
3. 生成真实账户和模拟盘不可变日终快照序列；
4. 日报至年报共同消费Report Manifest；
5. 建立集中运行Ledger、告警和重跑证据；
6. 完成至少五个连续交易日预验收及2026年8月完整R6观察窗口。
