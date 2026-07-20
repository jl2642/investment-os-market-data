from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from scripts import fmdl4_final_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl4_final_operational_acceptance.json"
TZ = ZoneInfo("Asia/Shanghai")


def verify_component(phase: str, spec: dict) -> tuple[list[str], dict]:
    errors: list[str] = []
    payloads = {}
    for key in ["pointer", "release", "decision", "validation"]:
        path = ROOT / spec[key]
        if not path.exists():
            errors.append(f"MISSING_{phase}_{key.upper()}:{spec[key]}")
            continue
        payloads[key] = core.read_json(path)
    if len(payloads) != 4:
        return errors, payloads
    pointer, release, decision, validation = (payloads[key] for key in ["pointer", "release", "decision", "validation"])
    expected_release_id = spec["expected_release_id"]
    expected_status = spec["expected_status"]
    if pointer.get("release_id") != expected_release_id or release.get("release_id") != expected_release_id or decision.get("release_id") != expected_release_id or validation.get("release_id") != expected_release_id:
        errors.append(f"{phase}_RELEASE_IDENTITY")
    if pointer.get("status") != expected_status or release.get("status") != expected_status or decision.get("status") != expected_status:
        errors.append(f"{phase}_STATUS")
    if validation.get("status") != "PASS":
        errors.append(f"{phase}_VALIDATION_STATUS")
    if decision.get("hard_failures") != [] or validation.get("hard_failures") != []:
        errors.append(f"{phase}_HARD_FAILURES")
    for label, payload in payloads.items():
        if payload.get("trade_authority") != "NONE":
            errors.append(f"{phase}_{label.upper()}_TRADE_AUTHORITY")
    return errors, payloads


def main() -> int:
    cfg = core.read_json(CONFIG)
    publication = cfg["publication"]
    candidate = ROOT / publication["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True)
    overlay = candidate / publication["overlay_namespace"]
    core_static = overlay / "CORE_STATIC"
    evidence_out = overlay / "EVIDENCE"
    state_out = overlay / "STATE_CURRENT"
    for path in [core_static, evidence_out, state_out]:
        path.mkdir(parents=True)

    started = datetime.now(TZ)
    hard_failures: list[str] = []
    component_payloads: dict[str, dict] = {}
    required_paths = list(cfg["lineage_inputs"].values())
    missing = [path for path in required_paths if not (ROOT / path).exists()]
    hard_failures.extend(f"MISSING_LINEAGE_INPUT:{path}" for path in missing)

    entry = cfg["entry_gate"]
    for key in ["pointer_path", "release_path", "decision_path", "validation_path"]:
        if not (ROOT / entry[key]).exists():
            hard_failures.append(f"MISSING_ENTRY:{entry[key]}")
    if not hard_failures:
        entry_pointer = core.read_json(ROOT / entry["pointer_path"])
        entry_release = core.read_json(ROOT / entry["release_path"])
        entry_decision = core.read_json(ROOT / entry["decision_path"])
        entry_validation = core.read_json(ROOT / entry["validation_path"])
        if entry_pointer.get("status") != entry["required_status"] or entry_release.get("status") != entry["required_status"] or entry_decision.get("status") != entry["required_status"]:
            hard_failures.append("ENTRY_STATUS")
        if entry_pointer.get("next_gate") != entry["required_next_gate"]:
            hard_failures.append("ENTRY_NEXT_GATE")
        if entry_validation.get("status") != "PASS" or entry_decision.get("hard_failures") != [] or entry_validation.get("hard_failures") != []:
            hard_failures.append("ENTRY_VALIDATION")

    for phase, spec in cfg["component_inputs"].items():
        errors, payloads = verify_component(phase, spec)
        hard_failures.extend(errors)
        component_payloads[phase] = payloads

    if any(item.startswith("MISSING_") for item in hard_failures):
        core.write_json(candidate / "FMDL4_FINAL_DECISION.json", {
            "program_id": "FMDL-4-FINAL",
            "status": "FMDL4_PUBLIC_EQUITY_INVESTING_AND_INVESTMENT_OS_INTEGRATION_REJECTED",
            "hard_failures": sorted(set(hard_failures)),
            "trade_authority": "NONE"
        })
        raise SystemExit("FMDL-4-FINAL missing required inputs")

    inputs = cfg["lineage_inputs"]
    evidence_records = core.read_jsonl(ROOT / inputs["evidence_envelopes"])
    research_priority = pd.read_csv(ROOT / inputs["research_priority_registry"], dtype={"symbol": str})
    research_objects = pd.read_csv(ROOT / inputs["research_objects"], dtype={"symbol": str})
    graduation = pd.read_csv(ROOT / inputs["graduation_decisions"], dtype={"symbol": str})
    graduated = graduation[graduation["graduation_decision"] == "GRADUATED"].copy()
    transitions = core.read_jsonl(ROOT / inputs["state_transitions"])
    queue = pd.read_csv(ROOT / inputs["reentry_queue"], dtype={"symbol": str})
    candidate_router = pd.read_csv(ROOT / inputs["candidate_router"], dtype={"symbol": str})
    simulation_router = pd.read_csv(ROOT / inputs["simulation_router"], dtype={"symbol": str})
    real_router = pd.read_csv(ROOT / inputs["real_account_router"], dtype={"symbol": str})
    versioned_diff = core.read_json(ROOT / inputs["versioned_diff"])
    rollback = core.read_json(ROOT / inputs["rollback_proof"])
    thesis_records = core.read_jsonl(ROOT / inputs["thesis_records"])
    catalyst_registry = pd.read_csv(ROOT / inputs["catalyst_registry"], dtype={"symbol": str})
    prove_kill_registry = pd.read_csv(ROOT / inputs["prove_kill_registry"], dtype={"symbol": str})
    attribution_registry = pd.read_csv(ROOT / inputs["attribution_registry"], dtype={"symbol": str})
    feedback = core.read_jsonl(ROOT / inputs["feedback_proposals"])

    lineage_records, lineage_errors = core.build_lineage_records(
        graduated, evidence_records, research_objects, transitions, thesis_records, queue
    )
    lineage_frame = pd.DataFrame(lineage_records).sort_values("symbol").reset_index(drop=True)
    expected_as_of_values = sorted({str(record.get("evidence_as_of")) for record in lineage_records})
    expected_as_of = expected_as_of_values[0] if len(expected_as_of_values) == 1 else ""
    baseline_validation_errors = sum(len(core.validate_operational_record(record, expected_as_of)) for record in lineage_records)

    component_decisions = {phase: payloads.get("decision", {}) for phase, payloads in component_payloads.items()}
    investment_state_mutation_count = 0
    for decision in component_decisions.values():
        metrics = decision.get("metrics", {})
        for key in ["candidate_pool_mutation_count", "simulation_mutation_count", "real_account_mutation_count", "state_mutation_count"]:
            investment_state_mutation_count += int(metrics.get(key, 0) or 0)
    investment_state_mutation_count += int(versioned_diff.get("candidate_pool_mutation_count", 0))
    investment_state_mutation_count += int(versioned_diff.get("simulation_mutation_count", 0))
    investment_state_mutation_count += int(versioned_diff.get("real_account_mutation_count", 0))

    state_crossover_count = 0
    state_crossover_count += int(candidate_router.get("candidate_pool_mutation_authorized", pd.Series(dtype=bool)).astype(bool).sum())
    state_crossover_count += int(simulation_router.get("simulation_mutation_authorized", pd.Series(dtype=bool)).astype(bool).sum())
    state_crossover_count += int(real_router.get("real_account_mutation_authorized", pd.Series(dtype=bool)).astype(bool).sum())
    if set(queue["symbol"].astype(str)) != set(graduated["symbol"].astype(str)):
        state_crossover_count += 1
    if not rollback.get("preserves_external_base") or not rollback.get("preserves_fmdl4a_adapter") or not rollback.get("preserves_fmdl4b_research"):
        state_crossover_count += 1

    rule_mutation_count = sum(bool(row.get("rule_mutation_applied")) for row in feedback)
    order_generation_count = sum(int(component_decisions[phase].get("metrics", {}).get("order_generation_count", 0) or 0) for phase in component_decisions)
    trade_authority_error_count = 0
    for payloads in component_payloads.values():
        for payload in payloads.values():
            trade_authority_error_count += int(payload.get("trade_authority") != "NONE")
    for record in lineage_records:
        trade_authority_error_count += int(record.get("trade_authority") != "NONE")

    snapshot_paths = []
    for spec in cfg["component_inputs"].values():
        snapshot_paths.extend([spec["pointer"], spec["release"]])
    before_snapshot = core.snapshot_hashes(ROOT, snapshot_paths)
    failure_results = core.run_failure_injections(lineage_records[0], expected_as_of) if lineage_records else []
    after_snapshot = core.snapshot_hashes(ROOT, snapshot_paths)
    lkg_preserved = before_snapshot == after_snapshot

    capability = core.capability_matrix(cfg)
    file_plan = core.file_library_maintenance_plan(cfg)
    refresh_requirements = {
        "requirements_version": "1.0.0",
        **cfg["canonical_refresh"],
        "external_base": cfg["external_canonical_base"],
        "accepted_component_release_ids": {phase: spec["expected_release_id"] for phase, spec in cfg["component_inputs"].items()},
        "current_account_state_claim": "NOT_RECONCILED_AFTER_EXTERNAL_RELEASE4",
        "automatic_state_or_file_library_mutation_performed": False,
        "authority": "CANONICAL_REFRESH_REQUIREMENTS_ONLY",
        "trade_authority": "NONE"
    }
    operational_audit = {
        "audit_version": "1.0.0",
        "a_share_evidence_as_of": expected_as_of,
        "full_universe_symbol_count": len(evidence_records),
        "research_longlist_count": len(research_priority),
        "formal_research_object_count": len(research_objects),
        "graduated_research_case_count": len(graduated),
        "reentry_review_count": len(queue),
        "thesis_record_count": len(thesis_records),
        "current_real_account_state": "EXTERNAL_RELEASE4_BASE_NOT_RECONCILED_POST_FMDL4",
        "current_simulation_state": "EXTERNAL_RELEASE4_BASE_NOT_RECONCILED_POST_FMDL4",
        "current_candidate_pool_state": "EXTERNAL_RELEASE4_BASE_NOT_RECONCILED_POST_FMDL4",
        "source_three_package_state": "RELEASE4_BASE_PLUS_ACCEPTED_GITHUB_OVERLAYS_NOT_YET_SINGLE_PACKAGE",
        "file_library_canonical_state": "RELEASE4_REMAINS_ACTIVE_UNTIL_RELEASE8_IMPORT_ACCEPTANCE",
        "post_acceptance_operation": cfg["recommended_next_operation"],
        "project_sources_required": False,
        "trade_authority": "NONE"
    }
    component_registry = {
        "registry_version": "1.0.0",
        "external_base": cfg["external_canonical_base"],
        "components": [
            {
                "phase": phase,
                "release_id": spec["expected_release_id"],
                "status": spec["expected_status"],
                "release_sha256": core.sha256_file(ROOT / spec["release"]),
                "decision_sha256": core.sha256_file(ROOT / spec["decision"]),
                "validation_sha256": core.sha256_file(ROOT / spec["validation"]),
            }
            for phase, spec in cfg["component_inputs"].items()
        ],
        "authority": cfg["authority"],
        "trade_authority": "NONE"
    }
    lkg_proof = {
        "proof_version": "1.0.0",
        "snapshot_before": before_snapshot,
        "snapshot_after_failure_injections": after_snapshot,
        "all_failure_injections_rejected": all(row["status"] == "REJECTED_AS_REQUIRED" for row in failure_results),
        "current_and_lkg_preserved": lkg_preserved,
        "failed_candidate_replaces_current": False,
        "failed_candidate_replaces_last_known_good": False,
        "trade_authority": "NONE"
    }
    acceptance_contract = {
        "contract_version": "1.0.0",
        "program_id": "FMDL-4-FINAL",
        "composition_sequence": publication["composition_sequence"],
        "layer_chain": ["EVIDENCE", "RESEARCH_JUDGMENT", "INVESTMENT_STATE_GOVERNANCE", "THESIS_ATTRIBUTION_FEEDBACK"],
        "real_account_action_requires_user_confirmation": True,
        "file_library_single_package_refresh_required": True,
        "project_sources_required": False,
        "authority": cfg["authority"],
        "trade_authority": "NONE"
    }

    core.write_json(core_static / "FMDL4_FINAL_OPERATIONAL_ACCEPTANCE_CONTRACT.json", acceptance_contract)
    core.write_json(core_static / "FMDL4_FINAL_CAPABILITY_MATRIX.json", {"matrix_version": "1.0.0", "capabilities": capability, "trade_authority": "NONE"})
    core.write_json(core_static / "FMDL4_FINAL_HARD_GATE_REGISTRY.json", {"gate_version": "1.0.0", "failure_injections": cfg["failure_injections"], "trade_authority": "NONE"})
    core.write_json(evidence_out / "FMDL4_FINAL_COMPONENT_RELEASE_REGISTRY.json", component_registry)
    core.write_json(evidence_out / "FMDL4_FINAL_FAILURE_INJECTION_RESULTS.json", {"results": failure_results, "trade_authority": "NONE"})
    core.write_json(evidence_out / "FMDL4_FINAL_FILE_LIBRARY_MAINTENANCE_PLAN.json", file_plan)
    core.write_json(evidence_out / "FMDL4_FINAL_CANONICAL_REFRESH_REQUIREMENTS.json", refresh_requirements)
    core.write_jsonl(state_out / "FMDL4_FINAL_CHAIN_REGISTRY.jsonl", lineage_records)
    lineage_frame.to_csv(state_out / "FMDL4_FINAL_CHAIN_REGISTRY.csv", index=False)
    core.write_json(state_out / "FMDL4_FINAL_OPERATIONAL_STATE_AUDIT.json", operational_audit)
    core.write_json(state_out / "FMDL4_FINAL_LKG_PRESERVATION_PROOF.json", lkg_proof)

    package_files = []
    for path in sorted(item for item in overlay.rglob("*") if item.is_file()):
        relative = path.relative_to(overlay).as_posix()
        package_files.append({
            "package_path": f"{publication['overlay_namespace']}/{relative}",
            "source_path": str(path.relative_to(ROOT)),
            "sha256": core.sha256_file(path),
            "bytes": path.stat().st_size,
            "package_domain": relative.split("/", 1)[0],
        })
    manifest = {
        "manifest_version": "1.0.0",
        "composition_sequence": publication["composition_sequence"],
        "composition_status": "FMDL4_RELEASE8_UNIFIED_INTEGRATION_CANDIDATE",
        "composition_mode": "IMMUTABLE_EXTERNAL_BASE_PLUS_VERSIONED_ADDITIVE_RELEASES",
        "external_base": cfg["external_canonical_base"],
        "component_releases": component_registry["components"],
        "overlay_namespace": publication["overlay_namespace"],
        "files": package_files,
        "aggregate_sha256": core.stable_hash(package_files),
        "investment_state_mutation_count": 0,
        "rule_mutation_count": 0,
        "order_generation_count": 0,
        "trade_authority": "NONE"
    }
    core.write_json(candidate / "FMDL4_FINAL_RELEASE8_MANIFEST.json", manifest)
    overlay_zip = candidate / publication["overlay_package_name"]
    core.deterministic_zip(overlay, overlay_zip)

    acceptance = cfg["acceptance"]
    metrics = {
        "universe_symbol_count": len(evidence_records),
        "longlist_symbol_count": len(research_priority),
        "research_object_count": len(research_objects),
        "graduation_decision_count": len(graduation),
        "graduated_count": len(graduated),
        "transition_count": len(transitions),
        "reentry_queue_count": len(queue),
        "thesis_record_count": len(thesis_records),
        "catalyst_count": len(catalyst_registry),
        "prove_kill_count": len(prove_kill_registry),
        "attribution_record_count": len(attribution_registry),
        "feedback_proposal_count": len(feedback),
        "lineage_record_count": len(lineage_records),
        "lineage_error_count": len(lineage_errors) + baseline_validation_errors,
        "state_crossover_count": state_crossover_count,
        "investment_state_mutation_count": investment_state_mutation_count,
        "rule_mutation_count": rule_mutation_count,
        "order_generation_count": order_generation_count,
        "trade_authority_error_count": trade_authority_error_count,
        "failure_injection_count": len(failure_results),
        "failure_injection_rejected_count": sum(row["status"] == "REJECTED_AS_REQUIRED" for row in failure_results),
        "lkg_preservation_error_count": 0 if lkg_preserved else 1,
        "overlay_file_count": len(package_files),
        "elapsed_seconds": round((datetime.now(TZ) - started).total_seconds(), 4)
    }

    checks = {
        "ENTRY_AND_COMPONENT_RELEASE_CHAIN": not any("ENTRY" in item or "FMDL-4" in item for item in hard_failures),
        "FULL_UNIVERSE_AND_LONGLIST": metrics["universe_symbol_count"] == acceptance["required_universe_count"] and metrics["longlist_symbol_count"] == acceptance["required_longlist_count"],
        "RESEARCH_AND_GRADUATION_COUNTS": metrics["research_object_count"] == acceptance["required_research_object_count"] and metrics["graduated_count"] == acceptance["required_graduated_count"] and metrics["graduation_decision_count"] == acceptance["required_longlist_count"],
        "TRANSITION_AND_THESIS_COUNTS": metrics["transition_count"] == acceptance["required_transition_count"] and metrics["thesis_record_count"] == acceptance["required_thesis_count"],
        "CATALYST_PROVE_KILL_FEEDBACK_COUNTS": metrics["catalyst_count"] == acceptance["required_catalyst_count"] and metrics["prove_kill_count"] == acceptance["required_prove_kill_count"] and metrics["feedback_proposal_count"] == acceptance["required_feedback_count"],
        "END_TO_END_LINEAGE": metrics["lineage_record_count"] == acceptance["required_graduated_count"] and metrics["lineage_error_count"] <= acceptance["maximum_lineage_error_count"],
        "STATE_DOMAIN_SEPARATION": metrics["state_crossover_count"] <= acceptance["maximum_state_crossover_count"],
        "ZERO_INVESTMENT_AND_RULE_MUTATION": metrics["investment_state_mutation_count"] <= acceptance["maximum_investment_state_mutation_count"] and metrics["rule_mutation_count"] <= acceptance["maximum_rule_mutation_count"],
        "ZERO_ORDER_AND_TRADE_AUTHORITY": metrics["order_generation_count"] <= acceptance["maximum_order_generation_count"] and metrics["trade_authority_error_count"] <= acceptance["maximum_trade_authority_error_count"],
        "FAILURE_INJECTION": metrics["failure_injection_count"] == acceptance["required_failure_injection_count"] and metrics["failure_injection_rejected_count"] == acceptance["required_failure_injection_count"],
        "LKG_PRESERVATION": metrics["lkg_preservation_error_count"] == 0,
        "CANONICAL_REFRESH_TRUTHFULNESS": operational_audit["current_real_account_state"].endswith("NOT_RECONCILED_POST_FMDL4") and refresh_requirements["status"] == "REQUIRED_POST_FMDL4_FINAL"
    }
    hard_failures.extend([key for key, passed in checks.items() if not passed])
    hard_failures = sorted(set(hard_failures))

    semantic_hashes = {
        "lineage_registry": core.semantic_frame_hash(lineage_frame),
        "component_registry": core.stable_hash(component_registry),
        "capability_matrix": core.stable_hash(capability),
        "operational_state_audit": core.stable_hash(operational_audit),
        "failure_injection_results": core.stable_hash(failure_results),
        "lkg_preservation": core.stable_hash(lkg_proof),
        "file_library_maintenance_plan": core.stable_hash(file_plan),
        "canonical_refresh_requirements": core.stable_hash(refresh_requirements),
        "release8_manifest": manifest["aggregate_sha256"],
        "overlay_zip": core.sha256_file(overlay_zip)
    }
    composition_hash = core.stable_hash({
        "external_base_sha256": cfg["external_canonical_base"]["package_sha256"],
        "component_release_ids": {phase: spec["expected_release_id"] for phase, spec in cfg["component_inputs"].items()},
        "semantic_hashes": semantic_hashes,
        "composition_sequence": publication["composition_sequence"]
    })
    release_id = f"FMDL4FINAL_{expected_as_of.replace('-', '')}_{composition_hash[:12]}"
    status = cfg["exit_status"] if not hard_failures else "FMDL4_PUBLIC_EQUITY_INVESTING_AND_INVESTMENT_OS_INTEGRATION_REJECTED"
    decision = {
        "decision_version": "1.0.0",
        "program_id": "FMDL-4-FINAL",
        "release_id": release_id,
        "generated_at": started.isoformat(timespec="seconds"),
        "status": status,
        "hard_failures": hard_failures,
        "checks": [{"check_id": key, "status": "PASS" if value else "FAIL"} for key, value in checks.items()],
        "metrics": metrics,
        "component_release_ids": {phase: spec["expected_release_id"] for phase, spec in cfg["component_inputs"].items()},
        "external_canonical_base": cfg["external_canonical_base"],
        "semantic_hashes": semantic_hashes,
        "capability_summary": {
            "a_share_core_platform": "OPERATIONALLY_ACCEPTED_GOVERNED_DECISION_SUPPORT",
            "automatic_trading": "INTENTIONALLY_DISABLED",
            "realized_alpha_proof": "NOT_YET_ESTABLISHED",
            "file_library_single_package": "REFRESH_REQUIRED",
            "real_account_simulation_candidate_state": "RECONCILIATION_REQUIRED"
        },
        "recommended_next_operation": cfg["recommended_next_operation"],
        "controlled_limitations": cfg["controlled_limitations"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"]
    }
    core.write_json(candidate / "FMDL4_FINAL_DECISION.json", decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not hard_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
