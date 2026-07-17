from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd

from scripts import run_fmdl3a_benchmark_v2 as base
from scripts import run_fmdl3a_benchmark_v3 as final

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/fmdl3a_benchmark.json"

clean_title = final.clean_title
parse_period = final.parse_period
next_trading_open = final.next_trading_open

base.META["XUEQIU_CURRENT_VALUATION"] = (
    "VALUATION_AND_CAPITALIZATION",
    "MARKET_DATA_PROVIDER_FOR_MARKET_NUMERATORS",
)


def benchmark_one_xueqiu(sample: dict[str, Any], run_id: str) -> tuple[dict[str, Any], bool]:
    result = base.invoke(
        ak.stock_individual_spot_xq,
        {"symbol": final.xueqiu_symbol(sample["symbol"]), "timeout": 20},
        tries=2,
    )
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
    required_items = {"代码", "现价", "资产净值/总市值", "流通值", "市净率", "基金份额/总股本"}
    optional_items = {"市盈率(TTM)", "市盈率(动)", "市盈率(静)", "市销率", "每股收益"}
    required_hits = len(required_items & observed)
    row["required_field_hits"] = required_hits
    row["required_field_total"] = len(required_items)
    row["sample_value_coverage_ratio"] = required_hits / len(required_items)
    row["temporal_fields_present"] = "时间" if "时间" in observed else ""
    row["valuation_optional_field_hits"] = len(optional_items & observed)
    row["has_current_value_column"] = bool(value_col)
    usable = result[0] == "SUCCESS" and required_hits == len(required_items) and bool(value_col)
    row["status"] = "SUCCESS" if usable else ("PARTIAL" if result[0] == "SUCCESS" else result[0])
    row["record_quality"] = "VALID" if usable else ("PARTIAL" if result[0] == "SUCCESS" else "INVALID")
    return row, usable


def benchmark_xueqiu_parallel(samples: list[dict[str, Any]], run_id: str, workers: int = 6) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    successful = 0
    elapsed = 0.0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(benchmark_one_xueqiu, sample, run_id): sample for sample in samples}
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
        "XUEQIU_CURRENT_VALUATION",
        "SAMPLE_CURRENT_VALUATION_BUNDLE",
        "parallel per-symbol SH/SZ/BJ Xueqiu route",
        bundle_result,
    )
    bundle["row_count"] = successful
    bundle["required_field_hits"] = successful
    bundle["required_field_total"] = len(samples)
    bundle["sample_value_coverage_ratio"] = coverage
    bundle["record_quality"] = "VALID" if coverage == 1.0 else "PARTIAL"
    rows.append(bundle)
    return rows


def rejected_bse_statement_rows(samples: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    evidence = (
        "REJECTED",
        pd.DataFrame(),
        1,
        0.0,
        "REPEATED_EMPTY_ROUTE",
        "Rejected after real benchmark runs 29592790195 and 29590857424 returned no usable BSE three-statement bundle from tested free structured routes.",
    )
    for sample in [item for item in samples if item["board"] == "BSE"]:
        route_row = base.benchmark_row(
            run_id,
            sample,
            "EASTMONEY_BSE_PERIODIC_STATEMENTS",
            "REJECTED_ROUTE_EVIDENCE",
            "prior GitHub-hosted real benchmark evidence",
            evidence,
        )
        route_row["record_quality"] = "INVALID"
        rows.append(route_row)
        bundle_result = (
            "ERROR",
            pd.DataFrame(),
            1,
            0.0,
            "STRUCTURED_ROUTE_REJECTED",
            "BSE requires official CNINFO document extraction in FMDL-3B.",
        )
        bundle = base.benchmark_row(
            run_id,
            sample,
            "EASTMONEY_BSE_PERIODIC_STATEMENTS",
            "THREE_STATEMENT_BUNDLE",
            "rejected BSE structured route",
            bundle_result,
        )
        bundle["required_field_hits"] = 0
        bundle["required_field_total"] = 3
        bundle["sample_value_coverage_ratio"] = 0.0
        bundle["record_quality"] = "INVALID"
        rows.append(bundle)
    return rows


def benchmark_global_sources(samples: list[dict[str, Any]], run_id: str, workers: int) -> list[dict[str, Any]]:
    rows = benchmark_xueqiu_parallel(samples, run_id, workers=max(4, workers * 2))
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
    all_rows.extend(rejected_bse_statement_rows(samples, run_id))
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
    decision = final.build_decision(
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
