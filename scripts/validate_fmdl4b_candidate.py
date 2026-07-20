from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd

from config.fmdl4b_research_profiles import PROFILE_PAYLOAD_SHA256
from scripts import fmdl4b_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl4b_candidate_research.json"


def main() -> int:
    cfg = core.read_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    decision = core.read_json(candidate / "FMDL4B_DECISION.json")
    records = core.load_jsonl(candidate / "FMDL4B_PUBLIC_EQUITY_RESEARCH_OBJECTS.jsonl")
    object_frame = pd.read_csv(candidate / "FMDL4B_PUBLIC_EQUITY_RESEARCH_OBJECTS.csv", dtype={"symbol": str})
    stages = pd.read_csv(candidate / "FMDL4B_RESEARCH_STAGE_REGISTRY.csv", dtype={"symbol": str})
    decisions = pd.read_csv(candidate / "FMDL4B_GRADUATION_DECISIONS.csv", dtype={"symbol": str})
    source_ledger = core.read_json(candidate / "FMDL4B_SOURCE_LEDGER.json")
    raw_score_proof = core.read_json(candidate / "FMDL4B_NO_RAW_SCORE_PROMOTION_PROOF.json")
    mutation_proof = core.read_json(candidate / "FMDL4B_ZERO_STATE_MUTATION_PROOF.json")

    failures: list[str] = []
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        failures.append("DECISION")
    if len(stages) != cfg["research_cohort"]["required_total_registry_count"] or stages["symbol"].duplicated().any():
        failures.append("STAGE_REGISTRY")
    if len(decisions) != cfg["research_cohort"]["required_total_registry_count"] or decisions["symbol"].duplicated().any():
        failures.append("GRADUATION_DECISIONS")
    if len(records) != cfg["research_cohort"]["required_active_cohort_count"]:
        failures.append("RESEARCH_OBJECT_COUNT")
    if len(object_frame) != len(records) or object_frame["symbol"].duplicated().any():
        failures.append("RESEARCH_OBJECT_TABLE")

    record_errors = sum(bool(core.validate_research_object(record, cfg)) for record in records)
    if record_errors:
        failures.append("RESEARCH_OBJECT_SCHEMA")
    by_symbol = {str(record["symbol"]): record for record in records}
    row_binding_errors = 0
    for row in object_frame.to_dict(orient="records"):
        record = by_symbol.get(str(row["symbol"]))
        if not record or row.get("research_id") != record.get("research_id") or row.get("semantic_hash") != record.get("semantic_hash"):
            row_binding_errors += 1
    if row_binding_errors:
        failures.append("OBJECT_ROW_BINDING")

    evidence_registry = pd.read_csv(ROOT / cfg["inputs"]["research_priority_registry"], dtype={"symbol": str})
    evidence_ids = set(evidence_registry["evidence_id"].astype(str))
    unknown_evidence = int((~decisions["evidence_id"].astype(str).isin(evidence_ids)).sum())
    if unknown_evidence:
        failures.append("EVIDENCE_BINDING")
    active_symbols = set(evidence_registry.loc[
        evidence_registry["research_priority"] == cfg["research_cohort"]["active_priority"], "symbol"
    ].astype(str))
    if set(by_symbol) != active_symbols:
        failures.append("ACTIVE_COHORT_IDENTITY")

    decision_counts = Counter(decisions["graduation_decision"])
    if int(decision_counts["GRADUATED"]) < cfg["graduation_policy"]["minimum_graduated_count"]:
        failures.append("MINIMUM_GRADUATED_COUNT")
    non_active = decisions.loc[~decisions["formal_research_object_created"].astype(bool)]
    if not (non_active["graduation_decision"] == "DEFERRED").all():
        failures.append("NON_ACTIVE_MECHANICAL_REJECTION")
    if int(raw_score_proof.get("raw_score_only_decision_count", -1)) != 0:
        failures.append("RAW_SCORE_ONLY_DECISION")

    mutation_count = sum(int(mutation_proof.get(key, 0)) for key in [
        "candidate_pool_mutation_count", "simulation_mutation_count", "real_account_mutation_count",
        "trade_register_mutation_count", "position_thesis_mutation_count", "order_generation_count",
    ])
    mutation_count += int(stages["state_mutation_authorized"].astype(bool).sum())
    if mutation_count:
        failures.append("STATE_MUTATION")

    trade_authority_errors = int((stages["trade_authority"].astype(str) != "NONE").sum())
    trade_authority_errors += int((decisions["trade_authority"].astype(str) != "NONE").sum())
    trade_authority_errors += int((object_frame["trade_authority"].astype(str) != "NONE").sum())
    for payload in [decision, source_ledger, raw_score_proof, mutation_proof]:
        trade_authority_errors += int(payload.get("trade_authority") != "NONE")
    if trade_authority_errors:
        failures.append("TRADE_AUTHORITY")

    object_hash = core.semantic_frame_hash(object_frame, sort_by=("screen_rank", "symbol"))
    stage_hash = core.semantic_frame_hash(stages, sort_by=("overall_rank", "symbol"))
    decisions_hash = core.semantic_frame_hash(decisions, sort_by=("overall_rank", "symbol"))
    expected_hashes = decision.get("semantic_hashes", {})
    if object_hash != expected_hashes.get("research_objects"):
        failures.append("OBJECT_SEMANTIC_HASH")
    if stage_hash != expected_hashes.get("stage_registry"):
        failures.append("STAGE_SEMANTIC_HASH")
    if decisions_hash != expected_hashes.get("graduation_decisions"):
        failures.append("DECISION_SEMANTIC_HASH")
    if source_ledger.get("profile_payload_sha256") != PROFILE_PAYLOAD_SHA256:
        failures.append("PROFILE_PAYLOAD_IDENTITY")

    source_errors = 0
    if int(source_ledger.get("source_count", 0)) < len(records) * cfg["research_cohort"]["minimum_public_source_count"]:
        source_errors += 1
    for source in source_ledger.get("sources", []):
        if not str(source.get("source_date", "")).startswith(str(cfg["research_cohort"]["required_current_source_year"])):
            source_errors += 1
        if not all(source.get(key) for key in ["source_id", "title", "source_type", "url", "symbol"]):
            source_errors += 1
    if source_errors:
        failures.append("SOURCE_LEDGER")

    metrics = {
        **decision.get("metrics", {}),
        "independent_research_object_hash": object_hash,
        "independent_stage_registry_hash": stage_hash,
        "independent_graduation_decisions_hash": decisions_hash,
        "research_object_schema_error_count": record_errors,
        "object_row_binding_error_count": row_binding_errors,
        "unknown_evidence_binding_count": unknown_evidence,
        "state_mutation_error_count_independent": mutation_count,
        "trade_authority_error_count_independent": trade_authority_errors,
        "source_ledger_error_count": source_errors,
    }
    checks = [
        {"check_id": "DECISION_AND_COUNTS", "status": "PASS" if not {"DECISION", "STAGE_REGISTRY", "GRADUATION_DECISIONS", "RESEARCH_OBJECT_COUNT", "RESEARCH_OBJECT_TABLE", "MINIMUM_GRADUATED_COUNT"}.intersection(failures) else "FAIL"},
        {"check_id": "RESEARCH_OBJECT_SCHEMA_AND_BINDING", "status": "PASS" if not {"RESEARCH_OBJECT_SCHEMA", "OBJECT_ROW_BINDING", "EVIDENCE_BINDING", "ACTIVE_COHORT_IDENTITY"}.intersection(failures) else "FAIL"},
        {"check_id": "PUBLIC_SOURCE_LEDGER", "status": "PASS" if "SOURCE_LEDGER" not in failures else "FAIL"},
        {"check_id": "NO_RAW_SCORE_PROMOTION", "status": "PASS" if not {"RAW_SCORE_ONLY_DECISION", "NON_ACTIVE_MECHANICAL_REJECTION"}.intersection(failures) else "FAIL"},
        {"check_id": "SEMANTIC_HASHES_AND_PROFILE_IDENTITY", "status": "PASS" if not {"OBJECT_SEMANTIC_HASH", "STAGE_SEMANTIC_HASH", "DECISION_SEMANTIC_HASH", "PROFILE_PAYLOAD_IDENTITY"}.intersection(failures) else "FAIL"},
        {"check_id": "ZERO_STATE_MUTATION", "status": "PASS" if "STATE_MUTATION" not in failures else "FAIL"},
        {"check_id": "ZERO_TRADE_AUTHORITY", "status": "PASS" if "TRADE_AUTHORITY" not in failures else "FAIL"},
    ]
    validation = {
        "validation_version": "1.0.0",
        "program_id": "FMDL-4B",
        "release_id": decision.get("release_id"),
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": sorted(set(failures)),
        "checks": checks,
        "metrics": metrics,
        "controlled_limitations": cfg["controlled_limitations"],
        "graduated_meaning": cfg["graduation_policy"]["graduated_meaning"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    core.write_json(candidate / "FMDL4B_VALIDATION.json", validation)
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
