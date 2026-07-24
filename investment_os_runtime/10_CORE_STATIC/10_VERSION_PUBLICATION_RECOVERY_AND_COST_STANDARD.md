# 10｜版本、发布、恢复与成本标准

## 1. 单一版本族
Investment OS Runtime和State统一使用Schema Major `1.x`。FMDL数据层可保留自己的版本，但必须通过Market Capability Binding接入。禁止Current同时混用3.4.x/3.5.0。

## 2. Full Runtime与Capsule
`股票投资助手_CURRENT.zip`只表示完整运行Canonical；控制胶囊使用独立文件名。Release 8永久作为历史完整基线，Release 9只作为历史控制胶囊。

## 3. 发布
新Run ID不等于新Canonical。发布必须验证As-of、Manifest、Semantic Diff、State影响、零越权和回放。失败不得替换Current，保留LKG。

## 4. 恢复
完整基线只有在继任Full Runtime已生成、SHA验证、File Library打开验证和Clean-room通过后才可删除。Master Plan、Execution Register、START_HERE和Pointer属于必需恢复资产。

## 5. Runtime边界
Control Runtime负责Schema、Manifest、Freshness、权限、状态转换、账务、原子写回、发布、回滚和测试；基本面判断由Research & Decision Plane承担。Runtime离线运行，在线部分只生产Evidence。

## 6. 代码与测试
只保留一份权威源码，排除pyc；依赖锁定。新版Fixtures不得写死旧包名和阶段标签。自身Full Runtime必须通过Schema、迁移、权限、故障注入和Clean-room回放。

## 规则血缘
本模块承接：GOV-006, GOV-007, GOV-008, GOV-010, GOV-011, GOV-015, DAT-010, OPS-006, ENG-001, ENG-002, ENG-003, ENG-005, ENG-006, ENG-007, ENG-010, ENG-011, ENG-012, ENG-013
