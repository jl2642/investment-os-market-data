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
DEFAULT_CANDIDATE = ROOT / "outputs/financials/full_build/matrix/candidate"


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--candidate-root", type=Path, default=DEFAULT_CANDIDATE)
    args = parser.parse_args()

    cfg = matrix.load_json(args.config)
    root = args.candidate_root
    decision = matrix.load_json(root / "FMDL3B2_MATRIX_DECISION.json")
    manifest = matrix.load_json(root / "FMDL3B2_MATRIX_MANIFEST.json")
    membership = load_csv(root / "FMDL3B2_MEMBERSHIP.csv")
    shard_summary = load_csv(root / "FMDL3B2_SHARD_SUMMARY.csv")
    support = load_csv(root / "FMDL3B2_SUPPORT_MAP.csv")
    retry = load_csv(root / "FMDL3B2_RETRY_LEDGER.csv")
    conflicts = load_csv(root / "FMDL3B2_CONFLICT_LOG.csv")
    ambiguities = load_csv(root / "FMDL3B2_AMBIGUOUS_MAPPING_GROUPS.csv")
    performed_checks = load_csv(root / "FMDL3B2_VALIDATION_CHECKS.csv")
    raw_index = load_csv(root / "FMDL3B2_RAW_ARTIFACT_INDEX.csv")

    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: Any) -> None:
        checks.append({"check_id": check_id, "status": "PASS" if passed else "FAIL", "detail": detail})

    expected_status = "FMDL3B2_FULL_UNIVERSE_INITIAL_BUILD_ACCEPTED_WITH_CONTROLLED_QUARANTINE"
    add("DECISION_STATUS", decision.get("status") == expected_status, decision.get("status"))
    add("DECISION_HARD_FAILURES", decision.get("hard_failures") == [], decision.get("hard_failures"))

    shard_count = int(cfg["sharding"]["shard_count"])
    expected_ids = set(range(shard_count))
    observed_ids = set(pd.to_numeric(shard_summary.get("shard_id", pd.Series(dtype=int)), errors="coerce").dropna().astype(int))
    add("ALL_SHARDS_PRESENT", observed_ids == expected_ids and len(shard_summary) == shard_count, {"missing": sorted(expected_ids - observed_ids), "extra": sorted(observed_ids - expected_ids)})
    add("ALL_SHARD_DECISIONS_ACCEPTED", len(shard_summary) == shard_count and set(shard_summary["status"]) == {"FMDL3B2_SHARD_ACCEPTED"}, shard_summary.get("status", pd.Series(dtype=str)).value_counts().to_dict())
    add("ALL_SHARD_VALIDATIONS_PASS", len(shard_summary) == shard_count and set(shard_summary["validation_status"]) == {"PASS"}, shard_summary.get("validation_status", pd.Series(dtype=str)).value_counts().to_dict())

    universe = matrix.load_universe(UNIVERSE)
    observed_symbols = membership.get("symbol", pd.Series(dtype=str)).dropna().astype(str)
    observed_set = set(observed_symbols)
    duplicates = int(observed_symbols.duplicated(keep=False).sum())
    missing_symbols = sorted(set(universe) - observed_set)
    extra_symbols = sorted(observed_set - set(universe))
    add("EXACT_UNIVERSE_MEMBERSHIP_ONCE", len(observed_symbols) == len(universe) and not missing_symbols and not extra_symbols and duplicates == 0, {"universe": len(universe), "rows": len(observed_symbols), "missing": len(missing_symbols), "extra": len(extra_symbols), "duplicate_rows": duplicates})

    expected_assignments = matrix.assign_shards(universe, shard_count)
    membership_errors: list[int] = []
    if len(membership):
        membership["shard_id"] = pd.to_numeric(membership["shard_id"], errors="coerce").astype("Int64")
        for shard_id in range(shard_count):
            observed = sorted(membership[membership["shard_id"] == shard_id]["symbol"].astype(str))
            if observed != sorted(expected_assignments[shard_id]):
                membership_errors.append(shard_id)
    else:
        membership_errors = list(range(shard_count))
    add("DETERMINISTIC_SHARD_MEMBERSHIP_REPLAY", not membership_errors, membership_errors)

    add("ALL_SUPPORT_STATUSES_CONTROLLED", len(support) == len(universe) and set(support["statement_status"]).issubset({"SUPPORTED", "QUARANTINED"}), support.get("statement_status", pd.Series(dtype=str)).value_counts().to_dict())
    non_bse = support[support["board"] != "BSE"] if len(support) else support
    supported_ratio = float((non_bse["statement_status"] == "SUPPORTED").mean()) if len(non_bse) else 0.0
    quarantine_ratio = float((non_bse["statement_status"] == "QUARANTINED").mean()) if len(non_bse) else 1.0
    policy = cfg["aggregate_acceptance_policy"]
    add("NON_BSE_SUPPORTED_GATE", supported_ratio >= policy["minimum_non_bse_supported_ratio"], supported_ratio)
    add("NON_BSE_QUARANTINE_CAP", quarantine_ratio <= policy["maximum_non_bse_quarantine_ratio"], quarantine_ratio)
    bse = support[support["board"] == "BSE"] if len(support) else support
    bse_ok = len(bse) > 0 and bse["official_document_index_available"].astype(str).str.lower().eq("true").all()
    add("BSE_OFFICIAL_DOCUMENT_INDEX", bse_ok, {"bse_rows": len(bse)})

    metrics = decision["metrics"]
    add("PIT_GATE", float(metrics["official_pit_match_ratio"]) >= policy["minimum_official_pit_match_ratio"], metrics["official_pit_match_ratio"])
    add("ZERO_AMBIGUOUS_MAPPING_GROUPS", int(metrics["ambiguous_mapping_group_count"]) == 0 and len(ambiguities) == 0, {"decision": metrics["ambiguous_mapping_group_count"], "rows": len(ambiguities)})
    add("ZERO_FUTURE_FACTS", int(metrics["future_fact_count"]) == 0, metrics["future_fact_count"])
    add("ZERO_SOURCELESS_DECISION_GRADE", int(metrics["source_less_decision_grade_fact_count"]) == 0, metrics["source_less_decision_grade_fact_count"])
    add("ZERO_DUPLICATE_EFFECTIVE_INTERVALS", int(metrics["duplicate_effective_interval_count"]) == 0, metrics["duplicate_effective_interval_count"])
    unclassified = int((conflicts["status"] != "CLASSIFIED_CONTROLLED_EXCLUSION").sum()) if len(conflicts) else 0
    add("ALL_CONFLICTS_CLASSIFIED", int(metrics["unclassified_conflict_count"]) == 0 and unclassified == 0, {"decision": metrics["unclassified_conflict_count"], "rows": unclassified})
    performed_failures = int((performed_checks["result"] == "FAIL").sum()) if len(performed_checks) else 0
    add("PERFORMED_CHECKS_NO_FAILURE", int(metrics["performed_validation_failure_count"]) == 0 and performed_failures == 0, {"decision": metrics["performed_validation_failure_count"], "rows": performed_failures})

    normalized_files = sorted((root / "normalized").glob("shard-*.parquet"))
    revision_files = sorted((root / "revisions").glob("shard-*.parquet"))
    source_files = sorted((root / "sources").glob("shard-*.parquet"))
    add("NORMALIZED_SHARD_FILES", len(normalized_files) == shard_count, len(normalized_files))
    add("REVISION_SHARD_FILES", len(revision_files) == shard_count, len(revision_files))
    add("SOURCE_INDEX_SHARD_FILES", len(source_files) == shard_count, len(source_files))

    normalized_rows = 0
    normalized_trade_values: set[str] = set()
    normalized_read_errors: list[str] = []
    duplicate_interval_total = 0
    for path in normalized_files:
        try:
            frame = pd.read_parquet(path)
            normalized_rows += len(frame)
            if "trade_authority" in frame.columns:
                normalized_trade_values.update(frame["trade_authority"].dropna().astype(str))
            duplicate_interval_total += core.duplicate_effective_intervals(frame)
        except Exception as exc:
            normalized_read_errors.append(f"{path.name}:{type(exc).__name__}")
    add("NORMALIZED_PARQUET_READABLE", not normalized_read_errors, normalized_read_errors)
    add("NORMALIZED_ROW_COUNT_REPLAY", normalized_rows == int(metrics["normalized_fact_count"]), {"observed": normalized_rows, "decision": metrics["normalized_fact_count"]})
    add("NORMALIZED_ZERO_DUPLICATE_INTERVAL_REPLAY", duplicate_interval_total == 0, duplicate_interval_total)

    revision_rows = 0
    source_ids: set[str] = set()
    parquet_read_errors: list[str] = []
    for path in revision_files:
        try:
            revision_rows += len(pd.read_parquet(path))
        except Exception as exc:
            parquet_read_errors.append(f"{path.name}:{type(exc).__name__}")
    for path in source_files:
        try:
            frame = pd.read_parquet(path)
            if "source_id" in frame.columns:
                source_ids.update(frame["source_id"].dropna().astype(str))
        except Exception as exc:
            parquet_read_errors.append(f"{path.name}:{type(exc).__name__}")
    add("REVISION_AND_SOURCE_PARQUET_READABLE", not parquet_read_errors and revision_rows > 0 and len(source_ids) > 0, {"errors": parquet_read_errors, "revision_rows": revision_rows, "source_ids": len(source_ids)})

    max_file_mib = max([path.stat().st_size for path in normalized_files] or [0]) / 1024 / 1024
    total_mib = sum(path.stat().st_size for path in normalized_files) / 1024 / 1024
    add("NORMALIZED_FILE_SIZE", max_file_mib < cfg["storage"]["maximum_git_file_mib"], max_file_mib)
    add("NORMALIZED_TOTAL_SIZE", total_mib <= cfg["storage"]["maximum_total_normalized_mib"], total_mib)

    raw_ok = (
        len(raw_index) == shard_count
        and raw_index["raw_sha256"].notna().all()
        and raw_index["workflow_run_id"].astype(str).str.len().gt(0).all()
        and raw_index["artifact_name"].astype(str).str.startswith("fmdl3b2-raw-shard-").all()
        and set(raw_index["shard_validation_status"]) == {"PASS"}
    )
    add("RAW_ARTIFACT_INDEX_COMPLETE", raw_ok, {"rows": len(raw_index)})

    retry_symbols = set(retry.get("symbol", pd.Series(dtype=str)).dropna().astype(str))
    quarantined_symbols = set(support[support["statement_status"] == "QUARANTINED"]["symbol"].astype(str)) if len(support) else set()
    add("RETRY_LEDGER_SUBSET_OF_QUARANTINE", retry_symbols.issubset(quarantined_symbols), sorted(retry_symbols - quarantined_symbols)[:100])

    manifest_errors: list[str] = []
    for entry in manifest["files"]:
        path = root / entry["path"]
        if not path.exists() or matrix.file_sha256(path) != entry["sha256"] or path.stat().st_size != entry["bytes"]:
            manifest_errors.append(entry["path"])
    add("MANIFEST_INTEGRITY", not manifest_errors, manifest_errors)
    add("ZERO_TRADE_AUTHORITY", normalized_trade_values.issubset({"NONE"}) and decision.get("trade_authority") == "NONE" and set(raw_index["trade_authority"].dropna()).issubset({"NONE"}), sorted(normalized_trade_values))

    failures = [item["check_id"] for item in checks if item["status"] != "PASS"]
    payload = {
        "validation_version": "1.0.0",
        "release_id": decision["release_id"],
        "program_id": "FMDL-3B-2-MATRIX",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "hard_failures": failures,
        "decision_status": decision["status"],
        "metrics": decision["metrics"],
        "replay": {
            "normalized_rows": normalized_rows,
            "revision_rows": revision_rows,
            "source_id_count": len(source_ids),
            "maximum_normalized_shard_mib": max_file_mib,
            "total_normalized_mib": total_mib,
        },
        "authority": decision["authority"],
        "trade_authority": "NONE",
        "next_gate": decision["next_gate"],
    }
    matrix.write_json(root / "FMDL3B2_MATRIX_VALIDATION.json", payload)

    manifest["manifest_version"] = "1.1.0"
    manifest["files"] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "FMDL3B2_MATRIX_MANIFEST.json":
            manifest["files"].append({"path": str(path.relative_to(root)), "sha256": matrix.file_sha256(path), "bytes": path.stat().st_size})
    matrix.write_json(root / "FMDL3B2_MATRIX_MANIFEST.json", manifest)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
