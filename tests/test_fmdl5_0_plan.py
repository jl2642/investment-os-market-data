import json
from pathlib import Path

from scripts.validate_fmdl5_0_plan import validate


PLAN = Path("config/fmdl5_0_cross_market_master_plan.json")


def load():
    return json.loads(PLAN.read_text(encoding="utf-8"))


def test_plan_accepts():
    assert validate(load()) == []


def test_phase_counts_are_frozen():
    plan = load()
    assert len(plan["fmdl5"]["formal_subphases"]) == 8
    assert len(plan["fmdl6"]["formal_subphases"]) == 10


def test_round_caps_are_bounded():
    plan = load()
    assert plan["fmdl5"]["maximum_total_rounds_including_repairs"] == 10
    assert plan["fmdl6"]["maximum_total_rounds_including_repairs"] == 13


def test_state_boundaries_and_trade_authority():
    plan = load()
    assert plan["trade_authority"] == "NONE"
    assert plan["shared_state_boundaries"]["real_account_action_requires_user_confirmation"] is True


def test_next_gate_is_fmdl5a():
    assert load()["next_gate"] == "FMDL-5A_MARKET_CONTRACT_AND_UNIVERSE_BOUNDARY"
