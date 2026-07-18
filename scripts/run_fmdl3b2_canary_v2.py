from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from scripts import run_fmdl3b2_canary as base


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    base_result = base.main()
    cfg = base.load_json(base.CONFIG)
    candidate = base.ROOT / cfg["publication"]["candidate_root"]
    decision_path = candidate / "FMDL3B2_CANARY_DECISION.json"
    checks_path = candidate / "FMDL3B2_CANARY_VALIDATION_CHECKS.csv"
    manifest_path = candidate / "FMDL3B2_CANARY_MANIFEST.json"

    decision = base.load_json(decision_path)
    checks = pd.read_csv(checks_path, encoding="utf-8-sig")
    performed_failures = int((checks["result"] == "FAIL").sum()) if len(checks) else 0
    maximum = int(cfg["acceptance_policy"]["maximum_performed_validation_failure_count"])

    decision["decision_version"] = "1.1.0"
    decision["metrics"]["performed_validation_failure_count"] = performed_failures
    decision["checks"] = [
        check for check in decision.get("checks", []) if check.get("check_id") != "PERFORMED_CHECKS_NO_FAILURE"
    ]
    decision["checks"].append(
        {
            "check_id": "PERFORMED_CHECKS_NO_FAILURE",
            "status": "PASS" if performed_failures <= maximum else "FAIL",
            "detail": {"observed": performed_failures, "maximum": maximum},
        }
    )
    failures = [check["check_id"] for check in decision["checks"] if check["status"] != "PASS"]
    decision["hard_failures"] = failures
    decision["status"] = (
        "FMDL3B2_CANARY_ACCEPTED_FULL_UNIVERSE_MATRIX_AUTHORIZED"
        if not failures
        else "FMDL3B2_CANARY_REMEDIATION_REQUIRED"
    )
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = base.load_json(manifest_path)
    manifest["manifest_version"] = "1.1.0"
    manifest["files"] = []
    for path in sorted(candidate.iterdir()):
        if path.name != manifest_path.name:
            manifest["files"].append(
                {"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size}
            )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if base_result == 0 and not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
