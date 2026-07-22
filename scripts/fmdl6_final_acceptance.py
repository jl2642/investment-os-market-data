#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

PROGRAM_ID = "FMDL-6-FINAL"
DEFAULT_CONTRACT = "config/fmdl6_final_resume_ready_operational_acceptance.json"
DEFAULT_CANDIDATE = "outputs/fmdl6_final/candidate"
DEFAULT_ACCEPTANCE = "outputs/fmdl6_final/acceptance/FMDL6FINAL_INDEPENDENT_ACCEPTANCE.json"


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def check_row(checks: list[dict[str, Any]], errors: list[str], dimension: str, name: str, condition: bool, detail: Any = None) -> None:
    checks.append({"dimension": dimension, "check": name, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        errors.append(name)


def _target_manifest_path(target: Path, manifest_name: str) -> Path:
    return target / manifest_name


def audit_root(repo_root: Path, contract: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    chain: list[dict[str, Any]] = []
    dimension = "COMPONENT_RELEASE_CHAIN"
    sequences: list[int] = []

    for gate in contract["entry_gates"]:
        pid = gate["program_id"]
        pointer_path = repo_root / gate["pointer"]
        check_row(checks, errors, dimension, f"POINTER_EXISTS:{pid}", pointer_path.exists(), gate["pointer"])
        if not pointer_path.exists():
            continue
        pointer = load_json(pointer_path)
        current = repo_root / gate["current_path"]
        release_path = current / gate["release_file"]
        manifest_path = current / gate["manifest_file"]
        check_row(checks, errors, dimension, f"CURRENT_EXISTS:{pid}", current.is_dir(), gate["current_path"])
        check_row(checks, errors, dimension, f"RELEASE_EXISTS:{pid}", release_path.exists(), str(release_path.relative_to(repo_root)))
        check_row(checks, errors, dimension, f"MANIFEST_EXISTS:{pid}", manifest_path.exists(), str(manifest_path.relative_to(repo_root)))
        if not release_path.exists() or not manifest_path.exists():
            continue
        release = load_json(release_path)
        manifest = load_json(manifest_path)
        expected = gate["release_id"]
        expected_status = gate["status"]
        expected_sequence = gate["release_sequence"]
        canonical = pointer.get("canonical_sha256")
        sequences.append(int(release.get("release_sequence", -1)))

        check_row(checks, errors, dimension, f"POINTER_RELEASE:{pid}", pointer.get("release_id") == expected, pointer.get("release_id"))
        check_row(checks, errors, dimension, f"POINTER_STATUS:{pid}", pointer.get("status") == expected_status, pointer.get("status"))
        check_row(checks, errors, dimension, f"POINTER_SEQUENCE:{pid}", pointer.get("release_sequence") == expected_sequence, pointer.get("release_sequence"))
        check_row(checks, errors, dimension, f"POINTER_AUTHORITY:{pid}", pointer.get("trade_authority") == "NONE")
        check_row(checks, errors, dimension, f"RELEASE_ID:{pid}", release.get("release_id") == expected, release.get("release_id"))
        check_row(checks, errors, dimension, f"RELEASE_STATUS:{pid}", release.get("status") == expected_status, release.get("status"))
        check_row(checks, errors, dimension, f"RELEASE_SEQUENCE:{pid}", release.get("release_sequence") == expected_sequence, release.get("release_sequence"))
        check_row(checks, errors, dimension, f"RELEASE_AUTHORITY:{pid}", release.get("trade_authority") == "NONE")
        check_row(checks, errors, dimension, f"MANIFEST_RELEASE:{pid}", manifest.get("release_id") == expected, manifest.get("release_id"))
        check_row(checks, errors, dimension, f"MANIFEST_SEQUENCE:{pid}", manifest.get("release_sequence") == expected_sequence, manifest.get("release_sequence"))
        check_row(checks, errors, dimension, f"MANIFEST_AUTHORITY:{pid}", manifest.get("trade_authority") == "NONE")
        check_row(checks, errors, dimension, f"CANONICAL_BINDING:{pid}", canonical == release.get("canonical_sha256") == manifest.get("canonical_sha256"), canonical)

        file_errors: list[str] = []
        files = manifest.get("files") or {}
        for name, metadata in files.items():
            path = current / name
            if not path.exists():
                file_errors.append(f"MISSING:{name}")
            elif sha256_file(path) != metadata.get("sha256"):
                file_errors.append(f"HASH:{name}")
            elif path.stat().st_size != metadata.get("size_bytes"):
                file_errors.append(f"SIZE:{name}")
        check_row(checks, errors, "MANIFEST_AND_PUBLICATION_INTEGRITY", f"CURRENT_MANIFEST_FILES:{pid}", not file_errors, file_errors)

        publication_errors: list[str] = []
        for label in ("archive_path", "immutable_path"):
            target_value = pointer.get(label)
            if not target_value:
                publication_errors.append(f"MISSING_POINTER_FIELD:{label}")
                continue
            target = repo_root / str(target_value)
            target_manifest = _target_manifest_path(target, gate["manifest_file"])
            if not target_manifest.exists():
                publication_errors.append(f"MISSING:{label}")
            elif sha256_file(target_manifest) != sha256_file(manifest_path):
                publication_errors.append(f"MANIFEST_MISMATCH:{label}")
        check_row(checks, errors, "MANIFEST_AND_PUBLICATION_INTEGRITY", f"ARCHIVE_IMMUTABLE_PARITY:{pid}", not publication_errors, publication_errors)

        chain.append({
            "program_id": pid,
            "release_sequence": expected_sequence,
            "release_id": expected,
            "status": expected_status,
            "canonical_sha256": canonical,
            "pointer_path": gate["pointer"],
            "current_path": gate["current_path"],
            "archive_path": pointer.get("archive_path"),
            "immutable_path": pointer.get("immutable_path"),
            "manifest_file_count": len(files),
            "trade_authority": "NONE"
        })

    expected_sequences = list(range(contract["acceptance_gates"]["first_release_sequence"], contract["acceptance_gates"]["last_release_sequence"] + 1))
    check_row(checks, errors, dimension, "RELEASE_SEQUENCE_CONTIGUOUS", sequences == expected_sequences, sequences)
    check_row(checks, errors, dimension, "COMPONENT_COUNT", len(chain) == contract["acceptance_gates"]["component_count"], len(chain))

    base = contract["cross_market_base"]
    base_path = repo_root / base["pointer"]
    check_row(checks, errors, "CROSS_MARKET_BASE", "FMDL5_POINTER_EXISTS", base_path.exists(), base["pointer"])
    if base_path.exists():
        pointer = load_json(base_path)
        check_row(checks, errors, "CROSS_MARKET_BASE", "FMDL5_RELEASE", pointer.get("release_id") == base["release_id"], pointer.get("release_id"))
        check_row(checks, errors, "CROSS_MARKET_BASE", "FMDL5_STATUS", pointer.get("status") == base["status"], pointer.get("status"))
        check_row(checks, errors, "CROSS_MARKET_BASE", "RELEASE8_BASE", pointer.get("canonical_base_release_id") == base["canonical_base_release_id"], pointer.get("canonical_base_release_id"))
        check_row(checks, errors, "CROSS_MARKET_BASE", "FMDL5_AUTHORITY", pointer.get("trade_authority") == "NONE")

    activation = load_json(repo_root / contract["activation_gate"]["source_path"])
    check_row(checks, errors, "ACTIVATION_AND_DEFERRED_CONTROL", "ACTIVATION_GATE_CLOSED", activation.get("gate_status") == contract["activation_gate"]["required_status"], activation.get("gate_status"))
    check_row(checks, errors, "ACTIVATION_AND_DEFERRED_CONTROL", "ACTIVATION_CONDITIONS", activation.get("required_conditions") == contract["activation_gate"]["required_conditions"], activation.get("required_conditions"))
    check_row(checks, errors, "ACTIVATION_AND_DEFERRED_CONTROL", "IMPLICIT_ACTIVATION_FORBIDDEN", activation.get("partial_or_implicit_activation_forbidden") is True)
    check_row(checks, errors, "ACTIVATION_AND_DEFERRED_CONTROL", "ACTIVATION_AUTHORITY", activation.get("trade_authority") == "NONE")

    backlog = load_json(repo_root / contract["deferred_backlog"]["source_path"])
    actual_ids = [row.get("phase_id") for row in backlog.get("items") or []]
    check_row(checks, errors, "ACTIVATION_AND_DEFERRED_CONTROL", "DEFERRED_BACKLOG_PHASES", actual_ids == contract["deferred_backlog"]["required_phase_ids"], actual_ids)
    check_row(checks, errors, "ACTIVATION_AND_DEFERRED_CONTROL", "DEFERRED_BACKLOG_STATUS", all(row.get("status") == "DEFERRED_NOT_AUTHORIZED" for row in backlog.get("items") or []))
    check_row(checks, errors, "ACTIVATION_AND_DEFERRED_CONTROL", "DEFERRED_AUTHORITY", backlog.get("trade_authority") == "NONE")

    scope_leaks = [key for key, value in contract["scope"].items() if key.endswith("_authorized") and value is not False]
    check_row(checks, errors, "STATE_AND_TRADE_AUTHORITY_FIREWALL", "NO_SCOPE_AUTHORITY_LEAK", not scope_leaks, scope_leaks)
    check_row(checks, errors, "STATE_AND_TRADE_AUTHORITY_FIREWALL", "CONTRACT_AUTHORITY", contract.get("trade_authority") == "NONE")
    return checks, errors, chain


def _hash_protected_inputs(repo_root: Path, contract: dict[str, Any]) -> dict[str, str]:
    paths = [Path(row["pointer"]) for row in contract["entry_gates"]]
    paths += [Path(row["current_path"]) / row["manifest_file"] for row in contract["entry_gates"]]
    paths += [Path(contract["cross_market_base"]["pointer"]), Path(contract["activation_gate"]["source_path"]), Path(contract["deferred_backlog"]["source_path"])]
    return {str(path): sha256_file(repo_root / path) for path in paths}


def _copy_restore_assets(repo_root: Path, restore_root: Path, contract: dict[str, Any]) -> None:
    for gate in contract["entry_gates"]:
        pointer = repo_root / gate["pointer"]
        destination = restore_root / gate["pointer"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pointer, destination)
        current_source = repo_root / gate["current_path"]
        current_destination = restore_root / gate["current_path"]
        shutil.copytree(current_source, current_destination)
        pointer_doc = load_json(pointer)
        for field in ("archive_path", "immutable_path"):
            source = repo_root / pointer_doc[field]
            target = restore_root / pointer_doc[field]
            shutil.copytree(source, target)
    for relative in (contract["cross_market_base"]["pointer"], contract["activation_gate"]["source_path"], contract["deferred_backlog"]["source_path"]):
        source = repo_root / relative
        target = restore_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def clean_room_restore(repo_root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="fmdl6-final-clean-") as tmp:
        restore_root = Path(tmp)
        _copy_restore_assets(repo_root, restore_root, contract)
        checks, errors, chain = audit_root(restore_root, contract)
        return {
            "program_id": PROGRAM_ID,
            "restore_mode": "MINIMAL_POINTER_CURRENT_ARCHIVE_IMMUTABLE_SNAPSHOT",
            "component_count": len(chain),
            "check_count": len(checks),
            "error_count": len(errors),
            "errors": errors,
            "clean_room_restore": "PASS" if not errors else "FAIL",
            "chat_memory_required": False,
            "trade_authority": "NONE"
        }


def failure_rollback(repo_root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    before = _hash_protected_inputs(repo_root, contract)
    injections: list[dict[str, Any]] = []
    cases = [
        ("MISSING_COMPONENT_POINTER", "POINTER_EXISTS:FMDL-6C"),
        ("RELEASE_ID_MISMATCH", "POINTER_RELEASE:FMDL-6D"),
        ("MANIFEST_FILE_LOSS", "CURRENT_MANIFEST_FILES:FMDL-6E"),
        ("TRADE_AUTHORITY_ESCALATION", "RELEASE_AUTHORITY:FMDL-6A"),
        ("ACTIVATION_GATE_OPENED", "ACTIVATION_GATE_CLOSED")
    ]
    for injection_id, expected in cases:
        with tempfile.TemporaryDirectory(prefix="fmdl6-final-failure-") as tmp:
            root = Path(tmp)
            _copy_restore_assets(repo_root, root, contract)
            if injection_id == "MISSING_COMPONENT_POINTER":
                (root / contract["entry_gates"][3]["pointer"]).unlink()
            elif injection_id == "RELEASE_ID_MISMATCH":
                path = root / contract["entry_gates"][4]["pointer"]
                doc = load_json(path); doc["release_id"] = "CORRUPTED"; write_json(path, doc)
            elif injection_id == "MANIFEST_FILE_LOSS":
                gate = contract["entry_gates"][5]
                manifest = load_json(root / gate["current_path"] / gate["manifest_file"])
                victim = sorted(manifest["files"])[0]
                (root / gate["current_path"] / victim).unlink()
            elif injection_id == "TRADE_AUTHORITY_ESCALATION":
                gate = contract["entry_gates"][1]
                path = root / gate["current_path"] / gate["release_file"]
                doc = load_json(path); doc["trade_authority"] = "FULL"; write_json(path, doc)
            elif injection_id == "ACTIVATION_GATE_OPENED":
                path = root / contract["activation_gate"]["source_path"]
                doc = load_json(path); doc["gate_status"] = "OPEN"; write_json(path, doc)
            _, errors, _ = audit_root(root, contract)
            injections.append({"injection_id": injection_id, "expected_code": expected, "detected": expected in errors, "error_count": len(errors), "mutation_scope": "TEMPORARY_COPY_ONLY"})
    after = _hash_protected_inputs(repo_root, contract)
    false_negatives = sum(not row["detected"] for row in injections)
    return {
        "program_id": PROGRAM_ID,
        "injection_count": len(injections),
        "detected_count": len(injections) - false_negatives,
        "false_negative_count": false_negatives,
        "all_expected_failures_detected": false_negatives == 0,
        "injections": injections,
        "upstream_lkg_unchanged": before == after,
        "upstream_write_count": 0,
        "protected_hashes_before": before,
        "protected_hashes_after": after,
        "trade_authority": "NONE"
    }


def _user_guide(release_id: str) -> str:
    return f"""# 股票投资助手｜阶段完成后的使用说明

## 当前能力边界

- A股：已具备全市场数据、因子筛选、研究适配、Investment OS接入和运营验收能力。
- 港股通：已具备南向范围、财务与行情、因子筛选、研究对象和Investment OS接入能力。
- 美股：当前是24只技术基准证券的Resume-Ready Pilot，不是可投资生产系统。
- 当前美股交易权限始终为 `NONE`。

## 日常使用

用户只需在“股票投资助手”项目中用自然语言提出任务，例如：

1. 更新并检查真实持仓、模拟盘和候选池状态；
2. 分析某只A股或港股通股票，或比较若干标的；
3. 执行月度Operating Review、收益归因或调仓复核；
4. 检查数据是否刷新、系统是否出现失败或需要恢复；
5. 讨论投资判断、组合配置、风险和执行顺序。

ChatGPT应先读取Investment OS Release 8，以及GitHub中的FMDL Current、Last-success和不可变Release，再给出结论。用户不需要维护技术目录或上传FMDL阶段产物。

## 美股未来恢复

恢复入口：`outputs/status/FMDL6_FINAL_LAST_SUCCESS.json`。

当用户真正具备美股投资渠道后，应在项目中明确说明渠道、可交易证券范围、账户币种、税务和执行约束，并明确授权继续开发。系统随后按以下顺序恢复：

`FMDL-6X1 → FMDL-6X2 → FMDL-6X3 → FMDL-6X4`

可以在新的专用窗口持续开发美股；股票投资助手的其他窗口可以继续进行A股、港股通、真实持仓、模拟盘和候选池运营，二者互不冲突。新的开发窗口无需依赖旧聊天上下文，只需读取本Release及GitHub Canonical资产。

## 文件库

File Library只保留Investment OS Release 8的Canonical ZIP及其Pointer／START_HERE。FMDL-5和FMDL-6的技术Release、代码、工作流、Current、Archive和Last-success由GitHub保存，不需要再次上传到File Library。

正式美股试点收口Release：`{release_id}`。
"""


def build_candidate(repo_root: Path, contract_path: Path, candidate_dir: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    checks, errors, chain = audit_root(repo_root, contract)
    if errors:
        raise ValueError(f"FMDL-6-FINAL baseline rejected: {errors}")
    restore = clean_room_restore(repo_root, contract)
    rollback = failure_rollback(repo_root, contract)
    hard_failures: list[str] = []
    if restore["clean_room_restore"] != "PASS": hard_failures.append("CLEAN_ROOM_RESTORE")
    if rollback["false_negative_count"]: hard_failures.append("FAILURE_FALSE_NEGATIVE")
    if not rollback["upstream_lkg_unchanged"]: hard_failures.append("UPSTREAM_LKG_CHANGED")
    if hard_failures:
        raise ValueError(f"FMDL-6-FINAL controls rejected: {hard_failures}")
    if candidate_dir.exists(): shutil.rmtree(candidate_dir)
    candidate_dir.mkdir(parents=True, exist_ok=True)

    release_chain = {"program_id": PROGRAM_ID, "component_count": len(chain), "components": chain, "sequence_contiguous": True, "trade_authority": "NONE"}
    activation = load_json(repo_root / contract["activation_gate"]["source_path"])
    backlog = load_json(repo_root / contract["deferred_backlog"]["source_path"])
    resume_handoff = {
        "program_id": PROGRAM_ID,
        "current_program_status": "PHASE_COMPLETE_A_SHARE_HK_OPERATIONAL_US_RESUME_READY",
        "resume_entry_pointer": "outputs/status/FMDL6_FINAL_LAST_SUCCESS.json",
        "restore_order": [
            "outputs/status/FMDL6_FINAL_LAST_SUCCESS.json",
            "outputs/fmdl6_final/current/FMDL6FINAL_RESUME_HANDOFF.json",
            "outputs/fmdl6_final/current/FMDL6FINAL_RELEASE_CHAIN.json",
            "outputs/fmdl6_final/current/FMDL6FINAL_ACTIVATION_GATE.json",
            "outputs/fmdl6_final/current/FMDL6FINAL_DEFERRED_BACKLOG.json",
            "outputs/fmdl6_final/current/FMDL6FINAL_USER_OPERATING_GUIDE.md"
        ],
        "future_activation_sequence": contract["deferred_backlog"]["required_phase_ids"],
        "dedicated_us_development_window_supported": True,
        "parallel_a_hk_operations_supported": True,
        "chat_memory_required": False,
        "explicit_activation_required": True,
        "trade_authority": "NONE"
    }
    library = {
        "program_id": PROGRAM_ID,
        "keep_only": contract["file_library_retention"]["keep_only"],
        "github_is_authoritative_for": contract["file_library_retention"]["github_is_authoritative_for"],
        "separate_fmdl6_file_library_upload_required": False,
        "cleanup_rule": "KEEP_THE_TWO_CURRENT_RELEASE8_CANONICAL_ASSETS_DELETE_OTHER_OBSOLETE_DUPLICATE_OR_INTERMEDIATE_STOCK_ASSISTANT_FILES",
        "trade_authority": "NONE"
    }
    acceptance = {
        "program_id": PROGRAM_ID,
        "baseline_check_count": len(checks),
        "baseline_error_count": 0,
        "component_count": len(chain),
        "release_sequence_start": 19,
        "release_sequence_end": 24,
        "clean_room_restore": restore["clean_room_restore"],
        "failure_injection_count": rollback["injection_count"],
        "failure_injection_false_negative_count": rollback["false_negative_count"],
        "upstream_lkg_unchanged": rollback["upstream_lkg_unchanged"],
        "activation_gate_status": activation["gate_status"],
        "deferred_phase_count": len(backlog["items"]),
        "quality_and_cost_benchmark_release": chain[-1]["release_id"],
        "trade_authority": "NONE"
    }
    canonical_payload = {
        "program_id": PROGRAM_ID,
        "contract_sha256": sha256_file(contract_path),
        "release_chain": release_chain,
        "operational_acceptance": acceptance,
        "clean_room_restore": restore,
        "failure_rollback": rollback,
        "resume_handoff": resume_handoff,
        "activation_gate": activation,
        "deferred_backlog": backlog,
        "library_retention": library
    }
    canonical_sha = sha256_bytes(stable_json(canonical_payload).encode("utf-8"))
    release_id = f"FMDL6FINAL_{contract['as_of_date'].replace('-', '')}_{canonical_sha[:12]}"
    decision = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "status": contract["exit_status"],
        "hard_failures": [],
        "stock_investment_assistant_phase_status": "PHASE_COMPLETE_A_SHARE_HK_OPERATIONAL_US_RESUME_READY",
        "separate_technical_development_closeout_required": False,
        "operating_observation_required": True,
        "us_full_build_activation_gate": "CLOSED",
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "trade_authority": "NONE",
        "next_gate": contract["next_gate"]
    }
    validation = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "validation": "PASS",
        "contract_check_count": len(checks),
        "contract_error_count": 0,
        "clean_room_restore": "PASS",
        "failure_injection_false_negative_count": 0,
        "upstream_lkg_unchanged": True,
        "trade_authority": "NONE",
        "errors": []
    }
    release = {
        "program_id": PROGRAM_ID,
        "program_name": contract["program_name"],
        "release_id": release_id,
        "release_sequence": contract["publication"]["release_sequence"],
        "as_of_date": contract["as_of_date"],
        "status": contract["exit_status"],
        "authority": contract["authority"],
        "scope_mode": contract["scope"]["mode"],
        "canonical_sha256": canonical_sha,
        "contract_sha256": sha256_file(contract_path),
        "component_count": len(chain),
        "cross_market_base_release_id": contract["cross_market_base"]["release_id"],
        "investment_os_base_release_id": contract["cross_market_base"]["canonical_base_release_id"],
        "phase_completion_status": decision["stock_investment_assistant_phase_status"],
        "activation_gate_status": "CLOSED",
        "candidate_pool_integration_authorized": False,
        "simulation_integration_authorized": False,
        "real_account_integration_authorized": False,
        "order_generation_authorized": False,
        "trade_authority": "NONE",
        "next_gate": contract["next_gate"]
    }

    documents: dict[str, Any] = {
        "FMDL6FINAL_RELEASE_CHAIN.json": release_chain,
        "FMDL6FINAL_OPERATIONAL_ACCEPTANCE.json": acceptance,
        "FMDL6FINAL_CLEAN_ROOM_RESTORE.json": restore,
        "FMDL6FINAL_FAILURE_ROLLBACK.json": rollback,
        "FMDL6FINAL_RESUME_HANDOFF.json": resume_handoff,
        "FMDL6FINAL_ACTIVATION_GATE.json": activation,
        "FMDL6FINAL_DEFERRED_BACKLOG.json": backlog,
        "FMDL6FINAL_LIBRARY_RETENTION.json": library,
        "FMDL6FINAL_DECISION.json": decision,
        "FMDL6FINAL_VALIDATION.json": validation,
        "FMDL6FINAL_RELEASE.json": release
    }
    for name, document in documents.items(): write_json(candidate_dir / name, document)
    write_text(candidate_dir / "FMDL6FINAL_USER_OPERATING_GUIDE.md", _user_guide(release_id))
    manifest_names = sorted(list(documents) + ["FMDL6FINAL_USER_OPERATING_GUIDE.md"])
    manifest = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": release["release_sequence"],
        "canonical_sha256": canonical_sha,
        "contract_sha256": release["contract_sha256"],
        "files": {name: {"sha256": sha256_file(candidate_dir / name), "size_bytes": (candidate_dir / name).stat().st_size} for name in manifest_names},
        "trade_authority": "NONE"
    }
    write_json(candidate_dir / "FMDL6FINAL_MANIFEST.json", manifest)
    return release


def validate_candidate(repo_root: Path, contract_path: Path, candidate_dir: Path, acceptance_path: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    release = load_json(candidate_dir / "FMDL6FINAL_RELEASE.json")
    decision = load_json(candidate_dir / "FMDL6FINAL_DECISION.json")
    validation = load_json(candidate_dir / "FMDL6FINAL_VALIDATION.json")
    manifest = load_json(candidate_dir / "FMDL6FINAL_MANIFEST.json")
    errors: list[str] = []
    for name, metadata in manifest.get("files", {}).items():
        path = candidate_dir / name
        if not path.exists(): errors.append(f"MISSING_FILE:{name}")
        elif sha256_file(path) != metadata.get("sha256"): errors.append(f"HASH:{name}")
        elif path.stat().st_size != metadata.get("size_bytes"): errors.append(f"SIZE:{name}")
    canonical_payload = {
        "program_id": PROGRAM_ID,
        "contract_sha256": release["contract_sha256"],
        "release_chain": load_json(candidate_dir / "FMDL6FINAL_RELEASE_CHAIN.json"),
        "operational_acceptance": load_json(candidate_dir / "FMDL6FINAL_OPERATIONAL_ACCEPTANCE.json"),
        "clean_room_restore": load_json(candidate_dir / "FMDL6FINAL_CLEAN_ROOM_RESTORE.json"),
        "failure_rollback": load_json(candidate_dir / "FMDL6FINAL_FAILURE_ROLLBACK.json"),
        "resume_handoff": load_json(candidate_dir / "FMDL6FINAL_RESUME_HANDOFF.json"),
        "activation_gate": load_json(candidate_dir / "FMDL6FINAL_ACTIVATION_GATE.json"),
        "deferred_backlog": load_json(candidate_dir / "FMDL6FINAL_DEFERRED_BACKLOG.json"),
        "library_retention": load_json(candidate_dir / "FMDL6FINAL_LIBRARY_RETENTION.json")
    }
    canonical = sha256_bytes(stable_json(canonical_payload).encode("utf-8"))
    if canonical != release.get("canonical_sha256") or canonical != manifest.get("canonical_sha256"): errors.append("CANONICAL_RECOMPUTE")
    if release.get("status") != contract["exit_status"] or decision.get("status") != contract["exit_status"]: errors.append("STATUS")
    if validation.get("validation") != "PASS": errors.append("VALIDATION")
    if decision.get("hard_failures"): errors.append("HARD_FAILURES")
    if any(decision.get(key) != 0 for key in ("candidate_pool_mutation_count", "simulation_mutation_count", "real_account_mutation_count", "order_generation_count")): errors.append("STATE_MUTATION")
    if release.get("trade_authority") != "NONE" or decision.get("trade_authority") != "NONE": errors.append("TRADE_AUTHORITY")
    with tempfile.TemporaryDirectory(prefix="fmdl6-final-replay-") as tmp:
        replay = Path(tmp) / "candidate"
        replay_release = build_candidate(repo_root, contract_path, replay)
        replay_manifest = load_json(replay / "FMDL6FINAL_MANIFEST.json")
        same_input = replay_release["canonical_sha256"] == release["canonical_sha256"] and replay_manifest["files"] == manifest["files"]
    if not same_input: errors.append("SAME_INPUT_REPLAY")
    acceptance = {
        "program_id": PROGRAM_ID,
        "release_id": release["release_id"],
        "validation": "PASS" if not errors else "FAIL",
        "same_input_replay": "PASS" if same_input else "FAIL",
        "manifest_file_count": len(manifest.get("files", {})),
        "errors": errors,
        "trade_authority": "NONE"
    }
    write_json(acceptance_path, acceptance)
    if errors: raise ValueError(f"FMDL-6-FINAL independent validation failed: {errors}")
    return acceptance


def _copy_verified(source: Path, target: Path) -> None:
    if target.exists():
        if load_json(target / "FMDL6FINAL_MANIFEST.json") == load_json(source / "FMDL6FINAL_MANIFEST.json"): return
        raise FileExistsError(f"target differs: {target}")
    shutil.copytree(source, target)


def publish_candidate(repo_root: Path, contract_path: Path, candidate_dir: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    release = load_json(candidate_dir / "FMDL6FINAL_RELEASE.json")
    decision = load_json(candidate_dir / "FMDL6FINAL_DECISION.json")
    manifest = load_json(candidate_dir / "FMDL6FINAL_MANIFEST.json")
    if release["status"] != contract["exit_status"] or release["trade_authority"] != "NONE" or decision["hard_failures"]:
        raise ValueError("candidate is not publishable")
    current = repo_root / contract["publication"]["current_path"]
    archive = repo_root / contract["publication"]["archive_root"] / release["release_id"]
    immutable = repo_root / contract["publication"]["immutable_root"] / release["release_id"]
    if current.exists(): shutil.rmtree(current)
    shutil.copytree(candidate_dir, current)
    _copy_verified(candidate_dir, archive)
    _copy_verified(candidate_dir, immutable)
    last_success = {
        "program_id": PROGRAM_ID,
        "release_id": release["release_id"],
        "release_sequence": release["release_sequence"],
        "status": release["status"],
        "canonical_sha256": release["canonical_sha256"],
        "contract_sha256": release["contract_sha256"],
        "manifest_sha256": sha256_file(candidate_dir / "FMDL6FINAL_MANIFEST.json"),
        "current_path": contract["publication"]["current_path"],
        "archive_path": str(archive.relative_to(repo_root)),
        "immutable_path": str(immutable.relative_to(repo_root)),
        "component_count": release["component_count"],
        "phase_completion_status": release["phase_completion_status"],
        "activation_gate_status": release["activation_gate_status"],
        "resume_handoff_path": f"{contract['publication']['current_path']}/FMDL6FINAL_RESUME_HANDOFF.json",
        "user_operating_guide_path": f"{contract['publication']['current_path']}/FMDL6FINAL_USER_OPERATING_GUIDE.md",
        "library_retention_path": f"{contract['publication']['current_path']}/FMDL6FINAL_LIBRARY_RETENTION.json",
        "next_gate": release["next_gate"],
        "trade_authority": "NONE"
    }
    write_json(repo_root / contract["publication"]["last_success_path"], last_success)
    return last_success


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FMDL-6-FINAL operational acceptance")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("contract", "build", "validate", "publish"):
        current = sub.add_parser(name)
        current.add_argument("--repo-root", default=".")
        current.add_argument("--contract", default=DEFAULT_CONTRACT)
        if name in {"build", "validate", "publish"}: current.add_argument("--candidate", default=DEFAULT_CANDIDATE)
        if name == "validate": current.add_argument("--acceptance", default=DEFAULT_ACCEPTANCE)
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve(); contract = (root / args.contract).resolve()
    if args.command == "contract":
        checks, errors, _ = audit_root(root, load_json(contract)); print(json.dumps({"check_count": len(checks), "errors": errors}, sort_keys=True)); return 1 if errors else 0
    candidate = (root / args.candidate).resolve()
    if args.command == "build": print(json.dumps(build_candidate(root, contract, candidate), sort_keys=True)); return 0
    if args.command == "validate": print(json.dumps(validate_candidate(root, contract, candidate, (root / args.acceptance).resolve()), sort_keys=True)); return 0
    print(json.dumps(publish_candidate(root, contract, candidate), sort_keys=True)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
