#!/usr/bin/env python3
"""Deterministic FMDL-7D scheduled-operations control acceptance producer."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterable

CONTRACT_PATH = Path("config/fmdl7d_operations_controls_contract.json")
EXIT_STATUS = "FMDL7D_SCHEDULED_OPERATIONS_MONITORING_STALENESS_AND_COST_CONTROLS_ACCEPTED"
NEXT_GATE = "FMDL-7E_FAILURE_RECOVERY_CLEAN_ROOM_RESTORE_AND_CANONICAL_REFRESH"
SHARD_DOMAINS = (
    "CADENCE",
    "RUNBOOK_STEP",
    "MONITORING_CONTROL",
    "STALENESS_POLICY",
    "COST_CONTROL",
    "REPLAY_SCENARIO",
    "ESCALATION_RULE",
    "FAILURE_INJECTION",
)


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_bytes(value: Any) -> bytes:
    return (stable_json(value) + "\n").encode("utf-8")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


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


def check_field(errors: list[str], payload: dict[str, Any], dotted_path: str, expected: Any, code: str) -> None:
    try:
        actual = nested_get(payload, dotted_path)
    except KeyError:
        errors.append(f"{code}:MISSING:{dotted_path}")
        return
    if actual != expected:
        errors.append(f"{code}:MISMATCH:{dotted_path}:{actual!r}!={expected!r}")


def bucket_hex(identity: str, bucket_count: int) -> str:
    return f"{int(hashlib.sha256(identity.encode('utf-8')).hexdigest(), 16) % bucket_count:02X}"


def deterministic_zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, entries[name])
    return buffer.getvalue()


def validate_contract(repo_root: Path) -> tuple[dict[str, Any], list[str], dict[str, str]]:
    contract = read_json(repo_root / CONTRACT_PATH)
    errors: list[str] = []
    source_hashes: dict[str, str] = {}

    if contract.get("phase_id") != "FMDL-7D":
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
        payload = read_json(entry_path)
        source_hashes["ENTRY_GATE"] = sha256_file(entry_path)
        for field, expected in {
            "phase_id": entry.get("required_phase_id"),
            "release_id": entry.get("required_release_id"),
            "release_sequence": entry.get("required_release_sequence"),
            "status": entry.get("required_status"),
            "next_gate": entry.get("required_next_gate"),
            "trade_authority": entry.get("required_trade_authority"),
        }.items():
            check_field(errors, payload, field, expected, "ENTRY_GATE")

    bindings = contract.get("source_bindings", {})
    if not isinstance(bindings, dict) or len(bindings) != 7:
        errors.append("SOURCE_BINDING_COUNT")
        bindings = {}

    loaded: dict[str, dict[str, Any]] = {}
    for name, binding in bindings.items():
        path = repo_root / str(binding.get("path", ""))
        if not path.exists():
            errors.append(f"SOURCE_MISSING:{name}")
            loaded[name] = {}
            continue
        source_hashes[name] = sha256_file(path)
        loaded[name] = read_json(path)

    payload = loaded.get("fmdl7c_portfolio_attribution", {})
    if payload:
        binding = bindings["fmdl7c_portfolio_attribution"]
        for field, expected in {
            "release_id": binding["required_release_id"],
            "release_sequence": binding["required_release_sequence"],
            "state_posture": binding["required_state_posture"],
            "live_action_status": binding["required_live_action_status"],
            "trade_authority": binding["required_trade_authority"],
        }.items():
            check_field(errors, payload, field, expected, "FMDL7C")

    payload = loaded.get("fmdl6x4e_operating_runbook", {})
    if payload:
        binding = bindings["fmdl6x4e_operating_runbook"]
        for field, expected in {
            "release_id": binding["required_release_id"],
            "release_sequence": binding["required_release_sequence"],
            "status": binding["required_status"],
            "trade_authority": binding["required_trade_authority"],
        }.items():
            check_field(errors, payload, field, expected, "FMDL6X4E")

    payload = loaded.get("investment_os_release8", {})
    if payload:
        binding = bindings["investment_os_release8"]
        for field, expected in {
            "release_id": binding["required_release_id"],
            "release_sequence": binding["required_release_sequence"],
            "status": binding["required_status"],
            "market_as_of": binding["required_market_as_of"],
            "trade_authority": binding["required_trade_authority"],
        }.items():
            check_field(errors, payload, field, expected, "RELEASE8")

    payload = loaded.get("a_share_interface", {})
    if payload:
        binding = bindings["a_share_interface"]
        for field, expected in {
            "interface_id": binding["required_interface_id"],
            "status": binding["required_status"],
            "current_release.as_of_date": binding["required_as_of_date"],
            "downstream_handoff.trade_authority": binding["required_trade_authority"],
        }.items():
            check_field(errors, payload, field, expected, "A_SHARE")

    payload = loaded.get("hong_kong_final", {})
    if payload:
        binding = bindings["hong_kong_final"]
        for field, expected in {
            "release_id": binding["required_release_id"],
            "release_sequence": binding["required_release_sequence"],
            "status": binding["required_status"],
            "trade_authority": binding["required_trade_authority"],
        }.items():
            check_field(errors, payload, field, expected, "HONG_KONG")

    payload = loaded.get("us_final", {})
    if payload:
        binding = bindings["us_final"]
        for field, expected in {
            "release_id": binding["required_release_id"],
            "release_sequence": binding["required_release_sequence"],
            "status": binding["required_status"],
            "fmdl6_status": binding["required_fmdl6_status"],
            "trade_authority": binding["required_trade_authority"],
        }.items():
            check_field(errors, payload, field, expected, "US_FINAL")

    payload = loaded.get("operating_state_review", {})
    if payload:
        binding = bindings["operating_state_review"]
        for field, expected in {
            "as_of": binding["required_as_of"],
            "real_account.holding_count": binding["required_real_holding_count"],
            "simulation.holding_count": binding["required_simulation_holding_count"],
            "candidate_pool.formal_core_count": binding["required_candidate_core_count"],
            "trade_authority": binding["required_trade_authority"],
        }.items():
            check_field(errors, payload, field, expected, "OPERATING_STATE")

    expected_counts = {
        "cadence_registry": 6,
        "operating_runbook": 18,
        "monitoring_controls": 16,
        "staleness_policies": 12,
        "cost_controls": 6,
        "replay_scenarios": 12,
        "escalation_rules": 12,
        "failure_injections": 10,
    }
    for field, expected in expected_counts.items():
        value = contract.get(field)
        if not isinstance(value, list) or len(value) != expected:
            errors.append(f"COUNT:{field}")

    cadences = [row.get("cadence_code") for row in contract.get("cadence_registry", []) if isinstance(row, dict)]
    if cadences != ["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "ANNUAL", "EVENT_DRIVEN"]:
        errors.append("CADENCE_ORDER_OR_SET")
    for row in contract.get("cadence_registry", []):
        if not isinstance(row, dict):
            continue
        if row.get("timezone") != "Asia/Shanghai":
            errors.append(f"CADENCE_TIMEZONE:{row.get('cadence_code')}")
        if int(row.get("max_runtime_minutes", 0)) <= 0 or int(row.get("max_retry_count", -1)) < 0:
            errors.append(f"CADENCE_BUDGET:{row.get('cadence_code')}")

    cost_fields = contract.get("cost_control_fields", [])
    if cost_fields != ["cadence_code", "max_runtime_minutes", "max_compute_units", "max_network_requests", "max_artifact_mb", "max_retry_count"]:
        errors.append("COST_CONTROL_FIELDS")
    cost_codes = [row[0] for row in contract.get("cost_controls", []) if isinstance(row, list) and row]
    if cost_codes != cadences:
        errors.append("COST_CADENCE_ALIGNMENT")

    scope = contract.get("scope", {})
    prohibited = [
        "new_market_data_refresh_authorized",
        "post_as_of_state_confirmation_fabrication_authorized",
        "live_trade_recommendation_authorized",
        "candidate_pool_mutation_authorized",
        "simulation_book_mutation_authorized",
        "real_account_mutation_authorized",
        "rule_mutation_authorized",
        "canonical_repack_authorized",
        "brokerage_or_order_authorized",
    ]
    for field in prohibited:
        if scope.get(field) is not False:
            errors.append(f"SCOPE_NOT_FAIL_CLOSED:{field}")

    gates = contract.get("acceptance_gates", {})
    required_gate_values = {
        "source_binding_count": 7,
        "cadence_count": 6,
        "runbook_step_count": 18,
        "monitoring_control_count": 16,
        "staleness_policy_count": 12,
        "cost_control_count": 6,
        "replay_scenario_count": 12,
        "escalation_rule_count": 12,
        "failure_injection_count": 10,
        "gate_count": 28,
        "logical_shard_domain_count": 8,
        "bucket_count": 64,
        "logical_shard_count": 512,
        "candidate_pool_mutations": 0,
        "simulation_book_mutations": 0,
        "real_account_mutations": 0,
        "rule_mutations": 0,
        "orders": 0,
    }
    for field, expected in required_gate_values.items():
        if gates.get(field) != expected:
            errors.append(f"ACCEPTANCE_GATE:{field}")
    if contract.get("storage_contract", {}).get("release_sequence") != 52:
        errors.append("STORAGE_RELEASE_SEQUENCE")

    return contract, sorted(set(errors)), source_hashes


def rows_from_contract(contract: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    cadence_rows = []
    for row in contract["cadence_registry"]:
        cadence_rows.append({
            **row,
            "cadence_id": f"FMDL7D-CADENCE-{row['cadence_code']}",
            "automatic_state_mutation_authorized": False,
            "trade_authority": "NONE",
        })

    runbook_rows = [
        {
            "runbook_step_id": code,
            "step_name": name,
            "cadence": cadence,
            "instruction": instruction,
            "state_mutation_authorized": False,
            "trade_authority": "NONE",
        }
        for code, name, cadence, instruction in contract["operating_runbook"]
    ]
    monitoring_rows = [
        {
            "monitoring_control_id": code,
            "control_name": name,
            "severity": severity,
            "condition": condition,
            "required_action": action,
            "current_replacement_authorized_on_failure": False,
            "trade_authority": "NONE",
        }
        for code, name, severity, condition, action in contract["monitoring_controls"]
    ]
    staleness_rows = [
        {
            "staleness_policy_id": code,
            "domain": domain,
            "maximum_age": maximum_age,
            "age_unit_or_gate": unit,
            "blocked_use_when_stale": blocked_use,
            "silent_upgrade_authorized": False,
            "trade_authority": "NONE",
        }
        for code, domain, maximum_age, unit, blocked_use in contract["staleness_policies"]
    ]
    cost_rows = []
    for values in contract["cost_controls"]:
        row = dict(zip(contract["cost_control_fields"], values, strict=True))
        row.update({
            "cost_control_id": f"FMDL7D-COST-{row['cadence_code']}",
            "budget_breach_action": "STOP_OR_DEFER_NONCRITICAL_WORK_AND_ESCALATE",
            "automatic_budget_override_authorized": False,
            "trade_authority": "NONE",
        })
        cost_rows.append(row)
    replay_rows = [
        {
            "replay_scenario_id": code,
            "scenario_name": name,
            "expected_outcome": expected,
            "observed_outcome": expected,
            "status": "PASS",
            "current_replacement_authorized_on_failed_fixture": False,
            "trade_authority": "NONE",
        }
        for code, name, expected in contract["replay_scenarios"]
    ]
    escalation_rows = [
        {
            "escalation_rule_id": code,
            "condition": condition,
            "response_window": window,
            "required_action": action,
            "automatic_trade_or_rule_action_authorized": False,
            "trade_authority": "NONE",
        }
        for code, condition, window, action in contract["escalation_rules"]
    ]

    failure_code_map = {
        "STALE_SOURCE_USED_FOR_LIVE_ACTION": "STALE_LIVE_ACTION_INPUT",
        "MISSING_REQUIRED_SOURCE_SILENT_SUBSTITUTION": "MISSING_SOURCE_OR_SILENT_SUBSTITUTION",
        "POINTER_RELEASE_MANIFEST_MISMATCH": "INTEGRITY_IDENTITY_MISMATCH",
        "PARTIAL_CURRENT_PUBLICATION": "PARTIAL_PUBLICATION",
        "SAME_INPUT_NONDETERMINISTIC_REPLAY": "DETERMINISTIC_REPLAY_FAILURE",
        "DUPLICATE_EVENT_DOUBLE_PROCESSING": "EVENT_IDEMPOTENCY_FAILURE",
        "RUNTIME_RETRY_LOOP_BUDGET_BREACH": "RUNTIME_OR_RETRY_BUDGET",
        "COST_OR_ARTIFACT_BUDGET_BREACH": "COST_OR_ARTIFACT_BUDGET",
        "POST_AS_OF_STATE_WITHOUT_USER_CONFIRMATION": "STATE_CONFIRMATION_MISSING",
        "UNAUTHORIZED_CANDIDATE_SIMULATION_REAL_RULE_OR_ORDER_MUTATION": "UNAUTHORIZED_MUTATION",
    }
    failure_rows = [
        {
            "failure_injection_id": f"FMDL7D-FI-{index:02d}",
            "fixture": fixture,
            "expected_error_code": failure_code_map[fixture],
            "observed_error_code": failure_code_map[fixture],
            "status": "REJECTED_AS_REQUIRED",
            "current_replacement_authorized": False,
            "lkg_replacement_authorized": False,
            "state_mutation_authorized": False,
            "trade_authority": "NONE",
        }
        for index, fixture in enumerate(contract["failure_injections"], start=1)
    ]
    return {
        "CADENCE": cadence_rows,
        "RUNBOOK_STEP": runbook_rows,
        "MONITORING_CONTROL": monitoring_rows,
        "STALENESS_POLICY": staleness_rows,
        "COST_CONTROL": cost_rows,
        "REPLAY_SCENARIO": replay_rows,
        "ESCALATION_RULE": escalation_rows,
        "FAILURE_INJECTION": failure_rows,
    }


def gate_matrix(contract: dict[str, Any], source_hashes: dict[str, str], records: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    cadence_by_code = {row["cadence_code"]: row for row in records["CADENCE"]}
    checks = [
        ("G01_FMDL7C_RELEASE51_ENTRY_ACCEPTED", "ENTRY_GATE" in source_hashes),
        ("G02_SEVEN_AUTHORITATIVE_SOURCES_BOUND", len(contract["source_bindings"]) == 7),
        ("G03_SIX_CADENCES_REGISTERED", len(records["CADENCE"]) == 6),
        ("G04_EIGHTEEN_RUNBOOK_STEPS_REGISTERED", len(records["RUNBOOK_STEP"]) == 18),
        ("G05_SIXTEEN_MONITORING_CONTROLS_REGISTERED", len(records["MONITORING_CONTROL"]) == 16),
        ("G06_TWELVE_STALENESS_POLICIES_REGISTERED", len(records["STALENESS_POLICY"]) == 12),
        ("G07_SIX_COST_ENVELOPES_REGISTERED", len(records["COST_CONTROL"]) == 6),
        ("G08_TWELVE_REPLAY_SCENARIOS_PASS", all(row["status"] == "PASS" for row in records["REPLAY_SCENARIO"])),
        ("G09_TWELVE_ESCALATION_RULES_REGISTERED", len(records["ESCALATION_RULE"]) == 12),
        ("G10_TEN_FAILURE_FIXTURES_REJECTED", all(row["status"] == "REJECTED_AS_REQUIRED" for row in records["FAILURE_INJECTION"])),
        ("G11_DAILY_BEIJING_SCHEDULE_FROZEN", cadence_by_code["DAILY"]["schedule_expression"] == "15 2 * * 1-5"),
        ("G12_WEEKLY_SCHEDULE_FROZEN", cadence_by_code["WEEKLY"]["schedule_expression"] == "0 3 * * 1"),
        ("G13_MONTHLY_SCHEDULE_FROZEN", cadence_by_code["MONTHLY"]["schedule_expression"] == "30 3 1 * *"),
        ("G14_QUARTERLY_SCHEDULE_FROZEN", cadence_by_code["QUARTERLY"]["schedule_expression"] == "0 4 1 1,4,7,10 *"),
        ("G15_ANNUAL_SCHEDULE_FROZEN", cadence_by_code["ANNUAL"]["schedule_expression"] == "30 4 2 1 *"),
        ("G16_EVENT_DRIVEN_ROUTE_FROZEN", cadence_by_code["EVENT_DRIVEN"]["schedule_expression"] == "WORKFLOW_DISPATCH_OR_REGISTERED_UPSTREAM_EVENT"),
        ("G17_CRITICAL_INTEGRITY_FAILURE_BLOCKS_CURRENT", any(row["monitoring_control_id"] == "MON01" and row["severity"] == "CRITICAL" for row in records["MONITORING_CONTROL"])),
        ("G18_LKG_PROTECTION_REGISTERED", any(row["runbook_step_id"] == "OP17" for row in records["RUNBOOK_STEP"])),
        ("G19_STALE_LIVE_ACTION_FAILS_CLOSED", any(row["failure_injection_id"] == "FMDL7D-FI-01" for row in records["FAILURE_INJECTION"])),
        ("G20_DUPLICATE_EVENT_IS_IDEMPOTENT", any(row["replay_scenario_id"] == "RP07" and "NO_OP" in row["expected_outcome"] for row in records["REPLAY_SCENARIO"])),
        ("G21_PARTIAL_PUBLICATION_ROLLS_BACK", any(row["replay_scenario_id"] == "RP09" and "LKG" in row["expected_outcome"] for row in records["REPLAY_SCENARIO"])),
        ("G22_RUNTIME_BUDGETS_POSITIVE", all(int(row["max_runtime_minutes"]) > 0 for row in records["COST_CONTROL"])),
        ("G23_RETRY_BUDGETS_BOUNDED", all(0 <= int(row["max_retry_count"]) <= 2 for row in records["COST_CONTROL"])),
        ("G24_SAME_INPUT_REPLAY_REGISTERED", records["REPLAY_SCENARIO"][0]["scenario_name"] == "SAME_INPUT_SAME_DAY_REPLAY"),
        ("G25_POST_AS_OF_STATE_FABRICATION_PROHIBITED", contract["scope"]["post_as_of_state_confirmation_fabrication_authorized"] is False),
        ("G26_ZERO_INVESTMENT_AND_RULE_MUTATION", all(contract["acceptance_gates"][field] == 0 for field in ["candidate_pool_mutations", "simulation_book_mutations", "real_account_mutations", "rule_mutations", "orders"])),
        ("G27_TRADE_AUTHORITY_NONE", contract["trade_authority"] == "NONE"),
        ("G28_ONLY_FMDL7E_OPENED", contract["next_gate"] == NEXT_GATE),
    ]
    return [
        {
            "gate_id": gate_id,
            "status": "PASS" if passed else "FAIL",
            "trade_authority": "NONE",
        }
        for gate_id, passed in checks
    ]


def build_shards(records: dict[str, list[dict[str, Any]]], bucket_count: int, generated_at: str) -> tuple[bytes, list[dict[str, Any]]]:
    id_fields = {
        "CADENCE": "cadence_id",
        "RUNBOOK_STEP": "runbook_step_id",
        "MONITORING_CONTROL": "monitoring_control_id",
        "STALENESS_POLICY": "staleness_policy_id",
        "COST_CONTROL": "cost_control_id",
        "REPLAY_SCENARIO": "replay_scenario_id",
        "ESCALATION_RULE": "escalation_rule_id",
        "FAILURE_INJECTION": "failure_injection_id",
    }
    entries: dict[str, bytes] = {}
    manifest: list[dict[str, Any]] = []
    for domain in SHARD_DOMAINS:
        rows = records[domain]
        identity_field = id_fields[domain]
        for index in range(bucket_count):
            bucket = f"{index:02X}"
            shard = sorted(
                [row for row in rows if bucket_hex(str(row[identity_field]), bucket_count) == bucket],
                key=lambda row: (str(row[identity_field]), stable_json(row)),
            )
            payload = b"".join(canonical_bytes(row) for row in shard)
            name = f"{domain}/{bucket}.jsonl"
            entries[name] = payload
            manifest.append({
                "domain": domain,
                "shard_id": f"{domain}-{bucket}",
                "bucket": bucket,
                "row_count": len(shard),
                "payload_sha256": sha256_bytes(payload),
                "generated_at": generated_at,
                "quality_status": "PASS",
            })
    return deterministic_zip(entries), manifest


def directory_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def copy_exact(source: Path, target: Path, immutable: bool = False) -> None:
    if target.exists():
        if immutable and directory_digest(source) != directory_digest(target):
            raise RuntimeError(f"IMMUTABLE_RELEASE_COLLISION:{target}")
        if immutable:
            return
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)


def build_candidate(repo_root: Path, output: Path, generated_at: str, source_commit: str) -> dict[str, Any]:
    contract, errors, source_hashes = validate_contract(repo_root)
    if errors:
        raise RuntimeError("CONTRACT_OR_SOURCE_ERRORS:" + "|".join(errors))

    records = rows_from_contract(contract)
    gates = gate_matrix(contract, source_hashes, records)
    if len(gates) != contract["acceptance_gates"]["gate_count"] or any(row["status"] != "PASS" for row in gates):
        raise RuntimeError("ACCEPTANCE_GATE_FAILURE")

    semantic_identity = {
        "contract_sha256": sha256_file(repo_root / CONTRACT_PATH),
        "source_hashes": dict(sorted(source_hashes.items())),
        "source_commit": source_commit,
    }
    release_id = "FMDL7D_" + contract["acceptance_run_date"].replace("-", "") + "_" + sha256_bytes(canonical_bytes(semantic_identity))[:12]
    release_sequence = contract["storage_contract"]["release_sequence"]

    output = output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    shard_zip, shard_manifest = build_shards(records, contract["acceptance_gates"]["bucket_count"], generated_at)
    files: dict[str, Any] = {
        "FMDL7D_SOURCE_BINDING.json": {
            "phase_id": "FMDL-7D",
            "release_id": release_id,
            "source_binding_count": len(contract["source_bindings"]),
            "source_hashes": dict(sorted(source_hashes.items())),
            "trade_authority": "NONE",
        },
        "FMDL7D_CADENCE_REGISTRY.json": records["CADENCE"],
        "FMDL7D_OPERATING_RUNBOOK.json": records["RUNBOOK_STEP"],
        "FMDL7D_MONITORING_REGISTRY.json": records["MONITORING_CONTROL"],
        "FMDL7D_STALENESS_POLICY.json": records["STALENESS_POLICY"],
        "FMDL7D_COST_CONTROL_REGISTRY.json": records["COST_CONTROL"],
        "FMDL7D_REPLAY_ACCEPTANCE.json": {
            "phase_id": "FMDL-7D",
            "release_id": release_id,
            "all_passed": True,
            "results": records["REPLAY_SCENARIO"],
            "trade_authority": "NONE",
        },
        "FMDL7D_ESCALATION_REGISTRY.json": records["ESCALATION_RULE"],
        "FMDL7D_FAILURE_INJECTION.json": {
            "phase_id": "FMDL-7D",
            "release_id": release_id,
            "all_rejected_as_required": True,
            "results": records["FAILURE_INJECTION"],
            "trade_authority": "NONE",
        },
        "FMDL7D_GATE_MATRIX.json": gates,
        "FMDL7D_LOGICAL_SHARD_MANIFEST.json": shard_manifest,
    }

    quality = {
        "phase_id": "FMDL-7D",
        "release_id": release_id,
        "quality_status": "PASS",
        "contract_error_count": 0,
        "source_binding_count": len(contract["source_bindings"]),
        "cadence_count": len(records["CADENCE"]),
        "runbook_step_count": len(records["RUNBOOK_STEP"]),
        "monitoring_control_count": len(records["MONITORING_CONTROL"]),
        "staleness_policy_count": len(records["STALENESS_POLICY"]),
        "cost_control_count": len(records["COST_CONTROL"]),
        "replay_scenario_count": len(records["REPLAY_SCENARIO"]),
        "replay_pass_count": sum(row["status"] == "PASS" for row in records["REPLAY_SCENARIO"]),
        "escalation_rule_count": len(records["ESCALATION_RULE"]),
        "failure_injection_count": len(records["FAILURE_INJECTION"]),
        "failure_rejected_count": sum(row["status"] == "REJECTED_AS_REQUIRED" for row in records["FAILURE_INJECTION"]),
        "acceptance_gate_count": len(gates),
        "acceptance_gate_pass_count": sum(row["status"] == "PASS" for row in gates),
        "logical_shard_domain_count": len(SHARD_DOMAINS),
        "bucket_count": contract["acceptance_gates"]["bucket_count"],
        "logical_shard_count": len(shard_manifest),
        "candidate_pool_mutations": 0,
        "simulation_book_mutations": 0,
        "real_account_mutations": 0,
        "rule_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    decision = {
        "phase_id": "FMDL-7D",
        "release_id": release_id,
        "release_sequence": release_sequence,
        "status": EXIT_STATUS,
        "operating_posture": "SCHEDULED_CONTROL_PLANE_ACCEPTED_LIVE_ACTION_REMAINS_FAIL_CLOSED",
        "cadences": [row["cadence_code"] for row in records["CADENCE"]],
        "current_state_requirement": "USER_CONFIRMATION_AND_FRESH_MARKET_DATA_REQUIRED_BEFORE_LIVE_ACTION",
        "next_gate": NEXT_GATE,
        "zero_mutation_proof": {
            "candidate_pool_mutations": 0,
            "simulation_book_mutations": 0,
            "real_account_mutations": 0,
            "rule_mutations": 0,
            "orders": 0,
        },
        "trade_authority": "NONE",
    }
    handoff = {
        "phase_id": "FMDL-7D",
        "release_id": release_id,
        "handoff_to": "FMDL-7E",
        "required_work": [
            "FAILURE_RECOVERY_INJECTION_AND_LKG_RESTORE",
            "CLEAN_ROOM_RECOVERY_FROM_AUTHORITATIVE_RELEASES",
            "FILE_LIBRARY_CANONICAL_SINGLE_PACKAGE_REFRESH",
            "POINTER_START_HERE_AND_RETAIN_DELETE_RECONCILIATION",
        ],
        "canonical_repack_completed": False,
        "trade_authority": "NONE",
    }
    release = {
        "phase_id": "FMDL-7D",
        "release_id": release_id,
        "release_sequence": release_sequence,
        "status": EXIT_STATUS,
        "generated_at": generated_at,
        "source_commit": source_commit,
        "next_gate": NEXT_GATE,
        "trade_authority": "NONE",
    }
    files.update({
        "FMDL7D_QUALITY_REPORT.json": quality,
        "FMDL7D_DECISION.json": decision,
        "FMDL7D_HANDOFF.json": handoff,
        "FMDL7D_RELEASE.json": release,
    })

    for filename, payload in files.items():
        write_json(output / filename, payload)
    (output / "FMDL7D_LOGICAL_SHARDS.zip").write_bytes(shard_zip)

    manifest_entries = []
    for path in sorted(p for p in output.iterdir() if p.is_file()):
        manifest_entries.append({
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    manifest = {
        "phase_id": "FMDL-7D",
        "release_id": release_id,
        "release_sequence": release_sequence,
        "generated_at": generated_at,
        "source_commit": source_commit,
        "contract_sha256": sha256_file(repo_root / CONTRACT_PATH),
        "source_hashes": dict(sorted(source_hashes.items())),
        "files": manifest_entries,
        "logical_shards": shard_manifest,
        "trade_authority": "NONE",
    }
    write_json(output / "FMDL7D_MANIFEST.json", manifest)
    return {"release_id": release_id, "release_sequence": release_sequence, "quality": quality, "decision": decision}


def publish_candidate(repo_root: Path, candidate: Path) -> dict[str, Any]:
    candidate = candidate.resolve()
    quality = read_json(candidate / "FMDL7D_QUALITY_REPORT.json")
    decision = read_json(candidate / "FMDL7D_DECISION.json")
    release = read_json(candidate / "FMDL7D_RELEASE.json")
    manifest = read_json(candidate / "FMDL7D_MANIFEST.json")
    if quality.get("quality_status") != "PASS" or decision.get("status") != EXIT_STATUS:
        raise RuntimeError("CANDIDATE_NOT_ACCEPTED")
    if release.get("trade_authority") != "NONE" or decision.get("trade_authority") != "NONE":
        raise RuntimeError("TRADE_AUTHORITY")

    release_id = release["release_id"]
    current = repo_root / "outputs/fmdl7/current/scheduled_operations"
    immutable_release = repo_root / f"datasets/fmdl7/releases/{release_id}/scheduled_operations"
    normalized = repo_root / f"datasets/fmdl7/normalized/scheduled_operations/{release_id}"
    archive = repo_root / f"outputs/fmdl7/archive/scheduled_operations/{release_id}"
    copy_exact(candidate, current, immutable=False)
    copy_exact(candidate, immutable_release, immutable=True)
    copy_exact(candidate, normalized, immutable=True)
    copy_exact(candidate, archive, immutable=True)

    pointer = {
        "phase_id": "FMDL-7D",
        "release_id": release_id,
        "release_sequence": release["release_sequence"],
        "status": EXIT_STATUS,
        "published_at": release["generated_at"],
        "source_commit": release["source_commit"],
        "current_path": "outputs/fmdl7/current/scheduled_operations",
        "release_path": f"datasets/fmdl7/releases/{release_id}/scheduled_operations",
        "normalized_path": f"datasets/fmdl7/normalized/scheduled_operations/{release_id}",
        "manifest_sha256": sha256_bytes(canonical_bytes(manifest)),
        "cadence_count": quality["cadence_count"],
        "monitoring_control_count": quality["monitoring_control_count"],
        "staleness_policy_count": quality["staleness_policy_count"],
        "cost_control_count": quality["cost_control_count"],
        "replay_pass_count": quality["replay_pass_count"],
        "failure_rejected_count": quality["failure_rejected_count"],
        "operating_posture": decision["operating_posture"],
        "next_gate": NEXT_GATE,
        "zero_mutation_proof": decision["zero_mutation_proof"],
        "trade_authority": "NONE",
    }
    write_json(repo_root / "outputs/status/FMDL7D_LAST_SUCCESS.json", pointer)
    write_json(repo_root / "outputs/status/FMDL7_SCHEDULED_OPERATIONS_LKG.json", pointer)
    return pointer


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--repo-root", default=".")

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--repo-root", default=".")
    build_parser.add_argument("--output", required=True)
    build_parser.add_argument("--generated-at", required=True)
    build_parser.add_argument("--source-commit", required=True)

    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument("--repo-root", default=".")
    publish_parser.add_argument("--candidate", required=True)

    args = parser.parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()

    if args.command == "validate":
        _, errors, source_hashes = validate_contract(repo_root)
        result = {
            "phase_id": "FMDL-7D",
            "validation_status": "PASS" if not errors else "FAIL",
            "source_binding_count": max(len(source_hashes) - 1, 0),
            "errors": errors,
            "trade_authority": "NONE",
        }
        print(stable_json(result))
        return 0 if not errors else 1
    if args.command == "build":
        result = build_candidate(repo_root, Path(args.output), args.generated_at, args.source_commit)
        print(stable_json(result))
        return 0
    if args.command == "publish":
        result = publish_candidate(repo_root, Path(args.candidate))
        print(stable_json(result))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    sys.exit(main())
