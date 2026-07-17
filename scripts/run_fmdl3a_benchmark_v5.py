from __future__ import annotations

import argparse
import copy
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd

from scripts import run_fmdl3a_benchmark_v2 as base
from scripts import run_fmdl3a_benchmark_v3 as final
from scripts import run_fmdl3a_benchmark_v4 as fast

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/fmdl3a_benchmark.json"

clean_title = final.clean_title
parse_period = final.parse_period
next_trading_open = final.next_trading_open

base.META["EASTMONEY_INDIVIDUAL_INFO"] = (
    "VALUATION_AND_CAPITALIZATION",
    "MARKET_DATA_PROVIDER_FOR_MARKET_NUMERATORS",
)
base.META["XUEQIU_CURRENT_VALUATION"] = (
    "VALUATION_AND_CAPITALIZATION",
    "REJECTED_GITHUB_RUNNER_ROUTE",
)


def normalized_code(value: Any) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6)


def benchmark_one_capitalization(sample: dict[str, Any], run_id: str) -> tuple[dict[str, Any], bool]:
    result = base.invoke(
        ak.stock_individual_info_em,
        {"symbol": base.code(sample["symbol"]), "timeout": 20},
        tries=2,
    )
    row = base.benchmark_row(
        run_id,
        sample,
        "EASTMONEY_INDIVIDUAL_INFO",
        "CURRENT_PRICE_MARKET_CAP_AND_SHARE_COUNT",
        "akshare.stock_individual_info_em",
        result,
    )
    frame = result[1]
    item_col = base.find_col(frame, ["item"])
    value_col = base.find_col(frame, ["value"])
    values: dict[str, Any] = {}
    if item_col and value_col:
        values = dict(zip(frame[item_col].astype(str), frame[value_col]))
    required_items = ["股票代码", "最新", "总市值", "流通市值", "总股本", "流通股"]
    required_hits = sum(item in values for item in required_items)
    non_missing_hits = sum(
        item in values and pd.notna(values[item]) and str(values[item]).strip() not in {"", "-", "None", "nan"}
        for item in required_items
    )
    code_matches = "股票代码" in values and normalized_code(values["股票代码"]) == base.code(sample["symbol"])
    row["required_field_hits"] = required_hits
    row["required_field_total"] = len(required_items)
    row["sample_value_coverage_ratio"] = non_missing_hits / len(required_items)
    row["identity_code_matches"] = code_matches
    row["temporal_fields_present"] = "LATEST_SNAPSHOT_RETRIEVED_AT"
    usable = result[0] == "SUCCESS" and required_hits == len(required_items) and non_missing_hits == len(required_items) and code_matches
    row["status"] = "SUCCESS" if usable else ("PARTIAL" if result[0] == "SUCCESS" else result[0])
    row["record_quality"] = "VALID" if usable else ("PARTIAL" if result[0] == "SUCCESS" else "INVALID")
    return row, usable


def benchmark_capitalization_parallel(samples: list[dict[str, Any]], run_id: str, workers: int = 6) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    successful = 0
    elapsed = 0.0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(benchmark_one_capitalization, sample, run_id): sample for sample in samples}
        for future in as_completed(futures):
            row, usable = future.result()
            rows.append(row)
            successful += int(usable)
            elapsed += float(row.get("elapsed_seconds") or 0.0)
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
        "EASTMONEY_INDIVIDUAL_INFO",
        "SAMPLE_CURRENT_CAPITALIZATION_BUNDLE",
        "parallel per-symbol current market-numerator route",
        bundle_result,
    )
    bundle["row_count"] = successful
    bundle["required_field_hits"] = successful
    bundle["required_field_total"] = len(samples)
    bundle["sample_value_coverage_ratio"] = coverage
    bundle["record_quality"] = "VALID" if coverage == 1.0 else "PARTIAL"
    rows.append(bundle)
    return rows


def rejected_xueqiu_row(run_id: str) -> dict[str, Any]:
    result = (
        "REJECTED",
        pd.DataFrame(),
        1,
        0.0,
        "REJECTED_RESPONSE_SCHEMA",
        "Rejected after 13/13 GitHub-hosted calls returned missing data payload or remote disconnect in run 29595601272.",
    )
    return base.benchmark_row(
        run_id,
        None,
        "XUEQIU_CURRENT_VALUATION",
        "REJECTED_ROUTE_EVIDENCE",
        "akshare.stock_individual_spot_xq",
        result,
    )


def benchmark_global_sources(samples: list[dict[str, Any]], run_id: str, workers: int) -> list[dict[str, Any]]:
    rows = benchmark_capitalization_parallel(samples, run_id, workers=max(4, workers * 2))
    rows.append(rejected_xueqiu_row(run_id))
    rows.append(final.rejected_eastmoney_valuation_row(run_id))
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


def build_decision(
    config: dict[str, Any],
    rows: pd.DataFrame,
    summary: pd.DataFrame,
    pit: pd.DataFrame,
    trading_dates: list,
    support_map: pd.DataFrame,
    run_id: str,
) -> dict[str, Any]:
    supported_symbols = set(support_map.loc[support_map["statement_status"] == "SUPPORTED", "symbol"].astype(str))
    capital_rows = rows[
        (rows["source_id"] == "EASTMONEY_INDIVIDUAL_INFO")
        & (rows["component"] == "CURRENT_PRICE_MARKET_CAP_AND_SHARE_COUNT")
        & (rows["symbol"].isin(supported_symbols))
    ]
    successful_capital_symbols = set(capital_rows.loc[capital_rows["status"] == "SUCCESS", "symbol"].astype(str))
    supported_capital_coverage = len(successful_capital_symbols) / len(supported_symbols) if supported_symbols else 0.0
    full_capital_rows = rows[
        (rows["source_id"] == "EASTMONEY_INDIVIDUAL_INFO")
        & (rows["component"] == "CURRENT_PRICE_MARKET_CAP_AND_SHARE_COUNT")
    ]
    full_capital_coverage = float(full_capital_rows["status"].eq("SUCCESS").mean()) if len(full_capital_rows) else 0.0

    shadow_config = copy.deepcopy(config)
    shadow_policy = shadow_config["acceptance_policy"]
    shadow_policy["minimum_current_valuation_sample_coverage"] = shadow_policy.pop(
        "minimum_supported_universe_current_capitalization_coverage"
    )
    shadow_rows = rows.copy()
    shadow_rows.loc[shadow_rows["source_id"] == "EASTMONEY_INDIVIDUAL_INFO", "source_id"] = "XUEQIU_CURRENT_VALUATION"
    shadow_rows.loc[
        (shadow_rows["source_id"] == "XUEQIU_CURRENT_VALUATION")
        & (shadow_rows["component"] == "SAMPLE_CURRENT_CAPITALIZATION_BUNDLE"),
        "component",
    ] = "SAMPLE_CURRENT_VALUATION_BUNDLE"
    shadow_bundle = shadow_rows[
        (shadow_rows["source_id"] == "XUEQIU_CURRENT_VALUATION")
        & (shadow_rows["component"] == "SAMPLE_CURRENT_VALUATION_BUNDLE")
    ]
    if len(shadow_bundle):
        shadow_rows.loc[shadow_bundle.index, "sample_value_coverage_ratio"] = supported_capital_coverage
    shadow_summary = summary.copy()
    shadow_summary.loc[shadow_summary["source_id"] == "EASTMONEY_INDIVIDUAL_INFO", "source_id"] = "XUEQIU_CURRENT_VALUATION"

    decision = final.build_decision(
        shadow_config,
        shadow_rows,
        shadow_summary,
        pit,
        trading_dates,
        support_map,
        run_id,
    )
    transformed: list[dict[str, Any]] = []
    for item in decision["source_decisions"]:
        if item["source_id"] == "XUEQIU_CURRENT_VALUATION":
            transformed.append(
                {
                    "source_id": "EASTMONEY_INDIVIDUAL_INFO",
                    "decision": "PRIMARY_CURRENT_PRICE_MARKET_CAP_AND_SHARE_COUNT_SOURCE_SUPPORTED_UNIVERSE"
                    if supported_capital_coverage >= config["acceptance_policy"]["minimum_supported_universe_current_capitalization_coverage"]
                    else "REMEDIATION_REQUIRED",
                    "supported_universe_coverage_ratio": round(supported_capital_coverage, 6),
                    "full_sample_coverage_ratio": round(full_capital_coverage, 6),
                    "valuation_ratio_policy": "PROVIDER_PE_PB_SUPPORT_ONLY; RECOMPUTE_DECISION_GRADE_RATIOS_IN_FMDL3D",
                }
            )
        else:
            transformed.append(item)
    transformed.append(
        {
            "source_id": "XUEQIU_CURRENT_VALUATION",
            "decision": "REJECTED_GITHUB_RUNNER_RESPONSE_ROUTE; EVIDENCE_ONLY",
            "prior_evidence": "13/13 failed in run 29595601272",
        }
    )
    decision["source_decisions"] = transformed
    decision["decision_version"] = "1.3.0"
    decision["frozen_numeric_gates"] = config["acceptance_policy"]
    decision["valuation_semantics"] = config["valuation_semantics"]
    decision["measured_metrics"].pop("current_valuation_sample_coverage_ratio", None)
    decision["measured_metrics"]["supported_universe_current_capitalization_coverage_ratio"] = round(supported_capital_coverage, 6)
    decision["measured_metrics"]["full_sample_current_capitalization_coverage_ratio"] = round(full_capital_coverage, 6)
    decision["controlled_limitations"] = [
        value.replace(
            "EASTMONEY_CURRENT_VALUATION_REJECTED_ON_GITHUB_RUNNER; XUEQIU_PER_SYMBOL_ROUTE_SELECTED",
            "EASTMONEY_AGGREGATE_AND_XUEQIU_ROUTES_REJECTED; EASTMONEY_PER_SYMBOL_CAPITALIZATION_ROUTE_SELECTED",
        )
        for value in decision["controlled_limitations"]
    ]
    decision["controlled_limitations"].append(
        "PROVIDER_SUPPLIED_PE_PB_NOT_DECISION_GRADE; FMDL3D_RECOMPUTES_USING_POINT_IN_TIME_DENOMINATORS"
    )
    return decision


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
    all_rows.extend(benchmark_global_sources(samples, run_id, args.workers))
    all_rows.extend(fast.rejected_bse_statement_rows(samples, run_id))
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
    support_map = final.build_support_quarantine_map(samples, rows_frame)
    decision = build_decision(
        config,
        rows_frame,
        summary_frame,
        pit_frame,
        trading_dates,
        support_map,
        run_id,
    )
    final.write_outputs(
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
