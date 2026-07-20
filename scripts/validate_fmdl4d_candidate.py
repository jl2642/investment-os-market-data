from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

import pandas as pd

from scripts import fmdl4d_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl4d_thesis_attribution.json"


def truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def main() -> int:
    cfg = core.read_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    overlay = candidate / cfg["tracking"]["overlay_namespace"]
    state = overlay / "STATE_CURRENT"
    evidence = overlay / "EVIDENCE"
    core_static = overlay / "CORE_STATIC"

    decision = core.read_json(candidate / "FMDL4D_DECISION.json")
    manifest = core.read_json(candidate / "FMDL4D_RELEASE7_COMPOSITION_MANIFEST.json")
    tracking_contract = core.read_json(core_static / "FMDL4D_TRACKING_CONTRACT.json")
    feedback_firewall = core.read_json(core_static / "FMDL4D_FEEDBACK_FIREWALL.json")
    failure_taxonomy = core.read_json(core_static / "FMDL4D_FAILURE_TAXONOMY.json")
    source_binding = core.read_json(evidence / "FMDL4D_SOURCE_BINDING.json")
    thesis_records = core.read_jsonl(state / "FMDL4D_THESIS_RECORDS.jsonl")
    feedback_rows = core.read_jsonl(evidence / "FMDL4D_FEEDBACK_PROPOSALS.jsonl")
    thesis_frame = pd.read_csv(state / "FMDL4D_THESIS_RECORDS.csv", dtype={"symbol": str})
    catalyst_frame = pd.read_csv(state / "FMDL4D_CATALYST_REGISTRY.csv", dtype={"symbol": str})
    prove_kill_frame = pd.read_csv(state / "FMDL4D_PROVE_KILL_REGISTRY.csv", dtype={"symbol": str})
    attribution_frame = pd.read_csv(state / "FMDL4D_ATTRIBUTION_REGISTRY.csv", dtype={"symbol": str})
    decision_log_frame = pd.read_csv(state / "FMDL4D_DECISION_LOG.csv", dtype={"symbol": str})
    overlay_zip = candidate / "FMDL4D_RELEASE7_THESIS_ATTRIBUTION_OVERLAY.zip"

    failures: list[str] = []
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        failures.append("DECISION")

    expected_symbols = set(thesis_frame["symbol"].astype(str))
    symbol_errors = 0
    for frame in [catalyst_frame, prove_kill_frame, attribution_frame, decision_log_frame]:
        if set(frame["symbol"].astype(str)) != expected_symbols:
            symbol_errors += 1
    if len(expected_symbols) != cfg["acceptance"]["required_thesis_record_count"] or symbol_errors:
        failures.append("SYMBOL_COVERAGE")

    thesis_shape_error_count = sum(bool(core.validate_thesis_record(record, cfg)) for record in thesis_records)
    if thesis_shape_error_count:
        failures.append("THESIS_RECORD_SCHEMA")
    record_index = {record["symbol"]: record for record in thesis_records}
    row_binding_error_count = 0
    for row in thesis_frame.to_dict(orient="records"):
        record = record_index.get(str(row["symbol"]))
        if not record or row["thesis_record_id"] != record["thesis_record_id"] or row["semantic_hash"] != record["semantic_hash"]:
            row_binding_error_count += 1
    if row_binding_error_count:
        failures.append("THESIS_RECORD_ROW_BINDING")

    catalyst_ids = set(catalyst_frame["catalyst_id"].astype(str))
    prove_kill_ids = set(prove_kill_frame["prove_kill_id"].astype(str))
    link_error_count = 0
    for record in thesis_records:
        if not set(record["catalyst_ids"]).issubset(catalyst_ids):
            link_error_count += 1
        if not set(record["prove_kill_ids"]).issubset(prove_kill_ids):
            link_error_count += 1
    if link_error_count:
        failures.append("REGISTRY_LINKS")

    feedback_error_count = 0
    feedback_ids = set()
    for row in feedback_rows:
        feedback_ids.add(row.get("proposal_id"))
        if row.get("rule_mutation_applied") is not False:
            feedback_error_count += 1
        if row.get("human_approval_required") is not True or row.get("regression_required") is not True:
            feedback_error_count += 1
        if row.get("trade_authority") != "NONE":
            feedback_error_count += 1
    for record in thesis_records:
        if not set(record["feedback_proposal_ids"]).issubset(feedback_ids):
            feedback_error_count += 1
    if feedback_error_count or len(feedback_rows) != cfg["acceptance"]["required_feedback_proposal_count"]:
        failures.append("FEEDBACK_PROPOSALS")

    attribution_error_count = 0
    return_fields = [
        "gross_return", "benchmark_return", "active_return", "selection_attribution",
        "position_attribution", "timing_attribution", "fees_tax_attribution",
    ]
    for row in attribution_frame.to_dict(orient="records"):
        if row.get("exposure_status") != "NO_POSITION":
            attribution_error_count += 1
        if row.get("thesis_attribution_status") != "NOT_YET_OBSERVABLE_NO_POSITION":
            attribution_error_count += 1
        if row.get("failure_classification") != "NO_OBSERVATION":
            attribution_error_count += 1
        for field in return_fields:
            value = row.get(field)
            if value is not None and not pd.isna(value):
                attribution_error_count += 1
    if attribution_error_count:
        failures.append("ATTRIBUTION_OBSERVABILITY")

    append_only_error_count = 0
    for row in decision_log_frame.to_dict(orient="records"):
        if row.get("operation") != "APPEND":
            append_only_error_count += 1
        if truthy(row.get("prior_record_deleted")) or truthy(row.get("rule_mutation_applied")):
            append_only_error_count += 1
    if append_only_error_count:
        failures.append("APPEND_ONLY_LOG")

    semantic_hashes = {
        "thesis_records": core.semantic_frame_hash(thesis_frame),
        "catalyst_registry": core.semantic_frame_hash(catalyst_frame, sort_by=("symbol", "catalyst_id")),
        "prove_kill_registry": core.semantic_frame_hash(prove_kill_frame, sort_by=("symbol", "prove_kill_id")),
        "attribution_registry": core.semantic_frame_hash(attribution_frame),
        "decision_log": core.semantic_frame_hash(decision_log_frame),
        "feedback_proposals": core.stable_hash(feedback_rows),
        "failure_taxonomy": core.stable_hash(failure_taxonomy),
        "composition_manifest": manifest.get("aggregate_sha256"),
        "overlay_zip": core.sha256_file(overlay_zip),
    }
    semantic_hash_error_count = sum(
        semantic_hashes.get(key) != decision.get("semantic_hashes", {}).get(key)
        for key in semantic_hashes
    )
    if semantic_hash_error_count:
        failures.append("SEMANTIC_HASHES")

    manifest_error_count = 0
    expected_entries: dict[str, dict] = {}
    prefix = cfg["tracking"]["overlay_namespace"] + "/"
    for item in manifest.get("files", []):
        source = ROOT / item["source_path"]
        if not source.exists() or source.stat().st_size != item["bytes"] or core.sha256_file(source) != item["sha256"]:
            manifest_error_count += 1
        package_path = str(item["package_path"])
        if not package_path.startswith(prefix):
            manifest_error_count += 1
            continue
        expected_entries[package_path[len(prefix):]] = item
    if core.stable_hash(manifest.get("files", [])) != manifest.get("aggregate_sha256"):
        manifest_error_count += 1
    if manifest_error_count:
        failures.append("MANIFEST")

    zip_error_count = 0
    with zipfile.ZipFile(overlay_zip, "r") as archive:
        if set(archive.namelist()) != set(expected_entries):
            zip_error_count += 1
        for name, item in expected_entries.items():
            try:
                payload = archive.read(name)
            except KeyError:
                zip_error_count += 1
                continue
            if len(payload) != item["bytes"] or hashlib.sha256(payload).hexdigest() != item["sha256"]:
                zip_error_count += 1
    if zip_error_count:
        failures.append("ZIP")

    with tempfile.TemporaryDirectory() as temp_dir:
        replay_zip = Path(temp_dir) / "replay.zip"
        core.deterministic_zip(overlay, replay_zip)
        replay_hash = core.sha256_file(replay_zip)
    original_hash = core.sha256_file(overlay_zip)
    if replay_hash != original_hash:
        failures.append("SAME_INPUT_IDEMPOTENCE")

    governance_error_count = 0
    if tracking_contract.get("automatic_rule_mutation") is not False or tracking_contract.get("automatic_portfolio_action") is not False:
        governance_error_count += 1
    if feedback_firewall.get("single_stock_rule_change_allowed") is not False or feedback_firewall.get("single_period_rule_change_allowed") is not False:
        governance_error_count += 1
    if int(feedback_firewall.get("rule_mutation_count", 1)) != 0:
        governance_error_count += 1
    if len(failure_taxonomy.get("classifications", [])) != len(cfg["failure_taxonomy"]):
        governance_error_count += 1
    if governance_error_count:
        failures.append("GOVERNANCE_FIREWALL")

    binding_error_count = 0
    if source_binding.get("fmdl4c_release_id") != decision.get("bindings", {}).get("fmdl4c_release_id"):
        binding_error_count += 1
    if source_binding.get("trade_authority") != "NONE":
        binding_error_count += 1
    if binding_error_count:
        failures.append("SOURCE_BINDING")

    mutation_error_count = 0
    for key in [
        "candidate_pool_mutation_count", "simulation_mutation_count", "real_account_mutation_count",
        "order_generation_count", "rule_mutation_count",
    ]:
        if int(decision.get("metrics", {}).get(key, 0)) != 0:
            mutation_error_count += 1
    if mutation_error_count:
        failures.append("ZERO_MUTATION")

    trade_authority_error_count = 0
    for payload in [decision, manifest, tracking_contract, feedback_firewall, failure_taxonomy, source_binding]:
        if payload.get("trade_authority") != "NONE":
            trade_authority_error_count += 1
    for frame in [thesis_frame, catalyst_frame, prove_kill_frame, attribution_frame, decision_log_frame]:
        trade_authority_error_count += int((frame["trade_authority"].astype(str) != "NONE").sum())
    trade_authority_error_count += sum(row.get("trade_authority") != "NONE" for row in feedback_rows)
    if trade_authority_error_count:
        failures.append("TRADE_AUTHORITY")

    checks = [
        {"check_id": "DECISION", "status": "PASS" if "DECISION" not in failures else "FAIL"},
        {"check_id": "THESIS_RECORDS_AND_LINKS", "status": "PASS" if not {"SYMBOL_COVERAGE", "THESIS_RECORD_SCHEMA", "THESIS_RECORD_ROW_BINDING", "REGISTRY_LINKS"}.intersection(failures) else "FAIL"},
        {"check_id": "ATTRIBUTION_NOT_YET_OBSERVABLE", "status": "PASS" if "ATTRIBUTION_OBSERVABILITY" not in failures else "FAIL"},
        {"check_id": "APPEND_ONLY_DECISION_LOG", "status": "PASS" if "APPEND_ONLY_LOG" not in failures else "FAIL"},
        {"check_id": "FEEDBACK_AND_GOVERNANCE_FIREWALL", "status": "PASS" if not {"FEEDBACK_PROPOSALS", "GOVERNANCE_FIREWALL"}.intersection(failures) else "FAIL"},
        {"check_id": "SEMANTIC_HASHES", "status": "PASS" if "SEMANTIC_HASHES" not in failures else "FAIL"},
        {"check_id": "MANIFEST_AND_ZIP", "status": "PASS" if not {"MANIFEST", "ZIP"}.intersection(failures) else "FAIL"},
        {"check_id": "SAME_INPUT_IDEMPOTENCE", "status": "PASS" if "SAME_INPUT_IDEMPOTENCE" not in failures else "FAIL"},
        {"check_id": "SOURCE_BINDING", "status": "PASS" if "SOURCE_BINDING" not in failures else "FAIL"},
        {"check_id": "ZERO_INVESTMENT_AND_RULE_MUTATION", "status": "PASS" if "ZERO_MUTATION" not in failures else "FAIL"},
        {"check_id": "ZERO_TRADE_AUTHORITY", "status": "PASS" if "TRADE_AUTHORITY" not in failures else "FAIL"},
    ]
    validation = {
        "validation_version": "1.0.0",
        "program_id": "FMDL-4D",
        "release_id": decision.get("release_id"),
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": sorted(set(failures)),
        "checks": checks,
        "metrics": {
            **decision.get("metrics", {}),
            "independent_thesis_record_count": len(thesis_records),
            "independent_catalyst_count": len(catalyst_frame),
            "independent_prove_kill_count": len(prove_kill_frame),
            "independent_attribution_record_count": len(attribution_frame),
            "thesis_shape_error_count": thesis_shape_error_count,
            "row_binding_error_count": row_binding_error_count,
            "registry_link_error_count": link_error_count,
            "feedback_error_count": feedback_error_count,
            "attribution_error_count": attribution_error_count,
            "append_only_error_count": append_only_error_count,
            "semantic_hash_error_count": semantic_hash_error_count,
            "manifest_error_count": manifest_error_count,
            "zip_error_count": zip_error_count,
            "governance_error_count": governance_error_count,
            "binding_error_count": binding_error_count,
            "mutation_error_count": mutation_error_count,
            "trade_authority_error_count_independent": trade_authority_error_count,
            "independent_overlay_zip_sha256": original_hash,
            "idempotence_replay_zip_sha256": replay_hash,
        },
        "controlled_limitations": cfg["controlled_limitations"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    core.write_json(candidate / "FMDL4D_VALIDATION.json", validation)
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
