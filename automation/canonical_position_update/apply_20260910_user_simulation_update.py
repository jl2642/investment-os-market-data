#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "POSITION_UPDATE_20260910_USER_SIMULATION_INTRADAY"
AS_OF = "2026-09-10T13:17:00+08:00"
CASH = 269057.64

P = {
    "sim_source": ROOT / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_LEDGER_CURRENT.json",
    "sim": ROOT / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json",
    "delta": ROOT / "investment_os_runtime/30_STATE_CURRENT/15_PORTFOLIO_INPUT/USER_TRANSACTION_DELTA_LEDGER_CURRENT.json",
    "evidence": ROOT / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/POSITION_UPDATE_2026_09_10/USER_CONFIRMED_SIMULATION_TRADES_20260910.json",
}

TRADES = [
    {
        "delta_id": "SIM_20260910_SELL_600941_400",
        "action": "SELL",
        "security_id": "600941.SH",
        "security_code": "600941",
        "security_name": "中国移动",
        "quantity": 400,
        "price": 97.34,
        "gross_amount": 38936.0,
        "execution_time": "2026-09-10T13:00:00+08:00",
    },
    {
        "delta_id": "SIM_20260910_BUY_300124_300",
        "action": "BUY",
        "security_id": "300124.SZ",
        "security_code": "300124",
        "security_name": "汇川技术",
        "quantity": 300,
        "price": 54.65,
        "gross_amount": 16395.0,
        "execution_time": "2026-09-10T13:00:01+08:00",
    },
]

POSITION_TARGETS = {
    "300124.SZ": {
        "quantity": 500.0,
        "available_quantity": 200.0,
        "economic_cost_basis": 32199.0,
        "economic_unit_cost": 64.398,
        "broker_display_cost_price": 70.43,
    },
    "600941.SH": {
        "quantity": 300.0,
        "available_quantity": 300.0,
        "economic_cost_basis": 26091.0,
        "economic_unit_cost": 86.97,
        "broker_display_cost_price": 73.23,
    },
}

EXPECTED_QUANTITIES = {
    "000333.SZ": 800.0,
    "300012.SZ": 1000.0,
    "300124.SZ": 500.0,
    "300750.SZ": 100.0,
    "510500.SH": 7100.0,
    "600036.SH": 1600.0,
    "600276.SH": 800.0,
    "600309.SH": 700.0,
    "600406.SH": 1800.0,
    "600660.SH": 1600.0,
    "600690.SH": 1800.0,
    "600900.SH": 2200.0,
    "600938.SH": 1800.0,
    "600941.SH": 300.0,
    "601138.SH": 600.0,
    "601899.SH": 1000.0,
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
    assert set(EXPECTED_QUANTITIES) == set(by_sid), "unexpected Simulation holding set"
    for sid, target in POSITION_TARGETS.items():
        row = by_sid[sid]
        old_qty = float(row.get("quantity") or 0.0)
        if sid == "300124.SZ":
            assert old_qty in {200.0, 500.0}
        else:
            assert old_qty in {700.0, 300.0}
        row["quantity"] = target["quantity"]
        row["available_quantity"] = target["available_quantity"]
        row["cost_basis"] = target["economic_cost_basis"]
        row["unit_cost"] = target["economic_unit_cost"]
        row["position_source_as_of"] = AS_OF
        row["position_source_run_id"] = RUN_ID
        row["snapshot_type"] = "USER_CONFIRMED_INTRADAY_POSITION_UPDATE"
        mark = float(row.get("mark") or 0.0)
        row["market_value"] = round(mark * target["quantity"], 6)
        row["unrealized_pnl"] = round(row["market_value"] - row["cost_basis"], 6)
        row["unrealized_pnl_pct"] = round(row["unrealized_pnl"] / row["cost_basis"], 8) if row["cost_basis"] else 0.0

    for sid, qty in EXPECTED_QUANTITIES.items():
        assert float(by_sid[sid]["quantity"]) == qty

    summary = payload["summary"]
    position_mv = round(sum(float(r.get("market_value") or 0.0) for r in payload["holdings"]), 6)
    cost_basis = round(sum(float(r.get("cost_basis") or 0.0) for r in payload["holdings"]), 6)
    open_pnl = round(position_mv - cost_basis, 6)
    total_assets = round(position_mv + CASH, 6)
    summary["execution_cash_balance"] = CASH
    summary["position_market_value"] = position_mv
    summary["position_cost_basis"] = cost_basis
    summary["open_unrealized_pnl"] = open_pnl
    summary["account_total_assets"] = total_assets
    summary["account_total_pnl"] = round(total_assets - float(summary.get("original_capital") or 1_000_000.0), 6)
    if summary.get("historical_wp2_3_total_assets") is not None:
        summary["difference_vs_historical_wp2_3"] = round(total_assets - float(summary["historical_wp2_3_total_assets"]), 6)
    summary["position_update_note"] = "Quantities/cash reflect user-confirmed 2026-09-10 intraday trades; retained marks are not promoted to completed-close decision marks."

    pwm = payload.setdefault("position_watermark", {})
    pwm["base_state_as_of"] = AS_OF
    pwm["position_state_current"] = True
    pwm["user_delta_continuity_confirmed_through"] = AS_OF
    pwm["applied_delta_count"] = 2
    pwm["applied_delta_ids"] = [t["delta_id"] for t in TRADES]
    payload["status"] = "POSITION_CURRENT_USER_CONFIRMED_20260910_MARKS_RETAINED_PENDING_EOD"
    payload["trade_authority"] = "NONE"


def update_source_ledger(payload: dict[str, Any]) -> None:
    by_sid = {sid_of(row): row for row in payload["holdings"]}
    for sid, target in POSITION_TARGETS.items():
        row = by_sid[sid]
        row["as_of"] = AS_OF
        row["source_as_of"] = AS_OF
        row["run_id"] = RUN_ID
        row["source_run_id"] = RUN_ID
        row["data_source"] = "USER_CONFIRMED_SIMULATION_SCREENSHOT_INTRADAY_20260910"
        row["snapshot_type"] = "USER_CONFIRMED_INTRADAY_POSITION_AND_TRANSACTION_SNAPSHOT"
        row["promotion_status"] = "USER_CONFIRMED_RECONCILED_BASELINE"
        row["status_note"] = "USER_CONFIRMED_CURRENT_POSITION_AFTER_REPORTED_TRADE"
        row["formal_eod_snapshot_written"] = False
        row["mark_type"] = "RETAINED_PRIOR_MARK_PENDING_NEXT_EOD_REFRESH"
        row["quantity"] = int(target["quantity"])
        row["available_quantity"] = int(target["available_quantity"])
        row["broker_display_cost_price"] = target["broker_display_cost_price"]
        row["cost_price"] = target["broker_display_cost_price"]
        row["economic_cost_price"] = target["economic_unit_cost"]
        price = float(row.get("last_price_close") or 0.0)
        mv = round(price * target["quantity"], 6)
        row["market_value"] = mv
        display_basis = target["broker_display_cost_price"] * target["quantity"]
        row["holding_pnl"] = round(mv - display_basis, 6)
        row["broker_display_holding_pnl"] = row["holding_pnl"]
        pct = row["holding_pnl"] / display_basis if display_basis else 0.0
        row["holding_pnl_pct"] = f"{pct:.2%}"
        row["broker_display_holding_pnl_pct"] = round(pct, 6)

    retained_mv = round(sum(float(r.get("market_value") or 0.0) for r in payload["holdings"]), 6)
    retained_total = round(retained_mv + CASH, 6)
    for row in payload["holdings"]:
        mv = float(row.get("market_value") or 0.0)
        row["current_weight_pct_of_market_value"] = round(100.0 * mv / retained_mv, 6) if retained_mv else 0.0
        row["current_weight_pct_of_total_asset"] = round(100.0 * mv / retained_total, 6) if retained_total else 0.0

    payload["as_of"] = AS_OF
    payload["state_id"] = "SIMULATION_USER_CONFIRMED_INTRADAY_20260910"
    payload["status"] = "USER_CONFIRMED_INTRADAY_RECONCILED_WITH_2_TRADES"
    payload["snapshot_type"] = "USER_CONFIRMED_INTRADAY_POSITION_AND_TRANSACTION_SNAPSHOT"
    payload["orders"] = 0
    payload["trade_authority"] = "NONE"
    limitations = payload.setdefault("limitations", [])
    for value in [
        "INTRADAY_PRICES_NOT_PROMOTED_TO_COMPLETED_CLOSE",
        "POSITION_QUANTITIES_AND_REPORTED_TRADES_ARE_USER_AUTHORITY",
        "TRANSACTION_COST_COMPONENTS_NOT_SEPARATELY_CONFIRMED",
    ]:
        if value not in limitations:
            limitations.append(value)

    bindings = payload.setdefault("source_bindings", [])
    if not any(x.get("run_id") == RUN_ID for x in bindings if isinstance(x, dict)):
        bindings.append({
            "as_of": AS_OF,
            "formal_eod": False,
            "role": "USER_CONFIRMED_20260910_SIMULATION_POSITION_AND_TRADE_SOURCE",
            "run_id": RUN_ID,
            "evidence": "USER_UPLOADED_SIMULATION_HOLDINGS_AND_TRANSACTION_SCREENSHOTS",
        })

    trade_ledger = payload.setdefault("trade_ledger", [])
    existing = {str(x.get("delta_id")) for x in trade_ledger if isinstance(x, dict)}
    for trade in TRADES:
        if trade["delta_id"] in existing:
            continue
        trade_ledger.append({
            "account": "SIMULATION",
            "action": trade["action"],
            "amount": trade["gross_amount"],
            "as_of": AS_OF,
            "date": "2026-09-10",
            "delta_id": trade["delta_id"],
            "note": "User-executed ordinary Simulation trade after Phase3 recommendation; recorded after execution, not an automated order.",
            "price": trade["price"],
            "promotion_status": "USER_CONFIRMED_INTRADAY_MATERIALIZED",
            "quantity": trade["quantity"],
            "run_id": RUN_ID,
            "schema_version": "3.6.0",
            "security_code": trade["security_code"],
            "security_name": trade["security_name"],
            "source_run_id": RUN_ID,
            "source_schema_version": "3.6.0",
            "time": trade["execution_time"][11:19],
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
        "new_confirmed_trades": 2,
        "position_ratio": round(retained_mv / retained_total, 8) if retained_total else 0.0,
        "position_pct": f"{retained_mv / retained_total:.2%}" if retained_total else "0.00%",
        "promotion_status": "USER_CONFIRMED_RECONCILED_BASELINE",
        "run_id": RUN_ID,
        "source_as_of": AS_OF,
        "source_run_id": RUN_ID,
        "snapshot_type": "USER_CONFIRMED_INTRADAY_POSITION_AND_TRANSACTION_SNAPSHOT",
        "trade_action": "USER_EXECUTED_2_SIMULATION_TRADES",
        "trade_status": "MATERIALIZED_TO_SIMULATION_CURRENT",
        "pricing_caveat": "Position quantities, transaction prices and cash are user-confirmed. Per-security valuation fields retain the prior accepted display marks until the next completed-close refresh and are not decision-grade intraday marks.",
        "cash_reconciliation_note": "Broker simulation available cash CNY 269057.64 is authoritative; the CNY 32.65 difference versus gross trade cash arithmetic is left unallocated because fees/charges were not separately confirmed.",
    })


def update_delta_ledger(payload: dict[str, Any]) -> None:
    entries = payload.setdefault("entries", [])
    existing = {str(x.get("delta_id")) for x in entries if isinstance(x, dict)}
    for trade in TRADES:
        if trade["delta_id"] in existing:
            continue
        entries.append({
            "account": "SIMULATION",
            "action": trade["action"],
            "application_decision": "ALREADY_APPLIED_TO_POSITION_CURRENT_DO_NOT_REAPPLY",
            "applied_run_id": RUN_ID,
            "confirmation_authority": "USER",
            "delta_id": trade["delta_id"],
            "event_type": "SIMULATION_TRADE",
            "evidence_status": "USER_SCREENSHOT_CONFIRMED",
            "execution_time": trade["execution_time"],
            "gross_amount": trade["gross_amount"],
            "note": "User-executed ordinary Simulation trade recorded from transaction screenshot; canonical Simulation source and Position Current already include this delta.",
            "orders": 0,
            "position_engine_treatment": "SOURCE_BASELINE_ALREADY_CONTAINS_DELTA",
            "price": trade["price"],
            "quantity": trade["quantity"],
            "quantity_delta": trade["quantity"] if trade["action"] == "BUY" else -trade["quantity"],
            "rejection_reason": "Economic event is materialized in the canonical Simulation source baseline; reapplying it would double count the trade.",
            "security_code": trade["security_code"],
            "security_id": trade["security_id"],
            "security_name": trade["security_name"],
            "status": "REJECTED",
            "trade_authority": "NONE",
            "trade_date": "2026-09-10",
        })
    mids = payload.setdefault("materialized_delta_ids", [])
    for trade in TRADES:
        if trade["delta_id"] not in mids:
            mids.append(trade["delta_id"])
    payload["applied_delta_count"] = len(mids)
    payload["rejected_for_position_engine_count"] = sum(1 for x in entries if x.get("status") == "REJECTED")
    payload["unapplied_delta_count"] = 0
    payload["as_of"] = AS_OF
    payload["continuity_confirmed_through"] = AS_OF
    payload["ledger_id"] = "USER_TRANSACTION_DELTA_LEDGER_CURRENT_20260910"
    payload["status"] = "USER_CONFIRMED_CONTINUITY_CURRENT_NO_UNAPPLIED_DELTAS"
    payload["orders"] = 0
    payload["trade_authority"] = "NONE"


def build_evidence() -> dict[str, Any]:
    return {
        "run_id": RUN_ID,
        "as_of": AS_OF,
        "account": "SIMULATION",
        "evidence_status": "USER_SCREENSHOT_CONFIRMED",
        "snapshot_type": "USER_CONFIRMED_INTRADAY_POSITION_AND_TRANSACTION_SNAPSHOT",
        "position_authority": "USER_CONFIRMED_QUANTITIES",
        "intraday_prices_decision_grade": False,
        "completed_close_promotion": False,
        "available_cash": CASH,
        "reported_transactions": TRADES,
        "confirmed_positions": [
            {"security_id": sid, "quantity": qty, **({"available_quantity": POSITION_TARGETS[sid]["available_quantity"]} if sid in POSITION_TARGETS else {})}
            for sid, qty in sorted(EXPECTED_QUANTITIES.items())
        ],
        "real_account_confirmation": "UNCHANGED_QUANTITIES_CONFIRMED_SEPARATELY_BY_USER_SCREENSHOTS_NO_REAL_MUTATION_IN_THIS_RUN",
        "ai_autonomous_1m_mutation": False,
        "candidate_mutation": False,
        "policy_mutation": False,
        "orders": 0,
        "trade_authority": "NONE",
        "notes": [
            "Screenshots were captured before the 2026-09-10 close; displayed market values and P&L are observations only.",
            "Only actual holdings/available quantities, transaction prices/quantities, and reported available cash are promoted as user-confirmed economic facts.",
            "No exact fee allocation is inferred from the CNY 32.65 cash difference versus gross transaction arithmetic.",
        ],
    }


def validate() -> None:
    sim = read(P["sim"])
    source = read(P["sim_source"])
    delta = read(P["delta"])
    by_sid = {sid_of(row): row for row in sim["holdings"]}
    assert {sid: float(by_sid[sid]["quantity"]) for sid in EXPECTED_QUANTITIES} == EXPECTED_QUANTITIES
    assert float(by_sid["300124.SZ"]["available_quantity"]) == 200.0
    assert float(by_sid["600941.SH"]["available_quantity"]) == 300.0
    assert abs(float(by_sid["300124.SZ"]["cost_basis"]) - 32199.0) < 1e-6
    assert abs(float(by_sid["600941.SH"]["cost_basis"]) - 26091.0) < 1e-6
    assert abs(float(sim["summary"]["execution_cash_balance"]) - CASH) < 1e-6
    source_by_sid = {sid_of(row): row for row in source["holdings"]}
    assert int(source_by_sid["300124.SZ"]["quantity"]) == 500
    assert int(source_by_sid["600941.SH"]["quantity"]) == 300
    assert abs(float(source["summary"]["available_cash"]) - CASH) < 1e-6
    delta_ids = {x.get("delta_id") for x in delta.get("entries", [])}
    assert all(t["delta_id"] in delta_ids for t in TRADES)
    for t in TRADES:
        row = next(x for x in delta["entries"] if x.get("delta_id") == t["delta_id"])
        assert row["status"] == "REJECTED"
        assert row["application_decision"] == "ALREADY_APPLIED_TO_POSITION_CURRENT_DO_NOT_REAPPLY"
    assert sim.get("trade_authority") == source.get("trade_authority") == delta.get("trade_authority") == "NONE"
    assert source.get("orders") == delta.get("orders") == 0
    assert read(P["evidence"])["intraday_prices_decision_grade"] is False


def main() -> None:
    sim = read(P["sim"])
    source = read(P["sim_source"])
    delta = read(P["delta"])
    update_positions_current(sim)
    update_source_ledger(source)
    update_delta_ledger(delta)
    write(P["sim"], sim)
    write(P["sim_source"], source)
    write(P["delta"], delta)
    write(P["evidence"], build_evidence())
    validate()
    print({"status": "PASS", "run_id": RUN_ID, "simulation_quantity_mutations": 2, "real_mutations": 0, "ai_autonomous_mutations": 0, "candidate_mutations": 0, "orders": 0, "trade_authority": "NONE"})


if __name__ == "__main__":
    main()
