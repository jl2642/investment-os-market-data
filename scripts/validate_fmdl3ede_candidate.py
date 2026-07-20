from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts import fmdl3ede_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3ede_propagation_resilience.json"


def main() -> int:
    cfg = core.read_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    decision = core.read_json(candidate / "FMDL3E_DECISION.json")
    resilience = core.read_json(candidate / "FMDL3E_RESILIENCE_REPORT.json")
    manifest = core.read_json(candidate / "FMDL3E_MANIFEST.json")
    propagated = pd.read_parquet(candidate / "FMDL3E_PROPAGATED_UNIFIED_CURRENT.parquet")
    full = pd.read_parquet(candidate / "FMDL3E_FULL_REBUILD_REFERENCE.parquet")
    audit = pd.read_csv(candidate / "FMDL3E_FULL_REBUILD_AUDIT.csv", encoding="utf-8-sig")
    idempotence = pd.read_csv(candidate / "FMDL3E_IDEMPOTENCE_AUDIT.csv", encoding="utf-8-sig")
    scope = pd.read_csv(candidate / "FMDL3E_AFFECTED_SCOPE_SNAPSHOT.csv", encoding="utf-8-sig")

    errors: list[str] = []
    for item in manifest["files"]:
        path = candidate / item["path"]
        if not path.exists() or core.sha256_file(path) != item["sha256"] or path.stat().st_size != int(item["bytes"]):
            errors.append(f"MANIFEST_MISMATCH:{item['path']}")
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        errors.append("DECISION_NOT_ACCEPTED")
    if len(propagated) != int(cfg["propagation"]["required_universe_symbol_count"]):
        errors.append("UNIVERSE_COUNT_MISMATCH")
    if propagated["symbol"].duplicated().any():
        errors.append("DUPLICATE_SYMBOL")
    if int(audit["mismatch_count"].sum()) != 0:
        errors.append("FULL_REBUILD_MISMATCH")
    if int(idempotence["mismatch_count"].sum()) != 0:
        errors.append("IDEMPOTENCE_MISMATCH")
    if core.semantic_frame_hash(propagated) != core.semantic_frame_hash(full):
        errors.append("FULL_REBUILD_SEMANTIC_HASH_MISMATCH")
    if not resilience.get("rollback_lkg_preserved"):
        errors.append("ROLLBACK_LKG_NOT_PRESERVED")
    if not all(resilience.get("failure_injection", {}).values()):
        errors.append("FAILURE_INJECTION_NOT_REJECTED")
    if resilience.get("source_hash_errors"):
        errors.append("SOURCE_HASH_MUTATION")
    if set(propagated["trade_authority"].dropna().astype(str)) != {"NONE"}:
        errors.append("TRADE_AUTHORITY_PRESENT")
    recomputed_hashes = {
        "propagated_unified_current": core.semantic_frame_hash(propagated),
        "full_rebuild_reference": core.semantic_frame_hash(full),
        "full_rebuild_audit": core.semantic_frame_hash(audit, sort_by=("column",)),
        "idempotence_audit": core.semantic_frame_hash(idempotence, sort_by=("column",)),
        "affected_scope": core.semantic_frame_hash(scope, sort_by=("event_id",)),
    }
    if recomputed_hashes != decision.get("semantic_hashes"):
        errors.append("SEMANTIC_HASH_REPLAY_MISMATCH")

    check_names = ["MANIFEST", "DECISION", "UNIVERSE_COUNT", "DUPLICATE_SYMBOL", "FULL_REBUILD", "IDEMPOTENCE", "ROLLBACK_LKG", "FAILURE_INJECTION", "SOURCE_HASH", "TRADE_AUTHORITY", "SEMANTIC_HASH"]
    validation = {
        "validation_version": "1.0.0",
        "release_id": decision["release_id"],
        "program_id": "FMDL-3E-DE",
        "status": "PASS" if not errors else "FAIL",
        "hard_failures": errors,
        "checks": [{"check_id": name, "status": "FAIL" if any(error.startswith(name) for error in errors) else "PASS"} for name in check_names],
        "metrics": {
            **decision["metrics"],
            "manifest_error_count": sum(error.startswith("MANIFEST") for error in errors),
            "semantic_hash_error_count": int("SEMANTIC_HASH_REPLAY_MISMATCH" in errors),
            "independent_full_rebuild_mismatch_count": int(audit["mismatch_count"].sum()),
            "independent_idempotence_mismatch_count": int(idempotence["mismatch_count"].sum()),
        },
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    core.write_json(candidate / "FMDL3E_VALIDATION.json", validation)
    core.write_json(candidate / "FMDL3E_MANIFEST.json", core.manifest_for_directory(candidate, decision["release_id"]))
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
