#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


SINA_URL = "https://hq.sinajs.cn/list={symbols}"
FUND_URL = "https://fund.eastmoney.com/pingzhongdata/{code}.js?v={ts}"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def canonical_security_id(code: str) -> str:
    digits = str(code).strip().split(".")[0].zfill(6)
    if digits.startswith(("5", "6", "9")):
        return f"{digits}.SH"
    if digits.startswith(("0", "1", "2", "3")):
        return f"{digits}.SZ"
    if digits.startswith(("4", "8")):
        return f"{digits}.BJ"
    return digits


def sina_symbol(code: str) -> str:
    digits = str(code).zfill(6)
    if digits.startswith(("5", "6", "9")):
        return f"sh{digits}"
    if digits.startswith(("0", "1", "2", "3")):
        return f"sz{digits}"
    if digits.startswith(("4", "8")):
        return f"bj{digits}"
    raise ValueError(f"UNSUPPORTED_LISTED_CODE:{digits}")


def load_required_positions(root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    outputs = config["output_paths"]
    real_path = root / outputs["real_positions"]
    simulation_path = root / outputs["simulation_positions"]
    if real_path.exists() and simulation_path.exists():
        real = read_json(real_path)["holdings"]
        simulation = read_json(simulation_path)["holdings"]
        rows = real + simulation
    else:
        real_source = read_json(root / config["source_paths"]["real_legacy"])
        sim_source = read_json(root / config["source_paths"]["simulation_legacy"])
        rows = []
        for item in real_source.get("holdings", []):
            rows.append(
                {
                    "security_id": canonical_security_id(item["code"]),
                    "code": str(item["code"]).zfill(6),
                    "security_name": item.get("holding_name"),
                    "asset_class": item.get("asset_class", "UNKNOWN"),
                }
            )
        for item in sim_source.get("holdings", []):
            rows.append(
                {
                    "security_id": canonical_security_id(item["security_code"]),
                    "code": str(item["security_code"]).zfill(6),
                    "security_name": item.get("security_name"),
                    "asset_class": "A_SHARE_STOCK",
                }
            )
    dedup: dict[str, dict[str, Any]] = {}
    for row in rows:
        dedup[row["security_id"]] = row
    return sorted(dedup.values(), key=lambda row: row["security_id"])


def request_text(url: str, *, encoding: str | None = None, retries: int = 3) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 InvestmentOS-WP2R/1.0",
        "Referer": "https://finance.sina.com.cn/",
    }
    errors: list[str] = []
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read()
            return raw.decode(encoding or "utf-8", errors="replace")
        except Exception as exc:
            errors.append(f"attempt={attempt}:{type(exc).__name__}:{exc}")
            if attempt < retries:
                time.sleep(attempt * 2)
    raise RuntimeError("|".join(errors))


def fetch_sina_marks(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    if not rows:
        return [], []
    symbol_map = {sina_symbol(row["code"]): row for row in rows}
    text = request_text(SINA_URL.format(symbols=",".join(symbol_map)), encoding="gbk")
    marks: list[dict[str, Any]] = []
    errors: list[str] = []
    pattern = re.compile(r'var hq_str_(?P<symbol>\w+)="(?P<body>[^"]*)";')
    observed: set[str] = set()
    for match in pattern.finditer(text):
        symbol = match.group("symbol")
        if symbol not in symbol_map:
            continue
        observed.add(symbol)
        fields = match.group("body").split(",")
        row = symbol_map[symbol]
        try:
            if len(fields) < 32 or not fields[0]:
                raise ValueError("EMPTY_OR_SHORT_QUOTE")
            previous_close = float(fields[2] or 0)
            current = float(fields[3] or 0)
            mark = current if current > 0 else previous_close
            quote_date = fields[30]
            quote_time = fields[31]
            if mark <= 0 or not quote_date:
                raise ValueError("NON_POSITIVE_MARK_OR_MISSING_DATE")
            marks.append(
                {
                    "security_id": row["security_id"],
                    "code": row["code"],
                    "security_name": row.get("security_name") or fields[0],
                    "asset_class": row.get("asset_class", "LISTED_SECURITY"),
                    "mark": mark,
                    "mark_type": "LATEST_COMPLETED_OR_LAST",
                    "as_of_date": quote_date,
                    "as_of_time": quote_time,
                    "provider": "SINA_PUBLIC_TRACKED_QUOTES",
                    "freshness_status": "FRESH",
                    "source_role": "AUTOMATED_MARK_REFRESH",
                }
            )
        except Exception as exc:
            errors.append(f"{row['security_id']}:{type(exc).__name__}:{exc}")
    for symbol, row in symbol_map.items():
        if symbol not in observed:
            errors.append(f"{row['security_id']}:MISSING_PROVIDER_ROW")
    return marks, errors


def fetch_fund_mark(row: dict[str, Any]) -> dict[str, Any]:
    text = request_text(
        FUND_URL.format(code=row["code"], ts=int(time.time() * 1000)),
        encoding="utf-8",
    )
    match = re.search(r"var\s+Data_netWorthTrend\s*=\s*(\[.*?\]);", text, re.DOTALL)
    if not match:
        raise ValueError("FUND_NET_WORTH_TREND_NOT_FOUND")
    trend = json.loads(match.group(1))
    if not trend:
        raise ValueError("FUND_NET_WORTH_TREND_EMPTY")
    latest = trend[-1]
    nav = float(latest["y"])
    as_of = datetime.fromtimestamp(float(latest["x"]) / 1000, tz=timezone.utc).date().isoformat()
    if nav <= 0:
        raise ValueError("FUND_NAV_NON_POSITIVE")
    age = (date.today() - date.fromisoformat(as_of)).days
    return {
        "security_id": row["security_id"],
        "code": row["code"],
        "security_name": row.get("security_name"),
        "asset_class": row.get("asset_class", "FUND"),
        "mark": nav,
        "mark_type": "OFFICIAL_NAV",
        "as_of_date": as_of,
        "provider": "EASTMONEY_PUBLIC_NET_WORTH_TREND",
        "freshness_status": "FRESH" if age <= 2 else "ACCEPTABLE_LAG" if age <= 4 else "STALE",
        "source_role": "AUTOMATED_MARK_REFRESH",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default="automation/wp2_r/config.json")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    config = read_json(root / args.config)
    required = load_required_positions(root, config)
    listed = [row for row in required if row.get("asset_class") != "BOND_FUND"]
    funds = [row for row in required if row.get("asset_class") == "BOND_FUND"]
    listed_marks, errors = fetch_sina_marks(listed)
    marks = listed_marks
    for row in funds:
        try:
            marks.append(fetch_fund_mark(row))
        except Exception as exc:
            errors.append(f"{row['security_id']}:{type(exc).__name__}:{exc}")

    required_ids = {row["security_id"] for row in required}
    mark_ids = {row["security_id"] for row in marks}
    missing = sorted(required_ids - mark_ids)
    stale = sorted(
        row["security_id"]
        for row in marks
        if row.get("freshness_status") not in {"FRESH", "ACCEPTABLE_LAG"}
    )
    complete = not errors and not missing and not stale
    payload = {
        "schema_version": "1.0.0",
        "refresh_id": f"WP2R_PORTFOLIO_MARKS_REFRESH_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS_COMPLETE" if complete else "BLOCKED_PARTIAL_OR_STALE",
        "required_security_count": len(required_ids),
        "marked_security_count": len(mark_ids),
        "missing_security_ids": missing,
        "stale_security_ids": stale,
        "errors": errors,
        "marks": sorted(marks, key=lambda row: row["security_id"]),
        "automatic_quantity_or_cost_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    output = root / config["source_paths"]["marks_candidate"]
    write_json(output, payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    if not complete:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
