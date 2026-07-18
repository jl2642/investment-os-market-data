from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from scripts import fmdl3b2_matrix_core as matrix

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3b2_matrix.json"
UNIVERSE = ROOT / "outputs/current/DAILY_MARKET_SNAPSHOT.csv"


def concat_frames(frames: list[pd.DataFrame], columns: list[str] | None = None) -> pd.DataFrame:
    nonempty = [frame for frame in frames if frame is not None and len(frame)]
    if nonempty:
        return pd.concat(nonempty, ignore_index=True)
    return pd.DataFrame(columns=columns or [])


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig") if path.exists() else pd.DataFrame()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--input-root", type=Path, required=True)
    args = parser.parse_args()
    cfg = matrix.load_json(args.config)
    input_root = args.input_root
    shard_dirs = sorted({path.parent for path in input_root.rglob("SHARD_DECISION.json")})
    candidate = ROOT / "outputs/financials/full_build/matrix/candidate"
    if candidate.exists():
        shutil.rmtree(candidate)
    for subdir in ["normalized", "revisions", "sources"]:
        (candidate / subdir).mkdir(parents=True, exist_ok=True)

    universe = matrix.load_universe(UNIVERSE)
    expected_assignments = matrix.assign_shards(universe, int(cfg["sharding"]["shard_count"]))
    decisions: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []
    support_frames: list[pd.DataFrame] = []
    retry_frames: list[pd.DataFrame] = []
    conflict_frames: list[pd.DataFrame] = []
    ambiguity_frames: list[pd.DataFrame] = []
    check_frames: list[pd.DataFrame] = []
    qa_frames: list[pd.DataFrame] = []
    bridge_frames: list[pd.DataFrame] = []
    frequency_frames: list[pd.DataFrame] = []
    raw_artifact_rows: list[dict[str, Any]] = []
    membership_rows: list[dict[str, Any]] = []
    missing_shards: list[int] = []
    workflow_run_id = os.environ.get("GITHUB_RUN_ID", "UNKNOWN")

    dirs_by_id: dict[int, Path] = {}
    for shard_dir in shard_dirs:
        decision = matrix.load_json(shard_dir / "SHARD_DECISION.json")
        dirs_by_id[int(decision["shard_id"])] = shard_dir

    for shard_id in range(int(cfg["sharding"]["shard_count"])):
        if shard_id not in dirs_by_id:
            missing_shards.append(shard_id)
            continue
        shard_dir = dirs_by_id[shard_id]
        decision = matrix.load_json(shard_dir / "SHARD_DECISION.json")
        validation = matrix.load_json(shard_dir / "SHARD_VALIDATION.json")
        manifest = matrix.load_json(shard_dir / "SHARD_MANIFEST.json")
        symbols = load_csv(shard_dir / "SHARD_SYMBOLS.csv")
        support = load_csv(shard_dir / "SHARD_SUPPORT_MAP.csv")
        retry = load_csv(shard_dir / "SHARD_RETRY_LEDGER.csv")
        conflicts = load_csv(shard_dir / "SHARD_CONFLICT_LOG.csv")
        ambiguities = load_csv(shard_dir / "SHARD_AMBIGUOUS_MAPPING_GROUPS.csv")
        checks = load_csv(shard_dir / "SHARD_VALIDATION_CHECKS.csv")
        qa = load_csv(shard_dir / "SHARD_QA_FLAGS.csv")
        bridge = load_csv(shard_dir / "SHARD_COMPARABILITY_BRIDGE.csv")
        frequency = load_csv(shard_dir / "SHARD_FIELD_FREQUENCY.csv")

        decisions.append(decision)
        validations.append(validation)
        for frame in [support, retry, conflicts, ambiguities, checks, qa, bridge, frequency]:
            if len(frame):
                frame.insert(0, "shard_id", shard_id)
        support_frames.append(support)
        retry_frames.append(retry)
        conflict_frames.append(conflicts)
        ambiguity_frames.append(ambiguities)
        check_frames.append(checks)
        qa_frames.append(qa)
        bridge_frames.append(bridge)
        frequency_frames.append(frequency)

        for symbol in symbols.get("symbol", pd.Series(dtype=str)).astype(str):
            membership_rows.append({"symbol": symbol, "shard_id": shard_id})

        normalized_source = shard_dir / "SHARD_NORMALIZED_LONG.parquet"
        revision_source = shard_dir / "SHARD_REVISION_LEDGER.parquet"
        source_index_source = shard_dir / "SHARD_SOURCE_INDEX.parquet"
        shutil.copy2(normalized_source, candidate / "normalized" / f"shard-{shard_id:02d}.parquet")
        shutil.copy2(revision_source, candidate / "revisions" / f"shard-{shard_id:02d}.parquet")
        shutil.copy2(source_index_source, candidate / "sources" / f"shard-{shard_id:02d}.parquet")

        raw_entry = next((entry for entry in manifest["files"] if entry["path"] == "SHARD_RAW_FACTS.parquet"), None)
        raw_artifact_rows.append({
            "shard_id": shard_id,
            "artifact_name": cfg["storage"]["raw_artifact_name_pattern"].format(shard_id=f"{shard_id:02d}"),
            "workflow_run_id": workflow_run_id,
            "retention_days": cfg["sharding"]["raw_artifact_retention_days"],
            "raw_filename": "SHARD_RAW_FACTS.parquet",
            "raw_sha256": raw_entry["sha256"] if raw_entry else None,
            "raw_bytes": raw_entry["bytes"] if raw_entry else None,
            "shard_decision_status": decision["status"],
            "shard_validation_status": validation["status"],
            "trade_authority": "NONE",
        })

    support = concat_frames(support_frames)
    retry = concat_frames(retry_frames)
    conflicts = concat_frames(conflict_frames)
    ambiguities = concat_frames(ambiguity_frames)
    performed_checks = concat_frames(check_frames)
    qa = concat_frames(qa_frames)
    bridge = concat_frames(bridge_frames)
    frequency = concat_frames(frequency_frames)
    membership = pd.DataFrame(membership_rows)
    raw_artifacts = pd.DataFrame(raw_artifact_rows)

    if len(frequency):
        frequency = frequency.groupby(["statement", "provider_field_name", "mapping_status", "canonical_field_id"], dropna=False)["fact_count"].sum().reset_index().sort_values("fact_count", ascending=False)
    coverage = support.groupby(["board", "statement_status"], dropna=False).size().reset_index(name="symbol_count") if len(support) else pd.DataFrame(columns=["board", "statement_status", "symbol_count"])
    shard_summary = pd.DataFrame([
        {
            "shard_id": decision["shard_id"],
            "status": decision["status"],
            "validation_status": next((item["status"] for item in validations if item["shard_id"] == decision["shard_id"]), "MISSING"),
            **decision["metrics"],
            "membership_hash": decision["membership_hash"],
            "trade_authority": "NONE",
        }
        for decision in sorted(decisions, key=lambda item: item["shard_id"])
    ])

    outputs = {
        "FMDL3B2_MEMBERSHIP.csv": membership,
        "FMDL3B2_SHARD_SUMMARY.csv": shard_summary,
        "FMDL3B2_SUPPORT_MAP.csv": support,
        "FMDL3B2_RETRY_LEDGER.csv": retry,
        "FMDL3B2_CONFLICT_LOG.csv": conflicts,
        "FMDL3B2_AMBIGUOUS_MAPPING_GROUPS.csv": ambiguities,
        "FMDL3B2_VALIDATION_CHECKS.csv": performed_checks,
        "FMDL3B2_QA_FLAGS.csv": qa,
        "FMDL3B2_COMPARABILITY_BRIDGE.csv": bridge,
        "FMDL3B2_FIELD_FREQUENCY.csv": frequency,
        "FMDL3B2_COVERAGE.csv": coverage,
        "FMDL3B2_RAW_ARTIFACT_INDEX.csv": raw_artifacts,
    }
    for filename, frame in outputs.items():
        frame.to_csv(candidate / filename, index=False, encoding="utf-8-sig")

    duplicate_symbols = int(membership["symbol"].duplicated(keep=False).sum()) if len(membership) else 0
    observed_symbols = set(membership["symbol"].astype(str)) if len(membership) else set()
    missing_symbols = sorted(set(universe) - observed_symbols)
    extra_symbols = sorted(observed_symbols - set(universe))
    non_bse = support[support["board"] != "BSE"] if len(support) else support
    supported_ratio = float((non_bse["statement_status"] == "SUPPORTED").mean()) if len(non_bse) else 0.0
    quarantine_ratio = float((non_bse["statement_status"] == "QUARANTINED").mean()) if len(non_bse) else 1.0
    total_raw = sum(int(item["metrics"]["raw_fact_count"]) for item in decisions)
    weighted_pit = sum(float(item["metrics"]["official_pit_match_ratio"]) * int(item["metrics"]["raw_fact_count"]) for item in decisions)
    pit_ratio = weighted_pit / total_raw if total_raw else 0.0
    total_normalized_bytes = sum(path.stat().st_size for path in (candidate / "normalized").glob("*.parquet"))
    maximum_file_mib = max([path.stat().st_size for path in (candidate / "normalized").glob("*.parquet")] or [0]) / 1024 / 1024
    total_normalized_mib = total_normalized_bytes / 1024 / 1024
    bse = support[support["board"] == "BSE"] if len(support) else support
    bse_documents = bool(bse["official_document_index_available"].astype(bool).all()) if len(bse) else False

    aggregate_metrics = {
        "universe_symbol_count": len(universe),
        "observed_symbol_count": len(observed_symbols),
        "shard_count": len(decisions),
        "accepted_shard_count": sum(item["status"] == "FMDL3B2_SHARD_ACCEPTED" for item in decisions),
        "validated_shard_count": sum(item["status"] == "PASS" for item in validations),
        "supported_symbol_count": int((support["statement_status"] == "SUPPORTED").sum()) if len(support) else 0,
        "quarantined_symbol_count": int((support["statement_status"] == "QUARANTINED").sum()) if len(support) else 0,
        "non_bse_supported_ratio": supported_ratio,
        "non_bse_quarantine_ratio": quarantine_ratio,
        "official_pit_match_ratio": pit_ratio,
        "raw_fact_count": total_raw,
        "normalized_fact_count": sum(int(item["metrics"]["normalized_fact_count"]) for item in decisions),
        "decision_grade_fact_count": sum(int(item["metrics"]["decision_grade_fact_count"]) for item in decisions),
        "fallback_components_invoked": sum(int(item["metrics"]["fallback_components_invoked"]) for item in decisions),
        "fallback_components_used": sum(int(item["metrics"]["fallback_components_used"]) for item in decisions),
        "retry_symbol_count": len(set(retry["symbol"].astype(str))) if len(retry) else 0,
        "ambiguous_mapping_group_count": sum(int(item["metrics"]["ambiguous_mapping_group_count"]) for item in decisions),
        "future_fact_count": sum(int(item["metrics"]["future_fact_count"]) for item in decisions),
        "source_less_decision_grade_fact_count": sum(int(item["metrics"]["source_less_decision_grade_fact_count"]) for item in decisions),
        "duplicate_effective_interval_count": sum(int(item["metrics"]["duplicate_effective_interval_count"]) for item in decisions),
        "classified_conflict_count": sum(int(item["metrics"]["classified_conflict_count"]) for item in decisions),
        "unclassified_conflict_count": sum(int(item["metrics"]["unclassified_conflict_count"]) for item in decisions),
        "performed_validation_check_count": sum(int(item["metrics"]["performed_validation_check_count"]) for item in decisions),
        "performed_validation_failure_count": sum(int(item["metrics"]["performed_validation_failure_count"]) for item in decisions),
        "qa_flag_count": sum(int(item["metrics"]["qa_flag_count"]) for item in decisions),
        "duplicate_symbol_count": duplicate_symbols,
        "missing_symbol_count": len(missing_symbols),
        "extra_symbol_count": len(extra_symbols),
        "normalized_release_mib": total_normalized_mib,
        "maximum_normalized_shard_mib": maximum_file_mib,
        "raw_artifact_count": len(raw_artifacts),
    }

    policy = cfg["aggregate_acceptance_policy"]
    tests = {
        "ALL_32_SHARDS_PRESENT": not missing_shards and len(decisions) == int(cfg["sharding"]["shard_count"]),
        "ALL_SHARD_DECISIONS_ACCEPTED": all(item["status"] == "FMDL3B2_SHARD_ACCEPTED" for item in decisions),
        "ALL_SHARD_VALIDATIONS_PASS": all(item["status"] == "PASS" for item in validations),
        "EXACT_UNIVERSE_MEMBERSHIP": not missing_symbols and not extra_symbols and duplicate_symbols == 0 and len(observed_symbols) == len(universe),
        "NON_BSE_SUPPORTED_GATE": supported_ratio >= policy["minimum_non_bse_supported_ratio"],
        "NON_BSE_QUARANTINE_CAP": quarantine_ratio <= policy["maximum_non_bse_quarantine_ratio"],
        "PIT_GATE": pit_ratio >= policy["minimum_official_pit_match_ratio"],
        "ZERO_AMBIGUITY": aggregate_metrics["ambiguous_mapping_group_count"] <= policy["maximum_ambiguous_mapping_group_count"],
        "ZERO_FUTURE": aggregate_metrics["future_fact_count"] <= policy["maximum_future_fact_count"],
        "ZERO_SOURCELESS": aggregate_metrics["source_less_decision_grade_fact_count"] <= policy["maximum_source_less_decision_grade_fact_count"],
        "ZERO_DUPLICATE_INTERVAL": aggregate_metrics["duplicate_effective_interval_count"] <= policy["maximum_duplicate_effective_interval_count"],
        "ALL_CONFLICTS_CLASSIFIED": aggregate_metrics["unclassified_conflict_count"] <= policy["maximum_unclassified_conflict_count"],
        "PERFORMED_CHECKS_NO_FAILURE": aggregate_metrics["performed_validation_failure_count"] <= policy["maximum_performed_validation_failure_count"],
        "BSE_DOCUMENT_INDEX": bse_documents,
        "NORMALIZED_FILE_SIZE": maximum_file_mib < cfg["storage"]["maximum_git_file_mib"],
        "NORMALIZED_TOTAL_SIZE": total_normalized_mib <= cfg["storage"]["maximum_total_normalized_mib"],
        "RAW_ARTIFACT_INDEX_COMPLETE": len(raw_artifacts) == int(cfg["sharding"]["shard_count"]) and raw_artifacts["raw_sha256"].notna().all(),
    }
    failures = [name for name, passed in tests.items() if not passed]
    release_id = f"FMDL3B2M_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"
    decision = {
        "decision_version": "1.0.0",
        "release_id": release_id,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "program_id": "FMDL-3B-2-MATRIX",
        "workflow_run_id": workflow_run_id,
        "status": "FMDL3B2_FULL_UNIVERSE_INITIAL_BUILD_ACCEPTED_WITH_CONTROLLED_QUARANTINE" if not failures else "FMDL3B2_FULL_UNIVERSE_INITIAL_BUILD_REMEDIATION_REQUIRED",
        "hard_failures": failures,
        "checks": [{"check_id": name, "status": "PASS" if passed else "FAIL"} for name, passed in tests.items()],
        "metrics": aggregate_metrics,
        "missing_shards": missing_shards,
        "missing_symbols_sample": missing_symbols[:100],
        "extra_symbols_sample": extra_symbols[:100],
        "controlled_limitations": [
            "BSE_STRUCTURED_FACTS_REMAIN_CONTROLLED_QUARANTINE_PENDING_CNINFO_DOCUMENT_EXTRACTION",
            "RAW_FACTS_RETAINED_AS_90_DAY_IMMUTABLE_WORKFLOW_ARTIFACT_SHARDS_PENDING_DURABLE_RETENTION_ROUTE",
            "FULL_UNIVERSE_PROFILE_CLASSIFICATION_DEFERRED_TO_SECURITY_MASTER_ENRICHMENT",
            "FIELD_REGISTRY_REMAINS_CONSERVATIVE_AND_UNMAPPED_PROVIDER_FACTS_ARE_RAW_ONLY",
        ],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    matrix.write_json(candidate / "FMDL3B2_MATRIX_DECISION.json", decision)

    manifest = {
        "manifest_version": "1.0.0",
        "release_id": release_id,
        "program_id": "FMDL-3B-2-MATRIX",
        "status": "CANDIDATE",
        "files": [],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    for path in sorted(candidate.rglob("*")):
        if path.is_file() and path.name != "FMDL3B2_MATRIX_MANIFEST.json":
            manifest["files"].append({"path": str(path.relative_to(candidate)), "sha256": matrix.file_sha256(path), "bytes": path.stat().st_size})
    matrix.write_json(candidate / "FMDL3B2_MATRIX_MANIFEST.json", manifest)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
