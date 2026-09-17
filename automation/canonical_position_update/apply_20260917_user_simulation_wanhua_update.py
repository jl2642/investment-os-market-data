#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "POSITION_UPDATE_20260917_USER_SIMULATION_WANHUA_INTRADAY"
AS_OF = "2026-09-17T13:49:00+08:00"
TRADE_DATE = "2026-09-17"
CASH = 240388.34
TRADE = {
    "delta_id": "SIM_20260917_BUY_600309_100",
    "action": "BUY",
    "security_id": "600309.SH",
    "security_code": "600309",
    "security_name": "万华化学",
    "quantity": 100,
    "price": 70.59,
    "gross_amount": 7059.0,
    "execution_time": "2026-09-17T13:48:56+08:00",
}
TARGET_QUANTITY = 800.0
TARGET_AVAILABLE = 700.0
PRIOR_QUANTITY = 700.0
PRIOR_ECONOMIC_COST_BASIS = 49007.0
TARGET_ECONOMIC_COST_BASIS = 56066.0
TARGET_ECONOMIC_UNIT_COST = TARGET_ECONOMIC_COST_BASIS / TARGET_QUANTITY
BROKER_DISPLAY_COST_PRICE = 69.38

P = {
    "sim_source": ROOT / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_LEDGER_CURRENT.json",
    "sim": ROOT / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json",
    "delta": ROOT / "investment_os_runtime/30_STATE_CURRENT/15_PORTFOLIO_INPUT/USER_TRANSACTION_DELTA_LEDGER_CURRENT.json",
    "evidence": ROOT / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/POSITION_UPDATE_2026_09_17/USER_CONFIRMED_SIMULATION_WANHUA_TRADE_20260917.json",
}


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def sid_of(row: dict[str, Any]) -> str:
    sid = str(row.get("security_id") or "")
    if sid:
        return sid
    code = str(row.get("security_code") or row.get("code") or "").zfill(6)
    return f"{code}.SH" if code.startswith(("5", "6", "9")) else f"{code}.SZ"


def update_positions_current(payload: dict[str, Any]) -> None:
    by_sid = {sid_of(row): row for row in payload["holdings"]}
    row = by_sid[TRADE["security_id"]]
    old_qty = float(row.get("quantity") or 0.0)
    assert old_qty in {PRIOR_QUANTITY, TARGET_QUANTITY}, f"unexpected prior Wanhua quantity: {old_qty}"
    if old_qty == PRIOR_QUANTITY:
        assert abs(float(row.get("cost_basis") or 0.0) - PRIOR_ECONOMIC_COST_BASIS) < 1e-6
    row["quantity"] = TARGET_QUANTITY
    row["available_quantity"] = TARGET_AVAILABLE
    row["cost_basis"] = TARGET_ECONOMIC_COST_BASIS
    row["unit_cost"] = TARGET_ECONOMIC_UNIT_COST
    row["position_source_as_of"] = AS_OF
    row["position_source_run_id"] = RUN_ID
    row["snapshot_type"] = "USER_CONFIRMED_INTRADAY_POSITION_UPDATE"
    mark = float(row.get("mark") or 0.0)
    row["market_value"] = round(mark * TARGET_QUANTITY, 6)
    row["unrealized_pnl"] = round(row["market_value"] - row["cost_basis"], 6)
    row["unrealized_pnl_pct"] = round(row["unrealized_pnl"] / row["cost_basis"], 8) if row["cost_basis"] else 0.0

    summary = payload["summary"]
    position_mv = round(sum(float(r.get("market_value") or 0.0) for r in payload["holdings"]), 6)
    cost_basis = round(sum(float(r.get("cost_basis") or 0.0) for r in payload["holdings"]), 6)
    total_assets = round(position_mv + CASH, 6)
    summary["execution_cash_balance"] = CASH
    summary["position_market_value"] = position_mv
    summary["position_cost_basis"] = cost_basis
    summary["open_unrealized_pnl"] = round(position_mv - cost_basis, 6)
    summary["account_total_assets"] = total_assets
    summary["account_total_pnl"] = round(total_assets - float(summary.get("original_capital") or 1_000_000.0), 6)
    if summary.get("historical_wp2_3_total_assets") is not None:
        summary["difference_vs_historical_wp2_3"] = round(total_assets - float(summary["historical_wp2_3_total_assets"]), 6)
    summary["position_update_note"] = (
        "Wanhua quantity/cash reflect the user-confirmed 2026-09-17 intraday Simulation buy; retained marks are not promoted to completed-close decision marks."
    )

    pwm = payload.setdefault("position_watermark", {})
    ids = list(pwm.get("applied_delta_ids") or [])
    if TRADE["delta_id"] not in ids:
        ids.append(TRADE["delta_id"])
    pwm["base_state_as_of"] = AS_OF
    pwm["position_state_current"] = True
    pwm["user_delta_continuity_confirmed_through"] = AS_OF
    pwm["applied_delta_ids"] = ids
    pwm["applied_delta_count"] = len(ids)
    payload["status"] = "POSITION_CURRENT_USER_CONFIRMED_20260917_WANHUA_MARKS_RETAINED_PENDING_EOD"
    payload["trade_authority"] = "NONE"


def update_source_ledger(payload: dict[str, Any]) -> None:
    by_sid = {sid_of(row): row for row in payload["holdings"]}
    row = by_sid[TRADE["security_id"]]
    old_qty = float(row.get("quantity") or 0.0)
    assert old_qty in {PRIOR_QUANTITY, TARGET_QUANTITY}, f"unexpected source Wanhua quantity: {old_qty}"
    row["as_of"] = AS_OF
    row["source_as_of"] = AS_OF
    row["run_id"] = RUN_ID
    row["source_run_id"] = RUN_ID
    row["data_source"] = "USER_CONFIRMED_SIMULATION_SCREENSHOT_INTRADAY_20260917"
    row["snapshot_type"] = "USER_CONFIRMED_INTRADAY_POSITION_AND_TRANSACTION_SNAPSHOT"
    row["promotion_status"] = "USER_CONFIRMED_RECONCILED_BASELINE"
    row["status_note"] = "USER_CONFIRMED_CURRENT_POSITION_AFTER_REPORTED_TRADE"
    row["formal_eod_snapshot_written"] = False
    row["mark_type"] = "RETAINED_PRIOR_MARK_PENDING_NEXT_EOD_REFRESH"
    row["quantity"] = int(TARGET_QUANTITY)
    row["available_quantity"] = int(TARGET_AVAILABLE)
    row["broker_display_cost_price"] = BROKER_DISPLAY_COST_PRICE
    row["cost_price"] = BROKER_DISPLAY_COST_PRICE
    row["economic_cost_price"] = TARGET_ECONOMIC_UNIT_COST
    price = float(row.get("last_price_close") or 0.0)
    mv = round(price * TARGET_QUANTITY, 6)
    row["market_value"] = mv
    display_basis = BROKER_DISPLAY_COST_PRICE * TARGET_QUANTITY
    row["holding_pnl"] = round(mv - display_basis, 6)
    row["broker_display_holding_pnl"] = row["holding_pnl"]
    pct = row["holding_pnl"] / display_basis if display_basis else 0.0
    row["holding_pnl_pct"] = f"{pct:.2%}"
    row["broker_display_holding_pnl_pct"] = round(pct, 6)

    retained_mv = round(sum(float(r.get("market_value") or 0.0) for r in payload["holdings"]), 6)
    retained_total = round(retained_mv + CASH, 6)
    for h in payload["holdings"]:
        hmv = float(h.get("market_value") or 0.0)
        h["current_weight_pct_of_market_value"] = round(100.0 * hmv / retained_mv, 6) if retained_mv else 0.0
        h["current_weight_pct_of_total_asset"] = round(100.0 * hmv / retained_total, 6) if retained_total else 0.0

    payload["as_of"] = AS_OF
    payload["state_id"] = "SIMULATION_USER_CONFIRMED_INTRADAY_20260917_WANHUA"
    payload["status"] = "USER_CONFIRMED_INTRADAY_RECONCILED_WITH_WANHUA_TRADE"
    payload["snapshot_type"] = "USER_CONFIRMED_INTRADAY_POSITION_AND_TRANSACTION_SNAPSHOT"
    payload["orders"] = 0
    payload["trade_authority"] = "NONE"
    limitations = payload.setdefault("limitations", [])
    for value in [
        "INTRADAY_PRICES_NOT_PROMOTED_TO_COMPLETED_CLOSE",
        "POSITION_QUANTITIES_AND_REPORTED_TRADES_ARE_USER_AUTHORITY",
        "TRANSACTION_COST_COMPONENTS_NOT_SEPARATELY_CONFIRMED",
        "CASH_RECONCILIATION_COMPONENTS_NOT_SEPARATELY_ATTRIBUTED",
    ]:
        if value not in limitations:
            limitations.append(value)

    bindings = payload.setdefault("source_bindings", [])
    if not any(x.get("run_id") == RUN_ID for x in bindings if isinstance(x, dict)):
        bindings.append({
            "as_of": AS_OF,
            "formal_eod": False,
            "role": "USER_CONFIRMED_20260917_SIMULATION_WANHUA_POSITION_AND_TRADE_SOURCE",
            "run_id": RUN_ID,
            "evidence": "USER_UPLOADED_SIMULATION_HOLDINGS_AND_TRANSACTION_SCREENSHOTS",
        })

    trade_ledger = payload.setdefault("trade_ledger", [])
    existing = {str(x.get("delta_id")) for x in trade_ledger if isinstance(x, dict)}
    if TRADE["delta_id"] not in existing:
        trade_ledger.append({
            "account": "SIMULATION",
            "action": TRADE["action"],
            "amount": TRADE["gross_amount"],
            "as_of": AS_OF,
            "date": TRADE_DATE,
            "delta_id": TRADE["delta_id"],
            "note": "User-executed ordinary Simulation Wanhua trade after Phase3 recommendation; recorded after execution, not an automated order.",
            "price": TRADE["price"],
            "promotion_status": "USER_CONFIRMED_INTRADAY_MATERIALIZED",
            "quantity": TRADE["quantity"],
            "run_id": RUN_ID,
            "schema_version": "3.6.0",
            "security_code": TRADE["security_code"],
            "security_name": TRADE["security_name"],
            "source_run_id": RUN_ID,
            "source_schema_version": "3.6.0",
            "time": "13:48:56",
            "trade_authority": "NONE",
        })

    summary = payload["summary"]
    summary.update({
        "account": "SIMULATION",
        "as_of": AS_OF,
        "available_cash": CASH,
        "holding_line_market_value_sum": retained_mv,
        "market_value": retained_mv,
        "total_market_value": retained_mv,
        "total_assets": retained_total,
        "new_confirmed_trades": 1,
        "position_ratio": round(retained_mv / retained_total, 8) if retained_total else 0.0,
        "position_pct": f"{retained_mv / retained_total:.2%}" if retained_total else "0.00%",
        "promotion_status": "USER_CONFIRMED_RECONCILED_BASELINE",
        "run_id": RUN_ID,
        "source_as_of": AS_OF,
        "source_run_id": RUN_ID,
        "snapshot_type": "USER_CONFIRMED_INTRADAY_POSITION_AND_TRANSACTION_SNAPSHOT",
        "trade_action": "USER_EXECUTED_WANHUA_SIMULATION_BUY",
        "trade_status": "MATERIALIZED_TO_SIMULATION_CURRENT",
        "pricing_caveat": "Position quantity, transaction price, displayed cost and cash are user-confirmed. Per-security valuation fields retain prior accepted display marks until the next governed market refresh.",
        "cash_reconciliation_note": "Broker simulation available cash CNY 240388.34 is authoritative. The difference versus prior-cash-minus-gross-trade arithmetic is not attributed without separate fee evidence.",
    })


def update_delta_ledger(payload: dict[str, Any]) -> None:
    entries = payload.setdefault("entries", [])
    existing = {str(x.get("delta_id")) for x in entries if isinstance(x, dict)}
    if TRADE["delta_id"] not in existing:
        entries.append({
            "account": "SIMULATION",
            "action": TRADE["action"],
            "application_decision": "ALREADY_APPLIED_TO_POSITION_CURRENT_DO_NOT_REAPPLY",
            "applied_run_id": RUN_ID,
            "confirmation_authority": "USER",
            "delta_id": TRADE["delta_id"],
            "event_type": "SIMULATION_TRADE",
            "evidence_status": "USER_SCREENSHOT_CONFIRMED",
            "execution_time": TRADE["execution_time"],
            "gross_amount": TRADE["gross_amount"],
            "note": "User-executed ordinary Simulation Wanhua trade recorded from transaction and holdings screenshots; canonical Simulation source and Position Current already include this delta.",
            "orders": 0,
            "position_engine_treatment": "SOURCE_BASELINE_ALREADY_CONTAINS_DELTA",
            "price": TRADE["price"],
            "quantity": TRADE["quantity"],
            "quantity_delta": TRADE["quantity"],
            "rejection_reason": "Economic event is materialized in the canonical Simulation source baseline; reapplying it would double count the trade.",
            "security_code": TRADE["security_code"],
            "security_id": TRADE["security_id"],
            "security_name": TRADE["security_name"],
            "status": "REJECTED",
            "trade_authority": "NONE",
            "trade_date": TRADE_DATE,
        })
    mids = payload.setdefault("materialized_delta_ids", [])
    if TRADE["delta_id"] not in mids:
        mids.append(TRADE["delta_id"])
    payload["as_of"] = AS_OF
    payload["orders"] = 0
    payload["trade_authority"] = "NONE"


def build_evidence() -> dict[str, Any]:
    return {
        "account": "SIMULATION",
        "as_of": AS_OF,
        "authority": "USER_UPLOADED_SCREENSHOTS",
        "cash_after_trade": CASH,
        "decision_context": {
            "phase3_action": "ADD",
            "phase3_validated_quantity": 100,
            "system_reference_price": 70.78,
            "execution_status": "USER_EXECUTED",
        },
        "intraday_valuation_policy": "SCREENSHOT_INTRADAY_MARKS_RECORDED_AS_EVIDENCE_ONLY_NOT_PROMOTED_TO_DECISION_GRADE_CLOSE_MARKS",
        "orders": 0,
        "position_after_trade": {
            "security_id": "600309.SH",
            "security_name": "万华化学",
            "quantity": 800,
            "available_quantity": 700,
            "broker_display_cost_price": BROKER_DISPLAY_COST_PRICE,
        },
        "screenshots": {
            "holding_snapshot_time": "13:49",
            "transaction_snapshot_time": "13:48:56",
            "observed_total_assets_range": [992430.54, 992477.44],
            "observed_available_cash": CASH,
            "note": "Total assets differed slightly across consecutive screenshots because intraday marks moved; private economic facts used for writeback are quantity, availability, cash and executed transaction.",
        },
        "status": "PASS_USER_CONFIRMED_SIMULATION_TRADE",
        "trade": TRADE,
        "trade_authority": "NONE",
    }


def main() -> None:
    sim_source = read(P["sim_source"])
    sim = read(P["sim"])
    delta = read(P["delta"])
    update_source_ledger(sim_source)
    update_positions_current(sim)
    update_delta_ledger(delta)
    write(P["sim_source"], sim_source)
    write(P["sim"], sim)
    write(P["delta"], delta)
    write(P["evidence"], build_evidence())
    print({
        "status": "PASS",
        "delta_id": TRADE["delta_id"],
        "security_id": TRADE["security_id"],
        "quantity": TARGET_QUANTITY,
        "available_quantity": TARGET_AVAILABLE,
        "cash": CASH,
        "orders": 0,
        "trade_authority": "NONE",
    })


if __name__ == "__main__":
    main()
