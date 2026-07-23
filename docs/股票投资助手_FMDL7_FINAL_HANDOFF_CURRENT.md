# 股票投资助手｜FMDL-7 Final Current Handoff

updated_as_of: 2026-07-23
canonical_release: `INVESTMENT_OS_R9_20260723_0a3b2c2424cc`
repository: `jl2642/investment-os-market-data`
trade_authority: `NONE`

## SYSTEM_IDENTITY

股票投资助手已经完成FMDL-1至FMDL-7的主体开发和跨市场最终运营验收。当前系统不是自动交易机器人，而是以GitHub不可变Release、Last-success、LKG、File Library Canonical入口及人工决策权限为核心的公共股票投资研究与决策支持系统。

当前基线：

- A股：FMDL-1至FMDL-4；
- 港股通：FMDL-5；
- 美股：FMDL-6研究Adapter；
- 跨市场及全系统：FMDL-7；
- File Library Canonical：Release 9控制面、状态及恢复胶囊；
- FMDL-7完成后进入`POST_FMDL7_OPERATING_OBSERVATION_AND_TARGETED_ITERATION`，不默认继续制造FMDL-8或无限子阶段。

“完整接入”的含义是：市场身份、数据/研究能力、证据链、研究对象、决策路由、状态域、运行周期、陈旧性、恢复和人工权限已经纳入同一治理系统。它不表示三个市场的数据覆盖、投资权限和交易通道完全相同。

## MARKET_CAPABILITY_BOUNDARIES

### A股

已接入全市场接口、历史数据、基础因子和筛选漏斗、财务和估值、研究与决策接口、Candidate Pool、模拟盘、真实账户状态、归因和运行控制。

限制：当前组合及Candidate状态只确认至`2026-07-20_CLOSE`；实时建议前必须确认此后交易和资金变化，并刷新最新完成交易日行情。

### 港股通

已接入Stock Connect范围内的筛选、Research Object、Research Decision、Governed Route、A/H重复暴露控制和跨市场Overlay。

限制：研究毕业不等于自动进入Candidate Pool、模拟盘或真实账户；必须由用户重新审查和批准。A/H重复暴露不得自动选择市场或自动合并。

### 美股

已接入Security Master、身份与上市历史、市场/SEC数据存储框架、Readiness、因子状态、分类、研究卡、Public Equity Investing工作流契约、Decision Interface、Guardrails、模拟控制和跨市场Runbook。

限制：美股当前属于研究Adapter完整接入，而不是投资执行通道完整接入。正式Candidate晋级、正式模拟盘、券商、真实账户和订单均关闭；部分市场数据仍是`NON_DECISION_GRADE_FALLBACK`，不得生成正式收益或Alpha结论。

## CURRENT_STATE_AND_STALENESS

当前可恢复的投资状态为：

- 真实账户：7项持仓，LKG截至2026-07-20收盘；
- 模拟盘：16项持仓，LKG截至2026-07-20收盘；
- Candidate Core：20只；
- Active Memo：6项；
- 价格触发：0；
- 证券账户现金：执行性余额，不是战略现金资产桶；
- `trade_authority = NONE`。

任何新对话框不得把LKG冒充Current。实时组合分析必须先取得最新账户状态和最新市场行情。

## OPERATING_CADENCES

当前运营控制：

- 日度：工作日北京时间10:15，检查来源、行情、Pointer、LKG、市场Adapter、账户确认门禁和告警；
- 周度：周一11:00，复核Candidate、Active Memo、Thesis、重复暴露和模拟盘控制；
- 月度：每月1日11:30，执行组合归因、模拟PnL桥、候选表现覆盖和规则提案；
- 季度：季初首日12:00，复核财务、估值、研究对象和来源质量；
- 年度：1月2日12:30，执行策略、规则有效性、来源成本和系统治理审计；
- 事件驱动：财报、公告、价格、Thesis、数据质量、Pointer或状态变化事件。

所有周期只生成检查、分析、复核或提案，不自动修改Candidate Pool、模拟盘、真实账户、规则或订单。

## AUTHORITATIVE_ASSETS

新对话框恢复顺序：

1. File Library读取`股票投资助手_START_HERE_CURRENT.md`；
2. 读取`股票投资助手_CURRENT_POINTER.md`；
3. 读取`股票投资助手_CURRENT.zip`中的`00_CONTROL/CURRENT_POINTER.json`和`00_CONTROL/MANIFEST.json`；
4. GitHub检查`outputs/status/FMDL7_FINAL_LAST_SUCCESS.json`；
5. 检查A股FMDL-1至4、港股通FMDL-5、美股FMDL-6及FMDL-7各阶段Last-success；
6. 以GitHub不可变Release和Last-success为技术事实，以File Library Current入口为用户恢复入口；
7. 对话记忆、旧聊天结论和历史文件不得覆盖Canonical事实。

## NEW_CHAT_AUDIT_PROMPT

以下文字可原样发送到新的股票投资助手对话框：

> 现在对股票投资助手执行一次“真实功能、真实数据、真实运营状态”独立审计。请先读取文件库中的`股票投资助手_START_HERE_CURRENT.md`、`股票投资助手_CURRENT_POINTER.md`和`股票投资助手_CURRENT.zip`，再检查GitHub仓库`jl2642/investment-os-market-data`的`outputs/status/FMDL7_FINAL_LAST_SUCCESS.json`及其绑定的FMDL-1至FMDL-7不可变Release。不要依据旧对话记忆直接宣布完成。
>
> 审计必须区分：已实现功能、已验收但受限功能、尚未实现功能、数据覆盖缺口、陈旧状态、人工权限和交易权限。分别检查A股、港股通和美股的数据搜集、筛选、研究、Decision Interface、Candidate Pool、模拟盘、真实账户、收益归因、调仓建议、运营周期、故障恢复和File Library恢复能力。
>
> 特别注意：A股/港股通/美股“完整接入”是治理和研究系统接入，不等于三个市场数据覆盖和交易通道相同；美股当前是Research Adapter，正式Candidate、模拟、券商和交易仍关闭；当前真实账户、模拟盘和Candidate状态只确认至2026-07-20收盘，实时建议前必须确认此后变化并刷新行情；`trade_authority = NONE`。
>
> 输出请按“事实—判断—缺口—优先级—分步迭代计划”组织。不要无限新增阶段；只有真实缺陷、运营观察结果或用户明确的新需求才能进入定向开发。首先给出系统总体评级和P0/P1/P2问题，再提出一套可执行、可验收、有限轮次的迭代计划。

## ITERATION_GOVERNANCE

FMDL-7完成后，系统进入运营观察和定向迭代，而不是继续无条件扩张工程阶段。

允许启动新开发的条件：

- 独立审计发现可复现的真实缺陷；
- 真实运营中出现数据断裂、状态恢复失败、归因不闭合或权限越界；
- 用户提出新的市场、数据源、交易通道、报告产品或分析能力需求；
- 实际投资效果显示筛选、研究、择时、仓位或迁移规则需要校准；
- 上游数据源、法规、市场机制或软件接口发生实质变化。

每轮迭代必须有：明确缺陷或需求、权威输入、退出门禁、失败回退、状态零污染证明和有限轮次预算。

## PROHIBITED_OVERCLAIMS

禁止以下表述或行为：

- 声称三个市场数据覆盖和投资能力完全相同；
- 声称美股已具备券商、真实账户或正式模拟通道；
- 使用非Decision-grade数据生成正式投资建议或收益结论；
- 强制生成统一跨市场因子分数或全球股票排名；
- 使用Ticker进行跨市场身份匹配；
- 缺失数据时使用中性值填充或静默替换来源；
- 自动将研究毕业对象加入Candidate Pool；
- 自动将模拟盘正收益迁移至真实账户；
- 将2026-07-20 LKG状态冒充当前持仓；
- 未经用户授权修改Candidate Pool、模拟盘、真实账户、规则或订单；
- 将单只股票或单一期间表现包装成持续Alpha；
- 因为阶段编号已完成而跳过真实功能审计和运营效果检验。

## 当前结论

FMDL-1至FMDL-7完成后，股票投资助手的主体技术架构、A股主链、港股通Overlay、美股研究Adapter、跨市场治理、组合归因、运营控制、故障恢复和Canonical恢复入口均形成可审计基线。下一步应是独立真实功能审计、最新状态刷新和运营观察，而不是继续扩张阶段编号。
