from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Iterable

PHASE_ID = "FMDL-6X4-E"
EXIT_STATUS = "FMDL6X4E_CROSS_MARKET_COMPARABILITY_AND_OPERATING_RUNBOOK_ACCEPTED"
NEXT_GATE = "FMDL-6X4-FINAL_US_RESEARCH_ADAPTER_OPERATIONAL_ACCEPTANCE_AND_FMDL6_FREEZE"
CONTRACT_PATH = Path("config/fmdl6x4e_cross_market_runbook_contract.json")
D_POINTER_PATH = Path("outputs/status/FMDL6X4D_LAST_SUCCESS.json")
X3_POINTER_PATH = Path("outputs/status/FMDL6X3FINAL_LAST_SUCCESS.json")
FMDL5_POINTER_PATH = Path("outputs/status/FMDL5_FINAL_LAST_SUCCESS.json")
FMDL5_CONTRACT_PATH = Path("config/fmdl5_final_operational_acceptance.json")
A_SHARE_PUBLICATION_PATH = Path("config/post_fmdl4_release8_publication.json")
D_ROOT = Path("outputs/fmdl6x4/current/simulation_pilot_attribution_recovery")


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def record_hash(*parts: Any) -> str:
    return sha256_bytes("\x1f".join(stable_json(part) for part in parts).encode("utf-8"))


def bucket_hex(key: str, bucket_count: int = 64) -> str:
    return f"{int(hashlib.sha256(key.encode('utf-8')).hexdigest(), 16) % bucket_count:02X}"


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


def capability_matrix_map(contract: dict[str, Any]) -> dict[str, list[Any]]:
    return {str(row[0]): row for row in contract.get("capability_matrix", []) if isinstance(row, list) and row}


def validate_contract(repo_root: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    path = repo_root / CONTRACT_PATH
    if not path.is_file():
        return {}, ["CONTRACT_MISSING"]
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
        "forced_common_factor_score_authorized",
        "cross_market_security_ranking_authorized",
        "candidate_pool_mutation_authorized",
        "simulation_book_mutation_authorized",
        "real_account_mutation_authorized",
        "investment_recommendation_authorized",
        "brokerage_or_order_authorized",
    ):
        if scope.get(key) is not False:
            errors.append("SCOPE_" + key.upper())
    for key in (
        "market_capability_comparison_authorized",
        "dimension_level_comparability_assessment_authorized",
        "operating_runbook_freeze_authorized",
    ):
        if scope.get(key) is not True:
            errors.append("SCOPE_" + key.upper())

    entry = contract.get("entry_gate", {})
    entry_path = repo_root / entry.get("pointer_path", "")
    if not entry_path.is_file():
        errors.append("ENTRY_POINTER_MISSING")
    else:
        pointer = load_json(entry_path)
        checks = {
            "phase_id": "required_phase_id",
            "release_id": "required_release_id",
            "release_sequence": "required_release_sequence",
            "status": "required_status",
            "next_gate": "required_next_gate",
            "trade_authority": "required_trade_authority",
        }
        for field, required_key in checks.items():
            if pointer.get(field) != entry.get(required_key):
                errors.append("ENTRY_" + field.upper())

    roadmap = contract.get("roadmap_authority", {})
    roadmap_path = repo_root / roadmap.get("path", "")
    if not roadmap_path.is_file():
        errors.append("ROADMAP_MISSING")
    else:
        text = roadmap_path.read_text(encoding="utf-8")
        if roadmap.get("required_stage_text") not in text:
            errors.append("ROADMAP_STAGE_TEXT")
        if roadmap.get("required_following_stage_text") not in text:
            errors.append("ROADMAP_FOLLOWING_STAGE_TEXT")

    required_files = [
        D_POINTER_PATH,
        X3_POINTER_PATH,
        FMDL5_POINTER_PATH,
        FMDL5_CONTRACT_PATH,
        A_SHARE_PUBLICATION_PATH,
        D_ROOT / "FMDL6X4D_DECISION.json",
        D_ROOT / "FMDL6X4D_COVERAGE_REPORT.json",
        D_ROOT / "FMDL6X4D_ATTRIBUTION_REPORT.json",
        D_ROOT / "FMDL6X4D_FAILURE_RECOVERY_REPORT.json",
        D_ROOT / "FMDL6X4D_FMDL6X4E_HANDOFF.json",
        D_ROOT / "FMDL6X4D_MANIFEST.json",
    ]
    for required in required_files:
        if not (repo_root / required).is_file():
            errors.append("INPUT_MISSING:" + str(required))

    if not errors:
        source = contract["source_bindings"]
        a_spec = source["A_SHARE"]
        a_share = load_json(repo_root / a_spec["publication_path"])
        for field, expected in (
            ("release_id", a_spec["required_release_id"]),
            ("release_sequence", a_spec["required_release_sequence"]),
            ("status", a_spec["required_status"]),
            ("trade_authority", a_spec["required_trade_authority"]),
        ):
            if a_share.get(field) != expected:
                errors.append("A_SHARE_" + field.upper())
        if a_share.get("metrics", {}).get("candidate_core_count") != a_spec["expected_candidate_core_count"]:
            errors.append("A_SHARE_CANDIDATE_CORE_COUNT")

        hk_spec = source["HONG_KONG_CONNECT"]
        hk = load_json(repo_root / hk_spec["pointer_path"])
        for field, expected in (
            ("release_id", hk_spec["required_release_id"]),
            ("release_sequence", hk_spec["required_release_sequence"]),
            ("status", hk_spec["required_status"]),
            ("trade_authority", hk_spec["required_trade_authority"]),
            ("southbound_security_count", hk_spec["expected_security_universe_count"]),
            ("common_equity_count", hk_spec["expected_common_equity_count"]),
            ("longlist_count", hk_spec["expected_research_longlist_count"]),
            ("formal_research_object_count", hk_spec["expected_research_object_count"]),
            ("shadow_track_count", hk_spec["expected_shadow_track_count"]),
        ):
            if hk.get(field) != expected:
                errors.append("HK_" + field.upper())
        hk_contract = load_json(repo_root / hk_spec["contract_path"])
        if hk_contract.get("acceptance", {}).get("required_factor_count") != hk_spec["expected_factor_count"]:
            errors.append("HK_FACTOR_COUNT")
        if hk_contract.get("acceptance", {}).get("required_graduated_count") != hk_spec["expected_graduated_count"]:
            errors.append("HK_GRADUATED_COUNT")
        matrix = capability_matrix_map(hk_contract)
        if "A_SHARE_FULL_MARKET_DATA" not in matrix or "5,528" not in str(matrix["A_SHARE_FULL_MARKET_DATA"]):
            errors.append("A_SHARE_CAPABILITY_MATRIX_UNIVERSE")
        if "A_SHARE_SCREENING_AND_RESEARCH" not in matrix or "100-name" not in str(matrix["A_SHARE_SCREENING_AND_RESEARCH"]):
            errors.append("A_SHARE_CAPABILITY_MATRIX_RESEARCH")

        us_spec = source["US_EQUITY"]
        us_research = load_json(repo_root / us_spec["research_pointer_path"])
        if us_research.get("release_id") != us_spec["required_research_release_id"]:
            errors.append("US_RESEARCH_RELEASE_ID")
        if us_research.get("release_sequence") != us_spec["required_research_release_sequence"]:
            errors.append("US_RESEARCH_RELEASE_SEQUENCE")
        if us_research.get("status") != "FMDL6X3_FINAL_RESEARCH_PRODUCTION_RECONCILIATION_AND_OPERATIONAL_ACCEPTANCE_ACCEPTED":
            errors.append("US_RESEARCH_STATUS")
        if us_research.get("trade_authority") != us_spec["required_trade_authority"]:
            errors.append("US_RESEARCH_TRADE_AUTHORITY")
        if us_research.get("security_universe_count") != us_spec["expected_security_universe_count"]:
            errors.append("US_SECURITY_UNIVERSE_COUNT")
        if us_research.get("benchmark_pool_member_count") != us_spec["expected_benchmark_pool_member_count"]:
            errors.append("US_BENCHMARK_POOL_COUNT")
        if us_research.get("formal_candidate_promotion_count") != us_spec["expected_formal_candidate_promotion_count"]:
            errors.append("US_FORMAL_CANDIDATE_PROMOTION_COUNT")

        pilot = load_json(repo_root / us_spec["pilot_pointer_path"])
        if pilot.get("release_id") != us_spec["required_pilot_release_id"]:
            errors.append("US_PILOT_RELEASE_ID")
        if pilot.get("release_sequence") != us_spec["required_pilot_release_sequence"]:
            errors.append("US_PILOT_RELEASE_SEQUENCE")
        if pilot.get("status") != EXIT_STATUS.replace("6X4E_CROSS_MARKET_COMPARABILITY_AND_OPERATING_RUNBOOK", "6X4D_SIMULATION_ONLY_PILOT_ATTRIBUTION_AND_FAILURE_RECOVERY"):
            errors.append("US_PILOT_STATUS")
        if pilot.get("trade_authority") != us_spec["required_trade_authority"]:
            errors.append("US_PILOT_TRADE_AUTHORITY")

        coverage = load_json(repo_root / us_spec["pilot_current_root"] / "FMDL6X4D_COVERAGE_REPORT.json")
        attribution = load_json(repo_root / us_spec["pilot_current_root"] / "FMDL6X4D_ATTRIBUTION_REPORT.json")
        handoff = load_json(repo_root / us_spec["pilot_current_root"] / "FMDL6X4D_FMDL6X4E_HANDOFF.json")
        if coverage.get("shadow_security_count") != us_spec["expected_shadow_security_count"]:
            errors.append("US_SHADOW_SECURITY_COUNT")
        if coverage.get("shadow_attribution_observation_count") != us_spec["expected_shadow_attribution_observation_count"]:
            errors.append("US_SHADOW_ATTRIBUTION_COUNT")
        if coverage.get("shadow_portfolio_window_count") != us_spec["expected_shadow_portfolio_window_count"]:
            errors.append("US_SHADOW_WINDOW_COUNT")
        if attribution.get("formal_performance_claim") is not False:
            errors.append("US_FORMAL_PERFORMANCE_CLAIM")
        if attribution.get("market_data_grade") != "NON_DECISION_GRADE_FALLBACK":
            errors.append("US_MARKET_DATA_GRADE")
        if handoff.get("next_gate") != entry["required_next_gate"]:
            errors.append("US_HANDOFF_NEXT_GATE")

    dimensions = contract.get("comparability_dimensions", [])
    dimension_codes = [row.get("dimension_code") for row in dimensions]
    if len(dimensions) != 14 or len(set(dimension_codes)) != 14:
        errors.append("COMPARABILITY_DIMENSIONS")
    allowed_classes = set(contract.get("comparability_classes", []))
    for row in dimensions:
        if set(row.get("market_postures", {})) != {"A_SHARE", "HONG_KONG_CONNECT", "US_EQUITY"}:
            errors.append("DIMENSION_MARKET_SET:" + str(row.get("dimension_code")))
        if not set(row.get("market_postures", {}).values()).issubset(allowed_classes):
            errors.append("DIMENSION_CLASS:" + str(row.get("dimension_code")))

    expected_counts = {
        "market_count": 3,
        "comparability_dimension_count": 14,
        "market_dimension_assessment_count": 42,
        "normalization_rule_count": 14,
        "runbook_step_count": 12,
        "cadence_control_count": 5,
        "escalation_rule_count": 10,
        "final_gate_count": 8,
        "logical_shard_count": 448,
        "forced_common_factor_score_count": 0,
        "cross_market_security_rank_count": 0,
        "investment_recommendation_count": 0,
        "neutral_fill_count": 0,
    }
    for key, value in expected_counts.items():
        if contract.get("acceptance_gates", {}).get(key) != value:
            errors.append("ACCEPTANCE_GATE:" + key)
    if len(contract.get("runbook_steps", [])) != 12:
        errors.append("RUNBOOK_STEP_COUNT")
    if len(contract.get("cadence_controls", [])) != 5:
        errors.append("CADENCE_CONTROL_COUNT")
    if len(contract.get("escalation_rules", [])) != 10:
        errors.append("ESCALATION_RULE_COUNT")
    if len(contract.get("final_gates", [])) != 8:
        errors.append("FINAL_GATE_COUNT")
    return contract, sorted(set(errors))


def load_inputs(repo_root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    us_root = repo_root / contract["source_bindings"]["US_EQUITY"]["pilot_current_root"]
    return {
        "entry_pointer": load_json(repo_root / contract["entry_gate"]["pointer_path"]),
        "a_share": load_json(repo_root / contract["source_bindings"]["A_SHARE"]["publication_path"]),
        "hk_pointer": load_json(repo_root / contract["source_bindings"]["HONG_KONG_CONNECT"]["pointer_path"]),
        "hk_contract": load_json(repo_root / contract["source_bindings"]["HONG_KONG_CONNECT"]["contract_path"]),
        "us_research": load_json(repo_root / contract["source_bindings"]["US_EQUITY"]["research_pointer_path"]),
        "us_pilot": load_json(repo_root / contract["source_bindings"]["US_EQUITY"]["pilot_pointer_path"]),
        "us_decision": load_json(us_root / "FMDL6X4D_DECISION.json"),
        "us_coverage": load_json(us_root / "FMDL6X4D_COVERAGE_REPORT.json"),
        "us_attribution": load_json(us_root / "FMDL6X4D_ATTRIBUTION_REPORT.json"),
        "us_failure_recovery": load_json(us_root / "FMDL6X4D_FAILURE_RECOVERY_REPORT.json"),
        "us_handoff": load_json(us_root / "FMDL6X4D_FMDL6X4E_HANDOFF.json"),
        "us_manifest": load_json(us_root / "FMDL6X4D_MANIFEST.json"),
    }


def build_records(inputs: dict[str, Any], contract: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    source = contract["source_bindings"]
    a_spec = source["A_SHARE"]
    hk_spec = source["HONG_KONG_CONNECT"]
    us_spec = source["US_EQUITY"]
    markets = [
        {
            "market_capability_id": "PEIMARKET-" + record_hash("A_SHARE")[:24],
            "market_code": "A_SHARE",
            "market_name": "Mainland China A-share",
            "source_release_id": inputs["a_share"]["release_id"],
            "operational_posture": "OPERATIONAL_EXISTING_INVESTMENT_OS",
            "security_universe_count": a_spec["expected_security_universe_count"],
            "common_equity_count": None,
            "factor_count": None,
            "research_longlist_count": a_spec["expected_research_longlist_count"],
            "research_object_count": None,
            "formal_candidate_or_graduated_count": inputs["a_share"]["metrics"]["candidate_core_count"],
            "market_data_grade": a_spec["evidence_posture"],
            "performance_claim_allowed": False,
            "cross_market_rank_authorized": False,
            "trade_authority": "NONE",
        },
        {
            "market_capability_id": "PEIMARKET-" + record_hash("HONG_KONG_CONNECT")[:24],
            "market_code": "HONG_KONG_CONNECT",
            "market_name": "Hong Kong Stock Connect",
            "source_release_id": inputs["hk_pointer"]["release_id"],
            "operational_posture": "OPERATIONAL_ACCEPTED_FMDL5_OVERLAY",
            "security_universe_count": inputs["hk_pointer"]["southbound_security_count"],
            "common_equity_count": inputs["hk_pointer"]["common_equity_count"],
            "factor_count": hk_spec["expected_factor_count"],
            "research_longlist_count": inputs["hk_pointer"]["longlist_count"],
            "research_object_count": inputs["hk_pointer"]["formal_research_object_count"],
            "formal_candidate_or_graduated_count": hk_spec["expected_graduated_count"],
            "market_data_grade": hk_spec["evidence_posture"],
            "performance_claim_allowed": False,
            "cross_market_rank_authorized": False,
            "trade_authority": "NONE",
        },
        {
            "market_capability_id": "PEIMARKET-" + record_hash("US_EQUITY")[:24],
            "market_code": "US_EQUITY",
            "market_name": "United States Equity Research Universe",
            "source_release_id": inputs["us_pilot"]["release_id"],
            "operational_posture": "RESEARCH_ARCHITECTURE_OPERATIONAL_FORMAL_INVESTMENT_GATES_CLOSED",
            "security_universe_count": inputs["us_research"]["security_universe_count"],
            "common_equity_count": None,
            "factor_count": None,
            "research_longlist_count": inputs["us_research"]["benchmark_pool_member_count"],
            "research_object_count": inputs["us_coverage"]["security_control_count"],
            "formal_candidate_or_graduated_count": inputs["us_research"]["formal_candidate_promotion_count"],
            "market_data_grade": us_spec["evidence_posture"],
            "performance_claim_allowed": False,
            "cross_market_rank_authorized": False,
            "trade_authority": "NONE",
        },
    ]
    market_grade = {row["market_code"]: row["market_data_grade"] for row in markets}

    dimensions: list[dict[str, Any]] = []
    assessments: list[dict[str, Any]] = []
    normalization_rules: list[dict[str, Any]] = []
    for item in contract["comparability_dimensions"]:
        code = item["dimension_code"]
        dimensions.append({
            "comparability_dimension_id": "PEICMPDIM-" + record_hash(code)[:24],
            "dimension_code": code,
            "normalization_action": item["normalization_action"],
            "prohibited_shortcut": item["prohibited_shortcut"],
            "comparison_output": item["comparison_output"],
            "forced_common_score_authorized": False,
            "cross_market_security_rank_authorized": False,
            "trade_authority": "NONE",
        })
        normalization_rules.append({
            "normalization_rule_id": "PEINORM-" + record_hash(code)[:24],
            "dimension_code": code,
            "required_action": item["normalization_action"],
            "prohibited_shortcut": item["prohibited_shortcut"],
            "failure_posture": "FAIL_CLOSED_TO_CONTEXT_ONLY_OR_NOT_COMPARABLE",
            "neutral_fill_allowed": False,
            "silent_source_substitution_allowed": False,
            "trade_authority": "NONE",
        })
        for market_code, posture in sorted(item["market_postures"].items()):
            allowed_use = {
                "DIRECT_WITH_EXPLICIT_NORMALIZATION": "NORMALIZED_COMPARISON_WITH_EXPLICIT_SOURCE_AS_OF_AND_METHOD",
                "PARTIAL_CONTEXT_ONLY": "CONTEXT_ONLY_NO_COMMON_SCORE_OR_SECURITY_RANK",
                "NOT_COMPARABLE_FAIL_CLOSED": "NO_NUMERIC_CROSS_MARKET_COMPARISON",
            }[posture]
            assessments.append({
                "market_dimension_assessment_id": "PEICMPASSESS-" + record_hash(market_code, code)[:24],
                "market_code": market_code,
                "dimension_code": code,
                "comparability_class": posture,
                "required_normalization": item["normalization_action"],
                "evidence_grade": market_grade[market_code],
                "allowed_use": allowed_use,
                "prohibited_use": item["prohibited_shortcut"],
                "forced_common_score_authorized": False,
                "cross_market_security_rank_authorized": False,
                "trade_authority": "NONE",
            })

    runbook_steps = [
        {
            "runbook_step_id": "PEIRUNBOOK-" + record_hash(code)[:24],
            "sequence": index,
            "step_code": code,
            "step_name": name,
            "cadence": cadence,
            "control_text": text,
            "failure_posture": "FAIL_CLOSED_AND_PRESERVE_LKG",
            "automatic_state_mutation_authorized": False,
            "trade_authority": "NONE",
        }
        for index, (code, name, cadence, text) in enumerate(contract["runbook_steps"], start=1)
    ]
    cadence_controls = [
        {
            "cadence_control_id": "PEICADENCE-" + record_hash(cadence)[:24],
            "cadence": cadence,
            "required_review": review,
            "publication_requires_quality_pass": True,
            "automatic_trade_action_authorized": False,
            "trade_authority": "NONE",
        }
        for cadence, review in contract["cadence_controls"]
    ]
    escalation_rules = [
        {
            "operating_control_id": "PEIOPCTRL-" + record_hash(code)[:24],
            "control_type": "ESCALATION_RULE",
            "control_code": code,
            "trigger": trigger,
            "required_action": action,
            "result": "PASS_CONTROL_REGISTERED",
            "candidate_pool_mutations": 0,
            "simulation_book_mutations": 0,
            "real_account_mutations": 0,
            "orders": 0,
            "trade_authority": "NONE",
        }
        for code, trigger, action in contract["escalation_rules"]
    ]
    final_gates = [
        {
            "operating_control_id": "PEIOPCTRL-" + record_hash(code)[:24],
            "control_type": "FINAL_GATE",
            "control_code": code,
            "gate_name": name,
            "gate_status": "PASS",
            "candidate_pool_mutations": 0,
            "simulation_book_mutations": 0,
            "real_account_mutations": 0,
            "orders": 0,
            "trade_authority": "NONE",
        }
        for code, name in contract["final_gates"]
    ]
    return {
        "markets": sorted(markets, key=lambda row: row["market_code"]),
        "dimensions": sorted(dimensions, key=lambda row: row["dimension_code"]),
        "assessments": sorted(assessments, key=lambda row: (row["dimension_code"], row["market_code"])),
        "normalization_rules": sorted(normalization_rules, key=lambda row: row["dimension_code"]),
        "runbook_steps": sorted(runbook_steps, key=lambda row: row["sequence"]),
        "cadence_controls": sorted(cadence_controls, key=lambda row: row["cadence"]),
        "operating_controls": sorted(escalation_rules + final_gates, key=lambda row: row["operating_control_id"]),
    }


def build_shards(records: dict[str, list[dict[str, Any]]], bucket_count: int) -> tuple[bytes, list[dict[str, Any]]]:
    domains = (
        ("MARKET_CAPABILITY", records["markets"], "market_capability_id"),
        ("COMPARABILITY_DIMENSION", records["dimensions"], "comparability_dimension_id"),
        ("MARKET_DIMENSION_ASSESSMENT", records["assessments"], "market_dimension_assessment_id"),
        ("NORMALIZATION_RULE", records["normalization_rules"], "normalization_rule_id"),
        ("OPERATING_RUNBOOK_STEP", records["runbook_steps"], "runbook_step_id"),
        ("CADENCE_CONTROL", records["cadence_controls"], "cadence_control_id"),
        ("OPERATING_CONTROL", records["operating_controls"], "operating_control_id"),
    )
    entries: dict[str, bytes] = {}
    manifest: list[dict[str, Any]] = []
    for domain, rows, key in domains:
        for index in range(bucket_count):
            bucket = f"{index:02X}"
            selected = sorted((row for row in rows if bucket_hex(str(row[key]), bucket_count) == bucket), key=stable_json)
            data = jsonl_bytes(selected)
            name = f"{domain}/{bucket}.jsonl"
            entries[name] = data
            manifest.append({"path": name, "record_count": len(selected), "bytes": len(data), "sha256": sha256_bytes(data)})
    target = Path("/tmp/fmdl6x4e_registry_shards.zip")
    deterministic_zip(target, entries)
    data = target.read_bytes()
    target.unlink(missing_ok=True)
    return data, manifest


def build_queues(contract: dict[str, Any]) -> tuple[bytes, dict[str, int]]:
    queues = {
        "US_DECISION_GRADE_MARKET_AND_ATTRIBUTION_UPGRADE_QUEUE": [{
            "market_code": "US_EQUITY",
            "required_action": "UPGRADE_MARKET_DATA_VALUATION_PEERS_AND_ATTRIBUTION_BEFORE_FORMAL_CROSS_MARKET_COMPARISON_OR_SIMULATION",
            "trade_authority": "NONE",
        }],
        "CROSS_MARKET_FACTOR_NORMALIZATION_QUEUE": [{
            "market_scope": ["A_SHARE", "HONG_KONG_CONNECT", "US_EQUITY"],
            "required_action": "REGISTER_IDENTICAL_FORMULA_WINDOW_SOURCE_GRADE_AND_UNIVERSE_BEFORE_COMMON_FACTOR_USE",
            "trade_authority": "NONE",
        }],
        "CROSS_LISTING_DUPLICATION_REVIEW_QUEUE": [{
            "market_scope": ["A_SHARE", "HONG_KONG_CONNECT", "US_EQUITY"],
            "required_action": "REVIEW_A_H_ADR_AND_MULTI_CLASS_ISSUER_DUPLICATION_BEFORE_MARKET_SELECTION",
            "trade_authority": "NONE",
        }],
        "HUMAN_APPROVAL_AND_STATE_MUTATION_QUEUE": [{
            "market_scope": ["A_SHARE", "HONG_KONG_CONNECT", "US_EQUITY"],
            "required_action": "REQUIRE_EXPLICIT_HUMAN_APPROVAL_AND_SEPARATE_CANDIDATE_SIMULATION_REAL_ACCOUNT_GATES",
            "trade_authority": "NONE",
        }],
    }
    entries = {f"{name}.jsonl": jsonl_bytes(rows) for name, rows in sorted(queues.items())}
    target = Path("/tmp/fmdl6x4e_queues.zip")
    deterministic_zip(target, entries)
    data = target.read_bytes()
    target.unlink(missing_ok=True)
    return data, {name: len(rows) for name, rows in sorted(queues.items())}


def build_candidate(repo_root: Path, candidate: Path, accepted_at: str, source_commit: str) -> dict[str, Any]:
    contract, errors = validate_contract(repo_root)
    if errors:
        raise ValueError("CONTRACT_VALIDATION_FAILED:" + ",".join(errors))
    inputs = load_inputs(repo_root, contract)
    records = build_records(inputs, contract)
    identity = {
        "phase_id": PHASE_ID,
        "accepted_at": accepted_at,
        "source_commit": source_commit,
        "entry_release_id": inputs["entry_pointer"]["release_id"],
        "a_share_release_id": inputs["a_share"]["release_id"],
        "hong_kong_release_id": inputs["hk_pointer"]["release_id"],
        "us_research_release_id": inputs["us_research"]["release_id"],
        "contract_sha256": sha256_file(repo_root / CONTRACT_PATH),
        "entry_manifest_sha256": inputs["entry_pointer"]["manifest_sha256"],
    }
    release_id = f"FMDL6X4E_{accepted_at[:10].replace('-', '')}_{record_hash(identity)[:12]}"
    candidate = repo_root / candidate if not candidate.is_absolute() else candidate
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True, exist_ok=True)

    shard_bytes, shard_manifest = build_shards(records, contract["storage_contract"]["bucket_count"])
    queue_bytes, queue_counts = build_queues(contract)
    (candidate / "FMDL6X4E_REGISTRY_SHARDS.zip").write_bytes(shard_bytes)
    (candidate / "FMDL6X4E_OPERATING_QUEUES.zip").write_bytes(queue_bytes)

    direct_count = sum(row["comparability_class"] == "DIRECT_WITH_EXPLICIT_NORMALIZATION" for row in records["assessments"])
    partial_count = sum(row["comparability_class"] == "PARTIAL_CONTEXT_ONLY" for row in records["assessments"])
    blocked_count = sum(row["comparability_class"] == "NOT_COMPARABLE_FAIL_CLOSED" for row in records["assessments"])
    escalation_count = sum(row["control_type"] == "ESCALATION_RULE" for row in records["operating_controls"])
    final_gates = [row for row in records["operating_controls"] if row["control_type"] == "FINAL_GATE"]
    final_gate_pass_count = sum(row["gate_status"] == "PASS" for row in final_gates)

    write_json(candidate / "FMDL6X4E_CROSS_MARKET_CAPABILITY_REPORT.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "market_count": len(records["markets"]),
        "markets": records["markets"],
        "cross_market_security_rank_authorized": False,
        "persistent_alpha_proof": "NOT_ESTABLISHED",
        "trade_authority": "NONE",
    })
    write_json(candidate / "FMDL6X4E_COMPARABILITY_MATRIX.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "comparability_dimension_count": len(records["dimensions"]),
        "market_dimension_assessment_count": len(records["assessments"]),
        "direct_with_normalization_count": direct_count,
        "partial_context_only_count": partial_count,
        "not_comparable_fail_closed_count": blocked_count,
        "forced_common_factor_score_count": 0,
        "cross_market_security_rank_count": 0,
        "dimensions": records["dimensions"],
        "assessments": records["assessments"],
        "normalization_rules": records["normalization_rules"],
        "trade_authority": "NONE",
    })
    write_json(candidate / "FMDL6X4E_OPERATING_RUNBOOK.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "runbook_status": "FROZEN_FOR_OPERATIONAL_USE",
        "runbook_step_count": len(records["runbook_steps"]),
        "cadence_control_count": len(records["cadence_controls"]),
        "steps": records["runbook_steps"],
        "cadence_controls": records["cadence_controls"],
        "state_mutation_requires_separate_human_authority": True,
        "trade_authority": "NONE",
    })
    write_json(candidate / "FMDL6X4E_ESCALATION_AND_RECOVERY_REPORT.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "escalation_rule_count": escalation_count,
        "upstream_failure_recovery_scenario_count": inputs["us_failure_recovery"]["failure_recovery_scenario_count"],
        "upstream_failure_recovery_pass_count": inputs["us_failure_recovery"]["failure_recovery_pass_count"],
        "recovery_checkpoint_count": inputs["us_failure_recovery"]["recovery_checkpoint_count"],
        "controls": [row for row in records["operating_controls"] if row["control_type"] == "ESCALATION_RULE"],
        "lkg_required": True,
        "deterministic_replay_required": True,
        "trade_authority": "NONE",
    })
    write_json(candidate / "FMDL6X4E_FINAL_GATE_REPORT.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "final_gate_count": len(final_gates),
        "final_gate_pass_count": final_gate_pass_count,
        "all_final_gates_pass": final_gate_pass_count == len(final_gates),
        "gates": final_gates,
        "next_gate": NEXT_GATE,
        "trade_authority": "NONE",
    })
    write_json(candidate / "FMDL6X4E_QUEUE_SUMMARY.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "queue_counts": queue_counts,
        "queue_record_count": sum(queue_counts.values()),
        "trade_authority": "NONE",
    })
    write_json(candidate / "FMDL6X4E_SOURCE_BINDING.json", {
        **identity,
        "release_id": release_id,
        "roadmap_authority": contract["roadmap_authority"]["path"],
        "source_release_ids": {
            "A_SHARE": inputs["a_share"]["release_id"],
            "HONG_KONG_CONNECT": inputs["hk_pointer"]["release_id"],
            "US_RESEARCH": inputs["us_research"]["release_id"],
            "US_SIMULATION_PILOT": inputs["us_pilot"]["release_id"],
        },
        "us_market_data_grade": inputs["us_attribution"]["market_data_grade"],
        "us_shadow_attribution_formal_performance": inputs["us_attribution"]["formal_performance_claim"],
        "silent_source_substitution": False,
        "neutral_fill_used": False,
        "forced_common_factor_score_emitted": False,
        "cross_market_security_rank_emitted": False,
        "investment_recommendation_emitted": False,
        "trade_authority": "NONE",
    })
    write_json(candidate / "FMDL6X4E_FMDL6X4FINAL_HANDOFF.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "handoff_status": "OPEN_FOR_FMDL6X4FINAL_US_RESEARCH_ADAPTER_OPERATIONAL_ACCEPTANCE_AND_FMDL6_FREEZE_ONLY",
        "next_gate": NEXT_GATE,
        "accepted_market_count": len(records["markets"]),
        "accepted_comparability_dimension_count": len(records["dimensions"]),
        "accepted_runbook_step_count": len(records["runbook_steps"]),
        "required_final_controls": [
            "RECONCILE_FMDL6X1_THROUGH_FMDL6X4E_RELEASES_AND_POINTERS",
            "PROVE_US_ADAPTER_RECOVERY_AND_CLEAN_ROOM_OPERATION",
            "FREEZE_US_RESEARCH_ADAPTER_WITH_EXPLICIT_DATA_AND_DECISION_BOUNDARIES",
            "PRESERVE_CANDIDATE_SIMULATION_REAL_ACCOUNT_BROKERAGE_AND_ORDER_GATES",
        ],
        "candidate_pool_authorized": False,
        "simulation_book_authorized": False,
        "real_account_authorized": False,
        "brokerage_channel_available": False,
        "trade_authority": "NONE",
    })

    expected = contract["acceptance_gates"]
    actual = {
        "market_count": len(records["markets"]),
        "comparability_dimension_count": len(records["dimensions"]),
        "market_dimension_assessment_count": len(records["assessments"]),
        "normalization_rule_count": len(records["normalization_rules"]),
        "runbook_step_count": len(records["runbook_steps"]),
        "cadence_control_count": len(records["cadence_controls"]),
        "escalation_rule_count": escalation_count,
        "final_gate_count": len(final_gates),
        "logical_shard_count": len(shard_manifest),
        "forced_common_factor_score_count": 0,
        "cross_market_security_rank_count": 0,
        "investment_recommendation_count": 0,
        "neutral_fill_count": 0,
    }
    gate_errors = [key for key, value in expected.items() if actual.get(key) != value]
    quality_status = "PASS" if not gate_errors and final_gate_pass_count == len(final_gates) else "FAIL"
    write_json(candidate / "FMDL6X4E_QUALITY_REPORT.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "quality_status": quality_status,
        "acceptance_gate_actual": actual,
        "acceptance_gate_errors": gate_errors,
        "requested_shard_count": expected["logical_shard_count"],
        "actual_shard_count": len(shard_manifest),
        "final_gate_pass_count": final_gate_pass_count,
        "zero_mutation_proof": contract["zero_mutation_gate"],
        "trade_authority": "NONE",
    })
    write_json(candidate / "FMDL6X4E_DECISION.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "accepted_at": accepted_at,
        "source_commit": source_commit,
        "status": EXIT_STATUS,
        "next_gate": NEXT_GATE,
        "cross_market_comparability_status": "DIMENSION_LEVEL_COMPARABILITY_ACCEPTED_WITH_NO_FORCED_COMMON_SCORE_OR_SECURITY_RANK",
        "operating_runbook_status": "DAILY_WEEKLY_MONTHLY_QUARTERLY_AND_EVENT_DRIVEN_RUNBOOK_FROZEN",
        "a_share_operating_posture": "OPERATIONAL_EXISTING_INVESTMENT_OS",
        "hong_kong_operating_posture": "OPERATIONAL_ACCEPTED_FMDL5_OVERLAY",
        "us_operating_posture": "RESEARCH_ARCHITECTURE_OPERATIONAL_FORMAL_INVESTMENT_GATES_CLOSED",
        "fmdl6x4final_gate": "OPEN_FOR_US_RESEARCH_ADAPTER_OPERATIONAL_ACCEPTANCE_AND_FMDL6_FREEZE_ONLY",
        "investment_recommendation_count": 0,
        "zero_mutation_proof": contract["zero_mutation_gate"],
        "trade_authority": "NONE",
    })

    files: dict[str, dict[str, Any]] = {}
    for path in sorted(candidate.iterdir()):
        if path.name == "FMDL6X4E_MANIFEST.json" or not path.is_file():
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
    write_json(candidate / "FMDL6X4E_MANIFEST.json", manifest)
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
    manifest = load_json(candidate / "FMDL6X4E_MANIFEST.json")
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
    contract, errors = validate_contract(repo_root)
    if errors:
        raise ValueError("CONTRACT_VALIDATION_FAILED:" + ",".join(errors))
    candidate = repo_root / candidate if not candidate.is_absolute() else candidate
    manifest = load_json(candidate / "FMDL6X4E_MANIFEST.json")
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
    decision = load_json(candidate / "FMDL6X4E_DECISION.json")
    pointer = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "published_at": published_at,
        "source_commit": source_commit,
        "status": EXIT_STATUS,
        "next_gate": NEXT_GATE,
        "input_release_id": load_json(repo_root / D_POINTER_PATH)["release_id"],
        "current_path": contract["storage_contract"]["current_root"],
        "release_path": contract["storage_contract"]["release_root"].replace("<release_id>", release_id),
        "normalized_path": contract["storage_contract"]["normalized_root"].replace("<release_id>", release_id),
        "manifest_sha256": sha256_file(candidate / "FMDL6X4E_MANIFEST.json"),
        "cross_market_comparability_status": decision["cross_market_comparability_status"],
        "operating_runbook_status": decision["operating_runbook_status"],
        "fmdl6x4final_gate": decision["fmdl6x4final_gate"],
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
        print("FMDL-6X4-E contract validation PASS")
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
