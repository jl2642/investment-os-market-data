from __future__ import annotations

import argparse
import bisect
import hashlib
import html
import json
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/fmdl3a_benchmark.json"
TZ = ZoneInfo("Asia/Shanghai")

STATEMENTS = {
    "BALANCE_SHEET": ("stock_balance_sheet_by_report_em", "资产负债表"),
    "INCOME_STATEMENT": ("stock_profit_sheet_by_report_em", "利润表"),
    "CASH_FLOW_STATEMENT": ("stock_cash_flow_sheet_by_report_em", "现金流量表"),
}
BSE_REPORTS = {
    "BALANCE_SHEET": "RPT_DMSK_FN_BALANCE",
    "INCOME_STATEMENT": "RPT_DMSK_FN_INCOME",
    "CASH_FLOW_STATEMENT": "RPT_DMSK_FN_CASHFLOW",
}
META = {
    "CNINFO_OFFICIAL_DISCLOSURE": ("DISCLOSURE_METADATA", "REGULATORY_OR_EXCHANGE_STRUCTURED_DISCLOSURE"),
    "EASTMONEY_NOTICE_FALLBACK": ("DISCLOSURE_METADATA", "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"),
    "EASTMONEY_STATEMENTS": ("FINANCIAL_STATEMENTS", "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"),
    "EASTMONEY_BSE_PERIODIC_STATEMENTS": ("FINANCIAL_STATEMENTS", "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"),
    "SINA_STATEMENTS": ("FINANCIAL_STATEMENTS", "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"),
    "EASTMONEY_FINANCIAL_INDICATORS": ("FINANCIAL_INDICATORS", "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"),
    "EASTMONEY_CURRENT_VALUATION": ("VALUATION_AND_CAPITALIZATION", "MARKET_DATA_PROVIDER_FOR_MARKET_NUMERATORS"),
    "EASTMONEY_HISTORICAL_VALUATION": ("VALUATION_AND_CAPITALIZATION", "MARKET_DATA_PROVIDER_FOR_MARKET_NUMERATORS"),
    "EASTMONEY_SHARE_CAPITAL": ("SHARE_CAPITAL", "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"),
    "EASTMONEY_DIVIDENDS": ("SHAREHOLDER_RETURN", "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"),
    "EASTMONEY_BUYBACKS": ("SHAREHOLDER_RETURN", "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"),
    "SINA_TRADING_CALENDAR": ("MARKET_CALENDAR", "AUDITABLE_STANDARDIZED_PUBLIC_PROVIDER"),
}


def now() -> datetime:
    return datetime.now(TZ)


def code(symbol: str) -> str:
    return symbol.split(".")[0]


def em_symbol(symbol: str) -> str:
    security_code, exchange = symbol.split(".")
    return f"{exchange}{security_code}"


def sina_symbol(symbol: str) -> str:
    return em_symbol(symbol).lower()


def dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_col(frame: pd.DataFrame, names: list[str]) -> str | None:
    mapping = {str(column).upper(): str(column) for column in frame.columns}
    for name in names:
        if name.upper() in mapping:
            return mapping[name.upper()]
    return None


def invoke(function, kwargs: dict[str, Any] | None = None, tries: int = 2):
    started = time.monotonic()
    error: Exception | None = None
    for attempt in range(1, tries + 1):
        try:
            frame = function(**(kwargs or {}))
            if not isinstance(frame, pd.DataFrame):
                frame = pd.DataFrame(frame)
            status = "SUCCESS" if not frame.empty else "EMPTY"
            return status, frame, attempt, round(time.monotonic() - started, 4), None, None
        except Exception as exc:  # source failures must remain visible
            error = exc
            if attempt < tries:
                time.sleep(1.0 * attempt)
    return "ERROR", pd.DataFrame(), tries, round(time.monotonic() - started, 4), type(error).__name__, str(error)[:1000]


def benchmark_row(run_id: str, sample: dict[str, Any] | None, source_id: str, component: str, adapter: str, result):
    status, frame, attempts, elapsed, error_type, error_message = result
    family, source_rank = META[source_id]
    return {
        "run_id": run_id,
        "symbol": sample["symbol"] if sample else "*",
        "name": sample["name"] if sample else "FULL_MARKET",
        "profile": sample["profile"] if sample else "FULL_MARKET",
        "board": sample["board"] if sample else "FULL_MARKET",
        "source_id": source_id,
        "source_family": family,
        "source_rank": source_rank,
        "adapter": adapter,
        "component": component,
        "status": status,
        "attempts": attempts,
        "row_count": len(frame),
        "column_count": len(frame.columns),
        "elapsed_seconds": elapsed,
        "has_report_date": False,
        "has_announcement_date": False,
        "has_revision_signal": False,
        "latest_report_period": None,
        "earliest_report_period": None,
        "temporal_fields_present": "",
        "required_field_hits": 0,
        "required_field_total": 0,
        "sample_value_coverage_ratio": None,
        "error_type": error_type,
        "error_message": error_message,
        "record_quality": "VALID" if status == "SUCCESS" else ("PARTIAL" if status in {"EMPTY", "PARTIAL"} else "INVALID"),
        "source_retrieved_at": now().isoformat(timespec="seconds"),
    }


def set_temporal(row: dict[str, Any], frame: pd.DataFrame, report_names: list[str], announcement_names: list[str]) -> None:
    report_col = find_col(frame, report_names)
    announcement_cols = [find_col(frame, [name]) for name in announcement_names]
    announcement_cols = [name for name in announcement_cols if name]
    row["has_report_date"] = bool(report_col)
    row["has_announcement_date"] = bool(announcement_cols)
    row["temporal_fields_present"] = "|".join(([report_col] if report_col else []) + announcement_cols)
    if report_col:
        parsed = pd.to_datetime(frame[report_col], errors="coerce").dropna()
        if len(parsed):
            row["earliest_report_period"] = parsed.min().date().isoformat()
            row["latest_report_period"] = parsed.max().date().isoformat()


def report_periods(frame: pd.DataFrame, names: tuple[str, ...] = ("REPORT_DATE", "报告日")) -> set[str]:
    report_col = find_col(frame, list(names))
    if not report_col:
        return set()
    return {value.date().isoformat() for value in pd.to_datetime(frame[report_col], errors="coerce").dropna()}


def clean_title(title: Any) -> str:
    value = html.unescape(str(title))
    value = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", "", value)


def parse_period(title: Any) -> str | None:
    value = clean_title(title)
    if "摘要" in value or "英文版" in value:
        return None
    year_match = re.search(r"(20\d{2})年?", value)
    if not year_match:
        return None
    year = int(year_match.group(1))
    if re.search(r"第一季度报告|一季度报告|第一季报|一季报", value):
        return f"{year}-03-31"
    if re.search(r"半年度报告|半年报|中期报告", value):
        return f"{year}-06-30"
    if re.search(r"第三季度报告|三季度报告|第三季报|三季报", value):
        return f"{year}-09-30"
    if re.search(r"年度报告|年度财务报告|年报", value):
        return f"{year}-12-31"
    return None


def classify_filings(frame: pd.DataFrame, source_id: str, sample: dict[str, Any], title_names: list[str], date_names: list[str], link_names: list[str]) -> list[dict[str, Any]]:
    title_col = find_col(frame, title_names)
    date_col = find_col(frame, date_names)
    link_col = find_col(frame, link_names)
    if not title_col or not date_col:
        return []
    filings: list[dict[str, Any]] = []
    for _, source_row in frame.iterrows():
        raw_title = str(source_row.get(title_col, ""))
        normalized_title = clean_title(raw_title)
        period = parse_period(normalized_title)
        announced = pd.to_datetime(source_row.get(date_col), errors="coerce")
        if not period or pd.isna(announced):
            continue
        filings.append({
            "symbol": sample["symbol"],
            "name": sample["name"],
            "profile": sample["profile"],
            "board": sample["board"],
            "source_id": source_id,
            "report_period_end": period,
            "announcement_timestamp_raw": announced.isoformat(),
            "announcement_date": announced.date().isoformat(),
            "filing_title_raw": raw_title,
            "filing_title": normalized_title,
            "filing_link": str(source_row.get(link_col, "")) if link_col else None,
            "is_revision": bool(re.search(r"更正|修订|更新后|补充", normalized_title)),
        })
    filings.sort(key=lambda item: (item["report_period_end"], item["announcement_timestamp_raw"], item["filing_title"]))
    sequence: dict[str, int] = {}
    for filing in filings:
        period = filing["report_period_end"]
        sequence[period] = sequence.get(period, 0) + 1
        filing["revision_sequence"] = sequence[period]
    return filings


def benchmark_disclosure(sample: dict[str, Any], config: dict[str, Any], run_id: str):
    rows: list[dict[str, Any]] = []
    filings: list[dict[str, Any]] = []
    start = config["benchmark_window"]["announcement_start_date"]
    end = now().strftime("%Y%m%d")
    cninfo = invoke(
        ak.stock_zh_a_disclosure_report_cninfo,
        {"symbol": code(sample["symbol"]), "market": "沪深京", "keyword": "报告", "category": "", "start_date": start, "end_date": end},
        tries=3,
    )
    row = benchmark_row(run_id, sample, "CNINFO_OFFICIAL_DISCLOSURE", "PERIODIC_AND_REVISION_FILINGS", "akshare.stock_zh_a_disclosure_report_cninfo", cninfo)
    if len(cninfo[1]):
        parsed = classify_filings(cninfo[1], "CNINFO_OFFICIAL_DISCLOSURE", sample, ["公告标题"], ["公告时间"], ["公告链接"])
        filings.extend(parsed)
        row["has_announcement_date"] = bool(find_col(cninfo[1], ["公告时间"]))
        row["has_revision_signal"] = any(item["is_revision"] for item in parsed)
        row["required_field_hits"] = sum(bool(find_col(cninfo[1], [name])) for name in ["代码", "公告标题", "公告时间", "公告链接"])
        row["required_field_total"] = 4
        row["sample_value_coverage_ratio"] = row["required_field_hits"] / 4
        row["parsed_periodic_filing_count"] = len(parsed)
    rows.append(row)

    if sample["board"] != "BSE":
        fallback = invoke(
            ak.stock_individual_notice_report,
            {"security": code(sample["symbol"]), "symbol": "财务报告", "begin_date": start, "end_date": end},
            tries=2,
        )
        row = benchmark_row(run_id, sample, "EASTMONEY_NOTICE_FALLBACK", "FINANCIAL_REPORT_NOTICES", "akshare.stock_individual_notice_report", fallback)
        if len(fallback[1]):
            parsed = classify_filings(fallback[1], "EASTMONEY_NOTICE_FALLBACK", sample, ["公告标题"], ["公告日期"], ["网址"])
            filings.extend(parsed)
            row["has_announcement_date"] = bool(find_col(fallback[1], ["公告日期"]))
            row["has_revision_signal"] = any(item["is_revision"] for item in parsed)
            row["required_field_hits"] = sum(bool(find_col(fallback[1], [name])) for name in ["代码", "公告标题", "公告日期", "网址"])
            row["required_field_total"] = 4
            row["sample_value_coverage_ratio"] = row["required_field_hits"] / 4
            row["parsed_periodic_filing_count"] = len(parsed)
        rows.append(row)
    return rows, filings


def benchmark_symbol_statements(sample: dict[str, Any], run_id: str, source_id: str):
    rows: list[dict[str, Any]] = []
    period_sets: list[set[str]] = []
    component_success = 0
    elapsed_total = 0.0
    for component, (eastmoney_function, sina_name) in STATEMENTS.items():
        if source_id == "EASTMONEY_STATEMENTS":
            function = getattr(ak, eastmoney_function)
            kwargs = {"symbol": em_symbol(sample["symbol"])}
            adapter = f"akshare.{eastmoney_function}"
        else:
            function = ak.stock_financial_report_sina
            kwargs = {"stock": sina_symbol(sample["symbol"]), "symbol": sina_name}
            adapter = "akshare.stock_financial_report_sina"
        result = invoke(function, kwargs, tries=2)
        row = benchmark_row(run_id, sample, source_id, component, adapter, result)
        if len(result[1]):
            set_temporal(row, result[1], ["REPORT_DATE", "报告日"], ["NOTICE_DATE", "UPDATE_DATE", "更新日期"])
            period_sets.append(report_periods(result[1]))
            component_success += 1
        else:
            period_sets.append(set())
        elapsed_total += result[3]
        rows.append(row)
    common_periods = set.intersection(*period_sets) if all(period_sets) else set()
    bundle_status = "SUCCESS" if component_success == 3 and common_periods else ("PARTIAL" if component_success else "ERROR")
    bundle_result = (bundle_status, pd.DataFrame({"report_period_end": sorted(common_periods)}), 1, round(elapsed_total, 4), None, None)
    row = benchmark_row(run_id, sample, source_id, "THREE_STATEMENT_BUNDLE", "bundle", bundle_result)
    row["row_count"] = len(common_periods)
    row["has_report_date"] = bool(common_periods)
    row["latest_report_period"] = max(common_periods) if common_periods else None
    row["earliest_report_period"] = min(common_periods) if common_periods else None
    row["required_field_hits"] = component_success
    row["required_field_total"] = 3
    row["sample_value_coverage_ratio"] = component_success / 3
    row["record_quality"] = "VALID" if bundle_status == "SUCCESS" else ("PARTIAL" if component_success else "INVALID")
    rows.append(row)
    return rows, common_periods


def fetch_bse_periodic(report_name: str, report_date: str) -> pd.DataFrame:
    report_iso = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "NOTICE_DATE,SECURITY_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": report_name,
        "columns": "ALL",
        "filter": f'(TRADE_MARKET_CODE="069001017")(REPORT_DATE=\'{report_iso}\')',
    }
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"}
    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    payload = response.json()
    result = payload.get("result") or {}
    pages = int(result.get("pages") or 0)
    records: list[dict[str, Any]] = []
    for page_number in range(1, pages + 1):
        params["pageNumber"] = str(page_number)
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        page_payload = response.json().get("result") or {}
        records.extend(page_payload.get("data") or [])
    return pd.DataFrame(records)


def benchmark_bse_statements(samples: list[dict[str, Any]], config: dict[str, Any], run_id: str):
    bse_samples = [sample for sample in samples if sample["board"] == "BSE"]
    periods_by_symbol = {sample["symbol"]: {component: set() for component in BSE_REPORTS} for sample in bse_samples}
    rows: list[dict[str, Any]] = []
    adapter = "Eastmoney datacenter api/data/v1/get; TRADE_MARKET_CODE=069001017"
    for report_date in config["benchmark_window"]["bse_periodic_report_dates"]:
        report_iso = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"
        for component, report_name in BSE_REPORTS.items():
            result = invoke(fetch_bse_periodic, {"report_name": report_name, "report_date": report_date}, tries=3)
            frame = result[1]
            code_col = find_col(frame, ["SECURITY_CODE", "股票代码"])
            for sample in bse_samples:
                if code_col:
                    matched = frame[frame[code_col].astype(str).str.zfill(6) == code(sample["symbol"])].copy()
                else:
                    matched = pd.DataFrame()
                if len(matched):
                    sample_result = ("SUCCESS", matched, result[2], result[3], None, None)
                    periods_by_symbol[sample["symbol"]][component].add(report_iso)
                elif result[0] == "ERROR":
                    sample_result = result
                else:
                    sample_result = ("EMPTY", matched, result[2], result[3], None, None)
                row = benchmark_row(run_id, sample, "EASTMONEY_BSE_PERIODIC_STATEMENTS", component, adapter, sample_result)
                if len(matched):
                    row["has_report_date"] = True
                    row["latest_report_period"] = report_iso
                    row["earliest_report_period"] = report_iso
                    notice_col = find_col(matched, ["NOTICE_DATE", "公告日期"])
                    row["has_announcement_date"] = bool(notice_col)
                    row["temporal_fields_present"] = "REPORT_DATE" + ("|NOTICE_DATE" if notice_col else "")
                    row["required_field_hits"] = 3 if all(find_col(matched, [name]) for name in ["SECURITY_CODE", "REPORT_DATE", "NOTICE_DATE"]) else 2
                    row["required_field_total"] = 3
                    row["sample_value_coverage_ratio"] = row["required_field_hits"] / 3
                rows.append(row)
    composite_periods: dict[str, set[str]] = {}
    for sample in bse_samples:
        component_sets = list(periods_by_symbol[sample["symbol"]].values())
        common = set.intersection(*component_sets) if all(component_sets) else set()
        composite_periods[sample["symbol"]] = common
        successes = sum(bool(values) for values in component_sets)
        status = "SUCCESS" if successes == 3 and common else ("PARTIAL" if successes else "ERROR")
        result = (status, pd.DataFrame({"report_period_end": sorted(common)}), 1, 0.0, None, None)
        row = benchmark_row(run_id, sample, "EASTMONEY_BSE_PERIODIC_STATEMENTS", "THREE_STATEMENT_BUNDLE", "BSE periodic bundle", result)
        row["row_count"] = len(common)
        row["has_report_date"] = bool(common)
        row["latest_report_period"] = max(common) if common else None
        row["earliest_report_period"] = min(common) if common else None
        row["required_field_hits"] = successes
        row["required_field_total"] = 3
        row["sample_value_coverage_ratio"] = successes / 3
        row["record_quality"] = "VALID" if status == "SUCCESS" else ("PARTIAL" if successes else "INVALID")
        rows.append(row)
    return rows, composite_periods


def benchmark_extended(sample: dict[str, Any], run_id: str):
    if not sample.get("extended"):
        return []
    specs = [
        ("EASTMONEY_FINANCIAL_INDICATORS", "REPORT_PERIOD_INDICATORS", ak.stock_financial_analysis_indicator_em, {"symbol": sample["symbol"], "indicator": "按报告期"}, ["REPORT_DATE"], ["NOTICE_DATE", "UPDATE_DATE"], ["REPORT_DATE", "EPSJB", "PARENTNETPROFIT", "ROEJQ", "ZCFZL"]),
        ("EASTMONEY_HISTORICAL_VALUATION", "HISTORICAL_VALUATION", ak.stock_value_em, {"symbol": code(sample["symbol"])}, ["数据日期"], [], ["数据日期", "总市值", "流通市值", "总股本", "PE(TTM)", "市净率", "市销率"]),
        ("EASTMONEY_DIVIDENDS", "DIVIDEND_HISTORY", ak.stock_fhps_detail_em, {"symbol": code(sample["symbol"])}, ["报告期"], ["业绩披露日期", "预案公告日", "最新公告日期"], ["报告期", "现金分红-现金分红比例", "预案公告日", "股权登记日", "除权除息日", "方案进度"]),
        ("EASTMONEY_SHARE_CAPITAL", "SHARE_CAPITAL_HISTORY", ak.stock_zh_a_gbjg_em, {"symbol": sample["symbol"]}, ["变更日期"], [], ["变更日期", "总股本", "已流通股份", "已上市流通A股", "变动原因"]),
    ]
    rows: list[dict[str, Any]] = []
    for source_id, component, function, kwargs, report_names, announcement_names, expected in specs:
        result = invoke(function, kwargs, tries=2)
        row = benchmark_row(run_id, sample, source_id, component, f"akshare.{function.__name__}", result)
        if len(result[1]):
            set_temporal(row, result[1], report_names, announcement_names)
            row["required_field_hits"] = sum(bool(find_col(result[1], [name])) for name in expected)
            row["required_field_total"] = len(expected)
            row["sample_value_coverage_ratio"] = row["required_field_hits"] / len(expected)
        rows.append(row)
    return rows


def benchmark_symbol(sample: dict[str, Any], config: dict[str, Any], run_id: str):
    rows, filings = benchmark_disclosure(sample, config, run_id)
    periods: set[str] = set()
    if sample["board"] != "BSE":
        primary_rows, primary_periods = benchmark_symbol_statements(sample, run_id, "EASTMONEY_STATEMENTS")
        fallback_rows, _ = benchmark_symbol_statements(sample, run_id, "SINA_STATEMENTS")
        rows.extend(primary_rows)
        rows.extend(fallback_rows)
        periods = primary_periods
    rows.extend(benchmark_extended(sample, run_id))
    return rows, filings, periods


def benchmark_split_valuation(samples: list[dict[str, Any]], run_id: str):
    routes = [
        ("SH_MARKET", "SH_MAIN_AND_STAR", ak.stock_sh_a_spot_em),
        ("SZ_MARKET", "SZ_MAIN_AND_CHINEXT", ak.stock_sz_a_spot_em),
        ("BJ_MARKET", "BSE", ak.stock_bj_a_spot_em),
    ]
    rows: list[dict[str, Any]] = []
    frames: list[pd.DataFrame] = []
    elapsed_total = 0.0
    for component, board, function in routes:
        pseudo = {"symbol": "*", "name": component, "profile": "FULL_MARKET", "board": board}
        result = invoke(function, tries=3)
        elapsed_total += result[3]
        row = benchmark_row(run_id, pseudo, "EASTMONEY_CURRENT_VALUATION", component, f"akshare.{function.__name__}", result)
        if len(result[1]):
            expected = ["代码", "最新价", "市盈率-动态", "市净率", "总市值", "流通市值"]
            row["required_field_hits"] = sum(bool(find_col(result[1], [name])) for name in expected)
            row["required_field_total"] = len(expected)
            row["sample_value_coverage_ratio"] = row["required_field_hits"] / len(expected)
            frames.append(result[1])
        rows.append(row)
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    code_col = find_col(combined, ["代码"])
    available_codes = set(combined[code_col].astype(str).str.zfill(6)) if code_col else set()
    wanted_codes = {code(sample["symbol"]) for sample in samples}
    sample_coverage = len(available_codes & wanted_codes) / len(wanted_codes)
    status = "SUCCESS" if sample_coverage > 0 else "ERROR"
    result = (status, combined, 1, round(elapsed_total, 4), None, None)
    row = benchmark_row(run_id, None, "EASTMONEY_CURRENT_VALUATION", "FULL_MARKET_CURRENT_VALUATION_BUNDLE", "split SH/SZ/BJ endpoints", result)
    row["required_field_hits"] = sum(bool(find_col(combined, [name])) for name in ["代码", "最新价", "市盈率-动态", "市净率", "总市值", "流通市值"])
    row["required_field_total"] = 6
    row["sample_value_coverage_ratio"] = sample_coverage
    rows.append(row)
    return rows


def benchmark_global_sources(samples: list[dict[str, Any]], run_id: str):
    rows = benchmark_split_valuation(samples, run_id)
    result = invoke(ak.stock_repurchase_em, tries=3)
    row = benchmark_row(run_id, None, "EASTMONEY_BUYBACKS", "FULL_MARKET_BUYBACK_EVENTS", "akshare.stock_repurchase_em", result)
    if len(result[1]):
        expected = ["股票代码", "计划回购金额区间-下限", "已回购股份数量", "已回购金额", "最新公告日期"]
        row["required_field_hits"] = sum(bool(find_col(result[1], [name])) for name in expected)
        row["required_field_total"] = len(expected)
        row["sample_value_coverage_ratio"] = row["required_field_hits"] / len(expected)
        row["has_announcement_date"] = bool(find_col(result[1], ["最新公告日期"]))
    rows.append(row)
    return rows


def benchmark_calendar(run_id: str):
    result = invoke(ak.tool_trade_date_hist_sina, tries=3)
    row = benchmark_row(run_id, None, "SINA_TRADING_CALENDAR", "TRADING_CALENDAR", "akshare.tool_trade_date_hist_sina", result)
    dates: list[date] = []
    if len(result[1]):
        date_col = find_col(result[1], ["trade_date", "日期"])
        if date_col:
            dates = sorted({value.date() for value in pd.to_datetime(result[1][date_col], errors="coerce").dropna()})
            row["has_report_date"] = bool(dates)
    if not dates:
        row["record_quality"] = "INVALID"
    return dates, row


def next_trading_open(announcement_date: date, trading_dates: list[date], market_open_time: str) -> str | None:
    index = bisect.bisect_right(trading_dates, announcement_date)
    if index >= len(trading_dates):
        return None
    return f"{trading_dates[index].isoformat()}T{market_open_time}+08:00"


def build_pit_table(samples: list[dict[str, Any]], filings: list[dict[str, Any]], period_map: dict[str, set[str]], trading_dates: list[date], config: dict[str, Any], run_id: str) -> pd.DataFrame:
    output: list[dict[str, Any]] = []
    minimum_period = config["benchmark_window"]["minimum_report_period_end"]
    market_open = config["availability_policy"]["market_open_time"]
    sample_map = {sample["symbol"]: sample for sample in samples}
    official = [filing for filing in filings if filing["source_id"] == "CNINFO_OFFICIAL_DISCLOSURE"]
    fallback = [filing for filing in filings if filing["source_id"] == "EASTMONEY_NOTICE_FALLBACK"]
    for symbol, periods in period_map.items():
        for period in sorted(value for value in periods if value >= minimum_period):
            official_matches = [item for item in official if item["symbol"] == symbol and item["report_period_end"] == period]
            fallback_matches = [item for item in fallback if item["symbol"] == symbol and item["report_period_end"] == period]
            selected = official_matches or fallback_matches
            if not selected:
                sample = sample_map[symbol]
                output.append({
                    "run_id": run_id, "symbol": symbol, "name": sample["name"], "profile": sample["profile"], "board": sample["board"],
                    "report_period_end": period, "filing_source_id": None, "filing_title": None, "filing_link": None,
                    "announcement_date": None, "announcement_timestamp_raw": None, "availability_rule": "NEXT_TRADING_SESSION_OPEN",
                    "available_from": None, "revision_sequence": None, "match_status": "UNMATCHED", "point_in_time_grade": "BLOCKED",
                    "future_information_flag": False,
                })
                continue
            for filing in selected:
                available_from = next_trading_open(date.fromisoformat(filing["announcement_date"]), trading_dates, market_open)
                future_flag = False
                if available_from:
                    announcement_timestamp = pd.Timestamp(filing["announcement_timestamp_raw"])
                    if announcement_timestamp.tzinfo is None:
                        announcement_timestamp = announcement_timestamp.tz_localize("Asia/Shanghai")
                    future_flag = pd.Timestamp(available_from) <= announcement_timestamp
                output.append({
                    "run_id": run_id, "symbol": symbol, "name": filing["name"], "profile": filing["profile"], "board": filing["board"],
                    "report_period_end": period, "filing_source_id": filing["source_id"], "filing_title": filing["filing_title"],
                    "filing_link": filing["filing_link"], "announcement_date": filing["announcement_date"],
                    "announcement_timestamp_raw": filing["announcement_timestamp_raw"], "availability_rule": "NEXT_TRADING_SESSION_OPEN",
                    "available_from": available_from, "revision_sequence": filing["revision_sequence"],
                    "match_status": "OFFICIAL_MATCHED" if official_matches else "FALLBACK_MATCHED",
                    "point_in_time_grade": "DECISION_GRADE_DAILY" if official_matches and available_from else ("DEGRADED_FALLBACK" if available_from else "BLOCKED"),
                    "future_information_flag": future_flag,
                })
    return pd.DataFrame(output)


def build_summary(rows: pd.DataFrame) -> pd.DataFrame:
    output: list[dict[str, Any]] = []
    for source_id, group in rows.groupby("source_id"):
        calls = group[group["component"] != "THREE_STATEMENT_BUNDLE"]
        success = calls["status"].eq("SUCCESS")
        elapsed = pd.to_numeric(calls["elapsed_seconds"], errors="coerce")
        output.append({
            "source_id": source_id,
            "source_family": group["source_family"].iloc[0],
            "source_rank": group["source_rank"].iloc[0],
            "call_count": len(calls),
            "success_calls": int(success.sum()),
            "empty_calls": int(calls["status"].eq("EMPTY").sum()),
            "error_calls": int(calls["status"].eq("ERROR").sum()),
            "success_ratio": round(float(success.mean()) if len(calls) else 0, 6),
            "symbols_attempted": int(calls.loc[calls["symbol"] != "*", "symbol"].nunique()),
            "symbols_successful": int(calls.loc[(calls["symbol"] != "*") & success, "symbol"].nunique()),
            "profiles_successful": "|".join(sorted(calls.loc[success, "profile"].astype(str).unique())),
            "boards_successful": "|".join(sorted(calls.loc[success, "board"].astype(str).unique())),
            "median_elapsed_seconds": round(float(elapsed.median()), 4) if len(elapsed) else None,
            "p95_elapsed_seconds": round(float(elapsed.quantile(0.95)), 4) if len(elapsed) else None,
        })
    return pd.DataFrame(output).sort_values("source_id")


def build_coverage(rows: pd.DataFrame) -> pd.DataFrame:
    output: list[dict[str, Any]] = []
    symbol_rows = rows[rows["symbol"] != "*"]
    for source_id, source_group in symbol_rows.groupby("source_id"):
        for dimension in ["profile", "board"]:
            for value, group in source_group.groupby(dimension):
                if source_id in {"EASTMONEY_STATEMENTS", "EASTMONEY_BSE_PERIODIC_STATEMENTS", "SINA_STATEMENTS"}:
                    group = group[group["component"] == "THREE_STATEMENT_BUNDLE"]
                if group.empty:
                    continue
                success = group["status"].eq("SUCCESS")
                output.append({
                    "source_id": source_id, "dimension_type": dimension.upper(), "dimension_value": value,
                    "attempted": len(group), "successful": int(success.sum()),
                    "success_ratio": round(float(success.mean()), 6), "rows_returned": int(group["row_count"].sum()),
                })
    return pd.DataFrame(output).sort_values(["source_id", "dimension_type", "dimension_value"])


def source_success_ratio(summary: pd.DataFrame, source_id: str) -> float:
    selected = summary[summary["source_id"] == source_id]
    return 0.0 if selected.empty else float(selected["success_ratio"].iloc[0])


def statement_bundle_ratio(rows: pd.DataFrame, source_id: str) -> float:
    selected = rows[(rows["source_id"] == source_id) & (rows["component"] == "THREE_STATEMENT_BUNDLE")]
    return float(selected["status"].eq("SUCCESS").mean()) if len(selected) else 0.0


def composite_statement_status(rows: pd.DataFrame, samples: list[dict[str, Any]]):
    output: list[dict[str, Any]] = []
    for sample in samples:
        source_id = "EASTMONEY_BSE_PERIODIC_STATEMENTS" if sample["board"] == "BSE" else "EASTMONEY_STATEMENTS"
        selected = rows[(rows["source_id"] == source_id) & (rows["component"] == "THREE_STATEMENT_BUNDLE") & (rows["symbol"] == sample["symbol"])]
        success = bool(len(selected) and selected["status"].iloc[0] == "SUCCESS")
        output.append({**sample, "selected_source_id": source_id, "success": success})
    return pd.DataFrame(output)


def build_decision(config: dict[str, Any], rows: pd.DataFrame, summary: pd.DataFrame, pit: pd.DataFrame, trading_dates: list[date], run_id: str) -> dict[str, Any]:
    policy = config["acceptance_policy"]
    official_ratio = source_success_ratio(summary, "CNINFO_OFFICIAL_DISCLOSURE")
    fallback_notice_ratio = source_success_ratio(summary, "EASTMONEY_NOTICE_FALLBACK")
    sh_sz_ratio = statement_bundle_ratio(rows, "EASTMONEY_STATEMENTS")
    bse_ratio = statement_bundle_ratio(rows, "EASTMONEY_BSE_PERIODIC_STATEMENTS")
    fallback_statement_ratio = statement_bundle_ratio(rows, "SINA_STATEMENTS")
    composite = composite_statement_status(rows, config["sample_design"]["symbols"])
    composite_ratio = float(composite["success"].mean()) if len(composite) else 0.0
    profile_coverage = {key: round(float(group["success"].mean()), 6) for key, group in composite.groupby("profile")}
    board_coverage = {key: round(float(group["success"].mean()), 6) for key, group in composite.groupby("board")}
    official_pit_ratio = float(pit["match_status"].eq("OFFICIAL_MATCHED").mean()) if len(pit) else 0.0
    future_count = int(pit["future_information_flag"].fillna(False).astype(bool).sum()) if len(pit) else 0
    valuation_bundle = rows[(rows["source_id"] == "EASTMONEY_CURRENT_VALUATION") & (rows["component"] == "FULL_MARKET_CURRENT_VALUATION_BUNDLE")]
    valuation_coverage = float(valuation_bundle["sample_value_coverage_ratio"].iloc[0]) if len(valuation_bundle) and pd.notna(valuation_bundle["sample_value_coverage_ratio"].iloc[0]) else 0.0
    extended_sources = ["EASTMONEY_FINANCIAL_INDICATORS", "EASTMONEY_HISTORICAL_VALUATION", "EASTMONEY_SHARE_CAPITAL", "EASTMONEY_DIVIDENDS"]
    extended_ratios = {source_id: source_success_ratio(summary, source_id) for source_id in extended_sources}
    buyback_ratio = source_success_ratio(summary, "EASTMONEY_BUYBACKS")

    hard_failures: list[str] = []
    if not trading_dates:
        hard_failures.append("TRADING_CALENDAR_UNAVAILABLE")
    if official_ratio < policy["minimum_official_disclosure_call_success_ratio"]:
        hard_failures.append("OFFICIAL_DISCLOSURE_ROUTE_BELOW_THRESHOLD")
    if sh_sz_ratio < policy["minimum_sh_sz_statement_bundle_success_ratio"]:
        hard_failures.append("SH_SZ_STATEMENT_BUNDLE_BELOW_THRESHOLD")
    if bse_ratio < policy["minimum_bse_statement_bundle_success_ratio"]:
        hard_failures.append("BSE_STATEMENT_BUNDLE_BELOW_THRESHOLD")
    if composite_ratio < policy["minimum_composite_statement_bundle_success_ratio"]:
        hard_failures.append("COMPOSITE_STATEMENT_BUNDLE_BELOW_THRESHOLD")
    if fallback_statement_ratio < policy["minimum_statement_fallback_bundle_success_ratio"]:
        hard_failures.append("STATEMENT_FALLBACK_BUNDLE_BELOW_THRESHOLD")
    if official_pit_ratio < policy["minimum_point_in_time_match_ratio"]:
        hard_failures.append("POINT_IN_TIME_OFFICIAL_MATCH_BELOW_THRESHOLD")
    if valuation_coverage < policy["minimum_current_valuation_sample_coverage"]:
        hard_failures.append("CURRENT_VALUATION_SAMPLE_COVERAGE_BELOW_THRESHOLD")
    missing_profiles = [profile for profile in config["sample_design"]["minimum_profiles"] if profile_coverage.get(profile, 0) <= 0]
    if missing_profiles:
        hard_failures.append("PRIMARY_STATEMENT_PROFILE_GAP:" + ",".join(missing_profiles))
    missing_boards = [board for board in config["sample_design"]["minimum_boards"] if board_coverage.get(board, 0) <= 0]
    if missing_boards:
        hard_failures.append("PRIMARY_STATEMENT_BOARD_GAP:" + ",".join(missing_boards))
    if future_count:
        hard_failures.append(f"POINT_IN_TIME_FUTURE_INFORMATION:{future_count}")

    decisions: list[dict[str, Any]] = [
        {"source_id": "CNINFO_OFFICIAL_DISCLOSURE", "decision": "PRIMARY_ANNOUNCEMENT_AND_REVISION_METADATA" if official_ratio >= policy["minimum_official_disclosure_call_success_ratio"] and official_pit_ratio >= policy["minimum_point_in_time_match_ratio"] else "REMEDIATION_REQUIRED", "success_ratio": round(official_ratio, 6), "point_in_time_match_ratio": round(official_pit_ratio, 6)},
        {"source_id": "EASTMONEY_NOTICE_FALLBACK", "decision": "DEGRADED_METADATA_FALLBACK_SH_SZ_ONLY" if fallback_notice_ratio >= policy["minimum_official_disclosure_call_success_ratio"] else "NOT_RELIABLE_AS_FALLBACK", "success_ratio": round(fallback_notice_ratio, 6)},
        {"source_id": "EASTMONEY_STATEMENTS", "decision": "PRIMARY_STRUCTURED_THREE_STATEMENT_SOURCE_SH_SZ" if sh_sz_ratio >= policy["minimum_sh_sz_statement_bundle_success_ratio"] else "REMEDIATION_REQUIRED", "bundle_success_ratio": round(sh_sz_ratio, 6)},
        {"source_id": "EASTMONEY_BSE_PERIODIC_STATEMENTS", "decision": "PRIMARY_STRUCTURED_THREE_STATEMENT_SOURCE_BSE" if bse_ratio >= policy["minimum_bse_statement_bundle_success_ratio"] else "REMEDIATION_REQUIRED", "bundle_success_ratio": round(bse_ratio, 6)},
        {"source_id": "SINA_STATEMENTS", "decision": "FALLBACK_STRUCTURED_THREE_STATEMENT_SOURCE_SH_SZ" if fallback_statement_ratio >= policy["minimum_statement_fallback_bundle_success_ratio"] else "NOT_RELIABLE_AS_FALLBACK", "bundle_success_ratio": round(fallback_statement_ratio, 6)},
        {"source_id": "EASTMONEY_CURRENT_VALUATION", "decision": "PRIMARY_CURRENT_MARKET_CAP_PE_PB_SOURCE_SPLIT_BY_EXCHANGE" if valuation_coverage >= policy["minimum_current_valuation_sample_coverage"] else "REMEDIATION_REQUIRED", "sample_coverage_ratio": round(valuation_coverage, 6), "denominator_policy": "RAW_ONLY; FMDL3D_RECOMPUTES_VALIDITY"},
    ]
    for source_id, accepted_label in [
        ("EASTMONEY_FINANCIAL_INDICATORS", "CROSS_CHECK_AND_FACTOR_SUPPORT_ONLY"),
        ("EASTMONEY_HISTORICAL_VALUATION", "CONDITIONAL_HISTORICAL_VALUATION_SOURCE"),
        ("EASTMONEY_SHARE_CAPITAL", "PRIMARY_HISTORICAL_SHARE_CAPITAL_SOURCE_SH_SZ; BSE_GAP_VISIBLE"),
        ("EASTMONEY_DIVIDENDS", "PRIMARY_DIVIDEND_EVENT_SOURCE_SH_SZ; BSE_GAP_VISIBLE"),
    ]:
        ratio = extended_ratios[source_id]
        decisions.append({"source_id": source_id, "decision": accepted_label if ratio >= policy["minimum_extended_source_success_ratio"] else "SUPPORT_ONLY_OR_REMEDIATION_REQUIRED", "success_ratio": round(ratio, 6)})
    decisions.append({"source_id": "EASTMONEY_BUYBACKS", "decision": "PRIMARY_BUYBACK_EVENT_SOURCE" if buyback_ratio >= 1.0 else "DEGRADED_OR_REMEDIATION_REQUIRED", "success_ratio": round(buyback_ratio, 6)})

    controlled_limitations = [
        "EASTMONEY_PER_SYMBOL_AND_SINA_STATEMENT_ROUTES_DO_NOT_SUPPORT_BSE; USE_BSE_PERIODIC_ADAPTER",
        "BSE_HISTORICAL_VALUATION_SHARE_CAPITAL_AND_DIVIDEND_DETAIL_REQUIRE_FMDL3B_SPECIAL_HANDLING",
        "CURRENT_PROVIDER_PE_PB_ARE_RAW_CROSS_CHECKS; DENOMINATOR_VALIDITY_IS_RECOMPUTED_IN_FMDL3D",
        "DAILY_POINT_IN_TIME_RESOLUTION_ONLY; NO_INTRADAY_FINANCIAL_FACTOR_AUTHORITY",
    ]
    for source_id, ratio in extended_ratios.items():
        if ratio < policy["minimum_extended_source_success_ratio"]:
            controlled_limitations.append(f"{source_id}_BELOW_THRESHOLD:{ratio:.4f}")

    accepted = not hard_failures
    return {
        "decision_version": "1.1.0",
        "run_id": run_id,
        "generated_at": now().isoformat(timespec="seconds"),
        "program_id": "FMDL-3A",
        "status": "FMDL3A_ACCEPTED_SOURCE_ROUTE_AND_COVERAGE_GATES_FROZEN" if accepted else "FMDL3A_REMEDIATION_REQUIRED",
        "exit_gate": "SOURCE_ROUTE_AND_NUMERIC_COVERAGE_GATES_FROZEN" if accepted else "NOT_MET",
        "measured_metrics": {
            "sample_symbol_count": len(config["sample_design"]["symbols"]),
            "official_disclosure_call_success_ratio": round(official_ratio, 6),
            "fallback_notice_call_success_ratio": round(fallback_notice_ratio, 6),
            "sh_sz_primary_statement_bundle_success_ratio": round(sh_sz_ratio, 6),
            "bse_primary_statement_bundle_success_ratio": round(bse_ratio, 6),
            "composite_primary_statement_bundle_success_ratio": round(composite_ratio, 6),
            "fallback_statement_bundle_success_ratio": round(fallback_statement_ratio, 6),
            "official_point_in_time_match_ratio": round(official_pit_ratio, 6),
            "current_valuation_sample_coverage_ratio": round(valuation_coverage, 6),
            "future_information_count": future_count,
            "composite_statement_profile_coverage": profile_coverage,
            "composite_statement_board_coverage": board_coverage,
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
            "fallback_notice_grade": "DEGRADED_METADATA_SH_SZ_ONLY",
        },
        "source_decisions": decisions,
        "hard_failures": hard_failures,
        "controlled_limitations": controlled_limitations,
        "authority": config["authority"],
        "trade_authority": config["trade_authority"],
        "next_phase": "FMDL-3B" if accepted else "FMDL-3A-R",
    }


def write_outputs(config: dict[str, Any], run_id: str, rows: pd.DataFrame, summary: pd.DataFrame, coverage: pd.DataFrame, pit: pd.DataFrame, decision: dict[str, Any]) -> None:
    root = ROOT / config["publication"]["candidate_root"]
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    outputs = {
        "FMDL3A_BENCHMARK_ROWS.csv": rows,
        "FMDL3A_SOURCE_SUMMARY.csv": summary,
        "FMDL3A_COVERAGE_MAP.csv": coverage,
        "FMDL3A_POINT_IN_TIME_EVIDENCE.csv": pit,
        "FMDL3_SOURCE_INDEX.csv": pd.DataFrame(decision["source_decisions"]),
    }
    for filename, frame in outputs.items():
        frame.assign(run_id=run_id, authority=decision["authority"], trade_authority=decision["trade_authority"]).to_csv(root / filename, index=False)
    dump(root / "FMDL3A_SOURCE_DECISION.json", decision)
    manifest = {
        "manifest_version": "1.1.0", "run_id": run_id, "generated_at": now().isoformat(timespec="seconds"),
        "program_id": "FMDL-3A", "status": "CANDIDATE", "decision_status": decision["status"], "files": {},
        "authority": decision["authority"], "trade_authority": decision["trade_authority"],
    }
    for path in root.iterdir():
        manifest["files"][path.name] = {"path": str(path.relative_to(ROOT)), "size_bytes": path.stat().st_size, "sha256": sha256(path)}
    dump(root / "FMDL3A_MANIFEST.json", manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CFG)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    run_id = f"FMDL3A_{now().strftime('%Y%m%dT%H%M%S%z')}"
    samples = config["sample_design"]["symbols"]

    trading_dates, calendar_row = benchmark_calendar(run_id)
    all_rows: list[dict[str, Any]] = [calendar_row]
    all_rows.extend(benchmark_global_sources(samples, run_id))
    bse_rows, bse_periods = benchmark_bse_statements(samples, config, run_id)
    all_rows.extend(bse_rows)
    filings: list[dict[str, Any]] = []
    period_map: dict[str, set[str]] = dict(bse_periods)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(benchmark_symbol, sample, config, run_id): sample for sample in samples}
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
                all_rows.append(benchmark_row(run_id, sample, "EASTMONEY_STATEMENTS", "SYMBOL_BENCHMARK_UNHANDLED_FAILURE", "benchmark_symbol", result))
                period_map.setdefault(sample["symbol"], set())

    rows_frame = pd.DataFrame(all_rows).sort_values(["source_id", "symbol", "component"])
    summary_frame = build_summary(rows_frame)
    coverage_frame = build_coverage(rows_frame)
    pit_frame = build_pit_table(samples, filings, period_map, trading_dates, config, run_id)
    decision = build_decision(config, rows_frame, summary_frame, pit_frame, trading_dates, run_id)
    write_outputs(config, run_id, rows_frame, summary_frame, coverage_frame, pit_frame, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not decision["hard_failures"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
