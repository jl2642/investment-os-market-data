from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "outputs/financials/statements/candidate"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    decision = load_json(CANDIDATE / "FMDL3B4_DECISION.json")
    manifest = load_json(CANDIDATE / "FMDL3B4_MANIFEST.json")
    catalog = pd.read_csv(CANDIDATE / "FMDL3B4_STATEMENT_CATALOG.csv", encoding="utf-8-sig")
    statement_validation = load_json(CANDIDATE / "FMDL3B4_STATEMENT_VALIDATION_SNAPSHOT.json")
    comparability_validation = load_json(CANDIDATE / "FMDL3B4_COMPARABILITY_VALIDATION_SNAPSHOT.json")

    hash_errors = []
    for item in manifest.get("files", []):
        path = CANDIDATE / item["path"]
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            hash_errors.append(item["path"])

    role_counts = catalog.groupby("dataset_role").size().to_dict()
    checks = {
        "DECISION_ACCEPTED": decision.get("status") == "FMDL3B4_POINT_IN_TIME_STATEMENT_STORE_ACCEPTED",
        "DECISION_HARD_FAILURES_EMPTY": decision.get("hard_failures") == [],
        "MANIFEST_FILES_PRESENT": all((CANDIDATE / item["path"]).exists() for item in manifest.get("files", [])),
        "MANIFEST_HASHES_MATCH": not hash_errors,
        "CATALOG_PATHS_UNIQUE": not catalog["path"].duplicated().any(),
        "CATALOG_ALL_FILES_EXIST": catalog["exists"].astype(bool).all(),
        "EXACT_32_NORMALIZED_SHARDS": role_counts.get("statement_normalized") == 32,
        "EXACT_32_REVISION_SHARDS": role_counts.get("statement_revisions") == 32,
        "EXACT_32_SOURCE_INDEX_SHARDS": role_counts.get("statement_sources") == 32,
        "COMPARABILITY_ASSETS_COMPLETE": all(role_counts.get(role) == 1 for role in ["comparability_revision_lineage", "comparability_period_status", "comparability_fact_exceptions", "comparability_bridge"]),
        "STATEMENT_VALIDATION_PASS": statement_validation.get("status") == "PASS" and statement_validation.get("hard_failures") == [],
        "COMPARABILITY_VALIDATION_PASS": comparability_validation.get("status") == "PASS" and comparability_validation.get("hard_failures") == [],
        "NORMALIZED_FACT_REPLAY_MATCH": int(statement_validation["metrics"]["normalized_fact_count"]) == int(comparability_validation["metrics"]["normalized_fact_count_replayed"]),
        "ALL_RESTATEMENTS_REPLAY_CONTROLLED": next((x["status"] for x in comparability_validation["checks"] if x["check_id"] == "ALL_RESTATEMENTS_REPLAY_CONTROLLED"), None) == "PASS",
        "ALL_UNRESOLVED_PERIODS_BLOCKED": next((x["status"] for x in comparability_validation["checks"] if x["check_id"] == "ALL_UNRESOLVED_PERIODS_BLOCKED"), None) == "PASS",
        "ZERO_TRADE_AUTHORITY": set(catalog["trade_authority"].dropna()) == {"NONE"} and decision.get("trade_authority") == "NONE",
        "NEXT_GATE_FMDL3C": decision.get("next_gate") == "FMDL-3C_FINANCIAL_QUALITY_GROWTH_AND_BALANCE_SHEET_FACTORS",
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "validation_version": "1.0.0",
        "release_id": decision["release_id"],
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": failures,
        "checks": [{"check_id": k, "status": "PASS" if v else "FAIL"} for k, v in checks.items()],
        "metrics": decision["metrics"],
        "manifest_hash_errors": hash_errors,
        "authority": decision["authority"],
        "trade_authority": "NONE",
        "next_gate": decision["next_gate"],
    }
    (CANDIDATE / "FMDL3B4_VALIDATION.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
