#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests

SAMPLE_TICKERS = ["00005.HK", "00700.HK", "02800.HK", "09988.HK"]
HKMA_URL = "https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/er-eeri-daily"
HKEX_NEWLY_LISTED = "https://www.hkex.com.hk/Services/Trading/Securities/Trading-News/Newly-Listed-Securities?sc_lang=en"
HKEX_FULL_LIST = "https://www.hkex.com.hk/eng/services/trading/securities/securitieslists/ListOfSecurities.xlsx"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; InvestmentOS/5C; +https://github.com/jl2642/investment-os-market-data)",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        }
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    s.mount("https://", adapter)
    return s


def fetch(s: requests.Session, url: str, timeout: int = 90) -> requests.Response:
    last: Exception | None = None
    for attempt in range(5):
        try:
            response = s.get(url, timeout=(15, timeout), allow_redirects=True)
            response.raise_for_status()
            return response
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(min(16, 2**attempt))
    assert last is not None
    raise last


def yahoo_probe(s: requests.Session, ticker: str) -> dict[str, object]:
    period2 = int(datetime.now(timezone.utc).timestamp()) + 86400
    period1 = period2 - 40 * 86400
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker)}"
        f"?period1={period1}&period2={period2}&interval=1d&events=div%2Csplits"
    )
    response = fetch(s, url)
    payload = response.json()
    chart = payload.get("chart") or {}
    result = (chart.get("result") or [None])[0]
    if not result:
        raise ValueError(f"YAHOO_EMPTY_RESULT:{ticker}:{chart.get('error')}")
    timestamps = result.get("timestamp") or []
    quote_rows = (((result.get("indicators") or {}).get("quote") or [{}])[0])
    events = result.get("events") or {}
    return {
        "ticker": ticker,
        "url": url,
        "status_code": response.status_code,
        "response_sha256": sha256(response.content),
        "currency": ((result.get("meta") or {}).get("currency")),
        "exchange_timezone_name": ((result.get("meta") or {}).get("exchangeTimezoneName")),
        "timestamp_count": len(timestamps),
        "close_count": len([x for x in (quote_rows.get("close") or []) if x is not None]),
        "dividend_event_count": len(events.get("dividends") or {}),
        "split_event_count": len(events.get("splits") or {}),
        "latest_timestamp": max(timestamps) if timestamps else None,
    }


def stooq_probe(s: requests.Session, ticker: str) -> dict[str, object]:
    symbol = ticker.replace(".HK", ".hk").lstrip("0") or "0.hk"
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=40)
    url = (
        "https://stooq.com/q/d/l/"
        f"?s={quote(symbol)}&d1={start.strftime('%Y%m%d')}&d2={end.strftime('%Y%m%d')}&i=d"
    )
    response = fetch(s, url)
    text = response.text
    rows = list(csv.DictReader(io.StringIO(text))) if "Date" in text[:100] else []
    return {
        "ticker": ticker,
        "stooq_symbol": symbol,
        "url": url,
        "status_code": response.status_code,
        "response_sha256": sha256(response.content),
        "row_count": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "latest_date": rows[-1].get("Date") if rows else None,
        "preview": rows[-3:] if rows else text[:300],
    }


def hkma_probe(s: requests.Session) -> dict[str, object]:
    url = f"{HKMA_URL}?offset=0"
    response = fetch(s, url)
    payload = response.json()
    result = payload.get("result") or {}
    records = result.get("records") or []
    return {
        "url": url,
        "status_code": response.status_code,
        "response_sha256": sha256(response.content),
        "record_count": len(records),
        "fields": sorted(records[0].keys()) if records else [],
        "first_record": records[0] if records else None,
        "header": result.get("header"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    s = session()
    discovery: dict[str, object] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "yahoo": {},
        "stooq": {},
        "official": {},
        "hard_failures": [],
    }

    for ticker in SAMPLE_TICKERS:
        for provider, fn in (("yahoo", yahoo_probe), ("stooq", stooq_probe)):
            try:
                discovery[provider][ticker] = fn(s, ticker)  # type: ignore[index]
            except Exception as exc:  # noqa: BLE001
                discovery[provider][ticker] = {"error": f"{type(exc).__name__}: {exc}"}  # type: ignore[index]

    official_sources = {
        "hkma_fx": (HKMA_URL, hkma_probe),
        "hkex_newly_listed": (HKEX_NEWLY_LISTED, None),
        "hkex_full_list": (HKEX_FULL_LIST, None),
    }
    for key, (url, parser_fn) in official_sources.items():
        try:
            if parser_fn:
                discovery["official"][key] = parser_fn(s)  # type: ignore[index]
            else:
                response = fetch(s, url)
                suffix = ".xlsx" if "xlsx" in response.url.lower() else ".html"
                target = raw / f"{key}{suffix}"
                target.write_bytes(response.content)
                discovery["official"][key] = {  # type: ignore[index]
                    "url": response.url,
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "size_bytes": len(response.content),
                    "response_sha256": sha256(response.content),
                    "file": str(target.relative_to(out)),
                }
        except Exception as exc:  # noqa: BLE001
            discovery["official"][key] = {"url": url, "error": f"{type(exc).__name__}: {exc}"}  # type: ignore[index]
            discovery["hard_failures"].append(key)  # type: ignore[union-attr]

    yahoo_success = sum(1 for row in discovery["yahoo"].values() if "error" not in row)  # type: ignore[union-attr]
    stooq_success = sum(1 for row in discovery["stooq"].values() if row.get("row_count", 0) > 0)  # type: ignore[union-attr]
    discovery["decision"] = {
        "yahoo_sample_success_count": yahoo_success,
        "stooq_sample_success_count": stooq_success,
        "hkma_success": "error" not in discovery["official"].get("hkma_fx", {}),  # type: ignore[union-attr]
        "recommended_price_primary": "YAHOO" if yahoo_success >= 3 else "STOOQ",
        "recommended_price_fallback": "STOOQ" if stooq_success >= 2 else "NONE",
    }
    (out / "FMDL5C_SOURCE_DISCOVERY.json").write_text(
        json.dumps(discovery, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(discovery, ensure_ascii=False, indent=2))
    if yahoo_success == 0 and stooq_success == 0:
        return 2
    if "error" in discovery["official"].get("hkma_fx", {}):  # type: ignore[union-attr]
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
