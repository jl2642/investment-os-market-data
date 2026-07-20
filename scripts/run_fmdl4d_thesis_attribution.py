from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from scripts import fmdl4d_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl4d_thesis_attribution.json"
TZ = ZoneInfo("Asia/Shanghai")


def json_text(value):
    return json.dumps(core.canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def build_failure_taxonomy(cfg: dict) -> dict:
    definitions = {
        "NO_OBSERVATION": "No accepted exposure or approved entry exists; investment outcome attribution is unavailable.",
        "SELECTION_ERROR": "The selected issuer or security was inferior to available alternatives after comparable evidence and mandate constraints.",
        "RESEARCH_ERROR": "The original operating, accounting, competitive or governance thesis was materially wrong or incomplete.",
        "VALUATION_ERROR": "The company thesis may be intact, but the entry price or assumed multiple failed to preserve the required risk/reward.",
        "TIMING_ERROR": "The thesis horizon or catalyst timing was wrong despite an otherwise valid company and valuation case.",
        "POSITION_SIZING_ERROR": "Exposure magnitude was inconsistent with evidence quality, downside, liquidity or portfolio concentration.",
        "DATA_QUALITY_ERROR": "Stale, incomplete, inconsistent or incorrectly mapped data drove the conclusion.",
        "EXECUTION_ERROR": "Order, fee, liquidity, operational or implementation effects impaired the result independently of thesis quality.",
        "EXOGENOUS_SHOCK": "A material external event outside the underwritten range dominated the outcome.",
        "THESIS_DRIFT": "The position or recommendation persisted after the original thesis, catalysts or kill conditions changed.",
    }
    return {
        "taxonomy_version": "1.0.0",
        "classifications": [
            {"failure_classification": item, "definition": definitions[item]}
            for item in cfg["failure_taxonomy"]
        ],
        "classification_rule": "CLASSIFY_ONLY_AFTER_OBSERVABLE_EVIDENCE_AND_SEPARATE_COMPANY_THESIS_SECURITY_READINESS_POSITION_AND_EXECUTION",
        "automatic_strategy_rule_mutation": False,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }


def main() -> int:
    cfg = core.read_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True)
    overlay = candidate / cfg["tracking"]["overlay_namespace"]
    core_static = overlay / "CORE_STATIC"
    state_current = overlay / "STATE_CURRENT"
    evidence = overlay / "EVIDENCE"
    for path in [core_static, state_current, evidence]:
        path.mkdir(parents=True)

    started = datetime.now(TZ)
    hard_failures: list[str] = []
    entry = cfg["entry_gate"]
    inputs = cfg["inputs"]
    required_paths = [entry["pointer_path"], entry["release_path"], *inputs.values()]
    missing_paths = [path for path in required_paths if not (ROOT / path).exists()]
    if missing_paths:
        hard_failures.extend(f"MISSING_INPUT:{path}" for path in missing_paths)
        decision = {
            "decision_version": "1.0.0",
            "program_id": "FMDL-4D",
            "status": "FMDL4D_THESIS_ATTRIBUTION_AND_FEEDBACK_REJECTED",
            "hard_failures": hard_failures,
            "trade_authority": "NONE",
        }
        core.write_json(candidate / "FMDL4D_DECISION.json", decision)
        raise SystemExit("FMDL-4D missing inputs")

    pointer = core.read_json(ROOT / entry["pointer_path"])
    fmdl4c_release = core.read_json(ROOT / entry["release_path"])
    if pointer.get("status") != entry["required_status"]:
        hard_failures.append("ENTRY_STATUS")
    if pointer.get("next_gate") != entry["required_next_gate"]:
        hard_failures.append("ENTRY_NEXT_GATE")
    if pointer.get("release_id") != fmdl4c_release.get("release_id"):
        hard_failures.append("ENTRY_RELEASE_IDENTITY")
    if pointer.get("trade_authority") != "NONE" or fmdl4c_release.get("trade_authority") != "NONE":
        hard_failures.append("ENTRY_TRADE_AUTHORITY")

    queue = pd.read_csv(ROOT / inputs["reentry_queue"], dtype={"symbol": str})
    research = pd.read_csv(ROOT / inputs["research_objects"], dtype={"symbol": str})
    decisions = pd.read_csv(ROOT / inputs["graduation_decisions"], dtype={"symbol": str})
    queue = queue.sort_values(["priority", "symbol"], kind="stable").reset_index(drop=True)
    research_index = research.set_index("symbol").to_dict(orient="index")
    graduated = decisions[decisions["graduation_decision"] == "GRADUATED"].copy()

    missing_research = sorted(set(queue["symbol"]) - set(research_index))
    graduated_symbol_mismatch = sorted(set(queue["symbol"]) ^ set(graduated["symbol"]))

    catalyst_rows: list[dict] = []
    prove_kill_rows: list[dict] = []
    thesis_records: list[dict] = []
    attribution_rows: list[dict] = []
    decision_log_rows: list[dict] = []

    for queue_row in queue.to_dict(orient="records"):
        symbol = str(queue_row["symbol"])
        research_row = research_index.get(symbol)
        if research_row is None:
            continue
        symbol_catalysts = core.build_catalyst_rows(queue_row, research_row, cfg)
        symbol_prove_kill = core.build_prove_kill_rows(queue_row, research_row, cfg)
        catalyst_rows.extend(symbol_catalysts)
        prove_kill_rows.extend(symbol_prove_kill)
        thesis = core.build_thesis_record(queue_row, research_row, symbol_catalysts, symbol_prove_kill, cfg)
        thesis_records.append(thesis)
        attribution = core.build_attribution_row(queue_row, research_row, cfg)
        attribution_rows.append(attribution)
        decision_log_rows.append({
            "log_id": f"FMDL4D-LOG-{symbol}-{thesis['semantic_hash'][:12]}",
            "symbol": symbol,
            "name": str(queue_row["name"]),
            "thesis_version": cfg["tracking"]["thesis_version"],
            "operation": "APPEND",
            "decision_type": "THESIS_BASELINE_CREATED",
            "company_thesis_status": thesis["company_thesis_status"],
            "security_thesis_readiness": thesis["security_thesis_readiness"],
            "position_action": thesis["position_action"],
            "decision_reason": "CREATE_APPEND_ONLY_TRACKING_BASELINE_WITHOUT_POSITION_OR_TRADE_ACTION",
            "prior_record_deleted": False,
            "rule_mutation_applied": False,
            "candidate_pool_mutation_count": 0,
            "simulation_mutation_count": 0,
            "real_account_mutation_count": 0,
            "order_generation_count": 0,
            "authority": cfg["authority"],
            "trade_authority": "NONE",
        })

    feedback_rows = []
    for proposal in cfg["feedback_proposals"]:
        feedback_rows.append({
            **proposal,
            "rule_mutation_applied": False,
            "human_approval_required": True,
            "regression_required": True,
            "automatic_portfolio_action": False,
            "authority": cfg["authority"],
            "trade_authority": "NONE",
        })

    thesis_validation_error_count = sum(bool(core.validate_thesis_record(record, cfg)) for record in thesis_records)
    thesis_frame = pd.DataFrame([
        {
            "thesis_record_id": record["thesis_record_id"],
            "symbol": record["symbol"],
            "name": record["name"],
            "thesis_version": record["thesis_version"],
            "source_as_of": record["source_as_of"],
            "company_thesis_status": record["company_thesis_status"],
            "security_thesis_readiness": record["security_thesis_readiness"],
            "position_action": record["position_action"],
            "portfolio_role": record["portfolio_role"],
            "research_id": record["research_id"],
            "transition_id": record["transition_id"],
            "evidence_ids_json": json_text(record["evidence_ids"]),
            "catalyst_ids_json": json_text(record["catalyst_ids"]),
            "prove_kill_ids_json": json_text(record["prove_kill_ids"]),
            "feedback_proposal_ids_json": json_text(record["feedback_proposal_ids"]),
            "return_attribution_status": record["return_attribution"]["status"],
            "failure_classification": record["decision_attribution"]["failure_classification"],
            "maximum_review_date": record["next_review_gate"]["maximum_review_date"],
            "semantic_hash": record["semantic_hash"],
            "authority": record["authority"],
            "trade_authority": record["trade_authority"],
        }
        for record in thesis_records
    ]).sort_values("symbol").reset_index(drop=True)
    catalyst_frame = pd.DataFrame(catalyst_rows).sort_values(["symbol", "catalyst_id"]).reset_index(drop=True)
    prove_kill_frame = pd.DataFrame(prove_kill_rows).sort_values(["symbol", "prove_kill_id"]).reset_index(drop=True)
    attribution_frame = pd.DataFrame(attribution_rows).sort_values("symbol").reset_index(drop=True)
    decision_log_frame = pd.DataFrame(decision_log_rows).sort_values("symbol").reset_index(drop=True)

    tracking_contract = {
        "contract_version": "1.0.0",
        "program_id": "FMDL-4D",
        "status": "ACTIVE_APPEND_ONLY_THESIS_TRACKING",
        "state_domain": cfg["tracking"]["state_domain"],
        "thesis_version": cfg["tracking"]["thesis_version"],
        "company_thesis_security_thesis_position_separation": True,
        "current_price_required_for_security_readiness": True,
        "observable_exposure_required_for_return_attribution": True,
        "append_only_decision_log": True,
        "automatic_rule_mutation": False,
        "automatic_portfolio_action": False,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    feedback_firewall = {
        "firewall_version": "1.0.0",
        "single_stock_rule_change_allowed": False,
        "single_period_rule_change_allowed": False,
        "minimum_requirements": [
            "MULTIPLE_INDEPENDENT_OBSERVATIONS",
            "EXPLICIT_FAILURE_CLASSIFICATION",
            "REGRESSION_TESTING",
            "HUMAN_APPROVAL",
        ],
        "proposal_statuses_allowed": ["PROPOSED_NOT_APPLIED", "GOVERNANCE_FIREWALL_ACTIVE"],
        "rule_mutation_count": 0,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    failure_taxonomy = build_failure_taxonomy(cfg)
    source_binding = {
        "binding_version": "1.0.0",
        "fmdl4c_release_id": fmdl4c_release.get("release_id"),
        "fmdl4c_composition_sequence": fmdl4c_release.get("composition_sequence"),
        "fmdl4b_release_id": fmdl4c_release.get("fmdl4b_research_release_id"),
        "fmdl4a_release_id": fmdl4c_release.get("release5_adapter_release_id"),
        "external_base_sha256": fmdl4c_release.get("external_canonical_base", {}).get("package_sha256"),
        "source_as_of": sorted(set(thesis_frame["source_as_of"].astype(str))),
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }

    core.write_json(core_static / "FMDL4D_TRACKING_CONTRACT.json", tracking_contract)
    core.write_json(core_static / "FMDL4D_FEEDBACK_FIREWALL.json", feedback_firewall)
    core.write_json(core_static / "FMDL4D_FAILURE_TAXONOMY.json", failure_taxonomy)
    core.write_jsonl(state_current / "FMDL4D_THESIS_RECORDS.jsonl", thesis_records)
    thesis_frame.to_csv(state_current / "FMDL4D_THESIS_RECORDS.csv", index=False)
    catalyst_frame.to_csv(state_current / "FMDL4D_CATALYST_REGISTRY.csv", index=False)
    prove_kill_frame.to_csv(state_current / "FMDL4D_PROVE_KILL_REGISTRY.csv", index=False)
    attribution_frame.to_csv(state_current / "FMDL4D_ATTRIBUTION_REGISTRY.csv", index=False)
    decision_log_frame.to_csv(state_current / "FMDL4D_DECISION_LOG.csv", index=False)
    core.write_jsonl(evidence / "FMDL4D_FEEDBACK_PROPOSALS.jsonl", feedback_rows, sort_key="proposal_id")
    core.write_json(evidence / "FMDL4D_SOURCE_BINDING.json", source_binding)

    package_files = []
    for path in sorted(item for item in overlay.rglob("*") if item.is_file()):
        relative = path.relative_to(overlay).as_posix()
        package_files.append({
            "package_path": f"{cfg['tracking']['overlay_namespace']}/{relative}",
            "source_path": str(path.relative_to(ROOT)),
            "sha256": core.sha256_file(path),
            "bytes": path.stat().st_size,
            "package_domain": relative.split("/", 1)[0],
        })

    composition_manifest = {
        "manifest_version": "1.0.0",
        "composition_sequence": cfg["tracking"]["composition_sequence"],
        "composition_status": "RELEASE7_THESIS_ATTRIBUTION_OVERLAY_CANDIDATE",
        "composition_mode": "IMMUTABLE_BASE_PLUS_VERSIONED_ADDITIVE_STATE_OVERLAYS",
        "components": [
            {"component": "EXTERNAL_CANONICAL_BASE", "release_sequence": 4, "sha256": fmdl4c_release.get("external_canonical_base", {}).get("package_sha256")},
            {"component": "FMDL4A_EVIDENCE_ADAPTER", "release_id": fmdl4c_release.get("release5_adapter_release_id")},
            {"component": "FMDL4B_RESEARCH", "release_id": fmdl4c_release.get("fmdl4b_research_release_id")},
            {"component": "FMDL4C_REENTRY_STATE", "release_id": fmdl4c_release.get("release_id")},
            {"component": "FMDL4D_THESIS_ATTRIBUTION", "thesis_version": cfg["tracking"]["thesis_version"]},
        ],
        "overlay_namespace": cfg["tracking"]["overlay_namespace"],
        "files": package_files,
        "aggregate_sha256": core.stable_hash(package_files),
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "rule_mutation_count": 0,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    core.write_json(candidate / "FMDL4D_RELEASE7_COMPOSITION_MANIFEST.json", composition_manifest)
    overlay_zip = candidate / "FMDL4D_RELEASE7_THESIS_ATTRIBUTION_OVERLAY.zip"
    core.deterministic_zip(overlay, overlay_zip)

    metrics = {
        "total_fmdl4b_decision_count": len(decisions),
        "graduated_input_count": len(graduated),
        "reentry_queue_count": len(queue),
        "thesis_record_count": len(thesis_records),
        "catalyst_count": len(catalyst_rows),
        "prove_kill_count": len(prove_kill_rows),
        "attribution_record_count": len(attribution_rows),
        "feedback_proposal_count": len(feedback_rows),
        "decision_log_count": len(decision_log_rows),
        "missing_research_binding_count": len(missing_research),
        "graduated_symbol_mismatch_count": len(graduated_symbol_mismatch),
        "thesis_validation_error_count": thesis_validation_error_count,
        "observable_return_count": int((attribution_frame["thesis_attribution_status"] != cfg["tracking"]["attribution_status"]).sum()),
        "security_decision_grade_count": int((thesis_frame["security_thesis_readiness"] != cfg["tracking"]["security_thesis_readiness"]).sum()),
        "position_action_count": int((thesis_frame["position_action"] != "WAIT_FOR_PROOF").sum()),
        "append_only_log_error_count": int((decision_log_frame["operation"] != "APPEND").sum()) + int(decision_log_frame["prior_record_deleted"].astype(bool).sum()),
        "rule_mutation_count": int(sum(bool(row["rule_mutation_applied"]) for row in feedback_rows)),
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "trade_authority_error_count": (
            int((thesis_frame["trade_authority"] != "NONE").sum())
            + int((catalyst_frame["trade_authority"] != "NONE").sum())
            + int((prove_kill_frame["trade_authority"] != "NONE").sum())
            + int((attribution_frame["trade_authority"] != "NONE").sum())
            + int((decision_log_frame["trade_authority"] != "NONE").sum())
            + sum(1 for row in feedback_rows if row["trade_authority"] != "NONE")
        ),
        "overlay_file_count": len(package_files),
        "elapsed_seconds": round((datetime.now(TZ) - started).total_seconds(), 4),
    }

    acceptance = cfg["acceptance"]
    checks = {
        "ENTRY_GATE": not any(item.startswith("ENTRY_") for item in hard_failures),
        "REENTRY_AND_GRADUATION_SYMBOLS": metrics["reentry_queue_count"] == 6 and metrics["graduated_input_count"] == 6 and metrics["graduated_symbol_mismatch_count"] == 0,
        "RESEARCH_BINDING": metrics["missing_research_binding_count"] == 0,
        "THESIS_RECORDS": metrics["thesis_record_count"] == acceptance["required_thesis_record_count"] and metrics["thesis_validation_error_count"] == 0,
        "CATALYST_REGISTRY": metrics["catalyst_count"] >= acceptance["minimum_catalyst_count"],
        "PROVE_KILL_REGISTRY": metrics["prove_kill_count"] == acceptance["required_prove_kill_count"],
        "ATTRIBUTION_BASELINE": metrics["attribution_record_count"] == acceptance["required_attribution_record_count"] and metrics["observable_return_count"] <= acceptance["maximum_observable_return_count"],
        "FEEDBACK_PROPOSALS": metrics["feedback_proposal_count"] == acceptance["required_feedback_proposal_count"] and metrics["rule_mutation_count"] <= acceptance["maximum_rule_mutation_count"],
        "APPEND_ONLY_DECISION_LOG": metrics["append_only_log_error_count"] == 0,
        "ZERO_SECURITY_DECISION_GRADE": metrics["security_decision_grade_count"] <= acceptance["maximum_security_decision_grade_count"],
        "ZERO_POSITION_ACTION": metrics["position_action_count"] <= acceptance["maximum_position_action_count"],
        "ZERO_INVESTMENT_STATE_MUTATION": metrics["candidate_pool_mutation_count"] == 0 and metrics["simulation_mutation_count"] == 0 and metrics["real_account_mutation_count"] == 0,
        "ZERO_ORDER_GENERATION": metrics["order_generation_count"] == 0,
        "ZERO_TRADE_AUTHORITY": metrics["trade_authority_error_count"] <= acceptance["maximum_trade_authority_error_count"],
    }
    hard_failures.extend([check for check, passed in checks.items() if not passed])

    semantic_hashes = {
        "thesis_records": core.semantic_frame_hash(thesis_frame),
        "catalyst_registry": core.semantic_frame_hash(catalyst_frame, sort_by=("symbol", "catalyst_id")),
        "prove_kill_registry": core.semantic_frame_hash(prove_kill_frame, sort_by=("symbol", "prove_kill_id")),
        "attribution_registry": core.semantic_frame_hash(attribution_frame),
        "decision_log": core.semantic_frame_hash(decision_log_frame),
        "feedback_proposals": core.stable_hash(feedback_rows),
        "failure_taxonomy": core.stable_hash(failure_taxonomy),
        "composition_manifest": composition_manifest["aggregate_sha256"],
        "overlay_zip": core.sha256_file(overlay_zip),
    }
    release_semantic_hash = core.stable_hash({
        "fmdl4c_release_id": fmdl4c_release.get("release_id"),
        "thesis_version": cfg["tracking"]["thesis_version"],
        "semantic_hashes": semantic_hashes,
        "composition_sequence": cfg["tracking"]["composition_sequence"],
    })
    release_id = f"FMDL4D_20260717_{release_semantic_hash[:12]}"
    status = cfg["exit_status"] if not hard_failures else "FMDL4D_THESIS_ATTRIBUTION_AND_FEEDBACK_REJECTED"
    decision = {
        "decision_version": "1.0.0",
        "release_id": release_id,
        "generated_at": started.isoformat(timespec="seconds"),
        "program_id": "FMDL-4D",
        "status": status,
        "hard_failures": sorted(set(hard_failures)),
        "checks": [{"check_id": key, "status": "PASS" if value else "FAIL"} for key, value in checks.items()],
        "metrics": metrics,
        "bindings": source_binding,
        "semantic_hashes": semantic_hashes,
        "thesis_summary": {
            "company_thesis_intact_unverified_count": int((thesis_frame["company_thesis_status"] == "INTACT_UNTESTED_BASELINE").sum()),
            "company_thesis_watch_count": int((thesis_frame["company_thesis_status"] == "WATCH_UNTESTED_EXPECTATIONS_OR_QUALITY_GATE").sum()),
            "security_not_decision_grade_count": len(thesis_frame),
            "wait_for_proof_count": len(thesis_frame),
            "observable_return_count": metrics["observable_return_count"],
        },
        "controlled_limitations": cfg["controlled_limitations"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    core.write_json(candidate / "FMDL4D_DECISION.json", decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    if hard_failures:
        raise SystemExit("FMDL-4D candidate rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
