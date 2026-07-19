from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd

from scripts.fmdl3dd_core import EVENT_COLUMNS, normalize_dividend_frame

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3dd_engine.json"
TZ = ZoneInfo("Asia/Shanghai")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def shard_for(symbol: str, count: int) -> int:
    return int(hashlib.sha256(symbol.encode("utf-8")).hexdigest(), 16) % count


def fetch_report_period(date: str, cfg: dict) -> tuple[pd.DataFrame, dict]:
    started = time.monotonic()
    result = pd.DataFrame()
    state = "FAILED"
    error_type = None
    error_message = None
    attempt_count = 0
    for attempt in range(1, int(cfg["source"]["max_attempts"]) + 1):
        attempt_count = attempt
        try:
            result = ak.stock_fhps_em(date=date)
            state = "SUCCESS_EMPTY" if result is None or result.empty else "SUCCESS"
            error_type = None
            error_message = None
            break
        except Exception as exc:
            error_type = type(exc).__name__
            error_message = str(exc)[:500]
            if attempt < int(cfg["source"]["max_attempts"]):
                time.sleep(
                    float(cfg["source"]["initial_backoff_seconds"]) * attempt
                )
    retrieved_at = datetime.now(TZ).isoformat(timespec="seconds")
    if result is None:
        result = pd.DataFrame()
    if not result.empty:
        result = result.copy()
        result["代码"] = result["代码"].astype(str).str.replace(".0", "", regex=False).str.zfill(6)
        result["报告期"] = pd.to_datetime(date, format="%Y%m%d").date().isoformat()
    attempt = {
        "report_period_date": date,
        "source_state": state,
        "attempt_count": attempt_count,
        "source_row_count": int(len(result)),
        "error_type": error_type,
        "error_message": error_message,
        "elapsed_seconds": time.monotonic() - started,
        "retrieved_at": retrieved_at,
        "source_id": cfg["source"]["dividend_source_id"],
        "source_adapter": cfg["source"]["dividend_source_adapter"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    return result, attempt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-id", required=True)
    args = parser.parse_args()
    cfg = load_json(CONFIG)
    shard_id = int(args.shard_id)
    shard_count = int(cfg["sharding"]["shard_count"])
    cap = pd.read_parquet(ROOT / cfg["inputs"]["universe"])
    cap["symbol"] = cap["symbol"].astype(str)
    selected = cap[
        cap["symbol"].map(lambda value: shard_for(value, shard_count) == shard_id)
    ].copy().sort_values("symbol")
    selected["code"] = selected["symbol"].str[:6]
    selected_codes = set(selected["code"])
    out = ROOT / cfg["publication"]["shard_root"] / f"shard-{shard_id:02d}"
    out.mkdir(parents=True, exist_ok=True)

    period_parts: list[pd.DataFrame] = []
    period_attempts: list[dict] = []
    for report_date in cfg["source"]["report_period_dates"]:
        frame, attempt = fetch_report_period(str(report_date), cfg)
        period_attempts.append(attempt)
        if not frame.empty:
            subset = frame[frame["代码"].isin(selected_codes)].copy()
            if not subset.empty:
                period_parts.append(subset)
    all_periods_success = all(
        item["source_state"] in {"SUCCESS", "SUCCESS_EMPTY"}
        for item in period_attempts
    )
    combined = (
        pd.concat(period_parts, ignore_index=True)
        if period_parts
        else pd.DataFrame()
    )
    grouped = (
        {str(code): frame for code, frame in combined.groupby("代码", sort=False)}
        if not combined.empty
        else {}
    )
    retrieved_at = max(
        (item["retrieved_at"] for item in period_attempts),
        default=datetime.now(TZ).isoformat(timespec="seconds"),
    )

    event_parts: list[pd.DataFrame] = []
    attempts: list[dict] = []
    for row in selected.itertuples(index=False):
        symbol = str(row.symbol)
        code = str(row.code)
        source_rows = grouped.get(code, pd.DataFrame())
        if all_periods_success:
            source_state = "SUCCESS_EMPTY" if source_rows.empty else "SUCCESS"
            error_type = None
            error_message = None
        else:
            source_state = "FAILED"
            failed = [
                item
                for item in period_attempts
                if item["source_state"] not in {"SUCCESS", "SUCCESS_EMPTY"}
            ]
            error_type = "REPORT_PERIOD_BATCH_FAILURE"
            error_message = "|".join(
                f"{item['report_period_date']}:{item['error_type']}:{item['error_message']}"
                for item in failed
            )[:500]
        normalized_count = 0
        if source_state == "SUCCESS":
            normalized = normalize_dividend_frame(
                symbol,
                getattr(row, "name", None),
                source_rows,
                retrieved_at,
                cfg,
            )
            normalized_count = int(len(normalized))
            if normalized_count:
                event_parts.append(normalized)
        attempts.append(
            {
                "symbol": symbol,
                "name": getattr(row, "name", None),
                "shard_id": f"{shard_id:02d}",
                "source_state": source_state,
                "attempt_count": int(sum(item["attempt_count"] for item in period_attempts)),
                "source_row_count": int(len(source_rows)),
                "normalized_event_count": normalized_count,
                "error_type": error_type,
                "error_message": error_message,
                "elapsed_seconds": float(sum(item["elapsed_seconds"] for item in period_attempts)),
                "retrieved_at": retrieved_at,
                "source_id": cfg["source"]["dividend_source_id"],
                "source_adapter": cfg["source"]["dividend_source_adapter"],
                "authority": cfg["authority"],
                "trade_authority": "NONE",
            }
        )

    events = (
        pd.concat(event_parts, ignore_index=True)
        if event_parts
        else pd.DataFrame(columns=EVENT_COLUMNS)
    )
    attempts_frame = pd.DataFrame(attempts)
    period_attempts_frame = pd.DataFrame(period_attempts)
    events.to_parquet(
        out / "DIVIDEND_EVENTS.parquet", index=False, compression="zstd"
    )
    attempts_frame.to_csv(
        out / "DIVIDEND_SOURCE_ATTEMPTS.csv", index=False, encoding="utf-8-sig"
    )
    period_attempts_frame.to_csv(
        out / "DIVIDEND_PERIOD_ATTEMPTS.csv", index=False, encoding="utf-8-sig"
    )
    success_ratio = (
        float(
            attempts_frame["source_state"]
            .isin(["SUCCESS", "SUCCESS_EMPTY"])
            .mean()
        )
        if len(attempts_frame)
        else 1.0
    )
    decision = {
        "shard_id": f"{shard_id:02d}",
        "status": "PASS" if success_ratio >= 0.99 else "FAIL",
        "hard_failures": (
            []
            if success_ratio >= 0.99
            else ["DIVIDEND_SOURCE_ATTEMPT_RATIO_BELOW_SHARD_GATE"]
        ),
        "symbol_count": int(len(selected)),
        "attempt_row_count": int(len(attempts_frame)),
        "period_attempt_row_count": int(len(period_attempts_frame)),
        "event_row_count": int(len(events)),
        "source_success_ratio": success_ratio,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    (out / "SHARD_DECISION.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if decision["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
