from __future__ import annotations

from datetime import datetime, timezone

from automation.decision_lifecycle.build_decision_lifecycle import build

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)


def rec(
    sid: str,
    action: str,
    *,
    price: float = 10.0,
    entry: float | None = 9.0,
    blocker: str | None = "PRICE_BLOCKED",
) -> dict:
    return {
        "security_id": sid,
        "security_name": sid,
        "action": action,
        "current_price": price,
        "entry_price": entry,
        "expected_return": 0.12,
        "top_blocker": blocker,
        "ready_for_user_decision": action in {"BUY", "ADD", "TRIM", "EXIT"},
        "catalysts": ["catalyst one"],
        "kill_thesis": ["kill one"],
        "orders": 0,
        "trade_authority": "NONE",
    }


def recommendation(*rows: dict) -> dict:
    return {
        "state_id": "REC_TEST",
        "generated_at_utc": "2026-09-02T11:00:00+00:00",
        "records": list(rows),
    }


def surface(*monitoring_rows: dict) -> dict:
    return {
        "surface_id": "SURFACE_TEST",
        "as_of_date": "2026-09-01",
        "portfolio_monitoring": {"rows": list(monitoring_rows)},
    }


def holding(sid: str, price: float, *, flags: list[str] | None = None) -> dict:
    return {
        "account": "SIMULATION",
        "security_id": sid,
        "security_name": sid,
        "current_price": price,
        "monitoring_flags": flags or [],
    }


def test_buy_below_crossing_requires_fresh_d2_not_buy() -> None:
    lifecycle, queue = build(
        recommendation=recommendation(rec("600428.SH", "BUY_BELOW", price=11.67, entry=10.43)),
        surface=surface(),
        market_rows={"600428.SH": {"price": 10.40, "as_of_date": "2026-09-02"}},
        market_date="2026-09-02",
        now=NOW,
    )
    row = lifecycle["subjects"][0]
    assert row["lifecycle_state"] == "FLAT_PRICE_REUNDERWRITE"
    assert row["mechanical_trigger_keys"] == ["BUY_BELOW_PRICE_CONDITION_MET"]
    assert queue["records"][0]["review_type"] == "REUNDERWRITE_REQUIRED"
    assert queue["records"][0]["next_step"] == "FRESH_D2_BEFORE_ANY_BUY"
    assert lifecycle["controls"]["automatic_buy_sell"] is False
    assert lifecycle["orders"] == 0


def test_buy_below_above_threshold_remains_waiting() -> None:
    lifecycle, queue = build(
        recommendation=recommendation(rec("600428.SH", "BUY_BELOW", price=11.67, entry=10.43)),
        surface=surface(),
        market_rows={"600428.SH": {"price": 11.20, "as_of_date": "2026-09-02"}},
        market_date="2026-09-02",
        now=NOW,
    )
    assert lifecycle["subjects"][0]["lifecycle_state"] == "FLAT_WAIT_BUY_BELOW"
    assert queue["records"] == []


def test_existing_trim_is_immediate_user_action_review() -> None:
    lifecycle, queue = build(
        recommendation=recommendation(rec("159612.SZ", "TRIM", price=2.079, entry=2.0)),
        surface=surface(holding("159612.SZ", 2.079)),
        now=NOW,
    )
    assert lifecycle["subjects"][0]["lifecycle_state"] == "HELD_TRIM_REVIEW"
    assert queue["records"][0]["review_type"] == "USER_ACTION_REVIEW"
    assert queue["records"][0]["next_step"] == "PORTFOLIO_AND_EXECUTION_VALIDATION"


def test_drawdown_is_monitor_not_mechanical_exit() -> None:
    lifecycle, queue = build(
        recommendation=recommendation(rec("300124.SZ", "HOLD", price=61.87, entry=59.0)),
        surface=surface(holding("300124.SZ", 60.95, flags=["DRAWDOWN_GE_15PCT"])),
        now=NOW,
    )
    row = lifecycle["subjects"][0]
    assert row["lifecycle_state"] == "HELD_HOLD_DRAWDOWN_MONITOR"
    assert row["current_action"] == "HOLD"
    assert "DRAWDOWN_MONITOR_ACTIVE" in row["mechanical_trigger_keys"]
    assert queue["records"] == []
    assert lifecycle["summary"]["reunderwrite_required_count"] == 0


def test_concentration_is_portfolio_review_not_thesis_exit() -> None:
    lifecycle, queue = build(
        recommendation=recommendation(rec("605090.SH", "HOLD", price=33.89, entry=31.0)),
        surface=surface(holding("605090.SH", 33.89, flags=["ACCOUNT_WEIGHT_GE_15PCT"])),
        now=NOW,
    )
    row = lifecycle["subjects"][0]
    assert row["lifecycle_state"] == "HELD_CONCENTRATION_REVIEW"
    assert row["current_action"] == "HOLD"
    assert queue["records"][0]["review_type"] == "PORTFOLIO_REVIEW_REQUIRED"
    assert queue["records"][0]["next_step"] == "PHASE3_TARGET_WEIGHT_AND_SIZING_REVIEW"


def test_semantic_clauses_are_armed_but_never_keyword_fired() -> None:
    lifecycle, _ = build(
        recommendation=recommendation(rec("000333.SZ", "HOLD")),
        surface=surface(holding("000333.SZ", 10.0)),
        now=NOW,
    )
    watch = lifecycle["subjects"][0]["semantic_watch"]
    assert watch["catalysts"] == ["catalyst one"]
    assert watch["kill_thesis"] == ["kill one"]
    assert watch["automatic_keyword_inference_authorized"] is False
    assert lifecycle["summary"]["automatic_semantic_trigger_count"] == 0


def test_prior_state_marks_only_new_transition_as_new_trigger() -> None:
    prior = {
        "lifecycle_id": "OLD",
        "subjects": [{
            "security_id": "605090.SH",
            "mechanical_trigger_keys": ["PORTFOLIO_CONCENTRATION_ACTIVE"],
        }],
    }
    lifecycle, queue = build(
        recommendation=recommendation(rec("605090.SH", "TRIM")),
        surface=surface(holding("605090.SH", 10.0, flags=["ACCOUNT_WEIGHT_GE_15PCT"])),
        prior=prior,
        now=NOW,
    )
    row = lifecycle["subjects"][0]
    assert row["new_trigger_keys"] == ["POSITION_ACTION_TRIM"]
    by_key = {x["trigger_key"]: x for x in queue["records"]}
    assert by_key["POSITION_ACTION_TRIM"]["transition"] == "NEW_TRIGGER"
    assert by_key["PORTFOLIO_CONCENTRATION_ACTIVE"]["transition"] == "PERSISTING"
