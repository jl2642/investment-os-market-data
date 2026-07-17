from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd

from scripts import run_fmdl3a_benchmark_v2 as base

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/fmdl3a_benchmark.json"

# Re-export deterministic helpers for contract tests.
clean_title = base.clean_title
parse_period = base.parse_period
next_trading_open = base.next_trading_open

base.META["XUEQIU_CURRENT_VALUATION"] = (
    "VALUATION_AND_CAPITALIZATION",
    "MARKET_DATA_PROVIDER_FOR_MARKET_NUMERATORS",
)


def dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def xueqiu_symbol(symbol: str) -> str:
    security_code, exchange = symbol.split(".")
    return f"{exchange}{security_code}"


def benchmark_xueqiu_valuation(samples: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    successful = 0
    elapsed = 0.0
    required_items = {"代码", "现价", "资产净值/总市值", "流通值", "市净率", "基金份额/总股本"}
    optional_items = {"市盈率(TTM)", "市盈率(动)", "市盈率(静)", "市销率", "每股收益"}
    for sample in samples:
        result = base.invoke(
            ak.stock_individual_spot_xq,
            {"symbol": xueqiu_symbol(sample["symbol"]), "timeout": 20},
            tries=2,
        )
        elapsed += result[3]
        row = base.benchmark_row(
            run_id,
            sample,
            "XUEQIU_CURRENT_VALUATION",
            "CURRENT_VALUATION_AND_CAPITALIZATION",
            "akshare.stock_individual_spot_xq",
            result,
        )
        frame = result[1]
        item_col = base.find_col(frame, ["item"])
        value_col = base.find_col(frame, ["value"])
        observed = set(frame[item_col].astype(str)) if item_col else set()
        required_hits = len(required_items & observed)
        optional_hits = len(optional_items & observed)
        row["required_field_hits"] = required_hits
        row["required_field_total"] = len(required_items)
        row["sample_value_coverage_ratio"] = required_hits / len(required_items)
        row["temporal_fields_present"] = "时间" if "时间" in observed else ""
        row["valuation_optional_field_hits"] = optional_hits
        row["has_current_value_column"] = bool(value_col)
        usable = result[0] == "SUCCESS" and required_hits == len(required_items) and bool(value_col)
        row["status"] = "SUCCESS" if usable else ("PARTIAL" if result[0] == "SUCCESS" else result[0])
        row["record_quality"] = "VALID" if usable else ("PARTIAL" if result[0] == "SUCCESS" else "INVALID")
        if usable:
            successful += 1
        rows.append(row)
    coverage = successful / len(samples) if samples else 0.0
    bundle_result = (
        "SUCCESS" if coverage > 0 else "ERROR",
        pd.DataFrame({"symbol": [sample["symbol"] for sample in samples]}),
        1,
        round(elapsed, 4),
        None,
        None,
    )
    bundle = base.benchmark_row(
        run_id,
        None,
        "XUEQIU_CURRENT_VALUATION",
        "SAMPLE_CURRENT_VALUATION_BUNDLE",
        "per-symbol SH/SZ/BJ Xueqiu route",
        bundle_result,
    )
    bundle["row_count"] = successful
    bundle["required_field_hits"] = successful
    bundle["required_field_total"] = len(samples)
    bundle["sample_value_coverage_ratio"] = coverage
    bundle["record_quality"] = "VALID" if coverage == 1.0 else "PARTIAL"
    rows.append(bundle)
    return rows


def rejected_eastmoney_valuation_row(run_id: str) -> dict[str, Any]:
    result = (
        "REJECTED",
        pd.DataFrame(),
        1,
        0.0,
        "REPEATED_GITHUB_RUNNER_REMOTE_DISCONNECT",
        "Rejected after aggregate and split-market routes repeatedly disconnected in accepted benchmark evidence runs.",
    )
    return base.benchmark_row(
        run_id,
        None,
        "EASTMONEY_CURRENT_VALUATION",
        "REJECTED_ROUTE_EVIDENCE",
        "akshare.stock_zh_a_spot_em and split exchange endpoints",
        result,
    )


def benchmark_global_sources(samples: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    rows = benchmark_xueqiu_valuation(samples, run_id)
    rows.append(rejected_eastmoney_valuation_row(run_id))
    result = base.invoke(ak.stock_repurchase_em, tries=3)
    row = base.benchmark_row(
        run_id,
        None,
        "EASTMONEY_BUYBACKS",
        "FULL_MARKET_BUYBACK_EVENTS",
        "akshare.stock_repurchase_em",
        result,
    )
    if len(result[1]):
        expected = ["股票代码", "计划回购金额区间-下限", "已回购股份数量", "已回购金额", "最新公告日期"]
        row["required_field_hits"] = sum(bool(base.find_col(result[1], [name])) for name in expected)
        row["required_field_total"] = len(expected)
        row["sample_value_coverage_ratio"] = row["required_field_hits"] / len(expected)
        row["has_announcement_date"] = bool(base.find_col(result[1], ["最新公告日期"]))
    rows.append(row)
    return rows


def build_support_quarantine_map(
    samples: list[dict[str, Any]], rows: pd.DataFrame
) -> pd.DataFrame:
    output: list[dict[str, Any]] = []
    for sample in samples:
        primary_source = "EASTMONEY_BSE_PERIODIC_STATEMENTS" if sample["board"] == "BSE" else "EASTMONEY_STATEMENTS"
        bundle = rows[
            (rows["source_id"] == primary_source)
            & (rows["component"] == "THREE_STATEMENT_BUNDLE")
            & (rows["symbol"] == sample["symbol"])
        ]
        structured_success = bool(len(bundle) and bundle["status"].iloc[0] == "SUCCESS")
        disclosure = rows[
            (rows["source_id"] == "CNINFO_OFFICIAL_DISCLOSURE")
            & (rows["symbol"] == sample["symbol"])
        ]
        parsed_count = 0
        if len(disclosure) and "parsed_periodic_filing_count" in disclosure.columns:
            parsed_count = int(pd.to_numeric(disclosure["parsed_periodic_filing_count"], errors="coerce").fillna(0).max())
        official_document = bool(len(disclosure) and disclosure["status"].eq("SUCCESS").any() and parsed_count > 0)
        if structured_success:
            status = "SUPPORTED"
            reason = "STRUCTURED_THREE_STATEMENT_BUNDLE_ACCEPTED"
        elif sample["board"] == "BSE" and official_document:
            status = "QUARANTINED"
            reason = "BSE_STRUCTURED_STATEMENT_ROUTE_UNAVAILABLE; OFFICIAL_CNINFO_DOCUMENT_EXTRACTION_REQUIRED_IN_FMDL3B"
        else:
            status = "BLOCKED"
            reason = "NO_ACCEPTED_STRUCTURED_STATEMENT_OR_CONTROLLED_OFFICIAL_DOCUMENT_ROUTE"
        output.append(
            {
                **sample,
                "statement_status": status,
                "selected_structured_source_id": primary_source,
                "structured_bundle_success": structured_success,
                "official_document_source_available": official_document,
                "parsed_official_periodic_filing_count": parsed_count,
                "status_reason": reason,
            }
        )
    return pd.DataFrame(output)


def source_decision(decisions: list[dict[str, Any]], source_id: str, decision: str, **metrics: Any) -> None:
    decisions.append({"source_id": source_id, "decision": decision, **metrics})


def build_decision(
    config: dict[str, Any],
    rows: pd.DataFrame,
    summary: pd.DataFrame,
    pit: pd.DataFrame,
    trading_dates: list[date],
    support_map: pd.DataFrame,
    run_id: str,
) -> dict[str, Any]:
    policy = config["acceptance_policy"]
    official_ratio = base.source_success_ratio(summary, "CNINFO_OFFICIAL_DISCLOSURE")
    fallback_notice_ratio = base.source_success_ratio(summary, "EASTMONEY_NOTICE_FALLBACK")
    sh_sz_ratio = base.statement_bundle_ratio(rows, "EASTMONEY_STATEMENTS")
    fallback_statement_ratio = base.statement_bundle_ratio(rows, "SINA_STATEMENTS")
    supported = support_map["statement_status"].eq("SUPPORTED")
    quarantined = support_map["statement_status"].eq("QUARANTINED")
    blocked = support_map["statement_status"].eq("BLOCKED")
    eligible_denominator = int((~quarantined).sum())
    supported_universe_ratio = float(supported.sum() / eligible_denominator) if eligible_denominator else 0.0
    quarantine_ratio = float(quarantined.mean()) if len(support_map) else 1.0
    all_supported_or_quarantined = not bool(blocked.any())
    bse = support_map[support_map["board"] == "BSE"]
    bse_document_ratio = float(bse["official_document_source_available"].mean()) if len(bse) else 0.0
    profile_complete = bool(
        support_map.groupby("profile")["statement_status"].apply(lambda series: series.isin({"SUPPORTED", "QUARANTINED"}).all()).all()
    )
    board_complete = bool(
        support_map.groupby("board")["statement_status"].apply(lambda series: series.isin({"SUPPORTED", "QUARANTINED"}).all()).all()
    )
    official_pit_ratio = float(pit["match_status"].eq("OFFICIAL_MATCHED").mean()) if len(pit) else 0.0
    future_count = int(pit["future_information_flag"].fillna(False).astype(bool).sum()) if len(pit) else 0
    valuation_bundle = rows[
        (rows["source_id"] == "XUEQIU_CURRENT_VALUATION")
        & (rows["component"] == "SAMPLE_CURRENT_VALUATION_BUNDLE")
    ]
    valuation_coverage = (
        float(valuation_bundle["sample_value_coverage_ratio"].iloc[0])
        if len(valuation_bundle) and pd.notna(valuation_bundle["sample_value_coverage_ratio"].iloc[0])
        else 0.0
    )
    extended_sources = [
        "EASTMONEY_FINANCIAL_INDICATORS",
        "EASTMONEY_HISTORICAL_VALUATION",
        "EASTMONEY_SHARE_CAPITAL",
        "EASTMONEY_DIVIDENDS",
    ]
    extended_ratios = {source_id: base.source_success_ratio(summary, source_id) for source_id in extended_sources}
    buyback_ratio = base.source_success_ratio(summary, "EASTMONEY_BUYBACKS")

    hard_failures: list[str] = []
    if not trading_dates:
        hard_failures.append("TRADING_CALENDAR_UNAVAILABLE")
    if official_ratio < policy["minimum_official_disclosure_call_success_ratio"]:
        hard_failures.append("OFFICIAL_DISCLOSURE_ROUTE_BELOW_THRESHOLD")
    if sh_sz_ratio < policy["minimum_sh_sz_statement_bundle_success_ratio"]:
        hard_failures.append("SH_SZ_STATEMENT_BUNDLE_BELOW_THRESHOLD")
    if fallback_statement_ratio < policy["minimum_statement_fallback_bundle_success_ratio"]:
        hard_failures.append("STATEMENT_FALLBACK_BUNDLE_BELOW_THRESHOLD")
    if supported_universe_ratio < policy["minimum_supported_universe_statement_bundle_success_ratio"]:
        hard_failures.append("SUPPORTED_UNIVERSE_STATEMENT_BUNDLE_BELOW_THRESHOLD")
    if quarantine_ratio > policy["maximum_full_sample_statement_quarantine_ratio"]:
        hard_failures.append("STATEMENT_QUARANTINE_RATIO_ABOVE_CAP")
    if policy["require_all_symbols_supported_or_quarantined"] and not all_supported_or_quarantined:
        hard_failures.append("UNCONTROLLED_BLOCKED_SAMPLE_SYMBOL")
    if policy["require_bse_official_document_source"] and bse_document_ratio < 1.0:
        hard_failures.append("BSE_OFFICIAL_DOCUMENT_SOURCE_GAP")
    if policy["require_each_profile_supported_or_quarantined"] and not profile_complete:
        hard_failures.append("PROFILE_SUPPORT_OR_QUARANTINE_GAP")
    if policy["require_each_board_supported_or_quarantined"] and not board_complete:
        hard_failures.append("BOARD_SUPPORT_OR_QUARANTINE_GAP")
    if official_pit_ratio < policy["minimum_point_in_time_match_ratio"]:
        hard_failures.append("POINT_IN_TIME_OFFICIAL_MATCH_BELOW_THRESHOLD")
    if valuation_coverage < policy["minimum_current_valuation_sample_coverage"]:
        hard_failures.append("CURRENT_VALUATION_SAMPLE_COVERAGE_BELOW_THRESHOLD")
    if future_count:
        hard_failures.append(f"POINT_IN_TIME_FUTURE_INFORMATION:{future_count}")

    decisions: list[dict[str, Any]] = []
    source_decision(
        decisions,
        "CNINFO_OFFICIAL_DISCLOSURE",
        "PRIMARY_ANNOUNCEMENT_REVISION_AND_BSE_DOCUMENT_SOURCE" if official_ratio >= policy["minimum_official_disclosure_call_success_ratio"] else "REMEDIATION_REQUIRED",
        success_ratio=round(official_ratio, 6),
        point_in_time_match_ratio=round(official_pit_ratio, 6),
        bse_official_document_ratio=round(bse_document_ratio, 6),
    )
    source_decision(decisions, "EASTMONEY_NOTICE_FALLBACK", "DEGRADED_METADATA_FALLBACK_SH_SZ_ONLY", success_ratio=round(fallback_notice_ratio, 6))
    source_decision(decisions, "EASTMONEY_STATEMENTS", "PRIMARY_STRUCTURED_THREE_STATEMENT_SOURCE_SH_SZ", bundle_success_ratio=round(sh_sz_ratio, 6))
    source_decision(
        decisions,
        "EASTMONEY_BSE_PERIODIC_STATEMENTS",
        "REJECTED_EMPTY_STRUCTURED_ROUTE; BSE_QUARANTINED_FOR_FMDL3B_OFFICIAL_DOCUMENT_EXTRACTION",
        measured_bundle_success_ratio=round(base.statement_bundle_ratio(rows, "EASTMONEY_BSE_PERIODIC_STATEMENTS"), 6),
    )
    source_decision(decisions, "SINA_STATEMENTS", "FALLBACK_STRUCTURED_THREE_STATEMENT_SOURCE_SH_SZ", bundle_success_ratio=round(fallback_statement_ratio, 6))
    source_decision(
        decisions,
        "XUEQIU_CURRENT_VALUATION",
        "PRIMARY_CURRENT_MARKET_CAP_PE_PB_SHARE_COUNT_SOURCE" if valuation_coverage >= policy["minimum_current_valuation_sample_coverage"] else "REMEDIATION_REQUIRED",
        sample_coverage_ratio=round(valuation_coverage, 6),
        denominator_policy="RAW_ONLY; FMDL3D_RECOMPUTES_VALIDITY",
    )
    source_decision(
        decisions,
        "EASTMONEY_CURRENT_VALUATION",
        "REJECTED_GITHUB_RUNNER_UNSTABLE_ROUTE; EVIDENCE_ONLY",
        prior_evidence="aggregate and split-market endpoints repeatedly disconnected",
    )
    for source_id, accepted_label in [
        ("EASTMONEY_FINANCIAL_INDICATORS", "CROSS_CHECK_AND_FACTOR_SUPPORT_ONLY"),
        ("EASTMONEY_HISTORICAL_VALUATION", "CONDITIONAL_HISTORICAL_VALUATION_SOURCE_SH_SZ"),
        ("EASTMONEY_SHARE_CAPITAL", "PRIMARY_HISTORICAL_SHARE_CAPITAL_SOURCE_SH_SZ; BSE_GAP_VISIBLE"),
        ("EASTMONEY_DIVIDENDS", "PRIMARY_DIVIDEND_EVENT_SOURCE_SH_SZ; BSE_GAP_VISIBLE"),
    ]:
        ratio = extended_ratios[source_id]
        source_decision(
            decisions,
            source_id,
            accepted_label if ratio >= policy["minimum_extended_source_success_ratio"] else "SUPPORT_ONLY_OR_REMEDIATION_REQUIRED",
            success_ratio=round(ratio, 6),
        )
    source_decision(
        decisions,
        "EASTMONEY_BUYBACKS",
        "PRIMARY_BUYBACK_EVENT_SOURCE" if buyback_ratio >= 1.0 else "DEGRADED_OR_REMEDIATION_REQUIRED",
        success_ratio=round(buyback_ratio, 6),
    )

    controlled_limitations = [
        "BSE_STRUCTURED_THREE_STATEMENT_SOURCE_UNAVAILABLE_IN_TESTED_FREE_ROUTES; TWO_BSE_SAMPLES_CONTROLLED_QUARANTINE",
        "FMDL3B_MUST_BUILD_CNINFO_OFFICIAL_DOCUMENT_EXTRACTION_FOR_BSE_BEFORE_BSE_FACTOR_ELIGIBILITY",
        "EASTMONEY_CURRENT_VALUATION_REJECTED_ON_GITHUB_RUNNER; XUEQIU_PER_SYMBOL_ROUTE_SELECTED",
        "CURRENT_PROVIDER_PE_PB_ARE_RAW_CROSS_CHECKS; DENOMINATOR_VALIDITY_IS_RECOMPUTED_IN_FMDL3D",
        "DAILY_POINT_IN_TIME_RESOLUTION_ONLY; NO_INTRADAY_FINANCIAL_FACTOR_AUTHORITY",
    ]
    for source_id, ratio in extended_ratios.items():
        if ratio < policy["minimum_extended_source_success_ratio"]:
            controlled_limitations.append(f"{source_id}_BELOW_THRESHOLD:{ratio:.4f}")

    accepted = not hard_failures
    return {
        "decision_version": "1.2.0",
        "run_id": run_id,
        "generated_at": base.now().isoformat(timespec="seconds"),
        "program_id": "FMDL-3A",
        "status": "FMDL3A_ACCEPTED_SOURCE_ROUTE_AND_COVERAGE_GATES_FROZEN" if accepted else "FMDL3A_REMEDIATION_REQUIRED",
        "exit_gate": "SOURCE_ROUTE_AND_NUMERIC_COVERAGE_GATES_FROZEN" if accepted else "NOT_MET",
        "measured_metrics": {
            "sample_symbol_count": len(support_map),
            "official_disclosure_call_success_ratio": round(official_ratio, 6),
            "fallback_notice_call_success_ratio": round(fallback_notice_ratio, 6),
            "sh_sz_primary_statement_bundle_success_ratio": round(sh_sz_ratio, 6),
            "fallback_statement_bundle_success_ratio": round(fallback_statement_ratio, 6),
            "supported_universe_statement_bundle_success_ratio": round(supported_universe_ratio, 6),
            "full_sample_statement_quarantine_ratio": round(quarantine_ratio, 6),
            "supported_symbol_count": int(supported.sum()),
            "quarantined_symbol_count": int(quarantined.sum()),
            "blocked_symbol_count": int(blocked.sum()),
            "all_symbols_supported_or_quarantined": all_supported_or_quarantined,
            "bse_official_document_source_ratio": round(bse_document_ratio, 6),
            "official_point_in_time_match_ratio": round(official_pit_ratio, 6),
            "current_valuation_sample_coverage_ratio": round(valuation_coverage, 6),
            "future_information_count": future_count,
            "extended_source_success_ratios": extended_ratios,
            "buyback_source_success_ratio": round(buyback_ratio, 6),
        },
        "frozen_numeric_gates": policy,
        "frozen_point_in_time_contract": {
            "resolution": "DAILY",
            "report_period_end_is_not_availability": True,
            "primary_availability_source": "CNINFO_OFFICIAL_DISCLOSURE",
            "date_only_rule": "NEXT_TRADING_SESSION_OPEN",
            "timestamp_rule": "NEXT_TRADING_SESSION_OPEN",
            "market_open_time": config["availability_policy"]["market_open_time"],
            "calendar_source": config["availability_policy"]["calendar_source"],
            "restatement_rule": "NEW_REVISION_SEQUENCE; ZERO_SILENT_OVERWRITE",
            "bse_statement_policy": "CONTROLLED_QUARANTINE_UNTIL_CNINFO_DOCUMENT_EXTRACTION_IN_FMDL3B",
        },
        "source_decisions": decisions,
        "hard_failures": hard_failures,
        "controlled_limitations": controlled_limitations,
        "authority": config["authority"],
        "trade_authority": config["trade_authority"],
        "next_phase": "FMDL-3B" if accepted else "FMDL-3A-R",
    }


def write_outputs(
    config: dict[str, Any],
    run_id: str,
    rows: pd.DataFrame,
    summary: pd.DataFrame,
    coverage: pd.DataFrame,
    pit: pd.DataFrame,
    support_map: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    root = ROOT / config["publication"]["candidate_root"]
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    outputs = {
        "FMDL3A_BENCHMARK_ROWS.csv": rows,
        "FMDL3A_SOURCE_SUMMARY.csv": summary,
        "FMDL3A_COVERAGE_MAP.csv": coverage,
        "FMDL3A_POINT_IN_TIME_EVIDENCE.csv": pit,
        "FMDL3A_SUPPORT_QUARANTINE_MAP.csv": support_map,
        "FMDL3_SOURCE_INDEX.csv": pd.DataFrame(decision["source_decisions"]),
    }
    for filename, frame in outputs.items():
        frame.assign(
            run_id=run_id,
            authority=decision["authority"],
            trade_authority=decision["trade_authority"],
        ).to_csv(root / filename, index=False)
    dump(root / "FMDL3A_SOURCE_DECISION.json", decision)
    manifest = {
        "manifest_version": "1.2.0",
        "run_id": run_id,
        "generated_at": base.now().isoformat(timespec="seconds"),
        "program_id": "FMDL-3A",
        "status": "CANDIDATE",
        "decision_status": decision["status"],
        "files": {},
        "authority": decision["authority"],
        "trade_authority": decision["trade_authority"],
    }
    for path in root.iterdir():
        manifest["files"][path.name] = {
            "path": str(path.relative_to(ROOT)),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    dump(root / "FMDL3A_MANIFEST.json", manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CFG)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    run_id = f"FMDL3A_{base.now().strftime('%Y%m%dT%H%M%S%z')}"
    samples = config["sample_design"]["symbols"]

    trading_dates, calendar_row = base.benchmark_calendar(run_id)
    all_rows: list[dict[str, Any]] = [calendar_row]
    all_rows.extend(benchmark_global_sources(samples, run_id))
    bse_rows, _ = base.benchmark_bse_statements(samples, config, run_id)
    all_rows.extend(bse_rows)
    filings: list[dict[str, Any]] = []
    period_map: dict[str, set[str]] = {}

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(base.benchmark_symbol, sample, config, run_id): sample for sample in samples}
        for future in as_completed(futures):
            sample = futures[future]
            try:
                rows, sample_filings, periods = future.result()
                all_rows.extend(rows)
                filings.extend(sample_filings)
                if sample["board"] != "BSE":
                    period_map[sample["symbol"]] = periods
            except Exception as exc:
                result = ("ERROR", pd.DataFrame(), 1, 0.0, type(exc).__name__, str(exc))
                all_rows.append(
                    base.benchmark_row(
                        run_id,
                        sample,
                        "EASTMONEY_STATEMENTS",
                        "SYMBOL_BENCHMARK_UNHANDLED_FAILURE",
                        "benchmark_symbol",
                        result,
                    )
                )
                period_map.setdefault(sample["symbol"], set())

    # BSE PIT is anchored to official periodic filings even while statement values remain quarantined.
    minimum_period = config["benchmark_window"]["minimum_report_period_end"]
    for sample in samples:
        if sample["board"] == "BSE":
            period_map[sample["symbol"]] = {
                filing["report_period_end"]
                for filing in filings
                if filing["symbol"] == sample["symbol"]
                and filing["source_id"] == "CNINFO_OFFICIAL_DISCLOSURE"
                and filing["report_period_end"] >= minimum_period
            }

    rows_frame = pd.DataFrame(all_rows).sort_values(["source_id", "symbol", "component"])
    summary_frame = base.build_summary(rows_frame)
    coverage_frame = base.build_coverage(rows_frame)
    pit_frame = base.build_pit_table(samples, filings, period_map, trading_dates, config, run_id)
    support_map = build_support_quarantine_map(samples, rows_frame)
    decision = build_decision(
        config,
        rows_frame,
        summary_frame,
        pit_frame,
        trading_dates,
        support_map,
        run_id,
    )
    write_outputs(
        config,
        run_id,
        rows_frame,
        summary_frame,
        coverage_frame,
        pit_frame,
        support_map,
        decision,
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not decision["hard_failures"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
