# 股票投资助手｜阶段完成后的使用说明

## 当前能力边界

- A股：已具备全市场数据、因子筛选、研究适配、Investment OS接入和运营验收能力。
- 港股通：已具备南向范围、财务与行情、因子筛选、研究对象和Investment OS接入能力。
- 美股：当前是24只技术基准证券的Resume-Ready Pilot，不是可投资生产系统。
- 当前美股交易权限始终为 `NONE`。

## 日常使用

用户只需在“股票投资助手”项目中用自然语言提出任务，例如：

1. 更新并检查真实持仓、模拟盘和候选池状态；
2. 分析某只A股或港股通股票，或比较若干标的；
3. 执行月度Operating Review、收益归因或调仓复核；
4. 检查数据是否刷新、系统是否出现失败或需要恢复；
5. 讨论投资判断、组合配置、风险和执行顺序。

ChatGPT应先读取Investment OS Release 8，以及GitHub中的FMDL Current、Last-success和不可变Release，再给出结论。用户不需要维护技术目录或上传FMDL阶段产物。

## 美股未来恢复

恢复入口：`outputs/status/FMDL6_FINAL_LAST_SUCCESS.json`。

当用户真正具备美股投资渠道后，应在项目中明确说明渠道、可交易证券范围、账户币种、税务和执行约束，并明确授权继续开发。系统随后按以下顺序恢复：

`FMDL-6X1 → FMDL-6X2 → FMDL-6X3 → FMDL-6X4`

可以在新的专用窗口持续开发美股；股票投资助手的其他窗口可以继续进行A股、港股通、真实持仓、模拟盘和候选池运营，二者互不冲突。新的开发窗口无需依赖旧聊天上下文，只需读取本Release及GitHub Canonical资产。

## 文件库

File Library只保留Investment OS Release 8的Canonical ZIP及其Pointer／START_HERE。FMDL-5和FMDL-6的技术Release、代码、工作流、Current、Archive和Last-success由GitHub保存，不需要再次上传到File Library。

正式美股试点收口Release：`FMDL6FINAL_20260722_776a6b667b0f`。
