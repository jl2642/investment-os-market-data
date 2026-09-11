from __future__ import annotations

from automation.portfolio_execution.apply_protected_execution_episode_guard import (
    apply_protected_execution_episode_guard,
)


def rec(sid: str, action: str, underwriting_date: str) -> dict:
    return {
        "security_id": sid,
        "action": action,
        "underwriting_price_as_of": underwriting_date,
        "underwriting_price": 10.0,
        "entry_price": 10.0,
        "probability_weighted_value": 12.0,
        "confidence": "MEDIUM",
        "top_reasons": [f"D2_EXPLICIT_POSITION_ACTION_{action}"],
    }


def tx(account: str, sid: str, action: str, execution_time: str, delta_id: str) -> dict:
    return {
        "account": account,
        "security_id": sid,
        "action": action,
        "execution_time": execution_time,
        "delta_id": delta_id,
        "event_type": "SIMULATION_TRADE" if account == "SIMULATION" else "USER_CONFIRMED_REAL_TRADE",
        "confirmation_authority": "USER",
        "evidence_status": "USER_SCREENSHOT_CONFIRMED",
        "position_engine_treatment": "SOURCE_BASELINE_ALREADY_CONTAINS_DELTA",
        "quantity": 100,
    }


def phase3_row(account_key: str, sid: str, action: str, current_qty: float, target_qty: float, side: str) -> dict:
    current_weight = 0.03
    target_weight = 0.05 if side == "BUY" else 0.015
    account = {
        "target_plan": {
            "target_cash_weight": 0.50,
            "rows": [{
                "security_id": sid,
                "action": action,
                "current_weight": current_weight,
                "target_weight": target_weight,
                "target_weight_reasons": ["CURRENT_DECISION_SCORE_SIZED"],
            }],
        },
        "execution_validation": {
            "starting_cash": 100000.0,
            "ending_cash_if_all_validated_actions_executed": 90000.0 if side == "BUY" else 110000.0,
            "rows": [{
                "security_id": sid,
                "action": action,
                "current_weight": current_weight,
                "target_weight": target_weight,
                "current_quantity": current_qty,
                "target_quantity": target_qty,
                "validated_quantity": abs(target_qty - current_qty),
                "side": side,
                "status": "READY_FOR_USER_OR_VIRTUAL_EXECUTION",
                "reason": "BUY_QUANTITY_VALIDATED" if side == "BUY" else "SELL_QUANTITY_VALIDATED",
                "estimated_notional": 10000.0,
            }],
        },
    }
    return {account_key: account, "controls": {}, "orders": 0, "trade_authority": "NONE"}


def test_simulation_add_is_idempotent_after_user_confirmed_execution() -> None:
    sid = "300124.SZ"
    p3 = phase3_row("simulation_account", sid, "ADD", 500, 800, "BUY")
    recommendation = {
        "generated_at_utc": "2026-09-10T03:16:09Z",
        "records": [rec(sid, "ADD", "2026-09-09")],
    }
    ledger = {"entries": [tx("SIMULATION", sid, "BUY", "2026-09-10T13:00:01+08:00", "SIM_BUY_300124")]}
    out = apply_protected_execution_episode_guard(p3, recommendation, ledger)
    row = out["simulation_account"]["execution_validation"]["rows"][0]
    assert row["status"] == "NO_ACTION_ALREADY_EXECUTED_RECOMMENDATION_EPISODE"
    assert row["side"] == "HOLD"
    assert row["validated_quantity"] == 0
    assert row["target_quantity"] == 500
    assert "estimated_notional" not in row
    assert out["protected_execution_episode_guard"]["suppressed_repeat_action_count"] == 1


def test_simulation_trim_is_idempotent_after_user_confirmed_execution() -> None:
    sid = "600941.SH"
    p3 = phase3_row("simulation_account", sid, "TRIM", 300, 100, "SELL")
    recommendation = {
        "generated_at_utc": "2026-09-10T03:16:09Z",
        "records": [rec(sid, "TRIM", "2026-09-03")],
    }
    ledger = {"entries": [tx("SIMULATION", sid, "SELL", "2026-09-10T13:00:00+08:00", "SIM_SELL_600941")]}
    out = apply_protected_execution_episode_guard(p3, recommendation, ledger)
    row = out["simulation_account"]["execution_validation"]["rows"][0]
    assert row["status"] == "NO_ACTION_ALREADY_EXECUTED_RECOMMENDATION_EPISODE"
    assert row["target_quantity"] == 300
    assert out["simulation_account"]["execution_validation"]["ending_cash_if_all_validated_actions_executed"] == 100000.0


def test_opposite_direction_historical_trade_does_not_suppress_add() -> None:
    sid = "300124.SZ"
    p3 = phase3_row("simulation_account", sid, "ADD", 500, 800, "BUY")
    recommendation = {
        "generated_at_utc": "2026-09-10T03:16:09Z",
        "records": [rec(sid, "ADD", "2026-09-09")],
    }
    ledger = {"entries": [tx("SIMULATION", sid, "SELL", "2026-08-06T11:00:48+08:00", "OLD_SELL")]}
    out = apply_protected_execution_episode_guard(p3, recommendation, ledger)
    row = out["simulation_account"]["execution_validation"]["rows"][0]
    assert row["status"] == "READY_FOR_USER_OR_VIRTUAL_EXECUTION"
    assert row["validated_quantity"] == 300
    assert out["protected_execution_episode_guard"]["suppressed_repeat_action_count"] == 0


def test_same_day_fresh_underwriting_after_trade_reopens_episode() -> None:
    sid = "300124.SZ"
    p3 = phase3_row("simulation_account", sid, "ADD", 500, 800, "BUY")
    recommendation = {
        "generated_at_utc": "2026-09-10T06:00:00Z",
        "records": [rec(sid, "ADD", "2026-09-10")],
    }
    ledger = {"entries": [tx("SIMULATION", sid, "BUY", "2026-09-10T13:00:01+08:00", "EARLIER_BUY")]}
    out = apply_protected_execution_episode_guard(p3, recommendation, ledger)
    row = out["simulation_account"]["execution_validation"]["rows"][0]
    assert row["status"] == "READY_FOR_USER_OR_VIRTUAL_EXECUTION"
    assert out["protected_execution_episode_guard"]["suppressed_repeat_action_count"] == 0


def test_exit_is_not_suppressed_by_episode_guard() -> None:
    sid = "600001.SH"
    p3 = phase3_row("simulation_account", sid, "EXIT", 300, 0, "SELL")
    recommendation = {
        "generated_at_utc": "2026-09-10T03:16:09Z",
        "records": [rec(sid, "EXIT", "2026-09-09")],
    }
    ledger = {"entries": [tx("SIMULATION", sid, "SELL", "2026-09-10T13:00:00+08:00", "PARTIAL_EXIT")]}
    out = apply_protected_execution_episode_guard(p3, recommendation, ledger)
    row = out["simulation_account"]["execution_validation"]["rows"][0]
    assert row["status"] == "READY_FOR_USER_OR_VIRTUAL_EXECUTION"
    assert out["protected_execution_episode_guard"]["suppressed_repeat_action_count"] == 0
