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

PHASE_ID = "FMDL-6X3-E"
EXIT_STATUS = "FMDL6X3E_SCREENING_FUNNEL_RESEARCH_CARDS_AND_US_BENCHMARK_POOL_ACCEPTED"
NEXT_GATE = "FMDL-6X3-FINAL_RESEARCH_PRODUCTION_RECONCILIATION_AND_ACCEPTANCE"
CONTRACT_PATH = Path("config/fmdl6x3e_screening_research_cards_contract.json")
READINESS_ROOT = Path("outputs/fmdl6x3/current/research_universe_readiness")
FINANCIAL_ROOT = Path("outputs/fmdl6x3/current/financial_normalization")
FACTOR_ROOT = Path("outputs/fmdl6x3/current/factor_engine")
FRAMEWORK_ROOT = Path("outputs/fmdl6x3/current/sector_peer_benchmark")


def validate_contract(repo_root: Path) -> tuple[list[str], list[str]]:
    checks: list[str] = []
    errors: list[str] = []
    path = repo_root / CONTRACT_PATH
    if not path.is_file():
        return checks, ["CONTRACT_MISSING"]
    contract = load_json(path)
    if contract.get("phase_id") != PHASE_ID:
        errors.append("PHASE_ID")
    if contract.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")
    if contract.get("required_exit_status") != EXIT_STATUS:
        errors.append("EXIT_STATUS")
    if contract.get("next_gate") != NEXT_GATE:
        errors.append("NEXT_GATE")
    if contract.get("benchmark_pool_contract", {}).get("pool_is_not_candidate_pool") is not True:
        errors.append("POOL_CANDIDATE_SEPARATION")
    if contract.get("screening_contract", {}).get("formal_candidate_promotion_allowed") is not False:
        errors.append("CANDIDATE_PROMOTION_GATE")
    expected_files = (
        READINESS_ROOT / "FMDL6X3A_READINESS_SHARDS.zip",
        READINESS_ROOT / "FMDL6X3A_MANIFEST.json",
        FINANCIAL_ROOT / "FMDL6X3B_FINANCIAL_SHARDS.zip",
        FINANCIAL_ROOT / "FMDL6X3B_MANIFEST.json",
        FACTOR_ROOT / "FMDL6X3C_FACTOR_SHARDS.zip",
        FACTOR_ROOT / "FMDL6X3C_MANIFEST.json",
        FRAMEWORK_ROOT / "FMDL6X3D_FRAMEWORK_SHARDS.zip",
        FRAMEWORK_ROOT / "FMDL6X3D_MANIFEST.json",
        FRAMEWORK_ROOT / "FMDL6X3D_BENCHMARK_REGISTRY.json",
    )
    for rel in expected_files:
        if not (repo_root / rel).is_file():
            errors.append("INPUT_MISSING:" + str(rel))
    checks.extend([
        "CONTRACT_SHAPE",
        "UPSTREAM_RELEASES",
        "POOL_CANDIDATE_SEPARATION",
        "ZERO_MUTATION_GATE",
    ])
    if any(value != 0 for value in contract.get("zero_mutation_gate", {}).values()):
        errors.append("ZERO_MUTATION_GATE")
    return checks, errors


def load_inputs(repo_root: Path) -> dict[str, Any]:
    readiness_zip = repo_root / READINESS_ROOT / "FMDL6X3A_READINESS_SHARDS.zip"
    financial_zip = repo_root / FINANCIAL_ROOT / "FMDL6X3B_FINANCIAL_SHARDS.zip"
    factor_zip = repo_root / FACTOR_ROOT / "FMDL6X3C_FACTOR_SHARDS.zip"
    framework_zip = repo_root / FRAMEWORK_ROOT / "FMDL6X3D_FRAMEWORK_SHARDS.zip"
    return {
        "security_readiness": read_zip_jsonl(readiness_zip, "SECURITY_READINESS/"),
        "canonical_statements": read_zip_jsonl(financial_zip, "CANONICAL_STATEMENT/"),
        "derived_metrics": read_zip_jsonl(financial_zip, "DERIVED_METRIC/"),
        "normalization_issues": read_zip_jsonl(financial_zip, "NORMALIZATION_ISSUE/"),
        "factor_status": read_zip_jsonl(factor_zip, "SECURITY_FACTOR_STATUS/"),
        "quality_factors": read_zip_jsonl(factor_zip, "QUALITY_FACTOR/"),
        "market_factors": read_zip_jsonl(factor_zip, "MARKET_FACTOR/"),
        "risk_factors": read_zip_jsonl(factor_zip, "RISK_FACTOR/"),
        "classification": read_zip_jsonl(framework_zip, "SECURITY_CLASSIFICATION_STATUS/"),
        "peer_membership": read_zip_jsonl(framework_zip, "PEER_GROUP_MEMBERSHIP/"),
        "benchmark_assignment": read_zip_jsonl(framework_zip, "BENCHMARK_ASSIGNMENT/"),
        "benchmark_relative": read_zip_jsonl(framework_zip, "BENCHMARK_RELATIVE_FACTOR/"),
        "benchmark_registry": load_json(repo_root / FRAMEWORK_ROOT / "FMDL6X3D_BENCHMARK_REGISTRY.json"),
        "manifests": {
            "readiness": repo_root / READINESS_ROOT / "FMDL6X3A_MANIFEST.json",
            "financial": repo_root / FINANCIAL_ROOT / "FMDL6X3B_MANIFEST.json",
            "factor": repo_root / FACTOR_ROOT / "FMDL6X3C_MANIFEST.json",
            "framework": repo_root / FRAMEWORK_ROOT / "FMDL6X3D_MANIFEST.json",
        },
    }


def group_rows(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    for values in grouped.values():
        values.sort(key=stable_json)
    return grouped


def factor_snapshot(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in sorted(rows, key=lambda item: item["factor_name"]):
        out[row["factor_name"]] = {
            "value": row.get("factor_value", row.get("relative_factor_value")),
            "unit": row.get("unit"),
            "data_grade": row.get("data_grade"),
            "usage": row.get("factor_usage"),
            "as_of_date": row.get("as_of_date") or row.get("period_end"),
        }
    return out


def screening_disposition(
    readiness: dict[str, Any],
    has_quality: bool,
    has_market: bool,
    has_risk: bool,
    has_relative: bool,
    classification: dict[str, Any],
    contract: dict[str, Any],
) -> str:
    symbol = readiness["symbol"]
    pool = contract["benchmark_pool_contract"]
    if symbol in pool["core_quality_sandbox_symbols"]:
        if has_quality and has_market and has_risk and has_relative and classification.get("classification_status") == "OFFICIAL_SEC_SIC_LINKED_INTERNAL_CROSSWALK":
            return "CORE_RESEARCH_SANDBOX"
        raise RuntimeError("CORE_POOL_GATE_MISSING:" + symbol)
    if symbol in pool["filing_watch_symbols"]:
        if readiness.get("official_filing_count", 0) > 0 and classification.get("classification_status") == "OFFICIAL_SEC_SIC_LINKED_INTERNAL_CROSSWALK":
            return "OFFICIAL_FILING_WATCH"
        raise RuntimeError("FILING_WATCH_GATE_MISSING:" + symbol)
    if symbol in pool["benchmark_reference_symbols"]:
        if has_market and has_risk:
            return "BENCHMARK_REFERENCE"
        raise RuntimeError("BENCHMARK_REFERENCE_GATE_MISSING:" + symbol)
    scope = readiness["research_scope"]
    if scope == "EXCLUDED":
        return "EXCLUDED"
    if scope == "REVIEW_REQUIRED":
        return "INSTRUMENT_REVIEW_REQUIRED"
    if scope == "REFERENCE_ONLY":
        return "REFERENCE_ONLY"
    if has_market and has_risk:
        return "MARKET_RISK_SANDBOX_OBSERVATION"
    return "DATA_BACKFILL_PENDING"


def blockers_for(disposition: str, classification: dict[str, Any], readiness: dict[str, Any]) -> list[str]:
    if disposition == "CORE_RESEARCH_SANDBOX":
        return [
            "TTM_AND_ANNUAL_FINANCIALS_PENDING",
            "VALUATION_INPUTS_PENDING",
            "FORMAL_SAME_INDUSTRY_PEER_GROUP_PENDING",
            "DECISION_GRADE_MARKET_DATA_PENDING",
            "INVESTMENT_OS_CANDIDATE_PROMOTION_NOT_AUTHORIZED",
        ]
    if disposition == "OFFICIAL_FILING_WATCH":
        blockers = [
            "SEC_FINANCIAL_FACTS_PENDING",
            "FINANCIAL_NORMALIZATION_PENDING",
            "FORMAL_SAME_INDUSTRY_PEER_GROUP_PENDING",
            "DECISION_GRADE_MARKET_DATA_PENDING",
            "INVESTMENT_OS_CANDIDATE_PROMOTION_NOT_AUTHORIZED",
        ]
        if classification.get("special_profile_status") != "NONE":
            blockers.append(classification["special_profile_status"])
        return blockers
    if disposition == "BENCHMARK_REFERENCE":
        return [
            "REFERENCE_INSTRUMENT_NOT_ISSUER_CANDIDATE",
            "DECISION_GRADE_BENCHMARK_MARKET_DATA_PENDING",
        ]
    if disposition == "MARKET_RISK_SANDBOX_OBSERVATION":
        return [
            "OFFICIAL_SEC_FINANCIAL_EVIDENCE_PENDING",
            "OFFICIAL_CLASSIFICATION_EVIDENCE_PENDING",
            "DECISION_GRADE_MARKET_DATA_PENDING",
            "INVESTMENT_OS_CANDIDATE_PROMOTION_NOT_AUTHORIZED",
        ]
    if disposition == "DATA_BACKFILL_PENDING":
        return [
            readiness.get("financial_data_readiness", "SEC_DATA_PENDING"),
            readiness.get("market_data_readiness", "MARKET_DATA_PENDING"),
            "OFFICIAL_CLASSIFICATION_EVIDENCE_PENDING",
            "INVESTMENT_OS_CANDIDATE_PROMOTION_NOT_AUTHORIZED",
        ]
    if disposition == "REFERENCE_ONLY":
        return ["REFERENCE_ONLY_NOT_ISSUER_CANDIDATE"]
    if disposition == "INSTRUMENT_REVIEW_REQUIRED":
        return ["INSTRUMENT_PROFILE_REVIEW_REQUIRED"]
    return ["EXCLUDED_BY_RESEARCH_SCOPE"]


def card_status(disposition: str) -> str:
    return {
        "CORE_RESEARCH_SANDBOX": "FULL_SANDBOX_RESEARCH_CARD",
        "OFFICIAL_FILING_WATCH": "OFFICIAL_FILING_WATCH_CARD",
        "BENCHMARK_REFERENCE": "BENCHMARK_REFERENCE_CARD",
        "MARKET_RISK_SANDBOX_OBSERVATION": "MARKET_RISK_OBSERVATION_CARD",
        "DATA_BACKFILL_PENDING": "DATA_BACKFILL_SHELL_CARD",
        "REFERENCE_ONLY": "REFERENCE_ONLY_SHELL_CARD",
        "INSTRUMENT_REVIEW_REQUIRED": "REVIEW_REQUIRED_SHELL_CARD",
        "EXCLUDED": "EXCLUDED_SHELL_CARD",
    }[disposition]


def build_records(inputs: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    readiness_rows = sorted(inputs["security_readiness"], key=lambda row: row["canonical_security_id"])
    factor_status_by = {row["canonical_security_id"]: row for row in inputs["factor_status"]}
    classification_by = {row["canonical_security_id"]: row for row in inputs["classification"]}
    benchmark_assignment_by = {row["canonical_security_id"]: row for row in inputs["benchmark_assignment"]}
    peer_by = {row["canonical_security_id"]: row for row in inputs["peer_membership"]}
    quality_by = group_rows(inputs["quality_factors"], "canonical_security_id")
    market_by = group_rows(inputs["market_factors"], "canonical_security_id")
    risk_by = group_rows(inputs["risk_factors"], "canonical_security_id")
    relative_by = group_rows(inputs["benchmark_relative"], "canonical_security_id")
    statements_by = group_rows(inputs["canonical_statements"], "canonical_security_id")
    metrics_by = group_rows(inputs["derived_metrics"], "canonical_security_id")
    issues_by = group_rows(inputs["normalization_issues"], "canonical_security_id")

    errors: list[str] = []
    expected = contract["acceptance_gates"]["security_universe_count"]
    if len(readiness_rows) != expected:
        errors.append("READINESS_UNIVERSE")
    for name, mapping in (
        ("FACTOR_STATUS", factor_status_by),
        ("CLASSIFICATION", classification_by),
        ("BENCHMARK_ASSIGNMENT", benchmark_assignment_by),
    ):
        if len(mapping) != expected:
            errors.append(name + "_UNIVERSE")

    status_rows: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    queues: dict[str, list[dict[str, Any]]] = {
        "RESEARCH_CARD_DATA_BACKFILL_QUEUE": [],
        "REFERENCE_DATA_BACKFILL_QUEUE": [],
        "INSTRUMENT_PROFILE_REVIEW_QUEUE": [],
        "DECISION_GRADE_MARKET_UPGRADE_QUEUE": [],
        "VALUATION_PEER_BACKFILL_QUEUE": [],
        "FORMAL_CANDIDATE_PROMOTION_BLOCK_QUEUE": [],
        "US_BENCHMARK_POOL_REVIEW_QUEUE": [],
    }
    disposition_counts: Counter[str] = Counter()
    pool_symbols = set(contract["benchmark_pool_contract"]["member_symbols"])
    pool_rows: list[dict[str, Any]] = []
    role_map = {
        "AAPL": "STANDARD_OPERATING_COMPANY_HARDWARE_CASE",
        "MSFT": "STANDARD_OPERATING_COMPANY_SOFTWARE_CASE",
        "NVDA": "STANDARD_OPERATING_COMPANY_SEMICONDUCTOR_CASE",
        "JPM": "FINANCIAL_INSTITUTION_SPECIAL_PROFILE_CASE",
        "BRK.B": "INSURANCE_CONGLOMERATE_SPECIAL_PROFILE_CASE",
        "XOM": "INTEGRATED_ENERGY_CASE",
        "QQQ": "NASDAQ100_BENCHMARK_REFERENCE_INSTRUMENT",
    }

    for readiness in readiness_rows:
        sid = readiness["canonical_security_id"]
        classification = classification_by[sid]
        benchmark_assignment = benchmark_assignment_by[sid]
        has_quality = sid in quality_by
        has_market = sid in market_by
        has_risk = sid in risk_by
        has_relative = sid in relative_by
        disposition = screening_disposition(readiness, has_quality, has_market, has_risk, has_relative, classification, contract)
        disposition_counts[disposition] += 1
        blockers = blockers_for(disposition, classification, readiness)
        pool_member = readiness["symbol"] in pool_symbols
        pool_layer = None
        if disposition == "CORE_RESEARCH_SANDBOX":
            pool_layer = "CORE_FINANCIAL_QUALITY_SANDBOX"
        elif disposition == "OFFICIAL_FILING_WATCH":
            pool_layer = "OFFICIAL_FILING_CLASSIFICATION_WATCH"
        elif disposition == "BENCHMARK_REFERENCE":
            pool_layer = "BENCHMARK_REFERENCE_INSTRUMENT"

        status_row = {
            "screening_status_id": "USSCR-" + record_hash("SCREENING_STATUS", sid)[:24],
            "canonical_security_id": sid,
            "canonical_issuer_id": readiness["canonical_issuer_id"],
            "canonical_listing_id": readiness.get("canonical_listing_id"),
            "symbol": readiness["symbol"],
            "venue": readiness["venue"],
            "research_profile": readiness["research_profile"],
            "research_scope": readiness["research_scope"],
            "readiness_tier": readiness["readiness_tier"],
            "screening_disposition": disposition,
            "research_card_status": card_status(disposition),
            "benchmark_pool_member": pool_member,
            "benchmark_pool_layer": pool_layer,
            "official_filing_count": readiness.get("official_filing_count", 0),
            "official_fact_count": readiness.get("official_fact_count", 0),
            "quality_factor_available": has_quality,
            "market_factor_available": has_market,
            "risk_factor_available": has_risk,
            "benchmark_relative_available": has_relative,
            "official_classification_available": classification.get("classification_status") == "OFFICIAL_SEC_SIC_LINKED_INTERNAL_CROSSWALK",
            "formal_peer_available": classification.get("formal_peer_rank_gate") == "OPEN",
            "valuation_available": False,
            "formal_global_rank_available": False,
            "investment_os_candidate_promotion_ready": False,
            "blocker_codes": blockers,
            "candidate_pool_status": "NOT_AUTHORIZED",
            "trade_authority": "NONE",
        }
        status_rows.append(status_row)

        peer = peer_by.get(sid)
        card = {
            "research_card_id": "USCARD-" + record_hash("RESEARCH_CARD", sid)[:24],
            "card_version": "1.0.0",
            "card_type": card_status(disposition),
            "screening_disposition": disposition,
            "identity": {
                "canonical_security_id": sid,
                "canonical_issuer_id": readiness["canonical_issuer_id"],
                "canonical_listing_id": readiness.get("canonical_listing_id"),
                "symbol": readiness["symbol"],
                "official_security_name": readiness.get("official_security_name"),
                "venue": readiness["venue"],
                "instrument_type": readiness.get("instrument_type"),
                "research_profile": readiness["research_profile"],
                "research_scope": readiness["research_scope"],
            },
            "data_readiness": {
                "readiness_tier": readiness["readiness_tier"],
                "identity_readiness": readiness.get("identity_readiness"),
                "financial_data_readiness": readiness.get("financial_data_readiness"),
                "market_data_readiness": readiness.get("market_data_readiness"),
                "official_filing_count": readiness.get("official_filing_count", 0),
                "official_fact_count": readiness.get("official_fact_count", 0),
                "market_bar_count": readiness.get("market_bar_count", 0),
                "market_first_date": readiness.get("market_first_date"),
                "market_last_date": readiness.get("market_last_date"),
                "sec_cik10": readiness.get("sec_cik10"),
            },
            "classification": {
                "classification_status": classification.get("classification_status"),
                "sic_code": classification.get("sic_code"),
                "sic_title": classification.get("sic_title"),
                "sector": classification.get("sector"),
                "industry": classification.get("industry"),
                "classification_authority": classification.get("classification_authority"),
                "sector_industry_label_authority": classification.get("sector_industry_label_authority"),
                "special_profile_status": classification.get("special_profile_status"),
                "peer_group_id": peer.get("peer_group_id") if peer else None,
                "peer_group_status": peer.get("peer_group_status") if peer else None,
            },
            "factor_snapshot": {
                "quality": factor_snapshot(quality_by.get(sid, [])),
                "market": factor_snapshot(market_by.get(sid, [])),
                "risk": factor_snapshot(risk_by.get(sid, [])),
                "valuation": {},
                "global_score": None,
                "formal_rank_emitted": False,
            },
            "benchmark_context": {
                "assignment_status": benchmark_assignment.get("benchmark_assignment_status"),
                "benchmark_id": benchmark_assignment.get("benchmark_id"),
                "benchmark_usage": benchmark_assignment.get("benchmark_usage"),
                "relative_factors": factor_snapshot(relative_by.get(sid, [])),
            },
            "financial_evidence_summary": {
                "canonical_statement_row_count": len(statements_by.get(sid, [])),
                "derived_metric_row_count": len(metrics_by.get(sid, [])),
                "open_normalization_issue_count": len(issues_by.get(sid, [])),
                "ttm_ready": False,
                "annual_ready": False,
                "valuation_ready": False,
            },
            "blockers_and_gates": {
                "blocker_codes": blockers,
                "formal_peer_rank_gate": "CLOSED",
                "sector_neutral_factor_gate": "CLOSED",
                "formal_valuation_gate": "CLOSED",
                "investment_os_candidate_pool_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X3E",
                "simulation_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X3E",
                "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
                "trade_authority": "NONE",
            },
            "artifact_boundary": "RESEARCH_CARD_NOT_INVESTMENT_RECOMMENDATION",
        }
        cards.append(card)

        queue_base = {
            "canonical_security_id": sid,
            "canonical_issuer_id": readiness["canonical_issuer_id"],
            "symbol": readiness["symbol"],
            "screening_disposition": disposition,
        }
        if disposition == "DATA_BACKFILL_PENDING":
            queues["RESEARCH_CARD_DATA_BACKFILL_QUEUE"].append({**queue_base, "blocker_codes": blockers})
        elif disposition == "REFERENCE_ONLY":
            queues["REFERENCE_DATA_BACKFILL_QUEUE"].append({**queue_base, "required_action": "OPTIONAL_REFERENCE_DATA_ENRICHMENT"})
        elif disposition == "INSTRUMENT_REVIEW_REQUIRED":
            queues["INSTRUMENT_PROFILE_REVIEW_QUEUE"].append({**queue_base, "required_action": "RESOLVE_INSTRUMENT_PROFILE_BEFORE_RESEARCH_SCOPE"})
        if has_market and has_risk:
            queues["DECISION_GRADE_MARKET_UPGRADE_QUEUE"].append({**queue_base, "required_action": "REPLACE_NON_DECISION_GRADE_MARKET_DATA_BEFORE_FORMAL_USE"})
        issuer_pool_symbols = contract["benchmark_pool_contract"]["core_quality_sandbox_symbols"] + contract["benchmark_pool_contract"]["filing_watch_symbols"]
        if readiness["symbol"] in issuer_pool_symbols:
            queues["VALUATION_PEER_BACKFILL_QUEUE"].append({**queue_base, "blocker_codes": blockers})
            queues["FORMAL_CANDIDATE_PROMOTION_BLOCK_QUEUE"].append({**queue_base, "blocker_codes": blockers})
        if pool_member:
            pool_row = {
                "pool_membership_id": "USPOOL-" + record_hash("US_BENCHMARK_POOL", sid)[:24],
                "pool_id": "US_RESEARCH_BENCHMARK_POOL_V1",
                "pool_name": "US Research Benchmark Pool V1",
                "canonical_security_id": sid,
                "canonical_issuer_id": readiness["canonical_issuer_id"],
                "symbol": readiness["symbol"],
                "pool_layer": pool_layer,
                "validation_role": role_map[readiness["symbol"]],
                "screening_disposition": disposition,
                "research_card_id": card["research_card_id"],
                "formal_candidate_pool_member": False,
                "investment_recommendation": False,
                "candidate_pool_status": "NOT_AUTHORIZED",
                "trade_authority": "NONE",
            }
            pool_rows.append(pool_row)
            queues["US_BENCHMARK_POOL_REVIEW_QUEUE"].append({
                **queue_base,
                "pool_layer": pool_layer,
                "validation_role": role_map[readiness["symbol"]],
                "required_action": "REVIEW_RESEARCH_ARTIFACT_ONLY_NO_CANDIDATE_PROMOTION",
            })

    for rows in queues.values():
        rows.sort(key=stable_json)
    status_rows.sort(key=lambda row: row["canonical_security_id"])
    cards.sort(key=lambda row: row["identity"]["canonical_security_id"])
    pool_rows.sort(key=lambda row: (row["pool_layer"], row["symbol"]))

    research_scope_eligible = sum(row["research_scope"] in {"STANDARD_RESEARCH_PROFILE", "SPECIAL_RESEARCH_PROFILE"} for row in readiness_rows)
    official_classification_count = sum(row["official_classification_available"] for row in status_rows)
    official_filing_count = sum(row["official_filing_count"] > 0 for row in status_rows)
    quality_count = sum(row["quality_factor_available"] for row in status_rows)
    market_risk_count = sum(row["market_factor_available"] and row["risk_factor_available"] for row in status_rows)
    relative_count = sum(row["benchmark_relative_available"] for row in status_rows)
    funnel = [
        ("UNIVERSE_ACCOUNTED", len(status_rows), "PASS", "ALL_CANONICAL_SECURITIES"),
        ("RESEARCH_SCOPE_ELIGIBLE", research_scope_eligible, "PARTIAL", "STANDARD_OR_SPECIAL_RESEARCH_PROFILE"),
        ("OFFICIAL_CLASSIFICATION_READY", official_classification_count, "PARTIAL", "SEC_SIC_LINKED"),
        ("OFFICIAL_FILING_READY", official_filing_count, "PARTIAL", "SEC_OFFICIAL_FILING"),
        ("QUARTERLY_QUALITY_SANDBOX_READY", quality_count, "SANDBOX", "OFFICIAL_SEC_DERIVED_SINGLE_QUARTER"),
        ("MARKET_RISK_SANDBOX_READY", market_risk_count, "SANDBOX", "NON_DECISION_GRADE_MARKET_DATA"),
        ("BENCHMARK_RELATIVE_SANDBOX_READY", relative_count, "SANDBOX", "RELATIVE_TO_QQQ_NON_DECISION_GRADE"),
        ("FORMAL_VALUATION_READY", 0, "BLOCKED", "TTM_ANNUAL_BALANCE_SHEET_CASH_FLOW_PENDING"),
        ("FORMAL_PEER_READY", 0, "BLOCKED", "SAME_INDUSTRY_MINIMUM_AND_PERIOD_COMPARABILITY_PENDING"),
        ("US_BENCHMARK_POOL_MEMBER", len(pool_rows), "RESEARCH_ONLY", "NOT_FORMAL_CANDIDATE_POOL"),
        ("INVESTMENT_OS_GRADUATION_READY", 0, "CLOSED", "NOT_AUTHORIZED_IN_FMDL6X3E"),
    ]
    funnel_rows = [
        {
            "funnel_gate_id": "USFUNNEL-" + record_hash("FUNNEL_GATE", gate)[:24],
            "gate_name": gate,
            "security_count": count,
            "gate_status": status,
            "evidence_boundary": boundary,
            "formal_rank_emitted": False,
            "candidate_pool_mutations": 0,
            "trade_authority": "NONE",
        }
        for gate, count, status, boundary in funnel
    ]
    return {
        "status_rows": status_rows,
        "cards": cards,
        "pool_rows": pool_rows,
        "funnel_rows": funnel_rows,
        "queues": queues,
        "disposition_counts": disposition_counts,
        "errors": errors,
    }


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(stable_json(row) + "\n" for row in rows).encode("utf-8")


def build_shards(records: dict[str, Any], bucket_count: int, generated_at: str) -> tuple[bytes, list[dict[str, Any]]]:
    domains = (
        ("SCREENING_STATUS", records["status_rows"], lambda row: row["canonical_security_id"]),
        ("RESEARCH_CARD", records["cards"], lambda row: row["identity"]["canonical_security_id"]),
        ("BENCHMARK_POOL_MEMBERSHIP", records["pool_rows"], lambda row: row["canonical_security_id"]),
        ("FUNNEL_GATE_OBSERVATION", records["funnel_rows"], lambda row: row["funnel_gate_id"]),
    )
    entries: dict[str, bytes] = {}
    manifest: list[dict[str, Any]] = []
    for domain, rows, key_fn in domains:
        for index in range(bucket_count):
            bucket = f"{index:02X}"
            shard = [row for row in rows if bucket_hex(str(key_fn(row)), bucket_count) == bucket]
            shard.sort(key=lambda row: (str(key_fn(row)), stable_json(row)))
            payload = jsonl_bytes(shard)
            entries[f"{domain}/{bucket}.jsonl"] = payload
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
    checks, errors = validate_contract(repo_root)
    if errors:
        raise RuntimeError("CONTRACT_ERRORS:" + ",".join(errors))
    contract = load_json(repo_root / CONTRACT_PATH)
    inputs = load_inputs(repo_root)
    records = build_records(inputs, contract)
    if records["errors"]:
        raise RuntimeError("RECORD_ERRORS:" + ",".join(records["errors"]))

    input_manifest_sha = {name: sha256_file(path) for name, path in inputs["manifests"].items()}
    contract_sha = sha256_file(repo_root / CONTRACT_PATH)
    release_fingerprint = record_hash(
        "FMDL6X3E_RELEASE",
        contract_sha,
        input_manifest_sha["readiness"],
        input_manifest_sha["financial"],
        input_manifest_sha["factor"],
        input_manifest_sha["framework"],
    )
    release_id = f"FMDL6X3E_20260723_{release_fingerprint[:12]}"
    candidate_root.mkdir(parents=True, exist_ok=True)
    shard_zip, shards = build_shards(records, int(contract["storage_contract"]["bucket_count"]), accepted_at)
    (candidate_root / "FMDL6X3E_RESEARCH_SHARDS.zip").write_bytes(shard_zip)
    (candidate_root / "FMDL6X3E_REVIEW_QUEUES.zip").write_bytes(build_queue_zip(records["queues"]))

    dispositions = dict(sorted(records["disposition_counts"].items()))
    pool_by_layer = dict(sorted(Counter(row["pool_layer"] for row in records["pool_rows"]).items()))
    write_json(candidate_root / "FMDL6X3E_SCREENING_FUNNEL_SUMMARY.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "screening_method": "EVIDENCE_GATED_NON_RANKED_FUNNEL",
        "security_universe_count": len(records["status_rows"]),
        "disposition_counts": dispositions,
        "funnel_gates": records["funnel_rows"],
        "formal_candidate_promotion_count": 0,
        "global_rank_count": 0,
    })
    write_json(candidate_root / "FMDL6X3E_US_BENCHMARK_POOL.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "pool_id": "US_RESEARCH_BENCHMARK_POOL_V1",
        "pool_name": "US Research Benchmark Pool V1",
        "pool_status": "RESEARCH_VALIDATION_POOL_NOT_INVESTMENT_OS_CANDIDATE_POOL",
        "member_count": len(records["pool_rows"]),
        "layer_counts": pool_by_layer,
        "members": records["pool_rows"],
        "formal_candidate_pool_member_count": 0,
        "investment_recommendation_count": 0,
        "trade_authority": "NONE",
    })
    queue_counts = {name: len(rows) for name, rows in sorted(records["queues"].items())}
    write_json(candidate_root / "FMDL6X3E_QUEUE_SUMMARY.json", {"phase_id": PHASE_ID, "release_id": release_id, "queue_counts": queue_counts})

    gates = contract["acceptance_gates"]
    quality = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "quality_status": "PASS",
        "security_universe_expected": gates["security_universe_count"],
        "security_universe_actual": len(records["status_rows"]),
        "research_card_count": len(records["cards"]),
        "benchmark_pool_member_count": len(records["pool_rows"]),
        "disposition_counts": dispositions,
        "formal_candidate_promotion_count": 0,
        "global_rank_count": 0,
        "neutral_fill_count": 0,
        "expected_shard_count": gates["logical_shard_count"],
        "manifested_shard_count": len(shards),
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    expected_dispositions = {
        "CORE_RESEARCH_SANDBOX": gates["core_research_sandbox_count"],
        "OFFICIAL_FILING_WATCH": gates["official_filing_watch_count"],
        "BENCHMARK_REFERENCE": gates["benchmark_reference_count"],
        "MARKET_RISK_SANDBOX_OBSERVATION": gates["market_risk_observation_count"],
        "DATA_BACKFILL_PENDING": gates["data_backfill_pending_count"],
        "REFERENCE_ONLY": gates["reference_only_count"],
        "INSTRUMENT_REVIEW_REQUIRED": gates["instrument_review_count"],
        "EXCLUDED": gates["excluded_count"],
    }
    quality_errors: list[str] = []
    if len(records["status_rows"]) != gates["security_universe_count"]:
        quality_errors.append("SECURITY_UNIVERSE")
    if len(records["cards"]) != gates["research_card_count"]:
        quality_errors.append("RESEARCH_CARD_COUNT")
    if len(records["pool_rows"]) != gates["benchmark_pool_member_count"]:
        quality_errors.append("BENCHMARK_POOL_COUNT")
    for disposition, expected_count in expected_dispositions.items():
        if dispositions.get(disposition, 0) != expected_count:
            quality_errors.append("DISPOSITION:" + disposition)
    if len(shards) != gates["logical_shard_count"]:
        quality_errors.append("SHARD_COUNT")
    if any(row["investment_os_candidate_promotion_ready"] for row in records["status_rows"]):
        quality_errors.append("CANDIDATE_PROMOTION_READY")
    if any(row["formal_candidate_pool_member"] for row in records["pool_rows"]):
        quality_errors.append("FORMAL_POOL_MEMBER")
    if any(row["trade_authority"] != "NONE" for row in records["status_rows"] + records["pool_rows"]):
        quality_errors.append("TRADE_AUTHORITY")
    if quality_errors:
        quality["quality_status"] = "FAIL"
        quality["errors"] = quality_errors
    write_json(candidate_root / "FMDL6X3E_QUALITY_REPORT.json", quality)
    if quality_errors:
        raise RuntimeError("QUALITY_ERRORS:" + ",".join(quality_errors))

    coverage = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "security_universe_count": len(records["status_rows"]),
        "research_card_count": len(records["cards"]),
        "benchmark_pool_member_count": len(records["pool_rows"]),
        "core_research_sandbox_count": dispositions.get("CORE_RESEARCH_SANDBOX", 0),
        "official_filing_watch_count": dispositions.get("OFFICIAL_FILING_WATCH", 0),
        "market_risk_observation_count": dispositions.get("MARKET_RISK_SANDBOX_OBSERVATION", 0),
        "formal_candidate_promotion_count": 0,
        "full_research_readiness_claimed": False,
        "formal_screening_rank_completion_claimed": False,
        "benchmark_pool_is_candidate_pool": False,
    }
    write_json(candidate_root / "FMDL6X3E_COVERAGE_REPORT.json", coverage)
    decision = {
        "phase_id": PHASE_ID,
        "status": EXIT_STATUS,
        "release_id": release_id,
        "release_sequence": 40,
        "accepted_at": accepted_at,
        "source_commit": source_commit,
        "input_release_id": contract["input_contract"]["framework_release_id"],
        "next_gate": NEXT_GATE,
        "screening_status": "EVIDENCE_GATED_RESEARCH_FUNNEL_WITH_NO_FORMAL_RANK_OR_PROMOTION",
        "research_card_count": len(records["cards"]),
        "benchmark_pool_member_count": len(records["pool_rows"]),
        "formal_candidate_promotion_count": 0,
        "global_rank_count": 0,
        "research_production_gate": "OPEN_FOR_FMDL6X3_FINAL_RECONCILIATION",
        "investment_os_candidate_pool_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X3E",
        "simulation_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X3E",
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    write_json(candidate_root / "FMDL6X3E_DECISION.json", decision)
    write_json(candidate_root / "FMDL6X3E_SOURCE_BINDING.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "input_manifest_sha256": input_manifest_sha,
        "screening_method": "EVIDENCE_GATED_NON_RANKED_FUNNEL",
        "financial_source_grade": "DECISION_GRADE_OFFICIAL_SEC_DERIVED_WHERE_AVAILABLE",
        "market_source_grade": "NON_DECISION_GRADE_FALLBACK",
        "classification_authority": "SEC_OFFICIAL_WITH_INTERNAL_SEC_SIC_CROSSWALK",
        "benchmark_pool_is_candidate_pool": False,
        "neutral_fill_used": False,
        "silent_source_substitution": False,
        "formal_rank_emitted": False,
        "formal_candidate_promotion_emitted": False,
    })

    manifest_files: dict[str, Any] = {}
    for path in sorted(candidate_root.iterdir()):
        if path.name == "FMDL6X3E_MANIFEST.json" or not path.is_file():
            continue
        manifest_files[path.name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    write_json(candidate_root / "FMDL6X3E_MANIFEST.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": 40,
        "generated_at": accepted_at,
        "contract_sha256": contract_sha,
        "input_manifest_sha256": input_manifest_sha,
        "files": manifest_files,
        "shards": shards,
    })
    return {"decision": decision, "quality": quality, "coverage": coverage, "queue_counts": queue_counts, "contract_checks": checks}


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
    manifest = load_json(candidate_root / "FMDL6X3E_MANIFEST.json")
    for name, meta in manifest["files"].items():
        path = candidate_root / name
        if not path.is_file() or path.stat().st_size != meta["bytes"] or sha256_file(path) != meta["sha256"]:
            errors.append("MANIFEST_FILE:" + name)
    decision = load_json(candidate_root / "FMDL6X3E_DECISION.json")
    if decision.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")
    result = {
        "phase_id": PHASE_ID,
        "status": "PASS" if not errors else "FAIL",
        "same_input_replay": "PASS" if left == right else "FAIL",
        "errors": errors,
        "release_id": decision.get("release_id"),
    }
    write_json(acceptance_path, result)
    if errors:
        raise RuntimeError("ACCEPTANCE_ERRORS:" + ",".join(errors))
    return result


def publish(repo_root: Path, candidate_root: Path, published_at: str, source_commit: str) -> dict[str, Any]:
    contract = load_json(repo_root / CONTRACT_PATH)
    decision = load_json(candidate_root / "FMDL6X3E_DECISION.json")
    release_id = decision["release_id"]
    current = repo_root / contract["storage_contract"]["current_root"]
    release = repo_root / contract["storage_contract"]["release_root"].replace("<release_id>", release_id)
    normalized = repo_root / contract["storage_contract"]["normalized_root"].replace("<release_id>", release_id)
    archive_root = repo_root / contract["storage_contract"]["archive_root"]
    if release.exists():
        raise RuntimeError("IMMUTABLE_RELEASE_COLLISION")
    if current.exists():
        archive = archive_root / f"screening_research_cards_{published_at.replace(':', '').replace('-', '')}"
        copytree_replace(current, archive)
    copytree_replace(candidate_root, current)
    copytree_replace(candidate_root, release)
    copytree_replace(candidate_root, normalized)
    manifest_sha = sha256_file(current / "FMDL6X3E_MANIFEST.json")
    pointer = {
        "phase_id": PHASE_ID,
        "status": EXIT_STATUS,
        "release_id": release_id,
        "release_sequence": 40,
        "published_at": published_at,
        "source_commit": source_commit,
        "current_path": str(current.relative_to(repo_root)),
        "release_path": str(release.relative_to(repo_root)),
        "normalized_path": str(normalized.relative_to(repo_root)),
        "manifest_sha256": manifest_sha,
        "screening_status": decision["screening_status"],
        "research_card_count": decision["research_card_count"],
        "benchmark_pool_member_count": decision["benchmark_pool_member_count"],
        "formal_candidate_promotion_count": 0,
        "global_rank_count": 0,
        "next_gate": NEXT_GATE,
        "research_production_gate": decision["research_production_gate"],
        "investment_os_candidate_pool_gate": decision["investment_os_candidate_pool_gate"],
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    write_json(repo_root / contract["storage_contract"]["last_success"], pointer)
    write_json(repo_root / contract["storage_contract"]["last_known_good"], {
        **pointer,
        "lkg_scope": "FMDL6X3_SCREENING_RESEARCH_CARDS_AND_US_BENCHMARK_POOL_DOMAIN",
        "lkg_reason": "LATEST_ACCEPTED_EVIDENCE_GATED_RESEARCH_FUNNEL_WITH_ZERO_FORMAL_CANDIDATE_PROMOTION",
    })
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
        checks, errors = validate_contract(root)
        print({"checks": checks, "errors": errors})
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
