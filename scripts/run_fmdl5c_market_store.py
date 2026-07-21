#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import pandas as pd
import requests

PROGRAM_ID = "FMDL-5C"
SOURCE_RELEASE_ID = "FMDL5B2_20260721_752db2c65820"
SOURCE_PATH = Path("outputs/fmdl5b2/current/FMDL5B2_SECURITY_SEMANTIC_OVERLAY.csv")
CONTRACT_PATH = Path("config/fmdl5c_price_volume_corporate_action_fx_contract.json")
HKMA_URL = "https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/er-eeri-daily"
HKEX_NEWLY_LISTED = "https://www.hkex.com.hk/Services/Trading/Securities/Trading-News/Newly-Listed-Securities?sc_lang=en"
EASTMONEY_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
HK_TZ = ZoneInfo("Asia/Hong_Kong")
_thread = threading.local()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def code5(value: object) -> str:
    return str(value or "").strip().zfill(5)


def yahoo_symbol(code: str) -> str:
    return f"{int(code):04d}.HK"


def finite_number(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def get_session() -> requests.Session:
    session = getattr(_thread, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; InvestmentOS/5C; +https://github.com/jl2642/investment-os-market-data)",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
                "Referer": "https://quote.eastmoney.com/",
            }
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=2)
        session.mount("https://", adapter)
        _thread.session = session
    return session


def request(url: str, *, params: dict[str, str] | None = None, timeout: int = 120) -> requests.Response:
    last: Exception | None = None
    for attempt in range(5):
        try:
            response = get_session().get(url, params=params, timeout=(15, timeout), allow_redirects=True)
            response.raise_for_status()
            return response
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(min(16, 2**attempt))
    assert last is not None
    raise last


def parse_yahoo_payload(
    *, security_id: str, code: str, payload: dict[str, object], response_sha256: str, retrieved_at_utc: str
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    chart = payload.get("chart") or {}
    result = ((chart.get("result") or [None])[0]) if isinstance(chart, dict) else None
    if not isinstance(result, dict):
        raise ValueError(f"YAHOO_EMPTY_RESULT:{code}:{chart.get('error') if isinstance(chart, dict) else ''}")
    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators") or {}
    quote_block = ((indicators.get("quote") or [{}])[0]) if isinstance(indicators, dict) else {}
    adj_block = ((indicators.get("adjclose") or [{}])[0]) if isinstance(indicators, dict) else {}
    meta = result.get("meta") or {}
    currency = str(meta.get("currency") or "HKD")
    opens = quote_block.get("open") or []
    highs = quote_block.get("high") or []
    lows = quote_block.get("low") or []
    closes = quote_block.get("close") or []
    volumes = quote_block.get("volume") or []
    adj_closes = adj_block.get("adjclose") or []
    rows: list[dict[str, object]] = []
    for idx, ts in enumerate(timestamps):
        close = finite_number(closes[idx] if idx < len(closes) else None)
        if close is None:
            continue
        observation_date = datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(HK_TZ).date().isoformat()
        rows.append(
            {
                "security_id": security_id,
                "stock_code_5d": code,
                "provider_ticker": yahoo_symbol(code),
                "observation_date": observation_date,
                "open": finite_number(opens[idx] if idx < len(opens) else None),
                "high": finite_number(highs[idx] if idx < len(highs) else None),
                "low": finite_number(lows[idx] if idx < len(lows) else None),
                "close": close,
                "adj_close": finite_number(adj_closes[idx] if idx < len(adj_closes) else None),
                "volume": int(volumes[idx]) if idx < len(volumes) and volumes[idx] is not None else None,
                "turnover": None,
                "currency": currency,
                "provider": "YAHOO_CHART",
                "source_tier": "UNOFFICIAL_FREE_VENDOR",
                "retrieved_at_utc": retrieved_at_utc,
                "source_response_sha256": response_sha256,
            }
        )
    actions: list[dict[str, object]] = []
    events = result.get("events") or {}
    if isinstance(events, dict):
        for raw in (events.get("dividends") or {}).values():
            ts = int(raw.get("date") or 0)
            if not ts:
                continue
            actions.append(
                {
                    "security_id": security_id,
                    "stock_code_5d": code,
                    "action_date": datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(HK_TZ).date().isoformat(),
                    "action_type": "CASH_DIVIDEND",
                    "cash_amount": finite_number(raw.get("amount")),
                    "currency": currency,
                    "split_numerator": None,
                    "split_denominator": None,
                    "related_stock_code": "",
                    "provider": "YAHOO_CHART_EVENTS",
                    "source_tier": "UNOFFICIAL_FREE_VENDOR",
                    "retrieved_at_utc": retrieved_at_utc,
                    "source_response_sha256": response_sha256,
                    "evidence_detail": str(raw.get("formatted_date") or ""),
                }
            )
        for raw in (events.get("splits") or {}).values():
            ts = int(raw.get("date") or 0)
            if not ts:
                continue
            numerator = finite_number(raw.get("numerator"))
            denominator = finite_number(raw.get("denominator"))
            actions.append(
                {
                    "security_id": security_id,
                    "stock_code_5d": code,
                    "action_date": datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(HK_TZ).date().isoformat(),
                    "action_type": "STOCK_SPLIT_OR_CONSOLIDATION",
                    "cash_amount": None,
                    "currency": currency,
                    "split_numerator": numerator,
                    "split_denominator": denominator,
                    "related_stock_code": "",
                    "provider": "YAHOO_CHART_EVENTS",
                    "source_tier": "UNOFFICIAL_FREE_VENDOR",
                    "retrieved_at_utc": retrieved_at_utc,
                    "source_response_sha256": response_sha256,
                    "evidence_detail": str(raw.get("splitRatio") or ""),
                }
            )
    summary = {
        "provider": "YAHOO_CHART",
        "provider_ticker": yahoo_symbol(code),
        "row_count": len(rows),
        "action_count": len(actions),
        "currency": currency,
        "first_date": rows[0]["observation_date"] if rows else None,
        "latest_date": rows[-1]["observation_date"] if rows else None,
        "response_sha256": response_sha256,
    }
    return rows, actions, summary


def fetch_yahoo(security_id: str, code: str, start_date: str, end_date: str, retrieved_at_utc: str):
    start_ts = int(datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc).timestamp())
    end_ts = int((datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc) + timedelta(days=2)).timestamp())
    symbol = yahoo_symbol(code)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol)}"
        f"?period1={start_ts}&period2={end_ts}&interval=1d&events=div%2Csplits"
    )
    response = request(url)
    return parse_yahoo_payload(
        security_id=security_id,
        code=code,
        payload=response.json(),
        response_sha256=sha256_bytes(response.content),
        retrieved_at_utc=retrieved_at_utc,
    )


def parse_eastmoney_klines(
    *, security_id: str, code: str, payload: dict[str, object], response_sha256: str, retrieved_at_utc: str
) -> tuple[list[dict[str, object]], dict[str, object]]:
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        data = {}
    klines = data.get("klines") or []
    rows: list[dict[str, object]] = []
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 7:
            continue
        rows.append(
            {
                "security_id": security_id,
                "stock_code_5d": code,
                "provider_ticker": f"116.{code}",
                "observation_date": parts[0],
                "open": finite_number(parts[1]),
                "high": finite_number(parts[3]),
                "low": finite_number(parts[4]),
                "close": finite_number(parts[2]),
                "adj_close": None,
                "volume": int(float(parts[5])) if parts[5] else None,
                "turnover": finite_number(parts[6]),
                "currency": "HKD",
                "provider": "EASTMONEY_PUSH2HIS",
                "source_tier": "UNOFFICIAL_FREE_VENDOR",
                "retrieved_at_utc": retrieved_at_utc,
                "source_response_sha256": response_sha256,
            }
        )
    summary = {
        "provider": "EASTMONEY_PUSH2HIS",
        "provider_ticker": f"116.{code}",
        "row_count": len(rows),
        "action_count": 0,
        "currency": "HKD",
        "first_date": rows[0]["observation_date"] if rows else None,
        "latest_date": rows[-1]["observation_date"] if rows else None,
        "response_sha256": response_sha256,
    }
    return rows, summary


def fetch_eastmoney(security_id: str, code: str, start_date: str, retrieved_at_utc: str):
    params = {
        "secid": f"116.{code}",
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "0",
        "beg": start_date.replace("-", ""),
        "end": "20500000",
        "lmt": "100000",
    }
    response = request(EASTMONEY_URL, params=params)
    return parse_eastmoney_klines(
        security_id=security_id,
        code=code,
        payload=response.json(),
        response_sha256=sha256_bytes(response.content),
        retrieved_at_utc=retrieved_at_utc,
    )


def fetch_one_security(source: dict[str, str], start_date: str, end_date: str, retrieved_at_utc: str):
    security_id = source["security_id"]
    code = code5(source["stock_code_5d"])
    errors: list[str] = []
    try:
        rows, actions, summary = fetch_yahoo(security_id, code, start_date, end_date, retrieved_at_utc)
        if len(rows) >= 5:
            return rows, actions, summary, errors
        errors.append(f"YAHOO_INSUFFICIENT_ROWS:{len(rows)}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"YAHOO:{type(exc).__name__}:{exc}")
    try:
        rows, summary = fetch_eastmoney(security_id, code, start_date, retrieved_at_utc)
        if len(rows) >= 5:
            return rows, [], summary, errors
        errors.append(f"EASTMONEY_INSUFFICIENT_ROWS:{len(rows)}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"EASTMONEY:{type(exc).__name__}:{exc}")
    return [], [], {"provider": "NONE", "provider_ticker": "", "row_count": 0, "action_count": 0}, errors


def fetch_hkma_fx(start_date: str, retrieved_at_utc: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows: list[dict[str, object]] = []
    response_hashes: list[str] = []
    offset = 0
    while offset < 5000:
        response = request(HKMA_URL, params={"offset": str(offset)})
        response_hashes.append(sha256_bytes(response.content))
        payload = response.json()
        result = payload.get("result") or {}
        records = result.get("records") or []
        if not records:
            break
        oldest = None
        for record in records:
            observation_date = str(record.get("end_of_day") or "")
            if not observation_date:
                continue
            oldest = observation_date
            if observation_date < start_date:
                continue
            rows.append(
                {
                    "observation_date": observation_date,
                    "hkd_per_usd": finite_number(record.get("usd")),
                    "hkd_per_cny": finite_number(record.get("cny")),
                    "provider": "HKMA_ER_EERI_DAILY",
                    "source_tier": "OFFICIAL_OPEN_API",
                    "retrieved_at_utc": retrieved_at_utc,
                    "source_page_sha256": response_hashes[-1],
                }
            )
        if oldest and oldest < start_date:
            break
        offset += len(records)
    dedup = {row["observation_date"]: row for row in rows}
    final = [dedup[key] for key in sorted(dedup)]
    return final, {
        "provider": "HKMA_ER_EERI_DAILY",
        "page_count": len(response_hashes),
        "row_count": len(final),
        "first_date": final[0]["observation_date"] if final else None,
        "latest_date": final[-1]["observation_date"] if final else None,
        "page_sha256": response_hashes,
    }


def fetch_hkex_current_actions(universe_codes: set[str], retrieved_at_utc: str):
    response = request(HKEX_NEWLY_LISTED)
    response_hash = sha256_bytes(response.content)
    actions: list[dict[str, object]] = []
    warning = ""
    try:
        tables = pd.read_html(io.BytesIO(response.content))
        for table in tables:
            flat = [" ".join(str(x) for x in col if str(x) != "nan") if isinstance(col, tuple) else str(col) for col in table.columns]
            table.columns = flat
            code_col = next((col for col in table.columns if "Stock Code" in col and "Related" not in col), None)
            action_col = next((col for col in table.columns if "Corporate Action" in col), None)
            related_col = next((col for col in table.columns if "Related Stock Code" in col), None)
            date_col = next((col for col in table.columns if "Date of Listing" in col), None)
            if not code_col or not action_col:
                continue
            for _, row in table.iterrows():
                raw_code = str(row.get(code_col, "")).replace(".0", "").strip()
                if not raw_code.isdigit():
                    continue
                code = code5(raw_code)
                related = str(row.get(related_col, "") if related_col else "").replace(".0", "").strip()
                related_code = code5(related) if related.isdigit() else ""
                action = str(row.get(action_col, "") or "").strip()
                if not action or action.lower() == "nan":
                    continue
                if code not in universe_codes and related_code not in universe_codes:
                    continue
                raw_date = str(row.get(date_col, "") if date_col else "").replace("*", "").strip()
                parsed_date = pd.to_datetime(raw_date, errors="coerce", dayfirst=True)
                action_date = parsed_date.date().isoformat() if not pd.isna(parsed_date) else ""
                anchor_code = related_code if related_code in universe_codes else code
                actions.append(
                    {
                        "security_id": f"HKEX:{anchor_code}",
                        "stock_code_5d": anchor_code,
                        "action_date": action_date,
                        "action_type": "HKEX_CURRENT_LISTING_OR_CORPORATE_ACTION",
                        "cash_amount": None,
                        "currency": "",
                        "split_numerator": None,
                        "split_denominator": None,
                        "related_stock_code": code if anchor_code == related_code else related_code,
                        "provider": "HKEX_NEWLY_LISTED_SECURITIES",
                        "source_tier": "OFFICIAL_CURRENT_EVENT",
                        "retrieved_at_utc": retrieved_at_utc,
                        "source_response_sha256": response_hash,
                        "evidence_detail": action,
                    }
                )
    except Exception as exc:  # noqa: BLE001
        warning = f"HKEX_CURRENT_ACTION_PARSE:{type(exc).__name__}:{exc}"
    return actions, {
        "provider": "HKEX_NEWLY_LISTED_SECURITIES",
        "row_count": len(actions),
        "response_sha256": response_hash,
        "warning": warning,
    }


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    start_date = contract["history"]["start_date"]
    end_date = date.today().isoformat()
    retrieved_at_utc = datetime.now(timezone.utc).isoformat()
    with SOURCE_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        securities = list(csv.DictReader(handle))
    if len(securities) != int(contract["universe"]["security_count"]):
        raise ValueError(f"SOURCE_SECURITY_COUNT:{len(securities)}")

    price_rows: list[dict[str, object]] = []
    action_rows: list[dict[str, object]] = []
    provider_summaries: dict[str, dict[str, object]] = {}
    failure_rows: list[dict[str, object]] = []
    workers = int(os.environ.get("FMDL5C_WORKERS", "10"))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(fetch_one_security, source, start_date, end_date, retrieved_at_utc): source
            for source in securities
        }
        for future in as_completed(futures):
            source = futures[future]
            code = code5(source["stock_code_5d"])
            try:
                rows, actions, summary, errors = future.result()
            except Exception as exc:  # noqa: BLE001
                rows, actions, summary, errors = [], [], {"provider": "NONE", "row_count": 0}, [f"UNHANDLED:{type(exc).__name__}:{exc}"]
            price_rows.extend(rows)
            action_rows.extend(actions)
            provider_summaries[code] = summary
            if errors or not rows:
                failure_rows.append(
                    {
                        "security_id": source["security_id"],
                        "stock_code_5d": code,
                        "final_provider": summary.get("provider", "NONE"),
                        "row_count": summary.get("row_count", 0),
                        "errors": " | ".join(errors),
                    }
                )

    universe_codes = {code5(row["stock_code_5d"]) for row in securities}
    hkex_actions, hkex_action_summary = fetch_hkex_current_actions(universe_codes, retrieved_at_utc)
    action_rows.extend(hkex_actions)
    fx_rows, fx_summary = fetch_hkma_fx(start_date, retrieved_at_utc)

    price_df = pd.DataFrame(price_rows)
    if not price_df.empty:
        price_df = price_df.sort_values(["security_id", "observation_date", "provider"]).drop_duplicates(
            ["security_id", "observation_date"], keep="first"
        )
    latest_rows: list[dict[str, object]] = []
    if not price_df.empty:
        latest_df = price_df.sort_values(["security_id", "observation_date"]).groupby("security_id", as_index=False).tail(1)
        latest_rows = latest_df.to_dict("records")
    action_df = pd.DataFrame(action_rows)
    if not action_df.empty:
        action_df = action_df.sort_values(["security_id", "action_date", "action_type", "provider"]).drop_duplicates(
            ["security_id", "action_date", "action_type", "provider", "evidence_detail"], keep="first"
        )
        action_rows = action_df.to_dict("records")

    parquet_path = output / "FMDL5C_DAILY_PRICE_VOLUME.parquet"
    price_df.to_parquet(parquet_path, index=False, compression="zstd")
    write_csv(output / "FMDL5C_LATEST_PRICE_SNAPSHOT.csv", latest_rows)
    write_csv(output / "FMDL5C_CORPORATE_ACTIONS.csv", action_rows)
    write_csv(output / "FMDL5C_FX_DAILY.csv", fx_rows)
    write_csv(output / "FMDL5C_FAILURES.csv", failure_rows, ["security_id", "stock_code_5d", "final_provider", "row_count", "errors"])
    (output / "FMDL5C_LATEST_PRICE_SNAPSHOT.ndjson").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in latest_rows),
        encoding="utf-8",
    )

    by_security = price_df.groupby("security_id").size().to_dict() if not price_df.empty else {}
    latest_by_security = {str(row["security_id"]): str(row["observation_date"]) for row in latest_rows}
    max_market_date = max(latest_by_security.values()) if latest_by_security else ""
    max_market_day = date.fromisoformat(max_market_date) if max_market_date else None
    recent_security_count = sum(
        1
        for latest in latest_by_security.values()
        if max_market_day and (max_market_day - date.fromisoformat(latest)).days <= contract["acceptance"]["latest_price_max_age_calendar_days"]
    )
    historical_security_count = sum(1 for count in by_security.values() if count >= 20)
    duplicate_count = int(price_df.duplicated(["security_id", "observation_date"]).sum()) if not price_df.empty else 0
    invalid_price_count = 0
    invalid_volume_count = 0
    if not price_df.empty:
        for field in ["open", "high", "low", "close", "adj_close"]:
            if field in price_df:
                invalid_price_count += int((pd.to_numeric(price_df[field], errors="coerce") < 0).sum())
        invalid_volume_count = int((pd.to_numeric(price_df["volume"], errors="coerce") < 0).sum())
    latest_ratio = recent_security_count / len(securities)
    historical_ratio = historical_security_count / len(securities)
    fx_latest_date = fx_rows[-1]["observation_date"] if fx_rows else ""
    fx_age = (date.today() - date.fromisoformat(str(fx_latest_date))).days if fx_latest_date else 9999

    source_registry = {
        "program_id": PROGRAM_ID,
        "source_release_id": SOURCE_RELEASE_ID,
        "generated_at_utc": retrieved_at_utc,
        "price_provider_policy": contract["source_policy"]["price_volume"],
        "corporate_action_policy": contract["source_policy"]["corporate_actions"],
        "fx_policy": contract["source_policy"]["fx"],
        "security_provider_summaries": provider_summaries,
        "hkex_current_action_summary": hkex_action_summary,
        "fx_summary": fx_summary,
    }
    quality = {
        "source_security_count": len(securities),
        "price_row_count": int(len(price_df)),
        "latest_snapshot_count": len(latest_rows),
        "recent_security_count": recent_security_count,
        "latest_price_success_ratio": round(latest_ratio, 6),
        "historical_security_count": historical_security_count,
        "historical_price_success_ratio": round(historical_ratio, 6),
        "max_market_date": max_market_date,
        "yahoo_security_count": sum(1 for row in provider_summaries.values() if row.get("provider") == "YAHOO_CHART"),
        "eastmoney_fallback_security_count": sum(1 for row in provider_summaries.values() if row.get("provider") == "EASTMONEY_PUSH2HIS"),
        "failed_security_count": sum(1 for row in provider_summaries.values() if row.get("provider") == "NONE"),
        "corporate_action_count": len(action_rows),
        "hkex_official_current_action_count": hkex_action_summary["row_count"],
        "fx_row_count": len(fx_rows),
        "fx_latest_date": fx_latest_date,
        "fx_latest_age_calendar_days": fx_age,
        "duplicate_security_date_count": duplicate_count,
        "invalid_price_count": invalid_price_count,
        "invalid_volume_count": invalid_volume_count,
    }
    hard_failures: list[str] = []
    acceptance = contract["acceptance"]
    if latest_ratio < acceptance["latest_price_success_ratio_min"]:
        hard_failures.append(f"LATEST_PRICE_COVERAGE:{latest_ratio:.6f}")
    if historical_ratio < acceptance["historical_price_success_ratio_min"]:
        hard_failures.append(f"HISTORICAL_PRICE_COVERAGE:{historical_ratio:.6f}")
    if duplicate_count:
        hard_failures.append(f"DUPLICATE_SECURITY_DATE:{duplicate_count}")
    if invalid_price_count:
        hard_failures.append(f"NEGATIVE_PRICE:{invalid_price_count}")
    if invalid_volume_count:
        hard_failures.append(f"NEGATIVE_VOLUME:{invalid_volume_count}")
    if len(fx_rows) < acceptance["fx_row_count_min"]:
        hard_failures.append(f"FX_ROW_COUNT:{len(fx_rows)}")
    if fx_age > acceptance["fx_latest_max_age_calendar_days"]:
        hard_failures.append(f"FX_STALE:{fx_age}")
    decision = {
        "program_id": PROGRAM_ID,
        "source_release_id": SOURCE_RELEASE_ID,
        "release_sequence": contract["release_sequence"],
        "status": "FMDL5C_PRICE_VOLUME_CORPORATE_ACTION_AND_FX_STORE_ACCEPTED" if not hard_failures else "FMDL5C_REJECTED",
        "authority": contract["authority"],
        "metrics": quality,
        "hard_failures": hard_failures,
        "limitations": [
            "HKEX official bulk day-end and historical price files are paid products; free price history is vendor-tier evidence.",
            "Yahoo dividend and split events are not a substitute for issuer disclosure review in FMDL-5D.",
            "Corporate-action adjustment factors must preserve raw and vendor-adjusted prices separately.",
        ],
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "trade_authority": "NONE",
        "next_gate": contract["next_gate"],
    }
    (output / "FMDL5C_SOURCE_REGISTRY.json").write_text(json.dumps(source_registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "FMDL5C_QUALITY_REPORT.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "FMDL5C_DECISION.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest_files: dict[str, dict[str, object]] = {}
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name != "FMDL5C_MANIFEST.json":
            manifest_files[path.name] = {"size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
    canonical_material = json.dumps(manifest_files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    canonical_sha = sha256_bytes(canonical_material)
    release_id = f"FMDL5C_{date.today().strftime('%Y%m%d')}_{canonical_sha[:12]}"
    decision["release_id"] = release_id
    decision["canonical_sha256"] = canonical_sha
    (output / "FMDL5C_DECISION.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_files["FMDL5C_DECISION.json"] = {
        "size_bytes": (output / "FMDL5C_DECISION.json").stat().st_size,
        "sha256": sha256_file(output / "FMDL5C_DECISION.json"),
    }
    manifest = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": contract["release_sequence"],
        "canonical_sha256": canonical_sha,
        "source_release_id": SOURCE_RELEASE_ID,
        "generated_at_utc": retrieved_at_utc,
        "files": manifest_files,
    }
    (output / "FMDL5C_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    if hard_failures:
        raise SystemExit(2)
    return decision


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        shutil.rmtree(output)
    build(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
