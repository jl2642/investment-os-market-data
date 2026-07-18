from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3b4_statement_current.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    cfg = load_json(CONFIG)
    statement_pointer_path = ROOT / cfg["input_pointers"]["statement_base"]
    comparability_pointer_path = ROOT / cfg["input_pointers"]["comparability"]
    statement_pointer = load_json(statement_pointer_path)
    comparability_pointer = load_json(comparability_pointer_path)
    statement_validation_path = ROOT / cfg["required_input_files"]["statement_validation"]
    comparability_validation_path = ROOT / cfg["required_input_files"]["comparability_validation"]
    statement_validation = load_json(statement_validation_path)
    comparability_validation = load_json(comparability_validation_path)

    statement_root = ROOT / statement_pointer["release_root"]
    comparability_root = ROOT / comparability_pointer["release_root"]
    statement_release = load_json(statement_root / "FMDL3B2_RELEASE.json")
    comparability_release = load_json(comparability_root / "FMDL3B3_RELEASE.json")

    candidate = ROOT / cfg["publication"]["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True)

    catalog_rows = []
    roles = {
        "statement_normalized": [ROOT / p for p in statement_release["normalized_shards"]],
        "statement_revisions": [ROOT / p for p in statement_release["revision_shards"]],
        "statement_sources": [ROOT / p for p in statement_release["source_index_shards"]],
        "comparability_revision_lineage": [ROOT / comparability_release["revision_lineage_path"]],
        "comparability_period_status": [ROOT / comparability_release["period_revision_status_path"]],
        "comparability_fact_exceptions": [ROOT / comparability_release["fact_exception_path"]],
        "comparability_bridge": [ROOT / comparability_release["comparability_bridge_path"]],
    }
    for role, paths in roles.items():
        for ordinal, path in enumerate(paths):
            exists = path.exists()
            catalog_rows.append({
                "dataset_role": role,
                "ordinal": ordinal,
                "path": str(path.relative_to(ROOT)),
                "exists": exists,
                "bytes": path.stat().st_size if exists else None,
                "sha256": sha256(path) if exists else None,
                "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
                "trade_authority": "NONE",
            })
    catalog = pd.DataFrame(catalog_rows)
    catalog.to_csv(candidate / "FMDL3B4_STATEMENT_CATALOG.csv", index=False, encoding="utf-8-sig")

    normalized_count = int(statement_validation["metrics"]["normalized_fact_count"])
    comparability_replay_count = int(comparability_validation["metrics"]["normalized_fact_count_replayed"])
    restated_count = int(comparability_validation["metrics"]["restated_or_corrected_period_count"])
    unresolved_count = int(comparability_validation["metrics"]["unresolved_no_canonical_period_count"])
    checks = {
        "FMDL3B2_ENTRY_ACCEPTED": statement_pointer.get("status") == cfg["entry_gates"]["fmdl3b2_status"],
        "FMDL3B3_ENTRY_ACCEPTED": comparability_pointer.get("status") == cfg["entry_gates"]["fmdl3b3_status"],
        "STATEMENT_VALIDATION_PASS": statement_validation.get("status") == "PASS" and statement_validation.get("hard_failures") == [],
        "COMPARABILITY_VALIDATION_PASS": comparability_validation.get("status") == "PASS" and comparability_validation.get("hard_failures") == [],
        "STATEMENT_RELEASE_ID_MATCH": statement_release.get("release_id") == statement_pointer.get("release_id"),
        "COMPARABILITY_RELEASE_ID_MATCH": comparability_release.get("release_id") == comparability_pointer.get("release_id"),
        "EXACT_32_NORMALIZED_SHARDS": len(roles["statement_normalized"]) == 32,
        "EXACT_32_REVISION_SHARDS": len(roles["statement_revisions"]) == 32,
        "EXACT_32_SOURCE_INDEX_SHARDS": len(roles["statement_sources"]) == 32,
        "ALL_CATALOG_FILES_EXIST": bool(catalog["exists"].all()),
        "NORMALIZED_FACT_REPLAY_MATCH": normalized_count == comparability_replay_count,
        "PERIOD_CLASSIFICATIONS_EXPLICIT": next((x["status"] for x in comparability_validation["checks"] if x["check_id"] == "PERIOD_CLASSIFICATIONS_EXPLICIT"), None) == "PASS",
        "ALL_RESTATEMENTS_REPLAY_CONTROLLED": next((x["status"] for x in comparability_validation["checks"] if x["check_id"] == "ALL_RESTATEMENTS_REPLAY_CONTROLLED"), None) == "PASS",
        "ALL_UNRESOLVED_PERIODS_BLOCKED": next((x["status"] for x in comparability_validation["checks"] if x["check_id"] == "ALL_UNRESOLVED_PERIODS_BLOCKED"), None) == "PASS",
        "ZERO_TRADE_AUTHORITY": statement_pointer.get("trade_authority") == "NONE" and comparability_pointer.get("trade_authority") == "NONE" and set(catalog["trade_authority"]) == {"NONE"},
    }
    failures = [name for name, passed in checks.items() if not passed]
    release_id = f"FMDL3B4_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"
    metrics = {
        "statement_base_release_id": statement_pointer["release_id"],
        "comparability_release_id": comparability_pointer["release_id"],
        "universe_symbol_count": int(statement_validation["metrics"]["universe_symbol_count"]),
        "supported_symbol_count": int(statement_validation["metrics"]["supported_symbol_count"]),
        "quarantined_symbol_count": int(statement_validation["metrics"]["quarantined_symbol_count"]),
        "normalized_fact_count": normalized_count,
        "decision_grade_fact_count": int(statement_validation["metrics"]["decision_grade_fact_count"]),
        "revision_row_count": int(comparability_validation["metrics"]["input_revision_row_count"]),
        "period_status_count": int(comparability_validation["metrics"]["period_status_count"]),
        "restated_or_corrected_period_count": restated_count,
        "unresolved_no_canonical_period_count": unresolved_count,
        "comparison_count_replayed": int(comparability_validation["metrics"]["comparison_count_replayed"]),
        "comparison_exception_count": int(comparability_validation["metrics"]["comparison_exception_count"]),
        "catalog_file_count": len(catalog),
        "missing_catalog_file_count": int((~catalog["exists"]).sum()),
    }
    decision = {
        "decision_version": "1.0.0",
        "release_id": release_id,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "program_id": "FMDL-3B-4",
        "status": cfg["exit_status"] if not failures else "FMDL3B4_REMEDIATION_REQUIRED",
        "hard_failures": failures,
        "checks": [{"check_id": k, "status": "PASS" if v else "FAIL"} for k, v in checks.items()],
        "metrics": metrics,
        "statement_base_release_id": statement_pointer["release_id"],
        "comparability_release_id": comparability_pointer["release_id"],
        "controlled_limitations": comparability_release.get("controlled_limitations", []),
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    write_json(candidate / "FMDL3B4_DECISION.json", decision)
    write_json(candidate / "FMDL3B4_STATEMENT_BASE_POINTER.json", statement_pointer)
    write_json(candidate / "FMDL3B4_COMPARABILITY_POINTER.json", comparability_pointer)
    write_json(candidate / "FMDL3B4_STATEMENT_VALIDATION_SNAPSHOT.json", statement_validation)
    write_json(candidate / "FMDL3B4_COMPARABILITY_VALIDATION_SNAPSHOT.json", comparability_validation)

    manifest = {
        "manifest_version": "1.0.0",
        "release_id": release_id,
        "files": [],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    for path in sorted(candidate.iterdir()):
        if path.is_file() and path.name != "FMDL3B4_MANIFEST.json":
            manifest["files"].append({"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size})
    write_json(candidate / "FMDL3B4_MANIFEST.json", manifest)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
