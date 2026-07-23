from __future__ import annotations

import argparse
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from fmdl6x2d_common import (
    bucket_hex,
    copytree_replace,
    deterministic_zip,
    load_json,
    read_zip_jsonl,
    record_hash,
    sha256_bytes,
    sha256_file,
    stable_json,
    write_json,
)

PHASE_ID = "FMDL-6X4-C"
EXIT_STATUS = "FMDL6X4C_CANDIDATE_GRADUATION_DECISION_INTERFACE_AND_GUARDRAILS_ACCEPTED"
NEXT_GATE = "FMDL-6X4-FINAL_PUBLIC_EQUITY_INVESTING_INTEGRATION_RECONCILIATION_AND_OPERATIONAL_ACCEPTANCE"
CONTRACT_PATH = Path("config/fmdl6x4c_candidate_graduation_contract.json")
INTEGRATION_ROOT = Path("outputs/fmdl6x4/current/research_workflow_integration")
LAST_SUCCESS_PATH = Path("outputs/status/FMDL6X4B_LAST_SUCCESS.json")
INTEGRATION_LKG_PATH = Path("outputs/status/FMDL6X4_RESEARCH_WORKFLOW_INTEGRATION_LKG.json")
FACTOR_COVERAGE_PATH = Path("outputs/fmdl6x3/current/factor_engine/FMDL6X3C_COVERAGE_REPORT.json")
PEER_COVERAGE_PATH = Path("outputs/fmdl6x3/current/sector_peer_benchmark/FMDL6X3D_COVERAGE_REPORT.json")

RULES: list[dict[str, Any]] = [
    {
        "rule_code": "G01_CANONICAL_IDENTITY_REGISTERED",
        "rule_name": "Canonical identity registered",
        "applies_to": "ALL_SECURITIES",
        "expected": "CANONICAL_IDENTITY evidence registration exists",
        "failure_code": "CANONICAL_IDENTITY_EVIDENCE_MISSING",
    },
    {
        "rule_code": "G02_RESEARCH_CARD_REGISTERED",
        "rule_name": "Research Card registered",
        "applies_to": "ALL_SECURITIES",
        "expected": "RESEARCH_CARD evidence registration exists",
        "failure_code": "RESEARCH_CARD_EVIDENCE_MISSING",
    },
    {
        "rule_code": "G03_OFFICIAL_SEC_FILING_POSTURE_REGISTERED",
        "rule_name": "Official SEC filing posture registered",
        "applies_to": "ISSUER_SECURITIES",
        "expected": "OFFICIAL_SEC_FILING_POSTURE evidence registration exists",
        "failure_code": "OFFICIAL_SEC_FILING_POSTURE_MISSING",
    },
    {
        "rule_code": "G04_OFFICIAL_SEC_FINANCIAL_FACT_SET_REGISTERED",
        "rule_name": "Official SEC financial fact set registered",
        "applies_to": "ISSUER_SECURITIES",
        "expected": "OFFICIAL_SEC_FACT_SET evidence registration exists",
        "failure_code": "OFFICIAL_SEC_FACT_SET_MISSING",
    },
    {
        "rule_code": "G05_MINIMUM_REGISTERED_WORKFLOW_OUTPUTS_QC_PASSED",
        "rule_name": "Minimum registered workflow outputs and QC",
        "applies_to": "ISSUER_SECURITIES",
        "expected": "At least two registered QC-passed workflow outputs including issuer baseline and decision-grade financial output",
        "failure_code": "REGISTERED_WORKFLOW_OUTPUT_MINIMUM_NOT_MET",
    },
    {
        "rule_code": "G06_DECISION_GRADE_MARKET_DATA",
        "rule_name": "Decision-grade market data",
        "applies_to": "ISSUER_SECURITIES",
        "expected": "Market data grade is DECISION_GRADE",
        "failure_code": "DECISION_GRADE_MARKET_DATA_MISSING",
    },
    {
        "rule_code": "G07_FORMAL_VALUATION_READY",
        "rule_name": "Formal valuation ready",
        "applies_to": "ISSUER_SECURITIES",
        "expected": "Security-specific formal valuation is registered and valid",
        "failure_code": "FORMAL_VALUATION_NOT_READY",
    },
    {
        "rule_code": "G08_FORMAL_PEER_COMPARABILITY_READY",
        "rule_name": "Formal peer comparability ready",
        "applies_to": "ISSUER_SECURITIES",
        "expected": "Security is assigned to a valid formal comparable peer group",
        "failure_code": "FORMAL_PEER_COMPARABILITY_NOT_READY",
    },
    {
        "rule_code": "G09_USER_CONFIRMED_INVESTMENT_CONTEXT",
        "rule_name": "User-confirmed investment context",
        "applies_to": "ISSUER_SECURITIES",
        "expected": "Mandate, horizon, direction, benchmark and decision use are confirmed",
        "failure_code": "USER_CONFIRMED_INVESTMENT_CONTEXT_MISSING",
    },
    {
        "rule_code": "G10_THESIS_AND_FALSIFIERS_REGISTERED",
        "rule_name": "Thesis and falsifiers registered",
        "applies_to": "ISSUER_SECURITIES",
        "expected": "Thesis, variant view, catalysts, risks and falsifiers are registered",
        "failure_code": "THESIS_AND_FALSIFIERS_MISSING",
    },
    {
        "rule_code": "G11_HUMAN_APPROVAL_GRANTED",
        "rule_name": "Human approval granted",
        "applies_to": "ISSUER_SECURITIES",
        "expected": "HUMAN_USER explicitly approves research-candidate graduation",
        "failure_code": "HUMAN_APPROVAL_NOT_GRANTED",
    },
    {
        "rule_code": "G12_SECURITY_TYPE_ROUTED_CORRECTLY",
        "rule_name": "Security type routed correctly",
        "applies_to": "ALL_SECURITIES",
        "expected": "Issuer securities remain in issuer assessment and reference instruments remain outside issuer-candidate graduation",
        "failure_code": "SECURITY_TYPE_ROUTING_INVALID",
    },
]

GUARDRAILS: list[tuple[str, str, str]] = [
    ("GR01", "RESEARCH_PRIORITY_NOT_RECOMMENDATION", "Research-priority status cannot be represented as an investment recommendation."),
    ("GR02", "BENCHMARK_POOL_NOT_CANDIDATE_POOL", "US Research Benchmark Pool membership cannot create Candidate Pool membership."),
    ("GR03", "REGISTERED_WORKFLOW_OUTPUT_MINIMUM", "At least two registered QC-passed workflow outputs are required before human review."),
    ("GR04", "OUTPUT_IDENTITY_QC_AND_HASH_REQUIRED", "Every workflow output must bind security, issuer, sources, evidence labels, QC and artifact hash."),
    ("GR05", "DECISION_GRADE_MARKET_DATA_REQUIRED", "Non-decision-grade market data cannot support security-level graduation."),
    ("GR06", "FORMAL_VALUATION_REQUIRED", "A formal and current valuation is mandatory."),
    ("GR07", "FORMAL_PEER_COMPARABILITY_REQUIRED", "Formal peer comparability is mandatory and sector cohorts alone are insufficient."),
    ("GR08", "USER_CONFIRMED_INVESTMENT_CONTEXT_REQUIRED", "Mandate, direction, horizon, benchmark and decision use require user confirmation."),
    ("GR09", "THESIS_AND_FALSIFIERS_REQUIRED", "Thesis, variant view, catalysts, risks and falsifiers must be registered."),
    ("GR10", "HUMAN_APPROVAL_ONLY", "Only HUMAN_USER can approve graduation; automatic approval is prohibited."),
    ("GR11", "NO_AUTOMATIC_CANDIDATE_POOL_MUTATION", "Graduation assessment cannot mutate the Candidate Pool."),
    ("GR12", "NO_SIMULATION_MUTATION", "Graduation assessment cannot mutate simulation state."),
    ("GR13", "NO_BROKERAGE_OR_ORDER_CHANNEL", "No brokerage connection, real-account mutation or order may be created."),
    ("GR14", "APPEND_ONLY_DECISION_LOG", "Approval, rejection, deferral, withdrawal and downgrade transitions require an append-only log."),
    ("GR15", "DOWNGRADE_ON_STALE_CONFLICTING_OR_INVALIDATED_EVIDENCE", "Approved status must downgrade when evidence becomes stale, conflicting, withdrawn or invalidated."),
    ("GR16", "APPROVAL_DOES_NOT_AUTHORIZE_TRADE", "Research-candidate approval never creates trade authority."),
]


def validate_contract(repo_root: Path) -> tuple[dict[str, Any], list[str]]:
    path = repo_root / CONTRACT_PATH
    if not path.is_file():
        return {}, ["CONTRACT_MISSING"]
    contract = load_json(path)
    errors: list[str] = []
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

    pointer_path = repo_root / contract["entry_gate"]["pointer_path"]
    if not pointer_path.is_file():
        errors.append("ENTRY_POINTER_MISSING")
        return contract, sorted(set(errors))
    pointer = load_json(pointer_path)
    for field, key in (
        ("phase_id", "required_phase_id"),
        ("release_id", "required_release_id"),
        ("release_sequence", "required_release_sequence"),
        ("status", "required_status"),
        ("next_gate", "required_next_gate"),
        ("trade_authority", "required_trade_authority"),
    ):
        if pointer.get(field) != contract["entry_gate"].get(key):
            errors.append("ENTRY_" + field.upper())

    required = [
        INTEGRATION_ROOT / "FMDL6X4B_INTEGRATION_SHARDS.zip",
        INTEGRATION_ROOT / "FMDL6X4B_INTEGRATION_SUMMARY.json",
        INTEGRATION_ROOT / "FMDL6X4B_SOURCE_BINDING.json",
        INTEGRATION_ROOT / "FMDL6X4B_SOURCE_REGISTRY.json",
        INTEGRATION_ROOT / "FMDL6X4B_FMDL6X4C_HANDOFF.json",
        INTEGRATION_ROOT / "FMDL6X4B_MANIFEST.json",
        INTEGRATION_ROOT / "FMDL6X4B_DECISION.json",
        INTEGRATION_LKG_PATH,
        FACTOR_COVERAGE_PATH,
        PEER_COVERAGE_PATH,
    ]
    for item in required:
        if not (repo_root / item).is_file():
            errors.append("INPUT_MISSING:" + str(item))

    release_root = repo_root / pointer["release_path"]
    for name in ("FMDL6X4B_DECISION.json", "FMDL6X4B_MANIFEST.json"):
        current_file = repo_root / INTEGRATION_ROOT / name
        release_file = release_root / name
        if not release_file.is_file():
            errors.append("IMMUTABLE_RELEASE_FILE_MISSING:" + name)
        elif sha256_file(current_file) != sha256_file(release_file):
            errors.append("CURRENT_RELEASE_PARITY:" + name)
    if (repo_root / INTEGRATION_LKG_PATH).is_file():
        lkg = load_json(repo_root / INTEGRATION_LKG_PATH)
        if lkg.get("release_id") != pointer.get("release_id") or lkg.get("manifest_sha256") != pointer.get("manifest_sha256"):
            errors.append("LKG_BINDING")

    expected = {
        "security_count": 7,
        "issuer_candidate_scope_count": 6,
        "reference_instrument_count": 1,
        "graduation_rule_count": 12,
        "graduation_rule_assessment_count": 84,
        "rule_assessment_pass_count": 30,
        "rule_assessment_fail_count": 45,
        "rule_assessment_not_applicable_count": 9,
        "decision_interface_count": 7,
        "human_approval_state_count": 7,
        "guardrail_status_count": 16,
        "blocked_issuer_count": 6,
        "not_applicable_reference_count": 1,
        "graduation_event_count": 0,
        "formal_candidate_promotion_count": 0,
        "investment_recommendation_count": 0,
        "logical_shard_count": 320,
        "neutral_fill_count": 0,
    }
    for key, value in expected.items():
        if contract.get("acceptance_gates", {}).get(key) != value:
            errors.append("ACCEPTANCE_GATE:" + key)
    return contract, sorted(set(errors))


def load_inputs(repo_root: Path) -> dict[str, Any]:
    shard_path = repo_root / INTEGRATION_ROOT / "FMDL6X4B_INTEGRATION_SHARDS.zip"
    return {
        "evidence": read_zip_jsonl(shard_path, "EVIDENCE_REGISTRATION/"),
        "ledgers": read_zip_jsonl(shard_path, "SECURITY_EVIDENCE_LEDGER/"),
        "integration_states": read_zip_jsonl(shard_path, "WORKFLOW_INTEGRATION_STATE/"),
        "envelopes": read_zip_jsonl(shard_path, "INVOCATION_ENVELOPE/"),
        "output_contracts": read_zip_jsonl(shard_path, "OUTPUT_REGISTRATION_CONTRACT/"),
        "summary": load_json(repo_root / INTEGRATION_ROOT / "FMDL6X4B_INTEGRATION_SUMMARY.json"),
        "source_binding": load_json(repo_root / INTEGRATION_ROOT / "FMDL6X4B_SOURCE_BINDING.json"),
        "source_registry": load_json(repo_root / INTEGRATION_ROOT / "FMDL6X4B_SOURCE_REGISTRY.json"),
        "handoff": load_json(repo_root / INTEGRATION_ROOT / "FMDL6X4B_FMDL6X4C_HANDOFF.json"),
        "factor_coverage": load_json(repo_root / FACTOR_COVERAGE_PATH),
        "peer_coverage": load_json(repo_root / PEER_COVERAGE_PATH),
    }


def rule_registry() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in RULES:
        rows.append({
            "graduation_rule_id": "PEIGRADRULE-" + record_hash("PEI_GRADUATION_RULE", item["rule_code"])[:24],
            **item,
            "required_for_graduation": True,
            "weighted_score_used": False,
            "neutral_fill_allowed": False,
            "automatic_waiver_allowed": False,
            "human_override_requires_logged_decision": True,
            "candidate_pool_mutation_authorized": False,
            "trade_authority": "NONE",
        })
    return rows


def guardrail_registry() -> list[dict[str, Any]]:
    return [
        {
            "guardrail_id": "PEIGUARD-" + record_hash("PEI_GUARDRAIL", code)[:24],
            "guardrail_code": code,
            "guardrail_name": name,
            "guardrail_description": description,
            "guardrail_status": "ACTIVE_ENFORCED",
            "violation_count": 0,
            "automatic_waiver_allowed": False,
            "trade_authority": "NONE",
        }
        for code, name, description in GUARDRAILS
    ]


def build_records(inputs: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    evidence = sorted(inputs["evidence"], key=lambda row: row["evidence_registration_id"])
    ledgers = sorted(inputs["ledgers"], key=lambda row: row["canonical_security_id"])
    integration_states = sorted(inputs["integration_states"], key=lambda row: row["workflow_integration_state_id"])
    rules = rule_registry()
    guardrails = guardrail_registry()
    errors: list[str] = []

    if len(evidence) != 53:
        errors.append("INPUT_EVIDENCE_COUNT")
    if len(ledgers) != 7:
        errors.append("INPUT_LEDGER_COUNT")
    if len(integration_states) != 98:
        errors.append("INPUT_INTEGRATION_STATE_COUNT")
    if len(inputs["envelopes"]) != 10:
        errors.append("INPUT_ENVELOPE_COUNT")
    if len(inputs["output_contracts"]) != 14:
        errors.append("INPUT_OUTPUT_CONTRACT_COUNT")
    if inputs["summary"].get("registered_workflow_output_count") != 0:
        errors.append("REGISTERED_OUTPUT_BOUNDARY")
    if inputs["handoff"].get("candidate_pool_authorized") is not False:
        errors.append("HANDOFF_CANDIDATE_BOUNDARY")
    if inputs["factor_coverage"].get("valuation_factor_observation_count") != 0:
        errors.append("VALUATION_BOUNDARY")
    if inputs["peer_coverage"].get("formal_peer_group_count") != 0:
        errors.append("PEER_BOUNDARY")
    if inputs["factor_coverage"].get("market_data_grade") != "NON_DECISION_GRADE_FALLBACK":
        errors.append("MARKET_GRADE_BOUNDARY")

    evidence_by_security: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evidence:
        evidence_by_security[row["canonical_security_id"]].append(row)
    states_by_security: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in integration_states:
        states_by_security[row["canonical_security_id"]].append(row)

    approvals: list[dict[str, Any]] = []
    for ledger in ledgers:
        reference = ledger["symbol"] == "QQQ"
        approvals.append({
            "human_approval_state_id": "PEIAPPROVAL-" + record_hash("PEI_APPROVAL_STATE", ledger["canonical_security_id"])[:24],
            "canonical_security_id": ledger["canonical_security_id"],
            "canonical_issuer_id": ledger["canonical_issuer_id"],
            "symbol": ledger["symbol"],
            "decision_authority": "HUMAN_USER",
            "approval_status": "NOT_APPLICABLE_REFERENCE_INSTRUMENT" if reference else "NOT_REQUESTED_PREREQUISITES_INCOMPLETE",
            "approval_requested_at": None,
            "approval_decided_at": None,
            "decision_log_entry_id": None,
            "automatic_approval_allowed": False,
            "candidate_pool_mutation_authorized": False,
            "approval_does_not_authorize_trade": True,
            "trade_authority": "NONE",
        })
    approval_by_security = {row["canonical_security_id"]: row for row in approvals}

    assessments: list[dict[str, Any]] = []
    assessment_ids_by_security: dict[str, list[str]] = defaultdict(list)
    failed_rules_by_security: dict[str, list[str]] = defaultdict(list)
    minimum_outputs = contract["graduation_contract"]["minimum_registered_workflow_outputs"]
    registered_outputs = int(inputs["summary"].get("registered_workflow_output_count", 0))
    market_grade = inputs["factor_coverage"]["market_data_grade"]
    valuation_count = int(inputs["factor_coverage"]["valuation_factor_observation_count"])
    peer_count = int(inputs["peer_coverage"]["formal_peer_group_count"])

    for ledger in ledgers:
        sid = ledger["canonical_security_id"]
        symbol = ledger["symbol"]
        reference = symbol == "QQQ"
        security_evidence = evidence_by_security[sid]
        evidence_ids_by_type: dict[str, list[str]] = defaultdict(list)
        for row in security_evidence:
            evidence_ids_by_type[row["evidence_type"]].append(row["evidence_registration_id"])
        waiting_confirmations = sum(
            row["integration_status"] == "WAITING_USER_CONFIRMATION" for row in states_by_security[sid]
        )

        for rule in rules:
            code = rule["rule_code"]
            issuer_only = rule["applies_to"] == "ISSUER_SECURITIES"
            applicable = not (reference and issuer_only)
            status = "NOT_APPLICABLE"
            actual: Any = None
            related_evidence_ids: list[str] = []
            failure_code: str | None = None
            rationale = "Reference instrument is outside issuer-candidate graduation scope."

            if applicable:
                passed = False
                if code == "G01_CANONICAL_IDENTITY_REGISTERED":
                    related_evidence_ids = evidence_ids_by_type["CANONICAL_IDENTITY"]
                    actual = len(related_evidence_ids)
                    passed = actual > 0
                elif code == "G02_RESEARCH_CARD_REGISTERED":
                    related_evidence_ids = evidence_ids_by_type["RESEARCH_CARD"]
                    actual = len(related_evidence_ids)
                    passed = actual > 0
                elif code == "G03_OFFICIAL_SEC_FILING_POSTURE_REGISTERED":
                    related_evidence_ids = evidence_ids_by_type["OFFICIAL_SEC_FILING_POSTURE"]
                    actual = len(related_evidence_ids)
                    passed = actual > 0
                elif code == "G04_OFFICIAL_SEC_FINANCIAL_FACT_SET_REGISTERED":
                    related_evidence_ids = evidence_ids_by_type["OFFICIAL_SEC_FACT_SET"]
                    actual = len(related_evidence_ids)
                    passed = actual > 0
                elif code == "G05_MINIMUM_REGISTERED_WORKFLOW_OUTPUTS_QC_PASSED":
                    actual = registered_outputs
                    passed = actual >= minimum_outputs
                elif code == "G06_DECISION_GRADE_MARKET_DATA":
                    actual = market_grade
                    passed = actual == contract["graduation_contract"]["required_market_data_grade"]
                elif code == "G07_FORMAL_VALUATION_READY":
                    actual = valuation_count
                    passed = actual > 0
                elif code == "G08_FORMAL_PEER_COMPARABILITY_READY":
                    actual = peer_count
                    passed = actual > 0
                elif code == "G09_USER_CONFIRMED_INVESTMENT_CONTEXT":
                    actual = {"waiting_confirmation_mapping_count": waiting_confirmations, "confirmed_context_count": 0}
                    passed = False
                elif code == "G10_THESIS_AND_FALSIFIERS_REGISTERED":
                    actual = {"registered_thesis_output_count": 0, "registered_falsifier_set_count": 0}
                    passed = False
                elif code == "G11_HUMAN_APPROVAL_GRANTED":
                    actual = approval_by_security[sid]["approval_status"]
                    passed = actual == "APPROVED_RESEARCH_CANDIDATE"
                elif code == "G12_SECURITY_TYPE_ROUTED_CORRECTLY":
                    actual = "REFERENCE_INSTRUMENT" if reference else "ISSUER_SECURITY"
                    passed = True
                else:
                    raise KeyError(code)

                status = "PASS" if passed else "FAIL"
                failure_code = None if passed else rule["failure_code"]
                rationale = "Graduation requirement is satisfied." if passed else "Graduation requirement is not satisfied by registered evidence and state."
                if failure_code:
                    failed_rules_by_security[sid].append(failure_code)

            assessment_id = "PEIGRADASSESS-" + record_hash("PEI_GRADUATION_ASSESSMENT", sid, code)[:24]
            assessment_ids_by_security[sid].append(assessment_id)
            assessments.append({
                "graduation_rule_assessment_id": assessment_id,
                "graduation_rule_id": rule["graduation_rule_id"],
                "rule_code": code,
                "canonical_security_id": sid,
                "canonical_issuer_id": ledger["canonical_issuer_id"],
                "symbol": symbol,
                "applicable": applicable,
                "assessment_status": status,
                "actual": actual,
                "expected": rule["expected"],
                "evidence_registration_ids": sorted(related_evidence_ids),
                "failure_code": failure_code,
                "assessment_rationale": rationale,
                "automatic_waiver_allowed": False,
                "candidate_pool_mutation_authorized": False,
                "trade_authority": "NONE",
            })

    assessments.sort(key=lambda row: row["graduation_rule_assessment_id"])
    assessment_counts = Counter(row["assessment_status"] for row in assessments)

    decision_interfaces: list[dict[str, Any]] = []
    for ledger in ledgers:
        sid = ledger["canonical_security_id"]
        reference = ledger["symbol"] == "QQQ"
        fact_ready = "OFFICIAL_SEC_FACT_SET" in {row["evidence_type"] for row in evidence_by_security[sid]}
        decision_interfaces.append({
            "decision_interface_id": "PEIDECISION-" + record_hash("PEI_DECISION_INTERFACE", sid)[:24],
            "canonical_security_id": sid,
            "canonical_issuer_id": ledger["canonical_issuer_id"],
            "symbol": ledger["symbol"],
            "research_priority_status": "BENCHMARK_REFERENCE" if reference else "CORE_RESEARCH_SANDBOX" if fact_ready else "OFFICIAL_FILING_WATCH",
            "company_thesis_status": "NOT_APPLICABLE_REFERENCE_INSTRUMENT" if reference else "UNTESTED_NO_REGISTERED_WORKFLOW_OUTPUT",
            "security_thesis_readiness": "REFERENCE_ONLY_NON_DECISION_GRADE_MARKET" if reference else "NOT_DECISION_GRADE",
            "candidate_graduation_status": "NOT_APPLICABLE_REFERENCE_INSTRUMENT" if reference else "BLOCKED_EVIDENCE_AND_DECISION_REQUIREMENTS_PENDING",
            "human_approval_status": approval_by_security[sid]["approval_status"],
            "investment_recommendation_status": "NOT_ISSUED",
            "candidate_pool_status": "NOT_AUTHORIZED",
            "simulation_status": "CLOSED_NOT_AUTHORIZED",
            "graduation_rule_assessment_ids": sorted(assessment_ids_by_security[sid]),
            "blocking_codes": sorted(set(failed_rules_by_security[sid])),
            "allowed_next_action": "MAINTAIN_REFERENCE_INSTRUMENT" if reference else "BACKFILL_REGISTERED_OUTPUTS_DATA_CONTEXT_THESIS_AND_APPROVAL_PREREQUISITES",
            "automatic_promotion_allowed": False,
            "trade_authority": "NONE",
        })
    decision_interfaces.sort(key=lambda row: row["canonical_security_id"])
    approvals.sort(key=lambda row: row["canonical_security_id"])

    queues: dict[str, list[dict[str, Any]]] = {
        "REGISTERED_WORKFLOW_OUTPUT_BACKFILL_QUEUE": [],
        "DECISION_GRADE_MARKET_UPGRADE_QUEUE": [],
        "VALUATION_READINESS_QUEUE": [],
        "FORMAL_PEER_COMPARABILITY_QUEUE": [],
        "HUMAN_INVESTMENT_CONTEXT_QUEUE": [],
        "THESIS_FALSIFIER_REGISTRATION_QUEUE": [],
        "HUMAN_APPROVAL_PREREQUISITE_QUEUE": [],
        "REFERENCE_INSTRUMENT_REGISTRY": [],
    }
    for row in decision_interfaces:
        base = {
            "canonical_security_id": row["canonical_security_id"],
            "canonical_issuer_id": row["canonical_issuer_id"],
            "symbol": row["symbol"],
        }
        if row["candidate_graduation_status"] == "NOT_APPLICABLE_REFERENCE_INSTRUMENT":
            queues["REFERENCE_INSTRUMENT_REGISTRY"].append({**base, "required_action": "RETAIN_AS_BENCHMARK_REFERENCE_NOT_ISSUER_CANDIDATE"})
            continue
        queues["REGISTERED_WORKFLOW_OUTPUT_BACKFILL_QUEUE"].append({**base, "required_action": "REGISTER_MINIMUM_QC_PASSED_WORKFLOW_OUTPUTS"})
        queues["DECISION_GRADE_MARKET_UPGRADE_QUEUE"].append({**base, "required_action": "UPGRADE_MARKET_DATA_TO_DECISION_GRADE"})
        queues["VALUATION_READINESS_QUEUE"].append({**base, "required_action": "REGISTER_FORMAL_CURRENT_VALUATION"})
        queues["FORMAL_PEER_COMPARABILITY_QUEUE"].append({**base, "required_action": "ESTABLISH_FORMAL_COMPARABLE_PEER_GROUP"})
        queues["HUMAN_INVESTMENT_CONTEXT_QUEUE"].append({**base, "required_action": "CONFIRM_MANDATE_DIRECTION_HORIZON_BENCHMARK_AND_DECISION_USE"})
        queues["THESIS_FALSIFIER_REGISTRATION_QUEUE"].append({**base, "required_action": "REGISTER_THESIS_VARIANT_VIEW_CATALYSTS_RISKS_AND_FALSIFIERS"})
        queues["HUMAN_APPROVAL_PREREQUISITE_QUEUE"].append({**base, "required_action": "COMPLETE_ALL_RULES_BEFORE_REQUESTING_HUMAN_APPROVAL"})
    for rows in queues.values():
        rows.sort(key=stable_json)

    return {
        "rules": rules,
        "assessments": assessments,
        "decision_interfaces": decision_interfaces,
        "approvals": approvals,
        "guardrails": guardrails,
        "queues": queues,
        "assessment_counts": dict(sorted(assessment_counts.items())),
        "errors": errors,
    }


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(stable_json(row) + "\n" for row in rows).encode("utf-8")


def build_shards(records: dict[str, Any], bucket_count: int, generated_at: str) -> tuple[bytes, list[dict[str, Any]]]:
    domains = (
        ("GRADUATION_RULE", records["rules"], "graduation_rule_id"),
        ("GRADUATION_RULE_ASSESSMENT", records["assessments"], "graduation_rule_assessment_id"),
        ("DECISION_INTERFACE", records["decision_interfaces"], "decision_interface_id"),
        ("HUMAN_APPROVAL_STATE", records["approvals"], "human_approval_state_id"),
        ("GUARDRAIL_STATUS", records["guardrails"], "guardrail_id"),
    )
    entries: dict[str, bytes] = {}
    manifest: list[dict[str, Any]] = []
    for domain, rows, key in domains:
        for index in range(bucket_count):
            bucket = f"{index:02X}"
            shard = sorted(
                (row for row in rows if bucket_hex(str(row[key]), bucket_count) == bucket),
                key=lambda row: (str(row[key]), stable_json(row)),
            )
            payload = jsonl_bytes(shard)
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


def build_queue_zip(queues: dict[str, list[dict[str, Any]]]) -> bytes:
    return deterministic_zip({f"{name}.jsonl": jsonl_bytes(rows) for name, rows in sorted(queues.items())})


def build_candidate(repo_root: Path, candidate_root: Path, accepted_at: str, source_commit: str) -> dict[str, Any]:
    contract, contract_errors = validate_contract(repo_root)
    if contract_errors:
        raise RuntimeError("CONTRACT_ERRORS:" + ",".join(contract_errors))
    inputs = load_inputs(repo_root)
    records = build_records(inputs, contract)
    if records["errors"]:
        raise RuntimeError("RECORD_ERRORS:" + ",".join(records["errors"]))

    gates = contract["acceptance_gates"]
    decision_count = len(records["decision_interfaces"])
    blocked_issuers = sum(row["candidate_graduation_status"] == "BLOCKED_EVIDENCE_AND_DECISION_REQUIREMENTS_PENDING" for row in records["decision_interfaces"])
    reference_count = sum(row["candidate_graduation_status"] == "NOT_APPLICABLE_REFERENCE_INSTRUMENT" for row in records["decision_interfaces"])
    if len(records["rules"]) != gates["graduation_rule_count"]:
        raise RuntimeError("RULE_COUNT")
    if len(records["assessments"]) != gates["graduation_rule_assessment_count"]:
        raise RuntimeError("ASSESSMENT_COUNT")
    expected_assessment_counts = {
        "PASS": gates["rule_assessment_pass_count"],
        "FAIL": gates["rule_assessment_fail_count"],
        "NOT_APPLICABLE": gates["rule_assessment_not_applicable_count"],
    }
    if records["assessment_counts"] != expected_assessment_counts:
        raise RuntimeError("ASSESSMENT_STATUS_COUNTS:" + stable_json(records["assessment_counts"]))
    if decision_count != gates["decision_interface_count"] or len(records["approvals"]) != gates["human_approval_state_count"]:
        raise RuntimeError("DECISION_OR_APPROVAL_COUNT")
    if len(records["guardrails"]) != gates["guardrail_status_count"]:
        raise RuntimeError("GUARDRAIL_COUNT")
    if blocked_issuers != gates["blocked_issuer_count"] or reference_count != gates["not_applicable_reference_count"]:
        raise RuntimeError("GRADUATION_DISPOSITION_COUNTS")

    candidate_root.mkdir(parents=True, exist_ok=True)
    contract_sha = sha256_file(repo_root / CONTRACT_PATH)
    integration_manifest_sha = sha256_file(repo_root / INTEGRATION_ROOT / "FMDL6X4B_MANIFEST.json")
    factor_coverage_sha = sha256_file(repo_root / FACTOR_COVERAGE_PATH)
    peer_coverage_sha = sha256_file(repo_root / PEER_COVERAGE_PATH)
    release_fingerprint = record_hash("FMDL6X4C_RELEASE", contract_sha, integration_manifest_sha, factor_coverage_sha, peer_coverage_sha)
    release_id = f"FMDL6X4C_20260723_{release_fingerprint[:12]}"

    shard_zip, shards = build_shards(records, contract["storage_contract"]["bucket_count"], accepted_at)
    (candidate_root / "FMDL6X4C_GRADUATION_SHARDS.zip").write_bytes(shard_zip)
    (candidate_root / "FMDL6X4C_REVIEW_QUEUES.zip").write_bytes(build_queue_zip(records["queues"]))

    coverage = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "security_count": decision_count,
        "issuer_candidate_scope_count": blocked_issuers,
        "reference_instrument_count": reference_count,
        "graduation_rule_count": len(records["rules"]),
        "graduation_rule_assessment_count": len(records["assessments"]),
        "decision_interface_count": decision_count,
        "human_approval_state_count": len(records["approvals"]),
        "guardrail_status_count": len(records["guardrails"]),
        "graduation_event_count": 0,
        "formal_candidate_promotion_count": 0,
        "investment_recommendation_count": 0,
        "research_priority_is_candidate_status": False,
        "candidate_status_is_trade_authority": False,
    }
    write_json(candidate_root / "FMDL6X4C_COVERAGE_REPORT.json", coverage)
    write_json(candidate_root / "FMDL6X4C_RULE_REGISTRY.json", {"phase_id": PHASE_ID, "release_id": release_id, "rule_count": len(records["rules"]), "rules": records["rules"]})
    write_json(candidate_root / "FMDL6X4C_GUARDRAIL_REGISTRY.json", {"phase_id": PHASE_ID, "release_id": release_id, "guardrail_count": len(records["guardrails"]), "guardrails": records["guardrails"]})
    write_json(candidate_root / "FMDL6X4C_QUEUE_SUMMARY.json", {"phase_id": PHASE_ID, "release_id": release_id, "queue_counts": {name: len(rows) for name, rows in sorted(records["queues"].items())}})
    write_json(candidate_root / "FMDL6X4C_GRADUATION_EVENT_REGISTER.json", {"phase_id": PHASE_ID, "release_id": release_id, "graduation_event_count": 0, "events": []})

    quality = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "quality_status": "PASS",
        "security_count": decision_count,
        "graduation_rule_count": len(records["rules"]),
        "graduation_rule_assessment_count": len(records["assessments"]),
        "rule_assessment_status_counts": records["assessment_counts"],
        "decision_interface_count": decision_count,
        "human_approval_state_count": len(records["approvals"]),
        "guardrail_status_count": len(records["guardrails"]),
        "blocked_issuer_count": blocked_issuers,
        "not_applicable_reference_count": reference_count,
        "graduation_event_count": 0,
        "formal_candidate_promotion_count": 0,
        "investment_recommendation_count": 0,
        "neutral_fill_count": 0,
        "manifested_shard_count": len(shards),
        "expected_shard_count": gates["logical_shard_count"],
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    if len(shards) != gates["logical_shard_count"]:
        quality["quality_status"] = "FAIL"
        quality["errors"] = ["SHARD_COUNT"]
    write_json(candidate_root / "FMDL6X4C_QUALITY_REPORT.json", quality)
    if quality["quality_status"] != "PASS":
        raise RuntimeError("QUALITY_ERRORS")

    source_binding = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "input_release_id": contract["entry_gate"]["required_release_id"],
        "input_manifest_sha256": integration_manifest_sha,
        "factor_coverage_sha256": factor_coverage_sha,
        "peer_coverage_sha256": peer_coverage_sha,
        "registered_workflow_output_count": inputs["summary"]["registered_workflow_output_count"],
        "market_data_grade": inputs["factor_coverage"]["market_data_grade"],
        "valuation_factor_observation_count": inputs["factor_coverage"]["valuation_factor_observation_count"],
        "formal_peer_group_count": inputs["peer_coverage"]["formal_peer_group_count"],
        "neutral_fill_used": False,
        "silent_source_substitution": False,
        "automatic_approval_used": False,
        "candidate_promotion_emitted": False,
        "investment_recommendation_emitted": False,
        "trade_authority": "NONE",
    }
    write_json(candidate_root / "FMDL6X4C_SOURCE_BINDING.json", source_binding)

    decision = {
        "phase_id": PHASE_ID,
        "status": EXIT_STATUS,
        "release_id": release_id,
        "release_sequence": 44,
        "accepted_at": accepted_at,
        "source_commit": source_commit,
        "input_release_id": contract["entry_gate"]["required_release_id"],
        "next_gate": NEXT_GATE,
        "graduation_framework_status": "CANDIDATE_GRADUATION_INTERFACE_AND_GUARDRAILS_ACCEPTED_WITH_ZERO_GRADUATIONS",
        "blocked_issuer_count": blocked_issuers,
        "not_applicable_reference_count": reference_count,
        "graduation_event_count": 0,
        "formal_candidate_promotion_count": 0,
        "investment_recommendation_count": 0,
        "fmdl6x4_final_gate": "OPEN_FOR_FMDL6X4_FINAL_RECONCILIATION_ONLY",
        "investment_os_candidate_pool_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X4C",
        "simulation_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X4C",
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    write_json(candidate_root / "FMDL6X4C_DECISION.json", decision)

    handoff = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "next_gate": NEXT_GATE,
        "handoff_status": "OPEN_FOR_FMDL6X4_FINAL_RECONCILIATION_ONLY",
        "accepted_rule_count": len(records["rules"]),
        "accepted_guardrail_count": len(records["guardrails"]),
        "graduation_event_count": 0,
        "candidate_pool_authorized": False,
        "simulation_authorized": False,
        "brokerage_channel_available": False,
        "required_next_controls": [
            "RECONCILE_RELEASES_42_43_44_AND_CURRENT_RELEASE_LKG_PARITY",
            "VERIFY_ZERO_WORKFLOW_EXECUTION_ZERO_GRADUATION_AND_ZERO_INVESTMENT_ACTIONS",
            "FREEZE_PUBLIC_EQUITY_INVESTING_INTEGRATION_OPERATIONAL_BASELINE",
            "PRESERVE_HUMAN_DECISION_AUTHORITY_AND_ZERO_TRADE_AUTHORITY"
        ],
        "trade_authority": "NONE",
    }
    write_json(candidate_root / "FMDL6X4C_FMDL6X4FINAL_HANDOFF.json", handoff)

    manifest_files: dict[str, Any] = {}
    for path in sorted(candidate_root.iterdir()):
        if path.name == "FMDL6X4C_MANIFEST.json" or not path.is_file():
            continue
        manifest_files[path.name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    manifest = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": 44,
        "generated_at": accepted_at,
        "contract_sha256": contract_sha,
        "input_manifest_sha256": integration_manifest_sha,
        "factor_coverage_sha256": factor_coverage_sha,
        "peer_coverage_sha256": peer_coverage_sha,
        "files": manifest_files,
        "shards": shards,
    }
    write_json(candidate_root / "FMDL6X4C_MANIFEST.json", manifest)
    return {"decision": decision, "quality": quality, "coverage": coverage}


def validate_candidate(repo_root: Path, candidate_root: Path, accepted_at: str, source_commit: str, acceptance_path: Path) -> dict[str, Any]:
    replay = candidate_root.parent / (candidate_root.name + "_replay")
    if replay.exists():
        shutil.rmtree(replay)
    build_candidate(repo_root, replay, accepted_at, source_commit)
    left = {path.name: sha256_file(path) for path in candidate_root.iterdir() if path.is_file()}
    right = {path.name: sha256_file(path) for path in replay.iterdir() if path.is_file()}
    errors: list[str] = []
    if left != right:
        errors.append("SAME_INPUT_REPLAY_MISMATCH")
    manifest = load_json(candidate_root / "FMDL6X4C_MANIFEST.json")
    for name, meta in manifest["files"].items():
        path = candidate_root / name
        if not path.is_file() or path.stat().st_size != meta["bytes"] or sha256_file(path) != meta["sha256"]:
            errors.append("MANIFEST_FILE:" + name)
    decision = load_json(candidate_root / "FMDL6X4C_DECISION.json")
    if decision.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")
    result = {
        "phase_id": PHASE_ID,
        "status": "PASS" if not errors else "FAIL",
        "same_input_replay": "PASS" if left == right else "FAIL",
        "release_id": decision.get("release_id"),
        "errors": errors,
    }
    write_json(acceptance_path, result)
    if errors:
        raise RuntimeError("ACCEPTANCE_ERRORS:" + ",".join(errors))
    return result


def publish(repo_root: Path, candidate_root: Path, published_at: str, source_commit: str) -> dict[str, Any]:
    contract = load_json(repo_root / CONTRACT_PATH)
    decision = load_json(candidate_root / "FMDL6X4C_DECISION.json")
    release_id = decision["release_id"]
    current = repo_root / contract["storage_contract"]["current_root"]
    release = repo_root / contract["storage_contract"]["release_root"].replace("<release_id>", release_id)
    normalized = repo_root / contract["storage_contract"]["normalized_root"].replace("<release_id>", release_id)
    archive_root = repo_root / contract["storage_contract"]["archive_root"]
    if release.exists():
        raise RuntimeError("IMMUTABLE_RELEASE_COLLISION")
    if current.exists():
        archive = archive_root / f"candidate_graduation_guardrails_{published_at.replace(':', '').replace('-', '')}"
        copytree_replace(current, archive)
    copytree_replace(candidate_root, current)
    copytree_replace(candidate_root, release)
    copytree_replace(candidate_root, normalized)
    manifest_sha = sha256_file(current / "FMDL6X4C_MANIFEST.json")
    pointer = {
        "phase_id": PHASE_ID,
        "status": EXIT_STATUS,
        "release_id": release_id,
        "release_sequence": 44,
        "published_at": published_at,
        "source_commit": source_commit,
        "input_release_id": decision["input_release_id"],
        "current_path": str(current.relative_to(repo_root)),
        "release_path": str(release.relative_to(repo_root)),
        "normalized_path": str(normalized.relative_to(repo_root)),
        "manifest_sha256": manifest_sha,
        "graduation_framework_status": decision["graduation_framework_status"],
        "blocked_issuer_count": decision["blocked_issuer_count"],
        "not_applicable_reference_count": decision["not_applicable_reference_count"],
        "graduation_event_count": 0,
        "formal_candidate_promotion_count": 0,
        "investment_recommendation_count": 0,
        "next_gate": NEXT_GATE,
        "fmdl6x4_final_gate": decision["fmdl6x4_final_gate"],
        "investment_os_candidate_pool_gate": decision["investment_os_candidate_pool_gate"],
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    write_json(repo_root / contract["storage_contract"]["last_success"], pointer)
    lkg = {
        **pointer,
        "lkg_scope": "FMDL6X4_CANDIDATE_GRADUATION_DECISION_INTERFACE_AND_GUARDRAILS_DOMAIN",
        "lkg_reason": "LATEST_ACCEPTED_GRADUATION_RULES_DECISION_INTERFACE_AND_GUARDRAILS_WITH_ZERO_GRADUATIONS",
    }
    write_json(repo_root / contract["storage_contract"]["last_known_good"], lkg)
    return pointer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate-contract")
    for name in ("build", "validate-candidate", "publish"):
        command = sub.add_parser(name)
        command.add_argument("--candidate", required=True)
        if name in {"build", "validate-candidate"}:
            command.add_argument("--accepted-at", required=True)
            command.add_argument("--source-commit", required=True)
        if name == "validate-candidate":
            command.add_argument("--acceptance", required=True)
        if name == "publish":
            command.add_argument("--published-at", required=True)
            command.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root)
    if args.cmd == "validate-contract":
        contract, errors = validate_contract(root)
        print({"phase_id": contract.get("phase_id"), "errors": errors})
        if errors:
            raise SystemExit(1)
    elif args.cmd == "build":
        build_candidate(root, Path(args.candidate), args.accepted_at, args.source_commit)
    elif args.cmd == "validate-candidate":
        validate_candidate(root, Path(args.candidate), args.accepted_at, args.source_commit, Path(args.acceptance))
    elif args.cmd == "publish":
        publish(root, Path(args.candidate), args.published_at, args.source_commit)


if __name__ == "__main__":
    main()
