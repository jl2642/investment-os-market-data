#!/usr/bin/env python3
"""FMDL-7-0 deterministic master-plan producer and publisher."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

CONTRACT_PATH = Path("config/fmdl7_0_master_plan_contract.json")
EXIT_STATUS = "FMDL7_0_MASTER_PLAN_AUTHORITATIVE_ASSET_REGISTRY_AND_ACCEPTANCE_CONTRACT_ACCEPTED"
NEXT_GATE = "FMDL-7A_CROSS_MARKET_CANONICAL_INVENTORY_AND_STATE_RECONCILIATION"
STAGE_ORDER = ["FMDL-7-0", "FMDL-7A", "FMDL-7B", "FMDL-7C", "FMDL-7D", "FMDL-7E", "FMDL-7-FINAL"]
SHARD_DOMAINS = ["AUTHORITATIVE_ASSETS", "STAGE_GATES", "AUTHORITY_AND_CANONICAL", "ACCEPTANCE_AND_BUDGET"]


class ContractError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nested_get(value: Any, dotted_path: str) -> Any:
    cursor = value
    for part in dotted_path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            raise KeyError(dotted_path)
        cursor = cursor[part]
    return cursor


def validate_contract(repo_root: Path, contract: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    records: list[dict[str, Any]] = []

    if contract.get("phase_id") != "FMDL-7-0":
        errors.append("CONTRACT_PHASE_ID")
    if contract.get("required_exit_status") != EXIT_STATUS:
        errors.append("CONTRACT_REQUIRED_EXIT_STATUS")
    if contract.get("next_gate") != NEXT_GATE:
        errors.append("CONTRACT_NEXT_GATE")
    if contract.get("trade_authority") != "NONE":
        errors.append("CONTRACT_TRADE_AUTHORITY")

    assets = contract.get("authoritative_assets", [])
    if not isinstance(assets, list) or len(assets) != 7:
        errors.append("AUTHORITATIVE_ASSET_COUNT")
        assets = []
    asset_ids = [item.get("asset_id") for item in assets if isinstance(item, dict)]
    if len(set(asset_ids)) != len(asset_ids):
        errors.append("AUTHORITATIVE_ASSET_ID_DUPLICATE")

    for item in assets:
        if not isinstance(item, dict):
            errors.append("AUTHORITATIVE_ASSET_RECORD_TYPE")
            continue
        relative_path = item.get("path")
        if not isinstance(relative_path, str):
            errors.append(f"ASSET_PATH_INVALID:{item.get('asset_id')}")
            continue
        path = repo_root / relative_path
        if not path.exists():
            errors.append(f"ASSET_MISSING:{item.get('asset_id')}:{relative_path}")
            continue
        try:
            payload = read_json(path)
        except Exception as exc:  # pragma: no cover - defensive reporting
            errors.append(f"ASSET_JSON_INVALID:{item.get('asset_id')}:{type(exc).__name__}")
            continue
        check_results = []
        for dotted_path, expected in sorted(item.get("checks", {}).items()):
            try:
                actual = nested_get(payload, dotted_path)
                passed = actual == expected
            except KeyError:
                actual = None
                passed = False
            if not passed:
                errors.append(f"ASSET_CHECK_FAILED:{item.get('asset_id')}:{dotted_path}")
            check_results.append({
                "field": dotted_path,
                "expected": expected,
                "actual": actual,
                "status": "PASS" if passed else "FAIL",
            })
        records.append({
            "asset_id": item.get("asset_id"),
            "path": relative_path,
            "authority_role": item.get("authority_role"),
            "file_sha256": sha256_file(path),
            "check_count": len(check_results),
            "checks": check_results,
            "status": "PASS" if all(row["status"] == "PASS" for row in check_results) else "FAIL",
            "trade_authority": "NONE",
        })

    stages = contract.get("stage_plan", [])
    actual_order = [item.get("stage_id") for item in stages if isinstance(item, dict)]
    if actual_order != STAGE_ORDER:
        errors.append("STAGE_ORDER")
    if len({item.get("exit_status") for item in stages if isinstance(item, dict)}) != 7:
        errors.append("STAGE_EXIT_STATUS_UNIQUENESS")

    budget = contract.get("round_budget", {})
    if budget.get("formal_rounds") != 7:
        errors.append("ROUND_BUDGET_FORMAL")
    if budget.get("targeted_repair_rounds") != 2:
        errors.append("ROUND_BUDGET_REPAIR")
    if budget.get("hard_maximum_rounds") != 9:
        errors.append("ROUND_BUDGET_HARD_MAXIMUM")
    prohibited = set(budget.get("prohibited_expansion_patterns", []))
    if not {"FMDL-7F", "FMDL-7G", "FMDL-7X1", "FMDL-7X2"}.issubset(prohibited):
        errors.append("ROUND_BUDGET_PROHIBITED_EXPANSION")

    scope = contract.get("scope", {})
    forbidden_true = [
        "new_market_data_refresh_authorized",
        "research_workflow_execution_authorized",
        "candidate_pool_mutation_authorized",
        "simulation_book_mutation_authorized",
        "real_account_mutation_authorized",
        "rule_mutation_authorized",
        "brokerage_or_order_authorized",
    ]
    for field in forbidden_true:
        if scope.get(field) is not False:
            errors.append(f"SCOPE_NOT_FAIL_CLOSED:{field}")

    gates = contract.get("acceptance_gates", {})
    expected_gates = {
        "authoritative_asset_count": 7,
        "stage_count": 7,
        "formal_round_count": 7,
        "repair_round_count": 2,
        "hard_maximum_round_count": 9,
        "logical_shard_domain_count": 4,
        "bucket_count": 64,
        "logical_shard_count": 256,
        "candidate_pool_mutations": 0,
        "simulation_book_mutations": 0,
        "real_account_mutations": 0,
        "rule_mutations": 0,
        "orders": 0,
    }
    for field, expected in expected_gates.items():
        if gates.get(field) != expected:
            errors.append(f"ACCEPTANCE_GATE:{field}")

    refresh = contract.get("canonical_refresh_plan", {})
    if refresh.get("refresh_stage") != "FMDL-7E":
        errors.append("CANONICAL_REFRESH_STAGE")
    if refresh.get("premature_repack_authorized") is not False:
        errors.append("CANONICAL_PREMATURE_REPACK")

    storage = contract.get("storage_contract", {})
    if storage.get("release_sequence") != 48:
        errors.append("STORAGE_RELEASE_SEQUENCE")

    return sorted(set(errors)), records


def build_gate_matrix(asset_records: list[dict[str, Any]], contract: dict[str, Any]) -> list[dict[str, Any]]:
    checks = [
        ("SEVEN_AUTHORITATIVE_ASSETS_BOUND", len(asset_records) == 7 and all(row["status"] == "PASS" for row in asset_records)),
        ("FMDL1_THROUGH_FMDL6_SEQUENCE_REGISTERED", [row["asset_id"] for row in asset_records] == [item["asset_id"] for item in contract["authoritative_assets"]]),
        ("SEVEN_FORMAL_STAGES_FROZEN", len(contract["stage_plan"]) == 7),
        ("TWO_REPAIR_ROUNDS_MAXIMUM", contract["round_budget"]["targeted_repair_rounds"] == 2),
        ("NINE_TOTAL_ROUNDS_HARD_CAP", contract["round_budget"]["hard_maximum_rounds"] == 9),
        ("UNBOUNDED_PHASE_EXPANSION_PROHIBITED", "UNBOUNDED_SUBPHASE_CREATION" in contract["round_budget"]["prohibited_expansion_patterns"]),
        ("GITHUB_AND_FILE_LIBRARY_AUTHORITY_SEPARATED", set(contract["authority_registry"]) == {"github", "file_library", "investment_os_release8", "conversation_memory"}),
        ("CANONICAL_REFRESH_DEFERRED_TO_FMDL7E", contract["canonical_refresh_plan"]["refresh_stage"] == "FMDL-7E"),
        ("NO_PREMATURE_CANONICAL_REPACK", contract["canonical_refresh_plan"]["premature_repack_authorized"] is False),
        ("ZERO_INVESTMENT_STATE_MUTATION", all(contract["acceptance_gates"][field] == 0 for field in ["candidate_pool_mutations", "simulation_book_mutations", "real_account_mutations", "rule_mutations", "orders"])),
        ("TRADE_AUTHORITY_NONE", contract["trade_authority"] == "NONE"),
        ("ONLY_FMDL7A_NEXT_GATE_OPEN", contract["next_gate"] == NEXT_GATE),
    ]
    return [
        {
            "gate_order": index,
            "gate_code": code,
            "gate_status": "PASS" if passed else "FAIL",
            "trade_authority": "NONE",
        }
        for index, (code, passed) in enumerate(checks, start=1)
    ]


def build_candidate(repo_root: Path, output_dir: Path, generated_at: str, source_commit: str) -> dict[str, Any]:
    contract_path = repo_root / CONTRACT_PATH
    contract = read_json(contract_path)
    errors, asset_records = validate_contract(repo_root, contract)
    if errors:
        raise ContractError("CONTRACT_VALIDATION_FAILED:" + ",".join(errors))

    basis = {
        "contract_sha256": sha256_file(contract_path),
        "asset_hashes": {row["asset_id"]: row["file_sha256"] for row in asset_records},
        "source_commit": source_commit,
        "as_of_date": contract["as_of_date"],
    }
    release_digest = sha256_bytes(canonical_bytes(basis))
    release_id = f"FMDL7_0_{contract['as_of_date'].replace('-', '')}_{release_digest[:12]}"

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    gate_matrix = build_gate_matrix(asset_records, contract)
    gate_errors = [row["gate_code"] for row in gate_matrix if row["gate_status"] != "PASS"]
    if gate_errors:
        raise ContractError("ACCEPTANCE_GATE_FAILED:" + ",".join(gate_errors))

    shard_registry = [
        {
            "domain": domain,
            "bucket": bucket,
            "logical_shard_id": f"FMDL7ZERO-{domain}-{bucket:02d}",
            "state": "CONTRACT_FROZEN_NO_RUNTIME_EXECUTION",
            "trade_authority": "NONE",
        }
        for domain in SHARD_DOMAINS
        for bucket in range(64)
    ]

    write_json(output_dir / "FMDL7_0_AUTHORITATIVE_ASSET_REGISTRY.json", {
        "phase_id": "FMDL-7-0",
        "release_id": release_id,
        "asset_count": len(asset_records),
        "assets": asset_records,
        "registry_status": "PASS",
        "trade_authority": "NONE",
    })
    write_json(output_dir / "FMDL7_0_STAGE_PLAN.json", {
        "phase_id": "FMDL-7-0",
        "release_id": release_id,
        "stage_count": len(contract["stage_plan"]),
        "stages": contract["stage_plan"],
        "next_gate": NEXT_GATE,
        "trade_authority": "NONE",
    })
    write_json(output_dir / "FMDL7_0_AUTHORITY_REGISTRY.json", {
        "phase_id": "FMDL-7-0",
        "release_id": release_id,
        "authority_registry": contract["authority_registry"],
        "conversation_memory_authoritative": False,
        "trade_authority": "NONE",
    })
    write_json(output_dir / "FMDL7_0_CANONICAL_REFRESH_PLAN.json", {
        "phase_id": "FMDL-7-0",
        "release_id": release_id,
        **contract["canonical_refresh_plan"],
        "trade_authority": "NONE",
    })
    write_json(output_dir / "FMDL7_0_ACCEPTANCE_GATE_MATRIX.json", {
        "phase_id": "FMDL-7-0",
        "release_id": release_id,
        "gate_count": len(gate_matrix),
        "pass_count": sum(row["gate_status"] == "PASS" for row in gate_matrix),
        "gates": gate_matrix,
        "trade_authority": "NONE",
    })
    write_json(output_dir / "FMDL7_0_EXECUTION_AND_REPAIR_BUDGET.json", {
        "phase_id": "FMDL-7-0",
        "release_id": release_id,
        **contract["round_budget"],
        "budget_status": "FROZEN",
        "trade_authority": "NONE",
    })
    write_json(output_dir / "FMDL7_0_LOGICAL_SHARD_REGISTRY.json", {
        "phase_id": "FMDL-7-0",
        "release_id": release_id,
        "domain_count": 4,
        "bucket_count": 64,
        "logical_shard_count": len(shard_registry),
        "logical_shards": shard_registry,
        "trade_authority": "NONE",
    })

    quality_report = {
        "phase_id": "FMDL-7-0",
        "release_id": release_id,
        "quality_status": "PASS",
        "contract_error_count": 0,
        "authoritative_asset_count": len(asset_records),
        "authoritative_asset_pass_count": sum(row["status"] == "PASS" for row in asset_records),
        "stage_count": len(contract["stage_plan"]),
        "formal_round_count": contract["round_budget"]["formal_rounds"],
        "targeted_repair_round_count": contract["round_budget"]["targeted_repair_rounds"],
        "hard_maximum_round_count": contract["round_budget"]["hard_maximum_rounds"],
        "acceptance_gate_count": len(gate_matrix),
        "acceptance_gate_pass_count": len(gate_matrix),
        "logical_shard_count": len(shard_registry),
        "candidate_pool_mutations": 0,
        "simulation_book_mutations": 0,
        "real_account_mutations": 0,
        "rule_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    write_json(output_dir / "FMDL7_0_QUALITY_REPORT.json", quality_report)

    decision = {
        "phase_id": "FMDL-7-0",
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "generated_at": generated_at,
        "source_commit": source_commit,
        "status": EXIT_STATUS,
        "decision": "ACCEPT_AND_FREEZE_FMDL7_MASTER_PLAN_ASSET_REGISTRY_STAGE_GATES_AND_NINE_ROUND_HARD_CAP",
        "next_gate": NEXT_GATE,
        "canonical_refresh_stage": "FMDL-7E",
        "zero_mutation_proof": {
            "candidate_pool_mutations": 0,
            "simulation_book_mutations": 0,
            "real_account_mutations": 0,
            "rule_mutations": 0,
            "orders": 0,
        },
        "trade_authority": "NONE",
    }
    write_json(output_dir / "FMDL7_0_DECISION.json", decision)

    manifest_entries = []
    for path in sorted(output_dir.glob("*.json")):
        manifest_entries.append({
            "path": path.name,
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        })
    manifest = {
        "phase_id": "FMDL-7-0",
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "generated_at": generated_at,
        "source_commit": source_commit,
        "contract_path": CONTRACT_PATH.as_posix(),
        "contract_sha256": basis["contract_sha256"],
        "file_count": len(manifest_entries),
        "files": manifest_entries,
        "status": EXIT_STATUS,
        "trade_authority": "NONE",
    }
    write_json(output_dir / "FMDL7_0_MANIFEST.json", manifest)
    return decision


def verify_manifest(candidate_dir: Path) -> dict[str, Any]:
    manifest_path = candidate_dir / "FMDL7_0_MANIFEST.json"
    manifest = read_json(manifest_path)
    errors = []
    for item in manifest.get("files", []):
        path = candidate_dir / item["path"]
        if not path.exists():
            errors.append(f"MISSING:{item['path']}")
            continue
        if sha256_file(path) != item["sha256"]:
            errors.append(f"HASH:{item['path']}")
        if path.stat().st_size != item["size_bytes"]:
            errors.append(f"SIZE:{item['path']}")
    if errors:
        raise ContractError("MANIFEST_VALIDATION_FAILED:" + ",".join(errors))
    return manifest


def publish(repo_root: Path, candidate_dir: Path) -> dict[str, Any]:
    manifest = verify_manifest(candidate_dir)
    decision = read_json(candidate_dir / "FMDL7_0_DECISION.json")
    quality = read_json(candidate_dir / "FMDL7_0_QUALITY_REPORT.json")
    if decision.get("status") != EXIT_STATUS or quality.get("quality_status") != "PASS":
        raise ContractError("CANDIDATE_NOT_ACCEPTED")

    contract = read_json(repo_root / CONTRACT_PATH)
    release_id = decision["release_id"]
    current_path = repo_root / contract["storage_contract"]["current_root"]
    release_path = repo_root / contract["storage_contract"]["release_root"].replace("<release_id>", release_id)
    normalized_path = repo_root / contract["storage_contract"]["normalized_root"].replace("<release_id>", release_id)
    archive_root = repo_root / contract["storage_contract"]["archive_root"]

    if release_path.exists():
        existing_manifest = release_path / "FMDL7_0_MANIFEST.json"
        if not existing_manifest.exists() or sha256_file(existing_manifest) != sha256_file(candidate_dir / "FMDL7_0_MANIFEST.json"):
            raise ContractError("IMMUTABLE_RELEASE_COLLISION")
    else:
        release_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(candidate_dir, release_path)

    if current_path.exists():
        old_decision_path = current_path / "FMDL7_0_DECISION.json"
        old_release_id = "UNKNOWN"
        if old_decision_path.exists():
            old_release_id = read_json(old_decision_path).get("release_id", "UNKNOWN")
        archive_path = archive_root / old_release_id
        if not archive_path.exists():
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(current_path, archive_path)
        shutil.rmtree(current_path)
    current_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(candidate_dir, current_path)

    if normalized_path.exists():
        shutil.rmtree(normalized_path)
    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(candidate_dir, normalized_path)

    manifest_sha = sha256_file(candidate_dir / "FMDL7_0_MANIFEST.json")
    pointer = {
        "phase_id": "FMDL-7-0",
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "status": EXIT_STATUS,
        "published_at": decision["generated_at"],
        "source_commit": decision["source_commit"],
        "current_path": contract["storage_contract"]["current_root"],
        "release_path": contract["storage_contract"]["release_root"].replace("<release_id>", release_id),
        "normalized_path": contract["storage_contract"]["normalized_root"].replace("<release_id>", release_id),
        "manifest_sha256": manifest_sha,
        "authoritative_asset_count": 7,
        "formal_round_count": 7,
        "targeted_repair_round_count": 2,
        "hard_maximum_round_count": 9,
        "canonical_refresh_stage": "FMDL-7E",
        "next_gate": NEXT_GATE,
        "zero_mutation_proof": decision["zero_mutation_proof"],
        "trade_authority": "NONE",
    }
    last_success = repo_root / contract["storage_contract"]["last_success"]
    lkg = repo_root / contract["storage_contract"]["last_known_good"]
    write_json(last_success, pointer)
    write_json(lkg, {**pointer, "lkg_status": "LAST_KNOWN_GOOD"})
    return pointer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--output", required=True)
    build_parser.add_argument("--generated-at", required=True)
    build_parser.add_argument("--source-commit", required=True)
    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument("--candidate", required=True)

    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    try:
        if args.command == "validate":
            contract = read_json(repo_root / CONTRACT_PATH)
            errors, records = validate_contract(repo_root, contract)
            if errors:
                raise ContractError("CONTRACT_VALIDATION_FAILED:" + ",".join(errors))
            print(json.dumps({"status": "PASS", "asset_count": len(records)}, sort_keys=True))
        elif args.command == "build":
            decision = build_candidate(repo_root, Path(args.output).resolve(), args.generated_at, args.source_commit)
            print(json.dumps(decision, sort_keys=True))
        elif args.command == "publish":
            pointer = publish(repo_root, Path(args.candidate).resolve())
            print(json.dumps(pointer, sort_keys=True))
        return 0
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
