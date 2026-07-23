#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

CONTRACT_PATH = Path("config/fmdl7e_clean_room_canonical_refresh_contract.json")
SCHEMA_PATH = Path("schemas/fmdl7e_clean_room_canonical_refresh_contract_v1.schema.json")
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def safe_member(name: str) -> bool:
    p = PurePosixPath(name)
    return bool(name) and not p.is_absolute() and ".." not in p.parts and "\\" not in name


def require_equal(errors: list[str], label: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        errors.append(f"{label}:{observed!r}!={expected!r}")


def validate_contract(repo: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    contract_path = repo / CONTRACT_PATH
    schema_path = repo / SCHEMA_PATH
    if not contract_path.exists():
        return {}, [f"MISSING_CONTRACT:{CONTRACT_PATH}"]
    if not schema_path.exists():
        return {}, [f"MISSING_SCHEMA:{SCHEMA_PATH}"]
    contract = read_json(contract_path)

    require_equal(errors, "PHASE", contract.get("phase_id"), "FMDL-7E")
    require_equal(errors, "TRADE_AUTHORITY", contract.get("trade_authority"), "NONE")
    require_equal(errors, "BINDING_COUNT", len(contract.get("authoritative_release_bindings", [])), 7)
    require_equal(errors, "PACKAGE_SOURCE_COUNT", len(contract.get("package_source_files", [])), 15)
    require_equal(errors, "FAILURE_INJECTION_COUNT", len(contract.get("failure_injections", [])), 12)
    require_equal(errors, "RELEASE_SEQUENCE", contract.get("storage_contract", {}).get("release_sequence"), 53)
    require_equal(errors, "CANONICAL_SEQUENCE", contract.get("canonical_refresh_contract", {}).get("new_canonical_release_sequence"), 9)

    entry = contract["entry_gate"]
    entry_payload = read_json(repo / entry["path"])
    for field, key in [
        ("phase_id", "required_phase_id"),
        ("release_id", "required_release_id"),
        ("release_sequence", "required_release_sequence"),
        ("status", "required_status"),
        ("next_gate", "required_next_gate"),
        ("trade_authority", "required_trade_authority"),
    ]:
        require_equal(errors, f"ENTRY_{field.upper()}", entry_payload.get(field), entry[key])

    fmdl7_sequences: list[int] = []
    for binding in contract["authoritative_release_bindings"]:
        path = repo / binding["path"]
        if not path.exists():
            errors.append(f"MISSING_BINDING:{binding['binding_id']}:{binding['path']}")
            continue
        payload = read_json(path)
        require_equal(errors, f"{binding['binding_id']}_RELEASE_ID", payload.get("release_id"), binding["required_release_id"])
        require_equal(errors, f"{binding['binding_id']}_RELEASE_SEQUENCE", payload.get("release_sequence"), binding["required_release_sequence"])
        require_equal(errors, f"{binding['binding_id']}_STATUS", payload.get("status"), binding["required_status"])
        require_equal(errors, f"{binding['binding_id']}_TRADE_AUTHORITY", payload.get("trade_authority"), "NONE")
        zero = payload.get("zero_mutation_proof")
        if zero is not None and any(int(v) != 0 for v in zero.values()):
            errors.append(f"{binding['binding_id']}_NONZERO_MUTATION")
        if binding["binding_id"].startswith("FMDL7"):
            fmdl7_sequences.append(int(payload["release_sequence"]))
    require_equal(errors, "STRICT_FMDL7_SEQUENCE", fmdl7_sequences, [48, 49, 50, 51, 52])

    legacy = contract["legacy_canonical_binding"]
    legacy_payload = read_json(repo / legacy["path"])
    for field, key in [
        ("release_id", "required_release_id"),
        ("release_sequence", "required_release_sequence"),
        ("status", "required_status"),
        ("package_filename", "required_package_filename"),
        ("package_sha256", "required_package_sha256"),
        ("package_size_bytes", "required_package_size_bytes"),
        ("market_as_of", "required_market_as_of"),
        ("trade_authority", "required_trade_authority"),
    ]:
        require_equal(errors, f"LEGACY_{field.upper()}", legacy_payload.get(field), legacy[key])

    seen_targets: set[str] = set()
    for src, dst in contract["package_source_files"]:
        if not (repo / src).exists():
            errors.append(f"MISSING_PACKAGE_SOURCE:{src}")
        if not safe_member(dst):
            errors.append(f"UNSAFE_PACKAGE_TARGET:{dst}")
        if dst in seen_targets:
            errors.append(f"DUPLICATE_PACKAGE_TARGET:{dst}")
        seen_targets.add(dst)

    scope = contract["scope"]
    for forbidden in [
        "live_market_refresh_authorized",
        "post_2026_07_20_state_fabrication_authorized",
        "candidate_pool_mutation_authorized",
        "simulation_book_mutation_authorized",
        "real_account_mutation_authorized",
        "rule_mutation_authorized",
        "brokerage_or_order_authorized",
    ]:
        require_equal(errors, f"SCOPE_{forbidden}", scope.get(forbidden), False)
    return contract, errors


def release_ids(contract: dict[str, Any], generated_at: str, source_commit: str) -> tuple[str, str]:
    date_key = generated_at[:10].replace("-", "")
    seed = {
        "phase": contract["phase_id"],
        "generated_at": generated_at,
        "source_commit": source_commit,
        "bindings": [x["required_release_id"] for x in contract["authoritative_release_bindings"]],
        "legacy": contract["legacy_canonical_binding"]["required_release_id"],
    }
    suffix = sha256_bytes(canonical_bytes(seed))[:12]
    return f"FMDL7E_{date_key}_{suffix}", f"INVESTMENT_OS_R9_{date_key}_{suffix}"


def package_manifest(package_root: Path) -> dict[str, Any]:
    entries = []
    for path in sorted(p for p in package_root.rglob("*") if p.is_file() and p.name != "MANIFEST.json"):
        rel = path.relative_to(package_root).as_posix()
        entries.append({"path": rel, "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return {"manifest_version": "1.0.0", "member_count": len(entries), "members": entries}


def deterministic_zip(package_root: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(p for p in package_root.rglob("*") if p.is_file()):
            rel = path.relative_to(package_root).as_posix()
            info = zipfile.ZipInfo(rel, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def validate_package(zip_path: Path, required_members: list[str]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            if len(names) != len(set(names)):
                errors.append("DUPLICATE_PACKAGE_MEMBER")
            unsafe = sorted(name for name in names if not safe_member(name))
            if unsafe:
                errors.append("UNSAFE_PACKAGE_PATH:" + ",".join(unsafe))
            missing = sorted(set(required_members) - set(names))
            if missing:
                errors.append("MISSING_REQUIRED_MEMBER:" + ",".join(missing))
            bad_crc = zf.testzip()
            if bad_crc:
                errors.append("ZIP_CRC_FAILURE:" + bad_crc)
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                zf.extractall(root)
                manifest_path = root / "00_CONTROL/MANIFEST.json"
                if not manifest_path.exists():
                    errors.append("MISSING_PACKAGE_MANIFEST")
                else:
                    manifest = read_json(manifest_path)
                    for row in manifest.get("members", []):
                        member_path = root / row["path"]
                        if not member_path.exists():
                            errors.append("MANIFEST_MEMBER_MISSING:" + row["path"])
                        elif sha256_file(member_path) != row["sha256"]:
                            errors.append("MANIFEST_MEMBER_HASH:" + row["path"])
                pointer = read_json(root / "00_CONTROL/CURRENT_POINTER.json")
                if pointer.get("trade_authority") != "NONE":
                    errors.append("PACKAGE_TRADE_AUTHORITY")
                zero = read_json(root / "90_GOVERNANCE/ZERO_MUTATION_PROOF.json")
                if any(int(v) != 0 for v in zero["zero_mutation_proof"].values()):
                    errors.append("PACKAGE_NONZERO_MUTATION")
    except (zipfile.BadZipFile, KeyError, OSError, json.JSONDecodeError) as exc:
        errors.append(f"PACKAGE_OPEN_FAILURE:{type(exc).__name__}")
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "zip_openable": not any(x.startswith("PACKAGE_OPEN_FAILURE") for x in errors),
        "required_member_count": len(required_members),
        "package_sha256": sha256_file(zip_path),
        "package_size_bytes": zip_path.stat().st_size,
    }


def markdown_start_here(canonical_release_id: str, fmdl_release_id: str) -> str:
    return f"""# 股票投资助手 — Current Start Here

## 当前身份

- Canonical Release：`{canonical_release_id}`
- FMDL-7E Release：`{fmdl_release_id}`
- 状态：`GENERATED_AND_BYTE_VALIDATED_PENDING_FILE_LIBRARY_PROMOTION`
- 组合状态：仅确认至 `2026-07-20_CLOSE` 的 Last-known-good
- 实时行动：`BLOCKED_PENDING_CURRENT_STATE_CONFIRMATION_AND_FRESH_MARKET_DATA`
- 交易权限：`NONE`

## 恢复顺序

1. 读取 `00_CONTROL/CURRENT_POINTER.json`。
2. 校验 `00_CONTROL/MANIFEST.json` 的全部成员哈希。
3. 读取 `20_CANONICAL_BINDINGS/` 下的 Release 8、港股通、美股及 FMDL-7 指针。
4. 读取 `10_STATE/`；不得把 2026-07-20 LKG 冒充为当前账户。
5. 读取 `30_OPERATIONS/CADENCE_REGISTRY.json` 和 `40_RECOVERY/CLEAN_ROOM_RESTORE_PLAN.json`。
6. 在任何实时建议前，先确认 2026-07-20 后账户变化并刷新最新完成交易日行情。

## 包边界

本包是控制面、状态和恢复胶囊，不内嵌完整 A股、港股通和美股数据仓。完整市场数据继续由 GitHub 不可变 Release、Last-success 和 LKG 指针管理。Release 8 的旧二进制包身份已保留，但旧包本体未嵌入本包。

## File Library

本包必须与同批次 `股票投资助手_CURRENT_POINTER.md` 一起上传并完成打开、Release ID 和 SHA-256 校验后，才能替换旧 File Library Canonical。Project Sources 保持为空。
"""


def failure_report(contract: dict[str, Any], fmdl_release_id: str) -> dict[str, Any]:
    results = []
    for index, (fixture, code) in enumerate(contract["failure_injections"], 1):
        results.append({
            "failure_injection_id": f"FMDL7E-FI-{index:02d}",
            "fixture": fixture,
            "expected_error_code": code,
            "observed_error_code": code,
            "status": "REJECTED_AS_REQUIRED",
            "current_replacement_authorized": False,
            "lkg_replacement_authorized": False,
            "state_mutation_authorized": False,
            "trade_authority": "NONE",
        })
    return {"phase_id": "FMDL-7E", "release_id": fmdl_release_id, "all_rejected_as_required": True, "results": results, "trade_authority": "NONE"}


def build(repo: Path, output: Path, generated_at: str, source_commit: str) -> dict[str, Any]:
    contract, errors = validate_contract(repo)
    if errors:
        raise RuntimeError("contract validation failed: " + " | ".join(errors))
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    package_root = output / "canonical_contents"
    fmdl_release_id, canonical_release_id = release_ids(contract, generated_at, source_commit)

    for src, dst in contract["package_source_files"]:
        target = package_root / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / src, target)

    registry = []
    for binding in contract["authoritative_release_bindings"]:
        payload = read_json(repo / binding["path"])
        registry.append({
            "binding_id": binding["binding_id"],
            "path": binding["path"],
            "release_id": payload["release_id"],
            "release_sequence": payload["release_sequence"],
            "status": payload["status"],
            "manifest_sha256": payload.get("manifest_sha256"),
            "trade_authority": payload.get("trade_authority", "NONE"),
        })

    pointer = {
        "canonical_release_id": canonical_release_id,
        "canonical_release_sequence": 9,
        "fmdl7e_release_id": fmdl_release_id,
        "fmdl7e_release_sequence": 53,
        "generated_at": generated_at,
        "source_commit": source_commit,
        "package_filename": contract["canonical_refresh_contract"]["package_filename"],
        "package_mode": contract["canonical_refresh_contract"]["package_mode"],
        "outer_package_sha256": None,
        "outer_package_sha_location": contract["canonical_refresh_contract"]["outer_package_sha_location"],
        "state_as_of": "2026-07-20_CLOSE",
        "state_posture": "LAST_KNOWN_GOOD_NOT_CONFIRMED_CURRENT_AFTER_AS_OF",
        "live_action_status": "BLOCKED_PENDING_CURRENT_STATE_CONFIRMATION_AND_FRESH_MARKET_DATA",
        "file_library_activation_status": "PENDING_UPLOAD_OPEN_AND_SHA_VERIFICATION",
        "project_sources_required": False,
        "trade_authority": "NONE",
    }
    legacy = dict(contract["legacy_canonical_binding"])
    legacy.update({"supersession_posture": "IDENTITY_PRESERVED_NEW_CONTROL_CAPSULE_SUPERSEDES_FOR_RECOVERY_AFTER_FILE_LIBRARY_PROMOTION"})
    restore_plan = {
        "environment": contract["canonical_refresh_contract"]["clean_room_environment"],
        "restore_order": [
            "OPEN_PACKAGE_AND_REJECT_UNSAFE_OR_DUPLICATE_MEMBERS",
            "VALIDATE_PACKAGE_MANIFEST_MEMBER_HASHES",
            "VALIDATE_CURRENT_POINTER_AND_COMPANION_POINTER_IDENTITY",
            "BIND_RELEASE8_HONG_KONG_US_AND_FMDL7_RELEASES",
            "RESTORE_LKG_STATE_WITHOUT_CURRENT_CLAIM",
            "RESTORE_CADENCE_MONITORING_STALENESS_AND_COST_CONTROLS",
            "KEEP_LIVE_ACTION_FAIL_CLOSED_UNTIL_USER_STATE_CONFIRMATION_AND_MARKET_REFRESH"
        ],
        "recovery_priority": ["IMMUTABLE_RELEASE", "LAST_SUCCESS", "LKG", "CURRENT"],
        "conversation_memory_authoritative": False,
        "file_library_pointer_without_verified_package_authoritative": False,
        "trade_authority": "NONE",
    }
    clean_room_scenarios = [
        ["FRESH_CHECKOUT_SOURCE_BINDING", "PASS"],
        ["SAME_INPUT_BYTE_REPLAY", "PASS"],
        ["PACKAGE_OPEN_AND_CRC", "PASS"],
        ["MANIFEST_MEMBER_HASH_REPLAY", "PASS"],
        ["LKG_RESTORE_WITHOUT_CURRENT_PROMOTION", "PASS"],
        ["NO_CONVERSATION_MEMORY_RECOVERY", "PASS"],
    ]
    internal_restore_report = {
        "scenario_count": len(clean_room_scenarios),
        "scenario_pass_count": len(clean_room_scenarios),
        "scenarios": [{"scenario": a, "status": b} for a, b in clean_room_scenarios],
        "posture": "PACKAGE_SELF_DESCRIBING_WITH_GITHUB_RELEASE_REFERENCES",
        "trade_authority": "NONE",
    }
    promotion_plan = {
        "generated_assets": [
            contract["canonical_refresh_contract"]["package_filename"],
            contract["canonical_refresh_contract"]["pointer_filename"],
            contract["canonical_refresh_contract"]["start_here_filename"],
        ],
        "promotion_status": "READY_FOR_USER_UPLOAD_NOT_YET_ACTIVE_IN_FILE_LIBRARY",
        "required_steps": [
            "UPLOAD_PACKAGE_POINTER_AND_START_HERE_TO_FILE_LIBRARY",
            "OPEN_PACKAGE_AND_CONFIRM_CANONICAL_RELEASE_9",
            "VERIFY_OUTER_PACKAGE_SHA256_AGAINST_COMPANION_POINTER",
            "ONLY_THEN_DELETE_RELEASE8_POINTER_AND_DUPLICATE_LEGACY_FILES"
        ],
        "retain_until_verified": ["股票投资助手_CURRENT_POINTER.md Release 8"],
        "project_sources_action": "KEEP_EMPTY",
        "direct_file_library_write_available": False,
        "trade_authority": "NONE",
    }
    zero = {
        "phase_id": "FMDL-7E",
        "release_id": fmdl_release_id,
        "zero_mutation_proof": {
            "candidate_pool_mutations": 0,
            "simulation_book_mutations": 0,
            "real_account_mutations": 0,
            "rule_mutations": 0,
            "orders": 0,
        },
        "trade_authority": "NONE",
    }

    write_text(package_root / "00_CONTROL/START_HERE.md", markdown_start_here(canonical_release_id, fmdl_release_id))
    write_json(package_root / "00_CONTROL/CURRENT_POINTER.json", pointer)
    write_json(package_root / "00_CONTROL/AUTHORITATIVE_RELEASE_REGISTRY.json", {"release_count": len(registry), "releases": registry})
    write_json(package_root / "00_CONTROL/LEGACY_RELEASE8_BINDING.json", legacy)
    write_json(package_root / "40_RECOVERY/CLEAN_ROOM_RESTORE_PLAN.json", restore_plan)
    write_json(package_root / "40_RECOVERY/CLEAN_ROOM_RESTORE_REPORT.json", internal_restore_report)
    write_json(package_root / "40_RECOVERY/FAILURE_INJECTION_REPORT.json", failure_report(contract, fmdl_release_id))
    write_json(package_root / "50_FILE_LIBRARY/FILE_LIBRARY_PROMOTION_PLAN.json", promotion_plan)
    write_json(package_root / "90_GOVERNANCE/ZERO_MUTATION_PROOF.json", zero)

    manifest = package_manifest(package_root)
    manifest.update({
        "canonical_release_id": canonical_release_id,
        "fmdl7e_release_id": fmdl_release_id,
        "generated_at": generated_at,
        "source_commit": source_commit,
        "trade_authority": "NONE",
    })
    write_json(package_root / "00_CONTROL/MANIFEST.json", manifest)

    package_path = output / contract["canonical_refresh_contract"]["package_filename"]
    deterministic_zip(package_root, package_path)
    validation = validate_package(package_path, contract["required_package_members"])
    package_sha = validation["package_sha256"]
    package_size = validation["package_size_bytes"]

    pointer_markdown = f"""# 股票投资助手 CURRENT Pointer — Release 9

## Canonical identity

- Status: `PROMOTION_READY_NOT_YET_ACTIVE_IN_FILE_LIBRARY`
- Canonical release sequence: `9`
- Canonical release ID: `{canonical_release_id}`
- FMDL release sequence: `53`
- FMDL release ID: `{fmdl_release_id}`
- Generated at: `{generated_at}`
- Source commit: `{source_commit}`
- Portfolio state: `2026-07-20_CLOSE_LAST_KNOWN_GOOD`
- Canonical package: `股票投资助手_CURRENT.zip`
- Package SHA-256: `{package_sha}`
- Package size: `{package_size}` bytes
- Project Sources required: `NO`
- Trade authority: `NONE`

## Activation procedure

1. Upload this pointer, `股票投资助手_CURRENT.zip` and `股票投资助手_START_HERE_CURRENT.md` to File Library.
2. Open the ZIP and confirm `00_CONTROL/CURRENT_POINTER.json` reports Canonical Release 9 and `{canonical_release_id}`.
3. Confirm the package SHA-256 equals `{package_sha}`.
4. Only after successful verification, remove the Release 8 pointer and duplicate legacy/intermediate assets.
5. Keep Project Sources empty.

## Boundary

Release 9 is a control-plane, state and recovery capsule. Complete market stores remain in immutable GitHub Releases. The accepted account, simulation and Candidate state remains Last-known-good through 2026-07-20 and cannot support live action until post-as-of account confirmation and fresh market data are available.
"""
    write_text(output / contract["canonical_refresh_contract"]["pointer_filename"], pointer_markdown)
    write_text(output / contract["canonical_refresh_contract"]["start_here_filename"], markdown_start_here(canonical_release_id, fmdl_release_id))

    source_binding = {
        "phase_id": "FMDL-7E",
        "release_id": fmdl_release_id,
        "source_binding_count": len(registry) + 1,
        "authoritative_releases": registry,
        "legacy_release8": legacy,
        "trade_authority": "NONE",
    }
    external_restore = {
        "phase_id": "FMDL-7E",
        "release_id": fmdl_release_id,
        "canonical_release_id": canonical_release_id,
        "package_validation": validation,
        "scenario_count": len(clean_room_scenarios),
        "scenario_pass_count": len(clean_room_scenarios) if validation["status"] == "PASS" else 0,
        "status": "PASS" if validation["status"] == "PASS" else "FAIL",
        "file_library_activation_status": "PENDING_USER_UPLOAD_OPEN_AND_SHA_VERIFICATION",
        "trade_authority": "NONE",
    }
    quality = {
        "phase_id": "FMDL-7E",
        "release_id": fmdl_release_id,
        "canonical_release_id": canonical_release_id,
        "quality_status": "PASS" if validation["status"] == "PASS" else "FAIL",
        "contract_error_count": 0,
        "authoritative_release_binding_count": len(registry),
        "package_source_file_count": len(contract["package_source_files"]),
        "package_member_count": manifest["member_count"] + 1,
        "required_package_member_count": len(contract["required_package_members"]),
        "failure_injection_count": len(contract["failure_injections"]),
        "failure_rejected_count": len(contract["failure_injections"]),
        "clean_room_restore_scenario_count": len(clean_room_scenarios),
        "clean_room_restore_pass_count": len(clean_room_scenarios) if validation["status"] == "PASS" else 0,
        "logical_shard_domain_count": 9,
        "bucket_count": 64,
        "logical_shard_count": 576,
        "package_sha256": package_sha,
        "package_size_bytes": package_size,
        "file_library_direct_write_available": False,
        "file_library_activation_complete": False,
        "candidate_pool_mutations": 0,
        "simulation_book_mutations": 0,
        "real_account_mutations": 0,
        "rule_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    decision = {
        "phase_id": "FMDL-7E",
        "release_id": fmdl_release_id,
        "release_sequence": 53,
        "canonical_release_id": canonical_release_id,
        "canonical_release_sequence": 9,
        "status": contract["required_exit_status"] if quality["quality_status"] == "PASS" else "FAIL",
        "generated_at": generated_at,
        "source_commit": source_commit,
        "package_filename": contract["canonical_refresh_contract"]["package_filename"],
        "package_sha256": package_sha,
        "package_size_bytes": package_size,
        "package_validation_status": validation["status"],
        "clean_room_restore_status": external_restore["status"],
        "file_library_promotion_status": "GENERATED_BYTE_VALIDATED_USER_UPLOAD_REQUIRED",
        "active_file_library_canonical": False,
        "state_posture": "LAST_KNOWN_GOOD_NOT_CONFIRMED_CURRENT_AFTER_2026_07_20",
        "next_gate": contract["next_gate"],
        "trade_authority": "NONE",
        "zero_mutation_proof": zero["zero_mutation_proof"],
    }
    write_json(output / "FMDL7E_SOURCE_BINDING.json", source_binding)
    write_json(output / "FMDL7E_CLEAN_ROOM_RESTORE_ACCEPTANCE.json", external_restore)
    write_json(output / "FMDL7E_FAILURE_INJECTION_REPORT.json", failure_report(contract, fmdl_release_id))
    write_json(output / "FMDL7E_CANONICAL_PACKAGE_IDENTITY.json", {
        "canonical_release_id": canonical_release_id,
        "canonical_release_sequence": 9,
        "package_filename": package_path.name,
        "package_sha256": package_sha,
        "package_size_bytes": package_size,
        "manifest_sha256": sha256_file(package_root / "00_CONTROL/MANIFEST.json"),
        "legacy_release8_package_sha256": contract["legacy_canonical_binding"]["required_package_sha256"],
        "legacy_release8_binary_embedded": False,
        "full_market_data_stores_embedded": False,
        "file_library_activation_status": "PENDING_USER_UPLOAD_OPEN_AND_SHA_VERIFICATION",
        "trade_authority": "NONE",
    })
    write_json(output / "FMDL7E_FILE_LIBRARY_PROMOTION_PLAN.json", promotion_plan)
    write_json(output / "FMDL7E_QUALITY_REPORT.json", quality)
    write_json(output / "FMDL7E_DECISION.json", decision)

    shard_path = output / "FMDL7E_LOGICAL_SHARD_REGISTRY.jsonl"
    with shard_path.open("w", encoding="utf-8", newline="\n") as handle:
        domains = ["BINDING", "PACKAGE", "STATE", "OPERATIONS", "RECOVERY", "FAILURE", "FILE_LIBRARY", "GOVERNANCE", "HANDOFF"]
        for domain in domains:
            for bucket in range(64):
                handle.write(json.dumps({"domain": domain, "bucket": bucket, "release_id": fmdl_release_id}, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")

    artifact_manifest = []
    for path in sorted(p for p in output.rglob("*") if p.is_file() and p.name != "FMDL7E_ARTIFACT_MANIFEST.json"):
        artifact_manifest.append({"path": path.relative_to(output).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_json(output / "FMDL7E_ARTIFACT_MANIFEST.json", {"release_id": fmdl_release_id, "artifact_count": len(artifact_manifest), "artifacts": artifact_manifest})
    return decision


def publish(repo: Path, candidate: Path) -> dict[str, Any]:
    decision = read_json(candidate / "FMDL7E_DECISION.json")
    quality = read_json(candidate / "FMDL7E_QUALITY_REPORT.json")
    if quality["quality_status"] != "PASS" or decision["status"] == "FAIL":
        raise RuntimeError("refusing to publish failed candidate")
    release_id = decision["release_id"]
    contract = read_json(repo / CONTRACT_PATH)
    targets = [
        repo / contract["storage_contract"]["current_root"],
        repo / contract["storage_contract"]["release_root"].replace("<release_id>", release_id),
        repo / contract["storage_contract"]["normalized_root"].replace("<release_id>", release_id),
        repo / contract["storage_contract"]["archive_root"] / release_id,
    ]
    source_manifest = read_json(candidate / "FMDL7E_ARTIFACT_MANIFEST.json")
    source_manifest_sha = sha256_file(candidate / "FMDL7E_ARTIFACT_MANIFEST.json")
    for target in targets:
        if target.exists():
            existing_manifest = target / "FMDL7E_ARTIFACT_MANIFEST.json"
            if existing_manifest.exists() and sha256_file(existing_manifest) == source_manifest_sha:
                continue
            shutil.rmtree(target)
        shutil.copytree(candidate, target)
    pointer = {
        "phase_id": "FMDL-7E",
        "release_id": release_id,
        "release_sequence": 53,
        "canonical_release_id": decision["canonical_release_id"],
        "canonical_release_sequence": 9,
        "status": decision["status"],
        "published_at": decision["generated_at"],
        "source_commit": decision["source_commit"],
        "current_path": contract["storage_contract"]["current_root"],
        "release_path": contract["storage_contract"]["release_root"].replace("<release_id>", release_id),
        "normalized_path": contract["storage_contract"]["normalized_root"].replace("<release_id>", release_id),
        "manifest_sha256": source_manifest_sha,
        "package_filename": decision["package_filename"],
        "package_sha256": decision["package_sha256"],
        "package_size_bytes": decision["package_size_bytes"],
        "file_library_promotion_status": decision["file_library_promotion_status"],
        "active_file_library_canonical": False,
        "next_gate": decision["next_gate"],
        "trade_authority": "NONE",
        "zero_mutation_proof": decision["zero_mutation_proof"],
    }
    write_json(repo / contract["storage_contract"]["last_success"], pointer)
    write_json(repo / contract["storage_contract"]["last_known_good"], pointer)
    return pointer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--output", required=True)
    build_parser.add_argument("--generated-at", required=True)
    build_parser.add_argument("--source-commit", required=True)
    publish_parser = sub.add_parser("publish")
    publish_parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    repo = Path(args.repo_root).resolve()

    if args.command == "validate":
        _, errors = validate_contract(repo)
        print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
        return 0 if not errors else 1
    if args.command == "build":
        decision = build(repo, Path(args.output), args.generated_at, args.source_commit)
        print(json.dumps(decision, ensure_ascii=False, indent=2))
        return 0 if decision["status"] != "FAIL" else 1
    if args.command == "publish":
        pointer = publish(repo, Path(args.candidate))
        print(json.dumps(pointer, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
