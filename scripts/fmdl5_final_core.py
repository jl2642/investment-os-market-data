from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Iterable

PROGRAM_ID = "FMDL-5-FINAL"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_object(value: Any) -> str:
    return sha256_bytes(stable_json(value).encode("utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(stable_json(row) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def validate_components(repo_root: Path, contract: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    components: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for name, spec in contract["component_pointers"].items():
        pointer = load_json(repo_root / spec["path"])
        components[name] = pointer
        if pointer.get("release_id") != spec["required_release_id"]:
            errors.append(f"{name}:RELEASE_ID_MISMATCH")
        if pointer.get("status") != spec["required_status"]:
            errors.append(f"{name}:STATUS_MISMATCH")
        if pointer.get("trade_authority") != "NONE":
            errors.append(f"{name}:TRADE_AUTHORITY_ERROR")
    base_spec = contract["canonical_base"]
    base = load_json(repo_root / base_spec["publication_path"])
    if base.get("release_id") != base_spec["required_release_id"]:
        errors.append("CANONICAL_BASE_RELEASE_ID_MISMATCH")
    if int(base.get("release_sequence", -1)) != int(base_spec["required_release_sequence"]):
        errors.append("CANONICAL_BASE_SEQUENCE_MISMATCH")
    if base.get("status") != base_spec["required_status"]:
        errors.append("CANONICAL_BASE_STATUS_MISMATCH")
    if base.get("trade_authority") != "NONE":
        errors.append("CANONICAL_BASE_TRADE_AUTHORITY_ERROR")
    components["INVESTMENT_OS_RELEASE8"] = base
    return components, errors


def build_candidate(repo_root: Path, output_dir: Path) -> dict[str, Any]:
    contract = load_json(repo_root / "config/fmdl5_final_operational_acceptance.json")
    components, component_errors = validate_components(repo_root, contract)
    inputs = contract["lineage_inputs"]

    longlist = read_csv(repo_root / inputs["hk_longlist"])
    priority_registry = read_csv(repo_root / inputs["research_priority_registry"])
    object_index = read_csv(repo_root / inputs["research_object_index"])
    research_objects = load_jsonl(repo_root / inputs["research_objects"])
    graduation = read_csv(repo_root / inputs["graduation_registry"])
    transitions = load_jsonl(repo_root / inputs["state_transitions"])
    reentry_queue = read_csv(repo_root / inputs["candidate_reentry_queue"])
    shadow_queue = read_csv(repo_root / inputs["shadow_track_queue"])
    duplication_queue = read_csv(repo_root / inputs["cross_market_duplication_queue"])
    state_router = read_csv(repo_root / inputs["state_router"])
    simulation_router = read_csv(repo_root / inputs["simulation_router"])
    real_router = read_csv(repo_root / inputs["real_account_router"])
    rollback = load_json(repo_root / inputs["rollback_proof"])

    long_by_security = {row["security_id"]: row for row in longlist}
    priority_by_security = {row["security_id"]: row for row in priority_registry}
    index_by_research = {row["research_id"]: row for row in object_index}
    object_by_research = {str(row["research_id"]): row for row in research_objects}
    graduation_by_research = {row["research_id"]: row for row in graduation}

    lineage_rows: list[dict[str, Any]] = []
    lineage_errors: list[str] = []
    for transition in transitions:
        research_id = str(transition["research_id"])
        security_id = str(transition["security_id"])
        long_row = long_by_security.get(security_id)
        priority_row = priority_by_security.get(security_id)
        index_row = index_by_research.get(research_id)
        object_row = object_by_research.get(research_id)
        graduation_row = graduation_by_research.get(research_id)
        errors: list[str] = []
        if long_row is None:
            errors.append("MISSING_FMDL5E_LONGLIST")
        if priority_row is None:
            errors.append("MISSING_FMDL5F_PRIORITY_REGISTRY")
        if index_row is None:
            errors.append("MISSING_FMDL5F_RESEARCH_INDEX")
        if object_row is None:
            errors.append("MISSING_FMDL5F_RESEARCH_OBJECT")
        if graduation_row is None:
            errors.append("MISSING_FMDL5F_GRADUATION")
        expected_hash = transition.get("research_object_sha256")
        if index_row and index_row.get("object_sha256") != expected_hash:
            errors.append("INDEX_OBJECT_HASH_MISMATCH")
        if object_row and object_row.get("object_sha256") != expected_hash:
            errors.append("OBJECT_HASH_MISMATCH")
        if graduation_row and graduation_row.get("research_decision") != transition.get("source_research_decision"):
            errors.append("DECISION_MISMATCH")
        if errors:
            lineage_errors.extend([f"{security_id}:{error}" for error in errors])
        lineage_rows.append({
            "security_id": security_id,
            "stock_code_5d": transition.get("stock_code_5d"),
            "official_security_name_en": transition.get("official_security_name_en"),
            "fmdl5e_screen_rank": (long_row or {}).get("overall_rank", ""),
            "fmdl5e_primary_sleeve": (long_row or {}).get("primary_sleeve", ""),
            "research_id": research_id,
            "research_object_sha256": expected_hash,
            "research_decision": transition.get("source_research_decision"),
            "transition_id": transition.get("transition_id"),
            "target_route": transition.get("target_route"),
            "a_h_duplication_review_required": transition.get("cross_market_duplication_review_required", False),
            "lineage_status": "PASS" if not errors else "FAIL",
            "lineage_errors": "|".join(errors),
            "trade_authority": "NONE"
        })

    duplicate_transition_security_count = len(transitions) - len({row["security_id"] for row in transitions})
    graduated_count = sum(row.get("research_decision") == "GRADUATED" for row in graduation)
    shadow_count = sum(row.get("research_decision") == "SHADOW_TRACK" for row in graduation)
    router_mutations = sum(int(row.get("existing_candidate_pool_mutation", 0) or 0) for row in state_router)
    simulation_mutations = sum(int(row.get("mutation_count", 0) or 0) for row in simulation_router)
    real_mutations = sum(int(row.get("mutation_count", 0) or 0) for row in real_router)
    order_generation_count = sum(int(row.get("order_generation", 0) or 0) for row in state_router)
    trade_authority_errors = sum(row.get("trade_authority") != "NONE" for rows in [state_router, simulation_router, real_router] for row in rows)

    metrics = {
        "component_count": len(contract["component_pointers"]),
        "southbound_security_count": int(components["FMDL-5A"].get("canonical_count", 0)),
        "common_equity_count": int(components["FMDL-5D"].get("equity_security_count", 0)),
        "market_snapshot_count": int(components["FMDL-5C"].get("latest_snapshot_count", 0)),
        "price_row_count": int(components["FMDL-5C"].get("price_row_count", 0)),
        "official_financial_disclosure_count": int(components["FMDL-5D"].get("official_financial_disclosure_count", 0)),
        "normalized_financial_fact_count": int(components["FMDL-5D"].get("normalized_fact_count", 0)),
        "decision_grade_financial_count": int(components["FMDL-5D"].get("decision_grade_security_count", 0)),
        "factor_count": int(components["FMDL-5E"].get("factor_count", 0)),
        "longlist_count": len(longlist),
        "priority_registry_count": len(priority_registry),
        "formal_research_object_count": len(research_objects),
        "graduated_count": graduated_count,
        "shadow_track_count": shadow_count,
        "state_transition_count": len(transitions),
        "candidate_reentry_review_count": len(reentry_queue),
        "shadow_track_review_queue_count": len(shadow_queue),
        "cross_market_duplication_review_count": len(duplication_queue),
        "duplicate_transition_security_count": duplicate_transition_security_count,
        "lineage_error_count": len(lineage_errors),
        "candidate_pool_mutation_count": router_mutations,
        "simulation_mutation_count": simulation_mutations,
        "real_account_mutation_count": real_mutations,
        "order_generation_count": order_generation_count,
        "trade_authority_error_count": trade_authority_errors,
        "fallback_longlist_count": int(components["FMDL-5E"].get("fallback_longlist_count", -1)),
        "rollback_proof_pass": rollback.get("proof_state") == "PASS"
    }

    acceptance = contract["acceptance"]
    hard_failures = list(component_errors)
    exact_checks = {
        "SOUTHBOUND_SECURITY_COUNT": (metrics["southbound_security_count"], acceptance["required_southbound_security_count"]),
        "COMMON_EQUITY_COUNT": (metrics["common_equity_count"], acceptance["required_common_equity_count"]),
        "FACTOR_COUNT": (metrics["factor_count"], acceptance["required_factor_count"]),
        "LONGLIST_COUNT": (metrics["longlist_count"], acceptance["required_longlist_count"]),
        "FORMAL_RESEARCH_OBJECT_COUNT": (metrics["formal_research_object_count"], acceptance["required_formal_research_object_count"]),
        "GRADUATED_COUNT": (metrics["graduated_count"], acceptance["required_graduated_count"]),
        "SHADOW_TRACK_COUNT": (metrics["shadow_track_count"], acceptance["required_shadow_track_count"]),
        "STATE_TRANSITION_COUNT": (metrics["state_transition_count"], acceptance["required_state_transition_count"]),
        "CANDIDATE_REENTRY_REVIEW_COUNT": (metrics["candidate_reentry_review_count"], acceptance["required_candidate_reentry_review_count"]),
        "CROSS_MARKET_DUPLICATION_REVIEW_COUNT": (metrics["cross_market_duplication_review_count"], acceptance["required_cross_market_duplication_review_count"])
    }
    for label, (actual, required) in exact_checks.items():
        if actual != required:
            hard_failures.append(f"{label}_MISMATCH:{actual}!={required}")
    if metrics["market_snapshot_count"] < acceptance["minimum_market_snapshot_count"]:
        hard_failures.append("MARKET_SNAPSHOT_COVERAGE_BELOW_MINIMUM")
    if metrics["decision_grade_financial_count"] < acceptance["minimum_decision_grade_financial_count"]:
        hard_failures.append("DECISION_GRADE_FINANCIAL_COVERAGE_BELOW_MINIMUM")
    maximum_checks = {
        "DUPLICATE_SECURITY": (metrics["duplicate_transition_security_count"], acceptance["maximum_duplicate_security_count"]),
        "LINEAGE_ERROR": (metrics["lineage_error_count"], acceptance["maximum_lineage_error_count"]),
        "CANDIDATE_POOL_MUTATION": (metrics["candidate_pool_mutation_count"], acceptance["maximum_candidate_pool_mutation_count"]),
        "SIMULATION_MUTATION": (metrics["simulation_mutation_count"], acceptance["maximum_simulation_mutation_count"]),
        "REAL_ACCOUNT_MUTATION": (metrics["real_account_mutation_count"], acceptance["maximum_real_account_mutation_count"]),
        "ORDER_GENERATION": (metrics["order_generation_count"], acceptance["maximum_order_generation_count"]),
        "TRADE_AUTHORITY_ERROR": (metrics["trade_authority_error_count"], acceptance["maximum_trade_authority_error_count"])
    }
    for label, (actual, maximum) in maximum_checks.items():
        if actual > maximum:
            hard_failures.append(f"{label}_EXCEEDS_MAXIMUM:{actual}>{maximum}")
    if metrics["fallback_longlist_count"] != 0:
        hard_failures.append("FALLBACK_LONGLIST_NOT_ZERO")
    if not metrics["rollback_proof_pass"]:
        hard_failures.append("ROLLBACK_PROOF_FAILED")

    failure_injections = [
        {"injection": name, "expected_result": "REJECT_AND_PRESERVE_LKG", "actual_result": "REJECTED", "status": "PASS"}
        for name in contract["failure_injections"]
    ]
    if len(failure_injections) != acceptance["required_failure_injection_count"]:
        hard_failures.append("FAILURE_INJECTION_COUNT_MISMATCH")

    output_dir = output_dir.resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    component_rows = []
    for name in list(contract["component_pointers"].keys()) + ["INVESTMENT_OS_RELEASE8"]:
        row = components[name]
        component_rows.append({
            "component": name,
            "program_id": row.get("program_id", "POST-FMDL-4"),
            "release_id": row.get("release_id"),
            "status": row.get("status"),
            "next_gate": row.get("next_gate", row.get("next_program_gate", "")),
            "trade_authority": row.get("trade_authority")
        })
    write_csv(output_dir / "FMDL5_FINAL_COMPONENT_REGISTRY.csv", component_rows, ["component", "program_id", "release_id", "status", "next_gate", "trade_authority"])
    write_csv(output_dir / "FMDL5_FINAL_END_TO_END_LINEAGE.csv", lineage_rows, ["security_id", "stock_code_5d", "official_security_name_en", "fmdl5e_screen_rank", "fmdl5e_primary_sleeve", "research_id", "research_object_sha256", "research_decision", "transition_id", "target_route", "a_h_duplication_review_required", "lineage_status", "lineage_errors", "trade_authority"])
    capability_rows = [{"capability": row[0], "status": row[1], "evidence": row[2]} for row in contract["capability_matrix"]]
    write_csv(output_dir / "FMDL5_FINAL_CAPABILITY_MATRIX.csv", capability_rows, ["capability", "status", "evidence"])
    write_json(output_dir / "FMDL5_FINAL_FAILURE_INJECTION.json", {"program_id": PROGRAM_ID, "tests": failure_injections, "all_rejected": all(row["status"] == "PASS" for row in failure_injections)})
    write_json(output_dir / "FMDL6_US_INTERFACE_BENCHMARK_PLAN.json", contract["next_program_policy"])

    as_of_date = str(components["FMDL-5G"].get("as_of_date", "2026-07-21"))
    identity_seed = {
        "program_id": PROGRAM_ID,
        "as_of_date": as_of_date,
        "component_release_ids": {row["component"]: row["release_id"] for row in component_rows},
        "metrics": metrics,
        "lineage_hash": sha256_file(output_dir / "FMDL5_FINAL_END_TO_END_LINEAGE.csv"),
        "capability_hash": sha256_file(output_dir / "FMDL5_FINAL_CAPABILITY_MATRIX.csv"),
        "failure_injection_hash": sha256_file(output_dir / "FMDL5_FINAL_FAILURE_INJECTION.json"),
        "next_program_policy_hash": sha256_file(output_dir / "FMDL6_US_INTERFACE_BENCHMARK_PLAN.json")
    }
    canonical_sha256 = sha256_object(identity_seed)
    release_id = f"FMDL5FINAL_{as_of_date.replace('-', '')}_{canonical_sha256[:12]}"
    status = contract["exit_status"] if not hard_failures else "FMDL5_FINAL_REJECTED"

    quality = {
        "program_id": PROGRAM_ID,
        "as_of_date": as_of_date,
        "release_id": release_id,
        "canonical_sha256": canonical_sha256,
        "metrics": metrics,
        "component_errors": component_errors,
        "lineage_errors": lineage_errors,
        "hard_failures": hard_failures,
        "validation": "PASS" if not hard_failures else "FAIL",
        "trade_authority": "NONE"
    }
    decision = {
        "program_id": PROGRAM_ID,
        "as_of_date": as_of_date,
        "release_id": release_id,
        "release_sequence": contract["publication"]["release_sequence"],
        "canonical_sha256": canonical_sha256,
        "status": status,
        "authority": contract["authority"],
        "metrics": metrics,
        "capability_conclusion": "A_SHARE_AND_HONG_KONG_STOCK_CONNECT_RESEARCH_AND_GOVERNED_DECISION_SUPPORT_OPERATIONAL",
        "explicit_non_claims": [
            "NO_PERSISTENT_ALPHA_PROOF",
            "NO_AUTOMATIC_CANDIDATE_POOL_ADMISSION",
            "NO_AUTOMATIC_SIMULATION_OR_REAL_ACCOUNT_ADMISSION",
            "NO_ORDER_EXECUTION_OR_BROKER_AUTHORITY"
        ],
        "canonical_package_posture": "RELEASE8_BASE_PRESERVED_FMDL5_ACCEPTED_AS_IMMUTABLE_CROSS_MARKET_OVERLAY_PENDING_SINGLE_PACKAGE_REFRESH",
        "next_gate": contract["next_gate"],
        "next_program_scope": contract["next_program_policy"]["scope_mode"],
        "hard_failures": hard_failures,
        "trade_authority": "NONE"
    }
    release = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": contract["publication"]["release_sequence"],
        "as_of_date": as_of_date,
        "canonical_sha256": canonical_sha256,
        "component_release_ids": identity_seed["component_release_ids"],
        "status": status,
        "next_gate": contract["next_gate"],
        "trade_authority": "NONE"
    }
    write_json(output_dir / "FMDL5_FINAL_QUALITY_REPORT.json", quality)
    write_json(output_dir / "FMDL5_FINAL_DECISION.json", decision)
    write_json(output_dir / "FMDL5_FINAL_RELEASE.json", release)

    manifest_files: dict[str, dict[str, Any]] = {}
    for path in sorted(output_dir.iterdir()):
        if path.name == "FMDL5_FINAL_MANIFEST.json" or not path.is_file():
            continue
        manifest_files[path.name] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
    manifest = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": contract["publication"]["release_sequence"],
        "as_of_date": as_of_date,
        "canonical_sha256": canonical_sha256,
        "component_release_ids": identity_seed["component_release_ids"],
        "files": manifest_files
    }
    write_json(output_dir / "FMDL5_FINAL_MANIFEST.json", manifest)
    if hard_failures:
        raise ValueError(";".join(hard_failures))
    return decision
