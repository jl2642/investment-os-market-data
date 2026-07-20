from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

import pandas as pd

from scripts import fmdl4a_core as core
from scripts.run_fmdl4a_adapter import deterministic_zip

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl4a_research_handoff_adapter.json"


def read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def main() -> int:
    cfg = core.read_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    adapter_root = candidate / cfg["adapter"]["overlay_namespace"]
    decision = core.read_json(candidate / "FMDL4A_DECISION.json")
    manifest = core.read_json(candidate / "FMDL4A_RELEASE5_OVERLAY_MANIFEST.json")
    binding = core.read_json(adapter_root / "STATE_CURRENT/FMDL4A_BINDING_STATE.json")
    routing = core.read_json(adapter_root / "CORE_STATIC/FMDL4A_PUBLIC_EQUITY_ROUTING_CONTRACT.json")
    firewall = core.read_json(adapter_root / "CORE_STATIC/FMDL4A_AUTHORITY_FIREWALL.json")
    envelope = pd.read_parquet(adapter_root / "EVIDENCE/FMDL4A_EVIDENCE_ENVELOPE_CURRENT.parquet")
    registry = pd.read_csv(adapter_root / "EVIDENCE/FMDL4A_RESEARCH_PRIORITY_REGISTRY.csv", dtype={"symbol": str})
    records = read_jsonl(adapter_root / "EVIDENCE/FMDL4A_EVIDENCE_ENVELOPE_CURRENT.jsonl")
    overlay_zip = candidate / "FMDL4A_RELEASE5_ADAPTER_OVERLAY.zip"

    failures: list[str] = []
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        failures.append("DECISION")
    if len(envelope) != cfg["evidence_envelope"]["required_universe_symbol_count"] or envelope["symbol"].duplicated().any():
        failures.append("ENVELOPE_UNIVERSE")
    if len(registry) != cfg["evidence_envelope"]["required_longlist_symbol_count"] or registry["symbol"].duplicated().any():
        failures.append("RESEARCH_REGISTRY")
    if len(records) != len(envelope):
        failures.append("JSONL_COUNT")

    record_by_symbol = {record.get("symbol"): record for record in records}
    envelope_shape_error_count = sum(bool(core.validate_envelope_shape(record)) for record in records)
    if envelope_shape_error_count:
        failures.append("ENVELOPE_SHAPE")
    if set(record_by_symbol) != set(envelope["symbol"].astype(str)):
        failures.append("ENVELOPE_SYMBOL_SET")
    row_semantic_mismatch_count = 0
    for row in envelope.to_dict(orient="records"):
        record = record_by_symbol.get(str(row["symbol"]))
        if not record or row.get("evidence_id") != record.get("evidence_id") or row.get("semantic_hash") != record.get("semantic_hash"):
            row_semantic_mismatch_count += 1
    if row_semantic_mismatch_count:
        failures.append("ENVELOPE_ROW_BINDING")

    envelope_hash = core.semantic_frame_hash(envelope)
    registry_hash = core.semantic_frame_hash(registry, sort_by=("overall_rank", "symbol"))
    if envelope_hash != decision.get("semantic_hashes", {}).get("evidence_envelope"):
        failures.append("ENVELOPE_SEMANTIC_HASH")
    if registry_hash != decision.get("semantic_hashes", {}).get("research_priority_registry"):
        failures.append("REGISTRY_SEMANTIC_HASH")

    manifest_error_count = 0
    expected_zip_entries: dict[str, dict] = {}
    for item in manifest.get("files", []):
        source = ROOT / item["source_path"]
        if not source.exists() or core.sha256_file(source) != item["sha256"] or source.stat().st_size != item["bytes"]:
            manifest_error_count += 1
        package_path = str(item["package_path"])
        prefix = cfg["adapter"]["overlay_namespace"] + "/"
        if not package_path.startswith(prefix):
            manifest_error_count += 1
            continue
        expected_zip_entries[package_path[len(prefix):]] = item
    if manifest_error_count:
        failures.append("OVERLAY_MANIFEST")

    zip_error_count = 0
    with zipfile.ZipFile(overlay_zip, "r") as archive:
        actual_names = set(archive.namelist())
        if actual_names != set(expected_zip_entries):
            zip_error_count += 1
        for name, item in expected_zip_entries.items():
            try:
                payload = archive.read(name)
            except KeyError:
                zip_error_count += 1
                continue
            digest = hashlib.sha256(payload).hexdigest()
            if len(payload) != item["bytes"] or digest != item["sha256"]:
                zip_error_count += 1
    if zip_error_count:
        failures.append("OVERLAY_ZIP")

    with tempfile.TemporaryDirectory() as tmp:
        replay_zip = Path(tmp) / "replay.zip"
        deterministic_zip(adapter_root, replay_zip)
        replay_hash = core.sha256_file(replay_zip)
    original_zip_hash = core.sha256_file(overlay_zip)
    if replay_hash != original_zip_hash or original_zip_hash != decision.get("semantic_hashes", {}).get("overlay_zip"):
        failures.append("SAME_INPUT_IDEMPOTENCE")

    base = cfg["external_canonical_base"]
    base_identity_errors = 0
    for key, expected in [
        ("package_name", base["package_name"]),
        ("release_sequence", base["release_sequence"]),
        ("run_id", base["run_id"]),
        ("package_sha256", base["package_sha256"]),
        ("status", base["status"]),
    ]:
        if binding.get("base_package", {}).get(key) != expected:
            base_identity_errors += 1
    if base_identity_errors:
        failures.append("BASE_IDENTITY")

    mutation_error_count = 0
    for payload in [binding, firewall, manifest]:
        for key in ["base_state_mutation_count", "existing_path_replacement_count"]:
            if int(payload.get(key, 0)) != 0:
                mutation_error_count += 1
    for key in ["candidate_pool_mutation_count", "simulation_mutation_count", "real_account_mutation_count"]:
        if int(binding.get(key, 0)) != 0:
            mutation_error_count += 1
    if mutation_error_count:
        failures.append("STATE_MUTATION")

    trade_authority_error_count = 0
    for payload in [decision, manifest, binding, routing, firewall]:
        if payload.get("trade_authority") != "NONE":
            trade_authority_error_count += 1
    trade_authority_error_count += int((envelope["trade_authority"].astype(str) != "NONE").sum())
    trade_authority_error_count += int((registry["trade_authority"].astype(str) != "NONE").sum())
    if trade_authority_error_count:
        failures.append("TRADE_AUTHORITY")

    evidence_ids = set(envelope["evidence_id"].astype(str))
    unknown_registry_evidence_count = int((~registry["evidence_id"].astype(str).isin(evidence_ids)).sum())
    if unknown_registry_evidence_count:
        failures.append("RESEARCH_REGISTRY_EVIDENCE_BINDING")
    if routing.get("research_object_creation_phase") != "FMDL-4B" or routing.get("state_mutation_phase") != "FMDL-4C":
        failures.append("PHASE_OWNERSHIP")

    metrics = {
        **decision.get("metrics", {}),
        "envelope_shape_error_count_independent": envelope_shape_error_count,
        "envelope_row_binding_error_count": row_semantic_mismatch_count,
        "manifest_error_count": manifest_error_count,
        "zip_error_count": zip_error_count,
        "base_identity_error_count": base_identity_errors,
        "mutation_error_count": mutation_error_count,
        "trade_authority_error_count_independent": trade_authority_error_count,
        "unknown_registry_evidence_count": unknown_registry_evidence_count,
        "independent_envelope_semantic_hash": envelope_hash,
        "independent_registry_semantic_hash": registry_hash,
        "independent_overlay_zip_sha256": original_zip_hash,
        "idempotence_replay_zip_sha256": replay_hash,
    }
    checks = [
        {"check_id": "DECISION", "status": "PASS" if "DECISION" not in failures else "FAIL"},
        {"check_id": "ENVELOPE_AND_REGISTRY", "status": "PASS" if not {"ENVELOPE_UNIVERSE", "RESEARCH_REGISTRY", "JSONL_COUNT", "ENVELOPE_SHAPE", "ENVELOPE_SYMBOL_SET", "ENVELOPE_ROW_BINDING", "RESEARCH_REGISTRY_EVIDENCE_BINDING"}.intersection(failures) else "FAIL"},
        {"check_id": "SEMANTIC_HASHES", "status": "PASS" if not {"ENVELOPE_SEMANTIC_HASH", "REGISTRY_SEMANTIC_HASH"}.intersection(failures) else "FAIL"},
        {"check_id": "OVERLAY_MANIFEST_AND_ZIP", "status": "PASS" if not {"OVERLAY_MANIFEST", "OVERLAY_ZIP"}.intersection(failures) else "FAIL"},
        {"check_id": "SAME_INPUT_IDEMPOTENCE", "status": "PASS" if "SAME_INPUT_IDEMPOTENCE" not in failures else "FAIL"},
        {"check_id": "BASE_IDENTITY_AND_PHASE_OWNERSHIP", "status": "PASS" if not {"BASE_IDENTITY", "PHASE_OWNERSHIP"}.intersection(failures) else "FAIL"},
        {"check_id": "ZERO_STATE_MUTATION", "status": "PASS" if "STATE_MUTATION" not in failures else "FAIL"},
        {"check_id": "ZERO_TRADE_AUTHORITY", "status": "PASS" if "TRADE_AUTHORITY" not in failures else "FAIL"},
    ]
    validation = {
        "validation_version": "1.0.0",
        "release_id": decision.get("release_id"),
        "program_id": "FMDL-4A",
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": sorted(set(failures)),
        "checks": checks,
        "metrics": metrics,
        "controlled_limitations": cfg["controlled_limitations"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    core.write_json(candidate / "FMDL4A_VALIDATION.json", validation)
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
