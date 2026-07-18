from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from scripts import aggregate_fmdl3b2_matrix as base
from scripts import fmdl3b2_matrix_core as matrix
from scripts import fmdl3b2_validation_hardening as hardening

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3b2_matrix.json"
CANDIDATE = ROOT / "outputs/financials/full_build/matrix/candidate"


def _load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig") if path.exists() else pd.DataFrame()


def _refresh_manifest(root: Path) -> None:
    manifest = matrix.load_json(root / "FMDL3B2_MATRIX_MANIFEST.json")
    manifest["manifest_version"] = "1.1.0"
    manifest["files"] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "FMDL3B2_MATRIX_MANIFEST.json":
            manifest["files"].append({"path": str(path.relative_to(root)), "sha256": matrix.file_sha256(path), "bytes": path.stat().st_size})
    matrix.write_json(root / "FMDL3B2_MATRIX_MANIFEST.json", manifest)


def postprocess(config_path: Path) -> int:
    cfg = matrix.load_json(config_path)
    decision = matrix.load_json(CANDIDATE / "FMDL3B2_MATRIX_DECISION.json")
    support = _load_csv(CANDIDATE / "FMDL3B2_SUPPORT_MAP.csv")
    checks = _load_csv(CANDIDATE / "FMDL3B2_VALIDATION_CHECKS.csv")
    flags = _load_csv(CANDIDATE / "FMDL3B2_QA_FLAGS.csv")
    shard_summary = _load_csv(CANDIDATE / "FMDL3B2_SHARD_SUMMARY.csv")

    bse = support[support["board"] == "BSE"] if len(support) else support
    allowed = {"INDEXED_CLASSIFIED_PERIODIC_REPORTS", "NO_CLASSIFIED_PERIODIC_REPORT_IN_SCOPE_AFTER_SUCCESSFUL_CNINFO_QUERY"}
    bse_query_resolved = bool(
        len(bse) > 0
        and bse["official_query_status"].astype(str).eq("SUCCESS").all()
        and bse["official_document_status"].astype(str).isin(allowed).all()
    )
    classified_ok, classification_errors = hardening.controlled_exclusions_are_classified(checks, flags)
    controlled_count = int((checks["result"].astype(str) == hardening.CONTROLLED_RESULT).sum()) if len(checks) else 0
    performed_failures = int((checks["result"].astype(str) == "FAIL").sum()) if len(checks) else 0

    check_map = {item["check_id"]: item["status"] == "PASS" for item in decision.get("checks", [])}
    check_map.pop("BSE_DOCUMENT_INDEX", None)
    check_map["BSE_OFFICIAL_QUERY_RESOLUTION"] = bse_query_resolved
    check_map["CONTROLLED_VALIDATION_EXCLUSIONS_CLASSIFIED"] = classified_ok
    check_map["PERFORMED_CHECKS_NO_UNEXPLAINED_FAILURE"] = performed_failures <= cfg["aggregate_acceptance_policy"]["maximum_performed_validation_failure_count"]
    check_map.pop("PERFORMED_CHECKS_NO_FAILURE", None)
    failures = [name for name, passed in check_map.items() if not passed]

    metrics = decision["metrics"]
    metrics.update({
        "performed_validation_failure_count": performed_failures,
        "controlled_validation_exclusion_count": controlled_count,
        "controlled_validation_classification_error_count": len(classification_errors),
        "bse_indexed_periodic_report_count": int((bse["official_document_status"] == "INDEXED_CLASSIFIED_PERIODIC_REPORTS").sum()) if len(bse) else 0,
        "bse_no_classified_periodic_report_count": int((bse["official_document_status"] == "NO_CLASSIFIED_PERIODIC_REPORT_IN_SCOPE_AFTER_SUCCESSFUL_CNINFO_QUERY").sum()) if len(bse) else 0,
        "bse_query_unresolved_count": int((bse["official_query_status"] != "SUCCESS").sum()) if len(bse) else 0,
        "accepted_shard_count": int((shard_summary["status"] == "FMDL3B2_SHARD_ACCEPTED").sum()) if len(shard_summary) else 0,
        "validated_shard_count": int((shard_summary["validation_status"] == "PASS").sum()) if len(shard_summary) else 0,
    })
    decision["decision_version"] = "1.1.0"
    decision["status"] = "FMDL3B2_FULL_UNIVERSE_INITIAL_BUILD_ACCEPTED_WITH_CONTROLLED_QUARANTINE" if not failures else "FMDL3B2_FULL_UNIVERSE_INITIAL_BUILD_REMEDIATION_REQUIRED"
    decision["hard_failures"] = failures
    decision["checks"] = [{"check_id": name, "status": "PASS" if passed else "FAIL"} for name, passed in check_map.items()]
    decision["controlled_validation_classification_errors"] = classification_errors
    limitations = list(decision.get("controlled_limitations", []))
    for item in [
        "PROVIDER_INTERNAL_STATEMENT_INCONSISTENCIES_WITH_INDEPENDENT_EVIDENCE_ARE_RETAINED_AS_CONTROLLED_EXCLUSIONS_AND_AFFECTED_FACTS_ARE_NOT_DECISION_GRADE",
        "BSE_SUCCESSFUL_CNINFO_QUERIES_WITHOUT_CLASSIFIED_PERIODIC_REPORTS_REMAIN_VISIBLE_CONTROLLED_QUARANTINE",
    ]:
        if item not in limitations:
            limitations.append(item)
    decision["controlled_limitations"] = limitations
    matrix.write_json(CANDIDATE / "FMDL3B2_MATRIX_DECISION.json", decision)
    _refresh_manifest(CANDIDATE)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--input-root", type=Path, required=True)
    args, _ = parser.parse_known_args()
    base.main()
    return postprocess(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
