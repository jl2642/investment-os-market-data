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

PHASE_ID = "FMDL-6X4-B"
EXIT_STATUS = "FMDL6X4B_RESEARCH_WORKFLOW_INTEGRATION_AND_EVIDENCE_REGISTRATION_ACCEPTED"
NEXT_GATE = "FMDL-6X4-C_CANDIDATE_GRADUATION_DECISION_INTERFACE_AND_GUARDRAILS"
CONTRACT_PATH = Path("config/fmdl6x4b_research_workflow_integration_contract.json")
ADAPTER_ROOT = Path("outputs/fmdl6x4/current/public_equity_investing_adapter")

SOURCE_PATHS = {
    "FMDL6X3A_READINESS": Path("outputs/fmdl6x3/current/research_universe_readiness/FMDL6X3A_MANIFEST.json"),
    "FMDL6X3B_FINANCIAL_NORMALIZATION": Path("outputs/fmdl6x3/current/financial_normalization/FMDL6X3B_MANIFEST.json"),
    "FMDL6X3C_FACTOR_ENGINE": Path("outputs/fmdl6x3/current/factor_engine/FMDL6X3C_MANIFEST.json"),
    "FMDL6X3D_SECTOR_PEER_BENCHMARK": Path("outputs/fmdl6x3/current/sector_peer_benchmark/FMDL6X3D_MANIFEST.json"),
    "FMDL6X3E_SCREENING_RESEARCH_CARDS": Path("outputs/fmdl6x3/current/screening_research_cards/FMDL6X3E_MANIFEST.json"),
    "FMDL6X3FINAL_RECONCILIATION": Path("outputs/fmdl6x3/current/research_production_final/FMDL6X3FINAL_MANIFEST.json"),
    "FMDL6X4A_ADAPTER": ADAPTER_ROOT / "FMDL6X4A_MANIFEST.json",
}

SOURCE_METADATA = {
    "FMDL6X3A_READINESS": ("READINESS_AND_OFFICIAL_FILING_POSTURE", "DECISION_GRADE_OFFICIAL_SEC_WHERE_AVAILABLE"),
    "FMDL6X3B_FINANCIAL_NORMALIZATION": ("OFFICIAL_SEC_FACTS_AND_NORMALIZED_FINANCIALS", "DECISION_GRADE_OFFICIAL_SEC_DERIVED_WHERE_AVAILABLE"),
    "FMDL6X3C_FACTOR_ENGINE": ("QUALITY_MARKET_AND_RISK_FACTOR_STORE", "MIXED_OFFICIAL_FINANCIAL_AND_NON_DECISION_GRADE_MARKET"),
    "FMDL6X3D_SECTOR_PEER_BENCHMARK": ("CLASSIFICATION_PEER_AND_BENCHMARK_FRAMEWORK", "MIXED_OFFICIAL_CLASSIFICATION_AND_NON_DECISION_GRADE_MARKET"),
    "FMDL6X3E_SCREENING_RESEARCH_CARDS": ("SCREENING_RESEARCH_CARDS_AND_BENCHMARK_POOL", "RESEARCH_PRODUCTION_DERIVED"),
    "FMDL6X3FINAL_RECONCILIATION": ("RESEARCH_PRODUCTION_RECONCILIATION", "ACCEPTED_OPERATIONAL_BASELINE"),
    "FMDL6X4A_ADAPTER": ("PUBLIC_EQUITY_INVESTING_ADAPTER", "CONTRACT_MAPPING_ONLY"),
}


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
    else:
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

    for source_path in SOURCE_PATHS.values():
        if not (repo_root / source_path).is_file():
            errors.append("SOURCE_MISSING:" + str(source_path))

    required_adapter = [
        "FMDL6X4A_ADAPTER_SHARDS.zip",
        "FMDL6X4A_WORKFLOW_CONTRACT_REGISTRY.json",
        "FMDL6X4A_SOURCE_CATEGORY_REGISTRY.json",
        "FMDL6X4A_MAPPING_SUMMARY.json",
        "FMDL6X4A_FMDL6X4B_HANDOFF.json",
        "FMDL6X4A_SOURCE_BINDING.json",
    ]
    for name in required_adapter:
        if not (repo_root / ADAPTER_ROOT / name).is_file():
            errors.append("ADAPTER_INPUT_MISSING:" + name)

    expected = {
        "source_registry_count": 7,
        "evidence_registration_count": 53,
        "security_evidence_ledger_count": 7,
        "workflow_contract_count": 14,
        "security_workflow_mapping_count": 98,
        "invocation_envelope_count": 10,
        "output_registration_contract_count": 14,
        "logical_shard_count": 320,
        "formal_workflow_execution_count": 0,
        "registered_workflow_output_count": 0,
        "investment_recommendation_count": 0,
        "candidate_promotion_count": 0,
        "neutral_fill_count": 0,
    }
    gates = contract.get("acceptance_gates", {})
    for key, value in expected.items():
        if gates.get(key) != value:
            errors.append("ACCEPTANCE_GATE:" + key)
    return contract, sorted(set(errors))


def load_inputs(repo_root: Path) -> dict[str, Any]:
    adapter_zip = repo_root / ADAPTER_ROOT / "FMDL6X4A_ADAPTER_SHARDS.zip"
    return {
        "payloads": read_zip_jsonl(adapter_zip, "ADAPTER_PAYLOAD/"),
        "mappings": read_zip_jsonl(adapter_zip, "SECURITY_WORKFLOW_MAPPING/"),
        "workflow_contracts": read_zip_jsonl(adapter_zip, "WORKFLOW_CONTRACT/"),
        "source_requirements": read_zip_jsonl(adapter_zip, "SOURCE_CATEGORY_REQUIREMENT/"),
        "workflow_registry": load_json(repo_root / ADAPTER_ROOT / "FMDL6X4A_WORKFLOW_CONTRACT_REGISTRY.json"),
        "source_category_registry": load_json(repo_root / ADAPTER_ROOT / "FMDL6X4A_SOURCE_CATEGORY_REGISTRY.json"),
        "mapping_summary": load_json(repo_root / ADAPTER_ROOT / "FMDL6X4A_MAPPING_SUMMARY.json"),
        "handoff": load_json(repo_root / ADAPTER_ROOT / "FMDL6X4A_FMDL6X4B_HANDOFF.json"),
        "source_binding": load_json(repo_root / ADAPTER_ROOT / "FMDL6X4A_SOURCE_BINDING.json"),
    }


def source_registry(repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    rows: list[dict[str, Any]] = []
    ids: dict[str, str] = {}
    for key, path in sorted(SOURCE_PATHS.items()):
        source_sha = sha256_file(repo_root / path)
        source_id = "PEISOURCE-" + record_hash("PEI_SOURCE", key, source_sha)[:24]
        ids[key] = source_id
        source_scope, grade = SOURCE_METADATA[key]
        rows.append({
            "source_id": source_id,
            "source_key": key,
            "source_scope": source_scope,
            "source_artifact_path": str(path),
            "source_manifest_sha256": source_sha,
            "evidence_grade": grade,
            "runtime_connector_readiness_claimed": False,
            "silent_weaker_source_substitution_allowed": False,
            "trade_authority": "NONE",
        })
    return rows, ids


def add_evidence(
    rows: list[dict[str, Any]],
    payload: dict[str, Any],
    evidence_type: str,
    source: dict[str, Any],
    grade: str,
    label: str,
    as_of_date: str,
    notes: str,
) -> str:
    evidence_id = "PEIEVID-" + record_hash(
        "PEI_EVIDENCE", payload["canonical_security_id"], evidence_type, source["source_id"]
    )[:24]
    rows.append({
        "evidence_registration_id": evidence_id,
        "canonical_security_id": payload["canonical_security_id"],
        "canonical_issuer_id": payload["canonical_issuer_id"],
        "symbol": payload["symbol"],
        "research_card_id": payload["research_card_id"],
        "evidence_type": evidence_type,
        "source_id": source["source_id"],
        "source_artifact_path": source["source_artifact_path"],
        "source_manifest_sha256": source["source_manifest_sha256"],
        "evidence_grade": grade,
        "evidence_label": label,
        "as_of_date": as_of_date,
        "notes": notes,
        "workflow_output_registration_id": None,
        "candidate_pool_promotion_authorized": False,
        "investment_recommendation_authorized": False,
        "trade_authority": "NONE",
    })
    return evidence_id


def build_records(repo_root: Path, inputs: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    payloads = sorted(inputs["payloads"], key=lambda row: row["canonical_security_id"])
    mappings = sorted(inputs["mappings"], key=lambda row: row["mapping_id"])
    workflows = sorted(inputs["workflow_contracts"], key=lambda row: row["workflow_slug"])
    errors: list[str] = []
    if len(payloads) != 7:
        errors.append("PAYLOAD_COUNT")
    if len(mappings) != 98:
        errors.append("MAPPING_COUNT")
    if len(workflows) != 14:
        errors.append("WORKFLOW_COUNT")
    if inputs["handoff"].get("workflow_execution_authorized") is not False:
        errors.append("HANDOFF_EXECUTION_BOUNDARY")

    sources, _ = source_registry(repo_root)
    source_by_key = {row["source_key"]: row for row in sources}
    evidence: list[dict[str, Any]] = []
    evidence_ids_by_security: dict[str, list[str]] = defaultdict(list)
    as_of_date = contract["as_of_date"]

    for payload in payloads:
        security_id = payload["canonical_security_id"]
        posture = payload["evidence_posture"]

        def register(evidence_type: str, source_key: str, grade: str, label: str, notes: str) -> None:
            evidence_id = add_evidence(
                evidence, payload, evidence_type, source_by_key[source_key], grade, label, as_of_date, notes
            )
            evidence_ids_by_security[security_id].append(evidence_id)

        register(
            "CANONICAL_IDENTITY",
            "FMDL6X3A_READINESS",
            "CANONICAL_IDENTITY_ACCEPTED",
            "fact_provider_standardized",
            "Canonical Security and Issuer identity accepted by the readiness domain.",
        )
        register(
            "RESEARCH_CARD",
            "FMDL6X3E_SCREENING_RESEARCH_CARDS",
            "RESEARCH_PRODUCTION_DERIVED",
            "derived_calculation",
            "Research Card registered as workflow context, not an investment recommendation.",
        )
        register(
            "BENCHMARK_POOL_MEMBERSHIP",
            "FMDL6X3E_SCREENING_RESEARCH_CARDS",
            "RESEARCH_ONLY_ACCEPTED",
            "derived_calculation",
            "Membership in US_RESEARCH_BENCHMARK_POOL_V1; not Candidate Pool membership.",
        )
        register(
            "MARKET_RISK_FACTOR_SNAPSHOT",
            "FMDL6X3C_FACTOR_ENGINE",
            posture["market_source_grade"],
            "fact_provider_standardized",
            "Market and risk snapshot remains non-decision-grade fallback data.",
        )

        if posture["classification_status"] == "OFFICIAL_SEC_SIC_LINKED_INTERNAL_CROSSWALK":
            register(
                "OFFICIAL_CLASSIFICATION",
                "FMDL6X3D_SECTOR_PEER_BENCHMARK",
                "OFFICIAL_SEC_SIC_WITH_INTERNAL_CROSSWALK",
                "fact_source_reported",
                "SEC SIC evidence with internal crosswalk; not GICS or ICB.",
            )
        if int(posture.get("official_filing_count", 0)) > 0:
            register(
                "OFFICIAL_SEC_FILING_POSTURE",
                "FMDL6X3A_READINESS",
                "OFFICIAL_SEC_FILING_ACCEPTED",
                "fact_source_reported",
                f"{posture['official_filing_count']} official filing registration(s) available upstream.",
            )
        if int(posture.get("official_fact_count", 0)) > 0:
            register(
                "OFFICIAL_SEC_FACT_SET",
                "FMDL6X3B_FINANCIAL_NORMALIZATION",
                "DECISION_GRADE_OFFICIAL_SEC",
                "fact_source_reported",
                f"{posture['official_fact_count']} official SEC facts available upstream.",
            )
            register(
                "FINANCIAL_NORMALIZATION_BASELINE",
                "FMDL6X3B_FINANCIAL_NORMALIZATION",
                "PARTIAL_QUARTERLY_MODEL_LOADABLE",
                "derived_calculation",
                "Quarterly income-statement normalization only; TTM, annual, balance sheet and cash flow remain blocked.",
            )
            register(
                "QUALITY_FACTOR_SNAPSHOT",
                "FMDL6X3C_FACTOR_ENGINE",
                "QUARTERLY_QUALITY_SANDBOX_ONLY",
                "derived_calculation",
                "Single-quarter non-sector-neutral quality factor snapshot.",
            )
            register(
                "BENCHMARK_RELATIVE_FACTOR_SNAPSHOT",
                "FMDL6X3D_SECTOR_PEER_BENCHMARK",
                "NON_DECISION_GRADE_RELATIVE_SANDBOX_ONLY",
                "derived_calculation",
                "Relative-to-QQQ sandbox factors; not a formal benchmark or trade signal.",
            )
        if payload["symbol"] == "QQQ":
            register(
                "BENCHMARK_IDENTITY",
                "FMDL6X3D_SECTOR_PEER_BENCHMARK",
                "OFFICIAL_BENCHMARK_IDENTITY_NON_DECISION_MARKET",
                "fact_source_reported",
                "QQQ registered as Nasdaq-100 reference instrument; market data remains non-decision-grade.",
            )

    evidence.sort(key=lambda row: row["evidence_registration_id"])
    if len(evidence) != 53:
        errors.append("EVIDENCE_COUNT")

    ledgers: list[dict[str, Any]] = []
    for payload in payloads:
        security_id = payload["canonical_security_id"]
        ids = sorted(evidence_ids_by_security[security_id])
        type_counts = Counter(
            row["evidence_type"] for row in evidence if row["canonical_security_id"] == security_id
        )
        ledgers.append({
            "security_evidence_ledger_id": "PEILEDGER-" + record_hash("PEI_LEDGER", security_id)[:24],
            "canonical_security_id": security_id,
            "canonical_issuer_id": payload["canonical_issuer_id"],
            "symbol": payload["symbol"],
            "research_card_id": payload["research_card_id"],
            "evidence_registration_ids": ids,
            "evidence_registration_count": len(ids),
            "evidence_type_counts": dict(sorted(type_counts.items())),
            "runtime_source_check_required": True,
            "candidate_pool_promotion_authorized": False,
            "trade_authority": "NONE",
        })
    ledgers.sort(key=lambda row: row["canonical_security_id"])

    output_contracts: list[dict[str, Any]] = []
    for workflow in workflows:
        output_contracts.append({
            "output_registration_contract_id": "PEIOUTCONTRACT-" + record_hash(
                "PEI_OUTPUT_CONTRACT", workflow["workflow_slug"]
            )[:24],
            "workflow_contract_id": workflow["workflow_contract_id"],
            "workflow_slug": workflow["workflow_slug"],
            "owning_artifact": workflow["owning_artifact"],
            "required_registration_fields": [
                "workflow_output_registration_id",
                "workflow_contract_id",
                "invocation_envelope_id",
                "canonical_security_id",
                "canonical_issuer_id",
                "source_ids",
                "evidence_registration_ids",
                "as_of_date",
                "evidence_labels",
                "quality_status",
                "artifact_location",
                "artifact_sha256",
                "workflow_owner",
                "investment_recommendation_status",
                "candidate_pool_status",
                "trade_authority",
            ],
            "append_only_evidence_registration_required": True,
            "runtime_source_check_required": True,
            "workflow_execution_authorized": False,
            "registered_workflow_output_count": 0,
            "investment_recommendation_authorized": False,
            "candidate_pool_promotion_authorized": False,
            "trade_authority": "NONE",
        })
    output_contracts.sort(key=lambda row: row["workflow_slug"])

    status_map = {
        "PARTIAL_ADAPTER_READY": "INVOCATION_ENVELOPE_REGISTERED_RUNTIME_SOURCE_CHECK_PENDING",
        "HUMAN_CONFIRMATION_REQUIRED": "WAITING_USER_CONFIRMATION",
        "BLOCKED_REQUIRED_INPUTS_MISSING": "BLOCKED_REQUIRED_INPUTS_MISSING",
        "NOT_APPLICABLE_REFERENCE_INSTRUMENT": "NOT_APPLICABLE_REFERENCE_INSTRUMENT",
    }
    payload_by_security = {row["canonical_security_id"]: row for row in payloads}
    evidence_by_security = {
        security_id: sorted(evidence_ids_by_security[security_id]) for security_id in payload_by_security
    }
    source_ids_by_security = {
        security_id: sorted({
            row["source_id"] for row in evidence if row["canonical_security_id"] == security_id
        })
        for security_id in payload_by_security
    }
    output_by_workflow = {row["workflow_slug"]: row for row in output_contracts}
    integration_states: list[dict[str, Any]] = []
    envelopes: list[dict[str, Any]] = []

    for mapping in mappings:
        integration_status = status_map[mapping["adapter_status"]]
        state = {
            "workflow_integration_state_id": "PEIINT-" + record_hash(
                "PEI_INTEGRATION_STATE", mapping["mapping_id"]
            )[:24],
            "mapping_id": mapping["mapping_id"],
            "workflow_contract_id": mapping["workflow_contract_id"],
            "workflow_slug": mapping["workflow_slug"],
            "canonical_security_id": mapping["canonical_security_id"],
            "canonical_issuer_id": mapping["canonical_issuer_id"],
            "symbol": mapping["symbol"],
            "adapter_status": mapping["adapter_status"],
            "integration_status": integration_status,
            "blocker_codes": mapping["blocker_codes"],
            "human_confirmation_prompt": mapping["human_confirmation_prompt"],
            "runtime_source_check_required": mapping["runtime_source_check_required"],
            "invocation_envelope_id": None,
            "workflow_output_registration_contract_id": output_by_workflow[mapping["workflow_slug"]][
                "output_registration_contract_id"
            ],
            "workflow_execution_authorized": False,
            "registered_workflow_output_count": 0,
            "investment_recommendation_authorized": False,
            "candidate_pool_promotion_authorized": False,
            "trade_authority": "NONE",
        }
        if mapping["adapter_status"] == "PARTIAL_ADAPTER_READY":
            payload = payload_by_security[mapping["canonical_security_id"]]
            envelope_id = "PEIINVOKE-" + record_hash(
                "PEI_INVOCATION", mapping["mapping_id"], payload["adapter_payload_id"]
            )[:24]
            state["invocation_envelope_id"] = envelope_id
            envelopes.append({
                "invocation_envelope_id": envelope_id,
                "adapter_payload_id": payload["adapter_payload_id"],
                "mapping_id": mapping["mapping_id"],
                "workflow_contract_id": mapping["workflow_contract_id"],
                "workflow_slug": mapping["workflow_slug"],
                "canonical_security_id": mapping["canonical_security_id"],
                "canonical_issuer_id": mapping["canonical_issuer_id"],
                "symbol": mapping["symbol"],
                "research_card_id": mapping["research_card_id"],
                "source_ids": source_ids_by_security[mapping["canonical_security_id"]],
                "evidence_registration_ids": evidence_by_security[mapping["canonical_security_id"]],
                "minimum_required_inputs": mapping["minimum_required_inputs"],
                "required_source_categories": mapping["required_source_categories"],
                "runtime_source_check_status": "PENDING_NOT_EXECUTED",
                "human_confirmation_status": "NOT_REQUIRED_FOR_ENVELOPE_MATERIALIZATION",
                "execution_status": "NOT_EXECUTED",
                "workflow_execution_authorized": False,
                "workflow_output_registration_contract_id": output_by_workflow[mapping["workflow_slug"]][
                    "output_registration_contract_id"
                ],
                "registered_workflow_output_id": None,
                "investment_recommendation_authorized": False,
                "candidate_pool_promotion_authorized": False,
                "trade_authority": "NONE",
            })
        integration_states.append(state)

    integration_states.sort(key=lambda row: row["workflow_integration_state_id"])
    envelopes.sort(key=lambda row: row["invocation_envelope_id"])
    integration_counts = Counter(row["integration_status"] for row in integration_states)
    if dict(sorted(integration_counts.items())) != dict(sorted(
        contract["integration_contract"]["integration_state_counts"].items()
    )):
        errors.append("INTEGRATION_STATE_COUNTS")
    if len(envelopes) != 10:
        errors.append("INVOCATION_ENVELOPE_COUNT")
    if len(output_contracts) != 14:
        errors.append("OUTPUT_CONTRACT_COUNT")

    queues = {
        "RUNTIME_SOURCE_CHECK_QUEUE": [
            {
                "invocation_envelope_id": row["invocation_envelope_id"],
                "canonical_security_id": row["canonical_security_id"],
                "symbol": row["symbol"],
                "workflow_slug": row["workflow_slug"],
                "required_source_categories": row["required_source_categories"],
                "required_action": "PERFORM_MINIMUM_NATIVE_RUNTIME_SOURCE_CHECK_BEFORE_WORKFLOW_EXECUTION",
            }
            for row in envelopes
        ],
        "HUMAN_CONFIRMATION_QUEUE": [
            {
                "mapping_id": row["mapping_id"],
                "canonical_security_id": row["canonical_security_id"],
                "symbol": row["symbol"],
                "workflow_slug": row["workflow_slug"],
                "human_confirmation_prompt": row["human_confirmation_prompt"],
            }
            for row in mappings if row["adapter_status"] == "HUMAN_CONFIRMATION_REQUIRED"
        ],
        "BLOCKED_INPUT_QUEUE": [
            {
                "mapping_id": row["mapping_id"],
                "canonical_security_id": row["canonical_security_id"],
                "symbol": row["symbol"],
                "workflow_slug": row["workflow_slug"],
                "blocker_codes": row["blocker_codes"],
            }
            for row in mappings if row["adapter_status"] == "BLOCKED_REQUIRED_INPUTS_MISSING"
        ],
        "NOT_APPLICABLE_REGISTRY": [
            {
                "mapping_id": row["mapping_id"],
                "canonical_security_id": row["canonical_security_id"],
                "symbol": row["symbol"],
                "workflow_slug": row["workflow_slug"],
            }
            for row in mappings if row["adapter_status"] == "NOT_APPLICABLE_REFERENCE_INSTRUMENT"
        ],
    }
    for rows in queues.values():
        rows.sort(key=stable_json)

    return {
        "source_registry": sources,
        "evidence": evidence,
        "ledgers": ledgers,
        "output_contracts": output_contracts,
        "integration_states": integration_states,
        "envelopes": envelopes,
        "queues": queues,
        "errors": errors,
    }


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(stable_json(row) + "\n" for row in rows).encode("utf-8")


def build_shards(
    records: dict[str, Any], bucket_count: int, generated_at: str
) -> tuple[bytes, list[dict[str, Any]]]:
    domains = (
        ("EVIDENCE_REGISTRATION", records["evidence"], "evidence_registration_id"),
        ("SECURITY_EVIDENCE_LEDGER", records["ledgers"], "canonical_security_id"),
        ("WORKFLOW_INTEGRATION_STATE", records["integration_states"], "workflow_integration_state_id"),
        ("INVOCATION_ENVELOPE", records["envelopes"], "invocation_envelope_id"),
        ("OUTPUT_REGISTRATION_CONTRACT", records["output_contracts"], "output_registration_contract_id"),
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
    return deterministic_zip({
        f"{name}.jsonl": jsonl_bytes(rows) for name, rows in sorted(queues.items())
    })


def build_candidate(
    repo_root: Path, candidate_root: Path, accepted_at: str, source_commit: str
) -> dict[str, Any]:
    contract, contract_errors = validate_contract(repo_root)
    if contract_errors:
        raise RuntimeError("CONTRACT_ERRORS:" + ",".join(contract_errors))
    inputs = load_inputs(repo_root)
    records = build_records(repo_root, inputs, contract)
    if records["errors"]:
        raise RuntimeError("RECORD_ERRORS:" + ",".join(records["errors"]))

    candidate_root.mkdir(parents=True, exist_ok=True)
    release_fingerprint = record_hash(
        "FMDL6X4B_RELEASE",
        sha256_file(repo_root / CONTRACT_PATH),
        sha256_file(repo_root / ADAPTER_ROOT / "FMDL6X4A_MANIFEST.json"),
        *(row["source_manifest_sha256"] for row in records["source_registry"]),
    )
    release_id = f"FMDL6X4B_20260723_{release_fingerprint[:12]}"
    shard_zip, shard_manifest = build_shards(
        records, contract["storage_contract"]["bucket_count"], accepted_at
    )
    (candidate_root / "FMDL6X4B_INTEGRATION_SHARDS.zip").write_bytes(shard_zip)
    (candidate_root / "FMDL6X4B_REVIEW_QUEUES.zip").write_bytes(build_queue_zip(records["queues"]))

    write_json(candidate_root / "FMDL6X4B_SOURCE_REGISTRY.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "source_count": len(records["source_registry"]),
        "runtime_connector_readiness_claimed": False,
        "sources": records["source_registry"],
    })
    integration_counts = Counter(row["integration_status"] for row in records["integration_states"])
    write_json(candidate_root / "FMDL6X4B_INTEGRATION_SUMMARY.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "source_registry_count": len(records["source_registry"]),
        "evidence_registration_count": len(records["evidence"]),
        "security_evidence_ledger_count": len(records["ledgers"]),
        "workflow_integration_state_count": len(records["integration_states"]),
        "integration_status_counts": dict(sorted(integration_counts.items())),
        "invocation_envelope_count": len(records["envelopes"]),
        "output_registration_contract_count": len(records["output_contracts"]),
        "formal_workflow_execution_count": 0,
        "registered_workflow_output_count": 0,
    })
    queue_counts = {name: len(rows) for name, rows in sorted(records["queues"].items())}
    write_json(candidate_root / "FMDL6X4B_QUEUE_SUMMARY.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "queue_counts": queue_counts,
    })
    write_json(candidate_root / "FMDL6X4B_SOURCE_BINDING.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "input_release_id": contract["entry_gate"]["required_release_id"],
        "input_manifest_sha256": sha256_file(repo_root / ADAPTER_ROOT / "FMDL6X4A_MANIFEST.json"),
        "registered_source_ids": [row["source_id"] for row in records["source_registry"]],
        "runtime_source_check_required": True,
        "runtime_connector_readiness_claimed": False,
        "source_category_mapping_is_connector_readiness": False,
        "silent_source_substitution": False,
        "neutral_fill_used": False,
        "workflow_execution_emitted": False,
        "registered_workflow_output_emitted": False,
        "investment_recommendation_emitted": False,
        "candidate_promotion_emitted": False,
    })
    coverage = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "source_registry_count": len(records["source_registry"]),
        "evidence_registration_count": len(records["evidence"]),
        "security_evidence_ledger_count": len(records["ledgers"]),
        "workflow_contract_count": len(inputs["workflow_contracts"]),
        "security_workflow_mapping_count": len(inputs["mappings"]),
        "invocation_envelope_count": len(records["envelopes"]),
        "output_registration_contract_count": len(records["output_contracts"]),
        "workflow_execution_claimed": False,
        "registered_workflow_output_claimed": False,
        "decision_grade_handoff_claimed": False,
        "candidate_pool_integration_claimed": False,
    }
    write_json(candidate_root / "FMDL6X4B_COVERAGE_REPORT.json", coverage)
    quality = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "quality_status": "PASS",
        "source_registry_count": coverage["source_registry_count"],
        "evidence_registration_count": coverage["evidence_registration_count"],
        "security_evidence_ledger_count": coverage["security_evidence_ledger_count"],
        "workflow_contract_count": coverage["workflow_contract_count"],
        "security_workflow_mapping_count": coverage["security_workflow_mapping_count"],
        "invocation_envelope_count": coverage["invocation_envelope_count"],
        "output_registration_contract_count": coverage["output_registration_contract_count"],
        "formal_workflow_execution_count": 0,
        "registered_workflow_output_count": 0,
        "investment_recommendation_count": 0,
        "candidate_promotion_count": 0,
        "neutral_fill_count": 0,
        "manifested_shard_count": len(shard_manifest),
        "expected_shard_count": contract["acceptance_gates"]["logical_shard_count"],
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    errors: list[str] = []
    for key, expected in contract["acceptance_gates"].items():
        if key in quality and quality[key] != expected:
            errors.append("QUALITY_GATE:" + key)
    if len(shard_manifest) != 320:
        errors.append("SHARD_COUNT")
    if any(row["workflow_execution_authorized"] for row in records["envelopes"]):
        errors.append("ENVELOPE_EXECUTION_AUTHORITY")
    if errors:
        quality["quality_status"] = "FAIL"
        quality["errors"] = errors
    write_json(candidate_root / "FMDL6X4B_QUALITY_REPORT.json", quality)
    if errors:
        raise RuntimeError("QUALITY_ERRORS:" + ",".join(errors))

    decision = {
        "phase_id": PHASE_ID,
        "status": EXIT_STATUS,
        "release_id": release_id,
        "release_sequence": 43,
        "accepted_at": accepted_at,
        "source_commit": source_commit,
        "input_release_id": contract["entry_gate"]["required_release_id"],
        "next_gate": NEXT_GATE,
        "integration_status": "WORKFLOW_INTEGRATION_AND_EVIDENCE_REGISTRATION_ACCEPTED_WITH_ZERO_WORKFLOW_EXECUTION",
        "evidence_registration_count": len(records["evidence"]),
        "invocation_envelope_count": len(records["envelopes"]),
        "formal_workflow_execution_count": 0,
        "registered_workflow_output_count": 0,
        "investment_recommendation_count": 0,
        "formal_candidate_promotion_count": 0,
        "candidate_graduation_gate": "OPEN_FOR_FMDL6X4C_GUARDRAIL_DEVELOPMENT_ONLY",
        "investment_os_candidate_pool_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X4B",
        "simulation_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X4B",
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    write_json(candidate_root / "FMDL6X4B_DECISION.json", decision)
    write_json(candidate_root / "FMDL6X4B_FMDL6X4C_HANDOFF.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "next_gate": NEXT_GATE,
        "handoff_status": "OPEN_FOR_FMDL6X4C_CANDIDATE_GRADUATION_GUARDRAIL_DEVELOPMENT_ONLY",
        "registered_evidence_count": len(records["evidence"]),
        "registered_invocation_envelope_count": len(records["envelopes"]),
        "registered_workflow_output_count": 0,
        "candidate_pool_authorized": False,
        "simulation_authorized": False,
        "brokerage_channel_available": False,
        "required_next_controls": [
            "DEFINE_CANDIDATE_GRADUATION_EVIDENCE_MINIMUMS",
            "SEPARATE_RESEARCH_READINESS_FROM_INVESTMENT_DECISION_READINESS",
            "REQUIRE_REGISTERED_WORKFLOW_OUTPUTS_BEFORE_ANY_GRADUATION",
            "PRESERVE_HUMAN_DECISION_AUTHORITY_AND_ZERO_TRADE_AUTHORITY",
        ],
        "trade_authority": "NONE",
    })

    manifest_files: dict[str, Any] = {}
    for path in sorted(candidate_root.iterdir()):
        if path.name == "FMDL6X4B_MANIFEST.json" or not path.is_file():
            continue
        manifest_files[path.name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    write_json(candidate_root / "FMDL6X4B_MANIFEST.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": 43,
        "generated_at": accepted_at,
        "contract_sha256": sha256_file(repo_root / CONTRACT_PATH),
        "input_manifest_sha256": sha256_file(repo_root / ADAPTER_ROOT / "FMDL6X4A_MANIFEST.json"),
        "files": manifest_files,
        "shards": shard_manifest,
    })
    return {"decision": decision, "quality": quality, "coverage": coverage, "queue_counts": queue_counts}


def validate_candidate(
    repo_root: Path,
    candidate_root: Path,
    accepted_at: str,
    source_commit: str,
    acceptance_path: Path,
) -> dict[str, Any]:
    replay = candidate_root.parent / (candidate_root.name + "_replay")
    if replay.exists():
        shutil.rmtree(replay)
    build_candidate(repo_root, replay, accepted_at, source_commit)
    left = {path.name: sha256_file(path) for path in candidate_root.iterdir() if path.is_file()}
    right = {path.name: sha256_file(path) for path in replay.iterdir() if path.is_file()}
    errors: list[str] = [] if left == right else ["SAME_INPUT_REPLAY_MISMATCH"]
    manifest = load_json(candidate_root / "FMDL6X4B_MANIFEST.json")
    for name, meta in manifest["files"].items():
        path = candidate_root / name
        if not path.is_file() or path.stat().st_size != meta["bytes"] or sha256_file(path) != meta["sha256"]:
            errors.append("MANIFEST_FILE:" + name)
    decision = load_json(candidate_root / "FMDL6X4B_DECISION.json")
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
    decision = load_json(candidate_root / "FMDL6X4B_DECISION.json")
    release_id = decision["release_id"]
    current = repo_root / contract["storage_contract"]["current_root"]
    release = repo_root / contract["storage_contract"]["release_root"].replace("<release_id>", release_id)
    normalized = repo_root / contract["storage_contract"]["normalized_root"].replace("<release_id>", release_id)
    archive_root = repo_root / contract["storage_contract"]["archive_root"]
    if release.exists():
        raise RuntimeError("IMMUTABLE_RELEASE_COLLISION")
    if current.exists():
        archive_name = "research_workflow_integration_" + published_at.replace(":", "").replace("-", "")
        copytree_replace(current, archive_root / archive_name)
    copytree_replace(candidate_root, current)
    copytree_replace(candidate_root, release)
    copytree_replace(candidate_root, normalized)
    manifest_sha = sha256_file(current / "FMDL6X4B_MANIFEST.json")
    pointer = {
        "phase_id": PHASE_ID,
        "status": EXIT_STATUS,
        "release_id": release_id,
        "release_sequence": 43,
        "published_at": published_at,
        "source_commit": source_commit,
        "current_path": str(current.relative_to(repo_root)),
        "release_path": str(release.relative_to(repo_root)),
        "normalized_path": str(normalized.relative_to(repo_root)),
        "manifest_sha256": manifest_sha,
        "input_release_id": decision["input_release_id"],
        "integration_status": decision["integration_status"],
        "evidence_registration_count": decision["evidence_registration_count"],
        "invocation_envelope_count": decision["invocation_envelope_count"],
        "formal_workflow_execution_count": 0,
        "registered_workflow_output_count": 0,
        "investment_recommendation_count": 0,
        "formal_candidate_promotion_count": 0,
        "next_gate": NEXT_GATE,
        "candidate_graduation_gate": decision["candidate_graduation_gate"],
        "investment_os_candidate_pool_gate": decision["investment_os_candidate_pool_gate"],
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    write_json(repo_root / contract["storage_contract"]["last_success"], pointer)
    lkg = {
        **pointer,
        "lkg_scope": "FMDL6X4_RESEARCH_WORKFLOW_INTEGRATION_AND_EVIDENCE_REGISTRATION_DOMAIN",
        "lkg_reason": "LATEST_ACCEPTED_EVIDENCE_REGISTRY_AND_WORKFLOW_INTEGRATION_BASELINE_WITH_ZERO_EXECUTION",
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
    repo_root = Path(args.repo_root)
    if args.cmd == "validate-contract":
        _, errors = validate_contract(repo_root)
        print({"errors": errors})
        raise SystemExit(1 if errors else 0)
    if args.cmd == "build":
        build_candidate(repo_root, Path(args.candidate), args.accepted_at, args.source_commit)
    elif args.cmd == "validate-candidate":
        validate_candidate(
            repo_root,
            Path(args.candidate),
            args.accepted_at,
            args.source_commit,
            Path(args.acceptance),
        )
    elif args.cmd == "publish":
        publish(repo_root, Path(args.candidate), args.published_at, args.source_commit)


if __name__ == "__main__":
    main()
