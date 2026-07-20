#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

SH_TZ = ZoneInfo("Asia/Shanghai")
EASTMONEY_HOSTS = [
    "https://push2.eastmoney.com",
    "https://82.push2.eastmoney.com",
    "https://7.push2.eastmoney.com",
]
QUOTE_FIELDS = "f12,f14,f2,f3,f4,f5,f6,f15,f16,f17,f18,f124,f13"


@dataclass(frozen=True)
class QuoteRow:
    symbol: str
    name: str
    market: str
    asset_type: str
    quote_date: str
    close: float
    previous_close: float
    open: float
    high: float
    low: float
    pct_change: float
    change_amount: float
    volume: float
    turnover: float
    provider: str
    provider_timestamp: str
    retrieved_at: str
    validation_status: str


@dataclass(frozen=True)
class FundNavRow:
    fund_code: str
    name: str
    nav_date: str
    unit_nav: float
    accumulated_nav: float | None
    daily_growth_pct: float | None
    provider: str
    retrieved_at: str
    validation_status: str


def market_id(symbol: str) -> int:
    return 1 if symbol.startswith(("5", "6", "9")) else 0


def market_name(symbol: str) -> str:
    return "SSE" if market_id(symbol) == 1 else "SZSE"


def get_json(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = session.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("response is not a JSON object")
            return payload
        except Exception as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"request failed after retries: {url}: {last_error}")


def fetch_quotes(
    session: requests.Session,
    symbols: list[dict[str, Any]],
    target_date: date,
) -> tuple[list[QuoteRow], list[str]]:
    secids = ",".join(f"{market_id(row['symbol'])}.{row['symbol']}" for row in symbols)
    payload: dict[str, Any] | None = None
    errors: list[str] = []
    for host in EASTMONEY_HOSTS:
        try:
            payload = get_json(
                session,
                f"{host}/api/qt/ulist.np/get",
                params={
                    "secids": secids,
                    "fields": QUOTE_FIELDS,
                    "fltt": "2",
                    "invt": "2",
                    "ut": "fa5fd1943c7b386f172d6893dbfba10b",
                    "np": "1",
                },
            )
            if payload.get("data", {}).get("diff"):
                break
        except Exception as exc:
            errors.append(f"{host}: {exc}")
            payload = None
    if not payload or not payload.get("data", {}).get("diff"):
        raise RuntimeError("all Eastmoney quote hosts failed: " + " | ".join(errors))

    requested = {row["symbol"]: row for row in symbols}
    result: list[QuoteRow] = []
    seen: set[str] = set()
    retrieved_at = datetime.now(SH_TZ).isoformat(timespec="seconds")
    for item in payload["data"]["diff"]:
        symbol = str(item.get("f12", "")).zfill(6)
        if symbol not in requested:
            continue
        timestamp = int(item.get("f124") or 0)
        if timestamp <= 0:
            errors.append(f"{symbol}: missing provider timestamp")
            continue
        provider_dt = datetime.fromtimestamp(timestamp, SH_TZ)
        quote_date = provider_dt.date()
        close = item.get("f2")
        if close in (None, "-", 0):
            errors.append(f"{symbol}: missing close")
            continue
        validation_status = "PASS" if quote_date == target_date else "FAIL_DATE_MISMATCH"
        if quote_date != target_date:
            errors.append(
                f"{symbol}: quote date {quote_date.isoformat()} != target {target_date.isoformat()}"
            )
        result.append(
            QuoteRow(
                symbol=symbol,
                name=str(item.get("f14") or requested[symbol].get("name") or ""),
                market=market_name(symbol),
                asset_type="ETF" if symbol.startswith(("15", "51")) else "A_SHARE",
                quote_date=quote_date.isoformat(),
                close=float(close),
                previous_close=float(item.get("f18") or 0),
                open=float(item.get("f17") or 0),
                high=float(item.get("f15") or 0),
                low=float(item.get("f16") or 0),
                pct_change=float(item.get("f3") or 0),
                change_amount=float(item.get("f4") or 0),
                volume=float(item.get("f5") or 0),
                turnover=float(item.get("f6") or 0),
                provider="EASTMONEY_QLIST",
                provider_timestamp=provider_dt.isoformat(timespec="seconds"),
                retrieved_at=retrieved_at,
                validation_status=validation_status,
            )
        )
        seen.add(symbol)
    missing = sorted(set(requested) - seen)
    errors.extend(f"{symbol}: missing quote row" for symbol in missing)
    return sorted(result, key=lambda row: row.symbol), errors


def fetch_fund_nav(
    session: requests.Session,
    funds: list[dict[str, Any]],
    target_date: date,
) -> tuple[list[FundNavRow], list[str]]:
    result: list[FundNavRow] = []
    errors: list[str] = []
    retrieved_at = datetime.now(SH_TZ).isoformat(timespec="seconds")
    for fund in funds:
        code = str(fund["fund_code"]).zfill(6)
        try:
            payload = get_json(
                session,
                "https://api.fund.eastmoney.com/f10/lsjz",
                params={
                    "fundCode": code,
                    "pageIndex": "1",
                    "pageSize": "10",
                    "startDate": "",
                    "endDate": target_date.isoformat(),
                },
                headers={
                    "Referer": f"https://fundf10.eastmoney.com/jjjz_{code}.html",
                    "User-Agent": "Mozilla/5.0",
                },
            )
            rows = payload.get("Data", {}).get("LSJZList") or []
            if not rows:
                raise ValueError("no NAV rows")
            selected = next(
                (
                    row
                    for row in rows
                    if date.fromisoformat(row["FSRQ"]) <= target_date
                ),
                None,
            )
            if selected is None:
                raise ValueError("no NAV on or before target date")
            nav_date = date.fromisoformat(selected["FSRQ"])
            age_days = (target_date - nav_date).days
            validation_status = "PASS" if age_days <= 3 else "FAIL_STALE_NAV"
            if age_days > 3:
                errors.append(f"{code}: NAV {nav_date.isoformat()} is {age_days} days old")
            result.append(
                FundNavRow(
                    fund_code=code,
                    name=str(fund["name"]),
                    nav_date=nav_date.isoformat(),
                    unit_nav=float(selected["DWJZ"]),
                    accumulated_nav=(
                        float(selected["LJJZ"])
                        if selected.get("LJJZ") not in (None, "")
                        else None
                    ),
                    daily_growth_pct=(
                        float(selected["JZZZL"])
                        if selected.get("JZZZL") not in (None, "")
                        else None
                    ),
                    provider="EASTMONEY_FUND_F10",
                    retrieved_at=retrieved_at,
                    validation_status=validation_status,
                )
            )
        except Exception as exc:
            errors.append(f"{code}: {exc}")
    return result, errors


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    target_date = date.fromisoformat(config["target_market_date"])
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(
        {"User-Agent": "Mozilla/5.0 (Post-FMDL4 market refresh; repository validation)"}
    )
    quote_rows, quote_errors = fetch_quotes(session, config["symbols"], target_date)
    fund_rows, fund_errors = fetch_fund_nav(session, config["funds"], target_date)

    write_csv(
        output / f"POST_FMDL4_A_SHARE_QUOTES_{target_date:%Y%m%d}.csv",
        [asdict(row) for row in quote_rows],
    )
    write_csv(
        output / f"POST_FMDL4_FUND_NAV_{target_date:%Y%m%d}.csv",
        [asdict(row) for row in fund_rows],
    )

    all_errors = quote_errors + fund_errors
    decision = {
        "program_id": "POST-FMDL-4-MARKET-REFRESH",
        "target_market_date": target_date.isoformat(),
        "source_release4_sha256": config["source_release4_sha256"],
        "fmdl4final_release_id": config["fmdl4final_release_id"],
        "requested_symbol_count": len(config["symbols"]),
        "quote_row_count": len(quote_rows),
        "requested_fund_count": len(config["funds"]),
        "fund_nav_row_count": len(fund_rows),
        "quote_date_pass_count": sum(row.validation_status == "PASS" for row in quote_rows),
        "fund_nav_pass_count": sum(row.validation_status == "PASS" for row in fund_rows),
        "hard_failures": all_errors,
        "status": (
            "PASS"
            if not all_errors
            and len(quote_rows) == len(config["symbols"])
            and len(fund_rows) == len(config["funds"])
            else "FAIL"
        ),
        "trade_authority": "NONE",
        "generated_at": datetime.now(SH_TZ).isoformat(timespec="seconds"),
    }
    (output / "POST_FMDL4_MARKET_FETCH_DECISION.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if decision["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
