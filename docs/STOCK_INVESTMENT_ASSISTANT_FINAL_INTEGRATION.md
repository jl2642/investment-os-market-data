# 股票投资助手｜最终融合与开发收口

## 结论

本轮不是重建A股、港股或美股子系统，而是将已完成的能力收口为一个统一ChatGPT读接口，并补齐港股Candidate进入运营期后的周期性只读Review机制。

开发完成后的系统边界：

- A股：全市场Daily Market → History → Factors → Screening → Governed Dynamic Candidate；
- 港股通：正式70只Candidate（Core 2 / Watch 68）→ 周度只读Operating Review → 证据触发时另行形成受治理Candidate Proposal；
- 美股：维持bounded research rotation + SEC evidence能力，不宣称全美股每日全量刷新；
- REAL / SIMULATION：自动估值、风险、归因与动作审查可读；任何实际成交必须来自用户明确事实；
- ChatGPT：通过 `outputs/investment_os/STOCK_INVESTMENT_ASSISTANT_INTERFACE.json` 统一读取各市场和组合Current；
- GitHub：继续作为数据工厂、筛选、Candidate proposal与审计证据层；
- `orders=0`，`trade_authority=NONE`。

## 旧交接信息的最终处置

1. HKCU并非仍在P2B：P2A→P5E已经完成，Phase 5 CLOSED，进入Operating Observation。
2. A股Round 2自然 `workflow_run` 接棒已观察到成功，不再作为未完成开发项。
3. WP3-R旧完整能力红灯已被后续正式接受边界取代：连续Candidate能力已接受；金融行业专用research-grade指标是显式bounded limitation；20/60/120日Outcome属于自然时间成熟，不构成当前开发阻塞。
4. P0-I1在最新修复后的下一次自然运行仍属于运营观察事项；不得仅因尚未发生自然触发就重新开启开发Phase。
5. US SEC链采用受控raw-byte collector / transport-neutral evidence contract；GitHub-hosted runner直连SEC不被假定为可用。

## 港股动态运营机制

`HK Candidate Governed Operating Review` 每周六北京时间约10:30执行一次，只读取正式Candidate Current，生成70只标的的观察Review表和验证结果。

该Review：

- 不自动新增/删除Candidate；
- 不改变Core/Watch tier；
- 不写REAL/SIMULATION；
- 不创建订单；
- 保留每只股票既有 `principal_falsifier` 与 `monitor_triggers`；
- 只有当后续研究取得可核证的新证据并形成单独受治理Proposal/PR时，Candidate成员或tier才可能变化。

因此它解决的是“开发完成后如何持续运行”，而不是另造HKCU P5F或Phase 6。

## 最终用户工作方式

正常情况下用户无需维护GitHub工程。日常入口应是：

- 检查今天股票投资助手运行情况；
- 给出今天投资日报；
- 分析真实持仓、模拟盘和A/H Candidate；
- 检查最近新的A股/港股研究机会；
- 给出本周调仓建议；
- 做月报、季度归因与策略复盘。

只有GitHub无法自行获知的真实交易、申赎、资金流入流出等事实，才需要用户主动提供。

## 开发完成与运营验收的区别

`STOCK_INVESTMENT_ASSISTANT_DEVELOPMENT_COMPLETE` 表示既定系统能力、统一接口和治理边界已经完成；它不等同于声称所有自然生产链已经累计3/3连续周期。

后续若自然运行出现新故障，只允许基于新证据开启bounded repair；不得因为等待自然观察本身继续制造新Phase。
