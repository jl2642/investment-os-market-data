from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from scripts import fmdl3b2_matrix_core as matrix
from scripts import fmdl3b_core as core
from scripts import fmdl3b_semantic_overrides as semantic

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3b2_matrix.json"
UNIVERSE = ROOT / "outputs/current/DAILY_MARKET_SNAPSHOT.csv"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--shard-id", type=int, required=True)
    args = parser.parse_args()
    cfg = matrix.load_json(args.config)
    shard_count = int(cfg["sharding"]["shard_count"])
    shard_name = f"shard-{args.shard_id:02d}"
    root = ROOT / "outputs/financials/full_build/matrix/shards" / shard_name

    decision = matrix.load_json(root / "SHARD_DECISION.json")
    manifest = matrix.load_json(root / "SHARD_MANIFEST.json")
    symbols = pd.read_csv(root / "SHARD_SYMBOLS.csv", encoding="utf-8-sig")
    support = pd.read_csv(root / "SHARD_SUPPORT_MAP.csv", encoding="utf-8-sig")
    conflicts = pd.read_csv(root / "SHARD_CONFLICT_LOG.csv", encoding="utf-8-sig")
    checks_frame = pd.read_csv(root / "SHARD_VALIDATION_CHECKS.csv", encoding="utf-8-sig")
    raw = pd.read_parquet(root / "SHARD_RAW_FACTS.parquet")
    normalized = pd.read_parquet(root / "SHARD_NORMALIZED_LONG.parquet")
    revisions = pd.read_parquet(root / "SHARD_REVISION_LEDGER.parquet")
    sources = pd.read_parquet(root / "SHARD_SOURCE_INDEX.parquet")

    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: Any) -> None:
        checks.append({"check_id": check_id, "status": "PASS" if passed else "FAIL", "detail": detail})

    universe = matrix.load_universe(UNIVERSE)
    expected = matrix.assign_shards(universe, shard_count)[args.shard_id]
    observed = symbols["symbol"].astype(str).tolist()
    add("SHARD_ID", decision.get("shard_id") == args.shard_id, decision.get("shard_id"))
    add("DECISION_STATUS", decision.get("status") == "FMDL3B2_SHARD_ACCEPTED", decision.get("status"))
    add("DECISION_HARD_FAILURES", decision.get("hard_failures") == [], decision.get("hard_failures"))
    add("EXACT_DETERMINISTIC_MEMBERSHIP", observed == expected, {"expected": len(expected), "observed": len(observed)})
    add("MEMBERSHIP_HASH", decision.get("membership_hash") == matrix.shard_membership_hash(expected), decision.get("membership_hash"))
    add("SUPPORT_MAP_EXACT", set(support["symbol"].astype(str)) == set(expected) and not support["symbol"].duplicated().any(), len(support))
    add("ALL_SUPPORTED_OR_QUARANTINED", set(support["statement_status"]).issubset({"SUPPORTED", "QUARANTINED"}), sorted(set(support["statement_status"])))

    non_bse = support[support["board"] != "BSE"]
    supported_ratio = float((non_bse["statement_status"] == "SUPPORTED").mean()) if len(non_bse) else 1.0
    add("NON_BSE_SUPPORTED_GATE", supported_ratio >= cfg["shard_acceptance_policy"]["minimum_non_bse_statement_bundle_success_ratio"], supported_ratio)
    bse = support[support["board"] == "BSE"]
    bse_ok = bool(bse["official_document_index_available"].astype(bool).all()) if len(bse) else True
    add("BSE_DOCUMENT_INDEX", bse_ok, len(bse))

    pit_ratio = float(raw["available_from"].notna().mean()) if len(raw) else 1.0
    future = int((pd.to_datetime(raw["available_from"], errors="coerce", utc=True) < pd.to_datetime(raw["announcement_date"], errors="coerce", utc=True)).sum()) if len(raw) else 0
    add("PIT_GATE", pit_ratio >= cfg["shard_acceptance_policy"]["minimum_official_pit_match_ratio"], pit_ratio)
    add("ZERO_FUTURE_FACTS", future == 0, future)
    add("ZERO_AMBIGUOUS_MAPPING_GROUPS", len(semantic.ambiguous_source_mapping_groups(raw)) == 0, len(semantic.ambiguous_source_mapping_groups(raw)))
    add("ZERO_DUPLICATE_EFFECTIVE_INTERVALS", core.duplicate_effective_intervals(normalized) == 0, core.duplicate_effective_intervals(normalized))

    source_ids = set(sources["source_id"].dropna())
    missing_sources = set(normalized["source_id"].dropna()) - source_ids
    decision_grade = normalized["decision_grade_eligible"].astype(bool) if len(normalized) else pd.Series(dtype=bool)
    source_less = int((decision_grade & normalized["source_id"].isna()).sum()) if len(normalized) else 0
    add("SOURCE_LINEAGE", not missing_sources, sorted(missing_sources))
    add("ZERO_SOURCELESS_DECISION_GRADE", source_less == 0, source_less)
    unclassified = int((conflicts["status"] != "CLASSIFIED_CONTROLLED_EXCLUSION").sum()) if len(conflicts) else 0
    add("ALL_CONFLICTS_CLASSIFIED", unclassified == 0, unclassified)
    performed_failures = int((checks_frame["result"] == "FAIL").sum()) if len(checks_frame) else 0
    add("PERFORMED_CHECKS_NO_FAILURE", performed_failures == 0, performed_failures)
    add("REVISION_LEDGER", len(revisions) > 0 or not len(raw), len(revisions))
    add("STATEMENT_FAMILIES", set(normalized["statement"]).issubset({"balance_sheet", "income_statement", "cash_flow"}), sorted(set(normalized["statement"])))

    manifest_errors: list[str] = []
    for entry in manifest["files"]:
        path = root / entry["path"]
        if not path.exists() or matrix.file_sha256(path) != entry["sha256"] or path.stat().st_size != entry["bytes"]:
            manifest_errors.append(entry["path"])
    add("MANIFEST_INTEGRITY", not manifest_errors, manifest_errors)
    trade_values = set(raw["trade_authority"].dropna()) | set(normalized["trade_authority"].dropna())
    add("ZERO_TRADE_AUTHORITY", trade_values.issubset({"NONE"}) and decision.get("trade_authority") == "NONE", sorted(trade_values))

    failures = [item["check_id"] for item in checks if item["status"] != "PASS"]
    payload = {
        "validation_version": "1.0.0",
        "run_id": decision["run_id"],
        "program_id": "FMDL-3B-2-SHARD",
        "shard_id": args.shard_id,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "hard_failures": failures,
        "decision_status": decision["status"],
        "metrics": decision["metrics"],
        "authority": decision["authority"],
        "trade_authority": "NONE",
    }
    matrix.write_json(root / "SHARD_VALIDATION.json", payload)

    manifest["manifest_version"] = "1.1.0"
    manifest["files"] = []
    for path in sorted(root.iterdir()):
        if path.name != "SHARD_MANIFEST.json":
            manifest["files"].append({"path": path.name, "sha256": matrix.file_sha256(path), "bytes": path.stat().st_size})
    matrix.write_json(root / "SHARD_MANIFEST.json", manifest)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
