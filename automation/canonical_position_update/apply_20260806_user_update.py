#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "POSITION_UPDATE_20260806_USER_INTRADAY"
AS_OF_REAL = "2026-08-06T11:02:00+08:00"
AS_OF_SIM = "2026-08-06T11:03:00+08:00"
MAIN_BEFORE = "46e22203928d886203e21ad860b7ff55777da48b"

P = {
    "real_source": ROOT / "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_CURRENT.json",
    "real": ROOT / "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json",
    "equity": ROOT / "investment_os_runtime/30_STATE_CURRENT/12_EQUITY_COMPENSATION/EQUITY_COMPENSATION_CURRENT.json",
    "delta": ROOT / "investment_os_runtime/30_STATE_CURRENT/15_PORTFOLIO_INPUT/USER_TRANSACTION_DELTA_LEDGER_CURRENT.json",
    "sim_source": ROOT / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_LEDGER_CURRENT.json",
    "sim": ROOT / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json",
    "candidate": ROOT / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json",
    "weekly": ROOT / "investment_os_runtime/30_STATE_CURRENT/45_CANDIDATE_OPERATIONS/WEEKLY_PRICE_SCREEN_CURRENT.json",
    "candidate_review": ROOT / "investment_os_runtime/30_STATE_CURRENT/45_CANDIDATE_OPERATIONS/CANDIDATE_ACTION_REVIEW_CURRENT.json",
    "confirmations": ROOT / "investment_os_runtime/30_STATE_CURRENT/61_DECISIONS/USER_CONFIRMATIONS_CURRENT.json",
    "decision_proposals": ROOT / "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/DECISION_PROPOSALS_CURRENT.json",
    "portfolio_decision": ROOT / "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_PORTFOLIO_DECISION_CURRENT.json",
    "evidence": ROOT / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/POSITION_UPDATE_2026_08_06/USER_CONFIRMED_INTRADAY_SNAPSHOT_20260806.json",
    "baseline": ROOT / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/POSITION_UPDATE_2026_08_06/PROTECTED_STATE_BASELINE.json",
    "status": ROOT / "investment_os_runtime/50_OPERATING_PRODUCTS/OBSERVATION/STATUS/POSITION_UPDATE_STATUS_20260806_USER_INTRADAY.json",
    "run_manifest": ROOT / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1/RUN_MANIFESTS/POSITION_UPDATE_20260806_USER_INTRADAY.json",
    "report_manifest": ROOT / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1/REPORT_MANIFESTS/POSITION_UPDATE_20260806_USER_INTRADAY.json",
}

REAL_MARKS = {
    "017534": {"name": "富国天利增长债券C", "qty": 81640.26, "mark": 1.3968, "cost": 110614.38, "mv": 114035.12, "pnl": 3420.74, "pnl_pct": 0.0309, "asset_class": "BOND_FUND"},
    "110017": {"name": "易方达增强回报债券A", "qty": 71422.49, "mark": 1.4060, "cost": 100000.00, "mv": 100420.02, "pnl": 420.02, "pnl_pct": 0.0042, "asset_class": "BOND_FUND"},
    "159352": {"name": "A500ETF南方", "qty": 27700, "mark": 1.283, "cost_price": 1.366, "cost": 37838.20, "mv": 35539.10, "pnl": -2304.78, "pnl_pct": -0.0609, "asset_class": "A_SHARE_ETF"},
    "159612": {"name": "标普500ETF国泰", "qty": 10200, "mark": 2.074, "cost_price": 1.795, "cost": 18309.00, "mv": 21154.80, "pnl": 2847.20, "pnl_pct": 0.1555, "asset_class": "QDII_ETF"},
    "159655": {"name": "标普500ETF华夏", "qty": 11300, "mark": 2.017, "cost_price": 1.664, "cost": 18803.20, "mv": 22792.10, "pnl": 3985.30, "pnl_pct": 0.2119, "asset_class": "QDII_ETF"},
    "217003": {"name": "招商安泰债券A", "qty": 73142.57, "mark": 1.3870, "cost": 100000.00, "mv": 101448.74, "pnl": 1448.74, "pnl_pct": 0.0145, "asset_class": "BOND_FUND"},
    "510500": {"name": "中证500ETF南方", "qty": 7900, "mark": 7.836, "cost_price": 8.376, "cost": 66170.40, "mv": 61904.40, "pnl": -4268.52, "pnl_pct": -0.0645, "asset_class": "A_SHARE_ETF"},
    "605090": {"name": "九丰能源", "qty": 9900, "mark": 33.630, "cost_price": 33.055, "cost": 327244.50, "mv": 332937.00, "pnl": 5692.50, "pnl_pct": 0.0174, "asset_class": "A_SHARE_STOCK"},
}

SIM_MARKS = {
    "000333": {"name": "美的集团", "qty": 800, "available": 800, "mark": 85.22, "unit_cost": 77.38, "broker_cost": 77.38, "mv": 68176.00, "broker_pnl": 6269.54, "broker_pct": 0.1013, "bucket": "Core"},
    "300012": {"name": "华测检测", "qty": 1000, "available": 0, "mark": 14.07, "unit_cost": 14.08, "broker_cost": 14.09, "mv": 14070.00, "broker_pnl": -15.00, "broker_pct": -0.0011, "bucket": "Quality_Growth"},
    "300124": {"name": "汇川技术", "qty": 200, "available": 200, "mark": 63.95, "unit_cost": 79.02, "broker_cost": 94.07, "mv": 12790.00, "broker_pnl": -6024.46, "broker_pct": -0.3202, "bucket": "Growth/Observation"},
    "300750": {"name": "宁德时代", "qty": 100, "available": 100, "mark": 387.53, "unit_cost": 452.26, "broker_cost": 452.26, "mv": 38753.00, "broker_pnl": -6472.95, "broker_pct": -0.1431, "bucket": "Growth"},
    "510500": {"name": "中证500ETF南方", "qty": 7100, "available": 7100, "mark": 7.848, "unit_cost": 8.276, "broker_cost": 8.276, "mv": 55720.80, "broker_pnl": -3036.56, "broker_pct": -0.0517, "bucket": "Benchmark ETF"},
    "600036": {"name": "招商银行", "qty": 1600, "available": 1600, "mark": 38.57, "unit_cost": 35.42, "broker_cost": 35.42, "mv": 61712.00, "broker_pnl": 5039.02, "broker_pct": 0.0889, "bucket": "Core/Financial"},
    "600276": {"name": "恒瑞医药", "qty": 800, "available": 800, "mark": 52.78, "unit_cost": 50.27, "broker_cost": 50.27, "mv": 42224.00, "broker_pnl": 2007.56, "broker_pct": 0.0499, "bucket": "Growth/Medical"},
    "600309": {"name": "万华化学", "qty": 700, "available": 700, "mark": 74.23, "unit_cost": 70.01, "broker_cost": 70.01, "mv": 51961.00, "broker_pnl": 2956.67, "broker_pct": 0.0603, "bucket": "Cycle"},
    "600406": {"name": "国电南瑞", "qty": 1800, "available": 1800, "mark": 24.01, "unit_cost": 22.58, "broker_cost": 22.58, "mv": 43218.00, "broker_pnl": 2565.46, "broker_pct": 0.0631, "bucket": "Defensive"},
    "600660": {"name": "福耀玻璃", "qty": 1600, "available": 1600, "mark": 56.02, "unit_cost": 49.87, "broker_cost": 49.87, "mv": 89632.00, "broker_pnl": 9839.24, "broker_pct": 0.1233, "bucket": "Core"},
    "600690": {"name": "海尔智家", "qty": 1800, "available": 1800, "mark": 21.95, "unit_cost": 20.37, "broker_cost": 20.37, "mv": 39510.00, "broker_pnl": 2847.49, "broker_pct": 0.0777, "bucket": "Core"},
    "600900": {"name": "长江电力", "qty": 2200, "available": 2200, "mark": 27.61, "unit_cost": 26.47, "broker_cost": 26.47, "mv": 60742.00, "broker_pnl": 2517.41, "broker_pct": 0.0432, "bucket": "Core/Dividend"},
    "600938": {"name": "中国海油", "qty": 1800, "available": 1800, "mark": 30.50, "unit_cost": 26.26, "broker_cost": 26.26, "mv": 54900.00, "broker_pnl": 7638.10, "broker_pct": 0.1616, "bucket": "Cycle/Dividend"},
    "600941": {"name": "中国移动", "qty": 700, "available": 700, "mark": 95.83, "unit_cost": 86.97, "broker_cost": 86.97, "mv": 67081.00, "broker_pnl": 6204.97, "broker_pct": 0.1019, "bucket": "Core/Dividend"},
    "601138": {"name": "工业富联", "qty": 600, "available": 600, "mark": 69.18, "unit_cost": 76.43, "broker_cost": 76.43, "mv": 41508.00, "broker_pnl": -4352.89, "broker_pct": -0.0949, "bucket": "Growth/AI_Hardware"},
    "601899": {"name": "紫金矿业", "qty": 1000, "available": 1000, "mark": 34.59, "unit_cost": 30.66, "broker_cost": 30.66, "mv": 34590.00, "broker_pnl": 3930.23, "broker_pct": 0.1282, "bucket": "Cycle"},
}

TRADES = [
    {"delta_id": "SIM_20260806_SELL_002463_200", "action": "SELL", "code": "002463", "name": "沪电股份", "quantity": 200, "price": 119.89, "amount": 23978.00, "time": "11:00:35"},
    {"delta_id": "SIM_20260806_SELL_300124_200", "action": "SELL", "code": "300124", "name": "汇川技术", "quantity": 200, "price": 64.03, "amount": 12806.00, "time": "11:00:48"},
    {"delta_id": "SIM_20260806_BUY_300012_1000", "action": "BUY", "code": "300012", "name": "华测检测", "quantity": 1000, "price": 14.08, "amount": 14080.00, "time": "11:01:54"},
]


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def code(row: dict[str, Any]) -> str:
    return str(row.get("code") or row.get("security_code") or row.get("security_id", "").split(".")[0]).zfill(6)


def git_blob_sha(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def security_id(sec: str) -> str:
    return f"{sec}.SH" if sec.startswith(("5", "6", "9")) else f"{sec}.SZ"


def update_real_positions(payload: dict[str, Any]) -> None:
    by_code = {code(row): row for row in payload["holdings"]}
    assert set(by_code) == set(REAL_MARKS)
    for sec, item in REAL_MARKS.items():
        row = by_code[sec]
        row.update({
            "available_quantity": float(item["qty"]),
            "broker_display_unrealized_pnl": item["pnl"],
            "broker_display_unrealized_pnl_pct": item["pnl_pct"],
            "broker_verified": False,
            "cost_basis": item["cost"],
            "mark": item["mark"],
            "mark_as_of": AS_OF_REAL,
            "mark_freshness_status": "INTRADAY_USER_CONFIRMED",
            "mark_provider": "USER_CONFIRMED_REAL_SCREENSHOT_INTRADAY",
            "market_value": item["mv"],
            "position_source_as_of": AS_OF_REAL,
            "position_source_run_id": RUN_ID,
            "quantity": float(item["qty"]),
            "snapshot_type": "USER_CONFIRMED_INTRADAY",
            "unrealized_pnl": round(item["mv"] - item["cost"], 6),
            "unrealized_pnl_pct": round((item["mv"] - item["cost"]) / item["cost"], 8),
        })
        if "cost_price" in item:
            row["broker_display_unit_cost"] = item["cost_price"]
            row["unit_cost"] = item["cost_price"]
        else:
            row["unit_cost"] = item["cost"] / item["qty"]
        if sec == "605090":
            row.update({
                "batch_identity": "AGGREGATE_2026_STOCK_INCENTIVE_AND_OPTION_SETTLED",
                "broker_display_unit_cost": 33.055,
                "economic_cash_cost": 160330.50,
                "economic_cost_basis_status": "SEPARATE_EQUITY_COMPENSATION_SUBLEDGER",
                "pending_entitlement_quantity_excluded": 0,
                "technical_entitlement_codes_excluded": ["Q99460", "Q99461"],
            })
    payload.update({
        "formal_eod_snapshot_written": False,
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "state_id": "WP2R_REAL_POSITIONS_CURRENT_20260806_INTRADAY",
        "status": "POSITION_CURRENT_USER_CONFIRMED_INTRADAY_NOT_EOD",
        "trade_authority": "NONE",
        "orders": 0,
        "user_confirmed": True,
    })
    payload["mark_watermark"] = {
        "all_marks_fresh_or_acceptable": True,
        "all_positions_marked": True,
        "latest_mark_date": "2026-08-06",
        "marks_source_id": "USER_CONFIRMED_INTRADAY_20260806",
        "formal_eod": False,
    }
    payload["position_watermark"] = {
        "applied_delta_count": 1,
        "applied_delta_ids": ["REAL_605090_SECOND_4950_SETTLEMENT_20260806"],
        "base_state_as_of": AS_OF_REAL,
        "position_state_current": True,
        "user_delta_continuity_confirmed_through": AS_OF_REAL,
    }
    payload["reconciliation_exceptions"] = [{
        "allocation_policy": "DO_NOT_ALLOCATE_TO_ANY_SECURITY",
        "amount": -71.90,
        "exception_id": "REAL_STOCK_TOTAL_MINUS_LINE_SUM_20260806_INTRADAY",
        "status": "OPEN_INTRADAY_PRICE_TIMING_EXCEPTION",
    }]
    payload["summary"] = {
        "account_total_assets": 790928.83,
        "broker_bond_fund_total_reported": 315903.88,
        "broker_listed_security_total_reported": 474255.50,
        "broker_reconciliation_exception_amount": -71.90,
        "broker_total_assets_reported": 790928.83,
        "cash_semantics": "BROKER_EXECUTION_BALANCE_ONLY_EXTERNAL_LIQUIDITY_EXCLUDED",
        "execution_cash_balance": 769.45,
        "holding_count": 8,
        "listed_security_line_market_value_sum": 474327.40,
        "bond_fund_line_market_value_sum": 315903.88,
        "open_unrealized_pnl": 11251.60,
        "pending_entitlement_market_value_included": 0.0,
        "pending_entitlement_quantity_included": 0,
        "position_cost_basis": 778979.68,
        "position_market_value": 790231.28,
        "reconciliation_explanation": "Broker stock subtotal is preserved. CNY -71.90 intraday timing difference is not allocated to any security.",
        "reconciliation_status": "USER_CONFIRMED_INTRADAY_WITH_UNALLOCATED_TIMING_EXCEPTION",
    }


def update_real_source(payload: dict[str, Any]) -> None:
    by_code = {code(row): row for row in payload["holdings"]}
    assert set(by_code) == set(REAL_MARKS)
    for sec, item in REAL_MARKS.items():
        row = by_code[sec]
        row.update({
            "as_of": AS_OF_REAL,
            "data_source": "USER_CONFIRMED_BROKER_SCREENSHOT_INTRADAY_20260806",
            "formal_eod_snapshot_written": False,
            "holding_name": item["name"],
            "holding_pnl": item["pnl"],
            "holding_pnl_pct": f"{item['pnl_pct'] * 100:.2f}%",
            "latest_price_or_nav": item["mark"],
            "market_value": item["mv"],
            "promotion_status": "USER_CONFIRMED_INTRADAY_PROVISIONAL",
            "quantity_or_shares": float(item["qty"]),
            "run_id": RUN_ID,
            "snapshot_type": "USER_CONFIRMED_INTRADAY",
            "source_as_of": AS_OF_REAL,
            "source_run_id": RUN_ID,
            "source_schema_version": "3.5.0",
        })
        row["cost_price_or_cost"] = item.get("cost_price", item["cost"])
        if sec == "605090":
            row["batch_identity"] = "AGGREGATE_2026_STOCK_INCENTIVE_AND_OPTION_SETTLED"
            row["economic_cash_cost"] = 160330.50
            row["broker_display_cost_price"] = 33.055
    payload.update({
        "as_of": AS_OF_REAL,
        "formal_eod_snapshot_written": False,
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "state_id": "REAL_ACCOUNT_USER_CONFIRMED_INTRADAY_20260806",
        "status": "USER_CONFIRMED_INTRADAY_NOT_EOD_SECOND_605090_BATCH_SETTLED",
        "trade_authority": "NONE",
        "orders": 0,
    })
    payload["limitations"] = [
        "USER_CONFIRMED_INTRADAY_NOT_FORMAL_EOD",
        "BROKER_STOCK_TOTAL_LINE_SUM_EXCEPTION_NEGATIVE_71_90_UNALLOCATED",
        "605090_2026_AGGREGATE_9900_SETTLED",
        "605090_TAX_BASIS_AND_FEES_PENDING_DOCUMENTATION",
        "Q99460_AND_Q99461_TECHNICAL_CODES_EXCLUDED_FROM_ASSETS",
    ]
    payload["summary"] = {
        "account": "REAL",
        "as_of": AS_OF_REAL,
        "available_cash": 769.45,
        "bond_fund_total": 315903.88,
        "listed_security_line_market_value_sum": 474327.40,
        "listed_security_total_broker_reported": 474255.50,
        "market_value": 790159.38,
        "position_ratio": round(790159.38 / 790928.83, 8),
        "pricing_caveat": "User-confirmed intraday snapshot; not formal EOD. CNY -71.90 stock subtotal timing exception remains unallocated.",
        "promotion_status": "USER_CONFIRMED_INTRADAY_PROVISIONAL",
        "run_id": RUN_ID,
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "source_as_of": AS_OF_REAL,
        "source_run_id": RUN_ID,
        "source_schema_version": "3.5.0",
        "total_assets": 790928.83,
        "trade_action": "USER_CONFIRMED_SETTLEMENT_ONLY_NO_REAL_TRADE",
    }


def update_equity(payload: dict[str, Any]) -> None:
    payload.update({
        "as_of": AS_OF_REAL,
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "state_id": "EQUITY_COMPENSATION_CURRENT_20260806",
        "status": "CURRENT_2026_STOCK_INCENTIVE_AND_OPTION_BATCHES_SETTLED_TAX_FEES_PENDING",
        "orders": 0,
        "trade_authority": "NONE",
    })
    for program in payload["programs"]:
        for tranche in program["tranches"]:
            if tranche["year"] == 2026:
                tranche["status"] = "SETTLED_AS_ORDINARY_SHARES"
                tranche["current_position_quantity"] = 4950
    current = payload["current_recognition"]
    current["ordinary_share_position"] = {
        "quantity": 9900,
        "available_quantity": 9900,
        "market_price": 33.63,
        "market_value": 332937.0,
        "included_in_real_account_current": True,
        "batch_identity": "AGGREGATE_2026_STOCK_INCENTIVE_AND_OPTION_SETTLED",
        "broker_display_unit_cost": 33.055,
        "broker_display_cost_basis": 327244.50,
        "economic_cash_cost": 160330.50,
    }
    current["pending_entitlement"] = {
        "quantity": 0,
        "market_value": 0.0,
        "included_in_real_account_current": False,
        "included_in_total_assets": False,
        "status": "NO_PENDING_2026_ENTITLEMENT_AFTER_SECOND_SETTLEMENT",
    }
    for right in current.get("technical_entitlement_codes", []):
        right["market_value"] = 0.0
        right["asset_recognition"] = "TECHNICAL_RIGHT_ONLY_NOT_ADDITIONAL_ASSET"
    payload["double_counting_controls"] = [
        "CURRENT_ORDINARY_SHARE_QUANTITY_MUST_EQUAL_9900",
        "PENDING_ENTITLEMENT_MUST_EQUAL_ZERO_AFTER_SECOND_SETTLEMENT",
        "Q99460_AND_Q99461_MUST_NOT_ENTER_ORDINARY_HOLDINGS",
        "2025_SOLD_13200_SHARES_MUST_NOT_REENTER_CURRENT_HOLDINGS",
        "BROKER_DISPLAY_COST_MUST_NOT_REPLACE_2026_ECONOMIC_CASH_COST_160330_50",
    ]
    payload["unresolved_items"] = [
        {"item": "CONFIRM_2026_TAX_AND_FEES", "status": "OPEN", "required_evidence": "TAX_AND_FEE_STATEMENT"},
        {"item": "CONFIRM_TECHNICAL_CODE_DISPLAY_MAPPING", "status": "OPEN_NON_ASSET", "required_evidence": "BROKER_CODE_MAPPING_OPTIONAL"},
    ]


def make_delta(delta_id: str, account: str, action: str, sec: str, qty: float, **extra: Any) -> dict[str, Any]:
    value = {
        "account": account,
        "action": action,
        "application_decision": "APPLIED_TO_POSITION_CURRENT",
        "confirmation_authority": "USER",
        "delta_id": delta_id,
        "event_type": "POSITION_SETTLEMENT" if account == "REAL" else "SIMULATION_TRADE",
        "evidence_status": "USER_SCREENSHOT_CONFIRMED",
        "quantity": qty,
        "security_code": sec,
        "security_id": security_id(sec),
        "status": "APPLIED_TO_POSITION_CURRENT",
        "applied_run_id": RUN_ID,
    }
    value.update(extra)
    return value


def update_delta(payload: dict[str, Any]) -> None:
    by_id = {row["delta_id"]: row for row in payload.get("entries", [])}
    additions = [
        make_delta(
            "REAL_605090_SECOND_4950_SETTLEMENT_20260806", "REAL", "TRANSFER_IN", "605090", 4950,
            current_position_effect=4950, market_value_effect=166468.50,
            note="Remaining 4,950 2026 equity-compensation shares are visible and available as ordinary shares; aggregate ordinary holding is now 9,900.",
        ),
    ]
    for trade in TRADES:
        additions.append(make_delta(
            trade["delta_id"], "SIMULATION", trade["action"], trade["code"], trade["quantity"],
            price=trade["price"], gross_amount=trade["amount"], execution_time=f"2026-08-06T{trade['time']}+08:00",
            note="User-executed simulation trade recorded from transaction screenshot; not an automated order.",
        ))
    for row in additions:
        by_id[row["delta_id"]] = row
    payload["entries"] = list(by_id.values())
    payload.update({
        "applied_delta_count": 4,
        "as_of": AS_OF_SIM,
        "continuity_confirmed_through": AS_OF_SIM,
        "ledger_id": "USER_TRANSACTION_DELTA_LEDGER_CURRENT_20260806",
        "orders": 0,
        "rejected_for_position_engine_count": sum(row.get("status") == "REJECTED" for row in payload["entries"]),
        "schema_version": "1.0.0",
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "status": "FOUR_USER_CONFIRMED_DELTAS_APPLIED_INTRADAY_NOT_EOD",
        "trade_authority": "NONE",
        "unapplied_delta_count": 0,
        "unresolved_exception_count": 1,
        "unresolved_exceptions": ["2026_TAX_AND_FEES_PENDING"],
    })


def position_row(sec: str, item: dict[str, Any], old: dict[str, Any] | None) -> dict[str, Any]:
    row = dict(old or {})
    econ_cost = round(item["qty"] * item["unit_cost"], 6)
    row.update({
        "account": "SIMULATION",
        "asset_class": "A_SHARE_STOCK",
        "available_quantity": float(item["available"]),
        "broker_display_unit_cost": item["broker_cost"],
        "broker_display_unrealized_pnl": item["broker_pnl"],
        "broker_display_unrealized_pnl_pct": item["broker_pct"],
        "broker_verified": False,
        "code": sec,
        "cost_basis": econ_cost,
        "cost_basis_method": "UNIT_COST_TIMES_QUANTITY_ECONOMIC_LEDGER",
        "mark": item["mark"],
        "mark_as_of": AS_OF_SIM,
        "mark_freshness_status": "INTRADAY_USER_CONFIRMED",
        "mark_provider": "USER_CONFIRMED_SIMULATION_SCREENSHOT_INTRADAY",
        "market_value": item["mv"],
        "portfolio_bucket": item["bucket"],
        "position_source_as_of": AS_OF_SIM,
        "position_source_run_id": RUN_ID,
        "quantity": float(item["qty"]),
        "security_id": security_id(sec),
        "security_name": item["name"],
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "unit_cost": item["unit_cost"],
        "unrealized_pnl": round(item["mv"] - econ_cost, 6),
        "unrealized_pnl_pct": round((item["mv"] - econ_cost) / econ_cost, 8),
    })
    if sec == "300012":
        row["target_weight"] = "VALIDATION_POSITION"
        row["t_plus_one_availability"] = "NOT_AVAILABLE_ON_TRADE_DATE"
    if sec == "300124":
        row["target_weight"] = "REDUCED_OBSERVATION_200"
        row["broker_display_cost_semantics"] = "BROKER_BREAK_EVEN_DISPLAY_AFTER_PARTIAL_SALE_NOT_ECONOMIC_COST_OVERRIDE"
    return row


def update_sim_positions(payload: dict[str, Any]) -> None:
    old = {code(row): row for row in payload["holdings"]}
    assert "002463" in old
    rows = [position_row(sec, item, old.get(sec)) for sec, item in SIM_MARKS.items()]
    rows.sort(key=lambda row: row["security_id"])
    payload["holdings"] = rows
    payload.update({
        "formal_eod_snapshot_written": False,
        "orders": 0,
        "schema_version": "1.0.0",
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "state_id": "WP2R_SIMULATION_POSITIONS_CURRENT_20260806_INTRADAY",
        "status": "POSITION_CURRENT_THREE_USER_EXECUTED_SIM_TRADES_INTRADAY_NOT_EOD",
        "trade_authority": "NONE",
        "user_confirmed": True,
    })
    payload["mark_watermark"] = {
        "all_marks_fresh_or_acceptable": True,
        "all_positions_marked": True,
        "latest_mark_date": "2026-08-06",
        "marks_source_id": "USER_CONFIRMED_INTRADAY_20260806",
        "formal_eod": False,
    }
    payload["position_watermark"] = {
        "applied_delta_count": 3,
        "applied_delta_ids": [trade["delta_id"] for trade in TRADES],
        "base_state_as_of": AS_OF_SIM,
        "position_state_current": True,
        "user_delta_continuity_confirmed_through": AS_OF_SIM,
    }
    payload["reconciliation_exceptions"] = [
        {
            "allocation_policy": "DO_NOT_ALLOCATE_TO_ANY_SECURITY",
            "amount": -73.40,
            "exception_id": "SIMULATION_TOP_MARKET_VALUE_MINUS_LINE_SUM_20260806_INTRADAY",
            "status": "OPEN_INTRADAY_PRICE_TIMING_EXCEPTION",
        },
        {
            "allocation_policy": "DO_NOT_ALLOCATE_TO_INDIVIDUAL_TRADE",
            "amount": -33.39,
            "exception_id": "SIMULATION_GROSS_CASH_DELTA_MINUS_BROKER_CASH_DELTA_20260806",
            "status": "AGGREGATE_FEES_AND_TIMING_RECONCILIATION",
        },
    ]
    payload["summary"] = {
        "account_total_assets": 1020846.99,
        "account_total_pnl": 20846.99,
        "broker_display_open_pnl": 31913.83,
        "cash_semantics": "SIMULATION_LEDGER_AVAILABLE_CASH",
        "closed_fee_other_residual": -14071.21,
        "execution_cash_balance": 244332.59,
        "gross_realized_pnl_from_20260806_sales": -5514.00,
        "holding_count": 16,
        "market_value_reconciliation_exception_amount": -73.40,
        "new_confirmed_trades": 3,
        "open_unrealized_pnl": 34918.20,
        "original_capital": 1000000.00,
        "position_cost_basis": 741669.60,
        "position_market_value": 776514.40,
        "position_market_value_line_sum": 776587.80,
        "position_ratio_top_reported": 0.7607,
        "quantity_mutations_from_market_refresh": 0,
        "reconciliation_explanation": "Broker top market value is preserved. CNY -73.40 intraday timing difference and CNY 33.39 aggregate fees/timing are not allocated to securities.",
        "reconciliation_status": "USER_CONFIRMED_INTRADAY_WITH_UNALLOCATED_TIMING_AND_FEE_EXCEPTIONS",
        "top_market_value_reported": 776514.40,
        "top_total_assets_reported": 1020846.99,
        "observed_top_total_assets_range": [1020846.99, 1020917.39],
    }


def source_holding(sec: str, item: dict[str, Any], old: dict[str, Any] | None) -> dict[str, Any]:
    row = dict(old or {})
    econ_cost = round(item["qty"] * item["unit_cost"], 6)
    row.update({
        "as_of": AS_OF_SIM,
        "available_quantity": float(item["available"]),
        "broker_display_holding_pnl": item["broker_pnl"],
        "broker_display_holding_pnl_pct": item["broker_pct"],
        "cost_price": item["unit_cost"],
        "current_weight_pct_of_market_value": round(item["mv"] / 776514.40 * 100, 6),
        "current_weight_pct_of_total_asset": round(item["mv"] / 1020846.99 * 100, 6),
        "data_source": "USER_CONFIRMED_SIMULATION_SCREENSHOT_INTRADAY_20260806",
        "formal_eod_snapshot_written": False,
        "holding_pnl": item["broker_pnl"],
        "holding_pnl_pct": f"{item['broker_pct'] * 100:.2f}%",
        "last_price_close": item["mark"],
        "mark_type": "USER_CONFIRMED_INTRADAY_NOT_CLOSE",
        "market_value": item["mv"],
        "portfolio_bucket": item["bucket"],
        "promotion_status": "USER_CONFIRMED_INTRADAY_PROVISIONAL",
        "quantity": float(item["qty"]),
        "run_id": RUN_ID,
        "schema_version": "3.5.0",
        "security_code": sec,
        "security_name": item["name"],
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "source_as_of": AS_OF_SIM,
        "source_run_id": RUN_ID,
        "source_schema_version": "3.5.0",
        "status_note": "USER_CONFIRMED_POST_TRADE_POSITION",
    })
    if sec == "300124":
        row["broker_display_cost_price"] = 94.07
        row["economic_cost_price"] = 79.02
    if sec == "300012":
        row["broker_display_cost_price"] = 14.09
        row["economic_cost_price"] = 14.08
        row["status_note"] = "NEW_SIMULATION_VALIDATION_POSITION_T_PLUS_ONE_LOCKED"
    return row


def update_sim_source(payload: dict[str, Any]) -> None:
    old = {code(row): row for row in payload["holdings"]}
    payload["holdings"] = [source_holding(sec, item, old.get(sec)) for sec, item in sorted(SIM_MARKS.items())]
    trade_ids = {row.get("delta_id") for row in payload.get("trade_ledger", [])}
    for trade in TRADES:
        if trade["delta_id"] not in trade_ids:
            payload.setdefault("trade_ledger", []).append({
                "account": "SIMULATION",
                "action": trade["action"],
                "amount": trade["amount"],
                "as_of": AS_OF_SIM,
                "date": "2026-08-06",
                "delta_id": trade["delta_id"],
                "note": "User-executed simulation adjustment following Candidate investment review; recorded after execution, not an automated order.",
                "price": trade["price"],
                "promotion_status": "USER_CONFIRMED_INTRADAY_PROVISIONAL",
                "quantity": trade["quantity"],
                "run_id": RUN_ID,
                "schema_version": "3.5.0",
                "security_code": trade["code"],
                "security_name": trade["name"],
                "source_run_id": RUN_ID,
                "source_schema_version": "3.5.0",
                "time": trade["time"],
                "trade_authority": "NONE",
            })
    payload.update({
        "as_of": AS_OF_SIM,
        "formal_eod_snapshot_written": False,
        "orders": 0,
        "schema_version": "1.0.0",
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "state_id": "SIMULATION_USER_CONFIRMED_INTRADAY_20260806",
        "status": "USER_CONFIRMED_INTRADAY_THREE_TRADES_APPLIED_NOT_EOD",
        "trade_authority": "NONE",
    })
    payload["limitations"] = [
        "USER_CONFIRMED_INTRADAY_NOT_FORMAL_EOD",
        "THREE_USER_EXECUTED_SIMULATION_TRADES_APPLIED",
        "TOP_MARKET_VALUE_LINE_SUM_EXCEPTION_NEGATIVE_73_40_UNALLOCATED",
        "AGGREGATE_FEES_AND_TIMING_33_39_NOT_ALLOCATED_TO_INDIVIDUAL_TRADES",
        "LEGACY_TRADE_LEDGER_RETAINED_FOR_HISTORY",
    ]
    payload["summary"] = {
        "account": "SIMULATION",
        "as_of": AS_OF_SIM,
        "available_cash": 244332.59,
        "day_reference_pnl": -3395.49,
        "holding_line_market_value_sum": 776587.80,
        "market_value": 776514.40,
        "market_value_reconciliation_exception_amount": -73.40,
        "new_confirmed_trades": 3,
        "position_pct": "76.07%",
        "position_ratio": 0.7607,
        "pricing_caveat": "User-confirmed intraday snapshot at approximately 11:03 Asia/Shanghai; not a formal EOD close. Two observed top totals differed by CNY 70.40 within seconds.",
        "promotion_status": "USER_CONFIRMED_INTRADAY_PROVISIONAL",
        "run_id": RUN_ID,
        "schema_version": "3.5.0",
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "source_as_of": AS_OF_SIM,
        "source_run_id": RUN_ID,
        "source_schema_version": "3.5.0",
        "total_assets": 1020846.99,
        "total_market_value": 776514.40,
        "total_pnl": 20846.99,
        "trade_action": "TWO_SELLS_ONE_BUY_USER_EXECUTED_AND_RECORDED",
        "trade_status": "USER_CONFIRMED_EXECUTED_NO_AUTOMATED_ORDER",
    }
    payload.setdefault("source_bindings", []).append({
        "as_of": AS_OF_SIM,
        "formal_eod": False,
        "role": "USER_CONFIRMED_INTRADAY_SIMULATION_POST_TRADE_SOURCE",
        "run_id": RUN_ID,
    })


def update_confirmations(payload: dict[str, Any]) -> None:
    confirmations = {row.get("confirmation_id"): row for row in payload.get("confirmations", [])}
    rows = [
        {"confirmation_id": "CONF_REAL_605090_SECOND_4950_SETTLED_20260806", "account": "REAL", "confirmation_type": "POSITION_SETTLEMENT", "security_id": "605090.SH", "quantity": 4950, "status": "CONFIRMED_BY_USER", "as_of": AS_OF_REAL},
        {"confirmation_id": "CONF_REAL_NO_OTHER_CHANGES_THROUGH_20260806_1102", "account": "REAL", "confirmation_type": "POSITION_CONTINUITY", "status": "CONFIRMED_BY_USER", "as_of": AS_OF_REAL},
    ]
    rows.extend({
        "confirmation_id": f"CONF_{trade['delta_id']}", "account": "SIMULATION", "confirmation_type": "EXECUTED_TRADE",
        "security_id": security_id(trade["code"]), "action": trade["action"], "quantity": trade["quantity"],
        "price": trade["price"], "status": "CONFIRMED_BY_USER", "as_of": f"2026-08-06T{trade['time']}+08:00",
    } for trade in TRADES)
    for row in rows:
        row.update({"evidence": "USER_UPLOADED_SCREENSHOT", "trade_authority": "NONE"})
        confirmations[row["confirmation_id"]] = row
    payload.update({
        "as_of": AS_OF_SIM,
        "confirmations": list(confirmations.values()),
        "execution_authority": "USER_MANUAL_ONLY",
        "limitations": ["INTRADAY_NOT_FORMAL_EOD", "NO_AUTOMATED_ORDER_AUTHORITY"],
        "schema_version": "1.0.0",
        "state_id": "USER_CONFIRMATIONS_CURRENT_20260806",
        "status": "FIVE_CURRENT_USER_CONFIRMATIONS_RECORDED",
        "trade_authority": "NONE",
        "orders": 0,
    })


def candidate_review() -> dict[str, Any]:
    candidate = read(P["candidate"])
    weekly = read(P["weekly"])
    return {
        "schema_version": "1.0.0",
        "state_id": "CANDIDATE_ACTION_REVIEW_CURRENT_20260806",
        "as_of": AS_OF_SIM,
        "snapshot_type": "USER_CONFIRMED_INTRADAY_PORTFOLIO_LINKAGE",
        "candidate_market_watermark": "2026-08-05_CLOSE",
        "candidate_counts": candidate["counts"],
        "weekly_screen_covered_count": weekly["covered_count"],
        "candidate_membership_mutations": 0,
        "research_object_mutations": 0,
        "ready_for_user_decision_mutations": 0,
        "portfolio_linkages": [
            {
                "security_id": "300012.SZ", "security_name": "华测检测", "candidate_route": "SHADOW_TRACK_MEMBERS",
                "simulation_position": {"quantity": 1000, "entry_price": 14.08, "status": "USER_EXECUTED_VALIDATION_POSITION"},
                "candidate_admission_change": "NONE", "real_account_permission": False, "ready_for_user_decision": False,
            },
            {
                "security_id": "300124.SZ", "security_name": "汇川技术", "portfolio_action": "SIMULATION_REDUCED_400_TO_200",
                "candidate_membership_change": "NONE",
            },
            {
                "security_id": "002463.SZ", "security_name": "沪电股份", "portfolio_action": "SIMULATION_EXITED_200_TO_ZERO",
                "candidate_membership_change": "NONE",
            },
        ],
        "market_data_treatment": "DO_NOT_OVERWRITE_20260805_COMPLETED_CLOSE_WITH_20260806_INTRADAY",
        "orders": 0,
        "trade_authority": "NONE",
        "status": "PASS_PORTFOLIO_LINKAGE_ONLY_CANDIDATE_CANONICAL_UNCHANGED",
    }


def build_evidence() -> None:
    protected = [P["candidate"], P["weekly"], P["decision_proposals"], P["portfolio_decision"]]
    baseline = {
        "schema_version": "1.0.0",
        "baseline_commit": MAIN_BEFORE,
        "protected_files": [{"path": str(path.relative_to(ROOT)), "git_blob_sha": git_blob_sha(path), "expected_mutation": False} for path in protected],
        "candidate_membership_mutations": 0,
        "decision_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    write(P["baseline"], baseline)
    evidence = {
        "schema_version": "1.0.0",
        "evidence_id": RUN_ID,
        "captured_at": AS_OF_SIM,
        "canonical_commit_before": MAIN_BEFORE,
        "canonical_commit_after": "PENDING_PR_MERGE",
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "eod_status": "NOT_EOD_DO_NOT_APPEND_TO_FORMAL_EOD_SERIES",
        "input_evidence": [{"type": "USER_UPLOADED_BROKER_SCREENSHOT", "status": "AVAILABLE_AND_INSPECTED", "count": 8}],
        "confirmed_deltas": ["REAL_605090_SECOND_4950_SETTLEMENT_20260806"] + [trade["delta_id"] for trade in TRADES],
        "real_account": {"ordinary_605090_quantity": 9900, "pending_605090_quantity": 0, "other_position_changes": 0, "account_total_assets_intraday": 790928.83},
        "simulation": {"trades": TRADES, "holding_count_after": 16, "cash_after": 244332.59, "total_assets_intraday": 1020846.99},
        "candidate": {"membership_mutations": 0, "market_watermark_preserved": "2026-08-05_CLOSE", "portfolio_linkage_recorded": True},
        "exceptions": [
            {"id": "REAL_INTRADAY_STOCK_LINE_TIMING", "amount": -71.90, "status": "OPEN_UNALLOCATED"},
            {"id": "SIM_INTRADAY_MARKET_VALUE_LINE_TIMING", "amount": -73.40, "status": "OPEN_UNALLOCATED"},
            {"id": "SIM_AGGREGATE_FEES_AND_TIMING", "amount": 33.39, "status": "RECORDED_NOT_ALLOCATED"},
            {"id": "REAL_605090_TAX_AND_FEES", "status": "OPEN"},
        ],
        "non_mutation_scope": {"candidate_membership": "UNCHANGED", "formal_decisions": "UNCHANGED", "orders": 0, "trade_authority": "NONE"},
    }
    write(P["evidence"], evidence)
    common = {
        "run_id": RUN_ID,
        "as_of": AS_OF_SIM,
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "formal_eod": False,
        "canonical_commit_before": MAIN_BEFORE,
        "canonical_commit_after": "PENDING_PR_MERGE",
        "candidate_mutations": 0,
        "decision_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    write(P["status"], {**common, "product_type": "POSITION_UPDATE_STATUS", "status": "PASS_USER_CONFIRMED_DELTAS_APPLIED_INTRADAY_NOT_EOD", "next_gate": "PR_VALIDATION_AND_HUMAN_MERGE"})
    write(P["run_manifest"], {**common, "manifest_type": "RUN_MANIFEST", "status": "PASS_PENDING_REMOTE_GATES", "inputs": ["8_USER_UPLOADED_SCREENSHOTS", "USER_CONFIRMATION_IN_CHAT"], "outputs": [str(path.relative_to(ROOT)) for path in [P["real_source"], P["real"], P["equity"], P["delta"], P["sim_source"], P["sim"], P["candidate_review"], P["confirmations"]]]})
    write(P["report_manifest"], {**common, "manifest_type": "REPORT_MANIFEST", "status": "INTRADAY_POSITION_UPDATE_NOT_PERIODIC_REPORT", "publication_boundary": "DO_NOT_TREAT_AS_EOD", "evidence_path": str(P["evidence"].relative_to(ROOT))})


def main() -> None:
    real_source, real = read(P["real_source"]), read(P["real"])
    equity, delta = read(P["equity"]), read(P["delta"])
    sim_source, sim = read(P["sim_source"]), read(P["sim"])
    confirmations = read(P["confirmations"])

    update_real_source(real_source)
    update_real_positions(real)
    update_equity(equity)
    update_delta(delta)
    update_sim_source(sim_source)
    update_sim_positions(sim)
    update_confirmations(confirmations)

    write(P["real_source"], real_source)
    write(P["real"], real)
    write(P["equity"], equity)
    write(P["delta"], delta)
    write(P["sim_source"], sim_source)
    write(P["sim"], sim)
    write(P["confirmations"], confirmations)
    write(P["candidate_review"], candidate_review())
    build_evidence()

    print(json.dumps({
        "status": "PASS",
        "real_605090_quantity": 9900,
        "simulation_trades_applied": 3,
        "simulation_holding_count": 16,
        "candidate_membership_mutations": 0,
        "formal_eod_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
