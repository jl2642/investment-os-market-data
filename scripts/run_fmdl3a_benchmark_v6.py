from __future__ import annotations

import argparse
import copy
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
from scripts import run_fmdl3a_benchmark_v3 as final
from scripts import run_fmdl3a_benchmark_v4 as fast

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/fmdl3a_benchmark.json"
SNAPSHOT = ROOT / "outputs/current/DAILY_MARKET_SNAPSHOT.csv"

clean_title = final.clean_title
parse_period = final.parse_period
next_trading_open = final.next_trading_open

base.META.update(
    {
        "FMDL1_ACCEPTED_CURRENT_PRICE": ("VALUATION_AND_CAPITALIZATION", "ACCEPTED_INTERNAL_CURRENT"),
        "EASTMONEY_EFFECTIVE_SHARE_CAPITAL": ("SHARE_CAPITAL", "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"),
        "COMPOSITE_CURRENT_CAPITALIZATION": ("VALUATION_AND_CAPITALIZATION", "DERIVED_CALCULATION"),
        "EASTMONEY_INDIVIDUAL_INFO": ("VALUATION_AND_CAPITALIZATION", "REJECTED_GITHUB_RUNNER_ROUTE"),
        "XUEQIU_CURRENT_VALUATION": ("VALUATION_AND_CAPITALIZATION", "REJECTED_GITHUB_RUNNER_ROUTE"),
    }
)


def dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejected_route_row(run_id: str, source_id: str, error_type: str, message: str, adapter: str) -> dict[str, Any]:
    result = ("REJECTED", pd.DataFrame(), 1, 0.0, error_type, message)
    return base.benchmark_row(run_id, None, source_id, "REJECTED_ROUTE_EVIDENCE", adapter, result)


def load_accepted_prices(samples: list[dict[str, Any]], run_id: str):
    frame = pd.read_csv(SNAPSHOT, encoding="utf-8-sig")
    frame["symbol"] = frame["symbol"].astype(str)
    sample_map = {sample["symbol"]: sample for sample in samples if sample["board"] != "BSE"}
    rows: list[dict[str, Any]] = []
    evidence: dict[str, dict[str, Any]] = {}
    for symbol, sample in sample_map.items():
        selected = frame[frame["symbol"] == symbol].copy()
        usable = False
        if len(selected) == 1:
            record = selected.iloc[0]
            close = pd.to_numeric(pd.Series([record.get("close")]), errors="coerce").iloc[0]
            as_of = pd.to_datetime(record.get("as_of_date"), errors="coerce")
            usable = bool(pd.notna(close) and float(close) > 0 and pd.notna(as_of) and str(record.get("record_quality")) == "VALID")
            if usable:
                evidence[symbol] = {
                    "price_as_of_date": as_of.date().isoformat(),
                    "close": float(close),
                    "price_source_id": "FMDL1_ACCEPTED_CURRENT_PRICE",
                    "price_source_path": "outputs/current/DAILY_MARKET_SNAPSHOT.csv",
                    "price_source_timestamp": record.get("source_timestamp"),
                    "price_row_hash": record.get("row_hash"),
                }
        result = (
            "SUCCESS" if usable else ("EMPTY" if selected.empty else "ERROR"),
            selected,
            1,
            0.0,
            None if usable else "PRICE_CURRENT_INVALID",
            None if usable else "Expected exactly one VALID positive-close row in accepted FMDL-1 Current.",
        )
        row = base.benchmark_row(
            run_id,
            sample,
            "FMDL1_ACCEPTED_CURRENT_PRICE",
            "LATEST_COMPLETED_SESSION_CLOSE",
            "outputs/current/DAILY_MARKET_SNAPSHOT.csv",
            result,
        )
        row["required_field_hits"] = 5 if usable else 0
        row["required_field_total"] = 5
        row["sample_value_coverage_ratio"] = 1.0 if usable else 0.0
        row["has_report_date"] = usable
        row["latest_report_period"] = evidence.get(symbol, {}).get("price_as_of_date")
        row["earliest_report_period"] = evidence.get(symbol, {}).get("price_as_of_date")
        row["temporal_fields_present"] = "as_of_date|source_timestamp"
        row["record_quality"] = "VALID" if usable else "INVALID"
        rows.append(row)
    coverage = len(evidence) / len(sample_map) if sample_map else 0.0
    bundle_result = (
        "SUCCESS" if coverage > 0 else "ERROR",
        pd.DataFrame({"symbol": list(sample_map)}),
        1,
        0.0,
        None,
        None,
    )
    bundle = base.benchmark_row(
        run_id,
        None,
        "FMDL1_ACCEPTED_CURRENT_PRICE",
        "SUPPORTED_UNIVERSE_PRICE_BUNDLE",
        "accepted FMDL-1 Current",
        bundle_result,
    )
    bundle["row_count"] = len(evidence)
    bundle["required_field_hits"] = len(evidence)
    bundle["required_field_total"] = len(sample_map)
    bundle["sample_value_coverage_ratio"] = coverage
    bundle["record_quality"] = "VALID" if coverage == 1.0 else "PARTIAL"
    rows.append(bundle)
    return rows, evidence


def benchmark_one_effective_share(sample: dict[str, Any], price: dict[str, Any], run_id: str):
    result = base.invoke(ak.stock_zh_a_gbjg_em, {"symbol": sample["symbol"]}, tries=2)
    frame = result[1]
    usable = False
    evidence: dict[str, Any] | None = None
    date_col = base.find_col(frame, ["变更日期"])
    total_col = base.find_col(frame, ["总股本"])
    float_col = base.find_col(frame, ["已上市流通A股", "已流通股份"])
    eligible = pd.DataFrame()
    if len(frame) and date_col and total_col and float_col:
        prepared = frame.copy()
        prepared["__effective_date"] = pd.to_datetime(prepared[date_col], errors="coerce")
        prepared["__total_shares"] = pd.to_numeric(prepared[total_col], errors="coerce")
        prepared["__float_shares"] = pd.to_numeric(prepared[float_col], errors="coerce")
        price_as_of = pd.Timestamp(price["price_as_of_date"])
        eligible = prepared[
            prepared["__effective_date"].notna()
            & (prepared["__effective_date"] <= price_as_of)
            & (prepared["__total_shares"] > 0)
            & (prepared["__float_shares"] > 0)
        ].sort_values("__effective_date")
        if len(eligible):
            latest = eligible.iloc[-1]
            usable = True
            evidence = {
                "symbol": sample["symbol"],
                "name": sample["name"],
                "profile": sample["profile"],
                "board": sample["board"],
                **price,
                "share_effective_date": latest["__effective_date"].date().isoformat(),
                "total_shares": float(latest["__total_shares"]),
                "float_a_shares": float(latest["__float_shares"]),
                "share_source_id": "EASTMONEY_EFFECTIVE_SHARE_CAPITAL",
                "share_source_adapter": "akshare.stock_zh_a_gbjg_em",
                "future_effective_share_flag": bool(latest["__effective_date"] > price_as_of),
            }
            evidence["total_market_cap_cny"] = evidence["close"] * evidence["total_shares"]
            evidence["float_market_cap_cny"] = evidence["close"] * evidence["float_a_shares"]
            evidence["capitalization_source_id"] = "COMPOSITE_CURRENT_CAPITALIZATION"
            evidence["calculation_formula"] = "close*effective_share_count"
    row_result = (
        "SUCCESS" if usable else result[0],
        eligible.tail(1) if usable else frame,
        result[2],
        result[3],
        None if usable else (result[4] or "NO_PIT_EFFECTIVE_SHARE_ROW"),
        None if usable else (result[5] or "No positive share-count row effective not later than accepted price as-of date."),
    )
    row = base.benchmark_row(
        run_id,
        sample,
        "EASTMONEY_EFFECTIVE_SHARE_CAPITAL",
        "PIT_EFFECTIVE_TOTAL_AND_FLOAT_A_SHARES",
        "akshare.stock_zh_a_gbjg_em",
        row_result,
    )
    row["required_field_hits"] = 3 if usable else 0
    row["required_field_total"] = 3
    row["sample_value_coverage_ratio"] = 1.0 if usable else 0.0
    row["has_report_date"] = usable
    row["latest_report_period"] = evidence.get("share_effective_date") if evidence else None
    row["earliest_report_period"] = evidence.get("share_effective_date") if evidence else None
    row["temporal_fields_present"] = "变更日期|price_as_of_date"
    row["record_quality"] = "VALID" if usable else "INVALID"
    return row, evidence


def benchmark_composite_capitalization(samples: list[dict[str, Any]], run_id: str, workers: int):
    supported_samples = [sample for sample in samples if sample["board"] != "BSE"]
    price_rows, prices = load_accepted_prices(samples, run_id)
    share_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(benchmark_one_effective_share, sample, prices[sample["symbol"]], run_id): sample
            for sample in supported_samples
            if sample["symbol"] in prices
        }
        for future in as_completed(futures):
            row, evidence = future.result()
            share_rows.append(row)
            if evidence:
                evidence_rows.append(evidence)
    evidence_frame = pd.DataFrame(evidence_rows)
    derived_rows: list[dict[str, Any]] = []
    for sample in supported_samples:
        selected = evidence_frame[evidence_frame["symbol"] == sample["symbol"]] if not evidence_frame.empty else pd.DataFrame()
        usable = bool(
            len(selected) == 1
            and float(selected.iloc[0]["total_market_cap_cny"]) > 0
            and float(selected.iloc[0]["float_market_cap_cny"]) > 0
            and not bool(selected.iloc[0]["future_effective_share_flag"])
        )
        result = (
            "SUCCESS" if usable else "ERROR",
            selected,
            1,
            0.0,
            None if usable else "CAPITALIZATION_DERIVATION_FAILED",
            None if usable else "Missing accepted price or PIT-effective positive share counts.",
        )
        row = base.benchmark_row(
            run_id,
            sample,
            "COMPOSITE_CURRENT_CAPITALIZATION",
            "DERIVED_TOTAL_AND_FLOAT_MARKET_CAP",
            "FMDL1 close * PIT-effective share count",
            result,
        )
        row["required_field_hits"] = 7 if usable else 0
        row["required_field_total"] = 7
        row["sample_value_coverage_ratio"] = 1.0 if usable else 0.0
        row["has_report_date"] = usable
        row["latest_report_period"] = selected.iloc[0]["price_as_of_date"] if usable else None
        row["temporal_fields_present"] = "price_as_of_date|share_effective_date"
        row["record_quality"] = "VALID" if usable else "INVALID"
        derived_rows.append(row)
    coverage = sum(row["status"] == "SUCCESS" for row in derived_rows) / len(supported_samples) if supported_samples else 0.0
    bundle_result = (
        "SUCCESS" if coverage > 0 else "ERROR",
        evidence_frame,
        1,
        0.0,
        None,
        None,
    )
    bundle = base.benchmark_row(
        run_id,
        None,
        "COMPOSITE_CURRENT_CAPITALIZATION",
        "SUPPORTED_UNIVERSE_CURRENT_CAPITALIZATION_BUNDLE",
        "accepted price * PIT-effective shares",
        bundle_result,
    )
    bundle["row_count"] = len(evidence_frame)
    bundle["required_field_hits"] = len(evidence_frame)
    bundle["required_field_total"] = len(supported_samples)
    bundle["sample_value_coverage_ratio"] = coverage
    bundle["record_quality"] = "VALID" if coverage == 1.0 else "PARTIAL"
    derived_rows.append(bundle)
    return price_rows + share_rows + derived_rows, evidence_frame


def benchmark_global_sources(samples: list[dict[str, Any]], run_id: str, workers: int):
    rows, evidence = benchmark_composite_capitalization(samples, run_id, workers)
    rows.extend(
        [
            rejected_route_row(
                run_id,
                "EASTMONEY_INDIVIDUAL_INFO",
                "REPEATED_EMPTY_NON_JSON_ROUTE",
                "Rejected after 13/13 JSONDecodeError responses in run 29596511917.",
                "akshare.stock_individual_info_em",
            ),
            rejected_route_row(
                run_id,
                "XUEQIU_CURRENT_VALUATION",
                "REJECTED_RESPONSE_SCHEMA",
                "Rejected after 13/13 GitHub-hosted calls failed in run 29595601272.",
                "akshare.stock_individual_spot_xq",
            ),
            final.rejected_eastmoney_valuation_row(run_id),
        ]
    )
    result = base.invoke(ak.stock_repurchase_em, tries=3)
    row = base.benchmark_row(run_id, None, "EASTMONEY_BUYBACKS", "FULL_MARKET_BUYBACK_EVENTS", "akshare.stock_repurchase_em", result)
    if len(result[1]):
        expected = ["股票代码", "计划回购金额区间-下限", "已回购股份数量", "已回购金额", "最新公告日期"]
        row["required_field_hits"] = sum(bool(base.find_col(result[1], [name])) for name in expected)
        row["required_field_total"] = len(expected)
        row["sample_value_coverage_ratio"] = row["required_field_hits"] / len(expected)
        row["has_announcement_date"] = bool(base.find_col(result[1], ["最新公告日期"]))
    rows.append(row)
    return rows, evidence


def build_decision(config, rows, summary, pit, trading_dates, support_map, capitalization, run_id):
    policy = config["acceptance_policy"]
    cap_bundle = rows[
        (rows["source_id"] == "COMPOSITE_CURRENT_CAPITALIZATION")
        & (rows["component"] == "SUPPORTED_UNIVERSE_CURRENT_CAPITALIZATION_BUNDLE")
    ]
    cap_coverage = float(cap_bundle["sample_value_coverage_ratio"].iloc[0]) if len(cap_bundle) else 0.0
    future_share_count = int(capitalization.get("future_effective_share_flag", pd.Series(dtype=bool)).fillna(False).astype(bool).sum()) if not capitalization.empty else 0

    shadow_config = copy.deepcopy(config)
    shadow_config["acceptance_policy"]["minimum_current_valuation_sample_coverage"] = shadow_config["acceptance_policy"].pop("minimum_supported_universe_current_capitalization_coverage")
    shadow_config["acceptance_policy"].pop("require_zero_future_effective_share_count", None)
    shadow_rows = rows.copy()
    shadow_rows.loc[shadow_rows["source_id"] == "COMPOSITE_CURRENT_CAPITALIZATION", "source_id"] = "XUEQIU_CURRENT_VALUATION"
    shadow_rows.loc[
        (shadow_rows["source_id"] == "XUEQIU_CURRENT_VALUATION")
        & (shadow_rows["component"] == "SUPPORTED_UNIVERSE_CURRENT_CAPITALIZATION_BUNDLE"),
        "component",
    ] = "SAMPLE_CURRENT_VALUATION_BUNDLE"
    shadow_summary = summary.copy()
    shadow_summary.loc[shadow_summary["source_id"] == "COMPOSITE_CURRENT_CAPITALIZATION", "source_id"] = "XUEQIU_CURRENT_VALUATION"
    decision = final.build_decision(shadow_config, shadow_rows, shadow_summary, pit, trading_dates, support_map, run_id)

    transformed: list[dict[str, Any]] = []
    for item in decision["source_decisions"]:
        if item["source_id"] == "XUEQIU_CURRENT_VALUATION":
            transformed.extend(
                [
                    {
                        "source_id": "FMDL1_ACCEPTED_CURRENT_PRICE",
                        "decision": "PRIMARY_LATEST_COMPLETED_SESSION_CLOSE_SOURCE",
                        "supported_universe_coverage_ratio": round(
                            base.statement_bundle_ratio(rows.rename(columns={"component": "_component"}), "__never__"), 6
                        ) if False else round(float(rows[(rows.source_id == "FMDL1_ACCEPTED_CURRENT_PRICE") & (rows.component == "SUPPORTED_UNIVERSE_PRICE_BUNDLE")]["sample_value_coverage_ratio"].iloc[0]), 6),
                    },
                    {
                        "source_id": "EASTMONEY_EFFECTIVE_SHARE_CAPITAL",
                        "decision": "PRIMARY_PIT_EFFECTIVE_TOTAL_AND_FLOAT_A_SHARE_SOURCE_SUPPORTED_UNIVERSE",
                        "supported_universe_coverage_ratio": round(cap_coverage, 6),
                        "future_effective_share_count": future_share_count,
                    },
                    {
                        "source_id": "COMPOSITE_CURRENT_CAPITALIZATION",
                        "decision": "PRIMARY_DERIVED_TOTAL_AND_FLOAT_MARKET_CAP_SOURCE_SUPPORTED_UNIVERSE" if cap_coverage >= policy["minimum_supported_universe_current_capitalization_coverage"] and future_share_count == 0 else "REMEDIATION_REQUIRED",
                        "supported_universe_coverage_ratio": round(cap_coverage, 6),
                        "calculation_rule": config["valuation_semantics"]["current_capitalization_rule"],
                    },
                ]
            )
        else:
            transformed.append(item)
    transformed.extend(
        [
            {"source_id": "EASTMONEY_INDIVIDUAL_INFO", "decision": "REJECTED_GITHUB_RUNNER_NON_JSON_ROUTE; EVIDENCE_ONLY", "prior_evidence": "13/13 failed in run 29596511917"},
            {"source_id": "XUEQIU_CURRENT_VALUATION", "decision": "REJECTED_GITHUB_RUNNER_RESPONSE_ROUTE; EVIDENCE_ONLY", "prior_evidence": "13/13 failed in run 29595601272"},
        ]
    )
    decision["source_decisions"] = transformed
    decision["decision_version"] = "1.4.0"
    decision["frozen_numeric_gates"] = policy
    decision["valuation_semantics"] = config["valuation_semantics"]
    decision["measured_metrics"].pop("current_valuation_sample_coverage_ratio", None)
    decision["measured_metrics"]["supported_universe_current_capitalization_coverage_ratio"] = round(cap_coverage, 6)
    decision["measured_metrics"]["future_effective_share_count"] = future_share_count
    if future_share_count and "FUTURE_EFFECTIVE_SHARE_COUNT" not in decision["hard_failures"]:
        decision["hard_failures"].append("FUTURE_EFFECTIVE_SHARE_COUNT")
    accepted = not decision["hard_failures"]
    decision["status"] = "FMDL3A_ACCEPTED_SOURCE_ROUTE_AND_COVERAGE_GATES_FROZEN" if accepted else "FMDL3A_REMEDIATION_REQUIRED"
    decision["exit_gate"] = "SOURCE_ROUTE_AND_NUMERIC_COVERAGE_GATES_FROZEN" if accepted else "NOT_MET"
    decision["next_phase"] = "FMDL-3B" if accepted else "FMDL-3A-R"
    decision["controlled_limitations"] = [
        "BSE_STRUCTURED_THREE_STATEMENT_SOURCE_UNAVAILABLE_IN_TESTED_FREE_ROUTES; TWO_BSE_SAMPLES_CONTROLLED_QUARANTINE",
        "FMDL3B_MUST_BUILD_CNINFO_OFFICIAL_DOCUMENT_EXTRACTION_FOR_BSE_BEFORE_BSE_FACTOR_ELIGIBILITY",
        "PUBLIC_REALTIME_VALUATION_ENDPOINTS_REJECTED_ON_GITHUB_RUNNER; CAPITALIZATION_DERIVED_FROM_ACCEPTED_PRICE_AND_PIT_EFFECTIVE_SHARES",
        "PROVIDER_SUPPLIED_PE_PB_NOT_DECISION_GRADE; FMDL3D_RECOMPUTES_USING_POINT_IN_TIME_DENOMINATORS",
        "DAILY_POINT_IN_TIME_RESOLUTION_ONLY; NO_INTRADAY_FINANCIAL_FACTOR_AUTHORITY",
    ]
    return decision


def write_outputs(config, run_id, rows, summary, coverage, pit, support_map, capitalization, decision):
    root = ROOT / config["publication"]["candidate_root"]
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    outputs = {
        "FMDL3A_BENCHMARK_ROWS.csv": rows,
        "FMDL3A_SOURCE_SUMMARY.csv": summary,
        "FMDL3A_COVERAGE_MAP.csv": coverage,
        "FMDL3A_POINT_IN_TIME_EVIDENCE.csv": pit,
        "FMDL3A_SUPPORT_QUARANTINE_MAP.csv": support_map,
        "FMDL3A_CAPITALIZATION_EVIDENCE.csv": capitalization,
        "FMDL3_SOURCE_INDEX.csv": pd.DataFrame(decision["source_decisions"]),
    }
    for filename, frame in outputs.items():
        frame.assign(run_id=run_id, authority=decision["authority"], trade_authority=decision["trade_authority"]).to_csv(root / filename, index=False)
    dump(root / "FMDL3A_SOURCE_DECISION.json", decision)
    manifest = {"manifest_version": "1.4.0", "run_id": run_id, "generated_at": base.now().isoformat(timespec="seconds"), "program_id": "FMDL-3A", "status": "CANDIDATE", "decision_status": decision["status"], "files": {}, "authority": decision["authority"], "trade_authority": decision["trade_authority"]}
    for path in root.iterdir():
        manifest["files"][path.name] = {"path": str(path.relative_to(ROOT)), "size_bytes": path.stat().st_size, "sha256": sha256(path)}
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
    global_rows, capitalization = benchmark_global_sources(samples, run_id, args.workers)
    all_rows.extend(global_rows)
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
                all_rows.append(base.benchmark_row(run_id, sample, "EASTMONEY_STATEMENTS", "SYMBOL_BENCHMARK_UNHANDLED_FAILURE", "benchmark_symbol", result))
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
    decision = build_decision(config, rows_frame, summary_frame, pit_frame, trading_dates, support_map, capitalization, run_id)
    write_outputs(config, run_id, rows_frame, summary_frame, coverage_frame, pit_frame, support_map, capitalization, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not decision["hard_failures"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
