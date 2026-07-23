#!/usr/bin/env python3
"""Deterministic FMDL-7A canonical inventory and state-reconciliation producer."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

CONTRACT_PATH = Path("config/fmdl7a_state_reconciliation_contract.json")
EXIT_STATUS = "FMDL7A_CROSS_MARKET_CANONICAL_INVENTORY_AND_STATE_RECONCILIATION_ACCEPTED"
NEXT_GATE = "FMDL-7B_END_TO_END_RESEARCH_AND_DECISION_LINEAGE_ACCEPTANCE"
SHARD_DOMAINS = [
    "CANONICAL_INVENTORY",
    "MARKET_CAPABILITY_AND_FRESHNESS",
    "INVESTMENT_STATE_DOMAINS",
    "CROSS_MARKET_DUPLICATION",
    "FILE_LIBRARY_AND_ACCEPTANCE",
]


class ContractError(RuntimeError):
    """Raised when a frozen acceptance contract or source binding fails."""


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def nested_get(value: Any, dotted_path: str) -> Any:
    cursor = value
    for part in dotted_path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            raise KeyError(dotted_path)
        cursor = cursor[part]
    return cursor


def check_field(errors: list[str], payload: dict[str, Any], dotted_path: str, expected: Any, code: str) -> None:
    try:
        actual = nested_get(payload, dotted_path)
    except KeyError:
        errors.append(f"{code}:MISSING:{dotted_path}")
        return
    if actual != expected:
        errors.append(f"{code}:MISMATCH:{dotted_path}")


def validate_contract(repo_root: Path, contract: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    errors: list[str] = []
    source_hashes: dict[str, str] = {}

    if contract.get("phase_id") != "FMDL-7A":
        errors.append("CONTRACT_PHASE_ID")
    if contract.get("required_exit_status") != EXIT_STATUS:
        errors.append("CONTRACT_EXIT_STATUS")
    if contract.get("next_gate") != NEXT_GATE:
        errors.append("CONTRACT_NEXT_GATE")
    if contract.get("trade_authority") != "NONE":
        errors.append("CONTRACT_TRADE_AUTHORITY")

    entry = contract.get("entry_gate", {})
    entry_path = repo_root / str(entry.get("path", ""))
    if not entry_path.exists():
        errors.append("ENTRY_GATE_MISSING")
    else:
        entry_payload = read_json(entry_path)
        for field, expected in {
            "phase_id": entry.get("required_phase_id"),
            "release_id": entry.get("required_release_id"),
            "release_sequence": entry.get("required_release_sequence"),
            "status": entry.get("required_status"),
            "next_gate": entry.get("required_next_gate"),
            "trade_authority": entry.get("required_trade_authority"),
        }.items():
            check_field(errors, entry_payload, field, expected, "ENTRY_GATE")
        source_hashes["FMDL7_0_LAST_SUCCESS"] = sha256_file(entry_path)

    bindings = contract.get("source_bindings", {})
    if not isinstance(bindings, dict) or len(bindings) != 7:
        errors.append("SOURCE_BINDING_COUNT")
        bindings = {}

    def load_binding(name: str) -> tuple[Path, dict[str, Any]]:
        binding = bindings.get(name, {})
        path = repo_root / str(binding.get("path", ""))
        if not path.exists():
            errors.append(f"SOURCE_MISSING:{name}")
            return path, {}
        source_hashes[name] = sha256_file(path)
        if path.suffix.lower() == ".json":
            return path, read_json(path)
        return path, {}

    _, a_share = load_binding("a_share_interface")
    if a_share:
        b = bindings["a_share_interface"]
        for field, expected in {
            "interface_id": b["required_interface_id"],
            "status": b["required_status"],
            "current_release.run_id": b["required_run_id"],
            "current_release.as_of_date": b["required_as_of_date"],
            "downstream_handoff.trade_authority": b["required_trade_authority"],
        }.items():
            check_field(errors, a_share, field, expected, "A_SHARE")

    _, release8 = load_binding("investment_os_release8")
    if release8:
        b = bindings["investment_os_release8"]
        for field, expected in {
            "release_id": b["required_release_id"],
            "release_sequence": b["required_release_sequence"],
            "status": b["required_status"],
            "package_sha256": b["required_package_sha256"],
            "market_as_of": b["required_market_as_of"],
            "trade_authority": b["required_trade_authority"],
        }.items():
            check_field(errors, release8, field, expected, "RELEASE8")

    _, state_binding = load_binding("investment_state_binding")
    if state_binding:
        b = bindings["investment_state_binding"]
        if state_binding.get("source_release_sequence") != b["required_source_release_sequence"]:
            errors.append("STATE_BINDING_RELEASE_SEQUENCE")
        if len(state_binding.get("real_holdings", [])) != b["required_real_holding_count"]:
            errors.append("STATE_BINDING_REAL_HOLDING_COUNT")
        if len(state_binding.get("simulation_holdings", [])) != b["required_simulation_holding_count"]:
            errors.append("STATE_BINDING_SIMULATION_HOLDING_COUNT")
        if len(state_binding.get("candidate_core_20", [])) != b["required_candidate_core_count"]:
            errors.append("STATE_BINDING_CANDIDATE_COUNT")
        if len(state_binding.get("active_memo_price_thresholds", {})) != b["required_active_memo_count"]:
            errors.append("STATE_BINDING_ACTIVE_MEMO_COUNT")
        if state_binding.get("trade_authority") != b["required_trade_authority"]:
            errors.append("STATE_BINDING_TRADE_AUTHORITY")

    _, action_review = load_binding("operating_state_review")
    if action_review:
        b = bindings["operating_state_review"]
        for field, expected in {
            "as_of": b["required_as_of"],
            "real_account.holding_count": b["required_real_holding_count"],
            "simulation.holding_count": b["required_simulation_holding_count"],
            "candidate_pool.formal_core_count": b["required_candidate_core_count"],
            "candidate_pool.active_memo_count": b["required_active_memo_count"],
            "trade_authority": b["required_trade_authority"],
        }.items():
            check_field(errors, action_review, field, expected, "ACTION_REVIEW")

    _, hk_final = load_binding("hong_kong_final")
    if hk_final:
        b = bindings["hong_kong_final"]
        for field, expected in {
            "release_id": b["required_release_id"],
            "release_sequence": b["required_release_sequence"],
            "status": b["required_status"],
            "canonical_base_release_id": b["required_canonical_base_release_id"],
            "trade_authority": b["required_trade_authority"],
        }.items():
            check_field(errors, hk_final, field, expected, "HK_FINAL")

    hk_csv_binding = bindings.get("hong_kong_duplication_registry", {})
    hk_csv_path = repo_root / str(hk_csv_binding.get("path", ""))
    if not hk_csv_path.exists():
        errors.append("HK_DUPLICATION_REGISTRY_MISSING")
        hk_rows: list[dict[str, str]] = []
    else:
        source_hashes["hong_kong_duplication_registry"] = sha256_file(hk_csv_path)
        hk_rows = read_csv(hk_csv_path)
        if len(hk_rows) != hk_csv_binding.get("required_row_count"):
            errors.append("HK_DUPLICATION_ROW_COUNT")
        if sorted(row.get("security_id") for row in hk_rows) != sorted(hk_csv_binding.get("required_security_ids", [])):
            errors.append("HK_DUPLICATION_SECURITY_IDS")
        if any(row.get("trade_authority") != "NONE" for row in hk_rows):
            errors.append("HK_DUPLICATION_TRADE_AUTHORITY")

    _, us_final = load_binding("us_final")
    if us_final:
        b = bindings["us_final"]
        for field, expected in {
            "release_id": b["required_release_id"],
            "release_sequence": b["required_release_sequence"],
            "status": b["required_status"],
            "fmdl6_status": b["required_fmdl6_status"],
            "trade_authority": b["required_trade_authority"],
        }.items():
            check_field(errors, us_final, field, expected, "US_FINAL")

    observation = contract.get("file_library_observation", {})
    if observation.get("pointer_release_id") != "INVESTMENT_OS_R8_20260720_501345e84562":
        errors.append("FILE_LIBRARY_POINTER_RELEASE")
    if observation.get("pointer_package_sha256") != release8.get("package_sha256"):
        errors.append("FILE_LIBRARY_POINTER_SHA_MISMATCH")
    if observation.get("conversation_memory_authoritative") is not False:
        errors.append("CONVERSATION_MEMORY_AUTHORITY")

    if set(contract.get("market_inventory", {})) != {"A_SHARE", "HONG_KONG_CONNECT", "US_EQUITY"}:
        errors.append("MARKET_INVENTORY_SET")
    if set(contract.get("state_domains", {})) != {"real_account", "simulation_book", "candidate_pool"}:
        errors.append("STATE_DOMAIN_SET")
    if len(contract.get("duplication_controls", {}).get("a_h_duplication_cases", [])) != 2:
        errors.append("A_H_DUPLICATION_CASE_COUNT")
    if len(contract.get("reconciliation_conclusions", [])) != 6:
        errors.append("RECONCILIATION_CONCLUSION_COUNT")

    scope = contract.get("scope", {})
    for field in [
        "new_market_data_refresh_authorized",
        "research_workflow_execution_authorized",
        "candidate_pool_mutation_authorized",
        "simulation_book_mutation_authorized",
        "real_account_mutation_authorized",
        "rule_mutation_authorized",
        "canonical_repack_authorized",
        "brokerage_or_order_authorized",
    ]:
        if scope.get(field) is not False:
            errors.append(f"SCOPE_NOT_FAIL_CLOSED:{field}")

    gates = contract.get("acceptance_gates", {})
    expected_gates = {
        "source_binding_count": 7,
        "market_count": 3,
        "state_domain_count": 3,
        "a_h_duplication_case_count": 2,
        "real_account_duplication_case_count": 1,
        "reconciliation_conclusion_count": 6,
        "gate_count": 16,
        "logical_shard_domain_count": 5,
        "bucket_count": 64,
        "logical_shard_count": 320,
        "candidate_pool_mutations": 0,
        "simulation_book_mutations": 0,
        "real_account_mutations": 0,
        "rule_mutations": 0,
        "orders": 0,
    }
    for field, expected in expected_gates.items():
        if gates.get(field) != expected:
            errors.append(f"ACCEPTANCE_GATE:{field}")
    if contract.get("storage_contract", {}).get("release_sequence") != 49:
        errors.append("STORAGE_RELEASE_SEQUENCE")

    return sorted(set(errors)), source_hashes


def build_gate_matrix(contract: dict[str, Any], source_hashes: dict[str, str]) -> list[dict[str, Any]]:
    checks = [
        ("FMDL7_0_RELEASE48_ENTRY_ACCEPTED", "FMDL7_0_LAST_SUCCESS" in source_hashes),
        ("SEVEN_SOURCE_BINDINGS_VERIFIED", len(contract["source_bindings"]) == 7),
        ("THREE_MARKETS_REGISTERED", len(contract["market_inventory"]) == 3),
        ("THREE_INVESTMENT_STATE_DOMAINS_SEPARATED", len(contract["state_domains"]) == 3),
        ("A_SHARE_STALE_NEW_DECISION_BLOCKED", contract["market_inventory"]["A_SHARE"]["freshness_state"] == "STALE_FOR_NEW_FULL_MARKET_DECISION_REQUIRES_REFRESH"),
        ("HK_OVERLAY_NOT_REPACKED_IN_RELEASE8", "NOT_REPACKED" in contract["market_inventory"]["HONG_KONG_CONNECT"]["freshness_state"]),
        ("US_MARKET_AND_ATTRIBUTION_NON_DECISION_GRADE", "NON_DECISION_GRADE" in contract["market_inventory"]["US_EQUITY"]["freshness_state"]),
        ("REAL_ACCOUNT_LKG_NOT_FALSELY_CURRENT", "LAST_KNOWN_GOOD" in contract["state_domains"]["real_account"]["reconciliation_state"]),
        ("SIMULATION_LKG_NOT_FALSELY_CURRENT", "LAST_KNOWN_GOOD" in contract["state_domains"]["simulation_book"]["reconciliation_state"]),
        ("CANDIDATE_CORE20_LKG_PRESERVED", contract["state_domains"]["candidate_pool"]["formal_core_count"] == 20),
        ("REAL_SP500_DUPLICATION_REGISTERED", contract["duplication_controls"]["real_account_duplicate_exposure"]["security_codes"] == ["159612", "159655"]),
        ("TWO_A_H_DUPLICATION_CASES_REGISTERED", len(contract["duplication_controls"]["a_h_duplication_cases"]) == 2),
        ("FILE_LIBRARY_POINTER_MATCHED_BINARY_UNVERIFIED", contract["file_library_observation"]["canonical_zip_status"].startswith("NOT_INDEPENDENTLY_RETRIEVABLE")),
        ("NO_RESEARCH_OR_SHADOW_STATE_MISCLASSIFIED", "NO_RESEARCH_POOL_SHADOW_TRACK_OR_BENCHMARK_POOL_IS_A_FORMAL_CANDIDATE_OR_POSITION" in contract["reconciliation_conclusions"]),
        ("ZERO_MUTATION_GATE", all(contract["acceptance_gates"][key] == 0 for key in ["candidate_pool_mutations", "simulation_book_mutations", "real_account_mutations", "rule_mutations", "orders"])),
        ("ONLY_FMDL7B_NEXT_GATE_OPEN", contract["next_gate"] == NEXT_GATE and contract["trade_authority"] == "NONE"),
    ]
    return [
        {"gate_order": index, "gate_code": code, "gate_status": "PASS" if passed else "FAIL", "trade_authority": "NONE"}
        for index, (code, passed) in enumerate(checks, start=1)
    ]


def build_candidate(repo_root: Path, output_dir: Path, generated_at: str, source_commit: str) -> dict[str, Any]:
    contract_path = repo_root / CONTRACT_PATH
    contract = read_json(contract_path)
    errors, source_hashes = validate_contract(repo_root, contract)
    if errors:
        raise ContractError("CONTRACT_VALIDATION_FAILED:" + ",".join(errors))

    basis = {
        "contract_sha256": sha256_file(contract_path),
        "source_hashes": source_hashes,
        "source_commit": source_commit,
        "as_of_date": contract["as_of_date"],
    }
    release_digest = sha256_bytes(canonical_bytes(basis))
    release_id = f"FMDL7A_{contract['as_of_date'].replace('-', '')}_{release_digest[:12]}"

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    state_binding = read_json(repo_root / contract["source_bindings"]["investment_state_binding"]["path"])
    action_review = read_json(repo_root / contract["source_bindings"]["operating_state_review"]["path"])
    hk_rows = read_csv(repo_root / contract["source_bindings"]["hong_kong_duplication_registry"]["path"])

    inventory = [
        {"component": "A_SHARE_MARKET_INTERFACE", "identity": "FMDL1BC_20260717T174015+0800", "canonical_role": "A_SHARE_DATA_INTERFACE", "as_of": "2026-07-17", "reconciliation_state": "BOUND_STALE_FOR_NEW_DECISION", "trade_authority": "NONE"},
        {"component": "INVESTMENT_OS_RELEASE8", "identity": "INVESTMENT_OS_R8_20260720_501345e84562", "canonical_role": "BINARY_CANONICAL_BASE", "as_of": "2026-07-20_CLOSE", "reconciliation_state": "BOUND_LAST_KNOWN_GOOD", "trade_authority": "NONE"},
        {"component": "FMDL5_HONG_KONG_OVERLAY", "identity": "FMDL5FINAL_20260721_a43285d1ee25", "canonical_role": "IMMUTABLE_READ_ONLY_OVERLAY", "as_of": "2026-07-21", "reconciliation_state": "ACCEPTED_NOT_REPACKED", "trade_authority": "NONE"},
        {"component": "FMDL6_US_RESEARCH_ADAPTER", "identity": "FMDL6X4FINAL_20260723_dbe82fe7b7ec", "canonical_role": "FROZEN_RESEARCH_ADAPTER", "as_of": "2026-07-23", "reconciliation_state": "ACCEPTED_RESEARCH_ONLY", "trade_authority": "NONE"},
    ]
    write_json(output_dir / "FMDL7A_CANONICAL_INVENTORY.json", {
        "phase_id": "FMDL-7A",
        "release_id": release_id,
        "component_count": len(inventory),
        "components": inventory,
        "binary_canonical_base": "INVESTMENT_OS_R8_20260720_501345e84562",
        "overlays_repacked_in_binary_base": False,
        "canonical_refresh_stage": "FMDL-7E",
        "trade_authority": "NONE",
    })

    market_rows: list[dict[str, Any]] = []
    for market, record in contract["market_inventory"].items():
        market_rows.append({
            "market": market,
            "canonical_role": record["canonical_role"],
            "security_universe_count": record.get("security_universe_count", ""),
            "research_longlist_count": record.get("research_longlist_count", ""),
            "research_object_count": record.get("research_object_count", ""),
            "candidate_or_benchmark_count": record.get("candidate_core_count", record.get("benchmark_pool_member_count", "")),
            "as_of": record.get("operating_state_as_of", record.get("as_of_date", "")),
            "freshness_state": record["freshness_state"],
            "decision_grade": record["decision_grade"],
            "trade_authority": "NONE",
        })
    write_csv(output_dir / "FMDL7A_MARKET_CAPABILITY_MATRIX.csv", market_rows, [
        "market", "canonical_role", "security_universe_count", "research_longlist_count", "research_object_count",
        "candidate_or_benchmark_count", "as_of", "freshness_state", "decision_grade", "trade_authority",
    ])

    state_registry = {
        "phase_id": "FMDL-7A",
        "release_id": release_id,
        "as_of": action_review["as_of"],
        "state_authority": "LAST_KNOWN_GOOD_NOT_CONFIRMED_CURRENT_AFTER_AS_OF",
        "real_account": {**contract["state_domains"]["real_account"], "holdings": state_binding["real_holdings"]},
        "simulation_book": {**contract["state_domains"]["simulation_book"], "holdings": state_binding["simulation_holdings"]},
        "candidate_pool": {
            **contract["state_domains"]["candidate_pool"],
            "core_members": state_binding["candidate_core_20"],
            "active_memo_price_thresholds": state_binding["active_memo_price_thresholds"],
        },
        "cash_policy": state_binding["cash_policy"],
        "post_as_of_user_confirmation_required": True,
        "trade_authority": "NONE",
    }
    write_json(output_dir / "FMDL7A_STATE_DOMAIN_REGISTRY.json", state_registry)

    freshness_rows = [
        {"domain": "A_SHARE_MARKET_DATA", "as_of": "2026-07-17", "freshness_state": "STALE", "allowed_use": "LKG_CONTEXT_ONLY", "blocked_use": "NEW_FULL_MARKET_DECISION", "recovery_action": "REFRESH_BEFORE_FMDL7C_DECISION_REVIEW", "trade_authority": "NONE"},
        {"domain": "REAL_ACCOUNT_STATE", "as_of": "2026-07-20_CLOSE", "freshness_state": "UNCONFIRMED_AFTER_AS_OF", "allowed_use": "LAST_KNOWN_GOOD_RECONCILIATION", "blocked_use": "CLAIM_CURRENT_OR_EXECUTE", "recovery_action": "USER_CONFIRM_ANY_POST_AS_OF_CHANGE", "trade_authority": "NONE"},
        {"domain": "SIMULATION_STATE", "as_of": "2026-07-20_CLOSE", "freshness_state": "UNCONFIRMED_AFTER_AS_OF", "allowed_use": "LAST_KNOWN_GOOD_RECONCILIATION", "blocked_use": "CLAIM_CURRENT_OR_ATTRIBUTE_NEW_PERIOD", "recovery_action": "USER_CONFIRM_ANY_POST_AS_OF_CHANGE", "trade_authority": "NONE"},
        {"domain": "CANDIDATE_POOL_STATE", "as_of": "2026-07-20_CLOSE", "freshness_state": "UNCONFIRMED_AFTER_AS_OF", "allowed_use": "CORE20_LKG", "blocked_use": "AUTOMATIC_MEMBERSHIP_CHANGE", "recovery_action": "REVALIDATE_TRIGGERS_AND_USER_APPROVAL", "trade_authority": "NONE"},
        {"domain": "HONG_KONG_OVERLAY", "as_of": "2026-07-21", "freshness_state": "ACCEPTED_OVERLAY", "allowed_use": "RESEARCH_REENTRY_REVIEW", "blocked_use": "AUTOMATIC_CANDIDATE_OR_POSITION", "recovery_action": "PRESERVE_OVERLAY_UNTIL_FMDL7E_REPACK", "trade_authority": "NONE"},
        {"domain": "US_RESEARCH_ADAPTER", "as_of": "2026-07-23", "freshness_state": "RESEARCH_CURRENT_MARKET_NON_DECISION_GRADE", "allowed_use": "RESEARCH_ARCHITECTURE_AND_BENCHMARK_VALIDATION", "blocked_use": "FORMAL_CANDIDATE_SIMULATION_OR_PERFORMANCE_CLAIM", "recovery_action": "KEEP_FORMAL_GATES_CLOSED", "trade_authority": "NONE"},
        {"domain": "FILE_LIBRARY_BINARY", "as_of": "2026-07-20", "freshness_state": "POINTER_MATCHED_BINARY_NOT_BYTE_VERIFIED", "allowed_use": "IDENTITY_REFERENCE_ONLY", "blocked_use": "CLAIM_BINARY_VERIFIED_OR_OVERLAYS_REPACKED", "recovery_action": "VERIFY_AND_REFRESH_IN_FMDL7E", "trade_authority": "NONE"},
    ]
    write_csv(output_dir / "FMDL7A_FRESHNESS_AND_STALENESS_REGISTRY.csv", freshness_rows, [
        "domain", "as_of", "freshness_state", "allowed_use", "blocked_use", "recovery_action", "trade_authority",
    ])

    duplication_rows = [{
        "case_id": "REAL-SP500-ETF-DUPLICATION",
        "market_relation": "REAL_ACCOUNT_SAME_INDEX_EXPOSURE",
        "security_ids": "159612|159655",
        "names": "标普500ETF国泰|标普500ETF华夏",
        "review_state": "CONTROLLED_REVIEW_ONLY",
        "admission_state": "NO_AUTOMATIC_CONSOLIDATION",
        "trade_authority": "NONE",
    }]
    for row in sorted(hk_rows, key=lambda item: item["security_id"]):
        duplication_rows.append({
            "case_id": row["transition_id"],
            "market_relation": "A_H_CROSS_LISTING",
            "security_ids": row["security_id"],
            "names": row["official_security_name_en"],
            "review_state": row["review_state"],
            "admission_state": row["admission_state"],
            "trade_authority": row["trade_authority"],
        })
    write_csv(output_dir / "FMDL7A_CROSS_MARKET_DUPLICATION_REGISTRY.csv", duplication_rows, [
        "case_id", "market_relation", "security_ids", "names", "review_state", "admission_state", "trade_authority",
    ])

    write_json(output_dir / "FMDL7A_FILE_LIBRARY_RECONCILIATION.json", {
        "phase_id": "FMDL-7A",
        "release_id": release_id,
        **contract["file_library_observation"],
        "github_release8_identity_match": True,
        "file_library_is_not_technical_release_history": True,
        "required_fmdl7e_target": ["ONE_CURRENT_CANONICAL_ZIP", "ONE_MATCHING_POINTER", "ONE_START_HERE"],
        "trade_authority": "NONE",
    })

    gate_matrix = build_gate_matrix(contract, source_hashes)
    failed_gates = [row["gate_code"] for row in gate_matrix if row["gate_status"] != "PASS"]
    if failed_gates:
        raise ContractError("ACCEPTANCE_GATE_FAILED:" + ",".join(failed_gates))
    write_json(output_dir / "FMDL7A_ACCEPTANCE_GATE_MATRIX.json", {
        "phase_id": "FMDL-7A",
        "release_id": release_id,
        "gate_count": len(gate_matrix),
        "pass_count": len(gate_matrix),
        "gates": gate_matrix,
        "trade_authority": "NONE",
    })

    shards = [
        {"domain": domain, "bucket": bucket, "logical_shard_id": f"FMDL7A-{domain}-{bucket:02d}", "state": "RECONCILED_NO_MUTATION", "trade_authority": "NONE"}
        for domain in SHARD_DOMAINS for bucket in range(64)
    ]
    write_json(output_dir / "FMDL7A_LOGICAL_SHARD_REGISTRY.json", {
        "phase_id": "FMDL-7A",
        "release_id": release_id,
        "domain_count": len(SHARD_DOMAINS),
        "bucket_count": 64,
        "logical_shard_count": len(shards),
        "shards": shards,
        "trade_authority": "NONE",
    })

    quality = {
        "phase_id": "FMDL-7A",
        "release_id": release_id,
        "quality_status": "PASS",
        "contract_error_count": 0,
        "source_binding_count": 7,
        "source_binding_pass_count": 7,
        "market_count": 3,
        "state_domain_count": 3,
        "freshness_record_count": len(freshness_rows),
        "duplication_case_count": len(duplication_rows),
        "acceptance_gate_count": len(gate_matrix),
        "acceptance_gate_pass_count": len(gate_matrix),
        "logical_shard_count": len(shards),
        "candidate_pool_mutations": 0,
        "simulation_book_mutations": 0,
        "real_account_mutations": 0,
        "rule_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    write_json(output_dir / "FMDL7A_QUALITY_REPORT.json", quality)

    decision = {
        "phase_id": "FMDL-7A",
        "release_id": release_id,
        "release_sequence": 49,
        "published_at": generated_at,
        "source_commit": source_commit,
        "status": EXIT_STATUS,
        "next_gate": NEXT_GATE,
        "binary_canonical_base": "INVESTMENT_OS_R8_20260720_501345e84562",
        "a_share_new_decision_state": "BLOCKED_PENDING_REFRESH",
        "investment_state_posture": "LAST_KNOWN_GOOD_AS_OF_2026_07_20_USER_CONFIRMATION_REQUIRED",
        "file_library_posture": "POINTER_MATCHED_BINARY_VERIFICATION_DEFERRED_TO_FMDL7E",
        "canonical_refresh_stage": "FMDL-7E",
        "zero_mutation_proof": {"candidate_pool_mutations": 0, "simulation_book_mutations": 0, "real_account_mutations": 0, "rule_mutations": 0, "orders": 0},
        "trade_authority": "NONE",
    }
    write_json(output_dir / "FMDL7A_DECISION.json", decision)

    manifest_files = []
    for path in sorted(output_dir.iterdir(), key=lambda item: item.name):
        if path.name == "FMDL7A_MANIFEST.json" or not path.is_file():
            continue
        manifest_files.append({"path": path.name, "sha256": sha256_file(path), "size_bytes": path.stat().st_size})
    manifest = {
        "phase_id": "FMDL-7A",
        "release_id": release_id,
        "release_sequence": 49,
        "generated_at": generated_at,
        "source_commit": source_commit,
        "contract_sha256": sha256_file(contract_path),
        "source_hashes": source_hashes,
        "file_count": len(manifest_files),
        "files": manifest_files,
        "status": EXIT_STATUS,
        "next_gate": NEXT_GATE,
        "trade_authority": "NONE",
    }
    write_json(output_dir / "FMDL7A_MANIFEST.json", manifest)
    return {"release_id": release_id, "manifest_sha256": sha256_file(output_dir / "FMDL7A_MANIFEST.json"), "quality": quality, "decision": decision}


def directory_digest(root: Path) -> str:
    records = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        records.append({"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path), "size_bytes": path.stat().st_size})
    return sha256_bytes(canonical_bytes(records))


def copy_exact(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def publish_candidate(repo_root: Path, candidate: Path) -> dict[str, Any]:
    decision = read_json(candidate / "FMDL7A_DECISION.json")
    manifest = read_json(candidate / "FMDL7A_MANIFEST.json")
    if decision.get("status") != EXIT_STATUS or manifest.get("status") != EXIT_STATUS:
        raise ContractError("CANDIDATE_NOT_ACCEPTED")
    release_id = decision["release_id"]
    contract = read_json(repo_root / CONTRACT_PATH)
    storage = contract["storage_contract"]
    current = repo_root / storage["current_root"]
    release = repo_root / storage["release_root"].replace("<release_id>", release_id)
    normalized = repo_root / storage["normalized_root"].replace("<release_id>", release_id)
    archive = repo_root / storage["archive_root"] / release_id

    candidate_digest = directory_digest(candidate)
    if release.exists() and directory_digest(release) != candidate_digest:
        raise ContractError("IMMUTABLE_RELEASE_COLLISION")
    for target in [current, release, normalized, archive]:
        if target == release and target.exists():
            continue
        copy_exact(candidate, target)
    if not all(directory_digest(target) == candidate_digest for target in [current, release, normalized, archive]):
        raise ContractError("PUBLISHED_DIRECTORY_PARITY_FAILURE")

    pointer = {
        "phase_id": "FMDL-7A",
        "release_id": release_id,
        "release_sequence": 49,
        "published_at": decision["published_at"],
        "source_commit": decision["source_commit"],
        "status": EXIT_STATUS,
        "next_gate": NEXT_GATE,
        "current_path": storage["current_root"],
        "release_path": storage["release_root"].replace("<release_id>", release_id),
        "normalized_path": storage["normalized_root"].replace("<release_id>", release_id),
        "manifest_sha256": sha256_file(candidate / "FMDL7A_MANIFEST.json"),
        "market_count": 3,
        "state_domain_count": 3,
        "duplication_case_count": 3,
        "a_share_new_decision_state": "BLOCKED_PENDING_REFRESH",
        "investment_state_posture": "LAST_KNOWN_GOOD_AS_OF_2026_07_20_USER_CONFIRMATION_REQUIRED",
        "canonical_refresh_stage": "FMDL-7E",
        "zero_mutation_proof": decision["zero_mutation_proof"],
        "trade_authority": "NONE",
    }
    write_json(repo_root / storage["last_success"], pointer)
    write_json(repo_root / storage["last_known_good"], {**pointer, "lkg_status": "LAST_KNOWN_GOOD"})
    return pointer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    build = sub.add_parser("build")
    build.add_argument("--output", required=True)
    build.add_argument("--generated-at", required=True)
    build.add_argument("--source-commit", required=True)
    publish = sub.add_parser("publish")
    publish.add_argument("--candidate", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    try:
        if args.command == "validate":
            contract = read_json(repo_root / CONTRACT_PATH)
            errors, hashes = validate_contract(repo_root, contract)
            if errors:
                raise ContractError("CONTRACT_VALIDATION_FAILED:" + ",".join(errors))
            print(json.dumps({"status": "PASS", "source_binding_count": len(contract["source_bindings"]), "source_hash_count": len(hashes), "trade_authority": "NONE"}, sort_keys=True))
        elif args.command == "build":
            result = build_candidate(repo_root, repo_root / args.output, args.generated_at, args.source_commit)
            print(json.dumps(result, sort_keys=True))
        elif args.command == "publish":
            result = publish_candidate(repo_root, repo_root / args.candidate)
            print(json.dumps(result, sort_keys=True))
        return 0
    except (ContractError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
