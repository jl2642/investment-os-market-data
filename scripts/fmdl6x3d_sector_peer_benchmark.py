from __future__ import annotations

import argparse
import csv
import shutil
import zipfile
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

PHASE_ID = "FMDL-6X3-D"
EXIT_STATUS = "FMDL6X3D_SECTOR_INDUSTRY_PEER_AND_BENCHMARK_FRAMEWORK_ACCEPTED"
NEXT_GATE = "FMDL-6X3-E_SCREENING_FUNNEL_RESEARCH_CARDS_AND_US_BENCHMARK_POOL"
CONTRACT_PATH = Path("config/fmdl6x3d_sector_peer_benchmark_contract.json")
READINESS_ROOT = Path("outputs/fmdl6x3/current/research_universe_readiness")
FACTOR_ROOT = Path("outputs/fmdl6x3/current/factor_engine")
SIC_EVIDENCE_PATH = Path("evidence/fmdl6x3d_sec_sic_official.csv")
BENCHMARK_EVIDENCE_PATH = Path("evidence/fmdl6x3d_benchmark_official.csv")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_contract(repo_root: Path) -> tuple[list[str], list[str]]:
    checks: list[str] = []
    errors: list[str] = []
    contract_path = repo_root / CONTRACT_PATH
    if not contract_path.is_file():
        return checks, ["CONTRACT_MISSING"]
    contract = load_json(contract_path)
    if contract.get("phase_id") != PHASE_ID:
        errors.append("PHASE_ID")
    if contract.get("input_contract", {}).get("input_release_id") != "FMDL6X3C_20260722_2209fb89f9ed":
        errors.append("INPUT_RELEASE")
    expected = {
        "security_universe_count": 8785,
        "official_sic_evidence_count": 6,
        "available_benchmark_count": 1,
        "formal_peer_group_count": 0,
        "benchmark_relative_observation_count": 15,
        "logical_shard_count": 320,
    }
    gates = contract.get("acceptance_gates", {})
    for key, value in expected.items():
        if gates.get(key) != value:
            errors.append("ACCEPTANCE_GATE:" + key)
    for path in (
        repo_root / READINESS_ROOT / "FMDL6X3A_READINESS_SHARDS.zip",
        repo_root / READINESS_ROOT / "FMDL6X3A_MANIFEST.json",
        repo_root / FACTOR_ROOT / "FMDL6X3C_FACTOR_SHARDS.zip",
        repo_root / FACTOR_ROOT / "FMDL6X3C_MANIFEST.json",
        repo_root / SIC_EVIDENCE_PATH,
        repo_root / BENCHMARK_EVIDENCE_PATH,
    ):
        if not path.is_file():
            errors.append("INPUT_MISSING:" + str(path.relative_to(repo_root)))
    checks.extend(["CONTRACT_SHAPE", "UPSTREAM_INPUTS", "EVIDENCE_FILES", "ZERO_MUTATION_GATE"])
    if contract.get("zero_mutation_gate") != {
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders": 0,
    }:
        errors.append("ZERO_MUTATION_GATE")
    return checks, errors


def load_inputs(repo_root: Path) -> dict[str, Any]:
    readiness_zip = repo_root / READINESS_ROOT / "FMDL6X3A_READINESS_SHARDS.zip"
    factor_zip = repo_root / FACTOR_ROOT / "FMDL6X3C_FACTOR_SHARDS.zip"
    return {
        "security_readiness": read_zip_jsonl(readiness_zip, "SECURITY_READINESS/"),
        "factor_status": read_zip_jsonl(factor_zip, "SECURITY_FACTOR_STATUS/"),
        "quality_factors": read_zip_jsonl(factor_zip, "QUALITY_FACTOR/"),
        "market_factors": read_zip_jsonl(factor_zip, "MARKET_FACTOR/"),
        "risk_factors": read_zip_jsonl(factor_zip, "RISK_FACTOR/"),
        "sic_evidence": read_csv(repo_root / SIC_EVIDENCE_PATH),
        "benchmark_evidence": read_csv(repo_root / BENCHMARK_EVIDENCE_PATH),
        "readiness_manifest": repo_root / READINESS_ROOT / "FMDL6X3A_MANIFEST.json",
        "factor_manifest": repo_root / FACTOR_ROOT / "FMDL6X3C_MANIFEST.json",
    }


def _classification_status(status: dict[str, Any], evidence: dict[str, str] | None) -> str:
    if evidence:
        return "OFFICIAL_SEC_SIC_LINKED_INTERNAL_CROSSWALK"
    scope = status["research_scope"]
    if scope in {"STANDARD_RESEARCH_PROFILE", "SPECIAL_RESEARCH_PROFILE"}:
        return "OFFICIAL_SECTOR_EVIDENCE_BACKFILL_PENDING"
    if scope == "REFERENCE_ONLY":
        return "PROFILE_REFERENCE_ONLY_NO_ISSUER_SECTOR_REQUIRED"
    if scope == "REVIEW_REQUIRED":
        return "INSTRUMENT_PROFILE_REVIEW_REQUIRED"
    return "NOT_APPLICABLE"


def _benchmark_assignment(status: dict[str, Any], evidence: dict[str, str] | None) -> tuple[str, str | None]:
    if status["symbol"] in {"AAPL", "MSFT", "NVDA"} and evidence:
        return "SANDBOX_REFERENCE_AVAILABLE_NON_SECTOR_BENCHMARK", "USBMK-NASDAQ100-QQQ"
    scope = status["research_scope"]
    if scope in {"STANDARD_RESEARCH_PROFILE", "SPECIAL_RESEARCH_PROFILE"}:
        return "BENCHMARK_PENDING_SECTOR_OR_BROAD_REFERENCE", None
    if scope == "REFERENCE_ONLY":
        return "REFERENCE_INSTRUMENT_NO_ISSUER_BENCHMARK", None
    if scope == "REVIEW_REQUIRED":
        return "BENCHMARK_BLOCKED_PROFILE_REVIEW", None
    return "NOT_APPLICABLE", None


def build_records(inputs: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    statuses = sorted(inputs["factor_status"], key=lambda row: row["canonical_security_id"])
    readiness_by_security = {row["canonical_security_id"]: row for row in inputs["security_readiness"]}
    status_by_security = {row["canonical_security_id"]: row for row in statuses}
    evidence_by_security = {row["canonical_security_id"]: row for row in inputs["sic_evidence"]}

    errors: list[str] = []
    if len(statuses) != contract["acceptance_gates"]["security_universe_count"]:
        errors.append("SECURITY_UNIVERSE")
    if len(evidence_by_security) != contract["acceptance_gates"]["official_sic_evidence_count"]:
        errors.append("SIC_EVIDENCE_COUNT")

    for security_id, evidence in evidence_by_security.items():
        status = status_by_security.get(security_id)
        readiness = readiness_by_security.get(security_id)
        if not status or not readiness:
            errors.append("EVIDENCE_SECURITY_NOT_FOUND:" + security_id)
            continue
        if status["canonical_issuer_id"] != evidence["canonical_issuer_id"] or status["symbol"] != evidence["symbol"]:
            errors.append("EVIDENCE_IDENTITY_MISMATCH:" + security_id)
        if readiness.get("sec_cik10") != evidence["cik10"]:
            errors.append("EVIDENCE_CIK_MISMATCH:" + security_id)
        if not evidence["source_url"].startswith("https://www.sec.gov/"):
            errors.append("NON_SEC_SIC_SOURCE:" + security_id)

    classification_rows: list[dict[str, Any]] = []
    benchmark_assignments: list[dict[str, Any]] = []
    queues: dict[str, list[dict[str, Any]]] = {
        "CLASSIFICATION_EVIDENCE_BACKFILL_QUEUE": [],
        "PEER_GROUP_MINIMUM_SIZE_QUEUE": [],
        "SPECIAL_PROFILE_OVERRIDE_QUEUE": [],
        "BENCHMARK_SECURITY_BACKFILL_QUEUE": [],
        "BENCHMARK_DATA_GRADE_UPGRADE_QUEUE": [],
        "QUALITY_PERIOD_COMPARABILITY_QUEUE": [],
    }

    for status in statuses:
        sid = status["canonical_security_id"]
        evidence = evidence_by_security.get(sid)
        classification_status = _classification_status(status, evidence)
        assignment_status, benchmark_id = _benchmark_assignment(status, evidence)
        row = {
            "canonical_security_id": sid,
            "canonical_issuer_id": status["canonical_issuer_id"],
            "symbol": status["symbol"],
            "venue": status.get("venue"),
            "research_profile": status["research_profile"],
            "research_scope": status["research_scope"],
            "classification_status": classification_status,
            "sic_code": evidence["sic_code"] if evidence else None,
            "sic_title": evidence["sic_title"] if evidence else None,
            "sector": evidence["sector"] if evidence else None,
            "industry": evidence["industry"] if evidence else None,
            "classification_authority": evidence["classification_authority"] if evidence else None,
            "sector_industry_label_authority": "INTERNAL_SEC_SIC_CROSSWALK_V1" if evidence else None,
            "source_url": evidence["source_url"] if evidence else None,
            "special_profile_status": evidence["special_profile_status"] if evidence else "NONE",
            "formal_peer_rank_gate": "BLOCKED_INSUFFICIENT_SAME_INDUSTRY_COMPARABLE_PEERS" if evidence else "BLOCKED_CLASSIFICATION_EVIDENCE_PENDING" if status["research_scope"] in {"STANDARD_RESEARCH_PROFILE", "SPECIAL_RESEARCH_PROFILE"} else "NOT_APPLICABLE",
            "sector_neutral_factor_emitted": False,
            "candidate_pool_status": "NOT_AUTHORIZED",
            "trade_authority": "NONE",
        }
        classification_rows.append(row)
        benchmark_assignments.append({
            "canonical_security_id": sid,
            "canonical_issuer_id": status["canonical_issuer_id"],
            "symbol": status["symbol"],
            "research_profile": status["research_profile"],
            "research_scope": status["research_scope"],
            "sector": row["sector"],
            "benchmark_assignment_status": assignment_status,
            "benchmark_id": benchmark_id,
            "benchmark_usage": "NON_DECISION_GRADE_RELATIVE_SANDBOX_ONLY" if benchmark_id else None,
            "candidate_pool_status": "NOT_AUTHORIZED",
            "trade_authority": "NONE",
        })
        queue_base = {
            "canonical_security_id": sid,
            "canonical_issuer_id": status["canonical_issuer_id"],
            "symbol": status["symbol"],
            "research_profile": status["research_profile"],
            "research_scope": status["research_scope"],
        }
        if classification_status == "OFFICIAL_SECTOR_EVIDENCE_BACKFILL_PENDING":
            queues["CLASSIFICATION_EVIDENCE_BACKFILL_QUEUE"].append({**queue_base, "required_action": "CAPTURE_OFFICIAL_SEC_SIC_OR_APPROVED_CLASSIFICATION_EVIDENCE"})
        if assignment_status == "BENCHMARK_PENDING_SECTOR_OR_BROAD_REFERENCE":
            queues["BENCHMARK_SECURITY_BACKFILL_QUEUE"].append({**queue_base, "required_action": "RESOLVE_OFFICIAL_SECTOR_AND_ACCEPTED_BENCHMARK_SECURITY"})

    official_rows = [row for row in classification_rows if row["classification_status"] == "OFFICIAL_SEC_SIC_LINKED_INTERNAL_CROSSWALK"]
    industry_members: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    sector_members: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in official_rows:
        industry_members[(row["sector"], row["industry"])].append(row)
        sector_members[row["sector"]].append(row)

    peer_rows: list[dict[str, Any]] = []
    formal_peer_groups = 0
    for (sector, industry), members in sorted(industry_members.items()):
        member_count = len(members)
        if member_count >= contract["peer_contract"]["formal_peer_minimum_members"]:
            formal_peer_groups += 1
        group_id = "USPEER-" + record_hash("PEER_GROUP", sector, industry)[:24]
        for member in sorted(members, key=lambda row: row["canonical_security_id"]):
            peer_row = {
                "peer_group_id": group_id,
                "canonical_security_id": member["canonical_security_id"],
                "canonical_issuer_id": member["canonical_issuer_id"],
                "symbol": member["symbol"],
                "sector": sector,
                "industry": industry,
                "member_count": member_count,
                "peer_group_status": "FORMAL_PEER_GROUP" if member_count >= contract["peer_contract"]["formal_peer_minimum_members"] else "INSUFFICIENT_MEMBERS_FOR_FORMAL_PEER_GROUP",
                "formal_peer_rank_emitted": False,
                "candidate_pool_status": "NOT_AUTHORIZED",
                "trade_authority": "NONE",
            }
            peer_rows.append(peer_row)
            if member_count < contract["peer_contract"]["formal_peer_minimum_members"]:
                queues["PEER_GROUP_MINIMUM_SIZE_QUEUE"].append({
                    "peer_group_id": group_id,
                    "canonical_security_id": member["canonical_security_id"],
                    "canonical_issuer_id": member["canonical_issuer_id"],
                    "symbol": member["symbol"],
                    "sector": sector,
                    "industry": industry,
                    "member_count": member_count,
                    "minimum_required": contract["peer_contract"]["formal_peer_minimum_members"],
                    "required_action": "BACKFILL_OFFICIAL_SAME_INDUSTRY_COMPARABLE_PEERS",
                })
        for member in members:
            if member["special_profile_status"] != "NONE":
                queues["SPECIAL_PROFILE_OVERRIDE_QUEUE"].append({
                    "canonical_security_id": member["canonical_security_id"],
                    "canonical_issuer_id": member["canonical_issuer_id"],
                    "symbol": member["symbol"],
                    "special_profile_status": member["special_profile_status"],
                    "required_action": "IMPLEMENT_PROFILE_SPECIFIC_NORMALIZATION_BEFORE_FORMAL_PEER_RANKING",
                })

    sector_rows: list[dict[str, Any]] = []
    for sector, members in sorted(sector_members.items()):
        sector_rows.append({
            "sector_cohort_id": "USSECTOR-" + record_hash("SECTOR_COHORT", sector)[:24],
            "sector": sector,
            "official_member_count": len(members),
            "member_security_ids": sorted(member["canonical_security_id"] for member in members),
            "member_symbols": sorted(member["symbol"] for member in members),
            "industry_count": len({member["industry"] for member in members}),
            "cohort_status": "SECTOR_SANDBOX_ONLY_NOT_INDUSTRY_PEER_GROUP",
            "sector_neutral_rank_emitted": False,
            "trade_authority": "NONE",
        })

    benchmark_registry: list[dict[str, Any]] = []
    benchmark_by_id: dict[str, dict[str, Any]] = {}
    for row in inputs["benchmark_evidence"]:
        benchmark = {
            "benchmark_id": row["benchmark_id"],
            "benchmark_role": row["benchmark_role"],
            "symbol": row["symbol"],
            "canonical_security_id": row["canonical_security_id"],
            "canonical_issuer_id": row["canonical_issuer_id"],
            "index_name": row["index_name"],
            "benchmark_type": row["benchmark_type"],
            "evidence_authority": row["evidence_authority"],
            "evidence_url": row["evidence_url"],
            "availability_status": row["availability_status"],
            "data_grade": row["data_grade"],
            "usage_scope": row["usage_scope"],
        }
        benchmark_registry.append(benchmark)
        benchmark_by_id[benchmark["benchmark_id"]] = benchmark
    if len(benchmark_registry) != contract["acceptance_gates"]["available_benchmark_count"]:
        errors.append("AVAILABLE_BENCHMARK_COUNT")
    qqq = benchmark_by_id.get("USBMK-NASDAQ100-QQQ")
    if not qqq or qqq["canonical_security_id"] not in status_by_security:
        errors.append("QQQ_BENCHMARK_IDENTITY")
    elif status_by_security[qqq["canonical_security_id"]]["symbol"] != "QQQ":
        errors.append("QQQ_SYMBOL_MISMATCH")
    queues["BENCHMARK_DATA_GRADE_UPGRADE_QUEUE"].append({
        "benchmark_id": "USBMK-NASDAQ100-QQQ",
        "symbol": "QQQ",
        "current_data_grade": "NON_DECISION_GRADE_FALLBACK",
        "required_action": "UPGRADE_TO_ACCEPTED_DECISION_GRADE_MARKET_SOURCE_BEFORE_FORMAL_BENCHMARK_USE",
    })

    market_by_security_metric = {(row["canonical_security_id"], row["factor_name"]): row for row in inputs["market_factors"]}
    benchmark_relative_rows: list[dict[str, Any]] = []
    relative_metrics = contract["benchmark_contract"]["relative_market_metrics"]
    qqq_id = qqq["canonical_security_id"] if qqq else ""
    for symbol in ("AAPL", "MSFT", "NVDA"):
        status = next(row for row in statuses if row["symbol"] == symbol)
        for metric in relative_metrics:
            security_factor = market_by_security_metric.get((status["canonical_security_id"], metric))
            benchmark_factor = market_by_security_metric.get((qqq_id, metric))
            if not security_factor or not benchmark_factor:
                errors.append("BENCHMARK_FACTOR_MISSING:" + symbol + ":" + metric)
                continue
            benchmark_relative_rows.append({
                "relative_factor_id": "USREL-" + record_hash("BENCHMARK_RELATIVE", status["canonical_security_id"], metric, qqq_id)[:24],
                "canonical_security_id": status["canonical_security_id"],
                "canonical_issuer_id": status["canonical_issuer_id"],
                "symbol": symbol,
                "benchmark_id": qqq["benchmark_id"],
                "benchmark_symbol": "QQQ",
                "factor_name": metric + "_EXCESS_VS_QQQ",
                "security_factor_value": security_factor["factor_value"],
                "benchmark_factor_value": benchmark_factor["factor_value"],
                "relative_factor_value": security_factor["factor_value"] - benchmark_factor["factor_value"],
                "as_of_date": security_factor["as_of_date"],
                "unit": "ratio",
                "data_grade": "NON_DECISION_GRADE_FALLBACK",
                "factor_usage": "BENCHMARK_RELATIVE_SANDBOX_ONLY",
                "source_authority": "YAHOO_FREE_UNOFFICIAL",
                "sector_neutral": False,
                "candidate_pool_status": "NOT_AUTHORIZED",
                "trade_authority": "NONE",
            })

    quality_symbols = sorted({row["symbol"] for row in inputs["quality_factors"]})
    for symbol in quality_symbols:
        status = next(row for row in statuses if row["symbol"] == symbol)
        queues["QUALITY_PERIOD_COMPARABILITY_QUEUE"].append({
            "canonical_security_id": status["canonical_security_id"],
            "canonical_issuer_id": status["canonical_issuer_id"],
            "symbol": symbol,
            "required_action": "ALIGN_COMPARABLE_PERIODS_AND_BUILD_SAME_INDUSTRY_PEER_SET_BEFORE_FORMAL_RANKING",
        })

    for rows in queues.values():
        rows.sort(key=stable_json)
    classification_rows.sort(key=lambda row: row["canonical_security_id"])
    peer_rows.sort(key=lambda row: (row["peer_group_id"], row["canonical_security_id"]))
    benchmark_assignments.sort(key=lambda row: row["canonical_security_id"])
    benchmark_relative_rows.sort(key=lambda row: (row["canonical_security_id"], row["factor_name"]))
    sector_rows.sort(key=lambda row: row["sector"])

    return {
        "classification_rows": classification_rows,
        "peer_rows": peer_rows,
        "benchmark_assignments": benchmark_assignments,
        "benchmark_relative_rows": benchmark_relative_rows,
        "sector_rows": sector_rows,
        "benchmark_registry": benchmark_registry,
        "queues": queues,
        "formal_peer_group_count": formal_peer_groups,
        "errors": errors,
    }


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(stable_json(row) + "\n" for row in rows).encode("utf-8")


def build_shards(records: dict[str, Any], bucket_count: int, generated_at: str) -> tuple[bytes, list[dict[str, Any]]]:
    entries: dict[str, bytes] = {}
    manifest: list[dict[str, Any]] = []
    domains = (
        ("SECURITY_CLASSIFICATION_STATUS", records["classification_rows"], "canonical_security_id"),
        ("PEER_GROUP_MEMBERSHIP", records["peer_rows"], "canonical_security_id"),
        ("BENCHMARK_ASSIGNMENT", records["benchmark_assignments"], "canonical_security_id"),
        ("BENCHMARK_RELATIVE_FACTOR", records["benchmark_relative_rows"], "canonical_security_id"),
        ("SECTOR_COHORT_SUMMARY", records["sector_rows"], "sector_cohort_id"),
    )
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
    checks, contract_errors = validate_contract(repo_root)
    if contract_errors:
        raise RuntimeError("CONTRACT_ERRORS:" + ",".join(contract_errors))
    contract = load_json(repo_root / CONTRACT_PATH)
    inputs = load_inputs(repo_root)
    records = build_records(inputs, contract)
    if records["errors"]:
        raise RuntimeError("RECORD_ERRORS:" + ",".join(records["errors"]))

    contract_sha = sha256_file(repo_root / CONTRACT_PATH)
    readiness_manifest_sha = sha256_file(inputs["readiness_manifest"])
    factor_manifest_sha = sha256_file(inputs["factor_manifest"])
    sic_evidence_sha = sha256_file(repo_root / SIC_EVIDENCE_PATH)
    benchmark_evidence_sha = sha256_file(repo_root / BENCHMARK_EVIDENCE_PATH)
    release_fingerprint = record_hash("FMDL6X3D_RELEASE", contract_sha, readiness_manifest_sha, factor_manifest_sha, sic_evidence_sha, benchmark_evidence_sha)
    release_id = f"FMDL6X3D_20260723_{release_fingerprint[:12]}"
    candidate_root.mkdir(parents=True, exist_ok=True)
    shard_zip, shards = build_shards(records, int(contract["storage_contract"]["bucket_count"]), accepted_at)
    (candidate_root / "FMDL6X3D_FRAMEWORK_SHARDS.zip").write_bytes(shard_zip)
    (candidate_root / "FMDL6X3D_REVIEW_QUEUES.zip").write_bytes(build_queue_zip(records["queues"]))

    official_count = sum(row["classification_status"] == "OFFICIAL_SEC_SIC_LINKED_INTERNAL_CROSSWALK" for row in records["classification_rows"])
    queue_counts = {name: len(rows) for name, rows in sorted(records["queues"].items())}
    coverage = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "security_universe_count": len(records["classification_rows"]),
        "official_sec_sic_classified_security_count": official_count,
        "official_sector_count": len(records["sector_rows"]),
        "official_industry_cohort_count": len({row["peer_group_id"] for row in records["peer_rows"]}),
        "formal_peer_group_count": records["formal_peer_group_count"],
        "available_benchmark_count": len(records["benchmark_registry"]),
        "benchmark_relative_observation_count": len(records["benchmark_relative_rows"]),
        "sector_neutral_factor_count": 0,
        "global_factor_score_count": 0,
        "full_classification_completion_claimed": False,
        "formal_peer_framework_completion_claimed": False,
        "benchmark_usage": "PARTIAL_NON_DECISION_GRADE_SANDBOX_ONLY",
    }
    write_json(candidate_root / "FMDL6X3D_COVERAGE_REPORT.json", coverage)
    write_json(candidate_root / "FMDL6X3D_SECTOR_COHORTS.json", records["sector_rows"])
    write_json(candidate_root / "FMDL6X3D_BENCHMARK_REGISTRY.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "available_benchmarks": records["benchmark_registry"],
        "required_roles_pending": contract["benchmark_contract"]["required_roles_pending"],
        "formal_benchmark_usage_status": "BLOCKED_DECISION_GRADE_AND_COVERAGE_PENDING",
    })
    write_json(candidate_root / "FMDL6X3D_QUEUE_SUMMARY.json", {"phase_id": PHASE_ID, "release_id": release_id, "queue_counts": queue_counts})

    quality = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "quality_status": "PASS",
        "security_universe_expected": contract["acceptance_gates"]["security_universe_count"],
        "security_universe_actual": len(records["classification_rows"]),
        "official_sic_evidence_count": official_count,
        "sector_cohort_count": len(records["sector_rows"]),
        "formal_peer_group_count": records["formal_peer_group_count"],
        "available_benchmark_count": len(records["benchmark_registry"]),
        "benchmark_relative_observation_count": len(records["benchmark_relative_rows"]),
        "sector_neutral_factor_count": 0,
        "global_factor_score_count": 0,
        "neutral_fill_count": 0,
        "non_decision_benchmark_relative_rows": len(records["benchmark_relative_rows"]),
        "manifested_shard_count": len(shards),
        "expected_shard_count": contract["acceptance_gates"]["logical_shard_count"],
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    errors: list[str] = []
    gates = contract["acceptance_gates"]
    if quality["security_universe_actual"] != gates["security_universe_count"]:
        errors.append("SECURITY_UNIVERSE")
    if official_count != gates["official_sic_evidence_count"]:
        errors.append("OFFICIAL_SIC_EVIDENCE")
    if records["formal_peer_group_count"] != gates["formal_peer_group_count"]:
        errors.append("FORMAL_PEER_GROUP_BOUNDARY")
    if len(records["benchmark_registry"]) != gates["available_benchmark_count"]:
        errors.append("AVAILABLE_BENCHMARK")
    if len(records["benchmark_relative_rows"]) != gates["benchmark_relative_observation_count"]:
        errors.append("BENCHMARK_RELATIVE_COUNT")
    if len(shards) != gates["logical_shard_count"]:
        errors.append("SHARD_COUNT")
    if any(row["data_grade"] != "NON_DECISION_GRADE_FALLBACK" for row in records["benchmark_relative_rows"]):
        errors.append("BENCHMARK_DATA_GRADE")
    if errors:
        quality["quality_status"] = "FAIL"
        quality["errors"] = errors
    write_json(candidate_root / "FMDL6X3D_QUALITY_REPORT.json", quality)
    if errors:
        raise RuntimeError("QUALITY_ERRORS:" + ",".join(errors))

    decision = {
        "phase_id": PHASE_ID,
        "status": EXIT_STATUS,
        "release_id": release_id,
        "release_sequence": 39,
        "accepted_at": accepted_at,
        "source_commit": source_commit,
        "input_release_id": contract["input_contract"]["input_release_id"],
        "next_gate": NEXT_GATE,
        "framework_status": "PARTIAL_OFFICIAL_SEC_SIC_CLASSIFICATION_WITH_EXPLICIT_PEER_AND_BENCHMARK_GAPS",
        "official_sec_sic_classified_security_count": official_count,
        "formal_peer_group_count": 0,
        "available_benchmark_count": 1,
        "benchmark_relative_observation_count": len(records["benchmark_relative_rows"]),
        "sector_neutral_factor_count": 0,
        "global_factor_score_count": 0,
        "research_production_gate": "OPEN_FOR_FMDL6X3E_RESEARCH_CARDS_AND_BENCHMARK_POOL_WITH_PARTIAL_COMPARABILITY",
        "investment_os_candidate_pool_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X3D",
        "simulation_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X3D",
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    write_json(candidate_root / "FMDL6X3D_DECISION.json", decision)
    source_binding = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "input_manifest_sha256": {"readiness": readiness_manifest_sha, "factor_engine": factor_manifest_sha},
        "sic_evidence_sha256": sic_evidence_sha,
        "benchmark_evidence_sha256": benchmark_evidence_sha,
        "sic_authority": "SEC_OFFICIAL",
        "sector_industry_crosswalk_authority": "INTERNAL_SEC_SIC_CROSSWALK_V1_NOT_GICS_OR_ICB",
        "benchmark_identity_authority": "NASDAQ_AND_INVESCO_OFFICIAL",
        "benchmark_market_data_grade": "NON_DECISION_GRADE_FALLBACK",
        "neutral_fill_used": False,
        "silent_source_substitution": False,
        "formal_peer_rank_emitted": False,
        "sector_neutral_factor_emitted": False,
        "global_factor_score_emitted": False,
    }
    write_json(candidate_root / "FMDL6X3D_SOURCE_BINDING.json", source_binding)

    manifest_files: dict[str, Any] = {}
    for path in sorted(candidate_root.iterdir()):
        if path.name == "FMDL6X3D_MANIFEST.json" or not path.is_file():
            continue
        manifest_files[path.name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    manifest = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": 39,
        "generated_at": accepted_at,
        "contract_sha256": contract_sha,
        "input_manifest_sha256": {"readiness": readiness_manifest_sha, "factor_engine": factor_manifest_sha},
        "evidence_sha256": {"sic": sic_evidence_sha, "benchmark": benchmark_evidence_sha},
        "files": manifest_files,
        "shards": shards,
    }
    write_json(candidate_root / "FMDL6X3D_MANIFEST.json", manifest)
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
    manifest = load_json(candidate_root / "FMDL6X3D_MANIFEST.json")
    for name, meta in manifest["files"].items():
        path = candidate_root / name
        if not path.is_file() or path.stat().st_size != meta["bytes"] or sha256_file(path) != meta["sha256"]:
            errors.append("MANIFEST_FILE:" + name)
    decision = load_json(candidate_root / "FMDL6X3D_DECISION.json")
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
    decision = load_json(candidate_root / "FMDL6X3D_DECISION.json")
    release_id = decision["release_id"]
    current = repo_root / contract["storage_contract"]["current_root"]
    release = repo_root / contract["storage_contract"]["release_root"].replace("<release_id>", release_id)
    normalized = repo_root / contract["storage_contract"]["normalized_root"].replace("<release_id>", release_id)
    archive_root = repo_root / contract["storage_contract"]["archive_root"]
    if release.exists():
        raise RuntimeError("IMMUTABLE_RELEASE_COLLISION")
    if current.exists():
        archive = archive_root / f"sector_peer_benchmark_{published_at.replace(':', '').replace('-', '')}"
        copytree_replace(current, archive)
    copytree_replace(candidate_root, current)
    copytree_replace(candidate_root, release)
    copytree_replace(candidate_root, normalized)
    manifest_sha = sha256_file(current / "FMDL6X3D_MANIFEST.json")
    pointer = {
        "phase_id": PHASE_ID,
        "status": EXIT_STATUS,
        "release_id": release_id,
        "release_sequence": 39,
        "published_at": published_at,
        "source_commit": source_commit,
        "current_path": str(current.relative_to(repo_root)),
        "release_path": str(release.relative_to(repo_root)),
        "normalized_path": str(normalized.relative_to(repo_root)),
        "manifest_sha256": manifest_sha,
        "framework_status": decision["framework_status"],
        "official_sec_sic_classified_security_count": decision["official_sec_sic_classified_security_count"],
        "formal_peer_group_count": 0,
        "available_benchmark_count": 1,
        "benchmark_relative_observation_count": decision["benchmark_relative_observation_count"],
        "sector_neutral_factor_count": 0,
        "global_factor_score_count": 0,
        "next_gate": NEXT_GATE,
        "research_production_gate": decision["research_production_gate"],
        "investment_os_candidate_pool_gate": decision["investment_os_candidate_pool_gate"],
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    write_json(repo_root / contract["storage_contract"]["last_success"], pointer)
    lkg = {**pointer, "lkg_scope": "FMDL6X3_SECTOR_INDUSTRY_PEER_AND_BENCHMARK_DOMAIN", "lkg_reason": "LATEST_ACCEPTED_FRAMEWORK_WITH_EXPLICIT_CLASSIFICATION_PEER_AND_BENCHMARK_BOUNDARIES"}
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
