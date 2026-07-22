from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from fmdl6_0_publisher import build_candidate, sha256_file  # noqa: E402
from validate_fmdl6_0_plan import EXPECTED_DEFERRED, EXPECTED_INTERFACES, EXPECTED_PHASES, validate  # noqa: E402

PLAN_PATH = ROOT / "config/fmdl6_0_us_equity_resume_ready_pilot_architecture.json"


def load_plan() -> dict:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def accepted_decision(plan: dict) -> dict:
    return {
        "program_id": "FMDL-6-0",
        "status": plan["exit_status"],
        "hard_failures": [],
        "plan_sha256": sha256_file(PLAN_PATH),
        "scope_mode": plan["scope_decision"]["scope_mode"],
        "benchmark_security_target": 24,
        "formal_subphase_count_after_fmdl6_0": 6,
        "total_planned_round_count_including_fmdl6_0": 7,
        "maximum_total_rounds_including_targeted_repairs": 9,
        "activation_gate_status": "CLOSED",
        "next_gate": plan["next_gate"],
        "trade_authority": "NONE",
    }


def accepted_validation() -> dict:
    return {
        "validation": "PASS",
        "check_count": 1,
        "pass_count": 1,
        "error_count": 0,
        "errors": [],
    }


def test_architecture_plan_passes_all_gates() -> None:
    checks, errors = validate(ROOT, PLAN_PATH)
    assert not errors
    assert checks
    assert all(row["status"] == "PASS" for row in checks)


def test_scope_is_bounded_and_non_operational() -> None:
    plan = load_plan()
    scope = plan["scope_decision"]
    assert scope["scope_mode"] == "INTERFACE_AND_SMALL_BENCHMARK_ONLY"
    assert scope["benchmark_security_target"] == 24
    forbidden = [key for key, value in scope.items() if key.endswith("_authorized") and value is not False]
    assert forbidden == []
    assert plan["trade_authority"] == "NONE"


def test_phase_and_interface_sets_are_frozen() -> None:
    plan = load_plan()
    assert plan["current_execution_plan"]["formal_subphases_after_fmdl6_0"] == EXPECTED_PHASES
    assert {row["interface_id"] for row in plan["required_source_interfaces"]} == EXPECTED_INTERFACES
    assert {row["phase_id"] for row in plan["deferred_full_build_backlog"]} == EXPECTED_DEFERRED


def test_activation_gate_is_closed_and_explicit() -> None:
    plan = load_plan()
    gate = plan["activation_gate"]
    assert gate["gate_status"] == "CLOSED"
    assert gate["partial_or_implicit_activation_forbidden"] is True
    assert len(gate["required_conditions"]) == 5
    assert "USER_EXPLICITLY_APPROVES_FULL_BUILD" in gate["required_conditions"]


def test_publisher_is_deterministic(tmp_path: Path) -> None:
    plan = load_plan()
    decision = accepted_decision(plan)
    validation = accepted_validation()
    first = tmp_path / "first"
    second = tmp_path / "second"
    release_one = build_candidate(ROOT, first, plan, decision, validation)
    release_two = build_candidate(ROOT, second, plan, decision, validation)
    assert release_one == release_two
    first_files = {path.name: sha256_file(path) for path in first.iterdir() if path.is_file()}
    second_files = {path.name: sha256_file(path) for path in second.iterdir() if path.is_file()}
    assert first_files == second_files
    assert release_one["scope_mode"] == "INTERFACE_AND_SMALL_BENCHMARK_ONLY"
    assert release_one["activation_gate_status"] == "CLOSED"


def test_failed_decision_cannot_publish(tmp_path: Path) -> None:
    plan = load_plan()
    decision = accepted_decision(plan)
    decision["hard_failures"] = ["SYNTHETIC_FAILURE"]
    with pytest.raises(ValueError):
        build_candidate(ROOT, tmp_path / "candidate", plan, decision, accepted_validation())


def test_trade_authority_mutation_cannot_publish(tmp_path: Path) -> None:
    plan = copy.deepcopy(load_plan())
    plan["trade_authority"] = "BROKER"
    with pytest.raises(ValueError):
        build_candidate(ROOT, tmp_path / "candidate", plan, accepted_decision(load_plan()), accepted_validation())
