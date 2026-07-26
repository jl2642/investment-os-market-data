from pathlib import Path
from datetime import date, timedelta
import copy
import json

import pytest

from investment_os_control.core import (
    AuthorityError,
    PromotionError,
    assess_freshness,
    canonical_hash,
    classify_semantic_change,
    enforce_market_permission,
    gate_operating_product,
    read_json,
    route_event,
    validate_runtime,
)

HERE = Path(__file__).resolve()
RUNTIME = HERE.parents[2]
BINDINGS = RUNTIME / "50_MARKET_CAPABILITY_BINDINGS"


def a_share_binding_date() -> str:
    return str(read_json(BINDINGS / "A_SHARE_CURRENT.json")["as_of_date"])


def test_runtime_validation_passes_for_current_binding_date():
    evaluation_date = a_share_binding_date()
    result = validate_runtime(RUNTIME, evaluation_date)
    assert result["status"] == "PASS"
    assert result["trade_authority"] == "NONE"
    assert "A_SHARE_LIVE_ACTION_BLOCKED_BY_STALENESS" not in result["warnings"]


def test_a_share_daily_snapshot_blocks_when_stale():
    as_of_date = a_share_binding_date()
    evaluation_date = (
        date.fromisoformat(as_of_date) + timedelta(days=4)
    ).isoformat()
    result = assess_freshness(as_of_date, evaluation_date, 3, "BLOCK")
    assert result["stale"] is True
    assert result["outcome"] == "BLOCK"


def test_runtime_validation_blocks_stale_market_data():
    as_of_date = a_share_binding_date()
    evaluation_date = (
        date.fromisoformat(as_of_date) + timedelta(days=4)
    ).isoformat()
    result = validate_runtime(RUNTIME, evaluation_date)
    assert result["status"] == "PASS"
    assert result["trade_authority"] == "NONE"
    assert "A_SHARE_LIVE_ACTION_BLOCKED_BY_STALENESS" in result["warnings"]


def test_universe_uses_restrict_not_live_action():
    result = assess_freshness("2026-07-17", "2026-07-24", 7, "LABEL_AND_RESTRICT")
    assert result["stale"] is False
    assert result["outcome"] == "PASS"


def test_metadata_only_new_run_is_not_semantic_change():
    old = {"run_id": "A", "generated_at": "T1", "rows": 5528, "status": "ACTIVE"}
    new = {"run_id": "B", "generated_at": "T2", "rows": 5528, "status": "ACTIVE"}
    result = classify_semantic_change(old, new)
    assert result["exact_change"] is True
    assert result["semantic_change"] is False
    assert result["run_id_only_or_metadata_only"] is True


def test_real_semantic_change_detected():
    old = {"run_id": "A", "rows": 5528}
    new = {"run_id": "B", "rows": 5529}
    assert classify_semantic_change(old, new)["semantic_change"] is True


def test_canonical_hash_is_order_independent():
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})


def test_hk_research_allowed():
    hk = read_json(BINDINGS / "HK_CONNECT_CURRENT.json")
    assert enforce_market_permission(hk, "RESEARCH")["allowed"] is True


def test_hk_automatic_candidate_admission_blocked():
    hk = read_json(BINDINGS / "HK_CONNECT_CURRENT.json")
    assert enforce_market_permission(hk, "CANDIDATE_ADMISSION")["outcome"] == "BLOCK"


def test_hk_automatic_real_account_admission_blocked():
    hk = read_json(BINDINGS / "HK_CONNECT_CURRENT.json")
    assert enforce_market_permission(hk, "REAL_ACCOUNT_ADMISSION")["allowed"] is False


def test_us_research_allowed():
    us = read_json(BINDINGS / "US_RESEARCH_ADAPTER_CURRENT.json")
    assert enforce_market_permission(us, "RESEARCH")["allowed"] is True


@pytest.mark.parametrize(
    "action",
    ["CANDIDATE_PROPOSAL", "SIMULATION_PROPOSAL", "REAL_ACTION_PROPOSAL", "ORDER_EXECUTION"],
)
def test_us_formal_investment_channels_closed(action):
    us = read_json(BINDINGS / "US_RESEARCH_ADAPTER_CURRENT.json")
    assert enforce_market_permission(us, action)["allowed"] is False


def test_trade_authority_escalation_fails_closed():
    binding = read_json(BINDINGS / "A_SHARE_CURRENT.json")
    binding["trade_authority"] = "AUTO"
    with pytest.raises(AuthorityError):
        enforce_market_permission(binding, "RESEARCH")


@pytest.mark.parametrize("level", ["E0", "E1", "E2", "E3", "E4", "E5"])
def test_all_event_levels_route_without_trade(level):
    taxonomy = read_json(RUNTIME / "60_OPERATIONS_AND_EVENT" / "EVENT_TAXONOMY_AND_ROUTING.json")
    result = route_event({"event_id": f"X-{level}", "level": level}, taxonomy)
    assert result["automatic_trade"] is False
    assert result["state_change_mode"] == "PROPOSAL_ONLY"
    assert result["trade_authority"] == "NONE"


def test_e4_routes_urgent_decision_support():
    taxonomy = read_json(RUNTIME / "60_OPERATIONS_AND_EVENT" / "EVENT_TAXONOMY_AND_ROUTING.json")
    result = route_event({"event_id": "E4-1", "level": "E4"}, taxonomy)
    assert "URGENT_DECISION_SUPPORT" in result["routes"]


def test_e5_fails_closed():
    taxonomy = read_json(RUNTIME / "60_OPERATIONS_AND_EVENT" / "EVENT_TAXONOMY_AND_ROUTING.json")
    result = route_event({"event_id": "E5-1", "level": "E5"}, taxonomy)
    assert "FAIL_CLOSED" in result["routes"]
    assert "RECOVERY_QUEUE" in result["routes"]


def test_candidate_product_is_not_current():
    result = gate_operating_product({
        "product_id": "D1",
        "status": "CANDIDATE",
        "investment_state_mutations": 0,
        "orders": 0,
    })
    assert result["eligible_for_current"] is False


def test_current_without_qc_and_promotion_is_rejected():
    with pytest.raises(PromotionError):
        gate_operating_product({
            "product_id": "D2",
            "status": "CURRENT",
            "investment_state_mutations": 0,
            "orders": 0,
        })


def test_qc_and_promotion_can_make_product_eligible():
    result = gate_operating_product({
        "product_id": "D3",
        "status": "CURRENT",
        "qc_status": "PASS",
        "promotion_record": {"id": "P1"},
        "investment_state_mutations": 0,
        "orders": 0,
    })
    assert result["eligible_for_current"] is True


def test_scheduled_product_state_mutation_rejected():
    with pytest.raises(PromotionError):
        gate_operating_product({
            "product_id": "D4",
            "status": "CANDIDATE",
            "investment_state_mutations": 1,
            "orders": 0,
        })


def test_order_generation_rejected():
    with pytest.raises(PromotionError):
        gate_operating_product({
            "product_id": "D5",
            "status": "CANDIDATE",
            "investment_state_mutations": 0,
            "orders": 1,
        })


def test_cadences_are_not_active():
    registry = read_json(RUNTIME / "60_OPERATIONS_AND_EVENT" / "CADENCE_REGISTRY.json")
    assert len(registry["cadences"]) == 6
    assert all(
        row["activation"] in {"DISABLED_UNTIL_WP6", "INTERFACE_ACTIVE_PRODUCER_DISABLED"}
        for row in registry["cadences"]
    )


def test_candidate_alpha_is_blocked():
    contract = read_json(RUNTIME / "70_ATTRIBUTION_AND_CALIBRATION" / "CANDIDATE_OUTCOME_CONTRACT.json")
    assert contract["alpha_claim_allowed"] is False
    assert contract["current_status"] in {
        "BLOCKED_NO_VALID_CORE20_ENTRY_BASELINES",
        "BLOCKED_INSUFFICIENT_COMPLETED_EVALUATION_WINDOWS",
    }
    if contract["current_status"] == "BLOCKED_INSUFFICIENT_COMPLETED_EVALUATION_WINDOWS":
        assert contract["valid_entry_baseline_count"] == 2
        assert contract["completed_evaluation_windows"] == []


def test_rule_change_is_not_automatic():
    contract = read_json(RUNTIME / "70_ATTRIBUTION_AND_CALIBRATION" / "RULE_CALIBRATION_CONTRACT.json")
    assert contract["automatic_rule_change"] is False
    assert contract["single_case_rule_change_allowed"] is False
    assert "USER_APPROVAL_REQUIRED" in contract["lifecycle"]


def test_zero_mutation_proof():
    zero = read_json(RUNTIME / "00_CONTROL" / "ZERO_MUTATION_PROOF.json")
    assert zero["candidate_membership_mutations"] == 0
    assert zero["simulation_trade_mutations"] == 0
    assert zero["real_account_mutations"] == 0
    assert zero["rule_auto_mutations"] == 0
    assert zero["orders"] == 0
    assert zero["trade_authority"] == "NONE"


def test_fmdl7_cross_market_controls():
    binding = read_json(BINDINGS / "FMDL7_GOVERNANCE_BINDING.json")
    controls = binding["controls"]
    assert controls["human_user_is_only_investment_authority"] is True
    assert controls["candidate_simulation_real_account_state_domains_separate"] is True
    assert controls["automatic_candidate_promotion"] is False
    assert controls["automatic_rule_mutation"] is False
    assert controls["trade_authority"] == "NONE"


def test_replay_is_deterministic():
    registry = read_json(BINDINGS / "UPSTREAM_CURRENT_REGISTRY.json")
    first = canonical_hash(registry)
    second = canonical_hash(json.loads(json.dumps(registry)))
    assert first == second
