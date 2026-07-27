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
BENCHMARK_ID = "000300.SH"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def normalize_security_id(value: str) -> str:
    raw = str(value).strip().upper()
    if "." in raw:
        code, suffix = raw.split(".", 1)
        return f"{code.zfill(6)}.{suffix}"
    code = raw.zfill(6)
    if code.startswith(("4", "8", "92")):
        return f"{code}.BJ"
    if code.startswith(("5", "6")):
        return f"{code}.SH"
    return f"{code}.SZ"


def sina_symbol(security_id: str) -> str:
    code, suffix = normalize_security_id(security_id).split(".")
    return {"SH": "sh", "SZ": "sz", "BJ": "bj"}[suffix] + code


def request_text(url: str, retries: int = 3) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 InvestmentOS-WP3R/1.0",
        "Referer": "https://finance.sina.com.cn/",
    }
    errors = []
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.read().decode("gbk", errors="replace")
        except Exception as exc:
            errors.append(f"attempt={attempt}:{type(exc).__name__}:{exc}")
            if attempt < retries:
                time.sleep(attempt * 2)
    raise RuntimeError("|".join(errors))


def fetch_quotes(security_ids: list[str]) -> list[dict[str, Any]]:
    symbols = {sina_symbol(sid): sid for sid in security_ids}
    text = request_text(SINA_URL.format(symbols=",".join(symbols)))
    pattern = re.compile(r'var hq_str_(?P<symbol>\w+)="(?P<body>[^"]*)";')
    rows = []
    seen = set()
    for match in pattern.finditer(text):
        symbol = match.group("symbol")
        if symbol not in symbols:
            continue
        seen.add(symbol)
        fields = match.group("body").split(",")
        if len(fields) < 32 or not fields[0]:
            raise ValueError(f"EMPTY_OR_SHORT_QUOTE:{symbols[symbol]}")
        previous_close = float(fields[2] or 0)
        current = float(fields[3] or 0)
        close = current if current > 0 else previous_close
        trade_date = fields[30]
        trade_time = fields[31]
        if close <= 0 or not trade_date:
            raise ValueError(f"INVALID_QUOTE:{symbols[symbol]}")
        rows.append(
            {
                "security_id": symbols[symbol],
                "security_name": fields[0],
                "trade_date": trade_date,
                "close": close,
                "quote_time": trade_time,
                "provider": "SINA_PUBLIC_TRACKED_QUOTES",
                "source_role": "WP3R_CANDIDATE_OUTCOME_PRICE_LEDGER",
                "decision_grade": "TRACKED_MARKET_EVIDENCE",
                "trade_authority": "NONE",
            }
        )
    missing = sorted(set(symbols) - seen)
    if missing:
        raise ValueError("MISSING_QUOTES:" + ",".join(symbols[symbol] for symbol in missing))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default="automation/wp3_r/config.json")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    config = read_json(root / args.config)
    baselines = read_jsonl(root / config["inputs"]["entry_baselines"])
    valid = [row for row in baselines if row.get("status") == "COMPLETE" and row.get("entry_date") and row.get("entry_price")]
    if len(valid) != 2:
        raise ValueError(f"EXPECTED_TWO_COMPLETE_CORE_BASELINES_GOT:{len(valid)}")

    target_ids = sorted({normalize_security_id(row["security_id"]) for row in valid} | {BENCHMARK_ID})
    quotes = fetch_quotes(target_ids)
    quote_by_id = {row["security_id"]: row for row in quotes}

    ledger_path = root / "investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION/CANDIDATE_PRICE_LEDGER.jsonl"
    existing = read_jsonl(ledger_path)
    rows_by_key = {(normalize_security_id(row["security_id"]), str(row["trade_date"])): row for row in existing}

    seeded = 0
    for baseline in valid:
        sid = normalize_security_id(baseline["security_id"])
        key = (sid, str(baseline["entry_date"]))
        if key not in rows_by_key:
            rows_by_key[key] = {
                "security_id": sid,
                "security_name": baseline.get("security_name"),
                "trade_date": str(baseline["entry_date"]),
                "close": float(baseline["entry_price"]),
                "provider": "WP3_5_ACCEPTED_ENTRY_BASELINE",
                "source_role": "WP3R_CANDIDATE_OUTCOME_ENTRY_SEED",
                "decision_grade": "ACCEPTED_PROSPECTIVE_ENTRY_BASELINE",
                "trade_authority": "NONE",
            }
            seeded += 1

    appended = 0
    for quote in quotes:
        key = (quote["security_id"], quote["trade_date"])
        if key not in rows_by_key:
            rows_by_key[key] = quote
            appended += 1
        elif quote["security_id"] == BENCHMARK_ID and rows_by_key[key].get("provider") != "SINA_PUBLIC_TRACKED_QUOTES":
            rows_by_key[key] = quote

    entry_dates = {str(row["entry_date"]) for row in valid}
    if len(entry_dates) != 1:
        raise ValueError("CORE_ENTRY_DATES_NOT_ALIGNED")
    entry_date = next(iter(entry_dates))
    benchmark_quote = quote_by_id[BENCHMARK_ID]
    if benchmark_quote["trade_date"] == entry_date:
        rows_by_key[(BENCHMARK_ID, entry_date)] = benchmark_quote
    elif (BENCHMARK_ID, entry_date) not in rows_by_key:
        raise ValueError(
            f"BENCHMARK_ENTRY_DATE_NOT_AVAILABLE:entry={entry_date}:quote={benchmark_quote['trade_date']}"
        )

    final_rows = sorted(rows_by_key.values(), key=lambda row: (str(row["trade_date"]), normalize_security_id(row["security_id"])))
    if any(row.get("trade_authority") != "NONE" for row in final_rows):
        raise ValueError("PRICE_LEDGER_TRADE_AUTHORITY_VIOLATION")
    write_jsonl(ledger_path, final_rows)

    run = {
        "run_id": f"WP3R_CANDIDATE_PRICE_LEDGER_{datetime.now(CN).strftime('%Y%m%dT%H%M%S%z')}",
        "generated_at": datetime.now(CN).isoformat(),
        "status": "PASS_PRICE_LEDGER_CURRENT",
        "target_security_ids": target_ids,
        "valid_core_baseline_count": len(valid),
        "entry_seed_rows_added": seeded,
        "provider_quote_rows_added": appended,
        "ledger_row_count": len(final_rows),
        "latest_trade_date": max(str(row["trade_date"]) for row in final_rows),
        "candidate_membership_mutations": 0,
        "portfolio_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    write_json(
        root / "investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION/CANDIDATE_PRICE_LEDGER_RUN_CURRENT.json",
        run,
    )
    print(json.dumps(run, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
