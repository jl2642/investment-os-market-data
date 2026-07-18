from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "outputs/financials/comparability/candidate"
ALLOWED_RESTATEMENT = {
    "ORIGINAL_ONLY",
    "RESTATED_OR_CORRECTED",
    "UNRESOLVED_NO_CANONICAL_PERIODIC_DOCUMENT",
}
ALLOWED_EXCEPTION_COMPARABILITY = {"COMPARABLE_WITH_WARNING", "NOT_COMPARABLE"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=CANDIDATE)
    args = parser.parse_args()
    root = args.candidate
    decision = load_json(root / "FMDL3B3_DECISION.json")
    manifest = load_json(root / "FMDL3B3_MANIFEST.json")
    lineage = pd.read_parquet(root / "FMDL3B3_REVISION_LINEAGE.parquet")
    periods = pd.read_parquet(root / "FMDL3B3_PERIOD_REVISION_STATUS.parquet")
    facts = pd.read_parquet(root / "FMDL3B3_FACT_COMPARABILITY_EXCEPTIONS.parquet")
    bridge = pd.read_parquet(root / "FMDL3B3_COMPARABILITY_BRIDGE.parquet")
    hash_errors = []
    for item in manifest.get("files", []):
        path = root / item["path"]
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            hash_errors.append(item["path"])

    restated_periods = periods["restatement_status"].eq("RESTATED_OR_CORRECTED")
    unresolved_periods = periods["restatement_status"].eq("UNRESOLVED_NO_CANONICAL_PERIODIC_DOCUMENT")
    checks = {
        "DECISION_ACCEPTED": decision.get("status") == "FMDL3B3_COMPARABILITY_AND_RESTATEMENT_HARDENING_ACCEPTED",
        "DECISION_HARD_FAILURES_EMPTY": decision.get("hard_failures") == [],
        "MANIFEST_FILES_PRESENT": all((root / item["path"]).exists() for item in manifest.get("files", [])),
        "MANIFEST_HASHES_MATCH": not hash_errors,
        "REVISION_IDS_UNIQUE": not lineage["revision_id"].duplicated().any(),
        "PERIOD_KEYS_UNIQUE": not periods[["symbol", "report_period_end"]].duplicated().any(),
        "PERIOD_CLASSIFICATIONS_EXPLICIT": periods["restatement_status"].notna().all() and periods["historical_replay_status"].notna().all(),
        "PERIOD_CLASSIFICATIONS_CONTROLLED": set(periods["restatement_status"].dropna()).issubset(ALLOWED_RESTATEMENT),
        "FACT_EXCEPTION_IDS_UNIQUE": not facts["normalized_fact_id"].duplicated().any(),
        "FACT_EXCEPTION_CLASSIFICATIONS_EXPLICIT": facts["restatement_status"].notna().all() and facts["historical_replay_status"].notna().all() and facts["comparability_evidence_status"].notna().all(),
        "COMPARISON_IDS_UNIQUE": not bridge["comparison_id"].duplicated().any(),
        "EXCEPTION_COMPARABILITY_STATUSES_CONTROLLED": set(bridge["comparison_status"].dropna()).issubset(ALLOWED_EXCEPTION_COMPARABILITY),
        "NO_COMPARABLE_ROWS_IN_EXCEPTION_BRIDGE": not bridge["comparison_status"].eq("COMPARABLE").any(),
        "NO_CURRENT_VALID_ROWS_IN_FACT_EXCEPTIONS": not facts["comparability_evidence_status"].eq("CURRENT_VALID").any(),
        "ALL_RESTATEMENTS_REPLAY_CONTROLLED": periods.loc[restated_periods, "historical_replay_status"].eq("LATEST_ONLY_PRE_RESTATEMENT_NUMERIC_REPLAY_BLOCKED").all(),
        "ALL_UNRESOLVED_PERIODS_BLOCKED": periods.loc[unresolved_periods, "historical_replay_status"].eq("BLOCKED_NO_CANONICAL_PERIODIC_DOCUMENT").all(),
        "METRICS_REPLAY": (
            int(decision["metrics"]["classified_document_count"]) == len(lineage)
            and int(decision["metrics"]["period_status_count"]) == len(periods)
            and int(decision["metrics"]["fact_exception_count"]) == len(facts)
            and int(decision["metrics"]["comparison_exception_count"]) == len(bridge)
        ),
        "ZERO_TRADE_AUTHORITY": set(lineage["trade_authority"].dropna()).issubset({"NONE"}) and set(periods["trade_authority"].dropna()).issubset({"NONE"}) and set(facts["trade_authority"].dropna()).issubset({"NONE"}) and set(bridge["trade_authority"].dropna()).issubset({"NONE"})
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "validation_version": "1.1.0",
        "release_id": decision["release_id"],
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": failures,
        "checks": [{"check_id": name, "status": "PASS" if passed else "FAIL"} for name, passed in checks.items()],
        "metrics": decision["metrics"],
        "manifest_hash_errors": hash_errors,
        "authority": decision["authority"],
        "trade_authority": "NONE",
        "next_gate": decision["next_gate"]
    }
    (root / "FMDL3B3_VALIDATION.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
