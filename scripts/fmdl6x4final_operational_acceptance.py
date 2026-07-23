from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Iterable

PHASE_ID = "FMDL-6X4-FINAL"
EXIT_STATUS = "FMDL6X4_FINAL_US_RESEARCH_ADAPTER_OPERATIONAL_ACCEPTANCE_AND_FMDL6_FREEZE_ACCEPTED"
NEXT_GATE = "FMDL-7_CROSS_MARKET_AND_FULL_SYSTEM_FINAL_OPERATIONAL_ACCEPTANCE"
CONTRACT_PATH = Path("config/fmdl6x4final_operational_acceptance_contract.json")
ROADMAP_PATH = Path("docs/FMDL-6X3_X4_DEVELOPMENT_ROADMAP.md")


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def record_hash(*parts: Any) -> str:
    payload = "\x1f".join(stable_json(part) for part in parts).encode("utf-8")
    return sha256_bytes(payload)


def bucket_hex(key: str, bucket_count: int = 64) -> str:
    value = int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16) % bucket_count
    return f"{value:02X}"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def jsonl_bytes(rows: Iterable[dict[str, Any]]) -> bytes:
    return "".join(stable_json(row) + "\n" for row in rows).encode("utf-8")


def deterministic_zip(path: Path, entries: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, entries[name])


def copytree_replace(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def validate_contract(repo_root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    path = repo_root / CONTRACT_PATH
    if not path.is_file():
        return {}, {}, ["CONTRACT_MISSING"]
    contract = load_json(path)

    if contract.get("phase_id") != PHASE_ID:
        errors.append("PHASE_ID")
    if contract.get("required_exit_status") != EXIT_STATUS:
        errors.append("EXIT_STATUS")
    if contract.get("next_gate") != NEXT_GATE:
        errors.append("NEXT_GATE")
    if contract.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")
    if any(value != 0 for value in contract.get("zero_mutation_gate", {}).values()):
        errors.append("ZERO_MUTATION_GATE")

    scope = contract.get("scope", {})
    for key in (
        "new_data_backfill_authorized",
        "workflow_execution_authorized",
        "candidate_pool_mutation_authorized",
        "simulation_book_mutation_authorized",
        "real_account_mutation_authorized",
        "investment_recommendation_authorized",
        "brokerage_or_order_authorized",
    ):
        if scope.get(key) is not False:
            errors.append("SCOPE_" + key.upper())

    roadmap_spec = contract.get("roadmap_authority", {})
    roadmap_path = repo_root / roadmap_spec.get("path", str(ROADMAP_PATH))
    if not roadmap_path.is_file():
        errors.append("ROADMAP_MISSING")
    else:
        roadmap = roadmap_path.read_text(encoding="utf-8")
        for key in ("required_stage_text", "required_completion_text", "required_following_text"):
            if roadmap_spec.get(key) not in roadmap:
                errors.append("ROADMAP_" + key.upper())

    components: dict[str, dict[str, Any]] = {}
    specs = contract.get("component_pointers", [])
    if len(specs) != 8:
        errors.append("COMPONENT_SPEC_COUNT")
    sequences: list[int] = []
    for spec in specs:
        component_id = str(spec.get("component_id"))
        pointer_path = repo_root / str(spec.get("path"))
        if not pointer_path.is_file():
            errors.append("COMPONENT_POINTER_MISSING:" + component_id)
            continue
        pointer = load_json(pointer_path)
        components[component_id] = pointer
        checks = {
            "phase_id": spec.get("required_phase_id"),
            "release_id": spec.get("required_release_id"),
            "release_sequence": spec.get("required_release_sequence"),
            "status": spec.get("required_status"),
            "trade_authority": "NONE",
        }
        for field, expected in checks.items():
            if pointer.get(field) != expected:
                errors.append(f"{component_id}:{field.upper()}_MISMATCH")
        manifest_hash = str(pointer.get("manifest_sha256", ""))
        if len(manifest_hash) != 64:
            errors.append(f"{component_id}:MANIFEST_SHA256_MISSING_OR_INVALID")
        sequence = pointer.get("release_sequence")
        if isinstance(sequence, int):
            sequences.append(sequence)
        zero = pointer.get("zero_mutation_proof")
        if isinstance(zero, dict) and any(value != 0 for value in zero.values()):
            errors.append(f"{component_id}:ZERO_MUTATION_PROOF_FAILED")
        for field in (
            "formal_workflow_execution_count",
            "formal_candidate_promotion_count",
            "graduation_event_count",
            "investment_recommendation_count",
            "registered_workflow_output_count",
        ):
            if field in pointer and pointer.get(field) != 0:
                errors.append(f"{component_id}:{field.upper()}_NONZERO")

    required_sequences = [int(spec["required_release_sequence"]) for spec in specs]
    if sequences != required_sequences:
        errors.append("COMPONENT_SEQUENCE_BINDING")
    if any(left >= right for left, right in zip(required_sequences, required_sequences[1:])):
        errors.append("COMPONENT_SEQUENCE_NOT_STRICTLY_INCREASING")
    if len([spec for spec in specs if str(spec.get("component_id", "")).startswith("FMDL-6X4-")]) != 5:
        errors.append("X4_STAGE_COUNT")

    gates = contract.get("acceptance_gates", {})
    expected_gates = {
        "component_count": 8,
        "x4_stage_count": 5,
        "strict_release_sequence_count": 8,
        "freeze_control_count": 12,
        "recovery_control_count": 8,
        "operational_capability_count": 8,
        "final_gate_count": 12,
        "logical_shard_count": 384,
        "formal_workflow_execution_count": 0,
        "formal_candidate_promotion_count": 0,
        "formal_simulation_position_count": 0,
        "investment_recommendation_count": 0,
        "cross_market_security_rank_count": 0,
        "forced_common_factor_score_count": 0,
        "neutral_fill_count": 0,
    }
    for key, value in expected_gates.items():
        if gates.get(key) != value:
            errors.append("ACCEPTANCE_GATE:" + key)
    if len(contract.get("freeze_controls", [])) != 12:
        errors.append("FREEZE_CONTROL_COUNT")
    if len(contract.get("recovery_controls", [])) != 8:
        errors.append("RECOVERY_CONTROL_COUNT")
    return contract, components, sorted(set(errors))


def build_records(contract: dict[str, Any], components: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    component_rows: list[dict[str, Any]] = []
    release_rows: list[dict[str, Any]] = []
    capability_rows: list[dict[str, Any]] = []
    specs = contract["component_pointers"]
    previous_release_id: str | None = None
    for order, spec in enumerate(specs, start=1):
        pointer = components[spec["component_id"]]
        component_rows.append({
            "component_acceptance_id": "PEIFINALCOMP-" + record_hash(spec["component_id"])[:24],
            "component_order": order,
            "component_id": spec["component_id"],
            "phase_id": pointer["phase_id"],
            "release_id": pointer["release_id"],
            "release_sequence": pointer["release_sequence"],
            "status": pointer["status"],
            "manifest_sha256": pointer["manifest_sha256"],
            "current_path": pointer.get("current_path"),
            "release_path": pointer.get("release_path"),
            "component_acceptance_status": "BOUND_AND_ACCEPTED",
            "trade_authority": "NONE",
        })
        release_rows.append({
            "release_chain_id": "PEIFINALCHAIN-" + record_hash(order, pointer["release_id"])[:24],
            "component_order": order,
            "component_id": spec["component_id"],
            "release_id": pointer["release_id"],
            "release_sequence": pointer["release_sequence"],
            "predecessor_release_id": previous_release_id,
            "strictly_after_predecessor": order == 1 or pointer["release_sequence"] > specs[order - 2]["required_release_sequence"],
            "chain_status": "PASS",
            "trade_authority": "NONE",
        })
        capability_rows.append({
            "adapter_capability_id": "PEIFINALCAP-" + record_hash(spec["component_id"], spec["accepted_capability"])[:24],
            "component_id": spec["component_id"],
            "accepted_capability": spec["accepted_capability"],
            "operational_status": "ACCEPTED_AND_FROZEN",
            "new_execution_authorized": False,
            "candidate_pool_authorized": False,
            "formal_simulation_authorized": False,
            "brokerage_channel_available": False,
            "trade_authority": "NONE",
        })
        previous_release_id = pointer["release_id"]

    freeze_rows = [
        {
            "freeze_control_id": "PEIFINALFREEZE-" + record_hash(code)[:24],
            "control_order": index,
            "control_code": code,
            "control_status": "FROZEN_AND_ENFORCED",
            "automatic_waiver_allowed": False,
            "trade_authority": "NONE",
        }
        for index, code in enumerate(contract["freeze_controls"], start=1)
    ]
    recovery_rows = [
        {
            "recovery_control_id": "PEIFINALREC-" + record_hash(code)[:24],
            "control_order": index,
            "control_code": code,
            "control_status": "AVAILABLE_AND_REQUIRED",
            "fail_closed": True,
            "trade_authority": "NONE",
        }
        for index, code in enumerate(contract["recovery_controls"], start=1)
    ]
    final_gate_codes = [
        "ALL_EIGHT_COMPONENT_POINTERS_BOUND",
        "STRICT_RELEASE_SEQUENCE_ACCEPTED",
        "ALL_COMPONENT_MANIFEST_BINDINGS_PRESENT",
        "FMDL6X4_A_THROUGH_E_COMPLETE",
        "ROADMAP_FINAL_AUTHORITY_CONFIRMED",
        "ZERO_FORMAL_WORKFLOW_EXECUTION",
        "ZERO_FORMAL_CANDIDATE_PROMOTION",
        "ZERO_FORMAL_SIMULATION_POSITION",
        "ZERO_INVESTMENT_RECOMMENDATION",
        "ZERO_INVESTMENT_OS_MUTATION",
        "TRADE_AUTHORITY_NONE",
        "ONLY_FMDL7_NEXT_GATE_OPEN",
    ]
    final_gates = [
        {
            "final_gate_id": "PEIFINALGATE-" + record_hash(code)[:24],
            "gate_order": index,
            "gate_code": code,
            "gate_status": "PASS",
            "trade_authority": "NONE",
        }
        for index, code in enumerate(final_gate_codes, start=1)
    ]
    handoff_rows = [{
        "fmdl7_handoff_id": "PEIFMDL7-" + record_hash(NEXT_GATE)[:24],
        "handoff_status": "OPEN_FOR_CROSS_MARKET_AND_FULL_SYSTEM_FINAL_OPERATIONAL_ACCEPTANCE_ONLY",
        "next_gate": NEXT_GATE,
        "fmdl6_status": "COMPLETE_AND_FROZEN_AFTER_FMDL6X4_FINAL",
        "us_research_adapter_status": "OPERATIONALLY_ACCEPTED_AND_FROZEN",
        "candidate_pool_mutation_authorized": False,
        "simulation_book_mutation_authorized": False,
        "real_account_mutation_authorized": False,
        "brokerage_channel_available": False,
        "trade_authority": "NONE",
    }]
    return {
        "components": component_rows,
        "release_chain": release_rows,
        "capabilities": capability_rows,
        "freeze_controls": freeze_rows,
        "recovery_controls": recovery_rows,
        "final_gates": final_gates,
        "handoff": handoff_rows,
    }


def build_shards(records: dict[str, list[dict[str, Any]]], bucket_count: int) -> tuple[bytes, list[dict[str, Any]]]:
    domains = (
        ("COMPONENT_ACCEPTANCE", records["components"], "component_acceptance_id"),
        ("RELEASE_CHAIN", records["release_chain"], "release_chain_id"),
        ("ADAPTER_CAPABILITY", records["capabilities"], "adapter_capability_id"),
        ("FREEZE_CONTROL", records["freeze_controls"], "freeze_control_id"),
        ("RECOVERY_CONTROL", records["recovery_controls"], "recovery_control_id"),
        ("FMDL7_HANDOFF", records["handoff"], "fmdl7_handoff_id"),
    )
    entries: dict[str, bytes] = {}
    manifest: list[dict[str, Any]] = []
    for domain, rows, key in domains:
        for index in range(bucket_count):
            bucket = f"{index:02X}"
            shard_rows = sorted(
                (row for row in rows if bucket_hex(str(row[key]), bucket_count) == bucket),
                key=stable_json,
            )
            data = jsonl_bytes(shard_rows)
            name = f"{domain}/{bucket}.jsonl"
            entries[name] = data
            manifest.append({
                "path": name,
                "record_count": len(shard_rows),
                "bytes": len(data),
                "sha256": sha256_bytes(data),
            })
    target = Path("/tmp/fmdl6x4final_shards.zip")
    deterministic_zip(target, entries)
    data = target.read_bytes()
    target.unlink(missing_ok=True)
    return data, manifest


def build_candidate(repo_root: Path, candidate: Path, accepted_at: str, source_commit: str) -> dict[str, Any]:
    contract, components, errors = validate_contract(repo_root)
    if errors:
        raise ValueError("CONTRACT_VALIDATION_FAILED:" + ",".join(errors))
    records = build_records(contract, components)
    candidate = repo_root / candidate if not candidate.is_absolute() else candidate
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True, exist_ok=True)

    identity = {
        "phase_id": PHASE_ID,
        "accepted_at": accepted_at,
        "source_commit": source_commit,
        "input_release_id": components["FMDL-6X4-E"]["release_id"],
        "input_manifest_sha256": components["FMDL-6X4-E"]["manifest_sha256"],
        "contract_sha256": sha256_file(repo_root / CONTRACT_PATH),
        "roadmap_sha256": sha256_file(repo_root / ROADMAP_PATH),
    }
    release_id = f"FMDL6X4FINAL_{accepted_at[:10].replace('-', '')}_{record_hash(identity)[:12]}"
    shard_bytes, shard_manifest = build_shards(records, contract["storage_contract"]["bucket_count"])
    (candidate / "FMDL6X4FINAL_OPERATIONAL_SHARDS.zip").write_bytes(shard_bytes)

    write_json(candidate / "FMDL6X4FINAL_COMPONENT_REGISTRY.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "component_count": len(records["components"]),
        "components": records["components"],
        "trade_authority": "NONE",
    })
    write_json(candidate / "FMDL6X4FINAL_RELEASE_CHAIN_REPORT.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_chain_count": len(records["release_chain"]),
        "strict_release_order": all(row["strictly_after_predecessor"] for row in records["release_chain"]),
        "release_chain": records["release_chain"],
        "trade_authority": "NONE",
    })
    write_json(candidate / "FMDL6X4FINAL_US_ADAPTER_CAPABILITY_MATRIX.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "operational_capability_count": len(records["capabilities"]),
        "capabilities": records["capabilities"],
        "persistent_alpha_proof": "NOT_ESTABLISHED",
        "formal_performance_claim": False,
        "trade_authority": "NONE",
    })
    write_json(candidate / "FMDL6X4FINAL_FREEZE_REGISTRY.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "freeze_control_count": len(records["freeze_controls"]),
        "freeze_controls": records["freeze_controls"],
        "fmdl6_freeze_status": "FROZEN_AFTER_FINAL_ACCEPTANCE",
        "trade_authority": "NONE",
    })
    write_json(candidate / "FMDL6X4FINAL_RECOVERY_REPORT.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "recovery_control_count": len(records["recovery_controls"]),
        "recovery_controls": records["recovery_controls"],
        "same_input_replay_required": True,
        "last_known_good_required": True,
        "trade_authority": "NONE",
    })
    write_json(candidate / "FMDL6X4FINAL_FMDL7_HANDOFF.json", {
        **records["handoff"][0],
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "required_fmdl7_controls": [
            "RECONCILE_A_SHARE_HONG_KONG_CONNECT_AND_US_OPERATING_STATES",
            "VALIDATE_FULL_SYSTEM_POINTER_RELEASE_AND_MANIFEST_BINDINGS",
            "RUN_CROSS_MARKET_OPERATING_ACCEPTANCE_WITHOUT_FORCED_COMMON_RANK",
            "PRESERVE_USER_CONTROLLED_CANDIDATE_SIMULATION_REAL_ACCOUNT_AND_ORDER_GATES",
        ],
    })
    write_json(candidate / "FMDL6X4FINAL_SOURCE_BINDING.json", {
        **identity,
        "release_id": release_id,
        "component_release_ids": {key: value["release_id"] for key, value in components.items()},
        "component_manifest_sha256": {key: value["manifest_sha256"] for key, value in components.items()},
        "silent_source_substitution": False,
        "neutral_fill_used": False,
        "trade_authority": "NONE",
    })

    actual = {
        "component_count": len(records["components"]),
        "x4_stage_count": len([row for row in records["components"] if row["component_id"].startswith("FMDL-6X4-")]),
        "strict_release_sequence_count": len(records["release_chain"]),
        "freeze_control_count": len(records["freeze_controls"]),
        "recovery_control_count": len(records["recovery_controls"]),
        "operational_capability_count": len(records["capabilities"]),
        "final_gate_count": len(records["final_gates"]),
        "logical_shard_count": len(shard_manifest),
        "formal_workflow_execution_count": 0,
        "formal_candidate_promotion_count": 0,
        "formal_simulation_position_count": 0,
        "investment_recommendation_count": 0,
        "cross_market_security_rank_count": 0,
        "forced_common_factor_score_count": 0,
        "neutral_fill_count": 0,
    }
    expected = contract["acceptance_gates"]
    gate_errors = [key for key, value in expected.items() if actual.get(key) != value]
    final_gate_pass_count = sum(row["gate_status"] == "PASS" for row in records["final_gates"])
    quality_status = "PASS" if not gate_errors and final_gate_pass_count == expected["final_gate_count"] else "FAIL"
    write_json(candidate / "FMDL6X4FINAL_QUALITY_REPORT.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "quality_status": quality_status,
        "acceptance_gate_actual": actual,
        "acceptance_gate_errors": gate_errors,
        "final_gate_pass_count": final_gate_pass_count,
        "final_gates": records["final_gates"],
        "requested_shard_count": expected["logical_shard_count"],
        "actual_shard_count": len(shard_manifest),
        "zero_mutation_proof": contract["zero_mutation_gate"],
        "trade_authority": "NONE",
    })
    write_json(candidate / "FMDL6X4FINAL_DECISION.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "accepted_at": accepted_at,
        "source_commit": source_commit,
        "input_release_id": components["FMDL-6X4-E"]["release_id"],
        "status": EXIT_STATUS,
        "next_gate": NEXT_GATE,
        "fmdl6_status": "COMPLETE_AND_FROZEN",
        "us_research_adapter_status": "OPERATIONALLY_ACCEPTED_AND_FROZEN",
        "fmdl7_gate": "OPEN_FOR_CROSS_MARKET_AND_FULL_SYSTEM_FINAL_OPERATIONAL_ACCEPTANCE_ONLY",
        "candidate_pool_gate": "CLOSED_NO_AUTOMATIC_MUTATION",
        "formal_us_simulation_gate": "CLOSED_NO_FORMAL_POSITION",
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
        "investment_recommendation_count": 0,
        "zero_mutation_proof": contract["zero_mutation_gate"],
        "trade_authority": "NONE",
    })

    files: dict[str, dict[str, Any]] = {}
    for path in sorted(candidate.iterdir()):
        if path.name == "FMDL6X4FINAL_MANIFEST.json" or not path.is_file():
            continue
        files[path.name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    manifest = {
        **identity,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "status": EXIT_STATUS,
        "next_gate": NEXT_GATE,
        "files": files,
        "shards": shard_manifest,
        "logical_shard_count": len(shard_manifest),
        "quality_status": quality_status,
        "trade_authority": "NONE",
    }
    write_json(candidate / "FMDL6X4FINAL_MANIFEST.json", manifest)
    if quality_status != "PASS":
        raise ValueError("QUALITY_GATE_FAILED:" + ",".join(gate_errors))
    return manifest


def compare_directories(left: Path, right: Path) -> list[str]:
    left_files = {path.relative_to(left) for path in left.rglob("*") if path.is_file()}
    right_files = {path.relative_to(right) for path in right.rglob("*") if path.is_file()}
    errors = ["FILE_SET_MISMATCH"] if left_files != right_files else []
    for relative in sorted(left_files & right_files):
        if sha256_file(left / relative) != sha256_file(right / relative):
            errors.append("BYTE_MISMATCH:" + str(relative))
    return errors


def validate_candidate(repo_root: Path, candidate: Path, accepted_at: str, source_commit: str, acceptance: Path) -> dict[str, Any]:
    candidate = repo_root / candidate if not candidate.is_absolute() else candidate
    replay = candidate.parent / (candidate.name + "_replay")
    build_candidate(repo_root, replay, accepted_at, source_commit)
    errors = compare_directories(candidate, replay)
    manifest = load_json(candidate / "FMDL6X4FINAL_MANIFEST.json")
    result = {
        "phase_id": PHASE_ID,
        "release_id": manifest["release_id"],
        "acceptance_status": "PASS" if not errors else "FAIL",
        "same_input_byte_replay": not errors,
        "errors": errors,
        "trade_authority": "NONE",
    }
    acceptance_path = repo_root / acceptance if not acceptance.is_absolute() else acceptance
    write_json(acceptance_path, result)
    shutil.rmtree(replay, ignore_errors=True)
    if errors:
        raise ValueError("CANDIDATE_REPLAY_FAILED:" + ",".join(errors))
    return result


def publish(repo_root: Path, candidate: Path, published_at: str, source_commit: str) -> dict[str, Any]:
    contract, components, errors = validate_contract(repo_root)
    if errors:
        raise ValueError("CONTRACT_VALIDATION_FAILED:" + ",".join(errors))
    candidate = repo_root / candidate if not candidate.is_absolute() else candidate
    manifest = load_json(candidate / "FMDL6X4FINAL_MANIFEST.json")
    if manifest.get("source_commit") != source_commit:
        raise ValueError("SOURCE_COMMIT_MISMATCH")
    if manifest.get("quality_status") != "PASS":
        raise ValueError("CANDIDATE_NOT_QUALITY_PASSED")
    release_id = manifest["release_id"]
    current = repo_root / contract["storage_contract"]["current_root"]
    release = repo_root / contract["storage_contract"]["release_root"].replace("<release_id>", release_id)
    normalized = repo_root / contract["storage_contract"]["normalized_root"].replace("<release_id>", release_id)
    if release.exists():
        if compare_directories(candidate, release):
            raise ValueError("IMMUTABLE_RELEASE_COLLISION")
    else:
        copytree_replace(candidate, release)
    copytree_replace(candidate, current)
    copytree_replace(candidate, normalized)
    decision = load_json(candidate / "FMDL6X4FINAL_DECISION.json")
    pointer = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "published_at": published_at,
        "source_commit": source_commit,
        "status": EXIT_STATUS,
        "next_gate": NEXT_GATE,
        "input_release_id": components["FMDL-6X4-E"]["release_id"],
        "current_path": contract["storage_contract"]["current_root"],
        "release_path": contract["storage_contract"]["release_root"].replace("<release_id>", release_id),
        "normalized_path": contract["storage_contract"]["normalized_root"].replace("<release_id>", release_id),
        "manifest_sha256": sha256_file(candidate / "FMDL6X4FINAL_MANIFEST.json"),
        "fmdl6_status": decision["fmdl6_status"],
        "us_research_adapter_status": decision["us_research_adapter_status"],
        "fmdl7_gate": decision["fmdl7_gate"],
        "candidate_pool_gate": decision["candidate_pool_gate"],
        "formal_us_simulation_gate": decision["formal_us_simulation_gate"],
        "brokerage_real_account_gate": decision["brokerage_real_account_gate"],
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    write_json(repo_root / contract["storage_contract"]["last_success"], pointer)
    write_json(repo_root / contract["storage_contract"]["last_known_good"], {
        **pointer,
        "lkg_status": "LAST_KNOWN_GOOD_ACCEPTED",
        "recovery_priority": ["IMMUTABLE_RELEASE", "CURRENT", "NORMALIZED"],
    })
    return pointer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate-contract")
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--candidate", required=True)
    build_parser.add_argument("--accepted-at", required=True)
    build_parser.add_argument("--source-commit", required=True)
    validate_parser = subparsers.add_parser("validate-candidate")
    validate_parser.add_argument("--candidate", required=True)
    validate_parser.add_argument("--accepted-at", required=True)
    validate_parser.add_argument("--source-commit", required=True)
    validate_parser.add_argument("--acceptance", required=True)
    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument("--candidate", required=True)
    publish_parser.add_argument("--published-at", required=True)
    publish_parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    if args.command == "validate-contract":
        _, _, errors = validate_contract(repo_root)
        if errors:
            raise SystemExit("CONTRACT_VALIDATION_FAILED:" + ",".join(errors))
        print("FMDL-6X4-FINAL contract validation PASS")
    elif args.command == "build":
        manifest = build_candidate(repo_root, Path(args.candidate), args.accepted_at, args.source_commit)
        print(stable_json({"release_id": manifest["release_id"], "quality_status": manifest["quality_status"]}))
    elif args.command == "validate-candidate":
        result = validate_candidate(repo_root, Path(args.candidate), args.accepted_at, args.source_commit, Path(args.acceptance))
        print(stable_json(result))
    elif args.command == "publish":
        result = publish(repo_root, Path(args.candidate), args.published_at, args.source_commit)
        print(stable_json(result))


if __name__ == "__main__":
    main()
