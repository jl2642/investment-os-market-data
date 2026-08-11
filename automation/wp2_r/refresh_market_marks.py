#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

CN = ZoneInfo("Asia/Shanghai")
SINA_URL = "https://hq.sinajs.cn/list={symbols}"
FUND_URL = "https://fund.eastmoney.com/pingzhongdata/{code}.js?v={ts}"
EASTMONEY_INDEX_KLINE_URL = (
    "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    "?secid=1.000001&klt=101&fqt=0&lmt=15&end=20500101"
    "&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56"
)
COMPLETED_CLOSE_CUTOFF = "15:05:00"


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def canonical_security_id(code: str) -> str:
    raw = str(code).strip().upper()
    parts, digits = raw.split("."), raw.split(".")[0].zfill(6)
    if len(parts) > 1 and parts[1] in {"SH", "SZ", "BJ", "OF"}:
        return f"{digits}.{parts[1]}"
    if digits.startswith(("4", "8", "92")):
        return f"{digits}.BJ"
    if digits.startswith(("5", "6")):
        return f"{digits}.SH"
    if digits.startswith(("0", "1", "2", "3")):
        return f"{digits}.SZ"
    return digits


def security_id_for(code: str, asset_class: str) -> str:
    return f"{str(code).strip().split('.')[0].zfill(6)}.OF" if asset_class == "BOND_FUND" else canonical_security_id(code)


def sina_symbol(code: str) -> str:
    digits = str(code).zfill(6)
    if digits.startswith(("4", "8", "92")):
        return f"bj{digits}"
    if digits.startswith(("5", "6")):
        return f"sh{digits}"
    if digits.startswith(("0", "1", "2", "3")):
        return f"sz{digits}"
    raise ValueError(f"UNSUPPORTED_LISTED_CODE:{digits}")


def required_positions(root: Path, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    out = cfg["output_paths"]
    real_path, sim_path = root / out["real_positions"], root / out["simulation_positions"]
    if real_path.exists() and sim_path.exists():
        rows = read(real_path)["holdings"] + read(sim_path)["holdings"]
    else:
        rows = []
        real, sim = read(root / cfg["source_paths"]["real_legacy"]), read(root / cfg["source_paths"]["simulation_legacy"])
        for item in real.get("holdings", []):
            cls, code = item.get("asset_class", "UNKNOWN"), str(item["code"]).zfill(6)
            rows.append({"security_id": security_id_for(code, cls), "code": code, "security_name": item.get("holding_name"), "asset_class": cls})
        for item in sim.get("holdings", []):
            code = str(item["security_code"]).zfill(6)
            rows.append({"security_id": canonical_security_id(code), "code": code, "security_name": item.get("security_name"), "asset_class": "A_SHARE_STOCK"})
    return sorted({row["security_id"]: row for row in rows}.values(), key=lambda x: x["security_id"])


def request_text(url: str, encoding: str, retries: int = 3) -> str:
    headers = {"User-Agent": "Mozilla/5.0 InvestmentOS-WP2R/1.1", "Referer": "https://finance.sina.com.cn/"}
    errors = []
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as response:
                return response.read().decode(encoding, errors="replace")
        except Exception as exc:
            errors.append(f"attempt={attempt}:{type(exc).__name__}:{exc}")
            if attempt < retries:
                time.sleep(attempt * 2)
    raise RuntimeError("|".join(errors))


def freshness(as_of: str, max_days: int) -> str:
    age = (datetime.now(CN).date() - datetime.strptime(as_of, "%Y-%m-%d").date()).days
    return "FRESH" if age <= max_days else "STALE"


def latest_completed_listed_session(before_date: str) -> str:
    """Resolve the actual prior A-share session from benchmark daily bars.

    During an intraday quote, Sina's `previous_close` is the prior completed
    session's close, but the quote payload does not carry that prior session's
    date. Resolve the date independently from the Shanghai Composite daily bar
    calendar instead of reusing an older portfolio mark watermark.
    """
    text = request_text(EASTMONEY_INDEX_KLINE_URL, "utf-8")
    payload = json.loads(text)
    klines = ((payload.get("data") or {}).get("klines") or [])
    dates = []
    for row in klines:
        session = str(row).split(",", 1)[0]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", session) and session < before_date:
            dates.append(session)
    if not dates:
        raise ValueError(f"PRIOR_COMPLETED_SESSION_UNRESOLVED:{before_date}")
    return max(dates)


def listed_marks(
    rows: list[dict[str, Any]],
    max_days: int,
    existing_by_id: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    if not rows:
        return [], [], []
    symbols = {sina_symbol(row["code"]): row for row in rows}
    text = request_text(SINA_URL.format(symbols=",".join(symbols)), "gbk")
    pattern = re.compile(r'var hq_str_(?P<symbol>\w+)="(?P<body>[^"]*)";')
    marks, errors, observations, observed = [], [], [], set()
    today_cn = datetime.now(CN).date().isoformat()
    intraday_session_by_quote_date: dict[str, str] = {}
    for match in pattern.finditer(text):
        symbol = match.group("symbol")
        if symbol not in symbols:
            continue
        observed.add(symbol)
        row, fields = symbols[symbol], match.group("body").split(",")
        try:
            if len(fields) < 32 or not fields[0]:
                raise ValueError("EMPTY_OR_SHORT_QUOTE")
            previous_close = float(fields[2] or 0)
            current_quote = float(fields[3] or 0) or previous_close
            quote_date, quote_time = fields[30], fields[31]
            if previous_close <= 0 or current_quote <= 0 or not quote_date or not quote_time:
                raise ValueError("NON_POSITIVE_QUOTE_OR_MISSING_TIMESTAMP")

            is_intraday = quote_date == today_cn and quote_time < COMPLETED_CLOSE_CUTOFF
            if is_intraday:
                prior = existing_by_id.get(row["security_id"])
                if prior and str(prior.get("as_of_date", "")) >= quote_date:
                    raise ValueError("INTRADAY_BASELINE_NOT_PRIOR_TO_QUOTE_DATE")
                if quote_date not in intraday_session_by_quote_date:
                    intraday_session_by_quote_date[quote_date] = latest_completed_listed_session(quote_date)
                mark = previous_close
                as_of = intraday_session_by_quote_date[quote_date]
                as_time = "15:00:00"
                mark_type = "LATEST_COMPLETED_CLOSE_PRIOR_SESSION"
                observations.append({
                    "security_id": row["security_id"],
                    "security_name": row.get("security_name") or fields[0],
                    "observation_date": quote_date,
                    "observation_time": quote_time,
                    "intraday_quote": current_quote,
                    "previous_completed_close": previous_close,
                    "previous_completed_close_date": as_of,
                    "decision_grade": False,
                    "source_role": "INTRADAY_OBSERVATION_NOT_PORTFOLIO_CURRENT",
                })
            else:
                mark = current_quote
                as_of = quote_date
                as_time = quote_time
                mark_type = "LATEST_COMPLETED_CLOSE"

            marks.append({
                "security_id": row["security_id"],
                "code": row["code"],
                "security_name": row.get("security_name") or fields[0],
                "asset_class": row.get("asset_class", "LISTED_SECURITY"),
                "mark": mark,
                "mark_type": mark_type,
                "as_of_date": as_of,
                "as_of_time": as_time,
                "provider": "SINA_PUBLIC_TRACKED_QUOTES",
                "freshness_status": freshness(as_of, max_days),
                "source_role": "AUTOMATED_COMPLETED_CLOSE_REFRESH",
            })
        except Exception as exc:
            errors.append(f"{row['security_id']}:{type(exc).__name__}:{exc}")
    for symbol, row in symbols.items():
        if symbol not in observed:
            errors.append(f"{row['security_id']}:MISSING_PROVIDER_ROW")
    return marks, errors, observations


def fund_mark(row: dict[str, Any], max_days: int) -> dict[str, Any]:
    text = request_text(FUND_URL.format(code=row["code"], ts=int(time.time() * 1000)), "utf-8")
    match = re.search(r"var\s+Data_netWorthTrend\s*=\s*(\[.*?\]);", text, re.DOTALL)
    if not match:
        raise ValueError("FUND_NET_WORTH_TREND_NOT_FOUND")
    trend = json.loads(match.group(1))
    if not trend:
        raise ValueError("FUND_NET_WORTH_TREND_EMPTY")
    latest, nav = trend[-1], float(trend[-1]["y"])
    as_of = datetime.fromtimestamp(float(latest["x"]) / 1000, tz=CN).date().isoformat()
    if nav <= 0:
        raise ValueError("FUND_NAV_NON_POSITIVE")
    return {
        "security_id": row["security_id"], "code": row["code"], "security_name": row.get("security_name"),
        "asset_class": row.get("asset_class", "FUND"), "mark": nav, "mark_type": "OFFICIAL_NAV",
        "as_of_date": as_of, "provider": "EASTMONEY_PUBLIC_NET_WORTH_TREND",
        "freshness_status": freshness(as_of, max_days), "source_role": "AUTOMATED_MARK_REFRESH",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default="automation/wp2_r/config.json")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    cfg = read(root / args.config)
    rows = required_positions(root, cfg)
    marks_current_path = root / cfg["output_paths"]["portfolio_marks"]
    existing_payload = read(marks_current_path) if marks_current_path.exists() else {"marks": []}
    existing_by_id = {row["security_id"]: row for row in existing_payload.get("marks", [])}

    listed_rows = [x for x in rows if x.get("asset_class") != "BOND_FUND"]
    fund_rows = [x for x in rows if x.get("asset_class") == "BOND_FUND"]
    all_marks, errors, intraday_observations = listed_marks(
        listed_rows,
        cfg["freshness"]["listed_security_max_calendar_days"],
        existing_by_id,
    )
    for row in fund_rows:
        try:
            all_marks.append(fund_mark(row, cfg["freshness"]["fund_nav_max_calendar_days"]))
        except Exception as exc:
            errors.append(f"{row['security_id']}:{type(exc).__name__}:{exc}")

    required_ids = {x["security_id"] for x in rows}
    marked_ids = {x["security_id"] for x in all_marks}
    missing = sorted(required_ids - marked_ids)
    stale = sorted(x["security_id"] for x in all_marks if x.get("freshness_status") != "FRESH")
    complete = not errors and not missing and not stale
    listed_dates = [x["as_of_date"] for x in all_marks if x.get("asset_class") != "BOND_FUND"]
    payload = {
        "schema_version": "1.2.0",
        "refresh_id": f"WP2R_PORTFOLIO_MARKS_REFRESH_{datetime.now(CN).strftime('%Y%m%dT%H%M%S%z')}",
        "generated_at": datetime.now(CN).isoformat(),
        "status": "PASS_COMPLETE" if complete else "BLOCKED_PARTIAL_OR_STALE",
        "required_security_count": len(required_ids),
        "marked_security_count": len(marked_ids),
        "missing_security_ids": missing,
        "stale_security_ids": stale,
        "errors": errors,
        "latest_completed_listed_close_date": max(listed_dates) if listed_dates else None,
        "intraday_session_date_authority": "EASTMONEY_SHANGHAI_COMPOSITE_DAILY_BAR" if intraday_observations else None,
        "intraday_observation_count": len(intraday_observations),
        "intraday_observations": sorted(intraday_observations, key=lambda x: x["security_id"]),
        "marks": sorted(all_marks, key=lambda x: x["security_id"]),
        "automatic_quantity_or_cost_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    write(root / cfg["source_paths"]["marks_candidate"], payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    if not complete:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
