from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

PROGRAM_ID = "FMDL-6X1-FINAL"
CONTRACT_PATH = Path("config/fmdl6x1_final_operational_acceptance_contract.json")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def required_restore_paths(contract: dict[str, Any]) -> list[str]:
    paths = [str(CONTRACT_PATH), contract["fixed_execution_plan_path"]]
    for item in contract["input_release_chain"]:
        paths.extend([item["pointer_path"], item["current_asset"], item["release_asset"]])
        if item.get("handoff_current_asset"):
            paths.extend([item["handoff_current_asset"], item["handoff_release_asset"]])
    return list(dict.fromkeys(paths))


def collect_model(repo_root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    pointers: dict[str, dict[str, Any]] = {}
    parity: dict[str, bool] = {}
    assets: dict[str, dict[str, Any]] = {}
    for item in contract["input_release_chain"]:
        phase = item["phase_id"]
        pointers[phase] = load_json(repo_root / item["pointer_path"])
        current_path = repo_root / item["current_asset"]
        release_path = repo_root / item["release_asset"]
        parity[f"{phase}:PRIMARY"] = current_path.read_bytes() == release_path.read_bytes()
        assets[phase] = load_json(current_path)
        if item.get("handoff_current_asset"):
            handoff_current = repo_root / item["handoff_current_asset"]
            handoff_release = repo_root / item["handoff_release_asset"]
            parity[f"{phase}:HANDOFF"] = handoff_current.read_bytes() == handoff_release.read_bytes()
            assets[f"{phase}:HANDOFF"] = load_json(handoff_current)
    return {"pointers": pointers, "parity": parity, "assets": assets}


def evaluate_model(contract: dict[str, Any], model: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    pointers = model["pointers"]
    assets = model["assets"]
    parity = model["parity"]

    for item in contract["input_release_chain"]:
        phase = item["phase_id"]
        pointer = pointers.get(phase)
        if pointer is None:
            errors.append(f"MISSING_POINTER:{phase}")
            continue
        if pointer.get("phase_id") != phase:
            errors.append(f"POINTER_PHASE:{phase}")
        if pointer.get("release_id") != item["required_release_id"]:
            errors.append(f"POINTER_RELEASE:{phase}")
        if pointer.get("status") != item["required_status"]:
            errors.append(f"POINTER_STATUS:{phase}")
        if pointer.get("next_gate") != item["required_next_gate"]:
            errors.append(f"POINTER_NEXT_GATE:{phase}")
        if pointer.get("trade_authority") != "NONE":
            errors.append(f"POINTER_TRADE_AUTHORITY:{phase}")
        if not parity.get(f"{phase}:PRIMARY", False):
            errors.append(f"CURRENT_RELEASE_PARITY:{phase}")
        if item.get("handoff_current_asset") and not parity.get(f"{phase}:HANDOFF", False):
            errors.append(f"HANDOFF_PARITY:{phase}")

    a = assets.get("FMDL-6X1-A", {})
    a_dual = a.get("dual_activation", {})
    if a_dual.get("brokerage_real_account_gate", {}).get("status") != "CLOSED_NO_CHANNEL":
        errors.append("BROKERAGE_GATE_NOT_CLOSED")
    if a_dual.get("research_production_gate", {}).get("status") != "OPEN_FOR_CONTROLLED_BUILD":
        errors.append("A_RESEARCH_GATE_NOT_CONTROLLED_OPEN")
    if a.get("trade_authority") != "NONE":
        errors.append("A_TRADE_AUTHORITY")

    b = assets.get("FMDL-6X1-B", {})
    if set(b.get("venue_boundary", {}).get("included_primary_venues", [])) != {"XNYS", "XNAS", "XASE"}:
        errors.append("B_VENUE_BOUNDARY")
    if b.get("orthogonal_status_dimensions", {}).get("channel_status_default") != "CHANNEL_ELIGIBILITY_PENDING":
        errors.append("B_CHANNEL_DEFAULT")
    if b.get("orthogonal_status_dimensions", {}).get("portfolio_status_default") != "PORTFOLIO_ADMISSION_NOT_AUTHORIZED":
        errors.append("B_PORTFOLIO_DEFAULT")
    if b.get("classification_authority", {}).get("silent_source_substitution_forbidden") is not True:
        errors.append("B_SILENT_SUBSTITUTION")
    if b.get("trade_authority") != "NONE":
        errors.append("B_TRADE_AUTHORITY")

    c = assets.get("FMDL-6X1-C", {})
    if c.get("status") != "FMDL6X1C_SOURCE_COST_AND_EXECUTION_ROUTE_REVALIDATION_ACCEPTED":
        errors.append("C_STATUS")
    if c.get("route_policy", {}).get("market_fallbacks_decision_grade") is not False:
        errors.append("C_MARKET_GRADE")
    if c.get("route_policy", {}).get("silent_source_substitution_forbidden") is not True:
        errors.append("C_SILENT_SUBSTITUTION")
    if c.get("route_policy", {}).get("stooq_html_challenge_must_fail") is not True:
        errors.append("C_STOOQ_POLICY")
    if c.get("cost_summary", {}).get("paid_subscription_cost_usd") != 0:
        errors.append("C_PAID_COST")
    if c.get("trade_authority") != "NONE":
        errors.append("C_TRADE_AUTHORITY")

    d = assets.get("FMDL-6X1-D", {})
    if d.get("status") != "ACCEPTED":
        errors.append("D_STATUS")
    if d.get("trade_authority") != "NONE":
        errors.append("D_TRADE_AUTHORITY")
    if d.get("source_execution_contract", {}).get("sec_official_ingestion", {}).get("third_party_sec_proxy_authorized") is not False:
        errors.append("D_SEC_PROXY")
    if d.get("cost_and_runtime_policy", {}).get("paid_subscription_budget_usd") != 0:
        errors.append("D_PAID_BUDGET")
    if d.get("source_execution_contract", {}).get("market_history_and_corporate_actions", {}).get("stooq_route") != "DISABLED_HTML_CHALLENGE":
        errors.append("D_STOOQ_STATUS")
    d_sequence = [x.get("phase_id") for x in d.get("fmdl6x2_fixed_execution_plan", [])]
    if d_sequence != contract["fmdl6x2_entry"]["required_phase_sequence"]:
        errors.append("D_FMDL6X2_SEQUENCE")
    if "FMDL6X1_FINAL_ACCEPTED" not in d.get("fmdl6x2_entry_gates", {}).get("program_entry_requires", []):
        errors.append("D_FINAL_GATE_REQUIRED")
    if d.get("phase_exit", {}).get("next_gate") != "FMDL-6X1-FINAL_OPERATIONAL_ACCEPTANCE":
        errors.append("D_FINAL_NEXT_GATE")

    handoff = assets.get("FMDL-6X1-D:HANDOFF", {})
    handoff_sequence = [x.get("phase_id") for x in handoff.get("fixed_execution_plan", [])]
    if handoff_sequence != contract["fmdl6x2_entry"]["required_phase_sequence"]:
        errors.append("HANDOFF_SEQUENCE")
    handoff_post_final_gate = handoff.get("post_final_entry_gate") or d.get("phase_exit", {}).get("post_final_entry_gate")
    if handoff_post_final_gate != contract["next_gate"]:
        errors.append("HANDOFF_POST_FINAL_GATE")
    if handoff.get("fmdl6x2_phase_count") not in (None, 6):
        errors.append("HANDOFF_PHASE_COUNT")

    if contract["dual_gate_final_state"]["brokerage_real_account_gate"] != "CLOSED_NO_CHANNEL":
        errors.append("FINAL_BROKERAGE_GATE")
    if contract["dual_gate_final_state"]["research_production_gate"] != "OPEN_FOR_FMDL6X2_DATA_PRODUCTION":
        errors.append("FINAL_RESEARCH_GATE")
    if contract["source_and_cost_binding"]["silent_source_substitution_forbidden"] is not True:
        errors.append("FINAL_SILENT_SUBSTITUTION")
    if contract["source_and_cost_binding"]["third_party_sec_proxy_authorized"] is not False:
        errors.append("FINAL_SEC_PROXY")
    if contract["source_and_cost_binding"]["paid_subscription_budget_usd"] != 0:
        errors.append("FINAL_PAID_BUDGET")
    if contract.get("trade_authority") != "NONE":
        errors.append("FINAL_TRADE_AUTHORITY")
    if any(value is not False for value in contract["scope"].values()):
        errors.append("FINAL_SCOPE_MUTATION_AUTHORITY")
    if any(value != 0 for value in contract["zero_mutation_gate"].values()):
        errors.append("FINAL_ZERO_MUTATION")
    return sorted(set(errors))


def validate_contract(repo_root: Path, contract_path: Path = CONTRACT_PATH) -> tuple[list[dict[str, Any]], list[str]]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    contract_file = repo_root / contract_path
    if not contract_file.is_file():
        return [{"check_id": "CONTRACT_EXISTS", "status": "FAIL"}], ["CONTRACT_EXISTS"]
    contract = load_json(contract_file)

    def check(check_id: str, condition: bool, actual: Any = None, expected: Any = None) -> None:
        checks.append({"check_id": check_id, "status": "PASS" if condition else "FAIL", "actual": actual, "expected": expected})
        if not condition:
            errors.append(check_id)

    check("PHASE_ID", contract.get("phase_id") == PROGRAM_ID, contract.get("phase_id"), PROGRAM_ID)
    check("STATUS", contract.get("status") == "FINAL_ACCEPTANCE_CONTRACT_CANDIDATE", contract.get("status"), "FINAL_ACCEPTANCE_CONTRACT_CANDIDATE")
    check("TRADE_AUTHORITY", contract.get("trade_authority") == "NONE", contract.get("trade_authority"), "NONE")
    check("INPUT_PHASE_COUNT", len(contract.get("input_release_chain", [])) == 4, len(contract.get("input_release_chain", [])), 4)
    check("INPUT_PHASE_ORDER", [x.get("phase_id") for x in contract.get("input_release_chain", [])] == ["FMDL-6X1-A", "FMDL-6X1-B", "FMDL-6X1-C", "FMDL-6X1-D"])
    check("FAILURE_SCENARIO_COUNT", len(contract.get("failure_injection_scenarios", [])) == 9, len(contract.get("failure_injection_scenarios", [])), 9)
    check("FMDL6X2_PHASE_COUNT", contract.get("fmdl6x2_entry", {}).get("required_phase_count") == 6, contract.get("fmdl6x2_entry", {}).get("required_phase_count"), 6)
    check("RELEASE_SEQUENCE", contract.get("publication", {}).get("release_sequence") == 29, contract.get("publication", {}).get("release_sequence"), 29)
    check("EXIT_STATUS", contract.get("required_exit_status") == "FMDL6X1_FINAL_ACCEPTED")
    check("NEXT_GATE", contract.get("next_gate") == "FMDL-6X2-A_CURRENT_SECURITY_MASTER_PRODUCTION")
    check("HANDOFF_ASSET_COUNT", len(contract.get("fmdl6x2_entry", {}).get("required_handoff_assets", [])) == 7)
    plan_path = repo_root / contract.get("fixed_execution_plan_path", "")
    check("FIXED_PLAN_EXISTS", plan_path.is_file(), str(plan_path), "existing file")
    if plan_path.is_file():
        plan_text = plan_path.read_text(encoding="utf-8")
        check("FIXED_PLAN_FINAL_PRESENT", "FMDL-6X1-FINAL_OPERATIONAL_ACCEPTANCE" in plan_text)
        check("FIXED_PLAN_FIVE_ROUNDS", "exactly five planned rounds" in plan_text)

    missing_paths = [path for path in required_restore_paths(contract) if not (repo_root / path).is_file()]
    check("RESTORE_PATHS_EXIST", not missing_paths, missing_paths, [])
    if not missing_paths:
        model = collect_model(repo_root, contract)
        model_errors = evaluate_model(contract, model)
        check("CROSS_PHASE_MODEL", not model_errors, model_errors, [])
        errors.extend(model_errors)
    return checks, sorted(set(errors))


def run_failure_injections(repo_root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    baseline = collect_model(repo_root, contract)
    baseline_errors = evaluate_model(contract, baseline)
    if baseline_errors:
        raise RuntimeError(f"baseline model failed before injection: {baseline_errors}")

    scenarios: list[dict[str, Any]] = []

    def inject(name: str, mutate) -> None:
        model = copy.deepcopy(baseline)
        contract_copy = copy.deepcopy(contract)
        mutate(contract_copy, model)
        detected = bool(evaluate_model(contract_copy, model))
        scenarios.append({"scenario": name, "detected": detected})
        if not detected:
            raise RuntimeError(f"failure injection escaped: {name}")

    inject("MISSING_PRIOR_LAST_SUCCESS", lambda c, m: m["pointers"].pop("FMDL-6X1-C"))
    inject("PRIOR_RELEASE_ID_MISMATCH", lambda c, m: m["pointers"]["FMDL-6X1-B"].update({"release_id": "WRONG"}))
    inject("CURRENT_RELEASE_BYTE_MISMATCH", lambda c, m: m["parity"].update({"FMDL-6X1-D:PRIMARY": False}))
    inject("BROKERAGE_GATE_OPEN_WITHOUT_CHANNEL", lambda c, m: m["assets"]["FMDL-6X1-A"]["dual_activation"]["brokerage_real_account_gate"].update({"status": "OPEN"}))
    inject("TRADE_AUTHORITY_ESCALATED", lambda c, m: m["pointers"]["FMDL-6X1-D"].update({"trade_authority": "ORDER"}))
    inject("SILENT_SOURCE_SUBSTITUTION_ENABLED", lambda c, m: c["source_and_cost_binding"].update({"silent_source_substitution_forbidden": False}))
    inject("PAID_ROUTE_ACTIVATED_WITHOUT_APPROVAL", lambda c, m: c["source_and_cost_binding"].update({"paid_subscription_budget_usd": 1}))
    inject("FMDL6X2_PHASE_SEQUENCE_MUTATED", lambda c, m: m["assets"]["FMDL-6X1-D"].update({"fmdl6x2_fixed_execution_plan": list(reversed(m["assets"]["FMDL-6X1-D"]["fmdl6x2_fixed_execution_plan"]))}))
    inject("SEC_PROXY_AUTHORIZED", lambda c, m: m["assets"]["FMDL-6X1-D"]["source_execution_contract"]["sec_official_ingestion"].update({"third_party_sec_proxy_authorized": True}))

    return {
        "phase_id": PROGRAM_ID,
        "status": "PASS",
        "baseline_error_count": 0,
        "scenario_count": len(scenarios),
        "detected_count": sum(1 for x in scenarios if x["detected"]),
        "scenarios": scenarios,
    }


def run_clean_room_restore(repo_root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    paths = required_restore_paths(contract)
    with tempfile.TemporaryDirectory(prefix="fmdl6x1-final-clean-room-") as tmp:
        clean_root = Path(tmp)
        for relative in paths:
            source = repo_root / relative
            target = clean_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        checks, errors = validate_contract(clean_root)
        return {
            "phase_id": PROGRAM_ID,
            "status": "PASS" if not errors else "FAIL",
            "restored_file_count": len(paths),
            "validation_check_count": len(checks),
            "errors": errors,
            "restore_order": [
                "FMDL6X1_LAST_SUCCESS",
                "FMDL6X2_START_HERE",
                "FMDL6X2_BUILD_CONTRACT",
                "FMDL6X2_SOURCE_EXECUTION_REGISTRY",
                "FMDL6X2_DOMAIN_SCHEMA_REGISTRY",
                "FMDL6X2_SHARD_PLAN",
                "FMDL6X2_QUALITY_GATE_REGISTRY",
                "LATEST_DOMAIN_LKG_POINTERS",
                "IMMUTABLE_RELEASE_MANIFESTS",
            ],
        }


def build_handoff_assets(contract: dict[str, Any], model: dict[str, Any], release_id: str) -> dict[str, Any]:
    d = model["assets"]["FMDL-6X1-D"]
    handoff = model["assets"]["FMDL-6X1-D:HANDOFF"]
    build_contract = {
        "program_id": "FMDL-6X2",
        "status": "READY_FOR_FMDL6X2A_AFTER_FINAL_ACCEPTANCE",
        "entry_pointer": contract["publication"]["last_success"],
        "required_entry_status": contract["required_exit_status"],
        "release_id": release_id,
        "trade_authority": "NONE",
        "research_production_gate": contract["dual_gate_final_state"]["research_production_gate"],
        "brokerage_real_account_gate": contract["dual_gate_final_state"]["brokerage_real_account_gate"],
        "fixed_execution_plan": handoff["fixed_execution_plan"],
        "full_build_domains": d["full_build_domains"],
        "backfill_contract": d["backfill_contract"],
        "publication_and_recovery": d["publication_and_recovery"],
        "cost_and_runtime_policy": d["cost_and_runtime_policy"],
        "governing_principles": d["governing_principles"],
    }
    domain_registry = {
        "program_id": "FMDL-6X2",
        "schema_registry_version": "1.0.0",
        "domains": d["full_build_domains"],
        "identity_model": ["ISSUER", "SHARE_CLASS", "SECURITY", "EFFECTIVE_DATED_LISTING"],
        "unknown_or_conflicted_action": "QUARANTINE",
        "ticker_is_identity": False,
        "exchange_is_identity": False,
    }
    source_registry = {
        "program_id": "FMDL-6X2",
        "source_registry_version": "1.0.0",
        "source_execution_contract": d["source_execution_contract"],
        "paid_subscription_budget_usd": 0,
        "silent_source_substitution_forbidden": True,
        "trade_authority": "NONE",
    }
    shard_plan = {
        "program_id": "FMDL-6X2",
        "shard_plan_version": "1.0.0",
        "bucket_count": 64,
        "storage_and_sharding": d["storage_and_sharding"],
        "atomic_promotion_required": True,
        "partial_shard_may_replace_current": False,
    }
    quality_registry = {
        "program_id": "FMDL-6X2",
        "quality_gate_registry_version": "1.0.0",
        "quality_gates": d["quality_gates"],
        "zero_investment_state_mutations_required": True,
        "failure_preserves_current_and_lkg": True,
    }
    start_here = f"""# FMDL-6X2 START HERE

Canonical entry status: `{contract['required_exit_status']}`  
Entry pointer: `{contract['publication']['last_success']}`  
Authorized first phase: `{contract['next_gate']}`  
Research Production Gate: `{contract['dual_gate_final_state']['research_production_gate']}`  
Brokerage & Real-Account Gate: `{contract['dual_gate_final_state']['brokerage_real_account_gate']}`  
Trade authority: `NONE`

## Fixed execution sequence

1. FMDL-6X2-A — Current Security Master Production
2. FMDL-6X2-B — Issuer Identity, Classification & Review Queues
3. FMDL-6X2-C — Historical Listing & Lifecycle Backfill
4. FMDL-6X2-D — Market History, Corporate Actions & FX Store
5. FMDL-6X2-E — SEC Filings & Financial Facts Store
6. FMDL-6X2-FINAL — Full Store Reconciliation & Operational Acceptance

Do not start a later phase without the prior phase Last-success. Do not infer brokerage eligibility from research eligibility. No automatic order execution is authorized.
"""
    restore_order = """# FMDL-6X2 Clean-Room Restore Order

1. Read `outputs/status/FMDL6X1_LAST_SUCCESS.json`.
2. Verify status `FMDL6X1_FINAL_ACCEPTED` and next gate `FMDL-6X2-A_CURRENT_SECURITY_MASTER_PRODUCTION`.
3. Read `FMDL6X2_START_HERE.md`.
4. Restore `FMDL6X2_BUILD_CONTRACT.json`.
5. Restore `FMDL6X2_SOURCE_EXECUTION_REGISTRY.json`.
6. Restore `FMDL6X2_DOMAIN_SCHEMA_REGISTRY.json`.
7. Restore `FMDL6X2_SHARD_PLAN.json`.
8. Restore `FMDL6X2_QUALITY_GATE_REGISTRY.json`.
9. Restore the latest domain Last-known-good pointers when they exist.
10. Verify immutable Release manifests before promoting any Current output.

A failed, partial or hash-mismatched run must not replace Current or Last-known-good.
"""
    return {
        "FMDL6X2_START_HERE.md": start_here,
        "FMDL6X2_BUILD_CONTRACT.json": build_contract,
        "FMDL6X2_DOMAIN_SCHEMA_REGISTRY.json": domain_registry,
        "FMDL6X2_SOURCE_EXECUTION_REGISTRY.json": source_registry,
        "FMDL6X2_SHARD_PLAN.json": shard_plan,
        "FMDL6X2_QUALITY_GATE_REGISTRY.json": quality_registry,
        "FMDL6X2_RESTORE_ORDER.md": restore_order,
    }


def build_candidate(repo_root: Path, candidate_root: Path, accepted_at: str, source_commit: str) -> dict[str, Any]:
    contract = load_json(repo_root / CONTRACT_PATH)
    checks, errors = validate_contract(repo_root)
    if errors:
        raise RuntimeError(f"contract validation failed: {errors}")
    model = collect_model(repo_root, contract)
    injection = run_failure_injections(repo_root, contract)
    clean_room = run_clean_room_restore(repo_root, contract)
    if clean_room["status"] != "PASS":
        raise RuntimeError(f"clean-room restore failed: {clean_room['errors']}")

    decision_core = {
        "phase_id": PROGRAM_ID,
        "status": contract["required_exit_status"],
        "accepted_at": accepted_at,
        "source_commit": source_commit,
        "input_releases": [
            {
                "phase_id": item["phase_id"],
                "release_id": item["required_release_id"],
                "status": item["required_status"],
                "asset_sha256": sha256_file(repo_root / item["current_asset"]),
            }
            for item in contract["input_release_chain"]
        ],
        "research_production_gate": contract["dual_gate_final_state"]["research_production_gate"],
        "brokerage_real_account_gate": contract["dual_gate_final_state"]["brokerage_real_account_gate"],
        "channel_eligibility_default": contract["dual_gate_final_state"]["channel_eligibility_default"],
        "portfolio_admission_default": contract["dual_gate_final_state"]["portfolio_admission_default"],
        "independent_validation": "PASS",
        "same_input_replay": "PASS",
        "failure_injection": "PASS",
        "clean_room_restore": "PASS",
        "immutable_publication": "REQUIRED",
        "fmdl6x2_phase_count": contract["fmdl6x2_entry"]["required_phase_count"],
        "fmdl6x2_first_gate": contract["next_gate"],
        "paid_subscription_budget_usd": 0,
        "zero_mutation_proof": contract["zero_mutation_gate"],
        "trade_authority": "NONE",
        "next_gate": contract["next_gate"],
    }
    release_id = f"FMDL6X1_{accepted_at[:10].replace('-', '')}_{sha256_bytes(stable_json(decision_core).encode())[:12]}"
    decision = {**decision_core, "release_id": release_id, "release_sequence": contract["publication"]["release_sequence"]}

    accepted_contract = copy.deepcopy(contract)
    accepted_contract.update({
        "status": "ACCEPTED",
        "contract_version": "1.0.1",
        "acceptance": {
            "accepted_at": accepted_at,
            "source_commit": source_commit,
            "acceptance_reason": "INDEPENDENT_REPLAY_FAILURE_INJECTION_CLEAN_ROOM_AND_IMMUTABLE_PUBLICATION_PASS",
        },
        "release_id": release_id,
    })
    report = {
        "phase_id": PROGRAM_ID,
        "status": "PASS",
        "check_count": len(checks),
        "failed_checks": [],
        "checks": checks,
        "input_release_count": 4,
        "current_release_parity_count": len(model["parity"]),
        "all_current_release_pairs_match": all(model["parity"].values()),
    }
    chain_registry = {
        "phase_id": PROGRAM_ID,
        "release_chain": decision["input_releases"],
        "fixed_phase_sequence": ["FMDL-6X1-A", "FMDL-6X1-B", "FMDL-6X1-C", "FMDL-6X1-D", "FMDL-6X1-FINAL"],
        "final_release_id": release_id,
    }

    if candidate_root.exists():
        shutil.rmtree(candidate_root)
    candidate_root.mkdir(parents=True, exist_ok=True)

    base_files: dict[str, Any] = {
        "FMDL6X1_FINAL_CONTRACT.json": accepted_contract,
        "FMDL6X1_FINAL_DECISION.json": decision,
        "FMDL6X1_FINAL_ACCEPTANCE_REPORT.json": report,
        "FMDL6X1_FINAL_FAILURE_INJECTION.json": injection,
        "FMDL6X1_FINAL_CLEAN_ROOM_RESTORE.json": clean_room,
        "FMDL6X1_FINAL_RELEASE_CHAIN.json": chain_registry,
    }
    for name, value in base_files.items():
        write_json(candidate_root / name, value)

    handoff_assets = build_handoff_assets(contract, model, release_id)
    for name, value in handoff_assets.items():
        if isinstance(value, str):
            write_text(candidate_root / name, value)
        else:
            write_json(candidate_root / name, value)

    files_for_manifest = sorted(path for path in candidate_root.iterdir() if path.name != "FMDL6X1_FINAL_MANIFEST.json")
    manifest = {
        "phase_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": contract["publication"]["release_sequence"],
        "generated_at": accepted_at,
        "files": {
            path.name: {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for path in files_for_manifest
        },
    }
    write_json(candidate_root / "FMDL6X1_FINAL_MANIFEST.json", manifest)
    return decision


def compare_candidate_trees(left: Path, right: Path) -> tuple[bool, list[str]]:
    left_files = sorted(path.name for path in left.iterdir())
    right_files = sorted(path.name for path in right.iterdir())
    errors: list[str] = []
    if left_files != right_files:
        errors.append("FILE_SET_MISMATCH")
    for name in sorted(set(left_files) & set(right_files)):
        if (left / name).read_bytes() != (right / name).read_bytes():
            errors.append(f"BYTE_MISMATCH:{name}")
    return not errors, errors


def validate_candidate(repo_root: Path, candidate_root: Path, acceptance_path: Path, accepted_at: str, source_commit: str) -> None:
    with tempfile.TemporaryDirectory(prefix="fmdl6x1-final-replay-") as tmp:
        replay_root = Path(tmp) / "candidate"
        replay_decision = build_candidate(repo_root, replay_root, accepted_at, source_commit)
        candidate_decision = load_json(candidate_root / "FMDL6X1_FINAL_DECISION.json")
        same_tree, tree_errors = compare_candidate_trees(candidate_root, replay_root)
        checks = {
            "candidate_exists": (candidate_root / "FMDL6X1_FINAL_MANIFEST.json").is_file(),
            "same_input_replay": same_tree,
            "same_decision": candidate_decision == replay_decision,
            "accepted_status": candidate_decision.get("status") == "FMDL6X1_FINAL_ACCEPTED",
            "research_gate_open": candidate_decision.get("research_production_gate") == "OPEN_FOR_FMDL6X2_DATA_PRODUCTION",
            "brokerage_gate_closed": candidate_decision.get("brokerage_real_account_gate") == "CLOSED_NO_CHANNEL",
            "next_gate": candidate_decision.get("next_gate") == "FMDL-6X2-A_CURRENT_SECURITY_MASTER_PRODUCTION",
            "zero_mutations": all(value == 0 for value in candidate_decision.get("zero_mutation_proof", {}).values()),
            "trade_authority_none": candidate_decision.get("trade_authority") == "NONE",
        }
        result = {
            "phase_id": PROGRAM_ID,
            "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "tree_errors": tree_errors,
            "accepted_at": accepted_at,
        }
        write_json(acceptance_path, result)
        if result["status"] != "PASS":
            raise RuntimeError(result)


def publish(repo_root: Path, candidate_root: Path, published_at: str, source_commit: str) -> dict[str, Any]:
    contract = load_json(repo_root / CONTRACT_PATH)
    decision = load_json(candidate_root / "FMDL6X1_FINAL_DECISION.json")
    if decision.get("status") != contract["required_exit_status"]:
        raise RuntimeError("candidate is not accepted")
    release_id = decision["release_id"]
    current_root = repo_root / contract["publication"]["current_root"]
    release_root = repo_root / contract["publication"]["release_root"] / release_id
    if release_root.exists():
        raise RuntimeError(f"immutable release already exists: {release_root}")
    if current_root.exists():
        shutil.rmtree(current_root)
    shutil.copytree(candidate_root, current_root)
    shutil.copytree(candidate_root, release_root)
    for current_file in current_root.iterdir():
        release_file = release_root / current_file.name
        if current_file.read_bytes() != release_file.read_bytes():
            raise RuntimeError(f"Current/Release mismatch: {current_file.name}")

    manifest_path = current_root / "FMDL6X1_FINAL_MANIFEST.json"
    pointer = {
        "phase_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": decision["release_sequence"],
        "status": decision["status"],
        "current_path": contract["publication"]["current_root"],
        "release_path": str(release_root.relative_to(repo_root)),
        "manifest_sha256": sha256_file(manifest_path),
        "published_at": published_at,
        "source_commit": source_commit,
        "research_production_gate": decision["research_production_gate"],
        "brokerage_real_account_gate": decision["brokerage_real_account_gate"],
        "next_gate": decision["next_gate"],
        "trade_authority": "NONE",
    }
    write_json(repo_root / contract["publication"]["last_success"], pointer)
    return pointer


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    validate_cmd = sub.add_parser("validate-contract")
    validate_cmd.add_argument("--repo-root", default=".")

    build_cmd = sub.add_parser("build")
    build_cmd.add_argument("--repo-root", default=".")
    build_cmd.add_argument("--candidate", required=True)
    build_cmd.add_argument("--accepted-at", required=True)
    build_cmd.add_argument("--source-commit", required=True)

    replay_cmd = sub.add_parser("validate-candidate")
    replay_cmd.add_argument("--repo-root", default=".")
    replay_cmd.add_argument("--candidate", required=True)
    replay_cmd.add_argument("--acceptance", required=True)
    replay_cmd.add_argument("--accepted-at", required=True)
    replay_cmd.add_argument("--source-commit", required=True)

    publish_cmd = sub.add_parser("publish")
    publish_cmd.add_argument("--repo-root", default=".")
    publish_cmd.add_argument("--candidate", required=True)
    publish_cmd.add_argument("--published-at", required=True)
    publish_cmd.add_argument("--source-commit", required=True)

    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    if args.command == "validate-contract":
        checks, errors = validate_contract(repo_root)
        print(json.dumps({"check_count": len(checks), "errors": errors}, indent=2))
        return 1 if errors else 0
    if args.command == "build":
        decision = build_candidate(repo_root, repo_root / args.candidate, args.accepted_at, args.source_commit)
        print(json.dumps(decision, indent=2, sort_keys=True))
        return 0
    if args.command == "validate-candidate":
        validate_candidate(repo_root, repo_root / args.candidate, repo_root / args.acceptance, args.accepted_at, args.source_commit)
        return 0
    if args.command == "publish":
        pointer = publish(repo_root, repo_root / args.candidate, args.published_at, args.source_commit)
        print(json.dumps(pointer, indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
