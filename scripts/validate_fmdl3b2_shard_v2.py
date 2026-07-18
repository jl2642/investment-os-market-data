from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from scripts import fmdl3b2_matrix_core as matrix
from scripts import fmdl3b2_validation_hardening as hardening
from scripts import validate_fmdl3b2_shard as base

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3b2_matrix.json"


def _refresh_manifest(root: Path) -> None:
    manifest = matrix.load_json(root / "SHARD_MANIFEST.json")
    manifest["manifest_version"] = "1.3.0"
    manifest["files"] = []
    for path in sorted(root.iterdir()):
        if path.name != "SHARD_MANIFEST.json":
            manifest["files"].append({"path": path.name, "sha256": matrix.file_sha256(path), "bytes": path.stat().st_size})
    matrix.write_json(root / "SHARD_MANIFEST.json", manifest)


def _controlled_facts_are_downgraded(checks: pd.DataFrame, normalized: pd.DataFrame) -> tuple[bool, list[str]]:
    errors: list[str] = []
    controlled = checks[checks["result"].astype(str).eq(hardening.CONTROLLED_RESULT)] if len(checks) else checks
    for _, row in controlled.iterrows():
        test = str(row.get("test"))
        match = re.match(r"^([0-9]{6}\.(?:SH|SZ|BJ)):", test)
        symbol = match.group(1) if match else None
        period = str(row.get("period"))
        note = str(row.get("notes", ""))
        affected_match = re.search(r"affected_line_items=([^;]+)", note)
        affected = affected_match.group(1).split(",") if affected_match else []
        if not symbol or not affected:
            errors.append(f"unparseable_controlled_check={test}:{period}")
            continue
        facts = normalized[
            normalized["symbol"].astype(str).eq(symbol)
            & normalized["period_end"].astype(str).eq(period)
            & normalized["line_item_id"].astype(str).isin(affected)
        ]
        if facts.empty:
            errors.append(f"missing_affected_facts={symbol}:{period}:{affected}")
            continue
        if facts["decision_grade_eligible"].astype(bool).any():
            errors.append(f"decision_grade_not_removed={symbol}:{period}:{affected}")
        if not facts["record_quality"].astype(str).eq(hardening.CONTROLLED_FLAG_STATUS).all():
            errors.append(f"record_quality_not_controlled={symbol}:{period}:{affected}")
    return not errors, errors


def postprocess(shard_id: int) -> int:
    root = ROOT / "outputs/financials/full_build/matrix/shards" / f"shard-{shard_id:02d}"
    payload = matrix.load_json(root / "SHARD_VALIDATION.json")
    decision = matrix.load_json(root / "SHARD_DECISION.json")
    support = pd.read_csv(root / "SHARD_SUPPORT_MAP.csv", encoding="utf-8-sig")
    checks_frame = pd.read_csv(root / "SHARD_VALIDATION_CHECKS.csv", encoding="utf-8-sig")
    flags = pd.read_csv(root / "SHARD_QA_FLAGS.csv", encoding="utf-8-sig")
    normalized = pd.read_parquet(root / "SHARD_NORMALIZED_LONG.parquet")

    check_map = {item["check_id"]: item for item in payload.get("checks", [])}
    check_map.pop("BSE_DOCUMENT_INDEX", None)
    bse = support[support["board"] == "BSE"]
    allowed = {"INDEXED_CLASSIFIED_PERIODIC_REPORTS", "NO_CLASSIFIED_PERIODIC_REPORT_IN_SCOPE_AFTER_SUCCESSFUL_CNINFO_QUERY"}
    bse_ok = bool(
        bse["official_query_status"].astype(str).eq("SUCCESS").all()
        and bse["official_document_status"].astype(str).isin(allowed).all()
    ) if len(bse) else True
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
    downgraded_ok, downgrade_errors = _controlled_facts_are_downgraded(checks_frame, normalized)
    check_map["CONTROLLED_FACTS_REMOVED_FROM_DECISION_GRADE"] = {
        "check_id": "CONTROLLED_FACTS_REMOVED_FROM_DECISION_GRADE",
        "status": "PASS" if downgraded_ok else "FAIL",
        "detail": downgrade_errors,
    }
    failures = [check_id for check_id, item in check_map.items() if item["status"] != "PASS"]
    payload["validation_version"] = "1.1.0"
    payload["checks"] = list(check_map.values())
    payload["hard_failures"] = failures
    payload["status"] = "PASS" if not failures else "FAIL"
    payload["decision_status"] = decision["status"]
    payload["metrics"] = decision["metrics"]
    matrix.write_json(root / "SHARD_VALIDATION.json", payload)
    _refresh_manifest(root)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--shard-id", type=int, required=True)
    args, _ = parser.parse_known_args()
    base.main()
    return postprocess(args.shard_id)


if __name__ == "__main__":
    raise SystemExit(main())
