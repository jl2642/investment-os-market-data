from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROGRAM_ID = "FMDL-6X1-D"
CONTRACT_PATH = Path("config/fmdl6x1d_full_build_contract.json")
ACCEPTED_STATUS = "FMDL6X1D_FULL_BUILD_CONTRACT_AND_FMDL6X2_HANDOFF_ACCEPTED"
NEXT_GATE = "FMDL-6X1-FINAL_OPERATIONAL_ACCEPTANCE"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_contract(repo_root: Path, contract_path: Path = CONTRACT_PATH) -> tuple[list[dict[str, Any]], list[str]]:
    contract = load_json(repo_root / contract_path)
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def check(check_id: str, condition: bool, actual: Any, expected: Any) -> None:
        checks.append({"check_id": check_id, "status": "PASS" if condition else "FAIL", "actual": actual, "expected": expected})
        if not condition:
            errors.append(check_id)

    check("PHASE_ID", contract.get("phase_id") == PROGRAM_ID, contract.get("phase_id"), PROGRAM_ID)
    check("STATUS", contract.get("status") in {"CONTRACT_CANDIDATE", "ACCEPTED"}, contract.get("status"), "candidate or accepted")
    check("TRADE_AUTHORITY", contract.get("trade_authority") == "NONE", contract.get("trade_authority"), "NONE")

    entry = contract.get("entry_gate", {})
    pointer_path = repo_root / str(entry.get("pointer_path", ""))
    check("ENTRY_POINTER_EXISTS", pointer_path.is_file(), str(pointer_path), "existing file")
    if pointer_path.is_file():
        pointer = load_json(pointer_path)
        check("ENTRY_RELEASE", pointer.get("release_id") == entry.get("required_release_id"), pointer.get("release_id"), entry.get("required_release_id"))
        check("ENTRY_STATUS", pointer.get("status") == entry.get("required_status"), pointer.get("status"), entry.get("required_status"))
        check("ENTRY_NEXT_GATE", pointer.get("next_gate") == entry.get("required_next_gate"), pointer.get("next_gate"), entry.get("required_next_gate"))
        check("ENTRY_AUTHORITY", pointer.get("trade_authority") == "NONE", pointer.get("trade_authority"), "NONE")

    scope = contract.get("scope", {})
    check("SCOPE_MODE", scope.get("mode") == "CONTRACT_AND_HANDOFF_ONLY", scope.get("mode"), "CONTRACT_AND_HANDOFF_ONLY")
    for key, value in scope.items():
        if key.endswith("_authorized"):
            check(f"SCOPE_FALSE:{key}", value is False, value, False)

    domains = contract.get("full_build_domains", {})
    check("DOMAIN_GROUPS", set(domains) == {"identity_and_universe", "market_and_reference", "sec_and_fundamentals", "controlled_review"}, sorted(domains), "four required groups")
    check("IDENTITY_LAYERS", {"ISSUER", "SHARE_CLASS", "SECURITY", "EFFECTIVE_DATED_LISTING"} <= set(domains.get("identity_and_universe", [])), domains.get("identity_and_universe"), "identity layers")
    check("CONTROLLED_REVIEW", len(domains.get("controlled_review", [])) >= 4, len(domains.get("controlled_review", [])), ">=4")

    source = contract.get("source_execution_contract", {})
    check("SOURCE_GROUPS", set(source) == {"current_security_directory", "sec_official_ingestion", "market_history_and_corporate_actions", "fx", "historical_listing_and_lifecycle", "adr_and_special_instruments"}, sorted(source), "six source groups")
    sec = source.get("sec_official_ingestion", {})
    check("SEC_PROXY_FALSE", sec.get("third_party_sec_proxy_authorized") is False, sec.get("third_party_sec_proxy_authorized"), False)
    check("SEC_EXECUTORS", len(sec.get("approved_interim_execution_environments", [])) == 3, sec.get("approved_interim_execution_environments"), "three controlled official executors")
    market = source.get("market_history_and_corporate_actions", {})
    check("MARKET_NON_DECISION_GRADE", market.get("interim_grade") == "NON_DECISION_GRADE_FALLBACK", market.get("interim_grade"), "NON_DECISION_GRADE_FALLBACK")
    check("STOOQ_DISABLED", market.get("stooq_route") == "DISABLED_HTML_CHALLENGE", market.get("stooq_route"), "DISABLED_HTML_CHALLENGE")
    historical = source.get("historical_listing_and_lifecycle", {})
    check("NO_UNIVERSAL_HISTORY_SOURCE", historical.get("universal_zero_cost_official_route_confirmed") is False, historical.get("universal_zero_cost_official_route_confirmed"), False)
    check("NO_EXACT_OBSERVATION_DATE", historical.get("observation_only_may_be_represented_as_exact_effective_date") is False, historical.get("observation_only_may_be_represented_as_exact_effective_date"), False)

    backfill = contract.get("backfill_contract", {})
    check("IDENTITY_START", backfill.get("historical_identity", {}).get("target_start_date") == "2005-01-01", backfill.get("historical_identity", {}).get("target_start_date"), "2005-01-01")
    check("MARKET_START", backfill.get("market_history", {}).get("initial_target_start_date") == "2010-01-01", backfill.get("market_history", {}).get("initial_target_start_date"), "2010-01-01")
    check("SEC_START", backfill.get("sec_filings_and_facts", {}).get("target_start_date") == "2009-01-01", backfill.get("sec_filings_and_facts", {}).get("target_start_date"), "2009-01-01")

    storage = contract.get("storage_and_sharding", {})
    check("SHARD_64", storage.get("shard_function") == "SHA256_CANONICAL_SECURITY_OR_ISSUER_ID_MOD_64", storage.get("shard_function"), "64-bucket canonical hash")
    check("NO_PARTIAL_PROMOTION", storage.get("partial_shard_may_replace_current") is False, storage.get("partial_shard_may_replace_current"), False)

    publication = contract.get("publication_and_recovery", {})
    required_layers = {"WORK", "CANDIDATE", "CURRENT", "IMMUTABLE_RELEASE", "ARCHIVE", "LAST_SUCCESS", "LAST_KNOWN_GOOD"}
    check("PUBLICATION_LAYERS", required_layers <= set(publication.get("required_layers", [])), publication.get("required_layers"), sorted(required_layers))
    check("FAILED_RUN_CURRENT", publication.get("failed_run_may_replace_current") is False, publication.get("failed_run_may_replace_current"), False)
    check("FAILED_RUN_LKG", publication.get("failed_run_may_replace_lkg") is False, publication.get("failed_run_may_replace_lkg"), False)

    gates = contract.get("quality_gates", {})
    check("QUALITY_GROUPS", set(gates) == {"security_master", "point_in_time", "market_history", "sec_and_facts", "research_readiness", "release"}, sorted(gates), "six quality groups")
    check("SOURCE_ROW_ACCOUNTING", "100_PERCENT_SOURCE_ROW_ACCOUNTING" in gates.get("security_master", []), gates.get("security_master"), "100 percent accounting")
    check("NO_SURVIVORSHIP", "NO_CURRENT_ONLY_SURVIVORSHIP_BACKFILL" in gates.get("point_in_time", []), gates.get("point_in_time"), "no survivorship")
    check("SEC_LINEAGE", "CIK10_AND_ACCESSION_LINEAGE_REQUIRED" in gates.get("sec_and_facts", []), gates.get("sec_and_facts"), "SEC lineage")
    check("FAILURE_LKG", "FAILURE_INJECTION_PRESERVES_CURRENT_AND_LKG" in gates.get("release", []), gates.get("release"), "failure protection")

    cost = contract.get("cost_and_runtime_policy", {})
    check("PAID_BUDGET_ZERO", cost.get("paid_subscription_budget_usd") == 0, cost.get("paid_subscription_budget_usd"), 0)
    check("PAID_APPROVAL", cost.get("paid_api_or_dataset_activation_requires_user_approval") is True, cost.get("paid_api_or_dataset_activation_requires_user_approval"), True)
    check("BOUNDED_RUNTIME", int(cost.get("single_orchestrator_run_minutes_hard_ceiling", 0)) <= 180, cost.get("single_orchestrator_run_minutes_hard_ceiling"), "<=180")

    plan = contract.get("fmdl6x2_fixed_execution_plan", [])
    expected_phases = ["FMDL-6X2-A", "FMDL-6X2-B", "FMDL-6X2-C", "FMDL-6X2-D", "FMDL-6X2-E", "FMDL-6X2-FINAL"]
    check("PLAN_COUNT", len(plan) == 6, len(plan), 6)
    check("PLAN_SEQUENCE", [item.get("phase_id") for item in plan] == expected_phases, [item.get("phase_id") for item in plan], expected_phases)
    check("PLAN_EXIT_UNIQUE", len({item.get("exit_status") for item in plan}) == 6, [item.get("exit_status") for item in plan], "six unique exits")

    entry_gates = contract.get("fmdl6x2_entry_gates", {})
    check("FINAL_BEFORE_6X2", "FMDL6X1_FINAL_ACCEPTED" in entry_gates.get("program_entry_requires", []), entry_gates.get("program_entry_requires"), "FMDL6X1_FINAL_ACCEPTED")
    check("PHASE_E_SEC_PROOF", entry_gates.get("phase_e_requires_sec_official_executor_proof") is True, entry_gates.get("phase_e_requires_sec_official_executor_proof"), True)
    check("NO_BROKER_REQUIRED", entry_gates.get("brokerage_channel_not_required") is True, entry_gates.get("brokerage_channel_not_required"), True)

    check("HANDOFF_ASSETS", len(contract.get("handoff_assets_required", [])) == 7, len(contract.get("handoff_assets_required", [])), 7)
    phase_exit = contract.get("phase_exit", {})
    check("EXIT_STATUS", phase_exit.get("required_exit_status") == ACCEPTED_STATUS, phase_exit.get("required_exit_status"), ACCEPTED_STATUS)
    check("NEXT_GATE", phase_exit.get("next_gate") == NEXT_GATE, phase_exit.get("next_gate"), NEXT_GATE)
    check("POST_FINAL_GATE", phase_exit.get("post_final_entry_gate") == "FMDL-6X2-A_CURRENT_SECURITY_MASTER_PRODUCTION", phase_exit.get("post_final_entry_gate"), "FMDL-6X2-A_CURRENT_SECURITY_MASTER_PRODUCTION")
    check("RELEASE_SEQUENCE", phase_exit.get("release_sequence") == 28, phase_exit.get("release_sequence"), 28)

    zero = contract.get("zero_mutation_proof", {})
    for key in ("live_security_rows_created", "candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders"):
        check(f"ZERO:{key}", zero.get(key) == 0, zero.get(key), 0)
    return checks, errors


def build_accepted_contract(candidate: dict[str, Any], source_commit: str) -> dict[str, Any]:
    accepted = json.loads(json.dumps(candidate))
    accepted["status"] = "ACCEPTED"
    accepted["contract_version"] = "1.0.1"
    accepted["acceptance"] = {"accepted_at": utc_now(), "source_merge_commit": source_commit, "acceptance_reason": "FREEZE_FULL_BUILD_CONTRACT_AND_FMDL6X2_HANDOFF"}
    return accepted


def publish(repo_root: Path, source_commit: str) -> dict[str, Any]:
    checks, errors = validate_contract(repo_root)
    if errors:
        raise RuntimeError({"contract_errors": errors})
    candidate = load_json(repo_root / CONTRACT_PATH)
    accepted = build_accepted_contract(candidate, source_commit)
    contract_sha = sha256_bytes(stable_json(accepted).encode("utf-8"))
    release_id = f"FMDL6X1D_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{contract_sha[:12]}"
    current_root = repo_root / "outputs/fmdl6x1d/current"
    release_root = repo_root / "datasets/fmdl6x1d/releases" / release_id
    if release_root.exists():
        raise RuntimeError(f"immutable release already exists: {release_root}")
    shutil.rmtree(current_root, ignore_errors=True)
    current_root.mkdir(parents=True, exist_ok=True)
    release_root.mkdir(parents=True, exist_ok=False)

    decision = {"phase_id": PROGRAM_ID, "status": ACCEPTED_STATUS, "release_id": release_id, "release_sequence": 28, "contract_sha256": contract_sha, "next_gate": NEXT_GATE, "post_final_entry_gate": "FMDL-6X2-A_CURRENT_SECURITY_MASTER_PRODUCTION", "fmdl6x2_phase_count": 6, "paid_subscription_budget_usd": 0, "trade_authority": "NONE", "zero_mutation_proof": accepted["zero_mutation_proof"]}
    files = {
        "FMDL6X1D_CONTRACT.json": accepted,
        "FMDL6X1D_DECISION.json": decision,
        "FMDL6X2_HANDOFF_PLAN.json": {"phase_id": PROGRAM_ID, "release_id": release_id, "fixed_execution_plan": accepted["fmdl6x2_fixed_execution_plan"], "entry_gates": accepted["fmdl6x2_entry_gates"], "required_assets": accepted["handoff_assets_required"]},
    }
    for name, value in files.items():
        write_json(current_root / name, value)
        write_json(release_root / name, value)

    manifest_files = {name: {"sha256": sha256_file(current_root / name), "bytes": (current_root / name).stat().st_size} for name in sorted(files)}
    manifest = {"phase_id": PROGRAM_ID, "release_id": release_id, "generated_at": utc_now(), "files": manifest_files}
    write_json(current_root / "FMDL6X1D_MANIFEST.json", manifest)
    write_json(release_root / "FMDL6X1D_MANIFEST.json", manifest)

    pointer = {"phase_id": PROGRAM_ID, "release_id": release_id, "release_sequence": 28, "status": ACCEPTED_STATUS, "contract_sha256": contract_sha, "current_path": "outputs/fmdl6x1d/current", "release_path": str(release_root.relative_to(repo_root)), "next_gate": NEXT_GATE, "post_final_entry_gate": "FMDL-6X2-A_CURRENT_SECURITY_MASTER_PRODUCTION", "trade_authority": "NONE", "published_at": utc_now()}
    write_json(repo_root / "outputs/status/FMDL6X1D_LAST_SUCCESS.json", pointer)
    return pointer


def validate_publication(repo_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    pointer_path = repo_root / "outputs/status/FMDL6X1D_LAST_SUCCESS.json"
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def check(check_id: str, condition: bool, actual: Any, expected: Any) -> None:
        checks.append({"check_id": check_id, "status": "PASS" if condition else "FAIL", "actual": actual, "expected": expected})
        if not condition:
            errors.append(check_id)

    check("POINTER_EXISTS", pointer_path.is_file(), str(pointer_path), "existing")
    if not pointer_path.is_file():
        return checks, errors
    pointer = load_json(pointer_path)
    current = repo_root / pointer["current_path"]
    release = repo_root / pointer["release_path"]
    check("STATUS", pointer.get("status") == ACCEPTED_STATUS, pointer.get("status"), ACCEPTED_STATUS)
    check("NEXT_GATE", pointer.get("next_gate") == NEXT_GATE, pointer.get("next_gate"), NEXT_GATE)
    check("TRADE_AUTHORITY", pointer.get("trade_authority") == "NONE", pointer.get("trade_authority"), "NONE")
    for name in ("FMDL6X1D_CONTRACT.json", "FMDL6X1D_DECISION.json", "FMDL6X2_HANDOFF_PLAN.json", "FMDL6X1D_MANIFEST.json"):
        check(f"CURRENT:{name}", (current / name).is_file(), str(current / name), "existing")
        check(f"RELEASE:{name}", (release / name).is_file(), str(release / name), "existing")
        if (current / name).is_file() and (release / name).is_file():
            check(f"PARITY:{name}", sha256_file(current / name) == sha256_file(release / name), sha256_file(current / name), sha256_file(release / name))
    if (current / "FMDL6X1D_DECISION.json").is_file():
        decision = load_json(current / "FMDL6X1D_DECISION.json")
        check("ZERO_MUTATIONS", all(value == 0 for value in decision.get("zero_mutation_proof", {}).values()), decision.get("zero_mutation_proof"), "all zero")
        check("PLAN_COUNT", decision.get("fmdl6x2_phase_count") == 6, decision.get("fmdl6x2_phase_count"), 6)
    return checks, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["validate", "publish", "validate-publication"])
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-commit", default="UNKNOWN")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    if args.command == "validate":
        checks, errors = validate_contract(root)
        print(json.dumps({"checks": checks, "errors": errors}, indent=2))
        return 1 if errors else 0
    if args.command == "publish":
        print(json.dumps(publish(root, args.source_commit), indent=2))
        return 0
    checks, errors = validate_publication(root)
    print(json.dumps({"checks": checks, "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
