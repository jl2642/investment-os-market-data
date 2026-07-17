#!/usr/bin/env python3
"""Re-fetch only FMDL-2B-2 quarantined symbols and preserve diagnostic evidence."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd

from scripts import benchmark_historical_sources as base

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
QUARANTINE = ROOT / "outputs/history/candidate/HISTORICAL_QUARANTINE.csv"
CURRENT = ROOT / "outputs/current/CURRENT_RELEASE.json"
CONFIG = ROOT / "config/fmdl2_history_store.json"
OUTPUT = ROOT / "diagnostics/FMDL2B2_QUARANTINE_RETRY.json"


def invalid_rows(frame: pd.DataFrame) -> pd.DataFrame:
    prices = frame[["date", "open", "high", "low", "close"]].copy()
    for column in ("open", "high", "low", "close"):
        prices[column] = pd.to_numeric(prices[column], errors="coerce")
    valid = prices.dropna(subset=["open", "high", "low", "close"])
    mask = (
        (valid["high"] < valid[["open", "close", "low"]].max(axis=1))
        | (valid["low"] > valid[["open", "close", "high"]].min(axis=1))
        | (valid[["open", "high", "low", "close"]] <= 0).any(axis=1)
    )
    return valid.loc[mask]


def main() -> int:
    quarantine = pd.read_csv(QUARANTINE, dtype={"symbol": str})
    current = json.loads(CURRENT.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    as_of = date.fromisoformat(current["as_of_date"])
    start = as_of - timedelta(days=int(config["history_policy"]["retrieval_calendar_days"]))
    providers = base.provider_functions(start.strftime("%Y%m%d"), as_of.strftime("%Y%m%d"))
    sina = providers["sina_daily"]

    results = []
    for row in quarantine.to_dict(orient="records"):
        symbol = str(row["symbol"])
        item = {
            "symbol": symbol,
            "original_reason": row.get("quarantine_reason"),
            "retry_provider": "sina_daily",
            "retry_function": "stock_zh_a_daily",
        }
        try:
            raw = sina(symbol)
            normalized, meta = base.normalize_history(raw)
            normalized = normalized.loc[normalized["date"].dt.date <= as_of].copy()
            bad = invalid_rows(normalized)
            item.update({
                "retrieval_state": "SUCCESS",
                "observation_count": int(len(normalized)),
                "latest_date": str(normalized["date"].max().date()) if len(normalized) else None,
                "impossible_ohlc_rows": int(len(bad)),
                "invalid_samples": bad.head(5).assign(date=lambda x: x["date"].astype(str)).to_dict(orient="records"),
                "decision": "RECOVERED_VALID" if len(normalized) and bad.empty else (
                    "PERSISTENT_IMPOSSIBLE_OHLC" if len(bad) else "EMPTY_HISTORY"
                ),
                "source_meta": meta,
            })
        except Exception as exc:
            item.update({
                "retrieval_state": "FAILED",
                "decision": "SOURCE_FAILURE_PERSISTS",
                "error": f"{type(exc).__name__}: {exc}"[:1000],
            })
        results.append(item)

    payload = {
        "retry_version": "1.0.0",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "as_of_date": as_of.isoformat(),
        "akshare_version": getattr(ak, "__version__", "unknown"),
        "symbols_attempted": len(results),
        "results": results,
        "authority": "DIAGNOSTIC_ONLY_NO_BASE_STORE_MUTATION_NO_TRADE_AUTHORITY",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
