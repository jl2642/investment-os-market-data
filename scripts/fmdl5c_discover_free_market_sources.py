#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

SAMPLE_CODES = ["00005", "00700", "02800", "09988"]
HKMA_URL = "https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/er-eeri-daily"
HKEX_NEWLY_LISTED = "https://www.hkex.com.hk/Services/Trading/Securities/Trading-News/Newly-Listed-Securities?sc_lang=en"
HKEX_FULL_LIST = "https://www.hkex.com.hk/eng/services/trading/securities/securitieslists/ListOfSecurities.xlsx"
EASTMONEY_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def yahoo_symbol(code5: str) -> str:
    return f"{int(code5):04d}.HK"


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; InvestmentOS/5C; +https://github.com/jl2642/investment-os-market-data)",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            "Referer": "https://quote.eastmoney.com/",
        }
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    s.mount("https://", adapter)
    return s


def fetch(s: requests.Session, url: str, timeout: int = 90, params: dict[str, str] | None = None) -> requests.Response:
    last: Exception | None = None
    for attempt in range(5):
        try:
            response = s.get(url, params=params, timeout=(15, timeout), allow_redirects=True)
            response.raise_for_status()
            return response
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(min(16, 2**attempt))
    assert last is not None
    raise last


def yahoo_probe(s: requests.Session, code5: str) -> dict[str, object]:
    symbol = yahoo_symbol(code5)
    period2 = int(datetime.now(timezone.utc).timestamp()) + 86400
    period1 = period2 - 40 * 86400
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol)}"
        f"?period1={period1}&period2={period2}&interval=1d&events=div%2Csplits"
    )
    response = fetch(s, url)
    payload = response.json()
    chart = payload.get("chart") or {}
    result = (chart.get("result") or [None])[0]
    if not result:
        raise ValueError(f"YAHOO_EMPTY_RESULT:{symbol}:{chart.get('error')}")
    timestamps = result.get("timestamp") or []
    quote_rows = (((result.get("indicators") or {}).get("quote") or [{}])[0])
    events = result.get("events") or {}
    return {
        "code5": code5,
        "symbol": symbol,
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


def eastmoney_probe(s: requests.Session, code5: str) -> dict[str, object]:
    params = {
        "secid": f"116.{code5}",
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "0",
        "beg": "20260601",
        "end": "20500000",
        "lmt": "100",
    }
    response = fetch(s, EASTMONEY_URL, params=params)
    payload = response.json()
    data = payload.get("data") or {}
    klines = data.get("klines") or []
    return {
        "code5": code5,
        "url": response.url,
        "status_code": response.status_code,
        "response_sha256": sha256(response.content),
        "name": data.get("name"),
        "code": data.get("code"),
        "row_count": len(klines),
        "latest_row": klines[-1] if klines else None,
    }


def hkma_probe(s: requests.Session) -> dict[str, object]:
    response = fetch(s, HKMA_URL, params={"offset": "0"})
    payload = response.json()
    result = payload.get("result") or {}
    records = result.get("records") or []
    return {
        "url": response.url,
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
        "eastmoney": {},
        "official": {},
        "hard_failures": [],
    }

    for code5 in SAMPLE_CODES:
        for provider, fn in (("yahoo", yahoo_probe), ("eastmoney", eastmoney_probe)):
            try:
                discovery[provider][code5] = fn(s, code5)  # type: ignore[index]
            except Exception as exc:  # noqa: BLE001
                discovery[provider][code5] = {"error": f"{type(exc).__name__}: {exc}"}  # type: ignore[index]

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

    yahoo_success = sum(1 for row in discovery["yahoo"].values() if row.get("close_count", 0) > 0)  # type: ignore[union-attr]
    eastmoney_success = sum(1 for row in discovery["eastmoney"].values() if row.get("row_count", 0) > 0)  # type: ignore[union-attr]
    discovery["decision"] = {
        "yahoo_sample_success_count": yahoo_success,
        "eastmoney_sample_success_count": eastmoney_success,
        "hkma_success": "error" not in discovery["official"].get("hkma_fx", {}),  # type: ignore[union-attr]
        "recommended_price_primary": "YAHOO" if yahoo_success >= 3 else "EASTMONEY",
        "recommended_price_fallback": "EASTMONEY" if eastmoney_success >= 2 else "NONE",
        "stooq_rejected_reason": "BROWSER_CHALLENGE_ON_GITHUB_RUNNER",
    }
    (out / "FMDL5C_SOURCE_DISCOVERY.json").write_text(
        json.dumps(discovery, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(discovery, ensure_ascii=False, indent=2))
    if yahoo_success == 0 and eastmoney_success == 0:
        return 2
    if "error" in discovery["official"].get("hkma_fx", {}):  # type: ignore[union-attr]
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
