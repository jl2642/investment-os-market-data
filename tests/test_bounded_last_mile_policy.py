from automation.portfolio_execution.build_portfolio_execution import (
    AI_INITIAL_CAPITAL,
    apply_ai_virtual_rebalance,
    build_account_target_plan,
    build_execution_plan,
    update_ai_deployment_discipline,
)


def rec(sid: str, action: str, *, price: float = 10.0, implication: str = "EXISTING_POSITION") -> dict:
    return {
        "security_id": sid,
        "security_name": sid,
        "action": action,
        "current_price": price,
        "entry_price": price * 0.9,
        "base_value": price * 1.1,
        "probability_weighted_value": price * 1.08,
        "expected_return": 0.08,
        "bear_downside": -0.20,
        "confidence": "MEDIUM_HIGH",
        "portfolio_implication": implication,
        "orders": 0,
        "trade_authority": "NONE",
    }


def lifecycle_row(sid: str, price: float, state: str) -> dict:
    return {
        "security_id": sid,
        "latest_price": price,
        "lifecycle_state": state,
    }


def account_with_one(sid: str, qty: float, price: float, *, total: float = 1_000_000.0) -> dict:
    return {
        "account": "REAL",
        "summary": {
            "account_total_assets": total,
            "execution_cash_balance": total - qty * price,
        },
        "holdings": [{
            "security_id": sid,
            "security_name": sid,
            "quantity": qty,
            "available_quantity": qty,
            "mark": price,
            "market_value": qty * price,
            "asset_class": "A_SHARE_STOCK",
        }],
    }


def test_hold_concentration_is_diagnostic_only_at_source() -> None:
    acc = account_with_one("605090.SH", 12_000, 35.0)
    recommendation = {"state_id": "REC", "records": [rec("605090.SH", "HOLD", price=35.0)]}
    lifecycle = {
        "lifecycle_id": "LIFE",
        "subjects": [lifecycle_row("605090.SH", 35.0, "HELD_CONCENTRATION_REVIEW")],
    }
    plan = build_account_target_plan(acc, recommendation, lifecycle)
    row = plan["rows"][0]
    assert row["target_weight"] == row["current_weight"]
    assert "SINGLE_NAME_CAP_10PCT_RISK_REVIEW_ONLY" in row["target_weight_reasons"]
    execution = build_execution_plan(plan)["rows"][0]
    assert execution["side"] == "HOLD"
    assert execution["status"] == "NO_ACTION_REVIEW_ONLY"
    assert execution["validated_quantity"] == 0


def test_group_cap_cannot_shrink_hold_positions() -> None:
    acc = {
        "account": "SIMULATION",
        "summary": {"account_total_assets": 1_000_000.0, "execution_cash_balance": 600_000.0},
        "holdings": [
            {
                "security_id": "000001.SZ", "security_name": "A", "quantity": 20_000,
                "available_quantity": 20_000, "mark": 10.0, "market_value": 200_000.0,
                "asset_class": "A_SHARE_STOCK", "portfolio_bucket": "SAME_GROUP/core",
            },
            {
                "security_id": "000002.SZ", "security_name": "B", "quantity": 20_000,
                "available_quantity": 20_000, "mark": 10.0, "market_value": 200_000.0,
                "asset_class": "A_SHARE_STOCK", "portfolio_bucket": "SAME_GROUP/core",
            },
        ],
    }
    recommendation = {
        "state_id": "REC",
        "records": [rec("000001.SZ", "HOLD"), rec("000002.SZ", "HOLD")],
    }
    lifecycle = {
        "lifecycle_id": "LIFE",
        "subjects": [
            lifecycle_row("000001.SZ", 10.0, "HELD_HOLD"),
            lifecycle_row("000002.SZ", 10.0, "HELD_HOLD"),
        ],
    }
    plan = build_account_target_plan(acc, recommendation, lifecycle)
    assert all(row["target_weight"] == row["current_weight"] for row in plan["rows"])
    execution = build_execution_plan(plan)
    assert all(row["side"] == "HOLD" for row in execution["rows"])
    assert all(row["validated_quantity"] == 0 for row in execution["rows"])


def test_trim_remains_execution_candidate() -> None:
    acc = account_with_one("159612.SZ", 10_200, 2.0)
    recommendation = {"state_id": "REC", "records": [rec("159612.SZ", "TRIM", price=2.0)]}
    lifecycle = {
        "lifecycle_id": "LIFE",
        "subjects": [lifecycle_row("159612.SZ", 2.0, "HELD_TRIM_REVIEW")],
    }
    plan = build_account_target_plan(acc, recommendation, lifecycle)
    row = build_execution_plan(plan)["rows"][0]
    assert row["side"] == "SELL"
    assert row["status"] == "READY_FOR_USER_OR_VIRTUAL_EXECUTION"
    assert row["validated_quantity"] > 0


def test_action_direction_is_fail_closed() -> None:
    trim_plan = {
        "account": "REAL", "total_assets": 100_000.0, "current_cash": 50_000.0,
        "rows": [{
            "security_id": "000001.SZ", "security_name": "A", "asset_class": "A_SHARE_STOCK",
            "action": "TRIM", "current_weight": 0.10, "target_weight": 0.20,
            "research_score": 1.0, "current_quantity": 1_000.0, "available_quantity": 1_000.0,
            "current_price": 10.0,
        }],
    }
    add_plan = {
        "account": "REAL", "total_assets": 100_000.0, "current_cash": 50_000.0,
        "rows": [{
            "security_id": "000002.SZ", "security_name": "B", "asset_class": "A_SHARE_STOCK",
            "action": "ADD", "current_weight": 0.20, "target_weight": 0.10,
            "research_score": 1.0, "current_quantity": 2_000.0, "available_quantity": 2_000.0,
            "current_price": 10.0,
        }],
    }
    assert build_execution_plan(trim_plan)["rows"][0]["reason"] == "TRIM_OR_EXIT_CANNOT_AUTHORIZE_BUY"
    assert build_execution_plan(add_plan)["rows"][0]["reason"] == "ADD_CANNOT_AUTHORIZE_SELL"


def test_ai_day10_gate_does_not_force_buy() -> None:
    ai = {
        "initial_capital": AI_INITIAL_CAPITAL,
        "current_nav": AI_INITIAL_CAPITAL,
        "cash": AI_INITIAL_CAPITAL,
        "positions": [],
        "nav_history": [{"as_of_date": f"2026-09-{i:02d}"} for i in range(1, 11)],
    }
    d = update_ai_deployment_discipline(
        state=ai,
        recommendation={"records": []},
        as_of_date="2026-09-10",
    )
    assert "AI_BOOK_DEPLOYMENT_REVIEW" in d["triggered_gates"]
    assert d["rules"]["forced_buying"] is False
    assert ai["positions"] == []


def test_ai_day20_tracks_cumulative_decision_grade_d2_and_shortfall() -> None:
    ai = {
        "initial_capital": AI_INITIAL_CAPITAL,
        "current_nav": AI_INITIAL_CAPITAL,
        "cash": AI_INITIAL_CAPITAL,
        "positions": [],
        "nav_history": [{"as_of_date": f"2026-09-{i:02d}"} for i in range(1, 21)],
        "decision_grade_d2_seen": ["000001.SZ", "000002.SZ", "000003.SZ"],
    }
    recommendation = {
        "records": [
            rec("000004.SZ", "AVOID", implication="NEW_CAPITAL_CANDIDATE"),
            rec("000005.SZ", "BUY_BELOW", implication="NEW_CAPITAL_CANDIDATE"),
        ]
    }
    d = update_ai_deployment_discipline(
        state=ai,
        recommendation=recommendation,
        as_of_date="2026-09-20",
    )
    assert d["cumulative_decision_grade_d2_count"] == 5
    assert "D2_THROUGHPUT_SHORTFALL" not in d["triggered_gates"]
    assert "DAY20_DEPLOYMENT_REVIEW" in d["triggered_gates"]


def test_buy_below_never_directly_buys_ai_book() -> None:
    recommendation = {
        "state_id": "REC",
        "records": [rec("600428.SH", "BUY_BELOW", price=10.0, implication="NEW_CAPITAL_CANDIDATE")],
    }
    lifecycle = {
        "lifecycle_id": "LIFE",
        "subjects": [lifecycle_row("600428.SH", 9.0, "FLAT_WAIT_BUY_BELOW")],
    }
    state, report = apply_ai_virtual_rebalance(
        recommendation=recommendation,
        lifecycle=lifecycle,
        prior_state=None,
        as_of_date="2026-09-01",
    )
    assert state["positions"] == []
    assert report["deployment_discipline"]["current_buy_below_ids"] == ["600428.SH"]
    assert report["deployment_discipline"]["rules"]["buy_below_direct_buy_authorized"] is False
