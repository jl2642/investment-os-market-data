#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pandas as pd
import requests

from fmdl5d_core import (
    assign_filing_periods,
    build_unmapped_catalog,
    count_duplicate_keys,
    file_sha256,
    finite_number,
    infer_profile,
    is_financial_filing,
    latest_filing_map,
    load_field_registry,
    map_line_item,
    normalize_raw_facts,
    normalize_token,
    stable_hash,
)

HKEX_BASE_URL = "https://www1.hkexnews.hk"
HKEX_SEARCH_PAGE = f"{HKEX_BASE_URL}/search/titlesearch.xhtml"
HKEX_API_ENDPOINT = f"{HKEX_BASE_URL}/search/titleSearchServlet.do"
STATEMENTS = {
    "资产负债表": "balance_sheet",
    "利润表": "income_statement",
    "现金流量表": "cash_flow",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def monthly_chunks(start: date, end: date) -> list[tuple[date, date]]:
    chunks: list[tuple[date, date]] = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        if cursor.month == 12:
            next_month = date(cursor.year + 1, 1, 1)
        else:
            next_month = date(cursor.year, cursor.month + 1, 1)
        chunk_end = min(end, next_month - pd.Timedelta(days=1))
        chunks.append((max(start, cursor), chunk_end))
        cursor = next_month
    return chunks


def _extract_view_state_and_action(text: str) -> tuple[str, str]:
    view = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', text)
    form = re.search(r'<form[^>]*action="([^"]+)"', text)
    return (html.unescape(view.group(1)) if view else "", html.unescape(form.group(1)) if form else "")


def _parse_hkex_record(record: dict[str, Any], retrieved_at: str) -> dict[str, Any] | None:
    raw_code = str(record.get("STOCK_CODE", "")).split("\n")[0].strip()
    match = re.search(r"(\d{4,5})", raw_code)
    if not match:
        return None
    code = match.group(1).zfill(5)
    raw_timestamp = str(record.get("DATE_TIME", "")).strip()
    timestamp = pd.to_datetime(raw_timestamp, format="%d/%m/%Y %H:%M", errors="coerce")
    if pd.isna(timestamp):
        return None
    title = html.unescape(str(record.get("TITLE", ""))).replace("\xa0", " ").strip()
    category = html.unescape(str(record.get("LONG_TEXT", ""))).replace("\xa0", " ").strip()
    link = str(record.get("FILE_LINK", "")).strip()
    if link:
        link = urljoin(HKEX_BASE_URL, link)
    payload = {
        "news_id": str(record.get("NEWS_ID", "")).strip(),
        "stock_code_5d": code,
        "stock_name": str(record.get("STOCK_NAME", "")).split("\n")[0].strip(),
        "title": re.sub(r"\s+", " ", title),
        "category": re.sub(r"\s+", " ", category),
        "file_type": str(record.get("FILE_TYPE", "")).upper().strip(),
        "file_info": str(record.get("FILE_INFO", "")).strip(),
        "release_timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "filing_url": link,
        "source_id": "HKEXNEWS_TITLE_SEARCH",
        "source_tier": "OFFICIAL_PRIMARY",
        "source_retrieved_at": retrieved_at,
    }
    payload["source_record_sha256"] = stable_hash(record)
    return payload


def _fetch_hkex_chunk(session: requests.Session, start: date, end: date, retrieved_at: str) -> list[dict[str, Any]]:
    from_text = start.strftime("%Y%m%d")
    to_text = end.strftime("%Y%m%d")
    page = session.get(
        HKEX_SEARCH_PAGE,
        params={
            "sortDir": "0",
            "sortByRecordDate": "on",
            "searchType": "0",
            "category": "0",
            "t1code": "-2",
            "t2Gcode": "-2",
            "t2code": "-2",
            "documentType": "-1",
            "rowRange": "0",
            "lang": "EN",
        },
        timeout=45,
    )
    page.raise_for_status()
    view_state, form_action = _extract_view_state_and_action(page.text)
    if view_state:
        submit_url = urljoin(HKEX_SEARCH_PAGE, form_action or HKEX_SEARCH_PAGE)
        post = session.post(
            submit_url,
            data={
                "j_idt10": "j_idt10",
                "j_idt10:loadMoreRange": "100",
                "javax.faces.ViewState": view_state,
                "from": from_text,
                "to": to_text,
            },
            timeout=45,
        )
        post.raise_for_status()

    all_records: list[dict[str, Any]] = []
    fetched = 0
    total: int | None = None
    while True:
        row_range = fetched + 5000
        response = session.get(
            HKEX_API_ENDPOINT,
            params={
                "sortDir": "0",
                "sortByOptions": "DateTime",
                "category": "0",
                "market": "SEHK",
                "stockId": "-1",
                "documentType": "-1",
                "fromDate": from_text,
                "toDate": to_text,
                "title": "",
                "searchType": "0",
                "t1code": "-2",
                "t2Gcode": "-2",
                "t2code": "-2",
                "rowRange": str(row_range),
                "lang": "E",
            },
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": HKEX_SEARCH_PAGE,
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        raw_result = data.get("result")
        if not raw_result or raw_result == "null":
            break
        records = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
        if not records:
            break
        if total is None:
            total = int(records[0].get("TOTAL_COUNT", len(records)))
        new_records = records[fetched:]
        for raw in new_records:
            parsed = _parse_hkex_record(raw, retrieved_at)
            if parsed:
                all_records.append(parsed)
        fetched = len(records)
        if not data.get("hasNextRow") or (total is not None and fetched >= total):
            break
    return all_records


def fetch_hkex_financial_filings(start: date, end: date, universe_codes: set[str]) -> tuple[list[dict[str, Any]], list[str]]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; InvestmentOS-FMDL5D/1.0; research-data-pipeline)",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    retrieved_at = now_utc()
    results: list[dict[str, Any]] = []
    warnings: list[str] = []
    for start_chunk, end_chunk in monthly_chunks(start, end):
        last_error = ""
        for attempt in range(1, 4):
            try:
                records = _fetch_hkex_chunk(session, start_chunk, end_chunk, retrieved_at)
                for row in records:
                    if row["stock_code_5d"] in universe_codes and is_financial_filing(row["title"], row["category"]):
                        results.append(row)
                last_error = ""
                break
            except Exception as exc:
                last_error = f"{type(exc).__name__}:{exc}"
                time.sleep(attempt * 2)
        if last_error:
            warnings.append(f"HKEX_CHUNK_FAILED:{start_chunk}:{end_chunk}:{last_error}")
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in results:
        key = (row["stock_code_5d"], row.get("news_id", ""), row["filing_url"])
        deduped[key] = row
    return sorted(deduped.values(), key=lambda item: item["release_timestamp"]), warnings


def _ak_call(function, **kwargs):
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            return function(**kwargs)
        except Exception as exc:
            last_error = exc
            time.sleep(0.6 * attempt)
    assert last_error is not None
    raise last_error


def _currency_context(indicator: pd.DataFrame) -> tuple[dict[str, str], str | None, str | None]:
    if indicator is None or indicator.empty:
        return {}, None, None
    frame = indicator.copy()
    report_col = "REPORT_DATE" if "REPORT_DATE" in frame.columns else None
    currency_map: dict[str, str] = {}
    if report_col:
        for _, row in frame.iterrows():
            report = pd.to_datetime(row.get(report_col), errors="coerce")
            currency = str(row.get("CURRENCY", "")).strip().upper()
            if pd.notna(report) and currency and currency != "NAN":
                currency_map[report.date().isoformat()] = currency
    latest_currency = None
    if "CURRENCY" in frame.columns:
        values = [str(value).strip().upper() for value in frame["CURRENCY"].tolist() if str(value).strip() and str(value).upper() != "NAN"]
        latest_currency = values[0] if values else None
    fiscal_year = None
    if "FISCAL_YEAR" in frame.columns:
        values = [str(value).strip() for value in frame["FISCAL_YEAR"].tolist() if str(value).strip() and str(value).upper() != "NAN"]
        fiscal_year = values[0] if values else None
    return currency_map, latest_currency, fiscal_year


def fetch_security_financials(
    security: dict[str, Any],
    registry: dict[tuple[str, str], dict[str, Any]],
    start_date: date,
    maximum_periods: int,
) -> dict[str, Any]:
    import akshare as ak

    code = security["stock_code_5d"]
    raw_rows: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    statement_status: dict[str, str] = {}
    item_names: list[str] = []
    source_hashes: dict[str, str] = {}
    currency_map: dict[str, str] = {}
    latest_currency: str | None = None
    fiscal_year: str | None = None
    indicator_error = ""
    try:
        indicator = _ak_call(ak.stock_financial_hk_analysis_indicator_em, symbol=code, indicator="报告期")
        currency_map, latest_currency, fiscal_year = _currency_context(indicator)
        source_hashes["indicator"] = stable_hash(indicator.fillna("").astype(str).to_dict(orient="records"))
    except Exception as exc:
        indicator_error = f"{type(exc).__name__}:{exc}"

    periods: set[str] = set()
    for provider_statement, statement in STATEMENTS.items():
        try:
            frame = _ak_call(ak.stock_financial_hk_report_em, stock=code, symbol=provider_statement, indicator="报告期")
            if frame is None or frame.empty:
                statement_status[statement] = "EMPTY"
                continue
            source_hashes[statement] = stable_hash(frame.fillna("").astype(str).to_dict(orient="records"))
            report_col = "STD_REPORT_DATE" if "STD_REPORT_DATE" in frame.columns else "REPORT_DATE"
            prepared = frame.copy()
            prepared["__period"] = pd.to_datetime(prepared[report_col], errors="coerce")
            prepared = prepared[prepared["__period"].notna() & (prepared["__period"].dt.date >= start_date)]
            accepted_periods = sorted(prepared["__period"].dt.date.unique(), reverse=True)[:maximum_periods]
            prepared = prepared[prepared["__period"].dt.date.isin(accepted_periods)]
            for _, row in prepared.iterrows():
                period = row["__period"].date().isoformat()
                amount = finite_number(row.get("AMOUNT"))
                if amount is None:
                    continue
                source_code = str(row.get("STD_ITEM_CODE", "")).strip()
                source_name = str(row.get("STD_ITEM_NAME", "")).strip()
                item_names.append(source_name)
                mapped = map_line_item(statement, source_code, source_name, registry)
                if not mapped:
                    unmapped.append({"statement": statement, "source_item_code": source_code, "source_item_name": source_name})
                    continue
                currency = currency_map.get(period) or latest_currency or str(security.get("trading_currency", "")).upper() or "UNKNOWN"
                units = mapped["units"].replace("CURRENCY", currency)
                aliases = {normalize_token(value) for value in mapped["aliases"]}
                code_match = normalize_token(source_code) in aliases
                raw_rows.append(
                    {
                        "raw_fact_id": stable_hash(
                            {
                                "security_id": security["security_id"],
                                "statement": statement,
                                "period_end": period,
                                "source_item_code": source_code,
                                "source_item_name": source_name,
                                "amount": amount,
                            }
                        ),
                        "security_id": security["security_id"],
                        "issuer_id": security["issuer_id"],
                        "stock_code_5d": code,
                        "official_security_name_en": security.get("official_security_name_en", ""),
                        "official_issuer_name_en": security.get("official_issuer_name_en", ""),
                        "statement": statement,
                        "period_end": period,
                        "field_id": mapped["field_id"],
                        "field_name": mapped["field_name"],
                        "source_item_code": source_code,
                        "source_item_name": source_name,
                        "source_value": amount,
                        "currency": currency,
                        "units": units,
                        "sign_rule": mapped["sign_rule"],
                        "mapping_status": "MAPPED_EXPLICIT_SOURCE_CODE" if code_match else "MAPPED_EXACT_NORMALIZED_ALIAS",
                        "mapping_priority": 0 if code_match else 1,
                        "source_id": "EASTMONEY_HK_FINANCIAL_REPORT",
                        "source_tier": "UNOFFICIAL_FREE_VENDOR_STRUCTURED",
                        "source_adapter": "akshare.stock_financial_hk_report_em",
                        "source_location": f"{code}:{provider_statement}:报告期:{period}:{source_code or source_name}",
                        "source_response_sha256": source_hashes[statement],
                        "source_retrieved_at": now_utc(),
                        "trade_authority": "NONE",
                    }
                )
                periods.add(period)
            statement_status[statement] = "SUCCESS"
        except Exception as exc:
            statement_status[statement] = f"FAILED:{type(exc).__name__}:{exc}"

    profile = infer_profile(item_names, security.get("official_issuer_name_en", ""))
    for row in raw_rows:
        row["profile"] = profile
    successful_statements = sum(value == "SUCCESS" for value in statement_status.values())
    return {
        "security_id": security["security_id"],
        "issuer_id": security["issuer_id"],
        "stock_code_5d": code,
        "profile": profile,
        "raw_rows": raw_rows,
        "unmapped": unmapped,
        "periods": sorted(periods),
        "fiscal_year_end": fiscal_year,
        "latest_currency": latest_currency,
        "indicator_error": indicator_error,
        "statement_status": statement_status,
        "successful_statement_count": successful_statements,
        "source_hashes": source_hashes,
    }


def balance_sheet_tie_outs(normalized: pd.DataFrame) -> tuple[int, int]:
    if normalized.empty:
        return 0, 0
    balance = normalized[(normalized["statement"] == "balance_sheet") & normalized["decision_grade_eligible"]]
    if balance.empty:
        return 0, 0
    pivot = balance.pivot_table(index=["security_id", "period_end"], columns="field_id", values="normalized_value", aggfunc="first")
    checked = failed = 0
    for _, row in pivot.iterrows():
        if all(field in row and pd.notna(row[field]) for field in ("total_assets", "total_liabilities", "total_equity")):
            checked += 1
            assets = abs(float(row["total_assets"]))
            difference = abs(float(row["total_assets"]) - float(row["total_liabilities"]) - float(row["total_equity"]))
            if assets > 0 and difference / assets > 0.03:
                failed += 1
    return checked, failed


def build_current(normalized: pd.DataFrame) -> pd.DataFrame:
    eligible = normalized[normalized["decision_grade_eligible"]].copy()
    if eligible.empty:
        return pd.DataFrame()
    eligible["period_ts"] = pd.to_datetime(eligible["period_end"])
    latest = eligible.groupby("security_id")["period_ts"].max().rename("latest_period")
    eligible = eligible.join(latest, on="security_id")
    eligible = eligible[eligible["period_ts"] == eligible["latest_period"]]
    values = eligible.pivot_table(index="security_id", columns="field_id", values="normalized_value", aggfunc="first").reset_index()
    meta = eligible.sort_values(["security_id", "period_ts"]).groupby("security_id").tail(1)[
        [
            "security_id",
            "issuer_id",
            "stock_code_5d",
            "official_security_name_en",
            "official_issuer_name_en",
            "profile",
            "period_end",
            "currency",
            "available_from",
            "official_filing_id",
            "official_filing_url",
        ]
    ]
    return meta.merge(values, on="security_id", how="left").sort_values("stock_code_5d")


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--contract", default="config/fmdl5d_hkex_disclosure_financial_contract.json")
    parser.add_argument("--registry", default="config/fmdl5d_hk_financial_field_registry.json")
    parser.add_argument("--start-date", default="")
    parser.add_argument("--workers", type=int, default=int(os.environ.get("FMDL5D_WORKERS", "12")))
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
    registry, registry_payload = load_field_registry(Path(args.registry))
    source_decision = json.loads(Path(contract["source_release"]["decision_path"]).read_text(encoding="utf-8"))
    if source_decision.get("status") != contract["source_release"]["required_status"]:
        raise ValueError(f"SOURCE_RELEASE_NOT_ACCEPTED:{source_decision.get('status')}")
    overlay = pd.read_csv(contract["source_release"]["semantic_overlay_path"], dtype={"stock_code_5d": str})
    overlay["stock_code_5d"] = overlay["stock_code_5d"].astype(str).str.zfill(5)
    prices = pd.read_parquet(contract["source_release"]["price_store_path"], columns=["observation_date"])
    trading_days = sorted(pd.to_datetime(prices["observation_date"], errors="coerce").dropna().dt.date.unique())
    market_max_date = max(trading_days)
    start_date = pd.Timestamp(args.start_date or contract["period_policy"]["default_start_date"]).date()

    securities = overlay.to_dict(orient="records")
    equity_securities = [row for row in securities if str(row.get("security_type")) == "COMMON_EQUITY"]
    fund_securities = [row for row in securities if row not in equity_securities]
    universe_codes = {row["stock_code_5d"] for row in securities}

    filings, hkex_warnings = fetch_hkex_financial_filings(start_date, market_max_date, universe_codes)

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                fetch_security_financials,
                security,
                registry,
                start_date,
                int(contract["period_policy"]["maximum_periods_per_statement"]),
            ): security
            for security in equity_securities
        }
        for future in as_completed(futures):
            security = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append(
                    {
                        "security_id": security["security_id"],
                        "issuer_id": security["issuer_id"],
                        "stock_code_5d": security["stock_code_5d"],
                        "profile": "UNKNOWN",
                        "raw_rows": [],
                        "unmapped": [],
                        "periods": [],
                        "fiscal_year_end": None,
                        "latest_currency": None,
                        "indicator_error": "",
                        "statement_status": {"all": f"FAILED:{type(exc).__name__}:{exc}"},
                        "successful_statement_count": 0,
                        "source_hashes": {},
                    }
                )

    raw_rows = [row for result in results for row in result["raw_rows"]]
    unmapped_rows = [row for result in results for row in result["unmapped"]]
    periods_by_code = {result["stock_code_5d"]: result["periods"] for result in results}
    fiscal_year_by_code = {result["stock_code_5d"]: result["fiscal_year_end"] for result in results}
    assigned_filings = assign_filing_periods(filings, periods_by_code, fiscal_year_by_code, trading_days)
    latest_filings = latest_filing_map(assigned_filings)
    normalized_rows = normalize_raw_facts(raw_rows, latest_filings)

    raw = pd.DataFrame(raw_rows)
    normalized = pd.DataFrame(normalized_rows)
    disclosure_frame = pd.DataFrame(assigned_filings)
    unmapped_catalog = pd.DataFrame(build_unmapped_catalog(unmapped_rows))
    current = build_current(normalized) if not normalized.empty else pd.DataFrame()

    if not raw.empty:
        raw.to_parquet(output / "FMDL5D_MAPPED_RAW_FACTS.parquet", index=False)
    else:
        pd.DataFrame(columns=["raw_fact_id"]).to_parquet(output / "FMDL5D_MAPPED_RAW_FACTS.parquet", index=False)
    if not normalized.empty:
        normalized.to_parquet(output / "FMDL5D_NORMALIZED_FINANCIAL_FACTS.parquet", index=False)
    else:
        pd.DataFrame(columns=["normalized_fact_id"]).to_parquet(output / "FMDL5D_NORMALIZED_FINANCIAL_FACTS.parquet", index=False)
    disclosure_frame.to_csv(output / "FMDL5D_HKEX_FINANCIAL_DISCLOSURES.csv", index=False, encoding="utf-8-sig")
    current.to_csv(output / "FMDL5D_ISSUER_FINANCIAL_CURRENT.csv", index=False, encoding="utf-8-sig")
    unmapped_catalog.to_csv(output / "FMDL5D_UNMAPPED_FIELD_CATALOG.csv", index=False, encoding="utf-8-sig")

    structured_success = {result["security_id"] for result in results if result["successful_statement_count"] >= 2 and result["raw_rows"]}
    official_codes = {row["stock_code_5d"] for row in assigned_filings if row.get("report_period_end")}
    decision_grade_securities = set(normalized.loc[normalized["decision_grade_eligible"], "security_id"]) if not normalized.empty else set()
    duplicate_fact_keys = count_duplicate_keys(normalized, ["security_id", "statement", "period_end", "field_id"]) if not normalized.empty else 0
    invalid_numeric = int((~pd.to_numeric(normalized["normalized_value"], errors="coerce").notna()).sum()) if not normalized.empty else 0
    future_available = 0
    if not normalized.empty:
        available_dates = pd.to_datetime(normalized["available_from"], errors="coerce", utc=True)
        future_available = int((available_dates.dt.date > market_max_date).fillna(False).sum())
    missing_lineage = 0
    if not normalized.empty:
        eligible = normalized[normalized["decision_grade_eligible"]]
        missing_lineage = int((eligible["official_filing_id"].isna() | eligible["official_filing_url"].isna()).sum())
    tie_out_checked, tie_out_failed = balance_sheet_tie_outs(normalized)

    failures: list[dict[str, Any]] = []
    for result in sorted(results, key=lambda item: item["stock_code_5d"]):
        if result["successful_statement_count"] < 2 or not result["raw_rows"]:
            failures.append(
                {
                    "security_id": result["security_id"],
                    "stock_code_5d": result["stock_code_5d"],
                    "failure_type": "STRUCTURED_FINANCIAL_DATA_INSUFFICIENT",
                    "details": json.dumps(result["statement_status"], ensure_ascii=False, sort_keys=True),
                }
            )
    for security in fund_securities:
        failures.append(
            {
                "security_id": security["security_id"],
                "stock_code_5d": security["stock_code_5d"],
                "failure_type": "NOT_APPLICABLE_FUND_CONTROLLED_EXCLUSION",
                "details": str(security.get("security_type", "")),
            }
        )
    pd.DataFrame(failures).to_csv(output / "FMDL5D_FAILURES.csv", index=False, encoding="utf-8-sig")

    equity_count = len(equity_securities)
    metrics = {
        "source_security_count": len(securities),
        "equity_security_count": equity_count,
        "fund_controlled_exclusion_count": len(fund_securities),
        "structured_statement_security_count": len(structured_success),
        "structured_statement_security_ratio": round(len(structured_success) / equity_count, 6) if equity_count else 0.0,
        "official_financial_disclosure_count": len(assigned_filings),
        "official_financial_disclosure_security_count": len(official_codes),
        "official_financial_disclosure_security_ratio": round(len(official_codes) / equity_count, 6) if equity_count else 0.0,
        "matched_official_disclosure_count": sum(bool(row.get("report_period_end")) for row in assigned_filings),
        "unmatched_official_disclosure_count": sum(not bool(row.get("report_period_end")) for row in assigned_filings),
        "mapped_raw_fact_count": len(raw),
        "normalized_fact_count": len(normalized),
        "decision_grade_fact_count": int(normalized["decision_grade_eligible"].sum()) if not normalized.empty else 0,
        "decision_grade_security_count": len(decision_grade_securities),
        "decision_grade_security_ratio": round(len(decision_grade_securities) / equity_count, 6) if equity_count else 0.0,
        "unmapped_field_catalog_count": len(unmapped_catalog),
        "duplicate_fact_key_count": duplicate_fact_keys,
        "invalid_numeric_row_count": invalid_numeric,
        "future_available_row_count": future_available,
        "decision_grade_missing_lineage_count": missing_lineage,
        "balance_sheet_tie_out_checked_count": tie_out_checked,
        "balance_sheet_tie_out_failed_count": tie_out_failed,
        "structured_failure_security_count": equity_count - len(structured_success),
        "hkex_chunk_warning_count": len(hkex_warnings),
        "market_max_date": market_max_date.isoformat(),
    }

    acceptance = contract["acceptance"]
    hard_failures: list[str] = []
    if metrics["source_security_count"] != acceptance["expected_security_count"]:
        hard_failures.append("SOURCE_SECURITY_COUNT_MISMATCH")
    if metrics["equity_security_count"] < acceptance["minimum_equity_count"]:
        hard_failures.append("EQUITY_SECURITY_COUNT_BELOW_MINIMUM")
    if metrics["structured_statement_security_ratio"] < acceptance["minimum_structured_statement_security_ratio"]:
        hard_failures.append("STRUCTURED_STATEMENT_COVERAGE_BELOW_MINIMUM")
    if metrics["official_financial_disclosure_security_ratio"] < acceptance["minimum_official_financial_disclosure_security_ratio"]:
        hard_failures.append("OFFICIAL_DISCLOSURE_COVERAGE_BELOW_MINIMUM")
    if metrics["decision_grade_security_ratio"] < acceptance["minimum_decision_grade_security_ratio"]:
        hard_failures.append("DECISION_GRADE_SECURITY_COVERAGE_BELOW_MINIMUM")
    if metrics["normalized_fact_count"] < acceptance["minimum_normalized_fact_count"]:
        hard_failures.append("NORMALIZED_FACT_COUNT_BELOW_MINIMUM")
    if metrics["duplicate_fact_key_count"] > acceptance["maximum_duplicate_fact_keys"]:
        hard_failures.append("DUPLICATE_NORMALIZED_FACT_KEYS")
    if metrics["future_available_row_count"] > acceptance["maximum_future_available_rows"]:
        hard_failures.append("FUTURE_INFORMATION_LEAKAGE")
    if metrics["invalid_numeric_row_count"] > acceptance["maximum_invalid_numeric_rows"]:
        hard_failures.append("INVALID_NUMERIC_VALUES")
    if metrics["decision_grade_missing_lineage_count"] > acceptance["maximum_decision_grade_missing_lineage"]:
        hard_failures.append("DECISION_GRADE_LINEAGE_MISSING")

    quality = {
        **metrics,
        "hard_failures": hard_failures,
        "controlled_limitations": [
            "HKEXnews supplies official disclosure identity and timing; structured statement values remain explicitly vendor-tier evidence.",
            "Exact normalized alias mapping leaves unmapped fields null and auditable rather than forcing semantic matches.",
            "Funds and ETFs are controlled not-applicable exclusions from issuer financial normalization.",
            "A filing released on a trading date becomes available only at the next accepted Hong Kong trading-session open.",
        ],
        "hkex_warnings": hkex_warnings,
    }
    write_json(output / "FMDL5D_QUALITY_REPORT.json", quality)

    source_registry = {
        "program_id": "FMDL-5D",
        "generated_at": now_utc(),
        "source_release_id": source_decision["release_id"],
        "field_registry_version": registry_payload["registry_version"],
        "source_routes": contract["source_routes"],
        "hkex_financial_disclosure_scan": {
            "start_date": start_date.isoformat(),
            "end_date": market_max_date.isoformat(),
            "record_count": len(assigned_filings),
            "warnings": hkex_warnings,
        },
        "structured_financial_security_count": len(structured_success),
        "source_hashes_by_security": {
            result["stock_code_5d"]: result["source_hashes"] for result in results if result["source_hashes"]
        },
        "trade_authority": "NONE",
    }
    write_json(output / "FMDL5D_SOURCE_REGISTRY.json", source_registry)

    primary_files = [
        "FMDL5D_HKEX_FINANCIAL_DISCLOSURES.csv",
        "FMDL5D_MAPPED_RAW_FACTS.parquet",
        "FMDL5D_NORMALIZED_FINANCIAL_FACTS.parquet",
        "FMDL5D_ISSUER_FINANCIAL_CURRENT.csv",
        "FMDL5D_UNMAPPED_FIELD_CATALOG.csv",
        "FMDL5D_FAILURES.csv",
        "FMDL5D_QUALITY_REPORT.json",
        "FMDL5D_SOURCE_REGISTRY.json",
    ]
    data_hashes = {name: file_sha256(output / name) for name in primary_files}
    canonical_sha256 = stable_hash(
        {
            "program_id": "FMDL-5D",
            "source_release_id": source_decision["release_id"],
            "metrics": metrics,
            "data_hashes": data_hashes,
            "contract_version": contract["contract_version"],
            "registry_version": registry_payload["registry_version"],
        }
    )
    release_id = f"FMDL5D_{market_max_date.strftime('%Y%m%d')}_{canonical_sha256[:12]}"
    status = "FMDL5D_HKEX_DISCLOSURE_AND_FINANCIAL_NORMALIZATION_ACCEPTED_WITH_CONTROLLED_QUARANTINE" if not hard_failures else "FMDL5D_REJECTED"
    decision = {
        "program_id": "FMDL-5D",
        "status": status,
        "authority": contract["authority"],
        "trade_authority": "NONE",
        "release_id": release_id,
        "release_sequence": 14,
        "source_release_id": source_decision["release_id"],
        "canonical_sha256": canonical_sha256,
        "hard_failures": hard_failures,
        "metrics": metrics,
        "limitations": quality["controlled_limitations"],
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "next_gate": contract["publication"]["next_gate"],
    }
    write_json(output / "FMDL5D_DECISION.json", decision)

    manifest_files = primary_files + ["FMDL5D_DECISION.json"]
    manifest = {
        "program_id": "FMDL-5D",
        "release_id": release_id,
        "release_sequence": 14,
        "source_release_id": source_decision["release_id"],
        "canonical_sha256": canonical_sha256,
        "generated_at_utc": now_utc(),
        "files": {
            name: {"sha256": file_sha256(output / name), "size_bytes": (output / name).stat().st_size}
            for name in manifest_files
        },
    }
    write_json(output / "FMDL5D_MANIFEST.json", manifest)
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not hard_failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
