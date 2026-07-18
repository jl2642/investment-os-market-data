from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from scripts import fmdl3b3_core as core

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3b3_comparability.json"
LAST_SUCCESS = ROOT / "outputs/status/FMDL3B2_LAST_SUCCESS.json"
CANDIDATE = ROOT / "outputs/financials/comparability/candidate"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_input_root(explicit: Path | None) -> tuple[Path, dict]:
    pointer = load_json(LAST_SUCCESS)
    if pointer.get("status") != "FMDL3B2_FULL_UNIVERSE_INITIAL_BUILD_ACCEPTED_WITH_CONTROLLED_QUARANTINE":
        raise SystemExit("FMDL-3B-2 accepted entry gate not satisfied")
    root = explicit if explicit is not None else ROOT / pointer["release_root"]
    if not root.exists():
        raise SystemExit(f"FMDL-3B-2 release root missing: {root}")
    return root, pointer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--input-root", type=Path, default=None)
    args = parser.parse_args()
    cfg = load_json(args.config)
    input_root, entry = resolve_input_root(args.input_root)
    if CANDIDATE.exists():
        shutil.rmtree(CANDIDATE)
    CANDIDATE.mkdir(parents=True)

    revision_paths = sorted((input_root / "revisions").glob("shard-*.parquet"))
    normalized_paths = sorted((input_root / "normalized").glob("shard-*.parquet"))
    if len(revision_paths) != 32 or len(normalized_paths) != 32:
        raise SystemExit("expected 32 revision and 32 normalized shards")

    revisions = pd.concat([pd.read_parquet(path) for path in revision_paths], ignore_index=True)
    lineage, filing_period_status = core.build_authoritative_revision_lineage(revisions)
    normalized_periods = pd.concat(
        [pd.read_parquet(path, columns=["symbol", "period_end"]).drop_duplicates() for path in normalized_paths],
        ignore_index=True,
    ).drop_duplicates().rename(columns={"period_end": "report_period_end"})
    all_period_keys = pd.concat(
        [filing_period_status[["symbol", "report_period_end"]], normalized_periods],
        ignore_index=True,
    ).drop_duplicates()
    period_status = all_period_keys.merge(
        filing_period_status,
        on=["symbol", "report_period_end"],
        how="left",
        validate="one_to_one",
    )
    period_status["canonical_document_count"] = period_status["canonical_document_count"].fillna(0).astype(int)
    period_status["correction_notice_count"] = period_status["correction_notice_count"].fillna(0).astype(int)
    missing_canonical = period_status["canonical_document_count"].eq(0)
    period_status.loc[missing_canonical, "restatement_status"] = "UNRESOLVED_NO_CANONICAL_PERIODIC_DOCUMENT"
    period_status.loc[missing_canonical, "historical_replay_status"] = "BLOCKED_NO_CANONICAL_PERIODIC_DOCUMENT"
    period_status["trade_authority"] = "NONE"

    fact_exceptions: list[pd.DataFrame] = []
    bridge_exceptions: list[pd.DataFrame] = []
    total_facts = 0
    total_comparisons = 0
    for path in normalized_paths:
        normalized = pd.read_parquet(path)
        total_facts += len(normalized)
        overlay = core.build_fact_overlay(normalized, period_status)
        fact_exceptions.append(overlay[overlay["comparability_evidence_status"] != "CURRENT_VALID"].copy())
        bridge = core.build_comparability_bridge(overlay)
        total_comparisons += len(bridge)
        bridge_exceptions.append(bridge[bridge["comparison_status"] != "COMPARABLE"].copy())

    facts = pd.concat(fact_exceptions, ignore_index=True) if fact_exceptions else pd.DataFrame()
    bridge = pd.concat(bridge_exceptions, ignore_index=True) if bridge_exceptions else pd.DataFrame()
    lineage.to_parquet(CANDIDATE / "FMDL3B3_REVISION_LINEAGE.parquet", index=False, compression="zstd")
    period_status.to_parquet(CANDIDATE / "FMDL3B3_PERIOD_REVISION_STATUS.parquet", index=False, compression="zstd")
    facts.to_parquet(CANDIDATE / "FMDL3B3_FACT_COMPARABILITY_EXCEPTIONS.parquet", index=False, compression="zstd")
    bridge.to_parquet(CANDIDATE / "FMDL3B3_COMPARABILITY_BRIDGE.parquet", index=False, compression="zstd")

    document_summary = lineage.groupby(["document_class", "canonical_revision_status"], dropna=False).size().reset_index(name="row_count")
    period_summary = period_status.groupby(["restatement_status", "historical_replay_status"], dropna=False).size().reset_index(name="period_count")
    bridge_summary = bridge.groupby(["comparison_status", "reason_codes", "model_treatment"], dropna=False).size().reset_index(name="comparison_count")
    fact_summary = facts.groupby(["comparability_evidence_status", "fmdl3b3_decision_grade_eligible"], dropna=False).size().reset_index(name="fact_count")
    document_summary.to_csv(CANDIDATE / "FMDL3B3_DOCUMENT_CLASSIFICATION_SUMMARY.csv", index=False, encoding="utf-8-sig")
    period_summary.to_csv(CANDIDATE / "FMDL3B3_PERIOD_STATUS_SUMMARY.csv", index=False, encoding="utf-8-sig")
    bridge_summary.to_csv(CANDIDATE / "FMDL3B3_COMPARABILITY_SUMMARY.csv", index=False, encoding="utf-8-sig")
    fact_summary.to_csv(CANDIDATE / "FMDL3B3_FACT_EXCEPTION_SUMMARY.csv", index=False, encoding="utf-8-sig")

    release_id = f"FMDL3B3_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"
    metrics = {
        "input_revision_row_count": len(revisions),
        "classified_document_count": len(lineage),
        "normalized_period_key_count": len(normalized_periods),
        "period_status_count": len(period_status),
        "canonical_periodic_document_count": int(lineage["is_canonical_periodic_document"].sum()),
        "noncanonical_document_count": int((~lineage["is_canonical_periodic_document"]).sum()),
        "original_only_period_count": int((period_status["restatement_status"] == "ORIGINAL_ONLY").sum()),
        "restated_or_corrected_period_count": int((period_status["restatement_status"] == "RESTATED_OR_CORRECTED").sum()),
        "unresolved_no_canonical_period_count": int((period_status["restatement_status"] == "UNRESOLVED_NO_CANONICAL_PERIODIC_DOCUMENT").sum()),
        "normalized_fact_count_replayed": total_facts,
        "fact_exception_count": len(facts),
        "comparison_count_replayed": total_comparisons,
        "comparison_exception_count": len(bridge),
        "comparable_with_warning_count": int((bridge["comparison_status"] == "COMPARABLE_WITH_WARNING").sum()) if len(bridge) else 0,
        "not_comparable_count": int((bridge["comparison_status"] == "NOT_COMPARABLE").sum()) if len(bridge) else 0
    }
    normalized_period_set = set(map(tuple, normalized_periods[["symbol", "report_period_end"]].itertuples(index=False, name=None)))
    classified_period_set = set(map(tuple, period_status[["symbol", "report_period_end"]].itertuples(index=False, name=None)))
    checks = {
        "ENTRY_RELEASE_ACCEPTED": entry.get("status") == cfg["entry_status"],
        "EXACT_32_INPUT_SHARDS": len(revision_paths) == 32 and len(normalized_paths) == 32,
        "ALL_DOCUMENTS_CLASSIFIED": lineage["document_class"].notna().all(),
        "ZERO_DUPLICATE_REVISION_IDS": not lineage["revision_id"].duplicated().any(),
        "ALL_NORMALIZED_PERIODS_CLASSIFIED": normalized_period_set.issubset(classified_period_set) and period_status["restatement_status"].notna().all(),
        "ALL_PERIODS_CONTROLLED": set(period_status["restatement_status"]).issubset(set(cfg["allowed_restatement_statuses"])),
        "ALL_FACT_EXCEPTIONS_EXPLICIT": facts["restatement_status"].notna().all() and facts["historical_replay_status"].notna().all(),
        "ALL_COMPARABILITY_STATUSES_CONTROLLED": set(bridge["comparison_status"]).issubset(set(cfg["allowed_comparison_statuses"])),
        "ZERO_DUPLICATE_COMPARISON_IDS": not bridge["comparison_id"].duplicated().any() if len(bridge) else True,
        "ZERO_TRADE_AUTHORITY": set(lineage["trade_authority"].dropna()).issubset({"NONE"}) and set(period_status["trade_authority"].dropna()).issubset({"NONE"}) and (set(bridge["trade_authority"].dropna()).issubset({"NONE"}) if len(bridge) else True)
    }
    failures = [name for name, passed in checks.items() if not passed]
    decision = {
        "decision_version": "1.0.0",
        "release_id": release_id,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "program_id": "FMDL-3B-3",
        "status": "FMDL3B3_COMPARABILITY_AND_RESTATEMENT_HARDENING_ACCEPTED" if not failures else "FMDL3B3_REMEDIATION_REQUIRED",
        "hard_failures": failures,
        "checks": [{"check_id": name, "status": "PASS" if passed else "FAIL"} for name, passed in checks.items()],
        "metrics": metrics,
        "input_release_id": entry["release_id"],
        "controlled_limitations": [
            "HISTORICAL_STRUCTURED_VALUES_BEFORE_CORRECTION_ARE_NOT_AVAILABLE_FROM_THE_CURRENT_PROVIDER_EXPORT",
            "PRE_RESTATEMENT_NUMERIC_REPLAY_IS_BLOCKED_WHEN_ONLY_DOCUMENT_LINEAGE_EXISTS",
            "ABSENCE_FROM_EXCEPTION_TABLES_MEANS_COMPARABLE_UNDER_THE_FROZEN_DEFAULT_RULES",
            "BSE_AND_OTHER_UNSUPPORTED_STATEMENT_FACTS_REMAIN_CONTROLLED_BY_FMDL3B2_QUARANTINE"
        ],
        "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
        "trade_authority": "NONE",
        "next_gate": "FMDL-3B-4_STATEMENT_CURRENT_AND_ACCEPTANCE"
    }
    write_json(CANDIDATE / "FMDL3B3_DECISION.json", decision)
    manifest = {
        "manifest_version": "1.0.0",
        "release_id": release_id,
        "input_release_id": entry["release_id"],
        "files": [],
        "authority": decision["authority"],
        "trade_authority": "NONE"
    }
    for path in sorted(CANDIDATE.iterdir()):
        if path.is_file() and path.name != "FMDL3B3_MANIFEST.json":
            manifest["files"].append({"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size})
    write_json(CANDIDATE / "FMDL3B3_MANIFEST.json", manifest)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
