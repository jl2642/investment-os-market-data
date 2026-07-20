from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from config.fmdl4b_research_profiles import PROFILE_PAYLOAD_SHA256, load_profiles
from scripts import fmdl4b_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl4b_candidate_research.json"
TZ = ZoneInfo("Asia/Shanghai")


def verify_entry(cfg: dict) -> tuple[list[str], dict]:
    errors: list[str] = []
    entry = cfg["entry_gate"]
    required = [entry["pointer_path"], entry["release_path"], *cfg["inputs"].values()]
    missing = [path for path in required if not (ROOT / path).exists()]
    if missing:
        return [f"MISSING_INPUT:{path}" for path in missing], {}
    pointer = core.read_json(ROOT / entry["pointer_path"])
    release = core.read_json(ROOT / entry["release_path"])
    if pointer.get("status") != entry["required_status"]:
        errors.append("FMDL4A_POINTER_STATUS")
    if pointer.get("next_gate") != entry["required_next_gate"]:
        errors.append("FMDL4A_POINTER_NEXT_GATE")
    if pointer.get("release_id") != release.get("release_id"):
        errors.append("FMDL4A_RELEASE_IDENTITY")
    if pointer.get("trade_authority") != "NONE" or release.get("trade_authority") != "NONE":
        errors.append("FMDL4A_TRADE_AUTHORITY")
    binding = core.read_json(ROOT / cfg["inputs"]["binding_state"])
    if any(int(binding.get(key, 0)) != 0 for key in [
        "candidate_pool_mutation_count", "simulation_mutation_count", "real_account_mutation_count",
        "base_state_mutation_count", "existing_path_replacement_count",
    ]):
        errors.append("FMDL4A_MUTATION_BASELINE")
    return errors, {
        "fmdl4a_release_id": release.get("release_id"),
        "fmdl4a_base_sha256": release.get("external_canonical_base", {}).get("package_sha256"),
        "fmdl4a_candidate_release_sequence": release.get("candidate_release_sequence"),
        "fmdl4a_evidence_envelope_hash": release.get("semantic_hashes", {}).get("evidence_envelope"),
        "fmdl4a_registry_hash": release.get("semantic_hashes", {}).get("research_priority_registry"),
        "source_release_ids": release.get("source_release_ids", {}),
    }


def profile_payload_hash(profiles: list[dict]) -> str:
    payload = json.dumps(core.canonical(profiles), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def flatten_research_objects(records: list[dict]) -> pd.DataFrame:
    rows: list[dict] = []
    for record in records:
        rows.append({
            "research_id": record["research_id"],
            "symbol": record["symbol"],
            "name": record["name"],
            "as_of": record["as_of"],
            "research_version": record["research_version"],
            "research_stage": record["research_stage"],
            "graduation_decision": record["graduation_decision"],
            "business_model": record["business_model"],
            "competitive_position": record["competitive_position"],
            "owner_quality": record["owner_quality"],
            "earnings_drivers_json": json.dumps(record["earnings_drivers"], ensure_ascii=False, sort_keys=True),
            "catalysts_json": json.dumps(record["catalysts"], ensure_ascii=False, sort_keys=True),
            "risks_json": json.dumps(record["risks"], ensure_ascii=False, sort_keys=True),
            "variant_perception": record["variant_perception"],
            "why_now": record["why_now"],
            "first_rejection": record["first_rejection"],
            "what_would_make_investable": record["what_would_make_investable"],
            "prove_kill_checks_json": json.dumps(record["prove_kill_checks"], ensure_ascii=False, sort_keys=True),
            "decision_reason_codes_json": json.dumps(record["decision_reason_codes"], ensure_ascii=False, sort_keys=True),
            "graduation_condition": record["graduation_condition"],
            "next_workflow": record["next_workflow"],
            "evidence_ids_json": json.dumps(record["evidence_ids"], ensure_ascii=False, sort_keys=True),
            "public_sources_json": json.dumps(record["public_sources"], ensure_ascii=False, sort_keys=True),
            "source_count": record["source_count"],
            "screen_rank": record["screen_rank"],
            "screen_research_priority": record["screen_research_priority"],
            "research_status": record["research_status"],
            "state_mutation_authorized": record["state_mutation_authorized"],
            "authority": record["authority"],
            "trade_authority": record["trade_authority"],
            "semantic_hash": record["semantic_hash"],
        })
    return pd.DataFrame(rows).sort_values(["screen_rank", "symbol"], kind="stable").reset_index(drop=True)


def main() -> int:
    cfg = core.read_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True)

    started = datetime.now(TZ)
    entry_errors, bindings = verify_entry(cfg)
    if entry_errors and any(error.startswith("MISSING_INPUT") for error in entry_errors):
        core.write_json(candidate / "FMDL4B_DECISION.json", {
            "program_id": "FMDL-4B",
            "status": "FMDL4B_CANDIDATE_RESEARCH_AND_GRADUATION_REJECTED",
            "hard_failures": entry_errors,
            "trade_authority": "NONE",
        })
        raise SystemExit("FMDL-4B required inputs missing")

    registry = pd.read_csv(ROOT / cfg["inputs"]["research_priority_registry"], dtype={"symbol": str})
    envelopes = core.load_jsonl(ROOT / cfg["inputs"]["evidence_envelope_jsonl"])
    envelope_by_symbol = {str(item["symbol"]): item for item in envelopes}
    profiles = load_profiles()
    profiles_hash = profile_payload_hash(profiles)
    profile_by_symbol = {str(item["symbol"]): item for item in profiles}

    active = registry[registry["research_priority"] == cfg["research_cohort"]["active_priority"]].copy()
    active_symbols = set(active["symbol"].astype(str))
    profile_symbols = set(profile_by_symbol)
    registry_symbols = set(registry["symbol"].astype(str))
    missing_active_profiles = sorted(active_symbols - profile_symbols)
    unknown_profile_symbols = sorted(profile_symbols - active_symbols)
    missing_evidence_symbols = sorted(registry_symbols - set(envelope_by_symbol))

    as_of = str(registry["as_of_date"].iloc[0])
    research_version = f"FMDL4B-RV1-{as_of.replace('-', '')}"
    registry_index = registry.set_index("symbol").to_dict(orient="index")
    research_objects: list[dict] = []
    object_validation_error_count = 0
    source_requirement_error_count = 0
    raw_score_only_decision_count = 0

    for symbol in sorted(active_symbols):
        if symbol not in profile_by_symbol or symbol not in envelope_by_symbol:
            continue
        profile = profile_by_symbol[symbol]
        record = core.research_object(
            profile,
            registry_index[symbol],
            envelope_by_symbol[symbol],
            research_version=research_version,
            authority=cfg["authority"],
        )
        errors = core.validate_research_object(record, cfg)
        object_validation_error_count += int(bool(errors))
        source_requirement_error_count += sum(error in {"SOURCE_COUNT", "SOURCE_SHAPE", "SOURCE_FRESHNESS"} for error in errors)
        raw_score_only_decision_count += int(core.raw_score_only_decision(profile))
        research_objects.append(record)

    object_by_symbol = {item["symbol"]: item for item in research_objects}
    stage_rows: list[dict] = []
    decision_rows: list[dict] = []
    for row in registry.sort_values(["overall_rank", "symbol"], kind="stable").to_dict(orient="records"):
        symbol = str(row["symbol"])
        if symbol in object_by_symbol:
            obj = object_by_symbol[symbol]
            stage = obj["research_stage"]
            decision = obj["graduation_decision"]
            reason_codes = obj["decision_reason_codes"]
            research_id = obj["research_id"]
            source_count = obj["source_count"]
            research_status = obj["research_status"]
            next_workflow = obj["next_workflow"]
            formal_object_created = True
        else:
            stage = cfg["stage_model"]["non_active_default_stage"]
            decision = cfg["stage_model"]["non_active_default_decision"]
            reason_codes = [cfg["stage_model"]["non_active_reason_code"]]
            research_id = ""
            source_count = 0
            research_status = "DEFERRED_BEFORE_FORMAL_RESEARCH"
            next_workflow = "idea-generation"
            formal_object_created = False
        common = {
            "symbol": symbol,
            "name": row["name"],
            "overall_rank": int(row["overall_rank"]),
            "screen_research_priority": row["research_priority"],
            "evidence_id": row["evidence_id"],
            "research_id": research_id,
            "research_stage": stage,
            "graduation_decision": decision,
            "decision_reason_codes_json": json.dumps(reason_codes, ensure_ascii=False, sort_keys=True),
            "formal_research_object_created": formal_object_created,
            "source_count": source_count,
            "research_status": research_status,
            "next_workflow": next_workflow,
            "candidate_pool_mutation_authorized": False,
            "simulation_mutation_authorized": False,
            "real_account_mutation_authorized": False,
            "state_mutation_authorized": False,
            "authority": cfg["authority"],
            "trade_authority": "NONE",
        }
        stage_rows.append(common)
        decision_rows.append({
            **common,
            "decision_scope": "RESEARCH_GRADUATION_ONLY",
            "graduated_meaning": cfg["graduation_policy"]["graduated_meaning"] if decision == "GRADUATED" else "",
        })

    stage_registry = pd.DataFrame(stage_rows)
    decisions = pd.DataFrame(decision_rows)
    object_frame = flatten_research_objects(research_objects)
    source_ledger = {
        "ledger_version": "1.0.0",
        "research_version": research_version,
        "profile_payload_sha256": profiles_hash,
        "sources": sorted(
            [
                {**source, "symbol": profile["symbol"], "name": profile["name"]}
                for profile in profiles
                for source in profile["public_sources"]
            ],
            key=lambda item: (item["symbol"], item["source_date"], item["source_id"]),
        ),
        "source_count": sum(len(profile["public_sources"]) for profile in profiles),
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    raw_score_proof = {
        "proof_version": "1.0.0",
        "active_research_object_count": len(research_objects),
        "raw_score_only_decision_count": raw_score_only_decision_count,
        "evidence": {
            "all_active_objects_have_narrative_fields": raw_score_only_decision_count == 0,
            "all_active_objects_have_public_sources": all(len(profile["public_sources"]) >= cfg["research_cohort"]["minimum_public_source_count"] for profile in profiles),
            "non_active_names_are_deferred_not_rejected": bool((decisions.loc[~decisions["formal_research_object_created"], "graduation_decision"] == "DEFERRED").all()),
            "graduated_is_research_case_ready_only": True,
        },
        "prohibited_inference": "SCREEN_SCORE_OR_RANK_CANNOT_ALONE_GRADUATE_REJECT_OR_AUTHORIZE_INVESTMENT_STATE_CHANGE",
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    mutation_proof = {
        "proof_version": "1.0.0",
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "trade_register_mutation_count": 0,
        "position_thesis_mutation_count": 0,
        "order_generation_count": 0,
        "trade_authority": "NONE",
    }

    core.write_jsonl(candidate / "FMDL4B_PUBLIC_EQUITY_RESEARCH_OBJECTS.jsonl", research_objects)
    object_frame.to_csv(candidate / "FMDL4B_PUBLIC_EQUITY_RESEARCH_OBJECTS.csv", index=False)
    stage_registry.to_csv(candidate / "FMDL4B_RESEARCH_STAGE_REGISTRY.csv", index=False)
    decisions.to_csv(candidate / "FMDL4B_GRADUATION_DECISIONS.csv", index=False)
    core.write_json(candidate / "FMDL4B_SOURCE_LEDGER.json", source_ledger)
    core.write_json(candidate / "FMDL4B_NO_RAW_SCORE_PROMOTION_PROOF.json", raw_score_proof)
    core.write_json(candidate / "FMDL4B_ZERO_STATE_MUTATION_PROOF.json", mutation_proof)

    decision_counts = Counter(decisions["graduation_decision"])
    duplicate_registry = int(registry["symbol"].duplicated().sum())
    duplicate_objects = len(research_objects) - len(object_by_symbol)
    state_mutation_count = int(stage_registry[[
        "candidate_pool_mutation_authorized", "simulation_mutation_authorized",
        "real_account_mutation_authorized", "state_mutation_authorized",
    ]].astype(bool).sum().sum())
    trade_authority_error_count = int((stage_registry["trade_authority"] != "NONE").sum()) + int((object_frame["trade_authority"] != "NONE").sum())
    metrics = {
        "total_registry_count": len(registry),
        "active_cohort_count": len(active),
        "formal_research_object_count": len(research_objects),
        "decision_count": len(decisions),
        "graduated_count": int(decision_counts["GRADUATED"]),
        "deferred_count": int(decision_counts["DEFERRED"]),
        "rejected_count": int(decision_counts["REJECTED"]),
        "duplicate_registry_symbol_count": duplicate_registry,
        "duplicate_research_object_symbol_count": duplicate_objects,
        "missing_active_profile_count": len(missing_active_profiles),
        "unknown_profile_symbol_count": len(unknown_profile_symbols),
        "missing_evidence_binding_count": len(missing_evidence_symbols),
        "research_object_validation_error_count": object_validation_error_count,
        "source_requirement_error_count": source_requirement_error_count,
        "raw_score_only_decision_count": raw_score_only_decision_count,
        "state_mutation_count": state_mutation_count,
        "trade_authority_error_count": trade_authority_error_count,
        "public_source_count": source_ledger["source_count"],
        "elapsed_seconds": round((datetime.now(TZ) - started).total_seconds(), 4),
    }
    checks = {
        "ENTRY_GATE": not entry_errors,
        "TOTAL_REGISTRY_COUNT": len(registry) == cfg["research_cohort"]["required_total_registry_count"],
        "ACTIVE_COHORT_COUNT": len(active) == cfg["research_cohort"]["required_active_cohort_count"],
        "FORMAL_RESEARCH_OBJECT_COUNT": len(research_objects) == cfg["research_cohort"]["required_active_cohort_count"],
        "ALL_100_DECISIONS": len(decisions) == cfg["research_cohort"]["required_total_registry_count"],
        "MINIMUM_GRADUATED_COUNT": metrics["graduated_count"] >= cfg["graduation_policy"]["minimum_graduated_count"],
        "PROFILE_AND_EVIDENCE_BINDING": not missing_active_profiles and not unknown_profile_symbols and not missing_evidence_symbols,
        "RESEARCH_OBJECT_VALIDATION": object_validation_error_count == 0,
        "PUBLIC_SOURCE_REQUIREMENTS": source_requirement_error_count == 0,
        "NO_RAW_SCORE_ONLY_DECISIONS": raw_score_only_decision_count == 0,
        "ZERO_STATE_MUTATION": state_mutation_count == 0,
        "ZERO_TRADE_AUTHORITY": trade_authority_error_count == 0,
        "PROFILE_PAYLOAD_IDENTITY": profiles_hash == PROFILE_PAYLOAD_SHA256,
    }
    hard_failures = list(entry_errors) + [check for check, passed in checks.items() if not passed]
    persisted_object_frame = pd.read_csv(candidate / "FMDL4B_PUBLIC_EQUITY_RESEARCH_OBJECTS.csv", dtype={"symbol": str})
    persisted_stage_registry = pd.read_csv(candidate / "FMDL4B_RESEARCH_STAGE_REGISTRY.csv", dtype={"symbol": str})
    persisted_decisions = pd.read_csv(candidate / "FMDL4B_GRADUATION_DECISIONS.csv", dtype={"symbol": str})
    semantic_hashes = {
        "research_objects": core.semantic_frame_hash(persisted_object_frame, sort_by=("screen_rank", "symbol")),
        "stage_registry": core.semantic_frame_hash(persisted_stage_registry, sort_by=("overall_rank", "symbol")),
        "graduation_decisions": core.semantic_frame_hash(persisted_decisions, sort_by=("overall_rank", "symbol")),
        "source_ledger": core.stable_hash(source_ledger),
        "raw_score_proof": core.stable_hash(raw_score_proof),
        "mutation_proof": core.stable_hash(mutation_proof),
        "profile_payload": profiles_hash,
    }
    composition_hash = core.stable_hash({
        "bindings": bindings,
        "semantic_hashes": semantic_hashes,
        "decision_counts": dict(sorted(decision_counts.items())),
        "research_version": research_version,
    })
    release_id = f"FMDL4B_{as_of.replace('-', '')}_{composition_hash[:12]}"
    decision_payload = {
        "decision_version": "1.0.0",
        "program_id": "FMDL-4B",
        "release_id": release_id,
        "research_version": research_version,
        "generated_at": started.isoformat(timespec="seconds"),
        "status": cfg["exit_status"] if not hard_failures else "FMDL4B_CANDIDATE_RESEARCH_AND_GRADUATION_REJECTED",
        "hard_failures": hard_failures,
        "checks": [{"check_id": key, "status": "PASS" if value else "FAIL"} for key, value in checks.items()],
        "metrics": metrics,
        "bindings": bindings,
        "semantic_hashes": semantic_hashes,
        "controlled_limitations": cfg["controlled_limitations"],
        "graduated_meaning": cfg["graduation_policy"]["graduated_meaning"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    core.write_json(candidate / "FMDL4B_DECISION.json", decision_payload)
    print(json.dumps(decision_payload, ensure_ascii=False, indent=2))
    if hard_failures:
        raise SystemExit("FMDL-4B candidate rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
