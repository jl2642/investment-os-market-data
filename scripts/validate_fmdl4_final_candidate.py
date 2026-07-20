from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

import pandas as pd

from scripts import fmdl4_final_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl4_final_operational_acceptance.json"


def main() -> int:
    cfg = core.read_json(CONFIG)
    publication = cfg["publication"]
    candidate = ROOT / publication["candidate_root"]
    overlay = candidate / publication["overlay_namespace"]
    core_static = overlay / "CORE_STATIC"
    evidence = overlay / "EVIDENCE"
    state = overlay / "STATE_CURRENT"

    decision = core.read_json(candidate / "FMDL4_FINAL_DECISION.json")
    manifest = core.read_json(candidate / "FMDL4_FINAL_RELEASE8_MANIFEST.json")
    lineage = core.read_jsonl(state / "FMDL4_FINAL_CHAIN_REGISTRY.jsonl")
    lineage_frame = pd.read_csv(state / "FMDL4_FINAL_CHAIN_REGISTRY.csv", dtype={"symbol": str})
    component_registry = core.read_json(evidence / "FMDL4_FINAL_COMPONENT_RELEASE_REGISTRY.json")
    failure_results = core.read_json(evidence / "FMDL4_FINAL_FAILURE_INJECTION_RESULTS.json")["results"]
    file_plan = core.read_json(evidence / "FMDL4_FINAL_FILE_LIBRARY_MAINTENANCE_PLAN.json")
    refresh = core.read_json(evidence / "FMDL4_FINAL_CANONICAL_REFRESH_REQUIREMENTS.json")
    capability = core.read_json(core_static / "FMDL4_FINAL_CAPABILITY_MATRIX.json")["capabilities"]
    operational_audit = core.read_json(state / "FMDL4_FINAL_OPERATIONAL_STATE_AUDIT.json")
    lkg = core.read_json(state / "FMDL4_FINAL_LKG_PRESERVATION_PROOF.json")
    overlay_zip = candidate / publication["overlay_package_name"]

    failures: list[str] = []
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        failures.append("DECISION")

    lineage_shape_errors = 0
    expected_as_of = sorted({str(row.get("evidence_as_of")) for row in lineage})
    expected_as_of_value = expected_as_of[0] if len(expected_as_of) == 1 else ""
    for record in lineage:
        lineage_shape_errors += len(core.validate_operational_record(record, expected_as_of_value))
        semantic_payload = {key: value for key, value in record.items() if key not in {"lineage_id", "semantic_hash"}}
        semantic = core.stable_hash(semantic_payload)
        if semantic != record.get("semantic_hash") or record.get("lineage_id") != f"FMDL4FINAL-LIN-{record.get('symbol')}-{semantic[:16]}":
            lineage_shape_errors += 1
    if len(lineage) != cfg["acceptance"]["required_graduated_count"] or lineage_shape_errors:
        failures.append("LINEAGE_RECORDS")
    if set(lineage_frame["symbol"].astype(str)) != {str(row["symbol"]) for row in lineage}:
        failures.append("LINEAGE_TABLE_IDENTITY")

    component_errors = 0
    for component in component_registry.get("components", []):
        phase = component["phase"]
        spec = cfg["component_inputs"].get(phase, {})
        if component.get("release_id") != spec.get("expected_release_id"):
            component_errors += 1
        for key, field in [("release", "release_sha256"), ("decision", "decision_sha256"), ("validation", "validation_sha256")]:
            path = ROOT / spec.get(key, "")
            if not path.exists() or core.sha256_file(path) != component.get(field):
                component_errors += 1
    if component_errors:
        failures.append("COMPONENT_RELEASE_BINDING")

    failure_injection_errors = sum(row.get("status") != "REJECTED_AS_REQUIRED" for row in failure_results)
    if len(failure_results) != cfg["acceptance"]["required_failure_injection_count"] or failure_injection_errors:
        failures.append("FAILURE_INJECTION")
    if not lkg.get("current_and_lkg_preserved") or lkg.get("snapshot_before") != lkg.get("snapshot_after_failure_injections"):
        failures.append("LKG_PRESERVATION")

    if refresh.get("status") != "REQUIRED_POST_FMDL4_FINAL" or refresh.get("automatic_state_or_file_library_mutation_performed") is not False:
        failures.append("CANONICAL_REFRESH_TRUTHFULNESS")
    if file_plan.get("automatic_deletion_performed") is not False or "RELEASE4" not in file_plan.get("safety_rule", ""):
        failures.append("FILE_LIBRARY_MAINTENANCE_SAFETY")
    capability_index = {row["capability"]: row["status"] for row in capability}
    if capability_index.get("FILE_LIBRARY_SINGLE_PACKAGE_CANONICAL") != "REFRESH_REQUIRED_POST_FMDL4":
        failures.append("CAPABILITY_MATRIX_CANONICAL_STATUS")
    if capability_index.get("ORDER_EXECUTION") != "INTENTIONALLY_DISABLED":
        failures.append("CAPABILITY_MATRIX_AUTHORITY")
    if operational_audit.get("project_sources_required") is not False:
        failures.append("PROJECT_SOURCES_POLICY")

    mutation_errors = 0
    for key in ["investment_state_mutation_count", "rule_mutation_count", "order_generation_count"]:
        mutation_errors += int(decision.get("metrics", {}).get(key, 0) or 0)
        mutation_errors += int(manifest.get(key, 0) or 0)
    if mutation_errors:
        failures.append("ZERO_MUTATION")

    trade_errors = int(decision.get("trade_authority") != "NONE") + int(manifest.get("trade_authority") != "NONE")
    trade_errors += sum(row.get("trade_authority") != "NONE" for row in lineage)
    trade_errors += int(file_plan.get("trade_authority") != "NONE") + int(refresh.get("trade_authority") != "NONE")
    if trade_errors:
        failures.append("TRADE_AUTHORITY")

    manifest_errors = 0
    expected_entries: dict[str, dict] = {}
    prefix = publication["overlay_namespace"] + "/"
    for item in manifest.get("files", []):
        source = ROOT / item["source_path"]
        if not source.exists() or source.stat().st_size != item["bytes"] or core.sha256_file(source) != item["sha256"]:
            manifest_errors += 1
        package_path = item["package_path"]
        if not package_path.startswith(prefix):
            manifest_errors += 1
        else:
            expected_entries[package_path[len(prefix):]] = item
    if core.stable_hash(manifest.get("files", [])) != manifest.get("aggregate_sha256"):
        manifest_errors += 1
    if manifest_errors:
        failures.append("MANIFEST")

    zip_errors = 0
    with zipfile.ZipFile(overlay_zip, "r") as archive:
        if set(archive.namelist()) != set(expected_entries):
            zip_errors += 1
        for name, item in expected_entries.items():
            try:
                payload = archive.read(name)
            except KeyError:
                zip_errors += 1
                continue
            if len(payload) != item["bytes"] or hashlib.sha256(payload).hexdigest() != item["sha256"]:
                zip_errors += 1
    if zip_errors:
        failures.append("ZIP")

    with tempfile.TemporaryDirectory() as temp_dir:
        replay_zip = Path(temp_dir) / "replay.zip"
        core.deterministic_zip(overlay, replay_zip)
        replay_hash = core.sha256_file(replay_zip)
    original_hash = core.sha256_file(overlay_zip)
    if replay_hash != original_hash or original_hash != decision.get("semantic_hashes", {}).get("overlay_zip"):
        failures.append("SAME_INPUT_IDEMPOTENCE")

    semantic_hashes = {
        "lineage_registry": core.semantic_frame_hash(lineage_frame),
        "component_registry": core.stable_hash(component_registry),
        "capability_matrix": core.stable_hash(capability),
        "operational_state_audit": core.stable_hash(operational_audit),
        "failure_injection_results": core.stable_hash(failure_results),
        "lkg_preservation": core.stable_hash(lkg),
        "file_library_maintenance_plan": core.stable_hash(file_plan),
        "canonical_refresh_requirements": core.stable_hash(refresh),
        "release8_manifest": manifest.get("aggregate_sha256"),
        "overlay_zip": original_hash
    }
    semantic_errors = sum(semantic_hashes.get(key) != value for key, value in decision.get("semantic_hashes", {}).items())
    if semantic_errors:
        failures.append("SEMANTIC_HASHES")

    checks = [
        {"check_id": "DECISION_AND_RELEASE_CHAIN", "status": "PASS" if not {"DECISION", "COMPONENT_RELEASE_BINDING"}.intersection(failures) else "FAIL"},
        {"check_id": "END_TO_END_LINEAGE", "status": "PASS" if not {"LINEAGE_RECORDS", "LINEAGE_TABLE_IDENTITY"}.intersection(failures) else "FAIL"},
        {"check_id": "FAILURE_INJECTION_AND_LKG", "status": "PASS" if not {"FAILURE_INJECTION", "LKG_PRESERVATION"}.intersection(failures) else "FAIL"},
        {"check_id": "CAPABILITY_AND_CANONICAL_REFRESH_TRUTHFULNESS", "status": "PASS" if not {"CANONICAL_REFRESH_TRUTHFULNESS", "FILE_LIBRARY_MAINTENANCE_SAFETY", "CAPABILITY_MATRIX_CANONICAL_STATUS", "CAPABILITY_MATRIX_AUTHORITY", "PROJECT_SOURCES_POLICY"}.intersection(failures) else "FAIL"},
        {"check_id": "MANIFEST_ZIP_AND_IDEMPOTENCE", "status": "PASS" if not {"MANIFEST", "ZIP", "SAME_INPUT_IDEMPOTENCE", "SEMANTIC_HASHES"}.intersection(failures) else "FAIL"},
        {"check_id": "ZERO_MUTATION_AND_TRADE_AUTHORITY", "status": "PASS" if not {"ZERO_MUTATION", "TRADE_AUTHORITY"}.intersection(failures) else "FAIL"}
    ]
    validation = {
        "validation_version": "1.0.0",
        "program_id": "FMDL-4-FINAL",
        "release_id": decision.get("release_id"),
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": sorted(set(failures)),
        "checks": checks,
        "metrics": {
            **decision.get("metrics", {}),
            "independent_lineage_record_count": len(lineage),
            "lineage_shape_error_count": lineage_shape_errors,
            "component_binding_error_count": component_errors,
            "failure_injection_error_count": failure_injection_errors,
            "manifest_error_count": manifest_errors,
            "zip_error_count": zip_errors,
            "semantic_hash_error_count": semantic_errors,
            "mutation_error_count": mutation_errors,
            "trade_authority_error_count_independent": trade_errors,
            "independent_overlay_zip_sha256": original_hash,
            "idempotence_replay_zip_sha256": replay_hash
        },
        "recommended_next_operation": cfg["recommended_next_operation"],
        "controlled_limitations": cfg["controlled_limitations"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"]
    }
    core.write_json(candidate / "FMDL4_FINAL_VALIDATION.json", validation)
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
