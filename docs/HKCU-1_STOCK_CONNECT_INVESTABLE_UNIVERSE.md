# HKCU-1｜港股通可投资 Universe

## 1. 目标

HKCU-1 在已接受的 FMDL-5E 港股筛选 Universe 与 FMDL-5F 研究适配器之间增加一层独立、可审计、按生效日期控制的港股通资格门禁。

本阶段回答且只回答：某只港股在指定交易日是否属于投资者可通过沪港通或深港通新买入的证券，以及它是否满足进入进一步研究 Universe 的最低数据与流动性要求。

本阶段不形成个股投资结论、目标价、仓位、模拟交易或真实订单；`trade_authority = NONE`。

## 2. 权威输入

### 2.1 内部输入

- FMDL-5E Screening Universe Current；
- FMDL-5E Research Longlist Current；
- FMDL-5C行情、成交额、公司行动与汇率Current；
- FMDL-5D公告及财务证据Current。

### 2.2 外部官方来源

优先级如下：

1. 上海证券交易所/中国投资信息有限公司发布的沪港通下港股通标的证券名单及调整通知；
2. 深圳证券交易所/中国创盈市场服务有限公司发布的深港通下港股通标的证券名单及调整公告；
3. 香港交易所“所有合资格股份”页面及其沪港通、深港通南向合资格证券下载文件，作为交叉核验来源。

搜索结果、财经网站、券商名单和行情供应商不得作为资格判定权威来源。

## 3. 点时资格模型

每条资格记录必须包含：

- `security_id` 与五位港股代码；
- 沪港通新买入资格；
- 深港通新买入资格；
- 任一路径港股通新买入资格；
- 仅可卖出状态；
- 生效起始日与失效日；
- 公告日期、来源机构、来源URL、抓取时间及内容哈希；
- 资格判断状态和排除原因。

指定日期的资格判断不得使用未来公告。名单调入仅在官方指定生效日起有效；调出后不得继续进入可买Universe。仅可卖出证券不得被视为可新增仓位。

## 4. 状态定义

- `BUY_ELIGIBLE_BOTH`：沪港通和深港通均可买入；
- `BUY_ELIGIBLE_SH_ONLY`：仅沪港通可买入；
- `BUY_ELIGIBLE_SZ_ONLY`：仅深港通可买入；
- `SELL_ONLY`：只可卖出，不得新增仓位；
- `NOT_ELIGIBLE`：两条通道均不可买；
- `UNKNOWN_BLOCKED`：来源缺失、冲突、过期或无法解析，Fail Closed。

## 5. 可投资 Universe 门禁

证券进入 `HKCU1_INVESTABLE_UNIVERSE` 必须同时满足：

1. `southbound_buy_eligible = true`；
2. FMDL-5E `investability_status` 为 `ELIGIBLE_CORE` 或经明确规则允许的 `ELIGIBLE_WATCH`；
3. 证券类型为普通权益证券，基金、ETF、结构性产品及其他非公司权益按本阶段规则排除；
4. 最近20个交易日平均成交额不低于港币2,000万元；
5. 最近60个交易日有效成交日比例不低于90%；
6. 最近20个交易日零成交日不超过2日；
7. 具有有效最新价格和可核验市场日期；
8. 财务型公司需有FMDL-5D Decision-grade财务记录；特殊无盈利、18A或新上市公司可进入 `RESEARCH_EXCEPTION`，但不得伪装为财务完整；
9. 数据日期、资格日期和公告可用日期均不得发生未来泄露；
10. 无未知或冲突的资格状态。

上述阈值是研究Universe最低门槛，不是投资质量判断，也不代表推荐买入。

## 6. 输出

- `HKCU1_STOCK_CONNECT_ELIGIBILITY.csv`：点时官方资格主表；
- `HKCU1_INVESTABLE_UNIVERSE.csv`：满足资格与最低研究门禁的证券；
- `HKCU1_EXCLUSIONS.csv`：逐证券排除原因；
- `HKCU1_SOURCE_LEDGER.csv`：官方来源、有效期与哈希；
- `HKCU1_QUALITY_REPORT.json`：门禁及覆盖率；
- `HKCU1_DECISION.json`：发布决定与权限边界；
- `HKCU1_MANIFEST.json`：确定性文件身份。

## 7. 质量门禁

正式发布必须满足：

- 资格记录无重复证券和重叠有效期；
- 所有可买证券均至少有一个官方权威来源；
- 官方名单之间的冲突全部显式披露并Fail Closed；
- `SELL_ONLY`、`NOT_ELIGIBLE`和`UNKNOWN_BLOCKED`进入可投资Universe的数量为0；
- 未来生效公告、未来行情和未来财务数据使用数量为0；
- 可投资Universe每一行均能回溯FMDL-5E、FMDL-5C、FMDL-5D及官方资格来源；
- 未知资格默认阻断，不得以最近一次历史状态静默填充；
- 候选池、模拟盘、真实账户及订单变更数量均为0；
- `trade_authority = NONE`。

## 8. 更新频率

- 每个港股通交易日前检查官方名单变动；
- 每周至少进行一次官方全量名单重建与沪深交叉核验；
- 每次恒生综合指数定期调整、A+H新上市、价格稳定期结束、停牌/退市及官方临时调整后强制重建；
- 行情和FMDL-5E数据超过5个港股交易日未更新时，禁止晋级新的研究对象。

## 9. Phase 1验收边界

Phase 1验收通过仅意味着形成真实可买、来源可审计的港股通研究Universe。下一阶段才可对该Universe进行港股专项治理风险筛选、A/H折溢价分析和分层研究。
