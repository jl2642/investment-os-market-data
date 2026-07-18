from __future__ import annotations

import argparse
import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from scripts import fmdl3b2_matrix_core as matrix
from scripts import fmdl3b_core as core
from scripts import fmdl3b_semantic_overrides as semantic
from scripts import run_fmdl3b2_canary as canary
from scripts import run_fmdl3b_pilot as pilot

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3b2_matrix.json"
PILOT_CONFIG = ROOT / "config/fmdl3b_statement_store.json"
FIELD_REGISTRY = ROOT / "config/fmdl3b_field_registry.json"
UNIVERSE = ROOT / "outputs/current/DAILY_MARKET_SNAPSHOT.csv"
CANARY_RELEASE = ROOT / "outputs/financials/full_build/canary/current/FMDL3B2_CANARY_RELEASE.json"


def sample_for_symbol(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "name": symbol,
        "profile": "UNCLASSIFIED_FULL_UNIVERSE",
        "board": canary.derive_board(symbol),
        "extended": False,
    }


def shard_runtime_config(cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "canary": {
            "minimum_report_period_end": cfg["data_scope"]["minimum_report_period_end"],
            "maximum_periods_per_statement": cfg["data_scope"]["maximum_periods_per_statement"],
        }
    }


def empty_outputs() -> dict[str, pd.DataFrame]:
    return {
        "raw": matrix.empty_frame(["symbol", "statement", "report_period_end", "source_id", "canonical_field_id", "available_from", "trade_authority"]),
        "normalized": matrix.empty_frame(["symbol", "statement", "line_item_id", "period_end", "source_id", "decision_grade_eligible", "trade_authority"]),
        "revisions": matrix.empty_frame(["symbol", "report_period_end", "revision_sequence", "available_from"]),
        "sources": matrix.empty_frame(["source_id", "source_name", "source_type", "trade_authority"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--shard-id", type=int, required=True)
    parser.add_argument("--shard-count", type=int, default=None)
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()

    cfg = matrix.load_json(args.config)
    canary_release = matrix.load_json(CANARY_RELEASE)
    if canary_release.get("status") != cfg["entry_gate"]:
        raise SystemExit(f"canary entry gate not satisfied: {canary_release.get('status')}")
    shard_count = args.shard_count or int(cfg["sharding"]["shard_count"])
    workers = args.workers or int(cfg["sharding"]["workers_per_shard"])
    if args.shard_id < 0 or args.shard_id >= shard_count:
        raise SystemExit("invalid shard id")

    universe = matrix.load_universe(UNIVERSE)
    assignments = matrix.assign_shards(universe, shard_count)
    symbols = assignments[args.shard_id]
    if len(symbols) > int(cfg["sharding"]["maximum_symbols_per_shard"]):
        raise SystemExit(f"shard too large: {len(symbols)}")

    shard_name = f"shard-{args.shard_id:02d}"
    output = ROOT / "outputs/financials/full_build/matrix/shards" / shard_name
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    pd.DataFrame({"symbol": symbols}).to_csv(output / "SHARD_SYMBOLS.csv", index=False, encoding="utf-8-sig")

    base_index, base_registry = core.load_registry(FIELD_REGISTRY)
    registry_index, registry_payload = semantic.apply_overrides(base_index, base_registry)
    trading_days = pilot.fetch_calendar()
    runtime_cfg = shard_runtime_config(cfg)
    pilot_cfg = matrix.load_json(PILOT_CONFIG)

    started = time.monotonic()
    raw_rows: list[dict[str, Any]] = []
    revision_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    retry_rows: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(
                canary.extract_selected_facts,
                sample_for_symbol(symbol),
                runtime_cfg,
                registry_index,
                trading_days,
            ): symbol
            for symbol in symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                raw, revisions, sources, support = future.result()
                raw_rows.extend(raw)
                revision_rows.extend(revisions)
                source_rows.extend(sources)
                support_rows.append(support)
                if support["statement_status"] != "SUPPORTED" and support["board"] != "BSE":
                    retry_rows.append({
                        "symbol": symbol,
                        "retry_reason": support["status_reason"],
                        "retry_scope": "FULL_SYMBOL_PRIMARY_THEN_FALLBACK",
                        "status": "PENDING_REPAIR_OVERLAY",
                        "trade_authority": "NONE",
                    })
            except Exception as exc:
                sample = sample_for_symbol(symbol)
                support_rows.append({
                    "symbol": symbol,
                    "entity": symbol,
                    "profile": sample["profile"],
                    "board": sample["board"],
                    "official_filing_count": 0,
                    "official_document_index_available": False,
                    "primary_statement_components": 0,
                    "fallback_statement_components_invoked": 0,
                    "fallback_statement_components_used": 0,
                    "common_statement_period_count": 0,
                    "primary_only": False,
                    "statement_status": "QUARANTINED",
                    "status_reason": f"UNEXPECTED_SYMBOL_EXCEPTION:{type(exc).__name__}",
                    "trade_authority": "NONE",
                })
                retry_rows.append({
                    "symbol": symbol,
                    "retry_reason": f"{type(exc).__name__}:{str(exc)[:500]}",
                    "retry_scope": "FULL_SYMBOL_PRIMARY_THEN_FALLBACK",
                    "status": "PENDING_REPAIR_OVERLAY",
                    "trade_authority": "NONE",
                })

    elapsed = round(time.monotonic() - started, 4)
    frames = empty_outputs()
    raw = pd.DataFrame(raw_rows) if raw_rows else frames["raw"]
    normalized, conflicts = core.select_normalized_facts(
        raw,
        registry_payload,
        pilot_cfg["normalization"]["material_conflict_relative_tolerance"],
        pilot_cfg["normalization"]["material_conflict_absolute_tolerance"],
    )
    if normalized.empty:
        normalized = frames["normalized"]
    revisions = pd.DataFrame(revision_rows) if revision_rows else frames["revisions"]
    sources = pd.DataFrame(source_rows).drop_duplicates("source_id") if source_rows else frames["sources"]
    support = pd.DataFrame(support_rows).sort_values("symbol")
    retry = pd.DataFrame(retry_rows)
    if retry.empty:
        retry = matrix.empty_frame(["symbol", "retry_reason", "retry_scope", "status", "trade_authority"])
    if conflicts.empty:
        conflicts = matrix.empty_frame(["conflict_id", "entity", "symbol", "metric", "period", "source_a", "value_a", "source_b", "value_b", "conflict_type", "working_value", "resolution_basis", "open_question", "status", "trade_authority"])
    ambiguities = semantic.ambiguous_source_mapping_groups(raw)
    checks, flags, bridge = pilot.validation_checks(normalized, support, pilot_cfg)
    if checks.empty:
        checks = matrix.empty_frame(["check_id", "area", "period", "test", "expected_value", "observed_value", "variance", "result", "source_id", "notes"])
    if flags.empty:
        flags = matrix.empty_frame(["flag_id", "severity", "entity", "period", "area", "issue", "impact", "recommended_fix", "source_id", "status"])
    if bridge.empty:
        bridge = matrix.empty_frame(["area", "metric_or_framework", "current_period", "prior_period", "current_basis", "prior_basis", "comparison_status", "current_value", "prior_value", "model_treatment", "required_source", "source_id"])

    files = {
        "SHARD_RAW_FACTS.parquet": raw,
        "SHARD_NORMALIZED_LONG.parquet": normalized,
        "SHARD_REVISION_LEDGER.parquet": revisions,
        "SHARD_SOURCE_INDEX.parquet": sources,
    }
    for filename, frame in files.items():
        frame.to_parquet(output / filename, index=False, compression="zstd")
    support.to_csv(output / "SHARD_SUPPORT_MAP.csv", index=False, encoding="utf-8-sig")
    retry.to_csv(output / "SHARD_RETRY_LEDGER.csv", index=False, encoding="utf-8-sig")
    conflicts.to_csv(output / "SHARD_CONFLICT_LOG.csv", index=False, encoding="utf-8-sig")
    ambiguities.to_csv(output / "SHARD_AMBIGUOUS_MAPPING_GROUPS.csv", index=False, encoding="utf-8-sig")
    checks.to_csv(output / "SHARD_VALIDATION_CHECKS.csv", index=False, encoding="utf-8-sig")
    flags.to_csv(output / "SHARD_QA_FLAGS.csv", index=False, encoding="utf-8-sig")
    bridge.to_csv(output / "SHARD_COMPARABILITY_BRIDGE.csv", index=False, encoding="utf-8-sig")
    field_frequency = raw.groupby(["statement", "provider_field_name", "mapping_status", "canonical_field_id"], dropna=False).size().reset_index(name="fact_count").sort_values("fact_count", ascending=False) if len(raw) else matrix.empty_frame(["statement", "provider_field_name", "mapping_status", "canonical_field_id", "fact_count"])
    field_frequency.to_csv(output / "SHARD_FIELD_FREQUENCY.csv", index=False, encoding="utf-8-sig")

    non_bse = support[support["board"] != "BSE"]
    supported_ratio = float((non_bse["statement_status"] == "SUPPORTED").mean()) if len(non_bse) else 1.0
    pit_ratio = float(raw["available_from"].notna().mean()) if len(raw) else 1.0
    future = int((pd.to_datetime(raw["available_from"], errors="coerce", utc=True) < pd.to_datetime(raw["announcement_date"], errors="coerce", utc=True)).sum()) if len(raw) else 0
    decision_grade = normalized["decision_grade_eligible"].astype(bool) if len(normalized) else pd.Series(dtype=bool)
    source_less = int((decision_grade & normalized["source_id"].isna()).sum()) if len(normalized) else 0
    duplicate = core.duplicate_effective_intervals(normalized)
    unclassified_conflicts = int((conflicts["status"] != "CLASSIFIED_CONTROLLED_EXCLUSION").sum()) if len(conflicts) else 0
    performed_failures = int((checks["result"] == "FAIL").sum()) if len(checks) else 0
    bse = support[support["board"] == "BSE"]
    bse_documents = bool(bse["official_document_index_available"].astype(bool).all()) if len(bse) else True

    policy = cfg["shard_acceptance_policy"]
    tests = {
        "EXACT_SHARD_MEMBERSHIP": set(support["symbol"]) == set(symbols) and not support["symbol"].duplicated().any(),
        "NON_BSE_BUNDLE_GATE": supported_ratio >= policy["minimum_non_bse_statement_bundle_success_ratio"],
        "PIT_GATE": pit_ratio >= policy["minimum_official_pit_match_ratio"],
        "ZERO_AMBIGUITY": len(ambiguities) <= policy["maximum_ambiguous_mapping_group_count"],
        "ZERO_FUTURE": future <= policy["maximum_future_fact_count"],
        "ZERO_SOURCELESS": source_less <= policy["maximum_source_less_decision_grade_fact_count"],
        "ZERO_DUPLICATE_INTERVAL": duplicate <= policy["maximum_duplicate_effective_interval_count"],
        "ALL_CONFLICTS_CLASSIFIED": unclassified_conflicts <= policy["maximum_unclassified_conflict_count"],
        "PERFORMED_CHECKS_NO_FAILURE": performed_failures <= policy["maximum_performed_validation_failure_count"],
        "ALL_SUPPORTED_OR_QUARANTINED": set(support["statement_status"]).issubset({"SUPPORTED", "QUARANTINED"}),
        "BSE_DOCUMENT_INDEX": bse_documents,
        "ZERO_TRADE_AUTHORITY": set(raw["trade_authority"].dropna()).issubset({"NONE"}) and set(normalized["trade_authority"].dropna()).issubset({"NONE"}),
    }
    failures = [name for name, passed in tests.items() if not passed]
    run_id = f"FMDL3B2S_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}_{args.shard_id:02d}"
    decision = {
        "decision_version": "1.0.0",
        "run_id": run_id,
        "generated_at": core.now_iso(),
        "program_id": "FMDL-3B-2-SHARD",
        "shard_id": args.shard_id,
        "shard_count": shard_count,
        "shard_name": shard_name,
        "membership_hash": matrix.shard_membership_hash(symbols),
        "status": "FMDL3B2_SHARD_ACCEPTED" if not failures else "FMDL3B2_SHARD_REMEDIATION_REQUIRED",
        "hard_failures": failures,
        "checks": [{"check_id": name, "status": "PASS" if passed else "FAIL"} for name, passed in tests.items()],
        "metrics": {
            "symbol_count": len(symbols),
            "supported_symbol_count": int((support["statement_status"] == "SUPPORTED").sum()),
            "quarantined_symbol_count": int((support["statement_status"] == "QUARANTINED").sum()),
            "non_bse_supported_ratio": supported_ratio,
            "official_pit_match_ratio": pit_ratio,
            "raw_fact_count": len(raw),
            "normalized_fact_count": len(normalized),
            "decision_grade_fact_count": int(decision_grade.sum()) if len(normalized) else 0,
            "fallback_components_invoked": int(support["fallback_statement_components_invoked"].fillna(0).sum()),
            "fallback_components_used": int(support["fallback_statement_components_used"].fillna(0).sum()),
            "retry_symbol_count": len(retry),
            "ambiguous_mapping_group_count": len(ambiguities),
            "future_fact_count": future,
            "source_less_decision_grade_fact_count": source_less,
            "duplicate_effective_interval_count": duplicate,
            "classified_conflict_count": len(conflicts),
            "unclassified_conflict_count": unclassified_conflicts,
            "performed_validation_check_count": len(checks),
            "performed_validation_failure_count": performed_failures,
            "qa_flag_count": len(flags),
            "elapsed_seconds": elapsed,
        },
        "raw_artifact_contract": {
            "artifact_name": cfg["storage"]["raw_artifact_name_pattern"].format(shard_id=f"{args.shard_id:02d}"),
            "retention_days": cfg["sharding"]["raw_artifact_retention_days"],
            "raw_file": f"{shard_name}/SHARD_RAW_FACTS.parquet",
        },
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    matrix.write_json(output / "SHARD_DECISION.json", decision)

    manifest = {
        "manifest_version": "1.0.0",
        "run_id": run_id,
        "program_id": "FMDL-3B-2-SHARD",
        "shard_id": args.shard_id,
        "membership_hash": decision["membership_hash"],
        "status": "CANDIDATE",
        "files": [],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    for path in sorted(output.iterdir()):
        if path.name != "SHARD_MANIFEST.json":
            manifest["files"].append({"path": path.name, "sha256": matrix.file_sha256(path), "bytes": path.stat().st_size})
    matrix.write_json(output / "SHARD_MANIFEST.json", manifest)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
