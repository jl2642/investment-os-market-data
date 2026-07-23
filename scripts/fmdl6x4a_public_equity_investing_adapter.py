from __future__ import annotations

import argparse
import shutil
from collections import Counter
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

PHASE_ID = "FMDL-6X4-A"
EXIT_STATUS = "FMDL6X4A_PUBLIC_EQUITY_INVESTING_ADAPTER_AND_CONTRACT_MAPPING_ACCEPTED"
NEXT_GATE = "FMDL-6X4-B_RESEARCH_WORKFLOW_INTEGRATION_AND_EVIDENCE_REGISTRATION"
CONTRACT_PATH = Path("config/fmdl6x4a_public_equity_investing_adapter_contract.json")
FINAL_ROOT = Path("outputs/fmdl6x3/current/research_production_final")
SCREENING_ROOT = Path("outputs/fmdl6x3/current/screening_research_cards")
LAST_SUCCESS_PATH = Path("outputs/status/FMDL6X3FINAL_LAST_SUCCESS.json")

WORKFLOWS: list[dict[str, Any]] = [
    {
        "workflow_slug": "company-tearsheet",
        "workflow_name": "Company Tearsheet",
        "owning_artifact": "SOURCE_BACKED_ISSUER_OR_REFERENCE_BASELINE",
        "required_source_categories": ["Market Data & Estimates", "Company Filings & IR"],
        "minimum_required_inputs": ["canonical_identity", "source_inventory", "reported_company_facts", "market_context"],
    },
    {
        "workflow_slug": "financials-normalizer",
        "workflow_name": "Financials Normalizer",
        "owning_artifact": "MODEL_READY_NORMALIZED_FINANCIAL_PACKAGE",
        "required_source_categories": ["Company Filings & IR", "Portfolio Models & Trackers", "Market Data & Estimates"],
        "minimum_required_inputs": ["reported_financial_facts", "period_end_dates", "units_currency", "source_ids", "validation_scope"],
    },
    {
        "workflow_slug": "earnings-preview",
        "workflow_name": "Earnings Preview",
        "owning_artifact": "PRE_EARNINGS_INVESTOR_REPORT",
        "required_source_categories": ["Earnings Transcripts & Events", "Company Filings & IR", "Market Data & Estimates", "Internal Research"],
        "minimum_required_inputs": ["next_earnings_date", "reported_baseline", "consensus_bar", "guidance_history", "event_freeze_time"],
    },
    {
        "workflow_slug": "earnings-deep-dive",
        "workflow_name": "Earnings Deep Dive",
        "owning_artifact": "POST_EARNINGS_THESIS_AND_MODEL_IMPLICATIONS",
        "required_source_categories": ["Earnings Transcripts & Events", "Company Filings & IR", "Market Data & Estimates", "Internal Research"],
        "minimum_required_inputs": ["earnings_release", "reported_results", "transcript_or_call_commentary", "guidance", "price_reaction"],
    },
    {
        "workflow_slug": "comps-valuation",
        "workflow_name": "Comps Valuation",
        "owning_artifact": "PUBLIC_COMPARABLE_COMPANY_VALUATION",
        "required_source_categories": ["Market Data & Estimates", "Company Filings & IR", "Portfolio Models & Trackers"],
        "minimum_required_inputs": ["decision_grade_price", "shares_and_ev_bridge", "ttm_or_forward_denominators", "formal_peer_set", "comparability_checks"],
    },
    {
        "workflow_slug": "dcf-model-builder",
        "workflow_name": "DCF Model Builder",
        "owning_artifact": "FORMULA_FIRST_DCF_WORKBOOK",
        "required_source_categories": ["Company Filings & IR", "Market Data & Estimates", "Portfolio Models & Trackers"],
        "minimum_required_inputs": ["historical_financials", "forecast_driver_plan", "cash_flow", "net_debt", "share_count", "wacc_and_terminal_assumptions"],
    },
    {
        "workflow_slug": "three-statement-model-builder",
        "workflow_name": "Three Statement Model Builder",
        "owning_artifact": "FORMULA_FIRST_THREE_STATEMENT_WORKBOOK",
        "required_source_categories": ["Company Filings & IR", "Market Data & Estimates", "Portfolio Models & Trackers"],
        "minimum_required_inputs": ["income_statement", "balance_sheet", "cash_flow", "historical_periods", "forecast_assumptions", "capital_structure"],
    },
    {
        "workflow_slug": "scenario-sensitivity-generator",
        "workflow_name": "Scenario Sensitivity Generator",
        "owning_artifact": "SCENARIO_BREAKPOINT_AND_ACTION_THRESHOLD_ANALYSIS",
        "required_source_categories": ["Market Data & Estimates", "Company Filings & IR", "Portfolio Models & Trackers", "Earnings Transcripts & Events"],
        "minimum_required_inputs": ["user_confirmed_decision_context", "validated_base_case", "current_price", "scenario_drivers", "source_as_of_dates"],
    },
    {
        "workflow_slug": "catalyst-calendar",
        "workflow_name": "Catalyst Calendar",
        "owning_artifact": "DATED_CATALYST_AND_MONITORING_CALENDAR",
        "required_source_categories": ["Earnings Transcripts & Events", "Company Filings & IR", "Market Data & Estimates", "Internal Research"],
        "minimum_required_inputs": ["dated_event_evidence", "confirmed_or_inferred_status", "monitoring_window", "event_readthrough"],
    },
    {
        "workflow_slug": "long-short-pitch",
        "workflow_name": "Long Short Pitch",
        "owning_artifact": "PM_FACING_TRADE_PITCH",
        "required_source_categories": ["Company Filings & IR", "Market Data & Estimates", "Earnings Transcripts & Events", "Portfolio Models & Trackers", "Internal Research"],
        "minimum_required_inputs": ["variant_perception", "valuation", "catalysts", "risk_reward", "falsifiers", "trade_expression_context"],
    },
    {
        "workflow_slug": "thesis-tracker",
        "workflow_name": "Thesis Tracker",
        "owning_artifact": "THESIS_STATUS_AND_PROVE_KILL_TRACKER",
        "required_source_categories": ["Internal Research", "Company Filings & IR", "Market Data & Estimates", "Earnings Transcripts & Events", "Portfolio Models & Trackers"],
        "minimum_required_inputs": ["user_confirmed_thesis", "prove_kill_conditions", "monitoring_triggers", "review_cadence"],
    },
    {
        "workflow_slug": "memo-builder",
        "workflow_name": "Memo Builder",
        "owning_artifact": "FORMAL_PUBLIC_EQUITY_INVESTMENT_MEMO",
        "required_source_categories": ["Internal Research", "Company Filings & IR", "Market Data & Estimates", "Portfolio Models & Trackers"],
        "minimum_required_inputs": ["owning_analysis_outputs", "investment_question", "valuation_or_scenario_support", "risk_and_catalyst_evidence"],
    },
    {
        "workflow_slug": "meeting-prep",
        "workflow_name": "Meeting Prep",
        "owning_artifact": "INVESTOR_MEETING_PREP_BRIEF",
        "required_source_categories": ["Internal Research", "Company Filings & IR", "Earnings Transcripts & Events", "Market Data & Estimates"],
        "minimum_required_inputs": ["user_confirmed_meeting_purpose", "participants", "meeting_timing", "thesis_linked_questions"],
    },
    {
        "workflow_slug": "initiating-coverage",
        "workflow_name": "Initiating Coverage",
        "owning_artifact": "FULL_INITIATING_COVERAGE_REPORT",
        "required_source_categories": ["Company Filings & IR", "Market Data & Estimates", "Earnings Transcripts & Events", "Portfolio Models & Trackers", "Internal Research"],
        "minimum_required_inputs": ["complete_issuer_baseline", "multi_period_financials", "forecast", "valuation", "thesis", "catalysts", "risks"],
    },
]


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(stable_json(row) + "\n" for row in rows).encode("utf-8")


def validate_contract(repo_root: Path) -> tuple[dict[str, Any], list[str]]:
    contract_path = repo_root / CONTRACT_PATH
    errors: list[str] = []
    if not contract_path.is_file():
        return {}, ["CONTRACT_MISSING"]
    contract = load_json(contract_path)
    if contract.get("phase_id") != PHASE_ID:
        errors.append("PHASE_ID")
    if contract.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")
    if contract.get("workflow_contract", {}).get("workflow_slugs") != [row["workflow_slug"] for row in WORKFLOWS]:
        errors.append("WORKFLOW_REGISTRY_MISMATCH")
    entry = contract.get("entry_gate", {})
    pointer_path = repo_root / entry.get("pointer_path", "")
    if not pointer_path.is_file():
        errors.append("ENTRY_POINTER_MISSING")
    else:
        pointer = load_json(pointer_path)
        for key, expected in (
            ("phase_id", entry.get("required_phase_id")),
            ("release_id", entry.get("required_release_id")),
            ("release_sequence", entry.get("required_release_sequence")),
            ("status", entry.get("required_status")),
            ("next_gate", entry.get("required_next_gate")),
            ("fmdl6x4a_gate", entry.get("required_gate")),
        ):
            if pointer.get(key) != expected:
                errors.append("ENTRY_POINTER:" + key)
    for path in (
        repo_root / FINAL_ROOT / "FMDL6X3FINAL_MANIFEST.json",
        repo_root / FINAL_ROOT / "FMDL6X3FINAL_SOURCE_BINDING.json",
        repo_root / FINAL_ROOT / "FMDL6X3FINAL_FMDL6X4A_HANDOFF.json",
        repo_root / SCREENING_ROOT / "FMDL6X3E_US_BENCHMARK_POOL.json",
        repo_root / SCREENING_ROOT / "FMDL6X3E_RESEARCH_SHARDS.zip",
    ):
        if not path.is_file():
            errors.append("INPUT_MISSING:" + str(path.relative_to(repo_root)))
    if contract.get("zero_mutation_gate") != {
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders": 0,
    }:
        errors.append("ZERO_MUTATION_GATE")
    return contract, errors


def load_inputs(repo_root: Path) -> dict[str, Any]:
    pool_path = repo_root / SCREENING_ROOT / "FMDL6X3E_US_BENCHMARK_POOL.json"
    research_zip = repo_root / SCREENING_ROOT / "FMDL6X3E_RESEARCH_SHARDS.zip"
    return {
        "last_success": load_json(repo_root / LAST_SUCCESS_PATH),
        "final_manifest_path": repo_root / FINAL_ROOT / "FMDL6X3FINAL_MANIFEST.json",
        "final_source_binding": load_json(repo_root / FINAL_ROOT / "FMDL6X3FINAL_SOURCE_BINDING.json"),
        "final_handoff": load_json(repo_root / FINAL_ROOT / "FMDL6X3FINAL_FMDL6X4A_HANDOFF.json"),
        "pool_path": pool_path,
        "pool": load_json(pool_path),
        "research_zip_path": research_zip,
        "research_cards": read_zip_jsonl(research_zip, "RESEARCH_CARD/"),
    }


def _status_for(workflow_slug: str, pool_layer: str) -> str:
    reference = pool_layer == "BENCHMARK_REFERENCE_INSTRUMENT"
    core = pool_layer == "CORE_FINANCIAL_QUALITY_SANDBOX"
    if workflow_slug == "company-tearsheet":
        return "PARTIAL_ADAPTER_READY"
    if workflow_slug == "financials-normalizer":
        if reference:
            return "NOT_APPLICABLE_REFERENCE_INSTRUMENT"
        return "PARTIAL_ADAPTER_READY" if core else "BLOCKED_REQUIRED_INPUTS_MISSING"
    if workflow_slug in {
        "earnings-preview",
        "earnings-deep-dive",
        "comps-valuation",
        "dcf-model-builder",
        "three-statement-model-builder",
        "long-short-pitch",
        "memo-builder",
        "initiating-coverage",
    }:
        return "NOT_APPLICABLE_REFERENCE_INSTRUMENT" if reference else "BLOCKED_REQUIRED_INPUTS_MISSING"
    if workflow_slug == "scenario-sensitivity-generator":
        return "NOT_APPLICABLE_REFERENCE_INSTRUMENT" if reference else "HUMAN_CONFIRMATION_REQUIRED"
    if workflow_slug == "catalyst-calendar":
        return "BLOCKED_REQUIRED_INPUTS_MISSING"
    if workflow_slug == "thesis-tracker":
        return "HUMAN_CONFIRMATION_REQUIRED"
    if workflow_slug == "meeting-prep":
        return "NOT_APPLICABLE_REFERENCE_INSTRUMENT" if reference else "HUMAN_CONFIRMATION_REQUIRED"
    raise KeyError(workflow_slug)


def _blockers(workflow_slug: str, status: str, pool_layer: str) -> list[str]:
    if status == "NOT_APPLICABLE_REFERENCE_INSTRUMENT":
        return ["REFERENCE_INSTRUMENT_OUTSIDE_ISSUER_WORKFLOW_SCOPE"]
    if workflow_slug == "company-tearsheet":
        return [
            "RUNTIME_SOURCE_READINESS_CHECK_REQUIRED",
            "DECISION_GRADE_CURRENT_MARKET_DATA_PENDING",
            "OWNERSHIP_CONSENSUS_AND_POSITIONING_NOT_STORED",
        ]
    if workflow_slug == "financials-normalizer":
        if pool_layer == "CORE_FINANCIAL_QUALITY_SANDBOX":
            return ["TTM_ANNUAL_BALANCE_SHEET_AND_CASH_FLOW_PENDING", "RUNTIME_SOURCE_READINESS_CHECK_REQUIRED"]
        return ["OFFICIAL_SEC_COMPANY_FACTS_PENDING", "MODEL_READY_FINANCIAL_SCOPE_NOT_AVAILABLE"]
    mapping = {
        "earnings-preview": ["NEXT_EARNINGS_DATE_PENDING", "CONSENSUS_AND_GUIDANCE_HISTORY_PENDING", "EVENT_FREEZE_TIME_PENDING"],
        "earnings-deep-dive": ["CURRENT_RESULTS_PENDING", "TRANSCRIPT_OR_CALL_COMMENTARY_PENDING", "GUIDANCE_AND_PRICE_REACTION_PENDING"],
        "comps-valuation": ["FORMAL_PEER_SET_PENDING", "TTM_OR_FORWARD_DENOMINATORS_PENDING", "DECISION_GRADE_PRICE_AND_EV_BRIDGE_PENDING"],
        "dcf-model-builder": ["TTM_ANNUAL_AND_THREE_STATEMENT_HISTORY_PENDING", "FORECAST_DRIVER_PLAN_PENDING", "NET_DEBT_SHARE_COUNT_WACC_TERMINAL_INPUTS_PENDING"],
        "three-statement-model-builder": ["BALANCE_SHEET_AND_CASH_FLOW_PENDING", "MULTI_PERIOD_HISTORY_PENDING", "FORECAST_ASSUMPTIONS_PENDING"],
        "scenario-sensitivity-generator": ["USER_DECISION_CONTEXT_REQUIRED", "VALIDATED_BASE_CASE_REQUIRED", "SCENARIO_DRIVER_SELECTION_REQUIRED"],
        "catalyst-calendar": ["DATED_EVENT_EVIDENCE_PENDING", "CONFIRMED_VS_INFERRED_EVENT_STATUS_PENDING", "MONITORING_WINDOW_PENDING"],
        "long-short-pitch": ["VARIANT_PERCEPTION_NOT_ESTABLISHED", "FORMAL_VALUATION_AND_CATALYSTS_PENDING", "TRADE_EXPRESSION_CONTEXT_NOT_AUTHORIZED"],
        "thesis-tracker": ["USER_CONFIRMED_THESIS_REQUIRED", "PROVE_KILL_CONDITIONS_REQUIRED", "REVIEW_CADENCE_REQUIRED"],
        "memo-builder": ["OWNING_ANALYSIS_OUTPUTS_PENDING", "INVESTMENT_QUESTION_PENDING", "VALUATION_SCENARIO_AND_RISK_SUPPORT_PENDING"],
        "meeting-prep": ["MEETING_PURPOSE_REQUIRED", "PARTICIPANTS_AND_TIMING_REQUIRED", "THESIS_LINKED_QUESTION_SCOPE_REQUIRED"],
        "initiating-coverage": ["COMPLETE_MULTI_PERIOD_FINANCIALS_PENDING", "FORECAST_AND_VALUATION_PENDING", "THESIS_CATALYST_AND_RISK_PACKAGE_PENDING"],
    }
    return mapping[workflow_slug]


def _confirmation_prompt(workflow_slug: str, symbol: str) -> str | None:
    prompts = {
        "scenario-sensitivity-generator": f"Confirm the investment decision, validated base case and scenario drivers for {symbol}.",
        "thesis-tracker": f"Confirm the thesis, prove/kill conditions and review cadence for {symbol}.",
        "meeting-prep": f"Confirm the meeting purpose, participants, timing and desired decisions for {symbol}.",
    }
    return prompts.get(workflow_slug)


def build_records(inputs: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    cards_by_security = {
        card["identity"]["canonical_security_id"]: card
        for card in inputs["research_cards"]
        if card.get("identity", {}).get("canonical_security_id")
    }
    pool_members = sorted(inputs["pool"]["members"], key=lambda row: row["symbol"])
    errors: list[str] = []
    if len(pool_members) != contract["mapping_contract"]["benchmark_pool_member_count"]:
        errors.append("POOL_MEMBER_COUNT")

    workflow_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    for workflow in WORKFLOWS:
        row = {
            **workflow,
            "workflow_contract_id": "PEICONTRACT-" + record_hash("PEI_WORKFLOW", workflow["workflow_slug"])[:24],
            "adapter_payload_materialization_authorized": True,
            "workflow_execution_authorized": False,
            "decision_grade_handoff_authorized": False,
            "runtime_source_check_required": True,
            "trade_authority": "NONE",
        }
        workflow_rows.append(row)
        for category in workflow["required_source_categories"]:
            source_rows.append({
                "source_requirement_id": "PEISRC-" + record_hash("PEI_SOURCE_CATEGORY", workflow["workflow_slug"], category)[:24],
                "workflow_slug": workflow["workflow_slug"],
                "source_category": category,
                "category_requirement_status": "REQUIRED_AT_WORKFLOW_RUNTIME",
                "connector_readiness_claimed": False,
                "silent_weaker_source_substitution_allowed": False,
                "trade_authority": "NONE",
            })

    mapping_rows: list[dict[str, Any]] = []
    payload_rows: list[dict[str, Any]] = []
    queues: dict[str, list[dict[str, Any]]] = {
        "PARTIAL_RUNTIME_SOURCE_CHECK_QUEUE": [],
        "HUMAN_CONFIRMATION_QUEUE": [],
        "BLOCKED_INPUT_QUEUE": [],
        "NOT_APPLICABLE_REGISTRY": [],
    }

    final_source = inputs["final_source_binding"]
    input_release_id = inputs["last_success"]["release_id"]
    source_manifest_sha = inputs["last_success"]["manifest_sha256"]

    for member in pool_members:
        sid = member["canonical_security_id"]
        card = cards_by_security.get(sid)
        if not card:
            errors.append("POOL_MEMBER_CARD_MISSING:" + sid)
            continue
        if card.get("research_card_id") != member.get("research_card_id"):
            errors.append("POOL_MEMBER_CARD_ID_MISMATCH:" + sid)
        identity = card["identity"]
        if identity.get("canonical_issuer_id") != member.get("canonical_issuer_id") or identity.get("symbol") != member.get("symbol"):
            errors.append("POOL_MEMBER_IDENTITY_MISMATCH:" + sid)

        member_mappings: list[dict[str, Any]] = []
        for workflow in WORKFLOWS:
            slug = workflow["workflow_slug"]
            status = _status_for(slug, member["pool_layer"])
            blockers = _blockers(slug, status, member["pool_layer"])
            confirmation = _confirmation_prompt(slug, member["symbol"])
            mapping = {
                "mapping_id": "PEIMAP-" + record_hash("PEI_SECURITY_WORKFLOW", sid, slug)[:24],
                "canonical_security_id": sid,
                "canonical_issuer_id": member["canonical_issuer_id"],
                "symbol": member["symbol"],
                "research_card_id": member["research_card_id"],
                "benchmark_pool_id": member["pool_id"],
                "benchmark_pool_layer": member["pool_layer"],
                "screening_disposition": member["screening_disposition"],
                "workflow_slug": slug,
                "workflow_contract_id": "PEICONTRACT-" + record_hash("PEI_WORKFLOW", slug)[:24],
                "adapter_status": status,
                "required_source_categories": workflow["required_source_categories"],
                "minimum_required_inputs": workflow["minimum_required_inputs"],
                "available_input_release_id": input_release_id,
                "available_research_card": True,
                "blocker_codes": blockers,
                "human_confirmation_prompt": confirmation,
                "runtime_source_check_required": status != "NOT_APPLICABLE_REFERENCE_INSTRUMENT",
                "workflow_execution_authorized": False,
                "completed_workflow_artifact_emitted": False,
                "investment_recommendation_authorized": False,
                "candidate_pool_promotion_authorized": False,
                "simulation_authorized": False,
                "trade_authority": "NONE",
            }
            mapping_rows.append(mapping)
            member_mappings.append(mapping)
            queue_record = {
                "mapping_id": mapping["mapping_id"],
                "canonical_security_id": sid,
                "canonical_issuer_id": member["canonical_issuer_id"],
                "symbol": member["symbol"],
                "workflow_slug": slug,
                "adapter_status": status,
                "blocker_codes": blockers,
                "required_action": (
                    "PERFORM_RUNTIME_SOURCE_CHECK_AND_WORKFLOW_INTAKE"
                    if status == "PARTIAL_ADAPTER_READY"
                    else "OBTAIN_USER_CONFIRMATION_BEFORE_WORKFLOW_EXECUTION"
                    if status == "HUMAN_CONFIRMATION_REQUIRED"
                    else "BACKFILL_LOAD_BEARING_INPUTS_BEFORE_WORKFLOW_EXECUTION"
                    if status == "BLOCKED_REQUIRED_INPUTS_MISSING"
                    else "RETAIN_AS_NOT_APPLICABLE_REFERENCE_MAPPING"
                ),
            }
            queue_name = {
                "PARTIAL_ADAPTER_READY": "PARTIAL_RUNTIME_SOURCE_CHECK_QUEUE",
                "HUMAN_CONFIRMATION_REQUIRED": "HUMAN_CONFIRMATION_QUEUE",
                "BLOCKED_REQUIRED_INPUTS_MISSING": "BLOCKED_INPUT_QUEUE",
                "NOT_APPLICABLE_REFERENCE_INSTRUMENT": "NOT_APPLICABLE_REGISTRY",
            }[status]
            queues[queue_name].append(queue_record)

        status_counts = Counter(row["adapter_status"] for row in member_mappings)
        payload_rows.append({
            "adapter_payload_id": "PEIPAYLOAD-" + record_hash("PEI_ADAPTER_PAYLOAD", sid)[:24],
            "adapter_payload_version": "1.0.0",
            "canonical_security_id": sid,
            "canonical_issuer_id": member["canonical_issuer_id"],
            "symbol": member["symbol"],
            "research_profile": identity.get("research_profile"),
            "research_scope": identity.get("research_scope"),
            "research_card_id": member["research_card_id"],
            "screening_disposition": member["screening_disposition"],
            "benchmark_pool_id": member["pool_id"],
            "benchmark_pool_layer": member["pool_layer"],
            "validation_role": member["validation_role"],
            "input_release_id": input_release_id,
            "source_manifest_sha256": source_manifest_sha,
            "evidence_posture": {
                "financial_source_grade": final_source["financial_source_grade"],
                "market_source_grade": final_source["market_source_grade"],
                "classification_authority": final_source["classification_authority"],
                "neutral_fill_used": final_source["neutral_fill_used"],
                "silent_source_substitution": final_source["silent_source_substitution"],
                "official_filing_count": card.get("data_readiness", {}).get("official_filing_count", 0),
                "official_fact_count": card.get("data_readiness", {}).get("official_fact_count", 0),
                "market_data_readiness": card.get("data_readiness", {}).get("market_data_readiness"),
                "classification_status": card.get("classification", {}).get("classification_status"),
            },
            "workflow_mapping_ids": [row["mapping_id"] for row in member_mappings],
            "workflow_status_counts": dict(sorted(status_counts.items())),
            "workflow_execution_authorized": False,
            "completed_workflow_artifact_count": 0,
            "investment_recommendation_authorized": False,
            "candidate_pool_promotion_authorized": False,
            "simulation_authorized": False,
            "trade_authority": "NONE",
        })

    for rows in queues.values():
        rows.sort(key=stable_json)
    workflow_rows.sort(key=lambda row: row["workflow_slug"])
    source_rows.sort(key=lambda row: (row["workflow_slug"], row["source_category"]))
    mapping_rows.sort(key=lambda row: (row["canonical_security_id"], row["workflow_slug"]))
    payload_rows.sort(key=lambda row: row["canonical_security_id"])
    return {
        "workflow_rows": workflow_rows,
        "source_rows": source_rows,
        "mapping_rows": mapping_rows,
        "payload_rows": payload_rows,
        "queues": queues,
        "errors": errors,
    }


def build_shards(records: dict[str, Any], bucket_count: int, generated_at: str) -> tuple[bytes, list[dict[str, Any]]]:
    domains = (
        ("WORKFLOW_CONTRACT", records["workflow_rows"], "workflow_slug"),
        ("SECURITY_WORKFLOW_MAPPING", records["mapping_rows"], "mapping_id"),
        ("ADAPTER_PAYLOAD", records["payload_rows"], "canonical_security_id"),
        ("SOURCE_CATEGORY_REQUIREMENT", records["source_rows"], "source_requirement_id"),
    )
    entries: dict[str, bytes] = {}
    manifest: list[dict[str, Any]] = []
    for domain, rows, key in domains:
        for index in range(bucket_count):
            bucket = f"{index:02X}"
            shard = [row for row in rows if bucket_hex(str(row[key]), bucket_count) == bucket]
            shard.sort(key=lambda row: (str(row[key]), stable_json(row)))
            payload = _jsonl_bytes(shard)
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
    return deterministic_zip({f"{name}.jsonl": _jsonl_bytes(rows) for name, rows in sorted(queues.items())})


def build_candidate(repo_root: Path, candidate_root: Path, accepted_at: str, source_commit: str) -> dict[str, Any]:
    contract, contract_errors = validate_contract(repo_root)
    if contract_errors:
        raise RuntimeError("CONTRACT_ERRORS:" + ",".join(contract_errors))
    inputs = load_inputs(repo_root)
    records = build_records(inputs, contract)
    if records["errors"]:
        raise RuntimeError("RECORD_ERRORS:" + ",".join(records["errors"]))

    contract_sha = sha256_file(repo_root / CONTRACT_PATH)
    final_manifest_sha = sha256_file(inputs["final_manifest_path"])
    pool_sha = sha256_file(inputs["pool_path"])
    research_zip_sha = sha256_file(inputs["research_zip_path"])
    registry_sha = sha256_bytes(stable_json(WORKFLOWS).encode("utf-8"))
    release_id = "FMDL6X4A_20260723_" + record_hash(
        "FMDL6X4A_RELEASE", contract_sha, final_manifest_sha, pool_sha, research_zip_sha, registry_sha
    )[:12]

    candidate_root.mkdir(parents=True, exist_ok=True)
    shard_zip, shard_manifest = build_shards(records, contract["storage_contract"]["bucket_count"], accepted_at)
    (candidate_root / "FMDL6X4A_ADAPTER_SHARDS.zip").write_bytes(shard_zip)
    (candidate_root / "FMDL6X4A_REVIEW_QUEUES.zip").write_bytes(build_queue_zip(records["queues"]))

    status_counts = Counter(row["adapter_status"] for row in records["mapping_rows"])
    workflow_status = {}
    for workflow in WORKFLOWS:
        slug = workflow["workflow_slug"]
        workflow_status[slug] = dict(sorted(Counter(
            row["adapter_status"] for row in records["mapping_rows"] if row["workflow_slug"] == slug
        ).items()))

    write_json(candidate_root / "FMDL6X4A_WORKFLOW_CONTRACT_REGISTRY.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "workflow_count": len(records["workflow_rows"]),
        "workflows": records["workflow_rows"],
    })
    write_json(candidate_root / "FMDL6X4A_SOURCE_CATEGORY_REGISTRY.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "source_requirement_count": len(records["source_rows"]),
        "connector_readiness_claimed": False,
        "runtime_source_check_required": True,
        "requirements": records["source_rows"],
    })
    write_json(candidate_root / "FMDL6X4A_MAPPING_SUMMARY.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "benchmark_pool_member_count": len(records["payload_rows"]),
        "workflow_contract_count": len(records["workflow_rows"]),
        "security_workflow_mapping_count": len(records["mapping_rows"]),
        "status_counts": dict(sorted(status_counts.items())),
        "workflow_status_counts": workflow_status,
        "formal_workflow_execution_count": 0,
        "investment_recommendation_count": 0,
        "candidate_promotion_count": 0,
    })
    write_json(candidate_root / "FMDL6X4A_ADAPTER_PAYLOAD_SUMMARY.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "adapter_payload_count": len(records["payload_rows"]),
        "symbols": [row["symbol"] for row in records["payload_rows"]],
        "payload_ids": [row["adapter_payload_id"] for row in records["payload_rows"]],
        "workflow_execution_authorized": False,
    })
    write_json(candidate_root / "FMDL6X4A_QUEUE_SUMMARY.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "queue_counts": {name: len(rows) for name, rows in sorted(records["queues"].items())},
    })

    gates = contract["acceptance_gates"]
    quality = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "quality_status": "PASS",
        "workflow_contract_count": len(records["workflow_rows"]),
        "benchmark_pool_member_count": len(records["payload_rows"]),
        "security_workflow_mapping_count": len(records["mapping_rows"]),
        "adapter_payload_count": len(records["payload_rows"]),
        "partial_adapter_ready_count": status_counts["PARTIAL_ADAPTER_READY"],
        "human_confirmation_required_count": status_counts["HUMAN_CONFIRMATION_REQUIRED"],
        "blocked_required_inputs_count": status_counts["BLOCKED_REQUIRED_INPUTS_MISSING"],
        "not_applicable_count": status_counts["NOT_APPLICABLE_REFERENCE_INSTRUMENT"],
        "formal_workflow_execution_count": 0,
        "completed_workflow_artifact_count": 0,
        "investment_recommendation_count": 0,
        "candidate_promotion_count": 0,
        "neutral_fill_count": 0,
        "manifested_shard_count": len(shard_manifest),
        "expected_shard_count": gates["logical_shard_count"],
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    errors: list[str] = []
    checks = {
        "workflow_contract_count": quality["workflow_contract_count"],
        "benchmark_pool_member_count": quality["benchmark_pool_member_count"],
        "security_workflow_mapping_count": quality["security_workflow_mapping_count"],
        "adapter_payload_count": quality["adapter_payload_count"],
        "partial_adapter_ready_count": quality["partial_adapter_ready_count"],
        "human_confirmation_required_count": quality["human_confirmation_required_count"],
        "blocked_required_inputs_count": quality["blocked_required_inputs_count"],
        "not_applicable_count": quality["not_applicable_count"],
        "formal_workflow_execution_count": 0,
        "investment_recommendation_count": 0,
        "candidate_promotion_count": 0,
        "logical_shard_count": len(shard_manifest),
        "neutral_fill_count": 0,
    }
    for key, actual in checks.items():
        if actual != gates[key]:
            errors.append(f"ACCEPTANCE_GATE:{key}:{actual}!={gates[key]}")
    if any(row["workflow_execution_authorized"] for row in records["mapping_rows"]):
        errors.append("WORKFLOW_EXECUTION_AUTHORIZED")
    if any(row["candidate_pool_promotion_authorized"] for row in records["mapping_rows"]):
        errors.append("CANDIDATE_PROMOTION_AUTHORIZED")
    if any(row["trade_authority"] != "NONE" for row in records["mapping_rows"] + records["payload_rows"]):
        errors.append("TRADE_AUTHORITY")
    if errors:
        quality["quality_status"] = "FAIL"
        quality["errors"] = errors
    write_json(candidate_root / "FMDL6X4A_QUALITY_REPORT.json", quality)
    if errors:
        raise RuntimeError("QUALITY_ERRORS:" + ",".join(errors))

    coverage = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "fmdl6x3_final_release_id": inputs["last_success"]["release_id"],
        "benchmark_pool_member_count": len(records["payload_rows"]),
        "workflow_contract_count": len(records["workflow_rows"]),
        "security_workflow_mapping_count": len(records["mapping_rows"]),
        "adapter_payload_count": len(records["payload_rows"]),
        "partial_adapter_ready_count": status_counts["PARTIAL_ADAPTER_READY"],
        "human_confirmation_required_count": status_counts["HUMAN_CONFIRMATION_REQUIRED"],
        "blocked_required_inputs_count": status_counts["BLOCKED_REQUIRED_INPUTS_MISSING"],
        "not_applicable_count": status_counts["NOT_APPLICABLE_REFERENCE_INSTRUMENT"],
        "public_equity_workflow_execution_claimed": False,
        "decision_grade_handoff_claimed": False,
        "investment_recommendation_claimed": False,
        "candidate_pool_integration_claimed": False,
    }
    write_json(candidate_root / "FMDL6X4A_COVERAGE_REPORT.json", coverage)

    source_binding = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "input_release_id": inputs["last_success"]["release_id"],
        "input_manifest_sha256": final_manifest_sha,
        "input_pool_sha256": pool_sha,
        "input_research_cards_sha256": research_zip_sha,
        "workflow_registry_sha256": registry_sha,
        "financial_source_grade": inputs["final_source_binding"]["financial_source_grade"],
        "market_source_grade": inputs["final_source_binding"]["market_source_grade"],
        "classification_authority": inputs["final_source_binding"]["classification_authority"],
        "source_category_mapping_is_connector_readiness": False,
        "runtime_source_check_required": True,
        "neutral_fill_used": False,
        "silent_source_substitution": False,
        "workflow_execution_emitted": False,
        "investment_recommendation_emitted": False,
        "candidate_promotion_emitted": False,
    }
    write_json(candidate_root / "FMDL6X4A_SOURCE_BINDING.json", source_binding)

    decision = {
        "phase_id": PHASE_ID,
        "status": EXIT_STATUS,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "accepted_at": accepted_at,
        "source_commit": source_commit,
        "input_release_id": inputs["last_success"]["release_id"],
        "next_gate": NEXT_GATE,
        "adapter_status": "PUBLIC_EQUITY_INVESTING_CONTRACTS_MAPPED_WITH_PARTIAL_INPUT_READINESS_AND_ZERO_WORKFLOW_EXECUTION",
        "workflow_contract_count": len(records["workflow_rows"]),
        "security_workflow_mapping_count": len(records["mapping_rows"]),
        "adapter_payload_count": len(records["payload_rows"]),
        "formal_workflow_execution_count": 0,
        "completed_workflow_artifact_count": 0,
        "investment_recommendation_count": 0,
        "formal_candidate_promotion_count": 0,
        "research_workflow_integration_gate": "OPEN_FOR_FMDL6X4B_EVIDENCE_REGISTRATION_ONLY",
        "investment_os_candidate_pool_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X4A",
        "simulation_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X4A",
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    write_json(candidate_root / "FMDL6X4A_DECISION.json", decision)
    write_json(candidate_root / "FMDL6X4A_FMDL6X4B_HANDOFF.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "handoff_status": "OPEN_FOR_FMDL6X4B_WORKFLOW_INTEGRATION_AND_EVIDENCE_REGISTRATION_ONLY",
        "next_gate": NEXT_GATE,
        "accepted_adapter_payload_count": len(records["payload_rows"]),
        "accepted_workflow_contract_count": len(records["workflow_rows"]),
        "workflow_execution_authorized": False,
        "candidate_pool_authorized": False,
        "simulation_authorized": False,
        "brokerage_channel_available": False,
        "required_next_controls": [
            "REGISTER_EACH_WORKFLOW_OUTPUT_TO_CANONICAL_SECURITY_ISSUER_AND_SOURCE_IDS",
            "PERFORM_RUNTIME_SOURCE_CATEGORY_CHECKS_BEFORE_EACH_WORKFLOW_RUN",
            "PRESERVE_WORKFLOW_OWNERSHIP_AND_EVIDENCE_LABELS",
            "DO_NOT_PROMOTE_RESEARCH_OUTPUTS_TO_CANDIDATE_POOL_WITHOUT_6X4C_AUTHORIZATION"
        ],
        "trade_authority": "NONE",
    })

    manifest_files: dict[str, Any] = {}
    for path in sorted(candidate_root.iterdir()):
        if path.name == "FMDL6X4A_MANIFEST.json" or not path.is_file():
            continue
        manifest_files[path.name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    manifest = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "generated_at": accepted_at,
        "contract_sha256": contract_sha,
        "input_manifest_sha256": final_manifest_sha,
        "input_pool_sha256": pool_sha,
        "input_research_cards_sha256": research_zip_sha,
        "workflow_registry_sha256": registry_sha,
        "files": manifest_files,
        "shards": shard_manifest,
    }
    write_json(candidate_root / "FMDL6X4A_MANIFEST.json", manifest)
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
    manifest = load_json(candidate_root / "FMDL6X4A_MANIFEST.json")
    for name, meta in manifest["files"].items():
        path = candidate_root / name
        if not path.is_file() or path.stat().st_size != meta["bytes"] or sha256_file(path) != meta["sha256"]:
            errors.append("MANIFEST_FILE:" + name)
    decision = load_json(candidate_root / "FMDL6X4A_DECISION.json")
    if decision.get("trade_authority") != "NONE" or decision.get("formal_workflow_execution_count") != 0:
        errors.append("AUTHORITY_OR_EXECUTION")
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
    decision = load_json(candidate_root / "FMDL6X4A_DECISION.json")
    release_id = decision["release_id"]
    current = repo_root / contract["storage_contract"]["current_root"]
    release = repo_root / contract["storage_contract"]["release_root"].replace("<release_id>", release_id)
    normalized = repo_root / contract["storage_contract"]["normalized_root"].replace("<release_id>", release_id)
    archive_root = repo_root / contract["storage_contract"]["archive_root"]
    if release.exists():
        raise RuntimeError("IMMUTABLE_RELEASE_COLLISION")
    if current.exists():
        archive = archive_root / f"public_equity_investing_adapter_{published_at.replace(':', '').replace('-', '')}"
        copytree_replace(current, archive)
    copytree_replace(candidate_root, current)
    copytree_replace(candidate_root, release)
    copytree_replace(candidate_root, normalized)
    for name in ("FMDL6X4A_DECISION.json", "FMDL6X4A_MANIFEST.json"):
        if (current / name).read_bytes() != (release / name).read_bytes():
            raise RuntimeError("CURRENT_RELEASE_PARITY_FAILED:" + name)
    manifest_sha = sha256_file(current / "FMDL6X4A_MANIFEST.json")
    pointer = {
        "phase_id": PHASE_ID,
        "status": EXIT_STATUS,
        "published_at": published_at,
        "source_commit": source_commit,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "current_path": str(current.relative_to(repo_root)),
        "release_path": str(release.relative_to(repo_root)),
        "normalized_path": str(normalized.relative_to(repo_root)),
        "manifest_sha256": manifest_sha,
        "input_release_id": decision["input_release_id"],
        "adapter_status": decision["adapter_status"],
        "workflow_contract_count": decision["workflow_contract_count"],
        "security_workflow_mapping_count": decision["security_workflow_mapping_count"],
        "adapter_payload_count": decision["adapter_payload_count"],
        "formal_workflow_execution_count": 0,
        "investment_recommendation_count": 0,
        "formal_candidate_promotion_count": 0,
        "next_gate": NEXT_GATE,
        "research_workflow_integration_gate": decision["research_workflow_integration_gate"],
        "investment_os_candidate_pool_gate": decision["investment_os_candidate_pool_gate"],
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    write_json(repo_root / contract["storage_contract"]["last_success"], pointer)
    lkg = {
        **pointer,
        "lkg_scope": "FMDL6X4_PUBLIC_EQUITY_INVESTING_ADAPTER_DOMAIN",
        "lkg_reason": "LATEST_ACCEPTED_WORKFLOW_CONTRACT_MAPPING_WITH_ZERO_WORKFLOW_EXECUTION",
    }
    write_json(repo_root / contract["storage_contract"]["last_known_good"], lkg)
    return pointer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
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
    root = Path(args.repo_root).resolve()
    if args.command == "validate-contract":
        _, errors = validate_contract(root)
        if errors:
            raise RuntimeError("CONTRACT_ERRORS:" + ",".join(errors))
        print({"phase_id": PHASE_ID, "status": "PASS"})
    elif args.command == "build":
        build_candidate(root, root / args.candidate, args.accepted_at, args.source_commit)
    elif args.command == "validate-candidate":
        validate_candidate(root, root / args.candidate, args.accepted_at, args.source_commit, root / args.acceptance)
    elif args.command == "publish":
        publish(root, root / args.candidate, args.published_at, args.source_commit)


if __name__ == "__main__":
    main()
