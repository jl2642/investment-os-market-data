from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

PROGRAM_ID = "FMDL-6-0"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_payload(plan: dict[str, Any], decision: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "program_id": PROGRAM_ID,
        "plan_sha256": decision["plan_sha256"],
        "validation": validation["validation"],
        "entry_release_id": plan["entry_gate"]["required_release_id"],
        "investment_os_release_id": plan["accepted_cross_market_base"]["investment_os_release_id"],
        "fmdl5_final_release_id": plan["accepted_cross_market_base"]["fmdl5_final_release_id"],
        "scope_mode": plan["scope_decision"]["scope_mode"],
        "benchmark_security_target": plan["scope_decision"]["benchmark_security_target"],
        "formal_subphases_after_fmdl6_0": plan["current_execution_plan"]["formal_subphases_after_fmdl6_0"],
        "source_interface_ids": [row["interface_id"] for row in plan["required_source_interfaces"]],
        "deferred_phase_ids": [row["phase_id"] for row in plan["deferred_full_build_backlog"]],
        "activation_gate": plan["activation_gate"],
        "next_gate": plan["next_gate"],
        "trade_authority": "NONE",
    }


def build_candidate(
    repo_root: Path,
    candidate_root: Path,
    plan: dict[str, Any],
    decision: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    if decision.get("hard_failures"):
        raise ValueError("cannot publish a failed FMDL-6-0 architecture decision")
    if validation.get("validation") != "PASS" or validation.get("error_count") != 0:
        raise ValueError("cannot publish an unvalidated FMDL-6-0 architecture decision")
    if plan.get("trade_authority") != "NONE":
        raise ValueError("trade authority must remain NONE")

    if candidate_root.exists():
        shutil.rmtree(candidate_root)
    candidate_root.mkdir(parents=True, exist_ok=True)

    payload = canonical_payload(plan, decision, validation)
    canonical_sha = sha256_bytes(stable_json(payload).encode("utf-8"))
    release_id = f"FMDL6_0_{plan['as_of_date'].replace('-', '')}_{canonical_sha[:12]}"

    release = {
        "program_id": PROGRAM_ID,
        "program_name": plan["program_name"],
        "release_id": release_id,
        "release_sequence": plan["publication"]["release_sequence"],
        "as_of_date": plan["as_of_date"],
        "status": plan["exit_status"],
        "canonical_sha256": canonical_sha,
        "plan_sha256": decision["plan_sha256"],
        "scope_mode": plan["scope_decision"]["scope_mode"],
        "benchmark_security_target": plan["scope_decision"]["benchmark_security_target"],
        "formal_subphase_count_after_fmdl6_0": plan["current_execution_plan"]["formal_subphase_count_after_fmdl6_0"],
        "total_planned_round_count_including_fmdl6_0": plan["current_execution_plan"]["total_planned_round_count_including_fmdl6_0"],
        "maximum_total_rounds_including_targeted_repairs": plan["current_execution_plan"]["maximum_total_rounds_including_targeted_repairs"],
        "activation_gate_status": plan["activation_gate"]["gate_status"],
        "full_universe_development_authorized": False,
        "candidate_pool_integration_authorized": False,
        "simulation_integration_authorized": False,
        "real_account_integration_authorized": False,
        "order_generation_authorized": False,
        "next_gate": plan["next_gate"],
        "authority": plan["authority"],
        "trade_authority": "NONE",
    }

    decision_out = {**decision, "release_id": release_id, "canonical_sha256": canonical_sha}
    validation_out = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "canonical_sha256": canonical_sha,
        "validation": validation["validation"],
        "check_count": validation["check_count"],
        "pass_count": validation["pass_count"],
        "error_count": validation["error_count"],
        "errors": validation["errors"],
        "same_input_replay_required": True,
        "trade_authority": "NONE",
    }
    activation = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "gate_status": plan["activation_gate"]["gate_status"],
        "required_conditions": plan["activation_gate"]["required_conditions"],
        "full_build_activation_rule": plan["activation_gate"]["full_build_activation_rule"],
        "partial_or_implicit_activation_forbidden": plan["activation_gate"]["partial_or_implicit_activation_forbidden"],
        "full_universe_development_authorized": False,
        "candidate_pool_integration_authorized": False,
        "simulation_or_real_account_integration_authorized": False,
        "trade_authority": "NONE",
    }
    deferred = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "status": "DEFERRED_FULL_BUILD_NOT_AUTHORIZED",
        "items": plan["deferred_full_build_backlog"],
        "activation_gate_status": plan["activation_gate"]["gate_status"],
        "trade_authority": "NONE",
    }
    source_plan = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "status": "INTERFACES_DEFINED_BENCHMARK_PENDING_FMDL6B",
        "interfaces": plan["required_source_interfaces"],
        "official_primary_sources_first": True,
        "decision_grade_claimed_in_fmdl6_0": False,
        "next_source_gate": "FMDL-6B_SOURCE_INTERFACE_AND_ACCESS_BENCHMARK",
        "trade_authority": "NONE",
    }

    write_json(candidate_root / "FMDL6_0_RELEASE.json", release)
    write_json(candidate_root / "FMDL6_0_DECISION.json", decision_out)
    write_json(candidate_root / "FMDL6_0_VALIDATION.json", validation_out)
    write_json(candidate_root / "FMDL6_0_PLAN.json", plan)
    write_json(candidate_root / "FMDL6_ACTIVATION_GATE.json", activation)
    write_json(candidate_root / "FMDL6_DEFERRED_BACKLOG.json", deferred)
    write_json(candidate_root / "FMDL6_SOURCE_INTERFACE_PLAN.json", source_plan)
    shutil.copy2(repo_root / "docs/FMDL-6_START_HERE.md", candidate_root / "FMDL6_START_HERE.md")

    files: dict[str, dict[str, Any]] = {}
    for path in sorted(candidate_root.iterdir()):
        if path.name == "FMDL6_0_MANIFEST.json" or not path.is_file():
            continue
        files[path.name] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
    manifest = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": release["release_sequence"],
        "canonical_sha256": canonical_sha,
        "plan_sha256": decision["plan_sha256"],
        "files": files,
        "trade_authority": "NONE",
    }
    write_json(candidate_root / "FMDL6_0_MANIFEST.json", manifest)
    return release


def publish(repo_root: Path, candidate_root: Path, release: dict[str, Any]) -> dict[str, Any]:
    release_id = release["release_id"]
    plan = load_json(candidate_root / "FMDL6_0_PLAN.json")
    targets = [
        repo_root / plan["publication"]["current_root"],
        repo_root / plan["publication"]["release_root"] / release_id,
        repo_root / plan["publication"]["archive_root"] / release_id,
    ]
    for target in targets:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(candidate_root, target)

    last_success = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": release["release_sequence"],
        "status": release["status"],
        "canonical_sha256": release["canonical_sha256"],
        "scope_mode": release["scope_mode"],
        "benchmark_security_target": release["benchmark_security_target"],
        "activation_gate_status": release["activation_gate_status"],
        "current_path": plan["publication"]["current_root"],
        "immutable_path": f"{plan['publication']['release_root']}/{release_id}",
        "archive_path": f"{plan['publication']['archive_root']}/{release_id}",
        "restore_start_here": f"{plan['publication']['current_root']}/FMDL6_START_HERE.md",
        "activation_gate_path": f"{plan['publication']['current_root']}/FMDL6_ACTIVATION_GATE.json",
        "deferred_backlog_path": f"{plan['publication']['current_root']}/FMDL6_DEFERRED_BACKLOG.json",
        "next_gate": release["next_gate"],
        "trade_authority": "NONE",
    }
    write_json(repo_root / plan["publication"]["last_success"], last_success)
    return last_success


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--plan", default="config/fmdl6_0_us_equity_resume_ready_pilot_architecture.json")
    parser.add_argument("--decision", default="outputs/fmdl6_0/candidate/FMDL6_0_DECISION.json")
    parser.add_argument("--validation", default="outputs/fmdl6_0/candidate/FMDL6_0_VALIDATION.json")
    parser.add_argument("--candidate", default="outputs/fmdl6_0/candidate")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    plan = load_json(repo_root / args.plan)
    decision = load_json(repo_root / args.decision)
    validation = load_json(repo_root / args.validation)
    candidate_root = repo_root / args.candidate
    release = build_candidate(repo_root, candidate_root, plan, decision, validation)
    result: dict[str, Any] = release
    if args.publish:
        result = publish(repo_root, candidate_root, release)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0
