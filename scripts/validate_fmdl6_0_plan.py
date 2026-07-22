#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

PROGRAM_ID = "FMDL-6-0"
EXPECTED_PHASES = [
    "FMDL-6A_US_MARKET_CONTRACT_AND_SECURITY_IDENTITY",
    "FMDL-6B_SOURCE_INTERFACE_AND_ACCESS_BENCHMARK",
    "FMDL-6C_24_SECURITY_BENCHMARK_POOL",
    "FMDL-6D_MINIMAL_END_TO_END_DATA_CHAIN",
    "FMDL-6E_QUALITY_FAILURE_AND_COST_BENCHMARK",
    "FMDL-6-FINAL_RESUME_READY_OPERATIONAL_ACCEPTANCE",
]
EXPECTED_INTERFACES = {
    "SEC_EDGAR_IDENTITY_AND_SUBMISSIONS",
    "SEC_EDGAR_COMPANY_FACTS_AND_XBRL",
    "US_EXCHANGE_SECURITY_DIRECTORY",
    "FREE_DAILY_MARKET_CORPORATE_ACTION_AND_FX",
}
EXPECTED_DEFERRED = {
    "FMDL-6X1_CHANNEL_AND_INVESTABLE_UNIVERSE_REFRESH",
    "FMDL-6X2_FULL_UNIVERSE_AND_HISTORICAL_BUILD",
    "FMDL-6X3_FACTOR_SCREENING_AND_RESEARCH_PRODUCTION",
    "FMDL-6X4_INVESTMENT_OS_AND_PORTFOLIO_INTEGRATION",
}
EXPECTED_STATIC_ASSETS = {
    "docs/FMDL-6_START_HERE.md",
    "docs/FMDL-6-0_US_EQUITY_INTERFACE_AND_RESUME_READY_PILOT_ARCHITECTURE.md",
    "docs/FMDL-6-0_PRIMARY_SOURCE_AND_INTERFACE_REGISTER.md",
    "docs/FMDL-6-0_DEFERRED_FULL_BUILD_PLAN.md",
    "config/fmdl6_0_us_equity_resume_ready_pilot_architecture.json",
    "schemas/fmdl6_0_resume_ready_pilot_contract_v1.schema.json",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(repo_root: Path, plan_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    plan = load_json(plan_path)
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def check(check_id: str, condition: bool, actual: Any = None, expected: Any = None) -> None:
        checks.append({
            "check_id": check_id,
            "status": "PASS" if condition else "FAIL",
            "actual": actual,
            "expected": expected,
        })
        if not condition:
            errors.append(check_id)

    check("PROGRAM_ID", plan.get("program_id") == PROGRAM_ID, plan.get("program_id"), PROGRAM_ID)
    check("STATUS_CANDIDATE", plan.get("status") == "ARCHITECTURE_CANDIDATE", plan.get("status"), "ARCHITECTURE_CANDIDATE")
    check("TRADE_AUTHORITY_NONE", plan.get("trade_authority") == "NONE", plan.get("trade_authority"), "NONE")

    entry = plan.get("entry_gate", {})
    pointer_path = repo_root / str(entry.get("pointer_path", ""))
    check("ENTRY_POINTER_EXISTS", pointer_path.is_file(), str(pointer_path), "existing file")
    if pointer_path.is_file():
        pointer = load_json(pointer_path)
        check("ENTRY_RELEASE_ID", pointer.get("release_id") == entry.get("required_release_id"), pointer.get("release_id"), entry.get("required_release_id"))
        check("ENTRY_STATUS", pointer.get("status") == entry.get("required_status"), pointer.get("status"), entry.get("required_status"))
        check("ENTRY_NEXT_GATE", pointer.get("next_gate") == entry.get("required_next_gate"), pointer.get("next_gate"), entry.get("required_next_gate"))
        check("ENTRY_TRADE_AUTHORITY", pointer.get("trade_authority") == "NONE", pointer.get("trade_authority"), "NONE")

    scope = plan.get("scope_decision", {})
    check("SCOPE_MODE", scope.get("scope_mode") == "INTERFACE_AND_SMALL_BENCHMARK_ONLY", scope.get("scope_mode"), "INTERFACE_AND_SMALL_BENCHMARK_ONLY")
    check("BENCHMARK_TARGET_24", scope.get("benchmark_security_target") == 24, scope.get("benchmark_security_target"), 24)
    forbidden_authorizations = [
        "full_universe_development_authorized",
        "full_history_backfill_authorized",
        "full_financial_normalization_authorized",
        "factor_and_screening_production_authorized",
        "candidate_pool_integration_authorized",
        "simulation_integration_authorized",
        "real_account_integration_authorized",
        "order_generation_authorized",
        "automatic_trade_authority_authorized",
    ]
    for key in forbidden_authorizations:
        check(f"AUTHORIZATION_FALSE:{key}", scope.get(key) is False, scope.get(key), False)

    execution = plan.get("current_execution_plan", {})
    phases = execution.get("formal_subphases_after_fmdl6_0", [])
    check("FORMAL_PHASE_SEQUENCE", phases == EXPECTED_PHASES, phases, EXPECTED_PHASES)
    check("FORMAL_PHASE_COUNT", execution.get("formal_subphase_count_after_fmdl6_0") == 6, execution.get("formal_subphase_count_after_fmdl6_0"), 6)
    check("TOTAL_PLANNED_ROUNDS", execution.get("total_planned_round_count_including_fmdl6_0") == 7, execution.get("total_planned_round_count_including_fmdl6_0"), 7)
    max_rounds = execution.get("maximum_total_rounds_including_targeted_repairs")
    check("ROUND_CAP", isinstance(max_rounds, int) and max_rounds <= 9, max_rounds, "<=9")

    interfaces = {row.get("interface_id") for row in plan.get("required_source_interfaces", [])}
    check("SOURCE_INTERFACE_SET", interfaces == EXPECTED_INTERFACES, sorted(interfaces), sorted(EXPECTED_INTERFACES))

    deferred_rows = plan.get("deferred_full_build_backlog", [])
    deferred = {row.get("phase_id") for row in deferred_rows}
    check("DEFERRED_PHASE_SET", deferred == EXPECTED_DEFERRED, sorted(deferred), sorted(EXPECTED_DEFERRED))
    check("DEFERRED_NOT_AUTHORIZED", all(row.get("status") == "DEFERRED_NOT_AUTHORIZED" for row in deferred_rows), [row.get("status") for row in deferred_rows], "all DEFERRED_NOT_AUTHORIZED")

    activation = plan.get("activation_gate", {})
    check("ACTIVATION_GATE_CLOSED", activation.get("gate_status") == "CLOSED", activation.get("gate_status"), "CLOSED")
    check("ACTIVATION_CONDITION_COUNT", len(activation.get("required_conditions", [])) == 5, len(activation.get("required_conditions", [])), 5)
    check("IMPLICIT_ACTIVATION_FORBIDDEN", activation.get("partial_or_implicit_activation_forbidden") is True, activation.get("partial_or_implicit_activation_forbidden"), True)

    boundaries = plan.get("shared_state_boundaries", {})
    for key in (
        "research_graduation_is_not_candidate_admission",
        "candidate_admission_is_not_simulation_admission",
        "simulation_admission_is_not_real_account_admission",
        "real_account_action_requires_user_confirmation",
        "us_pilot_is_not_us_investment_capability_completion",
        "benchmark_pool_is_not_candidate_pool",
    ):
        check(f"BOUNDARY_TRUE:{key}", boundaries.get(key) is True, boundaries.get(key), True)
    check("BOUNDARY_TRADE_AUTHORITY", boundaries.get("trade_authority") == "NONE", boundaries.get("trade_authority"), "NONE")

    supersession = plan.get("controlled_supersession", {})
    historical_path = repo_root / str(supersession.get("historical_plan_path", ""))
    check("HISTORICAL_PLAN_PRESERVED", historical_path.is_file(), str(historical_path), "existing file")
    if historical_path.is_file():
        historical = load_json(historical_path)
        check("HISTORICAL_FMDL6_PHASE_COUNT", len(historical.get("fmdl6", {}).get("formal_subphases", [])) == 10, len(historical.get("fmdl6", {}).get("formal_subphases", [])), 10)
    check("HISTORICAL_RELEASE_MUTATION_FORBIDDEN", supersession.get("historical_release_mutation_authorized") is False, supersession.get("historical_release_mutation_authorized"), False)
    check("DEFERRED_LOGIC_PRESERVED", supersession.get("future_full_build_logic_preserved_as_deferred_backlog") is True, supersession.get("future_full_build_logic_preserved_as_deferred_backlog"), True)

    static_assets = set(plan.get("resume_ready_package", {}).get("required_static_assets", []))
    check("STATIC_ASSET_SET", static_assets == EXPECTED_STATIC_ASSETS, sorted(static_assets), sorted(EXPECTED_STATIC_ASSETS))
    for path_text in sorted(EXPECTED_STATIC_ASSETS):
        check(f"STATIC_ASSET_EXISTS:{path_text}", (repo_root / path_text).is_file(), path_text, "existing file")
    check("CHAT_HISTORY_NOT_REQUIRED", plan.get("resume_ready_package", {}).get("chat_history_required_for_restore") is False, plan.get("resume_ready_package", {}).get("chat_history_required_for_restore"), False)

    check("RELEASE_SEQUENCE", plan.get("publication", {}).get("release_sequence") == 19, plan.get("publication", {}).get("release_sequence"), 19)
    check("EXIT_STATUS", plan.get("exit_status") == "FMDL6_0_US_EQUITY_RESUME_READY_PILOT_ARCHITECTURE_ACCEPTED", plan.get("exit_status"), "FMDL6_0_US_EQUITY_RESUME_READY_PILOT_ARCHITECTURE_ACCEPTED")
    check("NEXT_GATE", plan.get("next_gate") == "FMDL-6A_US_MARKET_CONTRACT_AND_SECURITY_IDENTITY", plan.get("next_gate"), "FMDL-6A_US_MARKET_CONTRACT_AND_SECURITY_IDENTITY")

    return checks, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--plan", default="config/fmdl6_0_us_equity_resume_ready_pilot_architecture.json")
    parser.add_argument("--decision", default="outputs/fmdl6_0/candidate/FMDL6_0_DECISION.json")
    parser.add_argument("--validation", default="outputs/fmdl6_0/candidate/FMDL6_0_VALIDATION.json")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    plan_path = repo_root / args.plan
    plan = load_json(plan_path)
    checks, errors = validate(repo_root, plan_path)
    plan_sha = sha256_file(plan_path)

    decision = {
        "program_id": PROGRAM_ID,
        "status": plan["exit_status"] if not errors else "FMDL6_0_ARCHITECTURE_REJECTED",
        "hard_failures": errors,
        "plan_sha256": plan_sha,
        "scope_mode": plan["scope_decision"]["scope_mode"],
        "benchmark_security_target": plan["scope_decision"]["benchmark_security_target"],
        "formal_subphase_count_after_fmdl6_0": plan["current_execution_plan"]["formal_subphase_count_after_fmdl6_0"],
        "total_planned_round_count_including_fmdl6_0": plan["current_execution_plan"]["total_planned_round_count_including_fmdl6_0"],
        "maximum_total_rounds_including_targeted_repairs": plan["current_execution_plan"]["maximum_total_rounds_including_targeted_repairs"],
        "activation_gate_status": plan["activation_gate"]["gate_status"],
        "next_gate": plan["next_gate"],
        "trade_authority": "NONE",
    }
    validation = {
        "program_id": PROGRAM_ID,
        "validation": "PASS" if not errors else "FAIL",
        "check_count": len(checks),
        "pass_count": sum(row["status"] == "PASS" for row in checks),
        "error_count": len(errors),
        "errors": errors,
        "checks": checks,
        "plan_sha256": plan_sha,
        "trade_authority": "NONE",
    }
    write_json(repo_root / args.decision, decision)
    write_json(repo_root / args.validation, validation)
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
