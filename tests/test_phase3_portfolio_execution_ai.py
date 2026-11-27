from __future__ import annotations

import copy
import pytest

from automation.portfolio_execution.build_portfolio_execution import (
    AI_INITIAL_CAPITAL,
    apply_ai_virtual_rebalance,
    build_account_target_plan,
    build_execution_plan,
    update_ai_deployment_discipline,
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


def test_concentration_hold_is_review_only_not_mechanical_sell() -> None:
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
    assert row["target_weight"] == row["current_weight"]
    assert "SINGLE_NAME_CAP_10PCT_RISK_REVIEW_ONLY" in row["target_weight_reasons"]
    assert "CONCENTRATION_REVIEW_DIAGNOSTIC_ONLY" in row["target_weight_reasons"]
    execution = build_execution_plan(plan)["rows"][0]
    assert execution["side"] == "HOLD"
    assert execution["status"] == "NO_ACTION_REVIEW_ONLY"
    assert execution["validated_quantity"] == 0


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
            "action": "ADD",
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
    assert all(
        weight <= 0.30 + 1e-9 for weight in by_group.values()
    ), {
        "by_group": by_group,
        "current_nav": state["current_nav"],
        "cash_weight": report["cash_weight"],
        "attribution": report["attribution"],
        "diagnostics": report["diagnostics"],
    }
    assert all(
        pos["market_value"] / state["current_nav"] <= 0.10 + 1e-9
        for pos in state["positions"]
    ), {
        "positions": state["positions"],
        "current_nav": state["current_nav"],
    }


def test_day20_does_not_claim_30pct_deployment_when_eligible_capacity_is_exhausted() -> None:
    buy = rec("301109.SZ", "BUY", price=12.8, expected=0.12, name="军信股份")
    buy["portfolio_implication"] = "NEW_CAPITAL_CANDIDATE"
    buy["base_value"] = 14.0
    buy["probability_weighted_value"] = 14.3

    state = {
        "current_nav": 1_000_000.0,
        "cash": 800_000.0,
        "positions": [
            {
                "security_id": "002807.SZ",
                "security_name": "江阴银行",
                "quantity": 25_000,
                "last_price": 4.0,
                "market_value": 100_000.0,
                "risk_group": "A_SHARE_STOCK",
            },
            {
                "security_id": "301109.SZ",
                "security_name": "军信股份",
                "quantity": 7_812.5,
                "last_price": 12.8,
                "market_value": 100_000.0,
                "risk_group": "A_SHARE_STOCK",
            },
        ],
        "nav_history": [
            {"as_of_date": f"2026-09-{day:02d}"}
            for day in range(1, 21)
        ],
        "decision_grade_d2_seen": [
            "000900.SZ",
            "002807.SZ",
            "002936.SZ",
            "300230.SZ",
            "301109.SZ",
        ],
    }

    discipline = update_ai_deployment_discipline(
        state=state,
        recommendation=recommendation(buy),
        as_of_date="2026-09-20",
    )

    assert discipline["experiment_trading_day"] == 20
    assert discipline["eligible_incremental_deployable_capacity_weight"] <= 1e-12
    assert discipline["capacity_constrained_max_deployed_weight"] < 0.30
    assert "DAY20_CAPACITY_CONSTRAINED" in discipline["triggered_gates"]
    assert (
        "DEPLOYMENT_BELOW_30PCT_WITH_SUFFICIENT_ELIGIBLE_CAPACITY"
        not in discipline["triggered_gates"]
    )
    assert (
        discipline["high_cash_reason"]
        == "INSUFFICIENT_ELIGIBLE_DEPLOYABLE_CAPACITY_UNDER_PORTFOLIO_CAPS"
    )


def test_day20_flags_underdeployment_when_formal_buys_have_enough_capacity() -> None:
    rows = []
    for sid in ["000001.SZ", "000002.SZ", "000003.SZ"]:
        row = rec(sid, "BUY", price=10.0, expected=0.20)
        row["portfolio_implication"] = "NEW_CAPITAL_CANDIDATE"
        row["base_value"] = 12.0
        row["probability_weighted_value"] = 12.0
        rows.append(row)

    state = {
        "current_nav": 1_000_000.0,
        "cash": 1_000_000.0,
        "positions": [],
        "nav_history": [
            {"as_of_date": f"2026-09-{day:02d}"}
            for day in range(1, 21)
        ],
        "decision_grade_d2_seen": [
            "000001.SZ",
            "000002.SZ",
            "000003.SZ",
            "000004.SZ",
            "000005.SZ",
        ],
    }

    discipline = update_ai_deployment_discipline(
        state=state,
        recommendation=recommendation(*rows),
        as_of_date="2026-09-20",
    )

    assert discipline["eligible_incremental_deployable_capacity_weight"] >= 0.30 - 1e-12
    assert discipline["capacity_constrained_max_deployed_weight"] >= 0.30 - 1e-12
    assert (
        "DEPLOYMENT_BELOW_30PCT_WITH_SUFFICIENT_ELIGIBLE_CAPACITY"
        in discipline["triggered_gates"]
    )
    assert "DAY20_CAPACITY_CONSTRAINED" not in discipline["triggered_gates"]


def test_ai_same_session_replay_preserves_immutable_nav_and_transactions() -> None:
    first, _ = apply_ai_virtual_rebalance(
        recommendation=recommendation(rec("001227.SZ", "BUY", price=2.10)),
        lifecycle=lifecycle(life_row("001227.SZ", 2.10, "FLAT_BUY_REVIEW")),
        prior_state=None,
        as_of_date="2026-10-12",
    )
    before = copy.deepcopy(first)
    # A late callback tries to rerun the same session at a different price.
    second, receipt = apply_ai_virtual_rebalance(
        recommendation=recommendation(rec("001227.SZ", "BUY", price=2.50)),
        lifecycle=lifecycle(life_row("001227.SZ", 2.50, "FLAT_BUY_REVIEW")),
        prior_state=first,
        as_of_date="2026-10-12",
    )
    assert second["nav_history"] == before["nav_history"]
    assert second["transactions"] == before["transactions"]
    assert second["cash"] == before["cash"]
    assert second["current_nav"] == before["current_nav"]
    assert receipt["new_transaction_count"] == 0
    assert receipt["diagnostics"][0]["status"] == "NO_OP_SETTLED_SESSION_IMMUTABLE"


def test_ai_refuses_out_of_order_market_session() -> None:
    first, _ = apply_ai_virtual_rebalance(
        recommendation=recommendation(rec("001227.SZ", "BUY", price=2.10)),
        lifecycle=lifecycle(life_row("001227.SZ", 2.10)),
        prior_state=None,
        as_of_date="2026-10-13",
    )
    with pytest.raises(ValueError, match="AI_SETTLED_SESSION_BACKDATE"):
        apply_ai_virtual_rebalance(
            recommendation=recommendation(rec("001227.SZ", "HOLD", price=2.10)),
            lifecycle=lifecycle(life_row("001227.SZ", 2.10)),
            prior_state=first,
            as_of_date="2026-10-12",
        )


def test_ai_rejects_cross_session_official_listed_price() -> None:
    bad_price = life_row("001227.SZ", 2.12)
    bad_price.update({"price_as_of": "2026-10-13", "price_source": "A_SHARE_FULL_MARKET"})
    with pytest.raises(ValueError, match="AI_LISTED_PRICE_SESSION_MISMATCH"):
        apply_ai_virtual_rebalance(
            recommendation=recommendation(rec("001227.SZ", "BUY", price=2.12)),
            lifecycle=lifecycle(bad_price),
            prior_state=None,
            as_of_date="2026-10-12",
        )


def test_ai_rejects_inconsistent_prior_nav_history() -> None:
    first, _ = apply_ai_virtual_rebalance(
        recommendation=recommendation(rec("001227.SZ", "BUY", price=2.10)),
        lifecycle=lifecycle(life_row("001227.SZ", 2.10)),
        prior_state=None,
        as_of_date="2026-10-12",
    )
    first["nav_history"][-1]["nav"] += 3100.0
    with pytest.raises(ValueError, match="AI_SETTLED_NAV_STATE_HISTORY_CONFLICT"):
        apply_ai_virtual_rebalance(
            recommendation=recommendation(rec("001227.SZ", "BUY", price=2.12)),
            lifecycle=lifecycle(life_row("001227.SZ", 2.12)),
            prior_state=first,
            as_of_date="2026-10-12",
        )



def test_strategy_small_ordinary_buy_is_skipped_but_explicit_add_is_not():
    sid = "000001.SZ"
    initial, _ = apply_ai_virtual_rebalance(recommendation=recommendation(rec(sid, "BUY", price=10)),
        lifecycle=lifecycle(life_row(sid, 10)), prior_state=None, as_of_date="2026-09-01")
    # A small decline opens a single-lot ordinary rebalance.
    state, report = apply_ai_virtual_rebalance(recommendation=recommendation(rec(sid, "HOLD", price=9.8)),
        lifecycle=lifecycle(life_row(sid, 9.8)), prior_state=initial, as_of_date="2026-09-02")
    assert state["positions"][0]["quantity"] == initial["positions"][0]["quantity"]
    assert report["new_transaction_count"] == 0
    assert any(d["status"].startswith("SKIP_SMALL_ORDINARY_REBALANCE") for d in report["diagnostics"])
    _, add_report = apply_ai_virtual_rebalance(recommendation=recommendation(rec(sid, "ADD", price=9.8)),
        lifecycle=lifecycle(life_row(sid, 9.8)), prior_state=initial, as_of_date="2026-09-02")
    assert any(t["side"] == "BUY" for t in add_report["new_transactions"])


def test_strategy_small_risk_correction_and_exit_are_not_filtered():
    sid = "000001.SZ"
    initial, _ = apply_ai_virtual_rebalance(recommendation=recommendation(rec(sid, "BUY", price=10)),
        lifecycle=lifecycle(life_row(sid, 10)), prior_state=None, as_of_date="2026-09-01")
    state, report = apply_ai_virtual_rebalance(recommendation=recommendation(rec(sid, "HOLD", price=10.3)),
        lifecycle=lifecycle(life_row(sid, 10.3)), prior_state=initial, as_of_date="2026-09-02")
    assert any(t["side"] == "SELL" for t in report["new_transactions"])
    assert state["positions"][0]["market_value"] / state["current_nav"] <= 0.10
    small = copy.deepcopy(initial)
    p = small["positions"][0]
    p["quantity"] = 100
    p["market_value"] = 1000
    small["cash"] = small["current_nav"] - 1000
    _, report = apply_ai_virtual_rebalance(recommendation=recommendation(rec(sid, "EXIT", price=10)),
        lifecycle=lifecycle(life_row(sid, 10)), prior_state=small, as_of_date="2026-09-02")
    assert any(t["side"] == "SELL" and t["quantity"] == 100 for t in report["new_transactions"])


def test_strategy_pending_fresh_d2_does_not_liquidate_ai_position():
    sid = "920663.BJ"
    initial, _ = apply_ai_virtual_rebalance(recommendation=recommendation(rec(sid, "BUY", price=11)),
        lifecycle=lifecycle(life_row(sid, 11)), prior_state=None, as_of_date="2026-09-01")
    for status in ("FRESH_D2_REQUIRED_ON_PRICE_CROSS", "RESEARCH_REFRESH_PENDING", "HOLDING_REUNDERWRITE_REQUIRED"):
        r = rec(sid, "WATCH", price=10)
        r["research_freshness"] = status
        state, report = apply_ai_virtual_rebalance(recommendation=recommendation(r),
            lifecycle=lifecycle(life_row(sid, 10)), prior_state=initial, as_of_date="2026-09-02")
        assert state["positions"][0]["quantity"] == initial["positions"][0]["quantity"]
        assert report["new_transaction_count"] == 0
        assert state["orders"] == 0 and state["trade_authority"] == "NONE"


def test_strategy_historical_engine_replay_recent_verified_sessions(capsys):
    """Re-execute both engines against immutable point-in-time Phase3 snapshots.

    Only the post-session-guard interval is used. No future signals, synthetic
    prices, retrospective research, or real-account mutations.
    """
    import json
    import subprocess
    import types
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    anchor = "0fdcb4a17b980205eda6ef504e006378cf62064e"
    sessions = [
        ("2026-11-18", "a88cd6acf35acf5c7de5fa39a59f6f44c376afcf"),
        ("2026-11-19", "b71776e310b51e4e8cb135bc9fe79d92012b56df"),
        ("2026-11-20", "1446847a577a481dba4d3e78297a95ac8e3d3ecf"),
        ("2026-11-23", "49f02d6cae2abdb87f395353ae2377506afca214"),
        ("2026-11-24", "1cf3011bfac1c576aae1e2939cc53707b982625a"),
        ("2026-11-25", "d932a94aa67f0610ece592c63f5ba16b92748209"),
        ("2026-11-26", "f25fb05c48ef0431463df5c6ca4007170ea491e3"),
    ]
    def read(ref, path):
        return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=root, text=True)
    def payload(ref, path):
        return json.loads(read(ref, "operating_current/" + path))
    # In shallow local clones this historical integration test requires the
    # operating-current history; production Phase3 CI checks out full history.
    if subprocess.run(["git", "cat-file", "-e", anchor + "^{commit}"], cwd=root,
                      capture_output=True).returncode:
        pytest.skip("Pinned operating-current history not present in shallow clone")
    previous = payload(anchor, "ai_autonomous/AI_AUTONOMOUS_1M_CURRENT.json")
    assert previous["nav_history"][-1]["as_of_date"] == "2026-11-17"
    base = types.ModuleType("strategy_original_engine")
    exec(compile(read("9ca62244014beb24aa33828d830544176b255a7a",
                      "automation/portfolio_execution/build_portfolio_execution.py"),
                 "<pinned original engine>", "exec"), base.__dict__)
    old = copy.deepcopy(previous)
    new = copy.deepcopy(previous)
    initial_count = len(previous["transactions"])
    observed = []
    for day, ref in sessions:
        actual = payload(ref, "ai_autonomous/AI_AUTONOMOUS_1M_CURRENT.json")
        life = payload(ref, "decision_lifecycle/DECISION_LIFECYCLE_CURRENT.json")
        recs = payload(ref, "investment_pipeline/RECOMMENDATION_CURRENT.json")
        assert actual["nav_history"][-1]["as_of_date"] == day
        assert life["input_identity"]["recommendation_state_id"] == recs["state_id"]
        assert life["as_of_date"] == day
        old, old_report = base.apply_ai_virtual_rebalance(recommendation=recs, lifecycle=life,
            prior_state=old, as_of_date=day)
        new, report = apply_ai_virtual_rebalance(recommendation=recs, lifecycle=life,
            prior_state=new, as_of_date=day)
        assert abs(old["current_nav"] - actual["current_nav"]) < 0.02, (day, old["current_nav"], actual["current_nav"])
        assert len(old["transactions"]) == len(actual["transactions"]), day
        assert new["orders"] == 0 and new["trade_authority"] == "NONE"
        assert new["cash"] / new["current_nav"] >= 0.20 - 1e-8
        groups = {}
        for p in new["positions"]:
            w = p["market_value"] / new["current_nav"]
            assert w <= 0.10 + 1e-7, (day, p["security_id"], w)
            groups[p["risk_group"]] = groups.get(p["risk_group"], 0) + w
        assert max(groups.values(), default=0) <= 0.30 + 1e-7, (day, groups)
        observed.append({"date": day, "baseline_nav": old["current_nav"], "candidate_nav": new["current_nav"],
            "baseline_trades": old_report["new_transaction_count"], "candidate_trades": report["new_transaction_count"]})
    assert len(new["transactions"]) < len(old["transactions"])
    with capsys.disabled():
        print("STRATEGY_REPLAY_RECEIPT", json.dumps({"sessions": observed,
            "baseline_trades": len(old["transactions"]) - initial_count,
            "candidate_trades": len(new["transactions"]) - initial_count,
            "baseline_nav": old["current_nav"], "candidate_nav": new["current_nav"]}, sort_keys=True))
