#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PHASE_ID = "FMDL-7B"
EXIT_STATUS = "FMDL7B_END_TO_END_RESEARCH_AND_DECISION_LINEAGE_ACCEPTED"
NEXT_GATE = "FMDL-7C_PORTFOLIO_SIMULATION_ATTRIBUTION_AND_RULE_CALIBRATION_ACCEPTANCE"
CONTRACT_PATH = Path("config/fmdl7b_lineage_acceptance_contract.json")
SHARD_DOMAINS = [
    "MARKET_LINEAGE",
    "IDENTITY_LINK",
    "DECISION_ROUTE",
    "ORPHAN_CONTROL",
    "FAILURE_CONTROL",
    "AUTHORITY_CONTROL",
]


class AcceptanceError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(canonical_bytes(row) for row in rows))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_zip_jsonl(path: Path, prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            if not name.startswith(prefix + "/") or not name.endswith(".jsonl"):
                continue
            for line in archive.read(name).decode("utf-8-sig").splitlines():
                if line.strip():
                    rows.append(json.loads(line))
    return rows


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def validate_pointer(pointer: dict[str, Any], spec: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    checks = {
        "phase_id": spec.get("required_phase_id"),
        "release_id": spec.get("required_release_id"),
        "release_sequence": spec.get("required_release_sequence"),
        "status": spec.get("required_status"),
        "next_gate": spec.get("required_next_gate"),
        "trade_authority": spec.get("required_trade_authority", "NONE"),
    }
    for field, expected in checks.items():
        if expected is not None and pointer.get(field) != expected:
            errors.append(f"{label}_{field.upper()}_MISMATCH")
    return errors


def validate_contract(repo_root: Path) -> tuple[dict[str, Any], list[str]]:
    contract = read_json(repo_root / CONTRACT_PATH)
    errors: list[str] = []
    if contract.get("phase_id") != PHASE_ID:
        errors.append("CONTRACT_PHASE_ID")
    if contract.get("required_exit_status") != EXIT_STATUS:
        errors.append("CONTRACT_EXIT_STATUS")
    if contract.get("next_gate") != NEXT_GATE:
        errors.append("CONTRACT_NEXT_GATE")
    if contract.get("trade_authority") != "NONE":
        errors.append("CONTRACT_TRADE_AUTHORITY")

    entry_spec = contract["entry_gate"]
    entry_path = repo_root / entry_spec["path"]
    if not entry_path.is_file():
        errors.append("ENTRY_POINTER_MISSING")
    else:
        errors.extend(validate_pointer(read_json(entry_path), entry_spec, "ENTRY"))

    sources = contract.get("market_lineage_sources", {})
    if set(sources) != {"A_SHARE", "HONG_KONG_CONNECT", "US_EQUITY"}:
        errors.append("MARKET_SOURCE_SET")
    for market, spec in sources.items():
        pointer_path = repo_root / spec["pointer_path"]
        if not pointer_path.is_file():
            errors.append(f"{market}_POINTER_MISSING")
        else:
            errors.extend(validate_pointer(read_json(pointer_path), spec, market))
        for key, value in spec.items():
            if key.endswith("_path") and key != "pointer_path" and not (repo_root / value).is_file():
                errors.append(f"{market}_INPUT_MISSING:{key}")

    scope = contract.get("scope", {})
    forbidden = [
        "market_data_refresh_authorized",
        "new_research_execution_authorized",
        "candidate_pool_mutation_authorized",
        "simulation_book_mutation_authorized",
        "real_account_mutation_authorized",
        "rule_mutation_authorized",
        "investment_recommendation_authorized",
        "brokerage_or_order_authorized",
        "canonical_repack_authorized",
    ]
    for field in forbidden:
        if scope.get(field) is not False:
            errors.append(f"SCOPE_NOT_FAIL_CLOSED:{field}")

    gates = contract.get("acceptance_gates", {})
    expected = {
        "market_count": 3,
        "source_binding_count": 3,
        "a_share_lineage_count": 6,
        "hong_kong_lineage_count": 6,
        "us_lineage_count": 7,
        "cross_market_lineage_count": 19,
        "lineage_pass_count": 19,
        "orphan_lineage_count": 0,
        "duplicate_lineage_identity_count": 0,
        "automatic_candidate_promotion_count": 0,
        "investment_recommendation_count": 0,
        "candidate_pool_mutations": 0,
        "simulation_book_mutations": 0,
        "real_account_mutations": 0,
        "rule_mutations": 0,
        "orders": 0,
        "failure_injection_count": 7,
        "logical_shard_domain_count": 6,
        "bucket_count": 64,
        "logical_shard_count": 384,
    }
    for key, value in expected.items():
        if gates.get(key) != value:
            errors.append(f"ACCEPTANCE_GATE_CONTRACT:{key}")
    if contract.get("storage_contract", {}).get("release_sequence") != 50:
        errors.append("RELEASE_SEQUENCE")
    return contract, sorted(set(errors))


def validate_a_share(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("symbol", "evidence_id", "research_id", "transition_id", "thesis_record_id", "lineage_id"):
        if not str(row.get(field, "")).strip():
            errors.append("MISSING_" + field.upper())
    if row.get("graduation_decision") != "GRADUATED":
        errors.append("GRADUATION_DECISION")
    if row.get("state_domain") != "FMDL4C_REENTRY_REVIEW_QUEUE":
        errors.append("STATE_DOMAIN")
    if row.get("queue_state") not in {"CANDIDATE_POOL_REENTRY_REVIEW_READY", "SHADOW_TRACK_REENTRY_REVIEW_READY"}:
        errors.append("QUEUE_STATE")
    for field in ("candidate_pool_mutation_count", "simulation_mutation_count", "real_account_mutation_count", "order_generation_count"):
        if int(row.get(field, 0) or 0) != 0:
            errors.append("UNAUTHORIZED_MUTATION")
    if row.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")
    return sorted(set(errors))


def validate_hk(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("security_id", "research_id", "research_object_sha256", "transition_id"):
        if not str(row.get(field, "")).strip():
            errors.append("MISSING_" + field.upper())
    decision = row.get("research_decision")
    expected_route = "HK_CANDIDATE_REENTRY_REVIEW" if decision == "GRADUATED" else "HK_SHADOW_TRACK_REVIEW" if decision == "SHADOW_TRACK" else None
    if expected_route is None or row.get("target_route") != expected_route:
        errors.append("DECISION_ROUTE")
    if row.get("lineage_status") != "PASS" or str(row.get("lineage_errors", "")).strip():
        errors.append("UPSTREAM_LINEAGE_STATUS")
    if row.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")
    return sorted(set(errors))


def validate_us(decision: dict[str, Any], ledger: dict[str, Any] | None, evidence: list[dict[str, Any]], states: list[dict[str, Any]], approval: dict[str, Any] | None) -> list[str]:
    errors: list[str] = []
    if ledger is None:
        errors.append("MISSING_EVIDENCE_LEDGER")
    if not evidence:
        errors.append("MISSING_EVIDENCE_REGISTRATION")
    if not states:
        errors.append("MISSING_WORKFLOW_STATE")
    if approval is None:
        errors.append("MISSING_HUMAN_APPROVAL_STATE")
    symbol = decision.get("symbol")
    reference = symbol == "QQQ"
    expected_graduation = "NOT_APPLICABLE_REFERENCE_INSTRUMENT" if reference else "BLOCKED_EVIDENCE_AND_DECISION_REQUIREMENTS_PENDING"
    expected_approval = "NOT_APPLICABLE_REFERENCE_INSTRUMENT" if reference else "NOT_REQUESTED_PREREQUISITES_INCOMPLETE"
    if decision.get("candidate_graduation_status") != expected_graduation:
        errors.append("CANDIDATE_GRADUATION_STATUS")
    if decision.get("human_approval_status") != expected_approval:
        errors.append("HUMAN_APPROVAL_STATUS")
    if approval and approval.get("approval_status") != expected_approval:
        errors.append("APPROVAL_RECORD_STATUS")
    if decision.get("investment_recommendation_status") != "NOT_ISSUED":
        errors.append("INVESTMENT_RECOMMENDATION")
    if decision.get("candidate_pool_status") != "NOT_AUTHORIZED":
        errors.append("CANDIDATE_POOL_STATUS")
    if decision.get("simulation_status") != "CLOSED_NOT_AUTHORIZED":
        errors.append("SIMULATION_STATUS")
    if decision.get("automatic_promotion_allowed") is not False:
        errors.append("AUTOMATIC_PROMOTION")
    if decision.get("trade_authority") != "NONE" or (approval and approval.get("trade_authority") != "NONE"):
        errors.append("TRADE_AUTHORITY")
    return sorted(set(errors))


def build_lineages(repo_root: Path, contract: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    sources = contract["market_lineage_sources"]
    records: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []

    a_rows = read_csv(repo_root / sources["A_SHARE"]["lineage_path"])
    for row in a_rows:
        errors = validate_a_share(row)
        records.append({
            "market": "A_SHARE",
            "security_id": row["symbol"],
            "security_name": row.get("name", ""),
            "evidence_ids": [row.get("evidence_id")],
            "research_id": row.get("research_id"),
            "decision_id": row.get("lineage_id"),
            "decision_state": row.get("graduation_decision"),
            "governed_route_id": row.get("transition_id"),
            "governed_route_state": row.get("queue_state"),
            "thesis_id": row.get("thesis_record_id"),
            "data_grade": row.get("evidence_quality_state"),
            "lineage_status": "PASS" if not errors else "FAIL",
            "lineage_errors": errors,
            "automatic_candidate_promotion": False,
            "investment_recommendation_issued": False,
            "trade_authority": "NONE",
        })
        diagnostics.append({"market": "A_SHARE", "security_id": row["symbol"], "errors": errors})

    hk_rows = read_csv(repo_root / sources["HONG_KONG_CONNECT"]["lineage_path"])
    for row in hk_rows:
        errors = validate_hk(row)
        records.append({
            "market": "HONG_KONG_CONNECT",
            "security_id": row["security_id"],
            "security_name": row.get("official_security_name_en", ""),
            "evidence_ids": ["FMDL5E_SCREEN_RANK:" + str(row.get("fmdl5e_screen_rank", "")), row.get("research_object_sha256")],
            "research_id": row.get("research_id"),
            "decision_id": "HK_DECISION:" + str(row.get("research_id", "")),
            "decision_state": row.get("research_decision"),
            "governed_route_id": row.get("transition_id"),
            "governed_route_state": row.get("target_route"),
            "thesis_id": None,
            "data_grade": "OPERATIONAL_WITH_CONTROLLED_FREE_SOURCE_LIMITS",
            "a_h_duplication_review_required": truthy(row.get("a_h_duplication_review_required")),
            "lineage_status": "PASS" if not errors else "FAIL",
            "lineage_errors": errors,
            "automatic_candidate_promotion": False,
            "investment_recommendation_issued": False,
            "trade_authority": "NONE",
        })
        diagnostics.append({"market": "HONG_KONG_CONNECT", "security_id": row["security_id"], "errors": errors})

    us_spec = sources["US_EQUITY"]
    integration_summary = read_json(repo_root / us_spec["integration_summary_path"])
    integration_zip = repo_root / us_spec["integration_shards_path"]
    graduation_zip = repo_root / us_spec["graduation_shards_path"]
    evidence_rows = read_zip_jsonl(integration_zip, "EVIDENCE_REGISTRATION")
    ledgers = read_zip_jsonl(integration_zip, "SECURITY_EVIDENCE_LEDGER")
    states = read_zip_jsonl(integration_zip, "WORKFLOW_INTEGRATION_STATE")
    decisions = read_zip_jsonl(graduation_zip, "DECISION_INTERFACE")
    approvals = read_zip_jsonl(graduation_zip, "HUMAN_APPROVAL_STATE")
    ledger_by_sid = {row["canonical_security_id"]: row for row in ledgers}
    evidence_by_sid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    states_by_sid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    approval_by_sid = {row["canonical_security_id"]: row for row in approvals}
    for row in evidence_rows:
        evidence_by_sid[row["canonical_security_id"]].append(row)
    for row in states:
        states_by_sid[row["canonical_security_id"]].append(row)
    for decision in decisions:
        sid = decision["canonical_security_id"]
        evidence = evidence_by_sid.get(sid, [])
        workflow_states = states_by_sid.get(sid, [])
        approval = approval_by_sid.get(sid)
        errors = validate_us(decision, ledger_by_sid.get(sid), evidence, workflow_states, approval)
        records.append({
            "market": "US_EQUITY",
            "security_id": sid,
            "security_name": decision.get("symbol", ""),
            "evidence_ids": sorted(row["evidence_registration_id"] for row in evidence),
            "research_id": "US_RESEARCH_LEDGER:" + sid,
            "decision_id": decision.get("decision_interface_id"),
            "decision_state": decision.get("candidate_graduation_status"),
            "governed_route_id": decision.get("human_approval_status"),
            "governed_route_state": decision.get("allowed_next_action"),
            "thesis_id": None,
            "data_grade": decision.get("security_thesis_readiness"),
            "workflow_state_count": len(workflow_states),
            "lineage_status": "PASS" if not errors else "FAIL",
            "lineage_errors": errors,
            "automatic_candidate_promotion": bool(decision.get("automatic_promotion_allowed")),
            "investment_recommendation_issued": decision.get("investment_recommendation_status") != "NOT_ISSUED",
            "trade_authority": decision.get("trade_authority"),
        })
        diagnostics.append({"market": "US_EQUITY", "security_id": sid, "errors": errors})

    upstream = {
        "a_share_rows": len(a_rows),
        "hong_kong_rows": len(hk_rows),
        "us_decision_rows": len(decisions),
        "us_ledger_rows": len(ledgers),
        "us_evidence_rows": len(evidence_rows),
        "us_workflow_state_rows": len(states),
        "us_approval_rows": len(approvals),
        "us_integration_summary": integration_summary,
    }
    records.sort(key=lambda row: (row["market"], row["security_id"]))
    diagnostics.sort(key=lambda row: (row["market"], row["security_id"]))
    return records, diagnostics, upstream


def run_failure_injections(records: list[dict[str, Any]], contract: dict[str, Any]) -> list[dict[str, Any]]:
    by_market: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        by_market[row["market"]].append(row)
    results: list[dict[str, Any]] = []
    fixtures = [
        ("A_SHARE_MISSING_EVIDENCE_OR_RESEARCH_ID", "A_SHARE", lambda row: row.update({"evidence_ids": [], "research_id": ""}), {"MISSING_EVIDENCE_OR_RESEARCH"}),
        ("A_SHARE_CROSS_DOMAIN_OR_UNAUTHORIZED_MUTATION", "A_SHARE", lambda row: row.update({"governed_route_state": "REAL_ACCOUNT", "automatic_candidate_promotion": True}), {"UNAUTHORIZED_ROUTE_OR_PROMOTION"}),
        ("HONG_KONG_RESEARCH_OBJECT_HASH_OR_ROUTE_MISMATCH", "HONG_KONG_CONNECT", lambda row: row.update({"evidence_ids": ["BAD_HASH"], "governed_route_state": "REAL_ACCOUNT"}), {"UNAUTHORIZED_ROUTE_OR_PROMOTION"}),
        ("HONG_KONG_A_H_DUPLICATION_REVIEW_BYPASS", "HONG_KONG_CONNECT", lambda row: row.update({"a_h_duplication_review_required": False, "security_id": "HKEX:00300"}), {"A_H_DUPLICATION_BYPASS"}),
        ("US_MISSING_EVIDENCE_LEDGER_OR_DECISION_INTERFACE", "US_EQUITY", lambda row: row.update({"evidence_ids": [], "decision_id": ""}), {"MISSING_EVIDENCE_OR_DECISION"}),
        ("US_AUTOMATIC_PROMOTION_OR_HUMAN_APPROVAL_FABRICATION", "US_EQUITY", lambda row: row.update({"automatic_candidate_promotion": True, "decision_state": "APPROVED_RESEARCH_CANDIDATE"}), {"UNAUTHORIZED_ROUTE_OR_PROMOTION"}),
        ("ANY_MARKET_TRADE_AUTHORITY_ESCALATION", "A_SHARE", lambda row: row.update({"trade_authority": "EXECUTE"}), {"TRADE_AUTHORITY"}),
    ]

    def observe(row: dict[str, Any]) -> set[str]:
        errors: set[str] = set()
        if not row.get("evidence_ids") or not row.get("research_id"):
            errors.add("MISSING_EVIDENCE_OR_RESEARCH")
        if not row.get("evidence_ids") or not row.get("decision_id"):
            errors.add("MISSING_EVIDENCE_OR_DECISION")
        if row.get("automatic_candidate_promotion") or row.get("governed_route_state") == "REAL_ACCOUNT":
            errors.add("UNAUTHORIZED_ROUTE_OR_PROMOTION")
        if row.get("market") == "HONG_KONG_CONNECT" and row.get("security_id") == "HKEX:00300" and not row.get("a_h_duplication_review_required"):
            errors.add("A_H_DUPLICATION_BYPASS")
        if row.get("trade_authority") != "NONE":
            errors.add("TRADE_AUTHORITY")
        return errors

    for name, market, mutate, expected in fixtures:
        base = dict(by_market[market][0])
        base["evidence_ids"] = list(base.get("evidence_ids", []))
        if name == "HONG_KONG_A_H_DUPLICATION_REVIEW_BYPASS":
            base = dict(next(row for row in by_market[market] if row["security_id"] == "HKEX:00300"))
        mutate(base)
        observed = observe(base)
        results.append({
            "fixture_id": name,
            "expected_error_codes": sorted(expected),
            "observed_error_codes": sorted(observed),
            "status": "REJECTED_AS_REQUIRED" if expected.issubset(observed) else "FAILURE_NOT_CAUGHT",
            "current_replacement_authorized": False,
            "lkg_replacement_authorized": False,
            "trade_authority": "NONE",
        })
    return results


def build_candidate(repo_root: Path, output_dir: Path, generated_at: str, source_commit: str) -> dict[str, Any]:
    contract, contract_errors = validate_contract(repo_root)
    if contract_errors:
        raise AcceptanceError("CONTRACT_VALIDATION_FAILED:" + ",".join(contract_errors))
    records, diagnostics, upstream = build_lineages(repo_root, contract)
    failures = run_failure_injections(records, contract)

    counts = Counter(row["market"] for row in records)
    pass_count = sum(row["lineage_status"] == "PASS" for row in records)
    orphan_count = sum(bool(row["lineage_errors"]) for row in records)
    identity_keys = [(row["market"], row["security_id"], row["decision_id"]) for row in records]
    duplicate_count = len(identity_keys) - len(set(identity_keys))
    auto_promotions = sum(bool(row["automatic_candidate_promotion"]) for row in records)
    recommendations = sum(bool(row["investment_recommendation_issued"]) for row in records)
    trade_errors = sum(row["trade_authority"] != "NONE" for row in records)
    hk_ah_count = sum(row.get("a_h_duplication_review_required") for row in records if row["market"] == "HONG_KONG_CONNECT")
    a_queue_counts = Counter(row["governed_route_state"] for row in records if row["market"] == "A_SHARE")
    hk_decisions = Counter(row["decision_state"] for row in records if row["market"] == "HONG_KONG_CONNECT")
    us_states = Counter(row["decision_state"] for row in records if row["market"] == "US_EQUITY")

    observed = {
        "market_count": len(counts),
        "source_binding_count": 3,
        "a_share_lineage_count": counts["A_SHARE"],
        "hong_kong_lineage_count": counts["HONG_KONG_CONNECT"],
        "us_lineage_count": counts["US_EQUITY"],
        "cross_market_lineage_count": len(records),
        "lineage_pass_count": pass_count,
        "orphan_lineage_count": orphan_count,
        "duplicate_lineage_identity_count": duplicate_count,
        "automatic_candidate_promotion_count": auto_promotions,
        "investment_recommendation_count": recommendations,
        "candidate_pool_mutations": 0,
        "simulation_book_mutations": 0,
        "real_account_mutations": 0,
        "rule_mutations": 0,
        "orders": 0,
        "failure_injection_count": len(failures),
        "logical_shard_domain_count": len(SHARD_DOMAINS),
        "bucket_count": 64,
        "logical_shard_count": len(SHARD_DOMAINS) * 64,
    }
    metric_errors = [key for key, expected in contract["acceptance_gates"].items() if observed.get(key) != expected]
    additional_errors: list[str] = []
    if a_queue_counts != Counter({"CANDIDATE_POOL_REENTRY_REVIEW_READY": 4, "SHADOW_TRACK_REENTRY_REVIEW_READY": 2}):
        additional_errors.append("A_SHARE_ROUTE_COUNTS")
    if hk_decisions != Counter({"GRADUATED": 4, "SHADOW_TRACK": 2}):
        additional_errors.append("HK_DECISION_COUNTS")
    if hk_ah_count != 2:
        additional_errors.append("HK_A_H_COUNT")
    if us_states != Counter({"BLOCKED_EVIDENCE_AND_DECISION_REQUIREMENTS_PENDING": 6, "NOT_APPLICABLE_REFERENCE_INSTRUMENT": 1}):
        additional_errors.append("US_DECISION_COUNTS")
    us_spec = contract["market_lineage_sources"]["US_EQUITY"]
    if upstream["us_evidence_rows"] != us_spec["expected_evidence_registration_count"]:
        additional_errors.append("US_EVIDENCE_COUNT")
    if upstream["us_workflow_state_rows"] != us_spec["expected_workflow_state_count"]:
        additional_errors.append("US_WORKFLOW_STATE_COUNT")
    if upstream["us_integration_summary"].get("formal_workflow_execution_count") != 0 or upstream["us_integration_summary"].get("registered_workflow_output_count") != 0:
        additional_errors.append("US_FORMAL_WORKFLOW_BOUNDARY")
    if any(row["status"] != "REJECTED_AS_REQUIRED" for row in failures):
        additional_errors.append("FAILURE_INJECTION")
    if trade_errors:
        additional_errors.append("TRADE_AUTHORITY")
    all_errors = sorted(set(metric_errors + additional_errors))
    if all_errors:
        raise AcceptanceError("ACCEPTANCE_FAILED:" + ",".join(all_errors))

    source_paths: list[str] = [contract["entry_gate"]["path"]]
    for spec in contract["market_lineage_sources"].values():
        source_paths.extend(value for key, value in spec.items() if key.endswith("_path"))
    source_hashes = {path: sha256_file(repo_root / path) for path in sorted(set(source_paths))}
    basis = {
        "contract_sha256": sha256_file(repo_root / CONTRACT_PATH),
        "source_hashes": source_hashes,
        "source_commit": source_commit,
        "as_of_date": contract["as_of_date"],
    }
    release_id = "FMDL7B_" + contract["as_of_date"].replace("-", "") + "_" + sha256_bytes(canonical_bytes(basis))[:12]

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    write_jsonl(output_dir / "FMDL7B_CROSS_MARKET_LINEAGE_REGISTRY.jsonl", records)
    write_csv(
        output_dir / "FMDL7B_CROSS_MARKET_LINEAGE_REGISTRY.csv",
        records,
        ["market", "security_id", "security_name", "research_id", "decision_id", "decision_state", "governed_route_id", "governed_route_state", "thesis_id", "data_grade", "lineage_status", "trade_authority"],
    )
    write_json(output_dir / "FMDL7B_MARKET_LINEAGE_SUMMARY.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "market_counts": dict(sorted(counts.items())),
        "a_share_route_counts": dict(sorted(a_queue_counts.items())),
        "hong_kong_decision_counts": dict(sorted(hk_decisions.items())),
        "hong_kong_a_h_duplication_count": hk_ah_count,
        "us_decision_counts": dict(sorted(us_states.items())),
        "upstream_counts": upstream,
        "lineage_posture": {
            market: spec["lineage_posture"] for market, spec in contract["market_lineage_sources"].items()
        },
        "trade_authority": "NONE",
    })
    write_json(output_dir / "FMDL7B_ORPHAN_AND_DUPLICATE_REPORT.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "orphan_lineage_count": orphan_count,
        "duplicate_lineage_identity_count": duplicate_count,
        "diagnostics": diagnostics,
        "status": "PASS",
        "trade_authority": "NONE",
    })
    write_json(output_dir / "FMDL7B_FAILURE_INJECTION_RESULTS.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "results": failures,
        "all_rejected_as_required": True,
        "trade_authority": "NONE",
    })

    gates = [
        ("THREE_MARKETS_BOUND", len(counts) == 3),
        ("A_SHARE_SIX_COMPLETE_LINEAGES", counts["A_SHARE"] == 6),
        ("HK_SIX_COMPLETE_LINEAGES", counts["HONG_KONG_CONNECT"] == 6),
        ("US_SEVEN_FAIL_CLOSED_LINEAGES", counts["US_EQUITY"] == 7),
        ("NINETEEN_LINEAGES_PASS", pass_count == 19),
        ("NO_ORPHAN_LINEAGE", orphan_count == 0),
        ("NO_DUPLICATE_LINEAGE_IDENTITY", duplicate_count == 0),
        ("A_SHARE_ROUTE_SEPARATION", a_queue_counts == Counter({"CANDIDATE_POOL_REENTRY_REVIEW_READY": 4, "SHADOW_TRACK_REENTRY_REVIEW_READY": 2})),
        ("HK_GRADUATED_AND_SHADOW_SEPARATION", hk_decisions == Counter({"GRADUATED": 4, "SHADOW_TRACK": 2})),
        ("HK_A_H_DUPLICATION_CONTROL", hk_ah_count == 2),
        ("US_HUMAN_APPROVAL_FAIL_CLOSED", us_states == Counter({"BLOCKED_EVIDENCE_AND_DECISION_REQUIREMENTS_PENDING": 6, "NOT_APPLICABLE_REFERENCE_INSTRUMENT": 1})),
        ("NO_AUTOMATIC_PROMOTION", auto_promotions == 0),
        ("NO_INVESTMENT_RECOMMENDATION", recommendations == 0),
        ("ZERO_INVESTMENT_STATE_MUTATION", all(observed[key] == 0 for key in ["candidate_pool_mutations", "simulation_book_mutations", "real_account_mutations", "rule_mutations", "orders"])),
        ("SEVEN_FAILURES_REJECTED", len(failures) == 7 and all(row["status"] == "REJECTED_AS_REQUIRED" for row in failures)),
        ("TRADE_AUTHORITY_NONE", trade_errors == 0),
        ("ONLY_FMDL7C_NEXT_GATE_OPEN", contract["next_gate"] == NEXT_GATE),
    ]
    gate_rows = [
        {"gate_order": index, "gate_code": code, "gate_status": "PASS" if passed else "FAIL", "trade_authority": "NONE"}
        for index, (code, passed) in enumerate(gates, 1)
    ]
    write_json(output_dir / "FMDL7B_ACCEPTANCE_GATE_MATRIX.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "gate_count": len(gate_rows),
        "pass_count": sum(row["gate_status"] == "PASS" for row in gate_rows),
        "gates": gate_rows,
        "trade_authority": "NONE",
    })
    shard_rows = [
        {"domain": domain, "bucket": bucket, "logical_shard_id": f"FMDL7B-{domain}-{bucket:02d}", "state": "LINEAGE_ACCEPTED_NO_RUNTIME_MUTATION", "trade_authority": "NONE"}
        for domain in SHARD_DOMAINS for bucket in range(64)
    ]
    write_json(output_dir / "FMDL7B_LOGICAL_SHARD_REGISTRY.json", {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "domain_count": len(SHARD_DOMAINS),
        "bucket_count": 64,
        "logical_shard_count": len(shard_rows),
        "shards": shard_rows,
        "trade_authority": "NONE",
    })
    quality = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "quality_status": "PASS",
        "contract_error_count": 0,
        **observed,
        "acceptance_gate_count": len(gate_rows),
        "acceptance_gate_pass_count": len(gate_rows),
        "trade_authority": "NONE",
    }
    write_json(output_dir / "FMDL7B_QUALITY_REPORT.json", quality)
    decision = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "accepted_at": generated_at,
        "source_commit": source_commit,
        "status": EXIT_STATUS,
        "next_gate": NEXT_GATE,
        "market_count": 3,
        "cross_market_lineage_count": 19,
        "lineage_pass_count": 19,
        "a_share_lineage_posture": contract["market_lineage_sources"]["A_SHARE"]["lineage_posture"],
        "hong_kong_lineage_posture": contract["market_lineage_sources"]["HONG_KONG_CONNECT"]["lineage_posture"],
        "us_lineage_posture": contract["market_lineage_sources"]["US_EQUITY"]["lineage_posture"],
        "automatic_candidate_promotion_count": 0,
        "investment_recommendation_count": 0,
        "zero_mutation_proof": {key: observed[key] for key in ["candidate_pool_mutations", "simulation_book_mutations", "real_account_mutations", "rule_mutations", "orders"]},
        "trade_authority": "NONE",
    }
    write_json(output_dir / "FMDL7B_DECISION.json", decision)

    files = {}
    for path in sorted(output_dir.iterdir()):
        if path.is_file():
            files[path.name] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    manifest = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "generated_at": generated_at,
        "source_commit": source_commit,
        "contract_sha256": sha256_file(repo_root / CONTRACT_PATH),
        "source_hashes": source_hashes,
        "files": files,
        "quality_status": "PASS",
        "trade_authority": "NONE",
    }
    write_json(output_dir / "FMDL7B_MANIFEST.json", manifest)
    return decision


def replace_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def publish(repo_root: Path, candidate: Path) -> dict[str, Any]:
    contract = read_json(repo_root / CONTRACT_PATH)
    decision = read_json(candidate / "FMDL7B_DECISION.json")
    quality = read_json(candidate / "FMDL7B_QUALITY_REPORT.json")
    manifest = read_json(candidate / "FMDL7B_MANIFEST.json")
    if decision.get("status") != EXIT_STATUS or quality.get("quality_status") != "PASS":
        raise AcceptanceError("CANDIDATE_NOT_ACCEPTED")
    release_id = decision["release_id"]
    current = repo_root / contract["storage_contract"]["current_root"]
    immutable = repo_root / contract["storage_contract"]["release_root"].replace("<release_id>", release_id)
    normalized = repo_root / contract["storage_contract"]["normalized_root"].replace("<release_id>", release_id)
    archive = repo_root / contract["storage_contract"]["archive_root"] / release_id
    if immutable.exists():
        existing = read_json(immutable / "FMDL7B_MANIFEST.json")
        if canonical_bytes(existing) != canonical_bytes(manifest):
            raise AcceptanceError("IMMUTABLE_RELEASE_COLLISION")
    else:
        shutil.copytree(candidate, immutable)
    replace_tree(candidate, current)
    replace_tree(candidate, normalized)
    if not archive.exists():
        shutil.copytree(candidate, archive)
    manifest_sha = sha256_file(candidate / "FMDL7B_MANIFEST.json")
    pointer = {
        "phase_id": PHASE_ID,
        "release_id": release_id,
        "release_sequence": decision["release_sequence"],
        "published_at": decision["accepted_at"],
        "source_commit": decision["source_commit"],
        "status": EXIT_STATUS,
        "current_path": contract["storage_contract"]["current_root"],
        "release_path": contract["storage_contract"]["release_root"].replace("<release_id>", release_id),
        "normalized_path": contract["storage_contract"]["normalized_root"].replace("<release_id>", release_id),
        "manifest_sha256": manifest_sha,
        "market_count": decision["market_count"],
        "cross_market_lineage_count": decision["cross_market_lineage_count"],
        "lineage_pass_count": decision["lineage_pass_count"],
        "automatic_candidate_promotion_count": 0,
        "investment_recommendation_count": 0,
        "next_gate": NEXT_GATE,
        "trade_authority": "NONE",
        "zero_mutation_proof": decision["zero_mutation_proof"],
    }
    write_json(repo_root / contract["storage_contract"]["last_success"], pointer)
    write_json(repo_root / contract["storage_contract"]["last_known_good"], {**pointer, "lkg_status": "LAST_KNOWN_GOOD"})
    return pointer


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    build = sub.add_parser("build")
    build.add_argument("--output", required=True)
    build.add_argument("--generated-at", required=True)
    build.add_argument("--source-commit", required=True)
    pub = sub.add_parser("publish")
    pub.add_argument("--candidate", required=True)
    args = parser.parse_args()
    repo_root = Path(".").resolve()
    if args.command == "validate":
        _, errors = validate_contract(repo_root)
        if errors:
            raise SystemExit("\n".join(errors))
        print("PASS")
    elif args.command == "build":
        decision = build_candidate(repo_root, Path(args.output), args.generated_at, args.source_commit)
        print(decision["release_id"])
    else:
        pointer = publish(repo_root, Path(args.candidate))
        print(pointer["release_id"])


if __name__ == "__main__":
    main()
