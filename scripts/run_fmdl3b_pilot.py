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

import akshare as ak
import pandas as pd

from scripts import fmdl3b_core as core
from scripts import run_fmdl3a_benchmark_v2 as a3

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3b_statement_store.json"
REGISTRY = ROOT / "config/fmdl3b_field_registry.json"
SAMPLE_CONFIG = ROOT / "config/fmdl3a_benchmark.json"
FMDL3A_RELEASE = ROOT / "outputs/financials/benchmark/current/FMDL3A_RELEASE.json"

STATEMENTS = {
    "balance_sheet": ("stock_balance_sheet_by_report_em", "资产负债表"),
    "income_statement": ("stock_profit_sheet_by_report_em", "利润表"),
    "cash_flow": ("stock_cash_flow_sheet_by_report_em", "现金流量表")
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(function, kwargs: dict[str, Any], tries: int = 2):
    started = time.monotonic()
    last: Exception | None = None
    for attempt in range(1, tries + 1):
        try:
            frame = function(**kwargs)
            if not isinstance(frame, pd.DataFrame):
                frame = pd.DataFrame(frame)
            return ("SUCCESS" if not frame.empty else "EMPTY", frame, attempt, round(time.monotonic() - started, 4), None, None)
        except Exception as exc:
            last = exc
            if attempt < tries:
                time.sleep(attempt)
    return ("ERROR", pd.DataFrame(), tries, round(time.monotonic() - started, 4), type(last).__name__, str(last)[:1000])


def fetch_calendar() -> list[date]:
    frame = ak.tool_trade_date_hist_sina()
    column = "trade_date" if "trade_date" in frame.columns else frame.columns[0]
    return sorted(pd.to_datetime(frame[column], errors="coerce").dropna().dt.date.tolist())


def fetch_filings(sample: dict[str, Any], start_date: str, end_date: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    result = invoke(
        ak.stock_zh_a_disclosure_report_cninfo,
        {"symbol": core.code(sample["symbol"]), "market": "沪深京", "keyword": "报告", "category": "", "start_date": start_date, "end_date": end_date},
        tries=3,
    )
    filings: list[dict[str, Any]] = []
    if len(result[1]):
        filings = a3.classify_filings(result[1], "CNINFO_OFFICIAL_DISCLOSURE", sample, ["公告标题"], ["公告时间"], ["公告链接"])
    source = {
        "source_id": f"SRC-CNINFO-{core.code(sample['symbol'])}",
        "source_name": f"CNINFO periodic reports for {sample['symbol']}",
        "source_type": "filing",
        "owner_or_provider": "CNINFO",
        "period_covered": f"{start_date}-{end_date}",
        "as_of_date": end_date,
        "retrieved_at": core.now_iso(),
        "file_tab_page_url_or_location": "akshare.stock_zh_a_disclosure_report_cninfo",
        "source_rank": "REGULATORY_OR_EXCHANGE_STRUCTURED_DISCLOSURE",
        "freshness_status": "current" if result[0] == "SUCCESS" else "unknown",
        "notes": f"status={result[0]}; rows={len(result[1])}; error={result[5] or ''}",
        "trade_authority": "NONE",
    }
    for filing in filings:
        filing["source_id"] = source["source_id"]
    return filings, source


def fetch_statement_bundle(sample: dict[str, Any], route_id: str) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    frames: dict[str, pd.DataFrame] = {}
    sources: list[dict[str, Any]] = []
    for statement, (em_function, sina_name) in STATEMENTS.items():
        if route_id == "EASTMONEY_STATEMENTS":
            function = getattr(ak, em_function)
            kwargs = {"symbol": core.em_symbol(sample["symbol"])}
            adapter = f"akshare.{em_function}"
            rank = "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"
        else:
            function = ak.stock_financial_report_sina
            kwargs = {"stock": core.sina_symbol(sample["symbol"]), "symbol": sina_name}
            adapter = "akshare.stock_financial_report_sina"
            rank = "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER_FALLBACK"
        result = invoke(function, kwargs, tries=2)
        frames[statement] = result[1]
        sources.append({
            "source_id": f"SRC-{route_id}-{core.code(sample['symbol'])}-{statement.upper()}",
            "source_name": f"{route_id} {statement} {sample['symbol']}",
            "source_type": "provider_export",
            "owner_or_provider": "Eastmoney" if route_id == "EASTMONEY_STATEMENTS" else "Sina",
            "period_covered": "provider-returned-history",
            "as_of_date": datetime.now(TZ).date().isoformat(),
            "retrieved_at": core.now_iso(),
            "file_tab_page_url_or_location": adapter,
            "source_rank": rank,
            "freshness_status": "current" if result[0] == "SUCCESS" else "unknown",
            "notes": f"route_id={route_id}; status={result[0]}; rows={len(result[1])}; cols={len(result[1].columns)}; elapsed={result[3]}; error={result[5] or ''}",
            "route_id": route_id,
            "statement": statement,
            "status": result[0],
            "trade_authority": "NONE",
        })
    return frames, sources


def symbol_job(sample: dict[str, Any], cfg: dict[str, Any], registry_index, registry_payload, trading_days: list[date]):
    end_date = datetime.now(TZ).strftime("%Y%m%d")
    start_date = cfg["scope"]["minimum_report_period_end"].replace("-", "")[:4] + "0101"
    filings, cninfo_source = fetch_filings(sample, start_date, end_date)
    revision_rows = core.build_revision_intervals(filings, trading_days, cfg["point_in_time"]["market_open_time"])
    latest = core.latest_revision_map(revision_rows)
    support = {
        "symbol": sample["symbol"],
        "entity": sample["name"],
        "profile": sample["profile"],
        "board": sample["board"],
        "official_filing_count": len(filings),
        "official_document_index_available": bool(filings),
        "statement_status": "QUARANTINED" if sample["board"] == "BSE" else "PENDING",
        "status_reason": "BSE_OFFICIAL_DOCUMENT_INDEX_ONLY_PENDING_FMDL3B2_EXTRACTION" if sample["board"] == "BSE" else None,
        "trade_authority": "NONE",
    }
    if sample["board"] == "BSE":
        return [], revision_rows, [cninfo_source], support
    raw_rows: list[dict[str, Any]] = []
    source_rows = [cninfo_source]
    route_success: dict[str, int] = {}
    for route in ["EASTMONEY_STATEMENTS", "SINA_STATEMENTS"]:
        frames, sources = fetch_statement_bundle(sample, route)
        source_rows.extend(sources)
        route_success[route] = sum(not frame.empty for frame in frames.values())
        for statement, frame in frames.items():
            source_row = next(item for item in sources if item["statement"] == statement)
            raw_rows.extend(
                core.extract_raw_facts(
                    frame,
                    sample,
                    statement,
                    source_row["source_id"],
                    route,
                    source_row["file_tab_page_url_or_location"],
                    source_row["source_rank"],
                    source_row["retrieved_at"],
                    latest,
                    cfg["scope"]["minimum_report_period_end"],
                    cfg["scope"]["maximum_periods_per_statement"],
                    registry_index,
                )
            )
    periods_by_statement = {
        statement: sorted({row["report_period_end"] for row in raw_rows if row["statement"] == statement and row["source_route_id"] == "EASTMONEY_STATEMENTS"})
        for statement in STATEMENTS
    }
    common = set.intersection(*(set(v) for v in periods_by_statement.values())) if all(periods_by_statement.values()) else set()
    support["statement_status"] = "SUPPORTED" if len(common) > 0 and route_success.get("EASTMONEY_STATEMENTS") == 3 else "QUARANTINED"
    support["status_reason"] = "PRIMARY_THREE_STATEMENT_BUNDLE_WITH_OFFICIAL_PIT" if support["statement_status"] == "SUPPORTED" else "PRIMARY_BUNDLE_OR_OFFICIAL_PIT_INCOMPLETE"
    support["primary_statement_components"] = route_success.get("EASTMONEY_STATEMENTS", 0)
    support["fallback_statement_components"] = route_success.get("SINA_STATEMENTS", 0)
    support["common_primary_period_count"] = len(common)
    return raw_rows, revision_rows, source_rows, support


def validation_checks(normalized: pd.DataFrame, support: pd.DataFrame, cfg: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    checks: list[dict[str, Any]] = []
    flags: list[dict[str, Any]] = []
    bridge: list[dict[str, Any]] = []
    counter = 0

    def add(area, period, test, expected, observed, variance, result, source_id="MULTI_SOURCE", notes=""):
        nonlocal counter
        counter += 1
        checks.append({"check_id": f"CHK-{counter:05d}", "area": area, "period": period, "test": test, "expected_value": expected, "observed_value": observed, "variance": variance, "result": result, "source_id": source_id, "notes": notes})

    for (symbol, period), group in normalized.groupby(["symbol", "period_end"]):
        values = group.set_index("line_item_id")["normalized_value"].to_dict()
        if {"total_assets", "total_liabilities", "total_equity"}.issubset(values):
            expected = values["total_assets"]
            observed = values["total_liabilities"] + values["total_equity"]
            variance = observed - expected
            tolerance = max(abs(expected) * cfg["normalization"]["balance_sheet_relative_tolerance"], 1.0)
            result = "PASS" if abs(variance) <= tolerance else "FAIL"
            add("balance_sheet", period, f"{symbol}: assets = liabilities + equity", expected, observed, variance, result)
            if result == "FAIL":
                flags.append({"flag_id": f"FLAG-{len(flags)+1:05d}", "severity": "high", "entity": symbol, "period": period, "area": "balance_sheet", "issue": "Balance sheet does not tie within tolerance", "impact": "Affected period is audit-only for downstream modeling", "recommended_fix": "Reconcile provider field mapping and official filing", "source_id": "MULTI_SOURCE", "status": "OPEN"})
        if {"cfo", "cfi", "cff", "net_change_cash"}.issubset(values):
            expected = values["net_change_cash"]
            observed = values["cfo"] + values["cfi"] + values["cff"] + values.get("fx_cash_effect", 0.0)
            variance = observed - expected
            tolerance = max(abs(expected) * cfg["normalization"]["cash_flow_relative_tolerance"], 1.0)
            add("cash_flow", period, f"{symbol}: CFO+CFI+CFF+FX = net change cash", expected, observed, variance, "PASS" if abs(variance) <= tolerance else "FAIL")
        if {"beginning_cash", "net_change_cash", "ending_cash"}.issubset(values):
            expected = values["ending_cash"]
            observed = values["beginning_cash"] + values["net_change_cash"]
            variance = observed - expected
            tolerance = max(abs(expected) * cfg["normalization"]["cash_flow_relative_tolerance"], 1.0)
            add("cash_flow", period, f"{symbol}: beginning cash + net change = ending cash", expected, observed, variance, "PASS" if abs(variance) <= tolerance else "FAIL")
    for symbol, group in normalized.groupby("symbol"):
        for item_id, series in group.groupby("line_item_id"):
            originals = sorted(set(series["line_item_original"].astype(str)))
            if len(originals) > 1:
                bridge.append({"area": series.iloc[0]["statement"], "metric_or_framework": item_id, "current_period": series["period_end"].max(), "prior_period": series["period_end"].min(), "current_basis": originals[-1], "prior_basis": originals[0], "comparison_status": "recast_comparable", "current_value": None, "prior_value": None, "model_treatment": "USE_CANONICAL_SERIES_WITH_ORIGINAL_LABEL_LINEAGE", "required_source": "official filing if values conflict", "source_id": "MULTI_SOURCE"})
    for _, row in support[support["statement_status"] == "QUARANTINED"].iterrows():
        flags.append({"flag_id": f"FLAG-{len(flags)+1:05d}", "severity": "blocker" if row["board"] != "BSE" else "high", "entity": row["symbol"], "period": "ALL", "area": "statement_coverage", "issue": row["status_reason"], "impact": "No normalized decision-grade statement facts", "recommended_fix": "BSE: implement CNINFO document extraction in FMDL-3B-2; other boards: retry/reconcile source routes", "source_id": "CNINFO_OFFICIAL_DISCLOSURE", "status": "CONTROLLED_QUARANTINE"})
    return pd.DataFrame(checks), pd.DataFrame(flags), pd.DataFrame(bridge)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    cfg = read_json(args.config)
    release = read_json(FMDL3A_RELEASE)
    if release.get("status") != cfg["entry_gate"]:
        raise SystemExit(f"FMDL-3A entry gate not satisfied: {release.get('status')}")
    samples = read_json(SAMPLE_CONFIG)["sample_design"]["symbols"]
    registry_index, registry_payload = core.load_registry(REGISTRY)
    trading_days = fetch_calendar()
    run_id = f"FMDL3B1_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"
    candidate = ROOT / cfg["publication"]["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True)
    raw_rows: list[dict[str, Any]] = []
    revision_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(symbol_job, sample, cfg, registry_index, registry_payload, trading_days): sample for sample in samples}
        for future in as_completed(futures):
            raw, revisions, sources, support = future.result()
            raw_rows.extend(raw)
            revision_rows.extend(revisions)
            source_rows.extend(sources)
            support_rows.append(support)
    raw = pd.DataFrame(raw_rows)
    normalized, conflicts = core.select_normalized_facts(raw, registry_payload, cfg["normalization"]["material_conflict_relative_tolerance"], cfg["normalization"]["material_conflict_absolute_tolerance"])
    if conflicts.empty:
        conflicts = pd.DataFrame(columns=["conflict_id", "entity", "symbol", "metric", "period", "source_a", "value_a", "source_b", "value_b", "conflict_type", "working_value", "resolution_basis", "open_question", "status", "trade_authority"])
    support = pd.DataFrame(support_rows).sort_values("symbol")
    revisions = pd.DataFrame(revision_rows)
    source_index = pd.DataFrame(source_rows).drop_duplicates("source_id")
    checks, flags, bridge = validation_checks(normalized, support, cfg)
    if checks.empty:
        checks = pd.DataFrame(columns=["check_id", "area", "period", "test", "expected_value", "observed_value", "variance", "result", "source_id", "notes"])
    if flags.empty:
        flags = pd.DataFrame(columns=["flag_id", "severity", "entity", "period", "area", "issue", "impact", "recommended_fix", "source_id", "status"])
    if bridge.empty:
        bridge = pd.DataFrame(columns=["area", "metric_or_framework", "current_period", "prior_period", "current_basis", "prior_basis", "comparison_status", "current_value", "prior_value", "model_treatment", "required_source", "source_id"])
    coverage = support.groupby(["board", "profile", "statement_status"], dropna=False).size().reset_index(name="symbol_count")
    outputs = {
        "FMDL3B_RAW_FACTS.csv": raw,
        "FMDL3B_NORMALIZED_LONG.csv": normalized,
        "FMDL3B_SOURCE_INDEX.csv": source_index,
        "FMDL3B_REVISION_LEDGER.csv": revisions,
        "FMDL3B_COMPARABILITY_BRIDGE.csv": bridge,
        "FMDL3B_CONFLICT_LOG.csv": conflicts,
        "FMDL3B_QA_FLAGS.csv": flags,
        "FMDL3B_VALIDATION_CHECKS.csv": checks,
        "FMDL3B_SUPPORT_MAP.csv": support,
        "FMDL3B_COVERAGE.csv": coverage,
    }
    for name, frame in outputs.items():
        frame.to_csv(candidate / name, index=False, encoding="utf-8-sig")
    supported_non_bse = support[support["board"] != "BSE"]
    supported_ratio = float((supported_non_bse["statement_status"] == "SUPPORTED").mean()) if len(supported_non_bse) else 0.0
    pit_ratio = float(raw["available_from"].notna().mean()) if len(raw) else 0.0
    decision = {
        "decision_version": "1.0.0",
        "run_id": run_id,
        "generated_at": core.now_iso(),
        "program_id": "FMDL-3B-1",
        "status": "FMDL3B1_ACCEPTED_NORMALIZATION_PILOT" if supported_ratio >= cfg["acceptance_policy"]["minimum_supported_symbol_statement_bundle_ratio"] and pit_ratio >= cfg["acceptance_policy"]["minimum_official_pit_match_ratio"] else "FMDL3B1_REMEDIATION_REQUIRED",
        "metrics": {
            "sample_symbol_count": len(samples),
            "supported_symbol_count": int((support["statement_status"] == "SUPPORTED").sum()),
            "quarantined_symbol_count": int((support["statement_status"] == "QUARANTINED").sum()),
            "supported_non_bse_statement_bundle_ratio": supported_ratio,
            "official_pit_match_ratio": pit_ratio,
            "raw_fact_count": len(raw),
            "mapped_normalized_fact_count": len(normalized),
            "decision_grade_fact_count": int(normalized["decision_grade_eligible"].sum()) if len(normalized) else 0,
            "unmapped_raw_fact_count": int((raw["mapping_status"] == "UNMAPPED_RAW_ONLY").sum()) if len(raw) else 0,
            "classified_conflict_count": len(conflicts),
            "unclassified_conflict_count": 0,
            "future_fact_count": int((pd.to_datetime(raw["available_from"], errors="coerce", utc=True) < pd.to_datetime(raw["announcement_date"], errors="coerce", utc=True)).sum()) if len(raw) else 0,
            "source_less_decision_grade_fact_count": int((normalized["decision_grade_eligible"] & normalized["source_id"].isna()).sum()) if len(normalized) else 0,
            "duplicate_effective_interval_count": core.duplicate_effective_intervals(normalized),
            "validation_check_count": len(checks),
            "qa_flag_count": len(flags),
            "bse_official_document_index_ratio": float(support[support["board"] == "BSE"]["official_document_index_available"].mean()),
        },
        "controlled_limitations": [
            "PILOT_SCOPE_ONLY_NOT_FULL_UNIVERSE_COVERAGE",
            "BSE_OFFICIAL_DOCUMENTS_INDEXED_BUT_STRUCTURED_EXTRACTION_DEFERRED_TO_FMDL3B2",
            "PRIOR_REVISIONS_WITHOUT_HISTORICAL_STRUCTURED_VALUES_RETAINED_AS_DOCUMENT_ONLY",
            "UNMAPPED_PROVIDER_FIELDS_RETAINED_IN_RAW_STORE_AND_NOT_FORCED_INTO_CANONICAL_TAXONOMY",
        ],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_phase": "FMDL-3B-2",
    }
    write_json(candidate / "FMDL3B1_DECISION.json", decision)
    manifest = {"manifest_version": "1.0.0", "run_id": run_id, "program_id": "FMDL-3B-1", "status": "CANDIDATE", "generated_at": core.now_iso(), "files": [], "authority": cfg["authority"], "trade_authority": "NONE"}
    for path in sorted(candidate.iterdir()):
        if path.name != "FMDL3B1_MANIFEST.json":
            manifest["files"].append({"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size})
    write_json(candidate / "FMDL3B1_MANIFEST.json", manifest)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if decision["status"] == "FMDL3B1_ACCEPTED_NORMALIZATION_PILOT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
