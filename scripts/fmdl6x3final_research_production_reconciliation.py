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

PHASE_ID = "FMDL-6X3-FINAL"
EXIT_STATUS = "FMDL6X3_FINAL_RESEARCH_PRODUCTION_RECONCILIATION_AND_OPERATIONAL_ACCEPTANCE_ACCEPTED"
NEXT_GATE = "FMDL-6X4-A_PUBLIC_EQUITY_INVESTING_ADAPTER_AND_CONTRACT_MAPPING"
CONTRACT_PATH = Path("config/fmdl6x3final_research_production_reconciliation_contract.json")
LKG_PATHS = {
    "FMDL-6X3-A": Path("outputs/status/FMDL6X3_RESEARCH_UNIVERSE_LKG.json"),
    "FMDL-6X3-B": Path("outputs/status/FMDL6X3_FINANCIAL_NORMALIZATION_LKG.json"),
    "FMDL-6X3-C": Path("outputs/status/FMDL6X3_FACTOR_ENGINE_LKG.json"),
    "FMDL-6X3-D": Path("outputs/status/FMDL6X3_SECTOR_PEER_BENCHMARK_LKG.json"),
    "FMDL-6X3-E": Path("outputs/status/FMDL6X3_SCREENING_RESEARCH_CARDS_LKG.json"),
}


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(stable_json(row) + "\n" for row in rows).encode("utf-8")


def input_paths(repo_root: Path, spec: dict[str, Any]) -> dict[str, Path]:
    current = repo_root / spec["current_root"]
    pointer_path = repo_root / spec["pointer_path"]
    pointer = load_json(pointer_path)
    release = repo_root / pointer["release_path"]
    return {
        "current": current,
        "release": release,
        "pointer": pointer_path,
        "current_manifest": current / spec["manifest_name"],
        "release_manifest": release / spec["manifest_name"],
        "current_decision": current / spec["decision_name"],
        "release_decision": release / spec["decision_name"],
    }


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
    if contract.get("next_gate") != NEXT_GATE:
        errors.append("NEXT_GATE")
    if contract.get("storage_contract", {}).get("release_sequence") != 41:
        errors.append("RELEASE_SEQUENCE")
    if contract.get("reconciliation_contract", {}).get("required_release_sequences") != [36, 37, 38, 39, 40]:
        errors.append("INPUT_RELEASE_SEQUENCES")
    expected_phases = ["FMDL-6X3-A", "FMDL-6X3-B", "FMDL-6X3-C", "FMDL-6X3-D", "FMDL-6X3-E"]
    if list(contract.get("input_releases", {})) != expected_phases:
        errors.append("INPUT_DOMAIN_ORDER")
    for phase, spec in contract.get("input_releases", {}).items():
        pointer_path = repo_root / spec["pointer_path"]
        if not pointer_path.is_file():
            errors.append("POINTER_MISSING:" + phase)
            continue
        pointer = load_json(pointer_path)
        if pointer.get("phase_id") != phase:
            errors.append("POINTER_PHASE:" + phase)
        if pointer.get("release_id") != spec["release_id"]:
            errors.append("POINTER_RELEASE:" + phase)
        if pointer.get("release_sequence") != spec["release_sequence"]:
            errors.append("POINTER_SEQUENCE:" + phase)
        if pointer.get("trade_authority") != "NONE":
            errors.append("POINTER_TRADE_AUTHORITY:" + phase)
        paths = input_paths(repo_root, spec)
        for name in ("current_manifest", "release_manifest", "current_decision", "release_decision"):
            if not paths[name].is_file():
                errors.append("INPUT_FILE_MISSING:" + phase + ":" + name)
        if not (repo_root / LKG_PATHS[phase]).is_file():
            errors.append("LKG_MISSING:" + phase)
    if set(contract.get("zero_mutation_gate", {}).values()) != {0}:
        errors.append("ZERO_MUTATION_GATE")
    checks.extend([
        "CONTRACT_SHAPE",
        "STRICT_RELEASE_SEQUENCE",
        "LAST_SUCCESS_POINTERS",
        "DOMAIN_LKG_POINTERS",
        "CURRENT_RELEASE_FILES",
        "ZERO_MUTATION_GATE",
    ])
    return checks, sorted(errors)


def read_inputs(repo_root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    domains: dict[str, Any] = {}
    for phase, spec in contract["input_releases"].items():
        paths = input_paths(repo_root, spec)
        domains[phase] = {
            "spec": spec,
            "paths": paths,
            "pointer": load_json(paths["pointer"]),
            "lkg": load_json(repo_root / LKG_PATHS[phase]),
        }
    a = repo_root / contract["input_releases"]["FMDL-6X3-A"]["current_root"]
    b = repo_root / contract["input_releases"]["FMDL-6X3-B"]["current_root"]
    c = repo_root / contract["input_releases"]["FMDL-6X3-C"]["current_root"]
    d = repo_root / contract["input_releases"]["FMDL-6X3-D"]["current_root"]
    e = repo_root / contract["input_releases"]["FMDL-6X3-E"]["current_root"]
    domains["records"] = {
        "a_security": read_zip_jsonl(a / "FMDL6X3A_READINESS_SHARDS.zip", "SECURITY_READINESS/"),
        "a_issuer": read_zip_jsonl(a / "FMDL6X3A_READINESS_SHARDS.zip", "ISSUER_READINESS/"),
        "b_period": load_json(b / "FMDL6X3B_PERIOD_READINESS.json"),
        "c_status": read_zip_jsonl(c / "FMDL6X3C_FACTOR_SHARDS.zip", "SECURITY_FACTOR_STATUS/"),
        "c_quality": read_zip_jsonl(c / "FMDL6X3C_FACTOR_SHARDS.zip", "QUALITY_FACTOR/"),
        "c_market": read_zip_jsonl(c / "FMDL6X3C_FACTOR_SHARDS.zip", "MARKET_FACTOR/"),
        "c_risk": read_zip_jsonl(c / "FMDL6X3C_FACTOR_SHARDS.zip", "RISK_FACTOR/"),
        "c_valuation": read_zip_jsonl(c / "FMDL6X3C_FACTOR_SHARDS.zip", "VALUATION_FACTOR/"),
        "d_classification": read_zip_jsonl(d / "FMDL6X3D_FRAMEWORK_SHARDS.zip", "SECURITY_CLASSIFICATION_STATUS/"),
        "d_peer": read_zip_jsonl(d / "FMDL6X3D_FRAMEWORK_SHARDS.zip", "PEER_GROUP_MEMBERSHIP/"),
        "e_screening": read_zip_jsonl(e / "FMDL6X3E_RESEARCH_SHARDS.zip", "SCREENING_STATUS/"),
        "e_cards": read_zip_jsonl(e / "FMDL6X3E_RESEARCH_SHARDS.zip", "RESEARCH_CARD/"),
        "e_pool": read_zip_jsonl(e / "FMDL6X3E_RESEARCH_SHARDS.zip", "BENCHMARK_POOL_MEMBERSHIP/"),
    }
    return domains


def id_set(rows: list[dict[str, Any]], key: str = "canonical_security_id") -> set[str]:
    return {str(row[key]) for row in rows}


def reconcile(inputs: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    domain_rows: list[dict[str, Any]] = []
    for phase in contract["input_releases"]:
        domain = inputs[phase]
        paths = domain["paths"]
        pointer = domain["pointer"]
        lkg = domain["lkg"]
        manifest_sha = sha256_file(paths["current_manifest"])
        manifest_parity = paths["current_manifest"].read_bytes() == paths["release_manifest"].read_bytes()
        decision_parity = paths["current_decision"].read_bytes() == paths["release_decision"].read_bytes()
        pointer_binding = pointer.get("manifest_sha256") == manifest_sha
        lkg_binding = lkg.get("release_id") == pointer.get("release_id") and lkg.get("manifest_sha256") == manifest_sha
        if not manifest_parity:
            errors.append("MANIFEST_PARITY:" + phase)
        if not decision_parity:
            errors.append("DECISION_PARITY:" + phase)
        if not pointer_binding:
            errors.append("POINTER_MANIFEST_BINDING:" + phase)
        if not lkg_binding:
            errors.append("LKG_BINDING:" + phase)
        domain_rows.append({
            "phase_id": phase,
            "release_id": pointer["release_id"],
            "release_sequence": pointer["release_sequence"],
            "status": pointer["status"],
            "manifest_sha256": manifest_sha,
            "current_release_manifest_parity": manifest_parity,
            "current_release_decision_parity": decision_parity,
            "last_success_manifest_binding": pointer_binding,
            "lkg_binding": lkg_binding,
            "trade_authority": pointer.get("trade_authority"),
            "zero_mutation_proof": pointer.get("zero_mutation_proof"),
            "quality_status": "PASS" if all((manifest_parity, decision_parity, pointer_binding, lkg_binding)) else "FAIL",
        })

    rows = inputs["records"]
    a_ids = id_set(rows["a_security"])
    c_ids = id_set(rows["c_status"])
    d_ids = id_set(rows["d_classification"])
    e_screen_ids = id_set(rows["e_screening"])
    e_card_ids = id_set(rows["e_cards"])
    expected = contract["reconciliation_contract"]["security_universe_count"]
    if not (len(a_ids) == len(c_ids) == len(d_ids) == len(e_screen_ids) == len(e_card_ids) == expected):
        errors.append("SECURITY_UNIVERSE_COUNTS")
    if not (a_ids == c_ids == d_ids == e_screen_ids == e_card_ids):
        errors.append("SECURITY_UNIVERSE_IDENTITY")
    issuer_count = len(id_set(rows["a_issuer"], "canonical_issuer_id"))
    if issuer_count != contract["reconciliation_contract"]["issuer_universe_count"]:
        errors.append("ISSUER_UNIVERSE_COUNT")

    b_ids = id_set(rows["b_period"])
    quality_ids = id_set(rows["c_quality"])
    screening_by_id = {row["canonical_security_id"]: row for row in rows["e_screening"]}
    core_ids = {sid for sid, row in screening_by_id.items() if row["screening_disposition"] == "CORE_RESEARCH_SANDBOX"}
    watch_ids = {sid for sid, row in screening_by_id.items() if row["screening_disposition"] == "OFFICIAL_FILING_WATCH"}
    sic_ids = {row["canonical_security_id"] for row in rows["d_classification"] if row["classification_status"] == "OFFICIAL_SEC_SIC_LINKED_INTERNAL_CROSSWALK"}
    pool_ids = id_set(rows["e_pool"])
    if not (b_ids == quality_ids == core_ids and len(b_ids) == 3):
        errors.append("FINANCIAL_QUALITY_CORE_IDENTITY")
    if not (sic_ids == core_ids | watch_ids and len(sic_ids) == 6):
        errors.append("SIC_CORE_WATCH_IDENTITY")
    if len(pool_ids) != 7 or not sic_ids <= pool_ids:
        errors.append("BENCHMARK_POOL_IDENTITY")

    market_count = len(id_set(rows["c_market"]))
    risk_count = len(id_set(rows["c_risk"]))
    if market_count != 63 or risk_count != 63:
        errors.append("MARKET_RISK_SECURITY_COUNT")
    if rows["c_valuation"]:
        errors.append("VALUATION_NOT_ZERO")
    formal_peer_groups = {row.get("peer_group_id") for row in rows["d_peer"] if row.get("peer_group_status") == "FORMAL_PEER_GROUP"}
    if formal_peer_groups:
        errors.append("FORMAL_PEER_NOT_ZERO")
    if any(row.get("formal_candidate_pool_member") for row in rows["e_pool"]):
        errors.append("POOL_CANDIDATE_MUTATION")
    if any(row.get("investment_recommendation") for row in rows["e_pool"]):
        errors.append("POOL_RECOMMENDATION")

    disposition_counts = Counter(row["screening_disposition"] for row in rows["e_screening"])
    expected_dispositions = {
        "BENCHMARK_REFERENCE": 1,
        "CORE_RESEARCH_SANDBOX": 3,
        "DATA_BACKFILL_PENDING": 5428,
        "EXCLUDED": 1273,
        "INSTRUMENT_REVIEW_REQUIRED": 437,
        "MARKET_RISK_SANDBOX_OBSERVATION": 39,
        "OFFICIAL_FILING_WATCH": 3,
        "REFERENCE_ONLY": 1601,
    }
    if dict(sorted(disposition_counts.items())) != expected_dispositions:
        errors.append("SCREENING_DISPOSITION_COUNTS")

    factor_by_id = {row["canonical_security_id"]: row for row in rows["c_status"]}
    class_by_id = {row["canonical_security_id"]: row for row in rows["d_classification"]}
    card_by_id = {row["canonical_security_id"]: row for row in rows["e_cards"]}
    reconciliation_rows: list[dict[str, Any]] = []
    for readiness in sorted(rows["a_security"], key=lambda row: row["canonical_security_id"]):
        sid = readiness["canonical_security_id"]
        reconciliation_rows.append({
            "canonical_security_id": sid,
            "canonical_issuer_id": readiness["canonical_issuer_id"],
            "symbol": readiness["symbol"],
            "research_profile": readiness["research_profile"],
            "research_scope": readiness["research_scope"],
            "readiness_tier": readiness["readiness_tier"],
            "factor_status": factor_by_id[sid].get("factor_status"),
            "classification_status": class_by_id[sid].get("classification_status"),
            "screening_disposition": screening_by_id[sid]["screening_disposition"],
            "research_card_id": card_by_id[sid]["research_card_id"],
            "research_card_present": True,
            "benchmark_pool_member": sid in pool_ids,
            "formal_candidate_pool_member": False,
            "investment_recommendation": False,
            "candidate_pool_status": "NOT_AUTHORIZED",
            "trade_authority": "NONE",
            "reconciliation_status": "PASS",
        })

    gates = [
        ("RELEASE_SEQUENCE_CONTINUITY", 5, "PASS"),
        ("CURRENT_RELEASE_BYTE_PARITY", 5, "PASS"),
        ("LAST_SUCCESS_MANIFEST_BINDING", 5, "PASS"),
        ("DOMAIN_LKG_RECOVERY", 5, "PASS"),
        ("SECURITY_UNIVERSE_RECONCILIATION", len(a_ids), "PASS"),
        ("ISSUER_UNIVERSE_RECONCILIATION", issuer_count, "PASS"),
        ("FINANCIAL_QUALITY_CORE_RECONCILIATION", len(core_ids), "PASS"),
        ("OFFICIAL_CLASSIFICATION_WATCH_RECONCILIATION", len(sic_ids), "PASS"),
        ("MARKET_RISK_SANDBOX_BOUNDARY", market_count, "PASS"),
        ("VALUATION_GATE", 0, "BLOCKED_ACCEPTED"),
        ("FORMAL_PEER_GATE", 0, "BLOCKED_ACCEPTED"),
        ("GLOBAL_RANK_GATE", 0, "BLOCKED_ACCEPTED"),
        ("US_RESEARCH_BENCHMARK_POOL", len(pool_ids), "RESEARCH_ONLY_ACCEPTED"),
        ("INVESTMENT_OS_CANDIDATE_PROMOTION", 0, "CLOSED_ACCEPTED"),
        ("SIMULATION_GATE", 0, "CLOSED_ACCEPTED"),
        ("BROKERAGE_GATE", 0, "CLOSED_NO_CHANNEL"),
    ]
    gate_rows = [{
        "gate_id": "USX3FINAL-" + record_hash("FMDL6X3FINAL_GATE", name)[:24],
        "gate_name": name,
        "observed_count": count,
        "gate_status": status,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    } for name, count, status in gates]
    return {
        "domain_rows": sorted(domain_rows, key=lambda row: row["release_sequence"]),
        "reconciliation_rows": reconciliation_rows,
        "gate_rows": gate_rows,
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "core_ids": sorted(core_ids),
        "watch_ids": sorted(watch_ids),
        "sic_ids": sorted(sic_ids),
        "pool_ids": sorted(pool_ids),
        "issuer_count": issuer_count,
        "market_count": market_count,
        "errors": sorted(errors),
    }


def build_shards(records: dict[str, Any], generated_at: str, bucket_count: int = 64) -> tuple[bytes, list[dict[str, Any]]]:
    entries: dict[str, bytes] = {}
    manifest: list[dict[str, Any]] = []
    domains = (
        ("SECURITY_RESEARCH_RECONCILIATION", records["reconciliation_rows"], "canonical_security_id"),
        ("OPERATIONAL_ACCEPTANCE_GATE", records["gate_rows"], "gate_id"),
    )
    for domain, rows, key in domains:
        for index in range(bucket_count):
            bucket = f"{index:02X}"
            shard = [row for row in rows if bucket_hex(str(row[key]), bucket_count) == bucket]
            shard.sort(key=lambda row: (str(row[key]), stable_json(row)))
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


def build_candidate(repo_root: Path, candidate_root: Path, accepted_at: str, source_commit: str) -> dict[str, Any]:
    checks, contract_errors = validate_contract(repo_root)
    if contract_errors:
        raise RuntimeError("CONTRACT_ERRORS:" + ",".join(contract_errors))
    contract = load_json(repo_root / CONTRACT_PATH)
    inputs = read_inputs(repo_root, contract)
    records = reconcile(inputs, contract)
    if records["errors"]:
        raise RuntimeError("RECONCILIATION_ERRORS:" + ",".join(records["errors"]))
    candidate_root.mkdir(parents=True, exist_ok=True)
    contract_sha = sha256_file(repo_root / CONTRACT_PATH)
    input_hashes = {phase: sha256_file(inputs[phase]["paths"]["current_manifest"]) for phase in contract["input_releases"]}
    fingerprint = record_hash("FMDL6X3FINAL_RELEASE", contract_sha, *[input_hashes[p] for p in sorted(input_hashes)])
    release_id = f"FMDL6X3FINAL_20260723_{fingerprint[:12]}"
    shard_zip, shards = build_shards(records, accepted_at)
    (candidate_root / "FMDL6X3FINAL_RECONCILIATION_SHARDS.zip").write_bytes(shard_zip)
    write_json(candidate_root / "FMDL6X3FINAL_DOMAIN_REGISTRY.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "domain_count": len(records["domain_rows"]),
        "domains": records["domain_rows"],
    })
    write_json(candidate_root / "FMDL6X3FINAL_OPERATIONAL_GATES.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "gate_count": len(records["gate_rows"]),
        "gates": records["gate_rows"],
    })
    coverage = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "security_universe_count": len(records["reconciliation_rows"]),
        "issuer_universe_count": records["issuer_count"],
        "quarterly_financial_security_count": len(records["core_ids"]),
        "quality_sandbox_security_count": len(records["core_ids"]),
        "market_risk_sandbox_security_count": records["market_count"],
        "official_sic_security_count": len(records["sic_ids"]),
        "research_card_count": len(records["reconciliation_rows"]),
        "benchmark_pool_member_count": len(records["pool_ids"]),
        "formal_peer_group_count": 0,
        "valuation_ready_security_count": 0,
        "global_rank_count": 0,
        "formal_candidate_promotion_count": 0,
        "research_recommendation_count": 0,
        "global_full_data_completion_claimed": False,
        "formal_investment_ranking_claimed": False,
        "fmdl6x3_architecture_operationally_complete": True,
    }
    write_json(candidate_root / "FMDL6X3FINAL_COVERAGE_BOUNDARY.json", coverage)
    write_json(candidate_root / "FMDL6X3FINAL_SCREENING_RECONCILIATION.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "disposition_counts": records["disposition_counts"],
        "core_research_security_ids": records["core_ids"],
        "official_filing_watch_security_ids": records["watch_ids"],
        "official_sic_security_ids": records["sic_ids"],
        "benchmark_pool_security_ids": records["pool_ids"],
        "formal_candidate_promotion_count": 0,
    })
    write_json(candidate_root / "FMDL6X3FINAL_FMDL6X4A_HANDOFF.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "handoff_status": "OPEN_FOR_FMDL6X4A_ADAPTER_DEVELOPMENT_ONLY",
        "next_gate": NEXT_GATE,
        "accepted_input_release_ids": {phase: spec["release_id"] for phase, spec in contract["input_releases"].items()},
        "us_research_benchmark_pool_id": "US_RESEARCH_BENCHMARK_POOL_V1",
        "prohibited_interpretations": [
            "BENCHMARK_POOL_IS_NOT_INVESTMENT_OS_CANDIDATE_POOL",
            "RESEARCH_CARD_IS_NOT_INVESTMENT_RECOMMENDATION",
            "NON_DECISION_GRADE_MARKET_DATA_IS_NOT_TRADE_SIGNAL",
            "QUARTERLY_QUALITY_SANDBOX_IS_NOT_FORMAL_GLOBAL_RANK"
        ],
        "candidate_pool_authorized": False,
        "simulation_authorized": False,
        "brokerage_channel_available": False,
        "trade_authority": "NONE",
    })
    quality = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "quality_status": "PASS",
        "domain_count": len(records["domain_rows"]),
        "accepted_domain_count": sum(row["quality_status"] == "PASS" for row in records["domain_rows"]),
        "security_universe_expected": 8785,
        "security_universe_actual": len(records["reconciliation_rows"]),
        "research_card_count": len(records["reconciliation_rows"]),
        "benchmark_pool_member_count": len(records["pool_ids"]),
        "operational_gate_count": len(records["gate_rows"]),
        "formal_peer_group_count": 0,
        "valuation_ready_security_count": 0,
        "global_rank_count": 0,
        "formal_candidate_promotion_count": 0,
        "research_recommendation_count": 0,
        "neutral_fill_count": 0,
        "expected_shard_count": 128,
        "manifested_shard_count": len(shards),
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    if not (quality["accepted_domain_count"] == 5 and quality["security_universe_actual"] == 8785 and quality["research_card_count"] == 8785 and quality["benchmark_pool_member_count"] == 7 and quality["manifested_shard_count"] == 128):
        quality["quality_status"] = "FAIL"
        quality["errors"] = ["FINAL_ACCEPTANCE_COUNTS"]
    write_json(candidate_root / "FMDL6X3FINAL_QUALITY_REPORT.json", quality)
    if quality["quality_status"] != "PASS":
        raise RuntimeError("QUALITY_ERRORS:FINAL_ACCEPTANCE_COUNTS")
    write_json(candidate_root / "FMDL6X3FINAL_SOURCE_BINDING.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "contract_sha256": contract_sha,
        "input_manifest_sha256": input_hashes,
        "financial_source_grade": "DECISION_GRADE_OFFICIAL_SEC_DERIVED_WHERE_AVAILABLE",
        "classification_authority": "SEC_OFFICIAL_WITH_INTERNAL_SEC_SIC_CROSSWALK",
        "market_source_grade": "NON_DECISION_GRADE_FALLBACK",
        "benchmark_pool_is_candidate_pool": False,
        "neutral_fill_used": False,
        "silent_source_substitution": False,
        "formal_rank_emitted": False,
        "investment_recommendation_emitted": False,
        "formal_candidate_promotion_emitted": False,
    })
    decision = {
        "phase_id": PHASE_ID,
        "status": EXIT_STATUS,
        "release_id": release_id,
        "release_sequence": 41,
        "accepted_at": accepted_at,
        "source_commit": source_commit,
        "input_release_ids": {phase: spec["release_id"] for phase, spec in contract["input_releases"].items()},
        "next_gate": NEXT_GATE,
        "research_production_status": "FMDL6X3_ARCHITECTURE_OPERATIONALLY_COMPLETE_WITH_EXPLICIT_DATA_AND_DECISION_BOUNDARIES",
        "security_universe_count": 8785,
        "research_card_count": 8785,
        "benchmark_pool_member_count": 7,
        "formal_candidate_promotion_count": 0,
        "global_rank_count": 0,
        "research_recommendation_count": 0,
        "fmdl6x4a_gate": "OPEN_ADAPTER_AND_CONTRACT_MAPPING_ONLY",
        "investment_os_candidate_pool_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X3_FINAL",
        "simulation_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X3_FINAL",
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    write_json(candidate_root / "FMDL6X3FINAL_DECISION.json", decision)
    files: dict[str, Any] = {}
    for path in sorted(candidate_root.iterdir()):
        if path.name != "FMDL6X3FINAL_MANIFEST.json" and path.is_file():
            files[path.name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    write_json(candidate_root / "FMDL6X3FINAL_MANIFEST.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": 41,
        "generated_at": accepted_at,
        "contract_sha256": contract_sha,
        "input_manifest_sha256": input_hashes,
        "files": files,
        "shards": shards,
    })
    return {"decision": decision, "quality": quality, "coverage": coverage, "contract_checks": checks}


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
    manifest = load_json(candidate_root / "FMDL6X3FINAL_MANIFEST.json")
    for name, meta in manifest["files"].items():
        path = candidate_root / name
        if not path.is_file() or path.stat().st_size != meta["bytes"] or sha256_file(path) != meta["sha256"]:
            errors.append("MANIFEST_FILE:" + name)
    decision = load_json(candidate_root / "FMDL6X3FINAL_DECISION.json")
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
    decision = load_json(candidate_root / "FMDL6X3FINAL_DECISION.json")
    release_id = decision["release_id"]
    current = repo_root / contract["storage_contract"]["current_root"]
    release = repo_root / contract["storage_contract"]["release_root"].replace("<release_id>", release_id)
    normalized = repo_root / contract["storage_contract"]["normalized_root"].replace("<release_id>", release_id)
    archive_root = repo_root / contract["storage_contract"]["archive_root"]
    if release.exists():
        raise RuntimeError("IMMUTABLE_RELEASE_COLLISION")
    if current.exists():
        archive = archive_root / f"research_production_final_{published_at.replace(':', '').replace('-', '')}"
        copytree_replace(current, archive)
    copytree_replace(candidate_root, current)
    copytree_replace(candidate_root, release)
    copytree_replace(candidate_root, normalized)
    manifest_sha = sha256_file(current / "FMDL6X3FINAL_MANIFEST.json")
    pointer = {
        "phase_id": PHASE_ID,
        "status": EXIT_STATUS,
        "release_id": release_id,
        "release_sequence": 41,
        "published_at": published_at,
        "source_commit": source_commit,
        "current_path": str(current.relative_to(repo_root)),
        "release_path": str(release.relative_to(repo_root)),
        "normalized_path": str(normalized.relative_to(repo_root)),
        "manifest_sha256": manifest_sha,
        "research_production_status": decision["research_production_status"],
        "security_universe_count": 8785,
        "research_card_count": 8785,
        "benchmark_pool_member_count": 7,
        "formal_candidate_promotion_count": 0,
        "global_rank_count": 0,
        "next_gate": NEXT_GATE,
        "fmdl6x4a_gate": decision["fmdl6x4a_gate"],
        "investment_os_candidate_pool_gate": decision["investment_os_candidate_pool_gate"],
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL",
        "trade_authority": "NONE",
        "zero_mutation_proof": contract["zero_mutation_gate"],
    }
    write_json(repo_root / contract["storage_contract"]["last_success"], pointer)
    write_json(repo_root / contract["storage_contract"]["last_known_good"], {
        **pointer,
        "lkg_scope": "FMDL6X3_RESEARCH_PRODUCTION_FINAL_DOMAIN",
        "lkg_reason": "LATEST_ACCEPTED_RESEARCH_PRODUCTION_BASELINE_WITH_EXPLICIT_DATA_AND_DECISION_BOUNDARIES",
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
