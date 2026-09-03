from automation.portfolio_execution.apply_bounded_last_mile_policy import repair_account, deployment_discipline


def test_hold_concentration_cannot_generate_sell():
    account = {
        "target_plan": {"rows": [{"security_id": "605090.SH", "action": "HOLD", "current_weight": .42, "target_weight": .10, "current_quantity": 9900, "target_weight_reasons": ["CURRENT_DECISION_HOLD_PRESERVE", "SINGLE_NAME_CAP_10PCT"]}]},
        "execution_validation": {"rows": [{"security_id": "605090.SH", "security_name": "九丰能源", "side": "SELL", "status": "READY_FOR_USER_OR_VIRTUAL_EXECUTION", "current_weight": .42, "target_weight": .10, "current_quantity": 9900, "validated_quantity": 7600}]},
    }
    repairs = repair_account(account)
    row = account["execution_validation"]["rows"][0]
    assert repairs
    assert row["side"] == "HOLD"
    assert row["validated_quantity"] == 0
    assert row["status"] == "NO_ACTION_REVIEW_ONLY"
    assert account["target_plan"]["rows"][0]["target_weight"] == .42


def test_trim_remains_execution_candidate():
    account = {
        "target_plan": {"rows": [{"security_id": "159612.SZ", "action": "TRIM", "current_weight": .027, "target_weight": .0135, "current_quantity": 10200}]},
        "execution_validation": {"rows": [{"security_id": "159612.SZ", "side": "SELL", "status": "READY_FOR_USER_OR_VIRTUAL_EXECUTION", "current_weight": .027, "target_weight": .0135, "current_quantity": 10200, "validated_quantity": 5200}]},
    }
    assert repair_account(account) == []
    assert account["execution_validation"]["rows"][0]["validated_quantity"] == 5200


def test_ai_day10_gate_does_not_force_buy():
    ai = {"initial_capital": 1_000_000.0, "current_nav": 1_000_000.0, "cash": 1_000_000.0, "positions": [], "nav_history": [{"as_of_date": f"2026-09-{i:02d}"} for i in range(1, 11)]}
    report = {}
    d = deployment_discipline(ai, report, "2026-09-10")
    assert "AI_BOOK_DEPLOYMENT_REVIEW" in d["triggered_gates"]
    assert d["rules"]["forced_buying"] is False
    assert ai["positions"] == []
