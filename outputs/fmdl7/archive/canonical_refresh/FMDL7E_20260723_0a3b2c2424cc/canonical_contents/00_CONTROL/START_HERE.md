# 股票投资助手 — Current Start Here

## 当前身份

- Canonical Release：`INVESTMENT_OS_R9_20260723_0a3b2c2424cc`
- FMDL-7E Release：`FMDL7E_20260723_0a3b2c2424cc`
- 状态：`GENERATED_AND_BYTE_VALIDATED_PENDING_FILE_LIBRARY_PROMOTION`
- 组合状态：仅确认至 `2026-07-20_CLOSE` 的 Last-known-good
- 实时行动：`BLOCKED_PENDING_CURRENT_STATE_CONFIRMATION_AND_FRESH_MARKET_DATA`
- 交易权限：`NONE`

## 恢复顺序

1. 读取 `00_CONTROL/CURRENT_POINTER.json`。
2. 校验 `00_CONTROL/MANIFEST.json` 的全部成员哈希。
3. 读取 `20_CANONICAL_BINDINGS/` 下的 Release 8、港股通、美股及 FMDL-7 指针。
4. 读取 `10_STATE/`；不得把 2026-07-20 LKG 冒充为当前账户。
5. 读取 `30_OPERATIONS/CADENCE_REGISTRY.json` 和 `40_RECOVERY/CLEAN_ROOM_RESTORE_PLAN.json`。
6. 在任何实时建议前，先确认 2026-07-20 后账户变化并刷新最新完成交易日行情。

## 包边界

本包是控制面、状态和恢复胶囊，不内嵌完整 A股、港股通和美股数据仓。完整市场数据继续由 GitHub 不可变 Release、Last-success 和 LKG 指针管理。Release 8 的旧二进制包身份已保留，但旧包本体未嵌入本包。

## File Library

本包必须与同批次 `股票投资助手_CURRENT_POINTER.md` 一起上传并完成打开、Release ID 和 SHA-256 校验后，才能替换旧 File Library Canonical。Project Sources 保持为空。
