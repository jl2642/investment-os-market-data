from __future__ import annotations

from automation.portfolio_execution.build_portfolio_execution import (
    AI_INITIAL_CAPITAL,
    apply_ai_virtual_rebalance,
    build_account_target_plan,
    build_execution_plan,
)


def rec(
    sid: str,
    action: str,
    *,
    price: float,
    expected: float = 0.20,
    bear: float = -0.20,
    confidence: str = "HIGH",
    name: str | None = None,
) -> dict:
    return {
        "security_id": sid,
        "security_name": name or sid,
        "action": action,
        "current_price": price,
        "entry_price": price,
        "expected_return": expected,
        "bear_downside": bear,
        "confidence": confidence,
        "orders": 0,
        "trade_authority": "NONE",
    }


def recommendation(*rows: dict) -> dict:
    return {"state_id": "REC", "records": list(rows)}


def lifecycle(*rows: dict) -> dict:
    return {
        "lifecycle_id": "LIFE",
        "subjects": list(rows),
    }


def life_row(sid: str, price: float, state: str = "HELD_HOLD") -> dict:
    return {
        "security_id": sid,
        "latest_price": price,
        "lifecycle_state": state,
    }


def account(
    name: str,
    total: float,
    cash: float,
    holdings: list[dict],
) -> dict:
    return {
        "account": name,
        "summary": {
            "account_total_assets": total,
            "execution_cash_balance": cash,
        },
        "holdings": holdings,
    }


def holding(
    sid: str,
    qty: float,
    price: float,
    *,
    asset_class: str = "A_SHARE_STOCK",
    name: str | None = None,
    bucket: str | None = None,
) -> dict:
    row = {
        "security_id": sid,
        "security_name": name or sid,
        "quantity": qty,
        "available_quantity": qty,
        "mark": price,
        "market_value": qty * price,
        "asset_class": asset_class,
    }
    if bucket:
        row["portfolio_bucket"] = bucket
    return row


def test_concentration_hold_becomes_10pct_target_not_thesis_exit() -> None:
    acc = account(
        "REAL",
        1_000_000,
        100_000,
        [holding("605090.SH", 12_000, 35.0)],
    )
    plan = build_account_target_plan(
        acc,
        recommendation(rec("605090.SH", "HOLD", price=35.0)),
        lifecycle(life_row("605090.SH", 35.0, "HELD_CONCENTRATION_REVIEW")),
    )
    row = plan["rows"][0]
    assert row["target_weight"] == 0.10
    assert "SINGLE_NAME_CAP_10PCT" in row["target_weight_reasons"]


def test_trim_reduces_weight_instead_of_full_exit() -> None:
    acc = account(
        "REAL",
        1_000_000,
        100_000,
        [holding("159612.SZ", 20_000, 2.0, asset_class="QDII_ETF", name="标普500ETF国泰")],
    )
    plan = build_account_target_plan(
        acc,
        recommendation(rec("159612.SZ", "TRIM", price=2.0, name="标普500ETF国泰")),
        lifecycle(life_row("159612.SZ", 2.0, "HELD_TRIM_REVIEW")),
    )
    assert 0 < plan["rows"][0]["target_weight"] < plan["rows"][0]["current_weight"]


def test_catl_sub_lot_increment_is_blocked() -> None:
    acc = account(
        "SIMULATION",
        100_000,
        100_000,
        [holding("300750.SZ", 0, 360.0)],
    )
    plan = {
        "account": "SIMULATION",
        "total_assets": 100_000,
        "current_cash": 100_000,
        "rows": [{
            "security_id": "300750.SZ",
            "security_name": "宁德时代",
            "asset_class": "A_SHARE_STOCK",
            "current_weight": 0.0,
            "target_weight": 0.05,
            "research_score": 1.0,
            "current_quantity": 0.0,
            "available_quantity": 0.0,
            "current_price": 360.0,
        }],
    }
    execution = build_execution_plan(plan)
    row = execution["rows"][0]
    assert row["status"] == "NO_ACTION" or row["status"] == "BLOCK_LOT_SIZE"
    assert row.get("validated_quantity", 0) == 0


def test_off_exchange_fund_is_manual_review() -> None:
    plan = {
        "account": "REAL",
        "total_assets": 100_000,
        "current_cash": 10_000,
        "rows": [{
            "security_id": "017534.OF",
            "security_name": "债基",
            "asset_class": "BOND_FUND",
            "current_weight": 0.20,
            "target_weight": 0.10,
            "research_score": 0.1,
            "current_quantity": 10_000,
            "available_quantity": 10_000,
            "current_price": 1.4,
        }],
    }
    row = build_execution_plan(plan)["rows"][0]
    assert row["status"] == "MANUAL_FUND_EXECUTION_REVIEW"
    assert row["validated_quantity"] is None


def test_ai_stays_all_cash_when_no_buy_exists() -> None:
    state, report = apply_ai_virtual_rebalance(
        recommendation=recommendation(
            rec("600428.SH", "BUY_BELOW", price=11.67),
            rec("002936.SZ", "AVOID", price=1.81),
        ),
        lifecycle=lifecycle(
            life_row("600428.SH", 11.67, "FLAT_WAIT_BUY_BELOW"),
            life_row("002936.SZ", 1.81, "FLAT_AVOID"),
        ),
        prior_state=None,
        as_of_date="2026-09-01",
    )
    assert state["cash"] == AI_INITIAL_CAPITAL
    assert state["positions"] == []
    assert report["position_count"] == 0
    assert report["cash_weight"] == 1.0


def test_ai_builds_multiple_positions_with_100_share_lots_and_caps() -> None:
    recs = recommendation(
        rec("000001.SZ", "BUY", price=10.0, expected=0.30, name="A"),
        rec("000002.SZ", "BUY", price=20.0, expected=0.25, name="B"),
        rec("000003.SZ", "BUY", price=30.0, expected=0.20, name="C"),
    )
    life = lifecycle(
        life_row("000001.SZ", 10.0, "FLAT_BUY_REVIEW"),
        life_row("000002.SZ", 20.0, "FLAT_BUY_REVIEW"),
        life_row("000003.SZ", 30.0, "FLAT_BUY_REVIEW"),
    )
    state, report = apply_ai_virtual_rebalance(
        recommendation=recs,
        lifecycle=life,
        prior_state=None,
        as_of_date="2026-09-01",
    )
    assert len(state["positions"]) == 3
    for pos in state["positions"]:
        assert pos["quantity"] % 100 == 0
        assert pos["market_value"] / state["current_nav"] <= 0.101
    assert state["cash"] > 0
    assert report["new_transaction_count"] == 3


def test_ai_full_exit_and_realized_pnl_work() -> None:
    first_state, _ = apply_ai_virtual_rebalance(
        recommendation=recommendation(rec("000001.SZ", "BUY", price=10.0, expected=0.30)),
        lifecycle=lifecycle(life_row("000001.SZ", 10.0, "FLAT_BUY_REVIEW")),
        prior_state=None,
        as_of_date="2026-09-01",
    )
    second_state, report = apply_ai_virtual_rebalance(
        recommendation=recommendation(rec("000001.SZ", "EXIT", price=12.0, expected=0.0)),
        lifecycle=lifecycle(life_row("000001.SZ", 12.0, "HELD_EXIT_REVIEW")),
        prior_state=first_state,
        as_of_date="2026-09-02",
    )
    assert second_state["positions"] == []
    assert any(x["side"] == "SELL" for x in report["new_transactions"])
    assert second_state["realized_pnl"] > 0


def test_ai_trim_reduces_but_does_not_zero_position() -> None:
    first_state, _ = apply_ai_virtual_rebalance(
        recommendation=recommendation(rec("000001.SZ", "BUY", price=10.0, expected=0.30)),
        lifecycle=lifecycle(life_row("000001.SZ", 10.0, "FLAT_BUY_REVIEW")),
        prior_state=None,
        as_of_date="2026-09-01",
    )
    first_qty = first_state["positions"][0]["quantity"]
    second_state, _ = apply_ai_virtual_rebalance(
        recommendation=recommendation(rec("000001.SZ", "TRIM", price=10.0, expected=0.15)),
        lifecycle=lifecycle(life_row("000001.SZ", 10.0, "HELD_TRIM_REVIEW")),
        prior_state=first_state,
        as_of_date="2026-09-02",
    )
    assert 0 < second_state["positions"][0]["quantity"] < first_qty


def test_ai_only_top_ten_compete_for_capital() -> None:
    rows = []
    life_rows = []
    for i in range(11):
        sid = f"{i+1:06d}.SZ"
        rows.append(rec(sid, "BUY", price=10.0, expected=0.30 - i * 0.01))
        life_rows.append(life_row(sid, 10.0, "FLAT_BUY_REVIEW"))
    state, _ = apply_ai_virtual_rebalance(
        recommendation=recommendation(*rows),
        lifecycle=lifecycle(*life_rows),
        prior_state=None,
        as_of_date="2026-09-01",
    )
    assert len(state["positions"]) <= 10
    assert "000011.SZ" not in {x["security_id"] for x in state["positions"]}


def test_ai_performance_tracks_drawdown_and_turnover() -> None:
    state1, report1 = apply_ai_virtual_rebalance(
        recommendation=recommendation(rec("000001.SZ", "BUY", price=10.0, expected=0.30)),
        lifecycle=lifecycle(life_row("000001.SZ", 10.0, "FLAT_BUY_REVIEW")),
        prior_state=None,
        as_of_date="2026-09-01",
    )
    state2, report2 = apply_ai_virtual_rebalance(
        recommendation=recommendation(rec("000001.SZ", "HOLD", price=8.0, expected=0.20)),
        lifecycle=lifecycle(life_row("000001.SZ", 8.0, "HELD_HOLD")),
        prior_state=state1,
        as_of_date="2026-09-02",
    )
    assert report1["performance"]["turnover_since_inception"] > 0
    assert state2["current_nav"] < state1["current_nav"]
    assert state2["max_drawdown"] < 0


def test_ai_add_increases_existing_position_with_legal_lot() -> None:
    first_recs = []
    first_life = []
    for i in range(10):
        sid = f"{i+1:06d}.SZ"
        first_recs.append(rec(sid, "BUY", price=10.0, expected=0.20))
        first_life.append(life_row(sid, 10.0, "FLAT_BUY_REVIEW"))
    first_state, _ = apply_ai_virtual_rebalance(
        recommendation=recommendation(*first_recs),
        lifecycle=lifecycle(*first_life),
        prior_state=None,
        as_of_date="2026-09-01",
    )
    first_qty = next(
        x["quantity"] for x in first_state["positions"] if x["security_id"] == "000001.SZ"
    )

    second_recs = [rec("000001.SZ", "ADD", price=10.0, expected=0.50)]
    second_life = [life_row("000001.SZ", 10.0, "HELD_ADD_REVIEW")]
    for i in range(1, 10):
        sid = f"{i+1:06d}.SZ"
        second_recs.append(rec(sid, "HOLD", price=10.0, expected=0.20))
        second_life.append(life_row(sid, 10.0, "HELD_HOLD"))
    second_state, report = apply_ai_virtual_rebalance(
        recommendation=recommendation(*second_recs),
        lifecycle=lifecycle(*second_life),
        prior_state=first_state,
        as_of_date="2026-09-02",
    )
    second_qty = next(
        x["quantity"] for x in second_state["positions"] if x["security_id"] == "000001.SZ"
    )
    assert second_qty > first_qty
    assert second_qty % 100 == 0
    assert any(
        x["security_id"] == "000001.SZ" and x["side"] == "BUY"
        for x in report["new_transactions"]
    )


def test_ai_cash_floor_and_risk_group_cap_hold() -> None:
    recs = recommendation(
        rec("000001.SZ", "BUY", price=10.0, expected=0.50, name="A"),
        rec("000002.SZ", "BUY", price=10.0, expected=0.45, name="B"),
        rec("000003.SZ", "BUY", price=10.0, expected=0.40, name="C"),
        rec("000004.SZ", "BUY", price=10.0, expected=0.35, name="D"),
    )
    life = lifecycle(
        life_row("000001.SZ", 10.0, "FLAT_BUY_REVIEW"),
        life_row("000002.SZ", 10.0, "FLAT_BUY_REVIEW"),
        life_row("000003.SZ", 10.0, "FLAT_BUY_REVIEW"),
        life_row("000004.SZ", 10.0, "FLAT_BUY_REVIEW"),
    )
    state, report = apply_ai_virtual_rebalance(
        recommendation=recs,
        lifecycle=life,
        prior_state=None,
        as_of_date="2026-09-01",
    )
    assert report["cash_weight"] >= 0.20 - 1e-9
    by_group = {}
    for row in report["attribution"]:
        by_group[row["risk_group"]] = by_group.get(row["risk_group"], 0.0) + row["weight"]
    assert all(weight <= 0.30 + 1e-9 for weight in by_group.values())
    assert all(pos["market_value"] / state["current_nav"] <= 0.10 + 1e-9 for pos in state["positions"])
