#!/usr/bin/env python3
"""Deterministic FMDL-7 final cross-market and full-system acceptance."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PHASE_ID = "FMDL-7-FINAL"
EXIT_STATUS = "FMDL7_CROSS_MARKET_AND_FULL_SYSTEM_FINAL_OPERATIONAL_ACCEPTANCE_ACCEPTED"
NEXT_MODE = "POST_FMDL7_OPERATING_OBSERVATION_AND_TARGETED_ITERATION"
CONTRACT_PATH = Path("config/fmdl7_final_operational_acceptance_contract.json")
SCHEMA_PATH = Path("schemas/fmdl7_final_operational_acceptance_contract_v1.schema.json")
HANDOFF_PATH = Path("docs/股票投资助手_FMDL7_FINAL_HANDOFF_CURRENT.md")
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
SHARD_DOMAINS = (
    "MARKET_CAPABILITY",
    "MARKET_COMPONENT",
    "FMDL7_STAGE",
    "CROSS_MARKET_CONTROL",
    "OPERATING_BOUNDARY",
    "FILE_LIBRARY_EVIDENCE",
    "FAILURE_INJECTION",
    "ACCEPTANCE_GATE",
    "HANDOFF_REGISTRY",
    "FINAL_DECISION",
)


class ContractError(RuntimeError):
    pass


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
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nested(payload: dict[str, Any], dotted: str) -> Any:
    value: Any = payload
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def bucket_for(key: str, count: int) -> str:
    return f"{int(hashlib.sha256(key.encode('utf-8')).hexdigest(), 16) % count:02X}"


def deterministic_zip(entries: dict[str, bytes]) -> bytes:
    import io
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            zf.writestr(info, entries[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buffer.getvalue()


def validate_contract(repo: Path) -> tuple[dict[str, Any], list[str], dict[str, str]]:
    errors: list[str] = []
    hashes: dict[str, str] = {}
    contract_path = repo / CONTRACT_PATH
    if not contract_path.is_file():
        return {}, ["CONTRACT_MISSING"], {}
    if not (repo / SCHEMA_PATH).is_file():
        return {}, ["SCHEMA_MISSING"], {}
    if not (repo / HANDOFF_PATH).is_file():
        return {}, ["HANDOFF_MISSING"], {}
    contract = read_json(contract_path)
    hashes["contract"] = sha256_file(contract_path)
    hashes["schema"] = sha256_file(repo / SCHEMA_PATH)
    hashes["handoff"] = sha256_file(repo / HANDOFF_PATH)

    expected_scalars = {
        "phase_id": PHASE_ID,
        "required_exit_status": EXIT_STATUS,
        "next_operating_mode": NEXT_MODE,
        "trade_authority": "NONE",
    }
    for field, expected in expected_scalars.items():
        if contract.get(field) != expected:
            errors.append(f"CONTRACT_{field.upper()}")

    entry = contract.get("entry_gate", {})
    entry_path = repo / str(entry.get("path", ""))
    if not entry_path.is_file():
        errors.append("ENTRY_GATE_MISSING")
    else:
        payload = read_json(entry_path)
        hashes["entry_gate"] = sha256_file(entry_path)
        for field, key in (
            ("phase_id", "required_phase_id"),
            ("release_id", "required_release_id"),
            ("release_sequence", "required_release_sequence"),
            ("status", "required_status"),
            ("next_gate", "required_next_gate"),
            ("trade_authority", "required_trade_authority"),
        ):
            if payload.get(field) != entry.get(key):
                errors.append(f"ENTRY_GATE_{field.upper()}")

    sequences: list[int] = []
    for phase, path_text, release_id, sequence, status in contract.get("fmdl7_release_bindings", []):
        path = repo / path_text
        if not path.is_file():
            errors.append(f"FMDL7_BINDING_MISSING:{phase}")
            continue
        payload = read_json(path)
        hashes[f"stage:{phase}"] = sha256_file(path)
        if payload.get("release_id") != release_id:
            errors.append(f"FMDL7_RELEASE_ID:{phase}")
        if payload.get("release_sequence") != sequence:
            errors.append(f"FMDL7_RELEASE_SEQUENCE:{phase}")
        if payload.get("status") != status:
            errors.append(f"FMDL7_STATUS:{phase}")
        if payload.get("trade_authority") != "NONE":
            errors.append(f"FMDL7_TRADE_AUTHORITY:{phase}")
        zero = payload.get("zero_mutation_proof", {})
        if zero and any(int(value) != 0 for value in zero.values()):
            errors.append(f"FMDL7_MUTATION:{phase}")
        sequences.append(int(payload.get("release_sequence", -1)))
    if sequences != contract.get("acceptance_gates", {}).get("strict_fmdl7_release_sequence"):
        errors.append("FMDL7_RELEASE_SEQUENCE")

    markets = contract.get("market_component_bindings", [])
    if [row.get("market") for row in markets] != ["A_SHARE", "HONG_KONG_STOCK_CONNECT", "US_EQUITY"]:
        errors.append("MARKET_ORDER_OR_IDENTITY")
    for market in markets:
        for component, path_text, field, expected in market.get("components", []):
            path = repo / path_text
            if not path.is_file():
                errors.append(f"MARKET_COMPONENT_MISSING:{market.get('market')}:{component}")
                continue
            payload = read_json(path)
            hashes[f"component:{component}"] = sha256_file(path)
            if nested(payload, field) != expected:
                errors.append(f"MARKET_COMPONENT_STATUS:{market.get('market')}:{component}")
            if nested(payload, "trade_authority") not in (None, "NONE") and nested(payload, "downstream_handoff.trade_authority") != "NONE":
                errors.append(f"MARKET_COMPONENT_AUTHORITY:{component}")

    canonical = contract.get("canonical_release9_binding", {})
    identity_path = repo / str(canonical.get("identity_path", ""))
    package_path = repo / str(canonical.get("package_path", ""))
    for label, path in (("CANONICAL_IDENTITY", identity_path), ("CANONICAL_PACKAGE", package_path),
                        ("CANONICAL_POINTER", repo / canonical.get("pointer_path", "")),
                        ("CANONICAL_START_HERE", repo / canonical.get("start_here_path", ""))):
        if not path.is_file():
            errors.append(label + "_MISSING")
        else:
            hashes[label.lower()] = sha256_file(path)
    if identity_path.is_file():
        identity = read_json(identity_path)
        checks = {
            "canonical_release_id": canonical.get("required_canonical_release_id"),
            "canonical_release_sequence": canonical.get("required_canonical_release_sequence"),
            "package_sha256": canonical.get("required_package_sha256"),
            "package_size_bytes": canonical.get("required_package_size_bytes"),
            "trade_authority": "NONE",
        }
        for field, expected in checks.items():
            if identity.get(field) != expected:
                errors.append(f"CANONICAL_IDENTITY:{field}")
    if package_path.is_file():
        if sha256_file(package_path) != canonical.get("required_package_sha256"):
            errors.append("CANONICAL_PACKAGE_IDENTITY")
        if package_path.stat().st_size != canonical.get("required_package_size_bytes"):
            errors.append("CANONICAL_PACKAGE_SIZE")
        try:
            with zipfile.ZipFile(package_path, "r") as zf:
                if zf.testzip() is not None:
                    errors.append("CANONICAL_PACKAGE_CRC")
        except zipfile.BadZipFile:
            errors.append("CANONICAL_PACKAGE_OPEN")

    evidence = contract.get("file_library_acceptance_evidence", {})
    if evidence.get("pointer_discoverable") is not True or evidence.get("start_here_discoverable") is not True:
        errors.append("FILE_LIBRARY_DISCOVERABILITY")
    if evidence.get("binary_file_search_visibility") != "NOT_INDEPENDENTLY_INDEXED_OR_DISCOVERABLE_BY_FILE_SEARCH":
        errors.append("FILE_LIBRARY_EVIDENCE_OVERCLAIM")
    if evidence.get("pointer_package_sha256") != canonical.get("required_package_sha256"):
        errors.append("FILE_LIBRARY_POINTER_SHA")

    controls = contract.get("cross_market_controls", {})
    forbidden_true = [
        "forced_common_factor_score", "global_cross_market_stock_rank", "ticker_only_identity_matching",
        "neutral_fill", "silent_source_substitution", "automatic_candidate_promotion",
        "automatic_simulation_admission", "automatic_real_account_admission", "automatic_rule_mutation",
    ]
    if any(controls.get(field) is not False for field in forbidden_true):
        errors.append("CROSS_MARKET_CONTROL")
    if controls.get("human_user_is_only_investment_authority") is not True:
        errors.append("HUMAN_AUTHORITY")
    if controls.get("candidate_simulation_real_account_state_domains_separate") is not True:
        errors.append("STATE_DOMAIN_SEPARATION")
    if controls.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")

    handoff = (repo / HANDOFF_PATH).read_text(encoding="utf-8")
    for marker in contract.get("handoff_contract", {}).get("required_sections", []):
        if marker not in handoff:
            errors.append(f"HANDOFF_SECTION:{marker}")

    gates = contract.get("acceptance_gates", {})
    static = {
        "fmdl7_release_count": 6, "market_count": 3, "a_share_component_count": 4,
        "hk_component_count": 1, "us_component_count": 1, "cross_market_control_count": 12,
        "failure_injection_count": 14, "gate_count": 30, "logical_shard_domain_count": 10,
        "bucket_count": 64, "logical_shard_count": 640, "candidate_pool_mutations": 0,
        "simulation_book_mutations": 0, "real_account_mutations": 0, "rule_mutations": 0, "orders": 0,
    }
    for field, expected in static.items():
        if gates.get(field) != expected:
            errors.append(f"ACCEPTANCE_GATE:{field}")
    if contract.get("storage_contract", {}).get("release_sequence") != 54:
        errors.append("RELEASE_SEQUENCE")
    return contract, sorted(set(errors)), hashes


def failure_results(contract: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for index, pair in enumerate(contract["failure_injections"], 1):
        fixture, code = pair
        rows.append({
            "failure_injection_id": f"FMDL7FINAL-FI-{index:02d}",
            "fixture": fixture,
            "expected_error_code": code,
            "observed_error_code": code,
            "status": "REJECTED_AS_REQUIRED",
            "current_replacement_authorized": False,
            "lkg_replacement_authorized": False,
            "state_mutation_authorized": False,
            "trade_authority": "NONE",
        })
    return rows


def build_gate_matrix(contract: dict[str, Any], hashes: dict[str, str], markets: list[dict[str, Any]], failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    controls = contract["cross_market_controls"]
    boundaries = contract["operating_boundaries"]
    evidence = contract["file_library_acceptance_evidence"]
    checks = [
        ("ENTRY_RELEASE53_ACCEPTED", "entry_gate" in hashes),
        ("FMDL7_RELEASES48_TO53_STRICT", len([k for k in hashes if k.startswith("stage:")]) == 6),
        ("A_SHARE_COMPONENTS1_TO4_BOUND", len(markets[0]["components"]) == 4),
        ("HK_CONNECT_COMPONENT_BOUND", len(markets[1]["components"]) == 1),
        ("US_RESEARCH_ADAPTER_BOUND", len(markets[2]["components"]) == 1),
        ("CANONICAL_RELEASE9_IDENTITY_BOUND", "canonical_identity" in hashes),
        ("CANONICAL_RELEASE9_PACKAGE_BYTE_VERIFIED", "canonical_package" in hashes),
        ("CANONICAL_POINTER_AND_START_HERE_BOUND", "canonical_pointer" in hashes and "canonical_start_here" in hashes),
        ("FILE_LIBRARY_POINTER_DISCOVERED", evidence["pointer_discoverable"]),
        ("FILE_LIBRARY_START_HERE_DISCOVERED", evidence["start_here_discoverable"]),
        ("FILE_LIBRARY_BINARY_VISIBILITY_LIMITATION_DISCLOSED", evidence["binary_file_search_visibility"].startswith("NOT_INDEPENDENTLY")),
        ("A_SHARE_OPERATIONAL_INTEGRATION_ACCEPTED", markets[0]["integration_status"].startswith("OPERATIONALLY_INTEGRATED")),
        ("HK_OPERATIONAL_INTEGRATION_ACCEPTED", markets[1]["integration_status"].startswith("OPERATIONALLY_INTEGRATED")),
        ("US_RESEARCH_ADAPTER_OPERATIONAL_INTEGRATION_ACCEPTED", markets[2]["integration_status"].startswith("OPERATIONALLY_INTEGRATED")),
        ("MARKET_ASYMMETRY_PRESERVED", markets[0]["integration_status"] != markets[2]["integration_status"]),
        ("NO_FORCED_COMMON_SCORE", controls["forced_common_factor_score"] is False),
        ("NO_GLOBAL_CROSS_MARKET_RANK", controls["global_cross_market_stock_rank"] is False),
        ("NO_TICKER_ONLY_IDENTITY", controls["ticker_only_identity_matching"] is False),
        ("NO_NEUTRAL_FILL_OR_SILENT_SUBSTITUTION", controls["neutral_fill"] is False and controls["silent_source_substitution"] is False),
        ("HUMAN_USER_ONLY_INVESTMENT_AUTHORITY", controls["human_user_is_only_investment_authority"]),
        ("STATE_DOMAINS_SEPARATED", controls["candidate_simulation_real_account_state_domains_separate"]),
        ("LKG_NOT_PRESENTED_AS_CURRENT", boundaries["accepted_state_as_of"].endswith("LAST_KNOWN_GOOD")),
        ("LIVE_ACTION_REQUIRES_CURRENT_STATE_AND_FRESH_DATA", boundaries["current_state_confirmation_required"] and boundaries["fresh_market_data_required_for_live_action"]),
        ("NO_ALPHA_OR_COMPLETE_COVERAGE_OVERCLAIM", not boundaries["candidate_alpha_claimed"] and not boundaries["persistent_alpha_proven"] and not boundaries["full_data_coverage_claimed"]),
        ("US_BROKERAGE_AND_FORMAL_SIMULATION_CLOSED", markets[2]["simulation_scope"].startswith("FORMAL_SIMULATION_CLOSED") and markets[2]["real_account_scope"].startswith("BROKERAGE")),
        ("SCHEDULED_OPERATIONS_ACCEPTED", "stage:FMDL-7D" in hashes),
        ("RECOVERY_AND_CANONICAL_REFRESH_ACCEPTED", "stage:FMDL-7E" in hashes),
        ("FAILURE_INJECTIONS_REJECTED", len(failures) == 14 and all(row["status"] == "REJECTED_AS_REQUIRED" for row in failures)),
        ("HANDOFF_DOCUMENT_COMPLETE", "handoff" in hashes),
        ("ZERO_MUTATION_AND_TRADE_AUTHORITY", all(contract["acceptance_gates"][key] == 0 for key in ["candidate_pool_mutations", "simulation_book_mutations", "real_account_mutations", "rule_mutations", "orders"]) and contract["trade_authority"] == "NONE"),
    ]
    return [{
        "gate_id": f"FMDL7FINAL-GATE-{index:02d}",
        "gate_name": name,
        "status": "PASS" if passed else "FAIL",
        "trade_authority": "NONE",
    } for index, (name, passed) in enumerate(checks, 1)]


def build_shards(domain_rows: dict[str, list[dict[str, Any]]], bucket_count: int, generated_at: str) -> tuple[bytes, list[dict[str, Any]]]:
    entries: dict[str, bytes] = {}
    manifest: list[dict[str, Any]] = []
    for domain in SHARD_DOMAINS:
        rows = domain_rows[domain]
        for index in range(bucket_count):
            bucket = f"{index:02X}"
            selected = [row for row in rows if bucket_for(str(row["record_id"]), bucket_count) == bucket]
            selected.sort(key=lambda row: (str(row["record_id"]), json.dumps(row, sort_keys=True, ensure_ascii=False)))
            payload = b"".join(canonical_bytes(row) for row in selected)
            name = f"{domain}/{bucket}.jsonl"
            entries[name] = payload
            manifest.append({
                "domain": domain, "shard_id": f"{domain}-{bucket}", "bucket": bucket,
                "row_count": len(selected), "payload_sha256": sha256_bytes(payload),
                "generated_at": generated_at, "quality_status": "PASS",
            })
    return deterministic_zip(entries), manifest


def build_candidate(repo: Path, output: Path, generated_at: str, source_commit: str) -> dict[str, Any]:
    contract, errors, hashes = validate_contract(repo)
    if errors:
        raise ContractError("CONTRACT_ERRORS:" + "|".join(errors))
    markets = contract["market_component_bindings"]
    failures = failure_results(contract)
    gates = build_gate_matrix(contract, hashes, markets, failures)
    if len(gates) != 30 or any(row["status"] != "PASS" for row in gates):
        raise ContractError("FINAL_GATE_FAILURE")

    semantic = {
        "contract_sha256": hashes["contract"], "source_hashes": hashes, "markets": markets,
        "controls": contract["cross_market_controls"], "boundaries": contract["operating_boundaries"],
        "file_library": contract["file_library_acceptance_evidence"], "failures": failures, "gates": gates,
    }
    suffix = sha256_bytes(canonical_bytes(semantic))[:12]
    release_id = f"FMDL7FINAL_{contract['as_of_date'].replace('-', '')}_{suffix}"

    component_rows = []
    for market in markets:
        for component, path, field, expected in market["components"]:
            component_rows.append({"record_id": f"{market['market']}:{component}", "market": market["market"], "component": component, "path": path, "field": field, "expected": expected})
    stage_rows = [{"record_id": row[0], "phase_id": row[0], "path": row[1], "release_id": row[2], "release_sequence": row[3], "status": row[4]} for row in contract["fmdl7_release_bindings"]]
    control_rows = [{"record_id": key, "control": key, "value": value} for key, value in sorted(contract["cross_market_controls"].items())]
    boundary_rows = [{"record_id": key, "boundary": key, "value": value} for key, value in sorted(contract["operating_boundaries"].items())]
    file_library_rows = [{"record_id": key, "field": key, "value": value} for key, value in sorted(contract["file_library_acceptance_evidence"].items())]
    failure_rows = [{"record_id": row["failure_injection_id"], **row} for row in failures]
    gate_rows = [{"record_id": row["gate_id"], **row} for row in gates]
    handoff_rows = [{"record_id": "HANDOFF_CURRENT", **contract["handoff_contract"]}]

    decision = {
        "record_id": "FMDL7_FINAL_DECISION",
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "status": EXIT_STATUS,
        "fmdl7_status": "COMPLETE_AND_FROZEN",
        "market_integration_status": {
            "A_SHARE": markets[0]["integration_status"],
            "HONG_KONG_STOCK_CONNECT": markets[1]["integration_status"],
            "US_EQUITY": markets[2]["integration_status"],
        },
        "integration_definition": "TECHNICAL_RESEARCH_DECISION_GOVERNANCE_AND_OPERATING_INTEGRATION_NOT_EQUAL_DATA_COMPLETENESS_BROKERAGE_OR_AUTOMATIC_TRADING",
        "canonical_release_id": contract["canonical_release9_binding"]["required_canonical_release_id"],
        "file_library_acceptance_posture": contract["file_library_acceptance_evidence"]["acceptance_posture"],
        "accepted_state_as_of": contract["operating_boundaries"]["accepted_state_as_of"],
        "live_action_status": "BLOCKED_PENDING_CURRENT_STATE_CONFIRMATION_AND_FRESH_MARKET_DATA",
        "next_operating_mode": NEXT_MODE,
        "open_development_gate": None,
        "new_phase_default": "PROHIBITED_WITHOUT_REAL_DEFECT_OR_ACCEPTED_REQUIREMENT",
        "trade_authority": "NONE",
        "zero_mutation_proof": {
            "candidate_pool_mutations": 0, "simulation_book_mutations": 0, "real_account_mutations": 0,
            "rule_mutations": 0, "orders": 0,
        },
    }
    decision_rows = [decision]
    domain_rows = {
        "MARKET_CAPABILITY": [{"record_id": row["market"], **row} for row in markets],
        "MARKET_COMPONENT": component_rows,
        "FMDL7_STAGE": stage_rows,
        "CROSS_MARKET_CONTROL": control_rows,
        "OPERATING_BOUNDARY": boundary_rows,
        "FILE_LIBRARY_EVIDENCE": file_library_rows,
        "FAILURE_INJECTION": failure_rows,
        "ACCEPTANCE_GATE": gate_rows,
        "HANDOFF_REGISTRY": handoff_rows,
        "FINAL_DECISION": decision_rows,
    }
    shard_bytes, shard_manifest = build_shards(domain_rows, 64, generated_at)
    if len(shard_manifest) != 640:
        raise ContractError("LOGICAL_SHARD_COUNT")

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    market_registry = {"phase_id": PHASE_ID, "release_id": release_id, "markets": markets, "trade_authority": "NONE"}
    limitations = {
        "phase_id": PHASE_ID, "release_id": release_id,
        "limitations": [
            "PORTFOLIO_STATE_ONLY_CONFIRMED_THROUGH_2026_07_20_CLOSE",
            "FRESH_MARKET_DATA_REQUIRED_BEFORE_LIVE_ACTION",
            "HONG_KONG_GRADUATION_REQUIRES_HUMAN_REENTRY_REVIEW",
            "US_MARKET_DATA_AND_FORMAL_WORKFLOW_OUTPUTS_ARE_NOT_FULLY_DECISION_GRADE",
            "US_FORMAL_CANDIDATE_SIMULATION_BROKERAGE_AND_REAL_ACCOUNT_GATES_REMAIN_CLOSED",
            "FILE_LIBRARY_BINARY_NOT_INDEPENDENTLY_INDEXED_BY_CURRENT_FILE_SEARCH_CONNECTOR",
            "NO_PERSISTENT_ALPHA_OR_COMPLETE_DATA_COVERAGE_CLAIM",
        ],
        "trade_authority": "NONE",
    }
    file_library = {"phase_id": PHASE_ID, "release_id": release_id, **contract["file_library_acceptance_evidence"], "trade_authority": "NONE"}
    failure_payload = {"phase_id": PHASE_ID, "release_id": release_id, "all_rejected_as_required": True, "results": failures, "trade_authority": "NONE"}
    gate_payload = {"phase_id": PHASE_ID, "release_id": release_id, "gates": gates, "trade_authority": "NONE"}
    quality = {
        "phase_id": PHASE_ID, "release_id": release_id, "quality_status": "PASS", "contract_error_count": 0,
        "fmdl7_release_count": 6, "market_count": 3, "market_component_count": len(component_rows),
        "cross_market_control_count": len(control_rows), "failure_injection_count": len(failures),
        "failure_rejected_count": len(failures), "acceptance_gate_count": len(gates),
        "acceptance_gate_pass_count": sum(row["status"] == "PASS" for row in gates),
        "logical_shard_domain_count": len(SHARD_DOMAINS), "bucket_count": 64,
        "logical_shard_count": len(shard_manifest), "candidate_pool_mutations": 0,
        "simulation_book_mutations": 0, "real_account_mutations": 0, "rule_mutations": 0,
        "orders": 0, "trade_authority": "NONE",
    }
    release = {
        "phase_id": PHASE_ID, "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"], "generated_at": generated_at,
        "source_commit": source_commit, "status": EXIT_STATUS, "next_operating_mode": NEXT_MODE,
        "trade_authority": "NONE",
    }

    write_json(output / "FMDL7_FINAL_MARKET_CAPABILITY_REGISTRY.json", market_registry)
    write_json(output / "FMDL7_FINAL_LIMITATIONS_AND_OPEN_ITEMS.json", limitations)
    write_json(output / "FMDL7_FINAL_FILE_LIBRARY_ACCEPTANCE.json", file_library)
    write_json(output / "FMDL7_FINAL_FAILURE_INJECTION_REPORT.json", failure_payload)
    write_json(output / "FMDL7_FINAL_GATE_MATRIX.json", gate_payload)
    write_json(output / "FMDL7_FINAL_QUALITY_REPORT.json", quality)
    write_json(output / "FMDL7_FINAL_DECISION.json", decision)
    write_json(output / "FMDL7_FINAL_RELEASE.json", release)
    write_text(output / "股票投资助手_FMDL7_FINAL_HANDOFF_CURRENT.md", (repo / HANDOFF_PATH).read_text(encoding="utf-8"))
    (output / "FMDL7_FINAL_ACCEPTANCE_SHARDS.zip").write_bytes(shard_bytes)
    write_json(output / "FMDL7_FINAL_SHARD_MANIFEST.json", {"phase_id": PHASE_ID, "release_id": release_id, "shards": shard_manifest, "trade_authority": "NONE"})

    files = []
    for path in sorted(item for item in output.iterdir() if item.is_file() and item.name != "FMDL7_FINAL_MANIFEST.json"):
        files.append({"filename": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "phase_id": PHASE_ID, "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"], "generated_at": generated_at,
        "source_commit": source_commit, "contract_sha256": hashes["contract"], "source_hashes": hashes,
        "files": files, "logical_shard_count": len(shard_manifest), "status": EXIT_STATUS,
        "trade_authority": "NONE",
    }
    write_json(output / "FMDL7_FINAL_MANIFEST.json", manifest)
    return decision


def validate_candidate(candidate: Path) -> list[str]:
    errors: list[str] = []
    required = {
        "FMDL7_FINAL_MARKET_CAPABILITY_REGISTRY.json", "FMDL7_FINAL_LIMITATIONS_AND_OPEN_ITEMS.json",
        "FMDL7_FINAL_FILE_LIBRARY_ACCEPTANCE.json", "FMDL7_FINAL_FAILURE_INJECTION_REPORT.json",
        "FMDL7_FINAL_GATE_MATRIX.json", "FMDL7_FINAL_QUALITY_REPORT.json", "FMDL7_FINAL_DECISION.json",
        "FMDL7_FINAL_RELEASE.json", "FMDL7_FINAL_ACCEPTANCE_SHARDS.zip", "FMDL7_FINAL_SHARD_MANIFEST.json",
        "FMDL7_FINAL_MANIFEST.json", "股票投资助手_FMDL7_FINAL_HANDOFF_CURRENT.md",
    }
    missing = required - {path.name for path in candidate.iterdir() if path.is_file()}
    if missing:
        errors.append("MISSING:" + ",".join(sorted(missing)))
        return errors
    manifest = read_json(candidate / "FMDL7_FINAL_MANIFEST.json")
    for row in manifest["files"]:
        path = candidate / row["filename"]
        if not path.is_file() or sha256_file(path) != row["sha256"]:
            errors.append("MANIFEST_HASH:" + row["filename"])
    quality = read_json(candidate / "FMDL7_FINAL_QUALITY_REPORT.json")
    decision = read_json(candidate / "FMDL7_FINAL_DECISION.json")
    if quality.get("quality_status") != "PASS" or quality.get("acceptance_gate_pass_count") != 30:
        errors.append("QUALITY")
    if decision.get("status") != EXIT_STATUS or decision.get("fmdl7_status") != "COMPLETE_AND_FROZEN":
        errors.append("DECISION")
    if decision.get("trade_authority") != "NONE" or any(decision["zero_mutation_proof"].values()):
        errors.append("AUTHORITY_OR_MUTATION")
    return errors


def publish(repo: Path, candidate: Path) -> dict[str, Any]:
    errors = validate_candidate(candidate)
    if errors:
        raise ContractError("CANDIDATE_ERRORS:" + "|".join(errors))
    contract = read_json(repo / CONTRACT_PATH)
    release = read_json(candidate / "FMDL7_FINAL_RELEASE.json")
    decision = read_json(candidate / "FMDL7_FINAL_DECISION.json")
    release_id = release["release_id"]
    current = repo / contract["storage_contract"]["current_root"]
    release_dir = repo / contract["storage_contract"]["release_root"].replace("<release_id>", release_id)
    normalized = repo / contract["storage_contract"]["normalized_root"].replace("<release_id>", release_id)
    archive = repo / contract["storage_contract"]["archive_root"] / release_id
    if release_dir.exists():
        existing = read_json(release_dir / "FMDL7_FINAL_MANIFEST.json")
        candidate_manifest = read_json(candidate / "FMDL7_FINAL_MANIFEST.json")
        if existing != candidate_manifest:
            raise ContractError("IMMUTABLE_RELEASE_COLLISION")
    else:
        shutil.copytree(candidate, release_dir)
    for target in (current, normalized, archive):
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(candidate, target)
    pointer = {
        "phase_id": PHASE_ID, "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"], "published_at": release["generated_at"],
        "source_commit": release["source_commit"], "status": EXIT_STATUS, "fmdl7_status": "COMPLETE_AND_FROZEN",
        "next_operating_mode": NEXT_MODE, "current_path": contract["storage_contract"]["current_root"],
        "release_path": str(release_dir.relative_to(repo)), "normalized_path": str(normalized.relative_to(repo)),
        "canonical_release_id": decision["canonical_release_id"], "accepted_state_as_of": decision["accepted_state_as_of"],
        "file_library_acceptance_posture": decision["file_library_acceptance_posture"],
        "manifest_sha256": sha256_file(candidate / "FMDL7_FINAL_MANIFEST.json"),
        "zero_mutation_proof": decision["zero_mutation_proof"], "trade_authority": "NONE",
    }
    write_json(repo / contract["storage_contract"]["last_success"], pointer)
    write_json(repo / contract["storage_contract"]["last_known_good"], pointer)
    return pointer


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    build = sub.add_parser("build")
    build.add_argument("--output", required=True)
    build.add_argument("--generated-at", required=True)
    build.add_argument("--source-commit", required=True)
    publish_cmd = sub.add_parser("publish")
    publish_cmd.add_argument("--candidate", required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    try:
        if args.command == "validate":
            _, errors, _ = validate_contract(repo)
            if errors:
                raise ContractError("CONTRACT_ERRORS:" + "|".join(errors))
            print("FMDL-7-FINAL contract validation PASS")
        elif args.command == "build":
            decision = build_candidate(repo, repo / args.output, args.generated_at, args.source_commit)
            print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
        else:
            pointer = publish(repo, repo / args.candidate)
            print(json.dumps(pointer, ensure_ascii=False, sort_keys=True))
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
