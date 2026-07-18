from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from scripts import fmdl3b2_matrix_core as matrix
from scripts import fmdl3b2_validation_hardening as hardening
from scripts import validate_fmdl3b2_matrix as base

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3b2_matrix.json"
DEFAULT_CANDIDATE = ROOT / "outputs/financials/full_build/matrix/candidate"


def _load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig") if path.exists() else pd.DataFrame()


def _controlled_facts_downgraded(root: Path, checks: pd.DataFrame) -> tuple[bool, list[str]]:
    errors: list[str] = []
    cache: dict[int, pd.DataFrame] = {}
    controlled = checks[checks["result"].astype(str).eq(hardening.CONTROLLED_RESULT)] if len(checks) else checks
    for _, row in controlled.iterrows():
        shard_id = int(row.get("shard_id"))
        if shard_id not in cache:
            cache[shard_id] = pd.read_parquet(root / "normalized" / f"shard-{shard_id:02d}.parquet")
        normalized = cache[shard_id]
        test = str(row.get("test"))
        symbol_match = re.match(r"^([0-9]{6}\.(?:SH|SZ|BJ)):", test)
        affected_match = re.search(r"affected_line_items=([^;]+)", str(row.get("notes", "")))
        if not symbol_match or not affected_match:
            errors.append(f"unparseable_controlled_check=shard-{shard_id:02d}:{test}")
            continue
        symbol = symbol_match.group(1)
        period = str(row.get("period"))
        affected = affected_match.group(1).split(",")
        facts = normalized[
            normalized["symbol"].astype(str).eq(symbol)
            & normalized["period_end"].astype(str).eq(period)
            & normalized["line_item_id"].astype(str).isin(affected)
        ]
        if facts.empty:
            errors.append(f"missing_affected_facts=shard-{shard_id:02d}:{symbol}:{period}:{affected}")
            continue
        if facts["decision_grade_eligible"].astype(bool).any():
            errors.append(f"decision_grade_not_removed=shard-{shard_id:02d}:{symbol}:{period}:{affected}")
        if not facts["record_quality"].astype(str).eq(hardening.CONTROLLED_FLAG_STATUS).all():
            errors.append(f"record_quality_not_controlled=shard-{shard_id:02d}:{symbol}:{period}:{affected}")
    return not errors, errors


def _refresh_manifest(root: Path) -> None:
    manifest = matrix.load_json(root / "FMDL3B2_MATRIX_MANIFEST.json")
    manifest["manifest_version"] = "1.2.0"
    manifest["files"] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "FMDL3B2_MATRIX_MANIFEST.json":
            manifest["files"].append({"path": str(path.relative_to(root)), "sha256": matrix.file_sha256(path), "bytes": path.stat().st_size})
    matrix.write_json(root / "FMDL3B2_MATRIX_MANIFEST.json", manifest)


def postprocess(root: Path) -> int:
    payload = matrix.load_json(root / "FMDL3B2_MATRIX_VALIDATION.json")
    decision = matrix.load_json(root / "FMDL3B2_MATRIX_DECISION.json")
    support = _load_csv(root / "FMDL3B2_SUPPORT_MAP.csv")
    checks_frame = _load_csv(root / "FMDL3B2_VALIDATION_CHECKS.csv")
    flags = _load_csv(root / "FMDL3B2_QA_FLAGS.csv")

    check_map = {item["check_id"]: item for item in payload.get("checks", [])}
    check_map.pop("BSE_OFFICIAL_DOCUMENT_INDEX", None)
    check_map.pop("PERFORMED_CHECKS_NO_FAILURE", None)

    bse = support[support["board"] == "BSE"] if len(support) else support
    allowed = {"INDEXED_CLASSIFIED_PERIODIC_REPORTS", "NO_CLASSIFIED_PERIODIC_REPORT_IN_SCOPE_AFTER_SUCCESSFUL_CNINFO_QUERY"}
    bse_ok = bool(
        len(bse) > 0
        and bse["official_query_status"].astype(str).eq("SUCCESS").all()
        and bse["official_document_status"].astype(str).isin(allowed).all()
    )
    check_map["BSE_OFFICIAL_QUERY_RESOLUTION"] = {
        "check_id": "BSE_OFFICIAL_QUERY_RESOLUTION",
        "status": "PASS" if bse_ok else "FAIL",
        "detail": {
            "bse_rows": len(bse),
            "query_unresolved": int((bse["official_query_status"].astype(str) != "SUCCESS").sum()) if len(bse) else 0,
            "document_status": bse["official_document_status"].value_counts().to_dict() if len(bse) else {},
        },
    }
    classified_ok, classification_errors = hardening.controlled_exclusions_are_classified(checks_frame, flags)
    check_map["CONTROLLED_VALIDATION_EXCLUSIONS_CLASSIFIED"] = {
        "check_id": "CONTROLLED_VALIDATION_EXCLUSIONS_CLASSIFIED",
        "status": "PASS" if classified_ok else "FAIL",
        "detail": classification_errors,
    }
    downgraded_ok, downgrade_errors = _controlled_facts_downgraded(root, checks_frame)
    check_map["CONTROLLED_FACTS_REMOVED_FROM_DECISION_GRADE"] = {
        "check_id": "CONTROLLED_FACTS_REMOVED_FROM_DECISION_GRADE",
        "status": "PASS" if downgraded_ok else "FAIL",
        "detail": downgrade_errors,
    }
    performed_failures = int((checks_frame["result"].astype(str) == "FAIL").sum()) if len(checks_frame) else 0
    check_map["PERFORMED_CHECKS_NO_UNEXPLAINED_FAILURE"] = {
        "check_id": "PERFORMED_CHECKS_NO_UNEXPLAINED_FAILURE",
        "status": "PASS" if performed_failures == 0 else "FAIL",
        "detail": {"rows": performed_failures, "decision": decision["metrics"].get("performed_validation_failure_count")},
    }

    failures = [check_id for check_id, item in check_map.items() if item["status"] != "PASS"]
    payload["validation_version"] = "1.1.0"
    payload["checks"] = list(check_map.values())
    payload["hard_failures"] = failures
    payload["status"] = "PASS" if not failures else "FAIL"
    payload["decision_status"] = decision["status"]
    payload["metrics"] = decision["metrics"]
    matrix.write_json(root / "FMDL3B2_MATRIX_VALIDATION.json", payload)
    _refresh_manifest(root)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--candidate-root", type=Path, default=DEFAULT_CANDIDATE)
    args, _ = parser.parse_known_args()
    base.main()
    return postprocess(args.candidate_root)


if __name__ == "__main__":
    raise SystemExit(main())
