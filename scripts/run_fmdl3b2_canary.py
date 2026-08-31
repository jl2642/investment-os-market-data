from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from scripts import fmdl3b_core as core
from scripts import fmdl3b_semantic_overrides as semantic
from scripts import run_fmdl3b_pilot as pilot

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3b2_full_build.json"
PILOT_CONFIG = ROOT / "config/fmdl3b_statement_store.json"
FIELD_REGISTRY = ROOT / "config/fmdl3b_field_registry.json"
PILOT_SAMPLE = ROOT / "config/fmdl3a_benchmark.json"
SNAPSHOT = ROOT / "outputs/current/DAILY_MARKET_SNAPSHOT.csv"
PILOT_RELEASE = ROOT / "outputs/financials/pilot/current/FMDL3B1_RELEASE.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive_board(symbol: str) -> str:
    code, exchange = symbol.split(".")
    if exchange == "BJ":
        return "BSE"
    if exchange == "SH" and code.startswith("688"):
        return "STAR"
    if exchange == "SZ" and code.startswith(("300", "301")):
        return "CHINEXT"
    return "SH_MAIN" if exchange == "SH" else "SZ_MAIN"


def load_universe() -> list[str]:
    frame = pd.read_csv(SNAPSHOT, encoding="utf-8-sig", usecols=["symbol"])
    symbols = sorted(set(frame["symbol"].dropna().astype(str)))
    return [symbol for symbol in symbols if "." in symbol]


def choose_canary(universe: list[str], size: int) -> list[dict[str, Any]]:
    pilot_samples = load_json(PILOT_SAMPLE)["sample_design"]["symbols"]
    by_symbol = {item["symbol"]: dict(item) for item in pilot_samples}
    selected = list(by_symbol)
    candidates = [symbol for symbol in universe if symbol not in by_symbol and not symbol.endswith(".BJ")]
    candidates.sort(key=lambda symbol: hashlib.sha256(symbol.encode("utf-8")).hexdigest())
    for symbol in candidates:
        if len(selected) >= size:
            break
        selected.append(symbol)
        by_symbol[symbol] = {
            "symbol": symbol,
            "name": symbol,
            "profile": "UNCLASSIFIED_FULL_UNIVERSE",
            "board": derive_board(symbol),
            "extended": False,
        }
    return [by_symbol[symbol] for symbol in selected[:size]]


def _pit_cutoff_utc(value: str | None) -> pd.Timestamp | None:
    if not value:
        return None
    ts = pd.Timestamp(str(value))
    if ts.tzinfo is None:
        # A date-only financial cutoff is aligned to the A-share completed
        # session close. available_from is defined at a trading open (09:30),
        # so 15:00 includes evidence available for that completed session.
        if len(str(value)) == 10:
            ts = ts.tz_localize("Asia/Shanghai") + pd.Timedelta(hours=15)
        else:
            ts = ts.tz_localize("Asia/Shanghai")
    return ts.tz_convert("UTC")


def filter_revision_rows_for_cutoff(
    revision_rows: list[dict[str, Any]],
    as_of_cutoff: str | None,
) -> tuple[list[dict[str, Any]], set[tuple[str, str]]]:
    cutoff = _pit_cutoff_utc(as_of_cutoff)
    if cutoff is None:
        return revision_rows, set()
    eligible: list[dict[str, Any]] = []
    contaminated: set[tuple[str, str]] = set()
    for row in revision_rows:
        available = pd.to_datetime(row.get("available_from"), errors="coerce", utc=True)
        key = (str(row.get("symbol") or ""), str(row.get("report_period_end") or ""))
        if pd.isna(available):
            continue
        if available <= cutoff:
            eligible.append(dict(row))
        else:
            contaminated.add(key)
    # If a later revision exists after the cutoff, the provider's current
    # structured value may already reflect it. Historical numeric replay is
    # therefore blocked for that period rather than back-filled from the
    # current provider export.
    return eligible, contaminated


def extract_selected_facts(
    sample: dict[str, Any],
    cfg: dict[str, Any],
    registry_index,
    trading_days: list[date],
    as_of_cutoff: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    end_date = datetime.now(TZ).strftime("%Y%m%d")
    start_date = cfg["canary"]["minimum_report_period_end"].replace("-", "")[:4] + "0101"
    filings, cninfo_source = pilot.fetch_filings(sample, start_date, end_date)
    all_revision_rows = core.build_revision_intervals(filings, trading_days, "09:30:00")
    revision_rows, cutoff_contaminated_periods = filter_revision_rows_for_cutoff(
        all_revision_rows, as_of_cutoff
    )
    latest = core.latest_revision_map(revision_rows)
    support = {
        "symbol": sample["symbol"],
        "entity": sample["name"],
        "profile": sample["profile"],
        "board": sample["board"],
        "official_filing_count": len(revision_rows) if as_of_cutoff else len(filings),
        "official_document_index_available": bool(revision_rows) if as_of_cutoff else bool(filings),
        "primary_statement_components": 0,
        "fallback_statement_components_invoked": 0,
        "fallback_statement_components_used": 0,
        "statement_status": "QUARANTINED" if sample["board"] == "BSE" else "PENDING",
        "status_reason": "BSE_OFFICIAL_DOCUMENT_EXTRACTION_REQUIRED" if sample["board"] == "BSE" else None,
        "trade_authority": "NONE",
    }
    if sample["board"] == "BSE":
        return [], revision_rows, [cninfo_source], support

    source_rows: list[dict[str, Any]] = [cninfo_source]
    raw_rows: list[dict[str, Any]] = []
    primary_frames, primary_sources = pilot.fetch_statement_bundle(sample, "EASTMONEY_STATEMENTS")
    source_rows.extend(primary_sources)
    missing_statements = [statement for statement, frame in primary_frames.items() if frame.empty]
    support["primary_statement_components"] = 3 - len(missing_statements)

    fallback_frames: dict[str, pd.DataFrame] = {}
    fallback_sources: list[dict[str, Any]] = []
    if missing_statements:
        fallback_frames, fallback_sources = pilot.fetch_statement_bundle(sample, "SINA_STATEMENTS")
        source_rows.extend(fallback_sources)
        support["fallback_statement_components_invoked"] = 3

    selected_periods: dict[str, set[str]] = {statement: set() for statement in pilot.STATEMENTS}
    for statement in pilot.STATEMENTS:
        if not primary_frames[statement].empty:
            frame = primary_frames[statement]
            source = next(item for item in primary_sources if item["statement"] == statement)
            route = "EASTMONEY_STATEMENTS"
        elif statement in fallback_frames and not fallback_frames[statement].empty:
            frame = fallback_frames[statement]
            source = next(item for item in fallback_sources if item["statement"] == statement)
            route = "SINA_STATEMENTS"
            support["fallback_statement_components_used"] += 1
        else:
            continue
        rows = core.extract_raw_facts(
            frame,
            sample,
            statement,
            source["source_id"],
            route,
            source["file_tab_page_url_or_location"],
            source["source_rank"],
            source["retrieved_at"],
            latest,
            cfg["canary"]["minimum_report_period_end"],
            cfg["canary"]["maximum_periods_per_statement"],
            registry_index,
        )
        if as_of_cutoff:
            cutoff = _pit_cutoff_utc(as_of_cutoff)
            rows = [
                row for row in rows
                if row.get("available_from")
                and pd.to_datetime(row.get("available_from"), errors="coerce", utc=True) <= cutoff
                and (str(row.get("symbol")), str(row.get("report_period_end")))
                not in cutoff_contaminated_periods
            ]
        raw_rows.extend(rows)
        selected_periods[statement] = {row["report_period_end"] for row in rows}

    common_periods = set.intersection(*(selected_periods[statement] for statement in pilot.STATEMENTS)) if all(selected_periods.values()) else set()
    support["common_statement_period_count"] = len(common_periods)
    support["primary_only"] = support["primary_statement_components"] == 3
    if len(common_periods) > 0 and bool(filings):
        support["statement_status"] = "SUPPORTED"
        support["status_reason"] = "SELECTED_THREE_STATEMENT_BUNDLE_WITH_OFFICIAL_PIT"
    else:
        support["statement_status"] = "QUARANTINED"
        support["status_reason"] = "SELECTED_BUNDLE_OR_OFFICIAL_PIT_INCOMPLETE"
    return raw_rows, revision_rows, source_rows, support


def parquet_roundtrip(path: Path, expected_rows: int) -> bool:
    return path.exists() and len(pd.read_parquet(path)) == expected_rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()
    cfg = load_json(args.config)
    pilot_release = load_json(PILOT_RELEASE)
    if pilot_release.get("status") != cfg["entry_gate"]:
        raise SystemExit(f"pilot entry gate not satisfied: {pilot_release.get('status')}")
    pilot_cfg = load_json(PILOT_CONFIG)
    workers = args.workers or int(cfg["canary"]["workers"])
    universe = load_universe()
    samples = choose_canary(universe, int(cfg["canary"]["symbol_count"]))
    base_index, base_registry = core.load_registry(FIELD_REGISTRY)
    registry_index, registry_payload = semantic.apply_overrides(base_index, base_registry)
    trading_days = pilot.fetch_calendar()
    run_id = f"FMDL3B2C_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"
    candidate = ROOT / cfg["publication"]["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True)

    started = time.monotonic()
    raw_rows: list[dict[str, Any]] = []
    revision_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(extract_selected_facts, sample, cfg, registry_index, trading_days): sample for sample in samples}
        for future in as_completed(futures):
            raw, revisions, sources, support = future.result()
            raw_rows.extend(raw)
            revision_rows.extend(revisions)
            source_rows.extend(sources)
            support_rows.append(support)
    elapsed = round(time.monotonic() - started, 4)

    raw = pd.DataFrame(raw_rows)
    normalized, conflicts = core.select_normalized_facts(
        raw,
        registry_payload,
        pilot_cfg["normalization"]["material_conflict_relative_tolerance"],
        pilot_cfg["normalization"]["material_conflict_absolute_tolerance"],
    )
    support = pd.DataFrame(support_rows).sort_values("symbol")
    revisions = pd.DataFrame(revision_rows)
    sources = pd.DataFrame(source_rows).drop_duplicates("source_id")
    ambiguities = semantic.ambiguous_source_mapping_groups(raw)
    checks, flags, bridge = pilot.validation_checks(normalized, support, pilot_cfg)
    if conflicts.empty:
        conflicts = pd.DataFrame(columns=["conflict_id", "entity", "symbol", "metric", "period", "source_a", "value_a", "source_b", "value_b", "conflict_type", "working_value", "resolution_basis", "open_question", "status", "trade_authority"])
    if checks.empty:
        checks = pd.DataFrame(columns=["check_id", "area", "period", "test", "expected_value", "observed_value", "variance", "result", "source_id", "notes"])
    if flags.empty:
        flags = pd.DataFrame(columns=["flag_id", "severity", "entity", "period", "area", "issue", "impact", "recommended_fix", "source_id", "status"])
    if bridge.empty:
        bridge = pd.DataFrame(columns=["area", "metric_or_framework", "current_period", "prior_period", "current_basis", "prior_basis", "comparison_status", "current_value", "prior_value", "model_treatment", "required_source", "source_id"])

    raw_path = candidate / "FMDL3B2_CANARY_RAW_FACTS.parquet"
    normalized_path = candidate / "FMDL3B2_CANARY_NORMALIZED_LONG.parquet"
    revisions_path = candidate / "FMDL3B2_CANARY_REVISION_LEDGER.parquet"
    sources_path = candidate / "FMDL3B2_CANARY_SOURCE_INDEX.parquet"
    raw.to_parquet(raw_path, index=False, compression="zstd")
    normalized.to_parquet(normalized_path, index=False, compression="zstd")
    revisions.to_parquet(revisions_path, index=False, compression="zstd")
    sources.to_parquet(sources_path, index=False, compression="zstd")

    support.to_csv(candidate / "FMDL3B2_CANARY_SUPPORT_MAP.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(samples).to_csv(candidate / "FMDL3B2_CANARY_SYMBOLS.csv", index=False, encoding="utf-8-sig")
    conflicts.to_csv(candidate / "FMDL3B2_CANARY_CONFLICT_LOG.csv", index=False, encoding="utf-8-sig")
    ambiguities.to_csv(candidate / "FMDL3B2_CANARY_AMBIGUOUS_MAPPING_GROUPS.csv", index=False, encoding="utf-8-sig")
    checks.to_csv(candidate / "FMDL3B2_CANARY_VALIDATION_CHECKS.csv", index=False, encoding="utf-8-sig")
    flags.to_csv(candidate / "FMDL3B2_CANARY_QA_FLAGS.csv", index=False, encoding="utf-8-sig")
    bridge.to_csv(candidate / "FMDL3B2_CANARY_COMPARABILITY_BRIDGE.csv", index=False, encoding="utf-8-sig")

    field_frequency = raw.groupby(["statement", "provider_field_name", "mapping_status", "canonical_field_id"], dropna=False).size().reset_index(name="fact_count").sort_values("fact_count", ascending=False)
    field_frequency.to_csv(candidate / "FMDL3B2_CANARY_FIELD_FREQUENCY.csv", index=False, encoding="utf-8-sig")

    non_bse = support[support["board"] != "BSE"]
    supported_ratio = float((non_bse["statement_status"] == "SUPPORTED").mean()) if len(non_bse) else 0.0
    primary_only_share = float(non_bse["primary_only"].astype(bool).mean()) if len(non_bse) else 0.0
    pit_ratio = float(raw["available_from"].notna().mean()) if len(raw) else 0.0
    future = int((pd.to_datetime(raw["available_from"], errors="coerce", utc=True) < pd.to_datetime(raw["announcement_date"], errors="coerce", utc=True)).sum()) if len(raw) else 0
    decision_grade = normalized["decision_grade_eligible"].astype(bool) if len(normalized) else pd.Series(dtype=bool)
    source_less = int((decision_grade & normalized["source_id"].isna()).sum()) if len(normalized) else 0
    duplicate = core.duplicate_effective_intervals(normalized)
    unclassified_conflicts = int((conflicts["status"] != "CLASSIFIED_CONTROLLED_EXCLUSION").sum()) if len(conflicts) else 0
    max_mib = max(path.stat().st_size for path in [raw_path, normalized_path, revisions_path, sources_path]) / 1024 / 1024
    processed_non_bse = max(1, len(non_bse))
    projected_raw_mib = raw_path.stat().st_size / processed_non_bse * len(universe) / 1024 / 1024
    projected_normalized_mib = normalized_path.stat().st_size / processed_non_bse * len(universe) / 1024 / 1024
    projected_wall_minutes = elapsed / processed_non_bse * len(universe) / max(1, cfg["full_build"]["planned_shard_count"]) / 60
    runtime_storage = {
        "run_id": run_id,
        "universe_symbol_count": len(universe),
        "canary_symbol_count": len(samples),
        "processed_non_bse_symbol_count": len(non_bse),
        "elapsed_seconds": elapsed,
        "workers": workers,
        "planned_shard_count": cfg["full_build"]["planned_shard_count"],
        "projected_wall_minutes_per_shard_at_canary_rate": projected_wall_minutes,
        "raw_parquet_bytes": raw_path.stat().st_size,
        "normalized_parquet_bytes": normalized_path.stat().st_size,
        "revision_parquet_bytes": revisions_path.stat().st_size,
        "source_index_parquet_bytes": sources_path.stat().st_size,
        "maximum_canary_file_mib": max_mib,
        "projected_full_universe_raw_mib": projected_raw_mib,
        "projected_full_universe_normalized_mib": projected_normalized_mib,
        "raw_storage_route": cfg["storage"]["raw_storage_mode"],
        "normalized_storage_route": cfg["storage"]["normalized_storage_mode"],
        "parquet_roundtrip": {
            "raw": parquet_roundtrip(raw_path, len(raw)),
            "normalized": parquet_roundtrip(normalized_path, len(normalized)),
            "revisions": parquet_roundtrip(revisions_path, len(revisions)),
            "sources": parquet_roundtrip(sources_path, len(sources)),
        },
    }
    write_json(candidate / "FMDL3B2_CANARY_RUNTIME_STORAGE.json", runtime_storage)

    policy = cfg["acceptance_policy"]
    failures: list[str] = []
    tests = {
        "CANARY_SYMBOL_COUNT": len(samples) >= policy["minimum_canary_symbol_count"],
        "PRIMARY_BUNDLE_GATE": supported_ratio >= policy["minimum_non_bse_primary_bundle_success_ratio"],
        "PIT_GATE": pit_ratio >= policy["minimum_official_pit_match_ratio"],
        "PRIMARY_ONLY_SHARE": primary_only_share >= policy["minimum_primary_only_share"],
        "ZERO_AMBIGUITY": len(ambiguities) <= policy["maximum_ambiguous_source_mapping_group_count"],
        "ZERO_FUTURE": future <= policy["maximum_future_fact_count"],
        "ZERO_SOURCELESS": source_less <= policy["maximum_source_less_decision_grade_fact_count"],
        "ZERO_DUPLICATE_INTERVAL": duplicate <= policy["maximum_duplicate_effective_interval_count"],
        "ALL_CONFLICTS_CLASSIFIED": unclassified_conflicts <= policy["maximum_unclassified_conflict_count"],
        "ALL_SUPPORTED_OR_QUARANTINED": set(support["statement_status"]).issubset({"SUPPORTED", "QUARANTINED"}),
        "BSE_DOCUMENT_INDEX": bool(support[support["board"] == "BSE"]["official_document_index_available"].astype(bool).all()),
        "PARQUET_ROUNDTRIP": all(runtime_storage["parquet_roundtrip"].values()),
        "MAX_FILE_SIZE": max_mib < cfg["storage"]["maximum_git_file_mib"],
        "NORMALIZED_STORAGE_PROJECTION": projected_normalized_mib <= cfg["storage"]["maximum_projected_normalized_store_mib"],
    }
    failures = [name for name, passed in tests.items() if not passed]
    decision = {
        "decision_version": "1.0.0",
        "run_id": run_id,
        "generated_at": core.now_iso(),
        "program_id": "FMDL-3B-2-CANARY",
        "status": "FMDL3B2_CANARY_ACCEPTED_FULL_UNIVERSE_MATRIX_AUTHORIZED" if not failures else "FMDL3B2_CANARY_REMEDIATION_REQUIRED",
        "hard_failures": failures,
        "checks": [{"check_id": name, "status": "PASS" if passed else "FAIL"} for name, passed in tests.items()],
        "metrics": {
            "universe_symbol_count": len(universe),
            "canary_symbol_count": len(samples),
            "supported_symbol_count": int((support["statement_status"] == "SUPPORTED").sum()),
            "quarantined_symbol_count": int((support["statement_status"] == "QUARANTINED").sum()),
            "non_bse_statement_bundle_success_ratio": supported_ratio,
            "primary_only_share": primary_only_share,
            "official_pit_match_ratio": pit_ratio,
            "raw_fact_count": len(raw),
            "normalized_fact_count": len(normalized),
            "decision_grade_fact_count": int(decision_grade.sum()) if len(normalized) else 0,
            "fallback_components_invoked": int(support["fallback_statement_components_invoked"].fillna(0).sum()),
            "fallback_components_used": int(support["fallback_statement_components_used"].fillna(0).sum()),
            "classified_conflict_count": len(conflicts),
            "ambiguous_mapping_group_count": len(ambiguities),
            "future_fact_count": future,
            "source_less_decision_grade_fact_count": source_less,
            "duplicate_effective_interval_count": duplicate,
            "performed_validation_check_count": len(checks),
            "performed_validation_failure_count": int((checks["result"] == "FAIL").sum()) if len(checks) else 0,
            "qa_flag_count": len(flags),
        },
        "runtime_storage_path": "FMDL3B2_CANARY_RUNTIME_STORAGE.json",
        "field_frequency_path": "FMDL3B2_CANARY_FIELD_FREQUENCY.csv",
        "controlled_limitations": [
            "CANARY_NOT_FULL_UNIVERSE_PUBLICATION",
            "BSE_DOCUMENT_EXTRACTION_NOT_YET_IMPLEMENTED",
            "RAW_FULL_UNIVERSE_STORAGE_ROUTE_REMAINS_ARTIFACT_SHARDED_UNTIL_RETENTION_AND_SIZE_POLICY_FINALIZED",
            "PROFILE_CLASSIFICATION_FOR_NON_PILOT_CANARY_NAMES_IS_UNCLASSIFIED",
        ],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    write_json(candidate / "FMDL3B2_CANARY_DECISION.json", decision)

    manifest = {"manifest_version": "1.0.0", "run_id": run_id, "program_id": "FMDL-3B-2-CANARY", "status": "CANDIDATE", "generated_at": core.now_iso(), "files": [], "authority": cfg["authority"], "trade_authority": "NONE"}
    for path in sorted(candidate.iterdir()):
        if path.name != "FMDL3B2_CANARY_MANIFEST.json":
            manifest["files"].append({"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size})
    write_json(candidate / "FMDL3B2_CANARY_MANIFEST.json", manifest)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
