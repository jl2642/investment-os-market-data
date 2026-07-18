from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from scripts import fmdl3b2_matrix_core as matrix
from scripts import fmdl3b2_validation_hardening as hardening
from scripts import fmdl3b_core as core
from scripts import run_fmdl3b2_shard as base

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3b2_matrix.json"
PILOT_CONFIG = ROOT / "config/fmdl3b_statement_store.json"


def _parse_source_notes(value: object) -> tuple[str, int]:
    text = str(value or "")
    status_match = re.search(r"status=([^;]+)", text)
    rows_match = re.search(r"rows=(\d+)", text)
    return (status_match.group(1).strip() if status_match else "UNKNOWN", int(rows_match.group(1)) if rows_match else 0)


def enrich_official_query_resolution(support: pd.DataFrame, sources: pd.DataFrame) -> pd.DataFrame:
    support = support.copy()
    by_source = sources.set_index("source_id") if len(sources) and "source_id" in sources.columns else pd.DataFrame()
    statuses: list[str] = []
    raw_rows: list[int] = []
    document_states: list[str] = []
    reasons: list[str] = []
    for _, row in support.iterrows():
        code = str(row["symbol"]).split(".")[0]
        source_id = f"SRC-CNINFO-{code}"
        source = by_source.loc[source_id] if len(by_source) and source_id in by_source.index else None
        notes = source.get("notes") if source is not None else ""
        query_status, query_rows = _parse_source_notes(notes)
        filing_count = int(pd.to_numeric(pd.Series([row.get("official_filing_count", 0)]), errors="coerce").fillna(0).iloc[0])
        if filing_count > 0:
            document_state = "INDEXED_CLASSIFIED_PERIODIC_REPORTS"
        elif query_status == "SUCCESS":
            document_state = "NO_CLASSIFIED_PERIODIC_REPORT_IN_SCOPE_AFTER_SUCCESSFUL_CNINFO_QUERY"
        else:
            document_state = "CNINFO_QUERY_UNRESOLVED"
        reason = str(row.get("status_reason") or "")
        if str(row.get("board")) == "BSE":
            if document_state == "INDEXED_CLASSIFIED_PERIODIC_REPORTS":
                reason = "BSE_PERIODIC_REPORT_INDEX_AVAILABLE_PENDING_STRUCTURED_EXTRACTION"
            elif document_state == "NO_CLASSIFIED_PERIODIC_REPORT_IN_SCOPE_AFTER_SUCCESSFUL_CNINFO_QUERY":
                reason = document_state
            else:
                reason = "BSE_CNINFO_QUERY_UNRESOLVED"
        statuses.append(query_status)
        raw_rows.append(query_rows)
        document_states.append(document_state)
        reasons.append(reason)
    support["official_query_status"] = statuses
    support["official_query_raw_row_count"] = raw_rows
    support["official_document_status"] = document_states
    support["status_reason"] = reasons
    return support


def _manifest_refresh(root: Path, manifest: dict) -> None:
    manifest["manifest_version"] = "1.2.0"
    manifest["files"] = []
    for path in sorted(root.iterdir()):
        if path.name != "SHARD_MANIFEST.json":
            manifest["files"].append({"path": path.name, "sha256": matrix.file_sha256(path), "bytes": path.stat().st_size})
    matrix.write_json(root / "SHARD_MANIFEST.json", manifest)


def postprocess(shard_id: int, config_path: Path) -> int:
    cfg = matrix.load_json(config_path)
    pilot_cfg = matrix.load_json(PILOT_CONFIG)
    root = ROOT / "outputs/financials/full_build/matrix/shards" / f"shard-{shard_id:02d}"
    decision = matrix.load_json(root / "SHARD_DECISION.json")
    manifest = matrix.load_json(root / "SHARD_MANIFEST.json")
    raw = pd.read_parquet(root / "SHARD_RAW_FACTS.parquet")
    normalized = pd.read_parquet(root / "SHARD_NORMALIZED_LONG.parquet")
    sources = pd.read_parquet(root / "SHARD_SOURCE_INDEX.parquet")
    support = pd.read_csv(root / "SHARD_SUPPORT_MAP.csv", encoding="utf-8-sig")
    retry = pd.read_csv(root / "SHARD_RETRY_LEDGER.csv", encoding="utf-8-sig")
    conflicts = pd.read_csv(root / "SHARD_CONFLICT_LOG.csv", encoding="utf-8-sig")
    ambiguities = pd.read_csv(root / "SHARD_AMBIGUOUS_MAPPING_GROUPS.csv", encoding="utf-8-sig")
    checks = pd.read_csv(root / "SHARD_VALIDATION_CHECKS.csv", encoding="utf-8-sig")
    flags = pd.read_csv(root / "SHARD_QA_FLAGS.csv", encoding="utf-8-sig")

    support = enrich_official_query_resolution(support, sources)
    normalized, checks, flags, controlled_evidence = hardening.harden_statement_validation(
        normalized,
        checks,
        flags,
        balance_relative_tolerance=pilot_cfg["normalization"]["balance_sheet_relative_tolerance"],
        cash_relative_tolerance=pilot_cfg["normalization"]["cash_flow_relative_tolerance"],
    )
    classified_ok, classification_errors = hardening.controlled_exclusions_are_classified(checks, flags)

    normalized.to_parquet(root / "SHARD_NORMALIZED_LONG.parquet", index=False, compression="zstd")
    support.to_csv(root / "SHARD_SUPPORT_MAP.csv", index=False, encoding="utf-8-sig")
    checks.to_csv(root / "SHARD_VALIDATION_CHECKS.csv", index=False, encoding="utf-8-sig")
    flags.to_csv(root / "SHARD_QA_FLAGS.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(controlled_evidence, columns=["symbol", "period", "area", "reason", "independent_evidence", "affected_line_items", "downgraded_fact_count", "flag_id", "trade_authority"]).to_csv(
        root / "SHARD_CONTROLLED_VALIDATION_EXCLUSIONS.csv", index=False, encoding="utf-8-sig"
    )

    non_bse = support[support["board"] != "BSE"]
    supported_ratio = float((non_bse["statement_status"] == "SUPPORTED").mean()) if len(non_bse) else 1.0
    pit_ratio = float(raw["available_from"].notna().mean()) if len(raw) else 1.0
    future = int((pd.to_datetime(raw["available_from"], errors="coerce", utc=True) < pd.to_datetime(raw["announcement_date"], errors="coerce", utc=True)).sum()) if len(raw) else 0
    decision_grade = normalized["decision_grade_eligible"].astype(bool) if len(normalized) else pd.Series(dtype=bool)
    source_less = int((decision_grade & normalized["source_id"].isna()).sum()) if len(normalized) else 0
    duplicate = core.duplicate_effective_intervals(normalized)
    unclassified_conflicts = int((conflicts["status"] != "CLASSIFIED_CONTROLLED_EXCLUSION").sum()) if len(conflicts) else 0
    performed_failures = int((checks["result"].astype(str) == "FAIL").sum()) if len(checks) else 0
    controlled_count = int((checks["result"].astype(str) == hardening.CONTROLLED_RESULT).sum()) if len(checks) else 0
    bse = support[support["board"] == "BSE"]
    allowed_bse_states = {"INDEXED_CLASSIFIED_PERIODIC_REPORTS", "NO_CLASSIFIED_PERIODIC_REPORT_IN_SCOPE_AFTER_SUCCESSFUL_CNINFO_QUERY"}
    bse_query_resolved = bool(
        bse["official_query_status"].astype(str).eq("SUCCESS").all()
        and bse["official_document_status"].astype(str).isin(allowed_bse_states).all()
    ) if len(bse) else True

    policy = cfg["shard_acceptance_policy"]
    symbols = pd.read_csv(root / "SHARD_SYMBOLS.csv", encoding="utf-8-sig")["symbol"].astype(str).tolist()
    tests = {
        "EXACT_SHARD_MEMBERSHIP": set(support["symbol"].astype(str)) == set(symbols) and not support["symbol"].duplicated().any(),
        "NON_BSE_BUNDLE_GATE": supported_ratio >= policy["minimum_non_bse_statement_bundle_success_ratio"],
        "PIT_GATE": pit_ratio >= policy["minimum_official_pit_match_ratio"],
        "ZERO_AMBIGUITY": len(ambiguities) <= policy["maximum_ambiguous_mapping_group_count"],
        "ZERO_FUTURE": future <= policy["maximum_future_fact_count"],
        "ZERO_SOURCELESS": source_less <= policy["maximum_source_less_decision_grade_fact_count"],
        "ZERO_DUPLICATE_INTERVAL": duplicate <= policy["maximum_duplicate_effective_interval_count"],
        "ALL_CONFLICTS_CLASSIFIED": unclassified_conflicts <= policy["maximum_unclassified_conflict_count"],
        "PERFORMED_CHECKS_NO_UNEXPLAINED_FAILURE": performed_failures <= policy["maximum_performed_validation_failure_count"],
        "CONTROLLED_VALIDATION_EXCLUSIONS_CLASSIFIED": classified_ok,
        "ALL_SUPPORTED_OR_QUARANTINED": set(support["statement_status"]).issubset({"SUPPORTED", "QUARANTINED"}),
        "BSE_OFFICIAL_QUERY_RESOLUTION": bse_query_resolved,
        "ZERO_TRADE_AUTHORITY": set(raw["trade_authority"].dropna()).issubset({"NONE"}) and set(normalized["trade_authority"].dropna()).issubset({"NONE"}),
    }
    failures = [name for name, passed in tests.items() if not passed]
    decision["decision_version"] = "1.1.0"
    decision["status"] = "FMDL3B2_SHARD_ACCEPTED" if not failures else "FMDL3B2_SHARD_REMEDIATION_REQUIRED"
    decision["hard_failures"] = failures
    decision["checks"] = [{"check_id": name, "status": "PASS" if passed else "FAIL"} for name, passed in tests.items()]
    decision["metrics"].update({
        "supported_symbol_count": int((support["statement_status"] == "SUPPORTED").sum()),
        "quarantined_symbol_count": int((support["statement_status"] == "QUARANTINED").sum()),
        "non_bse_supported_ratio": supported_ratio,
        "official_pit_match_ratio": pit_ratio,
        "normalized_fact_count": len(normalized),
        "decision_grade_fact_count": int(decision_grade.sum()) if len(normalized) else 0,
        "future_fact_count": future,
        "source_less_decision_grade_fact_count": source_less,
        "duplicate_effective_interval_count": duplicate,
        "unclassified_conflict_count": unclassified_conflicts,
        "performed_validation_check_count": len(checks),
        "performed_validation_failure_count": performed_failures,
        "controlled_validation_exclusion_count": controlled_count,
        "controlled_validation_classification_error_count": len(classification_errors),
        "bse_indexed_periodic_report_count": int((bse["official_document_status"] == "INDEXED_CLASSIFIED_PERIODIC_REPORTS").sum()) if len(bse) else 0,
        "bse_no_classified_periodic_report_count": int((bse["official_document_status"] == "NO_CLASSIFIED_PERIODIC_REPORT_IN_SCOPE_AFTER_SUCCESSFUL_CNINFO_QUERY").sum()) if len(bse) else 0,
        "bse_query_unresolved_count": int((bse["official_query_status"] != "SUCCESS").sum()) if len(bse) else 0,
        "qa_flag_count": len(flags),
    })
    decision["controlled_validation_classification_errors"] = classification_errors
    matrix.write_json(root / "SHARD_DECISION.json", decision)
    _manifest_refresh(root, manifest)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--shard-id", type=int, required=True)
    args, _ = parser.parse_known_args()
    base.main()
    return postprocess(args.shard_id, args.config)


if __name__ == "__main__":
    raise SystemExit(main())
