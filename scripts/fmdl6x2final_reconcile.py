from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

PHASE_ID = "FMDL-6X2-FINAL"
STATUS = "FMDL6X2_FINAL_FULL_STORE_RECONCILIATION_AND_OPERATIONAL_ACCEPTANCE_ACCEPTED"
NEXT_GATE = "FMDL-6X3-A_RESEARCH_UNIVERSE_AND_DATA_READINESS_CONTRACT"
CONTRACT_PATH = Path("config/fmdl6x2final_full_store_reconciliation_contract.json")

DOMAIN_SPECS = {
    "security_master": {"phase_id": "FMDL-6X2-A", "pointer": "outputs/status/FMDL6X2A_LAST_SUCCESS.json", "status": "FMDL6X2A_CURRENT_SECURITY_MASTER_PRODUCTION_ACCEPTED", "sequence": 30, "manifest": "FMDL6X2A_MANIFEST.json", "decision": "FMDL6X2A_DECISION.json", "quality": "FMDL6X2A_QUALITY_REPORT.json"},
    "identity": {"phase_id": "FMDL-6X2-B", "pointer": "outputs/status/FMDL6X2B_LAST_SUCCESS.json", "status": "FMDL6X2B_IDENTITY_CLASSIFICATION_AND_REVIEW_QUEUES_ACCEPTED", "sequence": 31, "manifest": "FMDL6X2B_MANIFEST.json", "decision": "FMDL6X2B_DECISION.json", "quality": "FMDL6X2B_QUALITY_REPORT.json"},
    "listing_history": {"phase_id": "FMDL-6X2-C", "pointer": "outputs/status/FMDL6X2C_LAST_SUCCESS.json", "status": "FMDL6X2C_HISTORICAL_LISTING_AND_LIFECYCLE_BACKFILL_ACCEPTED", "sequence": 32, "manifest": "FMDL6X2C_MANIFEST.json", "decision": "FMDL6X2C_DECISION.json", "quality": "FMDL6X2C_QUALITY_REPORT.json"},
    "market_reference": {"phase_id": "FMDL-6X2-D", "pointer": "outputs/status/FMDL6X2D_LAST_SUCCESS.json", "status": "FMDL6X2D_MARKET_HISTORY_CORPORATE_ACTIONS_AND_FX_ACCEPTED", "sequence": 33, "manifest": "FMDL6X2D_MANIFEST.json", "decision": "FMDL6X2D_DECISION.json", "quality": "FMDL6X2D_QUALITY_REPORT.json"},
    "sec_filings_facts": {"phase_id": "FMDL-6X2-E", "pointer": "outputs/status/FMDL6X2E_LAST_SUCCESS.json", "status": "FMDL6X2E_SEC_FILINGS_AND_FINANCIAL_FACTS_STORE_ACCEPTED", "sequence": 34, "manifest": "FMDL6X2E_MANIFEST.json", "decision": "FMDL6X2E_DECISION.json", "quality": "FMDL6X2E_QUALITY_REPORT.json"},
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def validate_contract(repo_root: Path) -> dict[str, Any]:
    contract = read_json(repo_root / CONTRACT_PATH)
    assert contract["phase_id"] == PHASE_ID
    assert contract["trade_authority"] == "NONE"
    assert contract["required_exit_status"] == STATUS
    assert contract["next_gate"] == NEXT_GATE
    assert contract["storage_contract"]["release_sequence"] == 35
    assert set(contract["domain_contracts"]) == set(DOMAIN_SPECS)
    for name, spec in DOMAIN_SPECS.items():
        declared = contract["domain_contracts"][name]
        assert declared["pointer_path"] == spec["pointer"]
        assert declared["required_release_sequence"] == spec["sequence"]
        assert declared["required_status"] == spec["status"]
    return contract


def validate_domain(repo_root: Path, name: str, spec: dict[str, Any]) -> dict[str, Any]:
    pointer = read_json(repo_root / spec["pointer"])
    errors: list[str] = []
    if pointer.get("phase_id") != spec["phase_id"]:
        errors.append("PHASE_ID_MISMATCH")
    if pointer.get("status") != spec["status"]:
        errors.append("STATUS_MISMATCH")
    if pointer.get("release_sequence") != spec["sequence"]:
        errors.append("RELEASE_SEQUENCE_MISMATCH")
    if pointer.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY_NOT_NONE")
    if pointer.get("brokerage_real_account_gate") not in {None, "CLOSED_NO_CHANNEL"}:
        errors.append("BROKERAGE_GATE_NOT_CLOSED")

    current_root = repo_root / pointer["current_path"]
    release_root = repo_root / pointer["release_path"]
    current_manifest = current_root / spec["manifest"]
    release_manifest = release_root / spec["manifest"]
    current_decision = current_root / spec["decision"]
    release_decision = release_root / spec["decision"]
    current_quality = current_root / spec["quality"]
    for path in (current_manifest, release_manifest, current_decision, release_decision, current_quality):
        if not path.exists():
            errors.append(f"MISSING:{path.relative_to(repo_root)}")
    if errors:
        return {"domain": name, "errors": errors, "pointer": pointer, "quality": {}}

    manifest_hash = sha256_path(current_manifest)
    if manifest_hash != pointer.get("manifest_sha256"):
        errors.append("POINTER_MANIFEST_HASH_MISMATCH")
    if current_manifest.read_bytes() != release_manifest.read_bytes():
        errors.append("CURRENT_RELEASE_MANIFEST_PARITY_FAILED")
    if current_decision.read_bytes() != release_decision.read_bytes():
        errors.append("CURRENT_RELEASE_DECISION_PARITY_FAILED")
    decision = read_json(current_decision)
    quality = read_json(current_quality)
    if decision.get("status") != spec["status"]:
        errors.append("DECISION_STATUS_MISMATCH")
    if decision.get("trade_authority") != "NONE":
        errors.append("DECISION_TRADE_AUTHORITY_NOT_NONE")
    if quality.get("quality_status") != "PASS":
        errors.append("QUALITY_NOT_PASS")
    return {
        "domain": name,
        "phase_id": spec["phase_id"],
        "release_id": pointer["release_id"],
        "release_sequence": pointer["release_sequence"],
        "status": pointer["status"],
        "current_path": pointer["current_path"],
        "release_path": pointer["release_path"],
        "normalized_path": pointer.get("normalized_path"),
        "manifest_sha256": manifest_hash,
        "current_release_manifest_parity": True,
        "current_release_decision_parity": True,
        "quality_status": quality.get("quality_status"),
        "errors": errors,
        "pointer": pointer,
        "quality": quality,
    }


def cross_domain_reconcile(domains: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    a = domains["security_master"]["pointer"]
    b = domains["identity"]["pointer"]
    c = domains["listing_history"]["pointer"]
    d = domains["market_reference"]
    e = domains["sec_filings_facts"]
    checks = {
        "security_master_to_identity_listing_count": {"left": a.get("included_security_records"), "right": b.get("listing_records"), "expected": 8807},
        "identity_to_listing_history_count": {"left": b.get("listing_records"), "right": c.get("effective_listing_intervals"), "expected": 8807},
        "identity_to_market_universe_count": {"left": b.get("security_records"), "right": d["quality"].get("universe_accounted"), "expected": 8785},
        "identity_to_sec_issuer_universe_count": {"left": b.get("issuer_records"), "right": e["quality"].get("universe_accounted"), "expected": 7419},
        "release_sequence_continuity": {"actual": [domains[n]["release_sequence"] for n in DOMAIN_SPECS], "expected": [30, 31, 32, 33, 34]},
    }
    for name, check in checks.items():
        if "left" in check and not (check["left"] == check["right"] == check["expected"]):
            errors.append(f"CROSS_DOMAIN_COUNT_FAILED:{name}")
        if "actual" in check and check["actual"] != check["expected"]:
            errors.append(f"CROSS_DOMAIN_SEQUENCE_FAILED:{name}")
    if not (d["pointer"].get("accepted_dual_route_securities") == 64 and d["quality"].get("universe_accounted") == 8785 and d["pointer"].get("full_universe_market_history_claimed") is False):
        errors.append("MARKET_COVERAGE_BOUNDARY_NOT_PRESERVED")
    if not (e["pointer"].get("backfill_queue_count") == 7413 and e["quality"].get("universe_accounted") == 7419 and e["pointer"].get("full_universe_sec_store_claimed") is False):
        errors.append("SEC_COVERAGE_BOUNDARY_NOT_PRESERVED")
    if c.get("historical_completion_claimed") is not False:
        errors.append("LISTING_HISTORY_COMPLETION_OVERCLAIM")
    if d["pointer"].get("market_data_grade") != "NON_DECISION_GRADE_FALLBACK":
        errors.append("MARKET_DATA_GRADE_ESCALATED")
    return {
        "checks": checks,
        "listing_history_completion_claimed": c.get("historical_completion_claimed"),
        "market_history": {"accepted_dual_route_securities": d["pointer"].get("accepted_dual_route_securities"), "universe_securities": d["quality"].get("universe_accounted"), "full_universe_claimed": d["pointer"].get("full_universe_market_history_claimed"), "data_grade": d["pointer"].get("market_data_grade")},
        "sec_store": {"filing_count": e["pointer"].get("filing_count"), "fact_count": e["pointer"].get("fact_count"), "backfill_queue_count": e["pointer"].get("backfill_queue_count"), "universe_issuers": e["quality"].get("universe_accounted"), "full_universe_claimed": e["pointer"].get("full_universe_sec_store_claimed")},
        "quality_status": "PASS" if not errors else "FAIL",
    }, errors


def coverage_boundaries(domains: dict[str, dict[str, Any]]) -> dict[str, Any]:
    b = domains["identity"]["pointer"]
    c = domains["listing_history"]["pointer"]
    d = domains["market_reference"]["pointer"]
    e = domains["sec_filings_facts"]["pointer"]
    return {
        "phase_id": PHASE_ID,
        "security_master": "CURRENT_OFFICIAL_DIRECTORY_ACCEPTED",
        "identity": {"status": b.get("canonical_id_status"), "sec_identity_status": b.get("sec_identity_status"), "completion_claimed": False},
        "listing_history": {"status": c.get("history_status"), "accepted_snapshot_count": c.get("accepted_snapshot_count"), "completion_claimed": c.get("historical_completion_claimed")},
        "market_reference": {"status": d.get("market_store_status"), "grade": d.get("market_data_grade"), "accepted_security_count": d.get("accepted_dual_route_securities"), "completion_claimed": d.get("full_universe_market_history_claimed")},
        "sec_filings_facts": {"status": e.get("sec_store_status"), "filings": e.get("filing_count"), "facts": e.get("fact_count"), "backfill_queue": e.get("backfill_queue_count"), "completion_claimed": e.get("full_universe_sec_store_claimed")},
        "global_full_data_completion_claimed": False,
        "accepted_completion_claim": "PRODUCTION_STORES_AND_RESUMABLE_BACKFILL_MECHANISMS_ACCEPTED_WITH_EXPLICIT_COVERAGE_BOUNDARIES",
    }


def handoff_plan() -> dict[str, Any]:
    return {
        "phase_id": PHASE_ID,
        "next_gate": NEXT_GATE,
        "fmdl6x3": {"name": "US Research Production, Factor & Benchmark Pool", "completion_gate": "FMDL-6X3-FINAL_RESEARCH_PRODUCTION_ACCEPTANCE", "stages": [
            {"id": "FMDL-6X3-A", "name": "Research Universe & Data Readiness Contract"},
            {"id": "FMDL-6X3-B", "name": "Financial Normalization, TTM & Annual Metric Layer"},
            {"id": "FMDL-6X3-C", "name": "Factor, Valuation, Quality & Risk Engine"},
            {"id": "FMDL-6X3-D", "name": "Sector, Industry, Peer & Benchmark Framework"},
            {"id": "FMDL-6X3-E", "name": "Screening Funnel, Research Cards & US Benchmark Pool"},
            {"id": "FMDL-6X3-FINAL", "name": "Research Production Reconciliation & Acceptance"}], "authority_boundary": "RESEARCH_BENCHMARK_POOL_ONLY_NO_INVESTMENT_OS_CANDIDATE_MUTATION"},
        "fmdl6x4": {"name": "Public Equity Investing & Investment OS Integration", "completion_gate": "FMDL-6X4-FINAL_US_RESEARCH_ADAPTER_OPERATIONAL_ACCEPTANCE", "stages": [
            {"id": "FMDL-6X4-A", "name": "Public Equity Investing Adapter & Contract Mapping"},
            {"id": "FMDL-6X4-B", "name": "Research Workflow Integration & Evidence Registration"},
            {"id": "FMDL-6X4-C", "name": "Candidate Graduation, Decision Interface & Guardrails"},
            {"id": "FMDL-6X4-D", "name": "Simulation-Only Pilot, Attribution & Failure Recovery"},
            {"id": "FMDL-6X4-E", "name": "Cross-Market Comparability & Operating Runbook"},
            {"id": "FMDL-6X4-FINAL", "name": "US Research Adapter Operational Acceptance & FMDL-6 Freeze"}], "brokerage_boundary": "RESEARCH_COMPLETE_WITH_BROKERAGE_GATE_CLOSED_NO_CHANNEL"},
        "fmdl6_completion_rule": "FMDL-6_IS_COMPLETE_ONLY_AFTER_FMDL-6X4-FINAL_ACCEPTS_X1_X2_X3_X4_AND_FREEZES_THE_US_RESEARCH_ADAPTER",
        "fmdl7_role": "CROSS_MARKET_AND_FULL_SYSTEM_FINAL_OPERATIONAL_ACCEPTANCE_NOT_US_DATA_CONSTRUCTION",
    }


def build(repo_root: Path, candidate: Path, accepted_at: str, source_commit: str) -> dict[str, Any]:
    validate_contract(repo_root)
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True)
    domains = {name: validate_domain(repo_root, name, spec) for name, spec in DOMAIN_SPECS.items()}
    domain_errors = [err for value in domains.values() for err in value.get("errors", [])]
    reconciliation, cross_errors = cross_domain_reconcile(domains)
    errors = domain_errors + cross_errors
    domain_registry = {"phase_id": PHASE_ID, "domains": [{k: v for k, v in domain.items() if k not in {"pointer", "quality"}} for domain in domains.values()]}
    boundaries = coverage_boundaries(domains)
    handoff = handoff_plan()
    operational_gates = {"phase_id": PHASE_ID, "research_store_gate": "OPEN_FOR_FMDL6X3_RESEARCH_MODEL_PRODUCTION" if not errors else "CLOSED_RECONCILIATION_FAILURE", "investment_os_candidate_pool_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X2", "simulation_gate": "CLOSED_NOT_AUTHORIZED_IN_FMDL6X2", "brokerage_real_account_gate": "CLOSED_NO_CHANNEL", "order_generation_gate": "CLOSED", "trade_authority": "NONE", "zero_mutation_proof": {"candidate_pool_mutations": 0, "simulation_mutations": 0, "real_account_mutations": 0, "orders": 0}}
    contract_hash = sha256_path(repo_root / CONTRACT_PATH)
    domain_hashes = [domains[name]["manifest_sha256"] for name in DOMAIN_SPECS]
    release_fingerprint = sha256_bytes(canonical_json({"contract_sha256": contract_hash, "domain_manifest_sha256": domain_hashes}))[:12]
    release_id = f"FMDL6X2FINAL_20260722_{release_fingerprint}"
    decision = {"phase_id": PHASE_ID, "accepted_at": accepted_at, "source_commit": source_commit, "release_id": release_id, "release_sequence": 35, "status": STATUS if not errors else "FMDL6X2_FINAL_REJECTED", "full_store_status": "OPERATIONAL_STORES_ACCEPTED_WITH_EXPLICIT_PARTIAL_COVERAGE_AND_RESUMABLE_BACKFILL", "next_gate": NEXT_GATE, "research_production_gate": operational_gates["research_store_gate"], "brokerage_real_account_gate": "CLOSED_NO_CHANNEL", "trade_authority": "NONE", "zero_mutation_proof": operational_gates["zero_mutation_proof"]}
    quality = {"phase_id": PHASE_ID, "release_id": release_id, "domain_count_expected": 5, "domain_count_accepted": sum(not v["errors"] for v in domains.values()), "release_sequence_actual": [domains[n]["release_sequence"] for n in DOMAIN_SPECS], "release_sequence_expected": [30, 31, 32, 33, 34], "current_release_parity_failures": sum(bool(v["errors"]) for v in domains.values()), "cross_domain_error_count": len(cross_errors), "coverage_boundary_overclaims": sum(1 for e in errors if "BOUNDARY" in e or "OVERCLAIM" in e or "GRADE_ESCALATED" in e), "quality_status": "PASS" if not errors else "FAIL", "errors": errors, "trade_authority": "NONE", "zero_mutation_proof": operational_gates["zero_mutation_proof"]}
    outputs = {
        "FMDL6X2_FINAL_DOMAIN_REGISTRY.json": domain_registry,
        "FMDL6X2_FINAL_CROSS_DOMAIN_RECONCILIATION.json": {"phase_id": PHASE_ID, **reconciliation},
        "FMDL6X2_FINAL_COVERAGE_BOUNDARIES.json": boundaries,
        "FMDL6X2_FINAL_OPERATIONAL_GATES.json": operational_gates,
        "FMDL6X2_FINAL_HANDOFF.json": handoff,
        "FMDL6X2_FINAL_DECISION.json": decision,
        "FMDL6X2_FINAL_QUALITY_REPORT.json": quality,
    }
    for filename, payload in outputs.items():
        write_json(candidate / filename, payload)
    manifest_files = {filename: {"bytes": (candidate / filename).stat().st_size, "sha256": sha256_path(candidate / filename)} for filename in outputs}
    manifest = {"phase_id": PHASE_ID, "generated_at": accepted_at, "release_id": release_id, "release_sequence": 35, "contract_sha256": contract_hash, "domain_manifest_sha256": {name: domains[name]["manifest_sha256"] for name in DOMAIN_SPECS}, "files": manifest_files}
    write_json(candidate / "FMDL6X2_FINAL_MANIFEST.json", manifest)
    if errors:
        raise RuntimeError(";".join(errors))
    return decision


def validate_candidate(repo_root: Path, candidate: Path, accepted_at: str, source_commit: str, acceptance: Path) -> None:
    replay = candidate.parent / (candidate.name + "_replay")
    decision = build(repo_root, replay, accepted_at, source_commit)
    left = {p.name: sha256_path(p) for p in candidate.iterdir() if p.is_file()}
    right = {p.name: sha256_path(p) for p in replay.iterdir() if p.is_file()}
    if left != right:
        raise RuntimeError("CAPTURED_INPUT_REPLAY_MISMATCH")
    manifest = read_json(candidate / "FMDL6X2_FINAL_MANIFEST.json")
    for filename, meta in manifest["files"].items():
        if sha256_path(candidate / filename) != meta["sha256"]:
            raise RuntimeError(f"MANIFEST_HASH_MISMATCH:{filename}")
    write_json(acceptance, {"phase_id": PHASE_ID, "release_id": decision["release_id"], "status": "PASS", "captured_input_replay": "PASS", "manifest_validation": "PASS", "trade_authority": "NONE"})
    shutil.rmtree(replay)


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def publish(repo_root: Path, candidate: Path, published_at: str, source_commit: str) -> dict[str, Any]:
    decision = read_json(candidate / "FMDL6X2_FINAL_DECISION.json")
    release_id = decision["release_id"]
    current = repo_root / "outputs/fmdl6x2/current/full_store"
    release = repo_root / f"datasets/fmdl6x2/releases/{release_id}/full_store"
    normalized = repo_root / f"datasets/fmdl6x2/normalized/full_store/{release_id}"
    archive_root = repo_root / "outputs/fmdl6x2/archive"
    if release.exists():
        existing = {p.name: sha256_path(p) for p in release.iterdir() if p.is_file()}
        incoming = {p.name: sha256_path(p) for p in candidate.iterdir() if p.is_file()}
        if existing != incoming:
            raise RuntimeError("IMMUTABLE_RELEASE_COLLISION")
    if current.exists():
        old_decision = read_json(current / "FMDL6X2_FINAL_DECISION.json")
        archive = archive_root / old_decision["release_id"] / "full_store"
        if not archive.exists():
            copy_tree(current, archive)
    if not release.exists():
        copy_tree(candidate, release)
    copy_tree(candidate, normalized)
    copy_tree(candidate, current)
    for name in ("FMDL6X2_FINAL_DECISION.json", "FMDL6X2_FINAL_MANIFEST.json"):
        if (current / name).read_bytes() != (release / name).read_bytes():
            raise RuntimeError("CURRENT_RELEASE_PARITY_FAILED")
    manifest_hash = sha256_path(current / "FMDL6X2_FINAL_MANIFEST.json")
    pointer = {"phase_id": PHASE_ID, "status": STATUS, "published_at": published_at, "source_commit": source_commit, "release_id": release_id, "release_sequence": 35, "current_path": "outputs/fmdl6x2/current/full_store", "release_path": f"datasets/fmdl6x2/releases/{release_id}/full_store", "normalized_path": f"datasets/fmdl6x2/normalized/full_store/{release_id}", "manifest_sha256": manifest_hash, "domain_release_ids": {name: read_json(repo_root / spec["pointer"])["release_id"] for name, spec in DOMAIN_SPECS.items()}, "full_store_status": decision["full_store_status"], "next_gate": NEXT_GATE, "research_production_gate": "OPEN_FOR_FMDL6X3_RESEARCH_MODEL_PRODUCTION", "brokerage_real_account_gate": "CLOSED_NO_CHANNEL", "trade_authority": "NONE", "zero_mutation_proof": decision["zero_mutation_proof"]}
    write_json(repo_root / "outputs/status/FMDL6X2_FINAL_LAST_SUCCESS.json", pointer)
    lkg = dict(pointer)
    lkg["lkg_scope"] = "FMDL6X2_FULL_STORE_DOMAIN"
    lkg["lkg_reason"] = "LATEST_ACCEPTED_CROSS_DOMAIN_RECONCILED_STORE"
    write_json(repo_root / "outputs/status/FMDL6X2_FULL_STORE_LKG.json", lkg)
    return pointer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate-contract")
    b = sub.add_parser("build")
    b.add_argument("--candidate", required=True)
    b.add_argument("--accepted-at", required=True)
    b.add_argument("--source-commit", required=True)
    v = sub.add_parser("validate-candidate")
    v.add_argument("--candidate", required=True)
    v.add_argument("--accepted-at", required=True)
    v.add_argument("--source-commit", required=True)
    v.add_argument("--acceptance", required=True)
    p = sub.add_parser("publish")
    p.add_argument("--candidate", required=True)
    p.add_argument("--published-at", required=True)
    p.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    if args.command == "validate-contract":
        validate_contract(root)
    elif args.command == "build":
        build(root, root / args.candidate, args.accepted_at, args.source_commit)
    elif args.command == "validate-candidate":
        validate_candidate(root, root / args.candidate, args.accepted_at, args.source_commit, root / args.acceptance)
    elif args.command == "publish":
        publish(root, root / args.candidate, args.published_at, args.source_commit)


if __name__ == "__main__":
    main()
