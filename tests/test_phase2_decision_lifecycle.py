from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

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


def test_valuation_exhaustion_reopens_holding_d2() -> None:
    r = rec("600001.SH", "HOLD", price=100.0, entry=80.0, blocker=None)
    r["base_value"] = 110.0
    r["probability_weighted_value"] = 108.0
    lifecycle, queue = build(
        recommendation=recommendation(r),
        surface=surface(holding("600001.SH", 112.0)),
        market_rows={"600001.SH": {"price": 112.0, "as_of_date": "2026-09-02"}},
        market_date="2026-09-02",
        now=NOW,
    )
    row = lifecycle["subjects"][0]
    assert row["mark_expected_return"] < 0
    assert "VALUATION_EXHAUSTION_REUNDERWRITE" in row["mechanical_trigger_keys"]
    q = [x for x in queue["records"] if x["trigger_key"] == "VALUATION_EXHAUSTION_REUNDERWRITE"]
    assert len(q) == 1
    assert q[0]["review_type"] == "REUNDERWRITE_REQUIRED"
    assert q[0]["next_step"] == "FRESH_D2_FOR_HOLD_TRIM_OR_EXIT"


def test_new_drawdown_cross_reunderwrites_once_then_persists_as_monitor() -> None:
    prior = {
        "lifecycle_id": "OLD",
        "input_identity": {},
        "subjects": [{
            "security_id": "300124.SZ",
            "mechanical_trigger_keys": [],
        }],
    }
    current, queue = build(
        recommendation=recommendation(rec("300124.SZ", "HOLD", price=60.0, entry=59.0)),
        surface=surface(holding("300124.SZ", 60.0, flags=["DRAWDOWN_GE_15PCT"])),
        prior=prior,
        now=NOW,
    )
    assert "DRAWDOWN_MONITOR_ACTIVE" in current["subjects"][0]["new_trigger_keys"]
    q = [x for x in queue["records"] if x["trigger_key"] == "DRAWDOWN_MONITOR_ACTIVE"]
    assert len(q) == 1
    assert q[0]["review_type"] == "REUNDERWRITE_REQUIRED"

    prior2 = current
    again, queue2 = build(
        recommendation=recommendation(rec("300124.SZ", "HOLD", price=60.0, entry=59.0)),
        surface=surface(holding("300124.SZ", 60.0, flags=["DRAWDOWN_GE_15PCT"])),
        prior=prior2,
        now=NOW,
    )
    assert again["subjects"][0]["new_trigger_keys"] == []
    assert not [
        x for x in queue2["records"]
        if x["trigger_key"] == "DRAWDOWN_MONITOR_ACTIVE"
        and x["review_type"] == "REUNDERWRITE_REQUIRED"
    ]


def test_financial_context_advance_creates_equity_triage_not_etf_noise() -> None:
    prior = {
        "lifecycle_id": "OLD",
        "input_identity": {"financial_statement_watermark": "2026-08-28"},
        "subjects": [],
    }
    eq = rec("600036.SH", "HOLD", price=40.0, entry=38.0)
    etf = rec("159352.SZ", "HOLD", price=1.2, entry=1.1)
    etf["security_name"] = "A500ETF南方"
    lifecycle_payload, queue = build(
        recommendation=recommendation(eq, etf),
        surface=surface(
            holding("600036.SH", 40.0),
            holding("159352.SZ", 1.2),
        ),
        prior=prior,
        financial_context={
            "domain_id": "FINANCIAL_STATEMENT_CONTEXT",
            "data_watermark": "2026-09-30",
            "watermark_sort_key": "2026-09-30",
        },
        now=NOW,
    )
    q = [x for x in queue["records"] if x["trigger_key"] == "FINANCIAL_CONTEXT_ADVANCED_TRIAGE"]
    assert [x["security_id"] for x in q] == ["600036.SH"]
    assert lifecycle_payload["summary"]["financial_context_triage_count"] == 1


def test_material_event_evidence_forces_fresh_d2_without_auto_action() -> None:
    prior = {
        "lifecycle_id": "OLD",
        "input_identity": {"financial_statement_watermark": "2026-08-28"},
        "subjects": [],
    }
    lifecycle_payload, queue = build(
        recommendation=recommendation(rec("600309.SH", "HOLD", price=77.0, entry=72.0)),
        surface=surface(holding("600309.SH", 77.0)),
        prior=prior,
        financial_context={"data_watermark": "2026-08-28"},
        event_evidence={
            "event_evidence_id": "EVENTS_1",
            "records": [{
                "security_id": "600309.SH",
                "material": True,
                "event_type": "EARNINGS_GUIDANCE",
                "summary": "Management materially cut guidance.",
                "thesis_break_risk": True,
            }],
        },
        now=NOW,
    )
    q = [x for x in queue["records"] if x["trigger_key"] == "MATERIAL_FUNDAMENTAL_EVENT_REUNDERWRITE"]
    assert len(q) == 1
    assert q[0]["priority"] == "CRITICAL"
    assert q[0]["review_type"] == "REUNDERWRITE_REQUIRED"
    assert lifecycle_payload["controls"]["automatic_buy_sell"] is False
    assert lifecycle_payload["summary"]["material_event_trigger_count"] == 1


def test_holding_count_is_dynamic_across_portfolio_size_changes() -> None:
    for count in (7, 22, 23):
        recs = [rec(f"{600000 + i}.SH", "HOLD") for i in range(count)]
        holdings = [holding(f"{600000 + i}.SH", 10.0) for i in range(count)]
        lifecycle, _ = build(
            recommendation=recommendation(*recs),
            surface=surface(*holdings),
            now=NOW,
        )
        assert lifecycle["summary"]["held_subject_count"] == count
        assert lifecycle["summary"]["subject_count"] == count


def test_phase2_workflow_does_not_freeze_holding_count() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/final-closure-phase2-decision-lifecycle.yml"
    ).read_text(encoding="utf-8")
    assert 'held_subject_count"] == 22' not in workflow
    assert 'surface["executive"]["portfolio_holding_count"]' in workflow


def test_formal_buy_hurdle_cross_routes_fresh_d2_without_buy_promotion() -> None:
    """The 10% formal gate and 15% preferred entry have distinct meanings."""
    for sid, mark, preferred, formal in (
        ("300230.SZ", 4.01, 3.94, 4.061538461538461),
        ("301175.SZ", 5.36, 5.33, 5.5681818181818175),
    ):
        candidate = rec(sid, "BUY_BELOW", price=mark, entry=preferred)
        candidate["formal_buy_entry_price"] = formal
        candidate["portfolio_implication"] = "NEW_CAPITAL_CANDIDATE"
        lifecycle, queue = build(
            recommendation=recommendation(candidate),
            surface=surface(),
            market_rows={sid: {"price": mark, "as_of_date": "2026-11-20"}},
            market_date="2026-11-20",
            now=NOW,
        )
        subject = lifecycle["subjects"][0]
        assert subject["lifecycle_state"] == "FLAT_PRICE_REUNDERWRITE"
        assert subject["current_action"] == "BUY_BELOW"
        assert subject["ready_for_user_decision"] is False
        assert subject["mechanical_trigger_keys"] == ["BUY_BELOW_FORMAL_HURDLE_REUNDERWRITE"]
        assert len(queue["records"]) == 1
        row = queue["records"][0]
        assert row["review_type"] == "REUNDERWRITE_REQUIRED"
        assert row["next_step"] == "FRESH_D2_BEFORE_ANY_BUY"
        assert row["orders"] == 0
        assert lifecycle["controls"]["automatic_buy_sell"] is False
        assert lifecycle["orders"] == 0


def test_formal_buy_hurdle_not_crossed_does_not_create_research_queue() -> None:
    candidate = rec("301175.SZ", "BUY_BELOW", price=5.59, entry=5.33)
    candidate["formal_buy_entry_price"] = 5.5681818181818175
    lifecycle, queue = build(
        recommendation=recommendation(candidate),
        surface=surface(),
        market_rows={"301175.SZ": {"price": 5.59, "as_of_date": "2026-11-13"}},
        market_date="2026-11-13",
        now=NOW,
    )
    assert lifecycle["subjects"][0]["lifecycle_state"] == "FLAT_WAIT_BUY_BELOW"
    assert queue["records"] == []


def test_formal_gate_review_is_idempotent_until_signal_changes() -> None:
    candidate = rec("300230.SZ", "BUY_BELOW", price=4.01, entry=3.94)
    candidate["formal_buy_entry_price"] = 4.061538461538461
    kwargs = {
        "recommendation": recommendation(candidate),
        "surface": surface(),
        "market_rows": {"300230.SZ": {"price": 4.01, "as_of_date": "2026-11-20"}},
        "market_date": "2026-11-20",
        "now": NOW,
    }
    first, first_queue = build(prior={"lifecycle_id": "PREVIOUS", "subjects": []}, **kwargs)
    again, second_queue = build(prior=first, **kwargs)
    assert len(first_queue["records"]) == len(second_queue["records"]) == 1
    assert first_queue["records"][0]["transition"] == "NEW_TRIGGER"
    assert second_queue["records"][0]["transition"] == "PERSISTING"
    assert again["subjects"][0]["new_trigger_keys"] == []
    assert again["orders"] == 0


def test_held_position_and_missing_formal_gate_do_not_open_new_buy_route() -> None:
    candidate = rec("300230.SZ", "BUY_BELOW", price=4.01, entry=3.94)
    candidate["formal_buy_entry_price"] = 4.061538461538461
    _, held_queue = build(
        recommendation=recommendation(candidate),
        surface=surface(holding("300230.SZ", 4.01)),
        market_rows={"300230.SZ": {"price": 4.01, "as_of_date": "2026-11-20"}},
        market_date="2026-11-20",
        now=NOW,
    )
    assert not any(x["trigger_key"] == "BUY_BELOW_FORMAL_HURDLE_REUNDERWRITE"
                   for x in held_queue["records"])

    candidate.pop("formal_buy_entry_price")
    _, no_formal_queue = build(
        recommendation=recommendation(candidate),
        surface=surface(),
        market_rows={"300230.SZ": {"price": 4.01, "as_of_date": "2026-11-20"}},
        market_date="2026-11-20",
        now=NOW,
    )
    assert no_formal_queue["records"] == []
