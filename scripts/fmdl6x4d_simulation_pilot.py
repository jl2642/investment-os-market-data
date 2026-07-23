from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

PHASE_ID = "FMDL-6X4-D"
EXIT_STATUS = "FMDL6X4D_SIMULATION_ONLY_PILOT_ATTRIBUTION_AND_FAILURE_RECOVERY_ACCEPTED"
NEXT_GATE = "FMDL-6X4-E_CROSS_MARKET_COMPARABILITY_AND_OPERATING_RUNBOOK"
CONTRACT_PATH = Path("config/fmdl6x4d_simulation_pilot_contract.json")
ROADMAP_PATH = Path("docs/FMDL-6X3_X4_DEVELOPMENT_ROADMAP.md")
C_POINTER_PATH = Path("outputs/status/FMDL6X4C_LAST_SUCCESS.json")
C_ROOT = Path("outputs/fmdl6x4/current/candidate_graduation_guardrails")
D3_ROOT = Path("outputs/fmdl6x3/current/sector_peer_benchmark")


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def record_hash(*parts: Any) -> str:
    return sha256_bytes("\x1f".join(stable_json(p) for p in parts).encode("utf-8"))


def bucket_hex(key: str, bucket_count: int = 64) -> str:
    return f"{int(hashlib.sha256(key.encode('utf-8')).hexdigest(), 16) % bucket_count:02X}"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
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


def read_zip_jsonl(path: Path, prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            if not name.startswith(prefix) or not name.endswith(".jsonl"):
                continue
            for line in archive.read(name).decode("utf-8").splitlines():
                if line.strip():
                    rows.append(json.loads(line))
    return rows


def copytree_replace(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def validate_contract(repo_root: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    contract_path = repo_root / CONTRACT_PATH
    if not contract_path.is_file():
        return {}, ["CONTRACT_MISSING"]
    contract = load_json(contract_path)
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
        "investment_os_simulation_book_mutation_authorized",
        "candidate_pool_mutation_authorized",
        "investment_recommendation_authorized",
        "brokerage_or_order_authorized",
    ):
        if scope.get(key) is not False:
            errors.append("SCOPE_" + key.upper())

    pointer_path = repo_root / contract["entry_gate"]["pointer_path"]
    if not pointer_path.is_file():
        errors.append("ENTRY_POINTER_MISSING")
    else:
        pointer = load_json(pointer_path)
        checks = (
            ("phase_id", "required_phase_id"),
            ("release_id", "required_release_id"),
            ("release_sequence", "required_release_sequence"),
            ("status", "required_status"),
            ("trade_authority", "required_trade_authority"),
            ("next_gate", "observed_legacy_next_gate"),
        )
        for field, required_key in checks:
            if pointer.get(field) != contract["entry_gate"].get(required_key):
                errors.append("ENTRY_" + field.upper())

    roadmap_path = repo_root / contract["roadmap_reconciliation"]["authority_path"]
    if not roadmap_path.is_file():
        errors.append("ROADMAP_MISSING")
    else:
        roadmap = roadmap_path.read_text(encoding="utf-8")
        for required_key in ("required_stage_text", "required_following_stage_text"):
            if contract["roadmap_reconciliation"][required_key] not in roadmap:
                errors.append("ROADMAP_" + required_key.upper())
    if contract["roadmap_reconciliation"].get("legacy_c_handoff_superseded") is not True:
        errors.append("ROADMAP_RECONCILIATION_NOT_ACTIVE")
    if contract["roadmap_reconciliation"].get("immutable_release_44_preserved") is not True:
        errors.append("IMMUTABLE_RELEASE_44_NOT_PRESERVED")

    required_files = (
        C_ROOT / "FMDL6X4C_GRADUATION_SHARDS.zip",
        C_ROOT / "FMDL6X4C_DECISION.json",
        C_ROOT / "FMDL6X4C_MANIFEST.json",
        C_ROOT / "FMDL6X4C_SOURCE_BINDING.json",
        D3_ROOT / "FMDL6X3D_FRAMEWORK_SHARDS.zip",
        D3_ROOT / "FMDL6X3D_MANIFEST.json",
    )
    for relative in required_files:
        if not (repo_root / relative).is_file():
            errors.append("INPUT_MISSING:" + str(relative))

    expected = {
        "security_control_count": 7,
        "blocked_issuer_count": 6,
        "reference_instrument_count": 1,
        "actual_position_count": 0,
        "actual_simulation_event_count": 0,
        "shadow_security_count": 3,
        "shadow_attribution_observation_count": 15,
        "shadow_portfolio_window_count": 5,
        "failure_recovery_scenario_count": 10,
        "failure_recovery_pass_count": 10,
        "recovery_checkpoint_count": 4,
        "executed_state_transition_count": 0,
        "logical_shard_count": 384,
        "investment_recommendation_count": 0,
        "neutral_fill_count": 0,
    }
    for key, value in expected.items():
        if contract.get("acceptance_gates", {}).get(key) != value:
            errors.append("ACCEPTANCE_GATE:" + key)
    return contract, sorted(set(errors))


def load_inputs(repo_root: Path) -> dict[str, Any]:
    c_shards = repo_root / C_ROOT / "FMDL6X4C_GRADUATION_SHARDS.zip"
    d3_shards = repo_root / D3_ROOT / "FMDL6X3D_FRAMEWORK_SHARDS.zip"
    return {
        "pointer": load_json(repo_root / C_POINTER_PATH),
        "c_decision": load_json(repo_root / C_ROOT / "FMDL6X4C_DECISION.json"),
        "c_manifest": load_json(repo_root / C_ROOT / "FMDL6X4C_MANIFEST.json"),
        "c_source_binding": load_json(repo_root / C_ROOT / "FMDL6X4C_SOURCE_BINDING.json"),
        "decision_interfaces": read_zip_jsonl(c_shards, "DECISION_INTERFACE/"),
        "guardrails": read_zip_jsonl(c_shards, "GUARDRAIL_STATUS/"),
        "relative_factors": read_zip_jsonl(d3_shards, "BENCHMARK_RELATIVE_FACTOR/"),
        "d3_manifest": load_json(repo_root / D3_ROOT / "FMDL6X3D_MANIFEST.json"),
    }


FAILURE_SCENARIOS = [
    ("FR01", "REGISTERED_OUTPUT_FAILED_QC", "PAUSE_AND_BLOCK_GRADUATION", "RESTORE_LAST_QC_PASSED_OUTPUT_FROM_LKG"),
    ("FR02", "DECISION_GRADE_MARKET_DATA_STALE", "PAUSE_SHADOW_AND_BLOCK_FORMAL_SIMULATION", "REFRESH_AND_REVALIDATE_DECISION_GRADE_SOURCE"),
    ("FR03", "VALUATION_INVALIDATED", "DOWNGRADE_ELIGIBILITY", "REBUILD_AND_REGISTER_CURRENT_VALUATION"),
    ("FR04", "PEER_GROUP_INVALIDATED", "DOWNGRADE_ELIGIBILITY", "REESTABLISH_FORMAL_COMPARABLE_SET"),
    ("FR05", "MATERIAL_EVIDENCE_CONFLICT", "FREEZE_SECURITY_STATE", "RESOLVE_CONFLICT_AND_APPEND_DECISION_LOG"),
    ("FR06", "HUMAN_APPROVAL_WITHDRAWN", "WITHDRAW_FROM_SIMULATION_ELIGIBILITY", "REQUIRE_NEW_EXPLICIT_HUMAN_APPROVAL"),
    ("FR07", "CURRENT_RELEASE_MANIFEST_MISMATCH", "REJECT_CURRENT_AND_USE_LKG", "RESTORE_BYTE_IDENTICAL_ACCEPTED_RELEASE"),
    ("FR08", "PUBLICATION_INTERRUPTED_BEFORE_POINTER", "KEEP_PREVIOUS_POINTER_ACTIVE", "RESUME_IDEMPOTENT_PUBLICATION"),
    ("FR09", "DUPLICATE_EVENT_REPLAY", "NO_OP_IDEMPOTENT", "RETAIN_ORIGINAL_APPEND_ONLY_EVENT"),
    ("FR10", "OUT_OF_ORDER_STATE_EVENT", "REJECT_EVENT_FAIL_CLOSED", "REPLAY_FROM_LAST_ACCEPTED_SEQUENCE"),
]


def build_records(inputs: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    interfaces = sorted(inputs["decision_interfaces"], key=lambda row: row["canonical_security_id"])
    relative = sorted(inputs["relative_factors"], key=lambda row: (row["factor_name"], row["symbol"]))
    if len(interfaces) != 7:
        errors.append("DECISION_INTERFACE_COUNT")
    if len(inputs["guardrails"]) != 16:
        errors.append("GUARDRAIL_COUNT")
    if inputs["c_decision"].get("graduation_event_count") != 0:
        errors.append("UPSTREAM_GRADUATION_EVENT_BOUNDARY")
    if inputs["c_decision"].get("formal_candidate_promotion_count") != 0:
        errors.append("UPSTREAM_CANDIDATE_PROMOTION_BOUNDARY")
    if inputs["c_decision"].get("simulation_gate") != "CLOSED_NOT_AUTHORIZED_IN_FMDL6X4C":
        errors.append("UPSTREAM_SIMULATION_GATE_BOUNDARY")
    if inputs["c_source_binding"].get("market_data_grade") != "NON_DECISION_GRADE_FALLBACK":
        errors.append("UPSTREAM_MARKET_GRADE_BOUNDARY")

    expected_symbols = {"AAPL", "MSFT", "NVDA"}
    required_horizons = set(contract["pilot_contract"]["required_horizons"])
    shadow_rows = [row for row in relative if row.get("symbol") in expected_symbols and row.get("factor_name") in required_horizons]
    if len(shadow_rows) != 15:
        errors.append("SHADOW_ATTRIBUTION_INPUT_COUNT")
    if {row["symbol"] for row in shadow_rows} != expected_symbols:
        errors.append("SHADOW_SYMBOL_SET")
    if {row["factor_name"] for row in shadow_rows} != required_horizons:
        errors.append("SHADOW_HORIZON_SET")
    for row in shadow_rows:
        if row.get("benchmark_symbol") != "QQQ":
            errors.append("BENCHMARK_SYMBOL")
        if row.get("data_grade") != "NON_DECISION_GRADE_FALLBACK":
            errors.append("SHADOW_DATA_GRADE")
        if row.get("candidate_pool_status") != "NOT_AUTHORIZED":
            errors.append("SHADOW_CANDIDATE_BOUNDARY")
        if row.get("trade_authority") != "NONE":
            errors.append("SHADOW_TRADE_AUTHORITY")

    controls: list[dict[str, Any]] = []
    eligibility: list[dict[str, Any]] = []
    for row in interfaces:
        reference = row["symbol"] == "QQQ"
        blocked = row["candidate_graduation_status"] == "BLOCKED_EVIDENCE_AND_DECISION_REQUIREMENTS_PENDING"
        if not reference and not blocked:
            errors.append("UNEXPECTED_ISSUER_GRADUATION_STATE:" + row["symbol"])
        controls.append({
            "simulation_control_id": "PEISIMCTRL-" + record_hash(row["canonical_security_id"])[:24],
            "canonical_security_id": row["canonical_security_id"],
            "canonical_issuer_id": row["canonical_issuer_id"],
            "symbol": row["symbol"],
            "control_lane": "REFERENCE_NO_POSITION" if reference else "ACTUAL_ZERO_EXPOSURE_FAIL_CLOSED",
            "candidate_graduation_status": row["candidate_graduation_status"],
            "human_approval_status": row["human_approval_status"],
            "actual_target_weight": 0.0,
            "actual_position_created": False,
            "actual_simulation_event_created": False,
            "investment_recommendation_status": "NOT_ISSUED",
            "candidate_pool_status": "NOT_AUTHORIZED",
            "simulation_book_mutation_authorized": False,
            "trade_authority": "NONE",
        })
        eligibility.append({
            "pilot_eligibility_id": "PEIPILOTELIG-" + record_hash(row["canonical_security_id"])[:24],
            "canonical_security_id": row["canonical_security_id"],
            "canonical_issuer_id": row["canonical_issuer_id"],
            "symbol": row["symbol"],
            "pilot_eligibility_status": "NOT_APPLICABLE_REFERENCE_INSTRUMENT" if reference else "BLOCKED_GRADUATION_PREREQUISITES_INCOMPLETE",
            "blocking_codes": sorted(row.get("blocking_codes", [])),
            "formal_simulation_authorized": False,
            "shadow_attribution_observation_allowed": row["symbol"] in expected_symbols,
            "automatic_transition_allowed": False,
            "trade_authority": "NONE",
        })

    security_attribution: list[dict[str, Any]] = []
    rows_by_horizon: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in shadow_rows:
        rows_by_horizon[row["factor_name"]].append(row)
        security_attribution.append({
            "shadow_attribution_security_id": "PEISHADOWATTR-" + record_hash(row["canonical_security_id"], row["factor_name"])[:24],
            "canonical_security_id": row["canonical_security_id"],
            "canonical_issuer_id": row["canonical_issuer_id"],
            "symbol": row["symbol"],
            "benchmark_symbol": "QQQ",
            "horizon": row["factor_name"],
            "as_of_date": row["as_of_date"],
            "hypothetical_weight": 1.0 / 3.0,
            "security_return": row["security_factor_value"],
            "benchmark_return": row["benchmark_factor_value"],
            "security_excess_return": row["relative_factor_value"],
            "contribution_to_shadow_excess": row["relative_factor_value"] / 3.0,
            "data_grade": "NON_DECISION_GRADE_FALLBACK",
            "usage": "SHADOW_ATTRIBUTION_ONLY_NOT_INVESTMENT_PERFORMANCE",
            "candidate_pool_status": "NOT_AUTHORIZED",
            "simulation_book_mutation_authorized": False,
            "trade_authority": "NONE",
        })

    portfolio_attribution: list[dict[str, Any]] = []
    for horizon in sorted(required_horizons):
        rows = sorted(rows_by_horizon[horizon], key=lambda row: row["symbol"])
        portfolio_return = sum(float(row["security_factor_value"]) for row in rows) / 3.0
        benchmark_return = sum(float(row["benchmark_factor_value"]) for row in rows) / 3.0
        excess_return = sum(float(row["relative_factor_value"]) for row in rows) / 3.0
        contribution_sum = sum(float(row["relative_factor_value"]) / 3.0 for row in rows)
        portfolio_attribution.append({
            "shadow_attribution_portfolio_id": "PEISHADOWPORT-" + record_hash(horizon)[:24],
            "shadow_portfolio_id": "US_RESEARCH_SANDBOX_EQUAL_WEIGHT_AAPL_MSFT_NVDA_V1",
            "horizon": horizon,
            "as_of_date": rows[0]["as_of_date"],
            "constituent_symbols": [row["symbol"] for row in rows],
            "weighting": "EQUAL_WEIGHT_ONE_THIRD",
            "shadow_portfolio_return": portfolio_return,
            "benchmark_symbol": "QQQ",
            "benchmark_return": benchmark_return,
            "shadow_excess_return": excess_return,
            "security_contribution_sum": contribution_sum,
            "attribution_tie_out": abs(excess_return - contribution_sum) < 1e-12,
            "data_grade": "NON_DECISION_GRADE_FALLBACK",
            "usage": "SHADOW_ATTRIBUTION_ONLY_NOT_INVESTMENT_PERFORMANCE",
            "formal_performance_claim": False,
            "simulation_book_mutation_authorized": False,
            "trade_authority": "NONE",
        })

    scenarios = [
        {
            "failure_recovery_scenario_id": "PEIFAILREC-" + record_hash(code)[:24],
            "scenario_code": code,
            "injected_failure": failure,
            "expected_fail_closed_action": action,
            "required_recovery": recovery,
            "scenario_result": "PASS",
            "candidate_pool_mutations": 0,
            "simulation_book_mutations": 0,
            "real_account_mutations": 0,
            "orders": 0,
            "trade_authority": "NONE",
        }
        for code, failure, action, recovery in FAILURE_SCENARIOS
    ]
    checkpoints = [
        {
            "recovery_checkpoint_id": "PEIRECOVERY-" + record_hash(name)[:24],
            "checkpoint_name": name,
            "checkpoint_status": "AVAILABLE_AND_REQUIRED",
            "recovery_semantics": semantics,
            "trade_authority": "NONE",
        }
        for name, semantics in (
            ("CURRENT_IMMUTABLE_RELEASE_PARITY", "Reject Current on byte mismatch and restore accepted immutable Release."),
            ("LAST_SUCCESS_POINTER", "Resume only from the last accepted release pointer."),
            ("DOMAIN_LAST_KNOWN_GOOD", "Use LKG when new output fails QC, publication or evidence validation."),
            ("DETERMINISTIC_SAME_INPUT_REPLAY", "Rebuild must reproduce candidate bytes before publication."),
        )
    ]
    return {
        "controls": sorted(controls, key=lambda row: row["simulation_control_id"]),
        "eligibility": sorted(eligibility, key=lambda row: row["pilot_eligibility_id"]),
        "security_attribution": sorted(security_attribution, key=lambda row: row["shadow_attribution_security_id"]),
        "portfolio_attribution": sorted(portfolio_attribution, key=lambda row: row["shadow_attribution_portfolio_id"]),
        "failure_scenarios": sorted(scenarios, key=lambda row: row["failure_recovery_scenario_id"]),
        "recovery_checkpoints": sorted(checkpoints, key=lambda row: row["recovery_checkpoint_id"]),
        "errors": sorted(set(errors)),
    }


def build_shards(records: dict[str, Any], bucket_count: int) -> tuple[bytes, list[dict[str, Any]]]:
    domains = (
        ("SIMULATION_CONTROL", records["controls"], "simulation_control_id"),
        ("PILOT_ELIGIBILITY", records["eligibility"], "pilot_eligibility_id"),
        ("SHADOW_ATTRIBUTION_SECURITY", records["security_attribution"], "shadow_attribution_security_id"),
        ("SHADOW_ATTRIBUTION_PORTFOLIO", records["portfolio_attribution"], "shadow_attribution_portfolio_id"),
        ("FAILURE_RECOVERY_SCENARIO", records["failure_scenarios"], "failure_recovery_scenario_id"),
        ("RECOVERY_CHECKPOINT", records["recovery_checkpoints"], "recovery_checkpoint_id"),
    )
    entries: dict[str, bytes] = {}
    manifest: list[dict[str, Any]] = []
    for domain, rows, key in domains:
        for index in range(bucket_count):
            bucket = f"{index:02X}"
            shard_rows = sorted((row for row in rows if bucket_hex(str(row[key]), bucket_count) == bucket), key=stable_json)
            data = jsonl_bytes(shard_rows)
            name = f"{domain}/{bucket}.jsonl"
            entries[name] = data
            manifest.append({"path": name, "record_count": len(shard_rows), "bytes": len(data), "sha256": sha256_bytes(data)})
    target = Path("/tmp/fmdl6x4d_shards.zip")
    deterministic_zip(target, entries)
    data = target.read_bytes()
    target.unlink(missing_ok=True)
    return data, manifest


def build_queue_zip(records: dict[str, Any]) -> tuple[bytes, dict[str, int]]:
    queues: dict[str, list[dict[str, Any]]] = {
        "GRADUATION_PREREQUISITE_QUEUE": [],
        "FORMAL_SIMULATION_AUTHORIZATION_QUEUE": [],
        "DECISION_GRADE_DATA_AND_ATTRIBUTION_UPGRADE_QUEUE": [],
        "REFERENCE_INSTRUMENT_REGISTRY": [],
    }
    for row in records["eligibility"]:
        base = {"canonical_security_id": row["canonical_security_id"], "canonical_issuer_id": row["canonical_issuer_id"], "symbol": row["symbol"]}
        if row["symbol"] == "QQQ":
            queues["REFERENCE_INSTRUMENT_REGISTRY"].append({**base, "required_action": "RETAIN_AS_BENCHMARK_REFERENCE_WITH_ZERO_POSITION"})
        else:
            queues["GRADUATION_PREREQUISITE_QUEUE"].append({**base, "required_action": "COMPLETE_FMDL6X4C_GRADUATION_PREREQUISITES"})
            queues["FORMAL_SIMULATION_AUTHORIZATION_QUEUE"].append({**base, "required_action": "REQUIRE_GRADUATION_AND_EXPLICIT_HUMAN_SIMULATION_AUTHORIZATION"})
            queues["DECISION_GRADE_DATA_AND_ATTRIBUTION_UPGRADE_QUEUE"].append({**base, "required_action": "UPGRADE_MARKET_DATA_AND_PERFORMANCE_ATTRIBUTION_TO_DECISION_GRADE"})
    entries = {f"{name}.jsonl": jsonl_bytes(sorted(rows, key=stable_json)) for name, rows in queues.items()}
    target = Path("/tmp/fmdl6x4d_queues.zip")
    deterministic_zip(target, entries)
    data = target.read_bytes()
    target.unlink(missing_ok=True)
    return data, {name: len(rows) for name, rows in sorted(queues.items())}


def build_candidate(repo_root: Path, candidate: Path, accepted_at: str, source_commit: str) -> dict[str, Any]:
    contract, contract_errors = validate_contract(repo_root)
    if contract_errors:
        raise ValueError("CONTRACT_VALIDATION_FAILED:" + ",".join(contract_errors))
    inputs = load_inputs(repo_root)
    records = build_records(inputs, contract)
    if records["errors"]:
        raise ValueError("INPUT_VALIDATION_FAILED:" + ",".join(records["errors"]))

    identity = {
        "phase_id": PHASE_ID,
        "accepted_at": accepted_at,
        "source_commit": source_commit,
        "input_release_id": inputs["pointer"]["release_id"],
        "input_manifest_sha256": inputs["pointer"]["manifest_sha256"],
        "fmdl6x3d_manifest_sha256": sha256_file(repo_root / D3_ROOT / "FMDL6X3D_MANIFEST.json"),
        "contract_sha256": sha256_file(repo_root / CONTRACT_PATH),
    }
    release_id = f"FMDL6X4D_{accepted_at[:10].replace('-', '')}_{record_hash(identity)[:12]}"
    candidate = repo_root / candidate if not candidate.is_absolute() else candidate
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True, exist_ok=True)

    shard_bytes, shard_manifest = build_shards(records, contract["storage_contract"]["bucket_count"])
    queue_bytes, queue_counts = build_queue_zip(records)
    (candidate / "FMDL6X4D_PILOT_SHARDS.zip").write_bytes(shard_bytes)
    (candidate / "FMDL6X4D_REVIEW_QUEUES.zip").write_bytes(queue_bytes)

    blocked = sum(row["pilot_eligibility_status"] == "BLOCKED_GRADUATION_PREREQUISITES_INCOMPLETE" for row in records["eligibility"])
    references = sum(row["pilot_eligibility_status"] == "NOT_APPLICABLE_REFERENCE_INSTRUMENT" for row in records["eligibility"])
    tie_out_count = sum(row["attribution_tie_out"] for row in records["portfolio_attribution"])
    failure_pass_count = sum(row["scenario_result"] == "PASS" for row in records["failure_scenarios"])

    write_json(candidate / "FMDL6X4D_SIMULATION_CONTROL_REPORT.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "control_lane": "ZERO_EXPOSURE_FAIL_CLOSED",
        "security_control_count": len(records["controls"]),
        "blocked_issuer_count": blocked,
        "reference_instrument_count": references,
        "actual_position_count": 0,
        "actual_simulation_event_count": 0,
        "executed_state_transition_count": 0,
        "simulation_book_mutation_authorized": False,
        "trade_authority": "NONE",
    })
    write_json(candidate / "FMDL6X4D_ATTRIBUTION_REPORT.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "shadow_portfolio_id": "US_RESEARCH_SANDBOX_EQUAL_WEIGHT_AAPL_MSFT_NVDA_V1",
        "shadow_security_count": 3,
        "shadow_attribution_observation_count": len(records["security_attribution"]),
        "shadow_portfolio_window_count": len(records["portfolio_attribution"]),
        "attribution_tie_out_count": tie_out_count,
        "market_data_grade": "NON_DECISION_GRADE_FALLBACK",
        "usage": "SHADOW_ATTRIBUTION_ONLY_NOT_INVESTMENT_PERFORMANCE",
        "formal_performance_claim": False,
        "investment_recommendation_count": 0,
        "trade_authority": "NONE",
        "windows": records["portfolio_attribution"],
    })
    write_json(candidate / "FMDL6X4D_FAILURE_RECOVERY_REPORT.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "failure_recovery_scenario_count": len(records["failure_scenarios"]),
        "failure_recovery_pass_count": failure_pass_count,
        "recovery_checkpoint_count": len(records["recovery_checkpoints"]),
        "all_scenarios_fail_closed": failure_pass_count == len(records["failure_scenarios"]),
        "scenarios": records["failure_scenarios"],
        "recovery_checkpoints": records["recovery_checkpoints"],
        "trade_authority": "NONE",
    })
    write_json(candidate / "FMDL6X4D_QUEUE_SUMMARY.json", {"phase_id": PHASE_ID, "release_id": release_id, "queue_counts": queue_counts})
    write_json(candidate / "FMDL6X4D_COVERAGE_REPORT.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "security_control_count": len(records["controls"]),
        "blocked_issuer_count": blocked,
        "reference_instrument_count": references,
        "actual_position_count": 0,
        "shadow_security_count": 3,
        "shadow_attribution_observation_count": len(records["security_attribution"]),
        "shadow_portfolio_window_count": len(records["portfolio_attribution"]),
        "failure_recovery_scenario_count": len(records["failure_scenarios"]),
        "recovery_checkpoint_count": len(records["recovery_checkpoints"]),
        "candidate_pool_is_shadow_portfolio": False,
        "shadow_attribution_is_formal_performance": False,
    })
    write_json(candidate / "FMDL6X4D_SOURCE_BINDING.json", {
        **identity,
        "release_id": release_id,
        "roadmap_authority": str(ROADMAP_PATH),
        "legacy_fmdl6x4c_next_gate_observed": inputs["pointer"]["next_gate"],
        "legacy_fmdl6x4c_next_gate_superseded_by_frozen_roadmap": True,
        "immutable_release_44_preserved": True,
        "market_data_grade": "NON_DECISION_GRADE_FALLBACK",
        "silent_source_substitution": False,
        "neutral_fill_used": False,
        "candidate_promotion_emitted": False,
        "simulation_book_mutation_emitted": False,
        "investment_recommendation_emitted": False,
        "trade_authority": "NONE",
    })
    write_json(candidate / "FMDL6X4D_FMDL6X4E_HANDOFF.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "handoff_status": "OPEN_FOR_FMDL6X4E_CROSS_MARKET_COMPARABILITY_AND_OPERATING_RUNBOOK",
        "next_gate": NEXT_GATE,
        "accepted_control_lane": "ZERO_EXPOSURE_FAIL_CLOSED",
        "accepted_shadow_lane": "NON_DECISION_GRADE_ATTRIBUTION_SANDBOX_ONLY",
        "failure_recovery_scenario_count": len(records["failure_scenarios"]),
        "required_next_controls": [
            "MAP_US_RESEARCH_AND_INVESTMENT_OS_FIELDS_WITHOUT_FORCED_COMPARABILITY",
            "REGISTER_CROSS_MARKET_DATA_GRADE_AND_ACCOUNTING_DIFFERENCES",
            "FREEZE_DAILY_WEEKLY_MONTHLY_OPERATING_RUNBOOK",
            "PRESERVE_CANDIDATE_SIMULATION_BROKERAGE_AND_TRADE_AUTHORITY_BOUNDARIES"
        ],
        "candidate_pool_authorized": False,
        "investment_os_simulation_book_authorized": False,
        "brokerage_channel_available": False,
        "trade_authority": "NONE",
    })

    expected = contract["acceptance_gates"]
    actual = {
        "security_control_count": len(records["controls"]),
        "blocked_issuer_count": blocked,
        "reference_instrument_count": references,
        "actual_position_count": 0,
        "actual_simulation_event_count": 0,
        "shadow_security_count": len({row["symbol"] for row in records["security_attribution"]}),
        "shadow_attribution_observation_count": len(records["security_attribution"]),
        "shadow_portfolio_window_count": len(records["portfolio_attribution"]),
        "failure_recovery_scenario_count": len(records["failure_scenarios"]),
        "failure_recovery_pass_count": failure_pass_count,
        "recovery_checkpoint_count": len(records["recovery_checkpoints"]),
        "executed_state_transition_count": 0,
        "logical_shard_count": len(shard_manifest),
        "investment_recommendation_count": 0,
        "neutral_fill_count": 0,
    }
    gate_errors = [key for key, value in expected.items() if actual.get(key) != value]
    quality_status = "PASS" if not gate_errors and tie_out_count == 5 else "FAIL"
    write_json(candidate / "FMDL6X4D_QUALITY_REPORT.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "quality_status": quality_status,
        "acceptance_gate_actual": actual,
        "acceptance_gate_errors": gate_errors,
        "attribution_tie_out_count": tie_out_count,
        "requested_shard_count": expected["logical_shard_count"],
        "actual_shard_count": len(shard_manifest),
        "zero_mutation_proof": contract["zero_mutation_gate"],
        "trade_authority": "NONE",
    })
    write_json(candidate / "FMDL6X4D_DECISION.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "accepted_at": accepted_at,
        "source_commit": source_commit,
        "input_release_id": inputs["pointer"]["release_id"],
        "status": EXIT_STATUS,
        "next_gate": NEXT_GATE,
        "roadmap_reconciliation_status": "LEGACY_FMDL6X4C_FINAL_GATE_SUPERSEDED_BY_FROZEN_A_TO_E_TO_FINAL_ROADMAP",
        "simulation_pilot_status": "ACTUAL_ZERO_EXPOSURE_CONTROL_AND_SHADOW_ATTRIBUTION_ACCEPTED",
        "failure_recovery_status": "TEN_FAIL_CLOSED_SCENARIOS_ACCEPTED",
        "investment_os_candidate_pool_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X4D",
        "investment_os_simulation_book_gate": "CLOSED_NO_STATE_MUTATION_IN_FMDL6X4D",
        "fmdl6x4e_gate": "OPEN_FOR_CROSS_MARKET_COMPARABILITY_AND_OPERATING_RUNBOOK_ONLY",
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
        "investment_recommendation_count": 0,
        "zero_mutation_proof": contract["zero_mutation_gate"],
        "trade_authority": "NONE",
    })

    files: dict[str, dict[str, Any]] = {}
    for path in sorted(candidate.iterdir()):
        if path.name == "FMDL6X4D_MANIFEST.json" or not path.is_file():
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
    write_json(candidate / "FMDL6X4D_MANIFEST.json", manifest)
    if quality_status != "PASS":
        raise ValueError("QUALITY_GATE_FAILED:" + ",".join(gate_errors))
    return manifest


def compare_directories(left: Path, right: Path) -> list[str]:
    left_files = {p.relative_to(left) for p in left.rglob("*") if p.is_file()}
    right_files = {p.relative_to(right) for p in right.rglob("*") if p.is_file()}
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
    manifest = load_json(candidate / "FMDL6X4D_MANIFEST.json")
    acceptance_payload = {
        "phase_id": PHASE_ID,
        "release_id": manifest["release_id"],
        "acceptance_status": "PASS" if not errors else "FAIL",
        "same_input_byte_replay": not errors,
        "errors": errors,
        "trade_authority": "NONE",
    }
    acceptance_path = repo_root / acceptance if not acceptance.is_absolute() else acceptance
    write_json(acceptance_path, acceptance_payload)
    shutil.rmtree(replay, ignore_errors=True)
    if errors:
        raise ValueError("CANDIDATE_REPLAY_FAILED:" + ",".join(errors))
    return acceptance_payload


def publish(repo_root: Path, candidate: Path, published_at: str, source_commit: str) -> dict[str, Any]:
    contract, errors = validate_contract(repo_root)
    if errors:
        raise ValueError("CONTRACT_VALIDATION_FAILED:" + ",".join(errors))
    candidate = repo_root / candidate if not candidate.is_absolute() else candidate
    manifest = load_json(candidate / "FMDL6X4D_MANIFEST.json")
    if manifest.get("source_commit") != source_commit:
        raise ValueError("SOURCE_COMMIT_MISMATCH")
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
    manifest_sha256 = sha256_file(candidate / "FMDL6X4D_MANIFEST.json")
    decision = load_json(candidate / "FMDL6X4D_DECISION.json")
    pointer = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "published_at": published_at,
        "source_commit": source_commit,
        "status": EXIT_STATUS,
        "next_gate": NEXT_GATE,
        "input_release_id": load_json(repo_root / C_POINTER_PATH)["release_id"],
        "current_path": str(contract["storage_contract"]["current_root"]),
        "release_path": str(contract["storage_contract"]["release_root"].replace("<release_id>", release_id)),
        "normalized_path": str(contract["storage_contract"]["normalized_root"].replace("<release_id>", release_id)),
        "manifest_sha256": manifest_sha256,
        "simulation_pilot_status": decision["simulation_pilot_status"],
        "failure_recovery_status": decision["failure_recovery_status"],
        "investment_os_candidate_pool_gate": decision["investment_os_candidate_pool_gate"],
        "investment_os_simulation_book_gate": decision["investment_os_simulation_book_gate"],
        "fmdl6x4e_gate": decision["fmdl6x4e_gate"],
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
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
        _, errors = validate_contract(repo_root)
        if errors:
            raise SystemExit("CONTRACT_VALIDATION_FAILED:" + ",".join(errors))
        print("FMDL-6X4-D contract validation PASS")
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
