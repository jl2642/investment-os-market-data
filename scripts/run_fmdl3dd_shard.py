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

from scripts.fmdl3dd_core import normalize_dividend_frame

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3dd_engine.json"
TZ = ZoneInfo("Asia/Shanghai")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def shard_for(symbol: str, count: int) -> int:
    return int(hashlib.sha256(symbol.encode("utf-8")).hexdigest(), 16) % count


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
    out = ROOT / cfg["publication"]["shard_root"] / f"shard-{shard_id:02d}"
    out.mkdir(parents=True, exist_ok=True)

    event_parts: list[pd.DataFrame] = []
    attempts: list[dict] = []
    for row in selected.itertuples(index=False):
        symbol = str(row.symbol)
        code = symbol[:6]
        name = getattr(row, "name", None)
        started = time.monotonic()
        source_state = "FAILED"
        error_type = None
        error_message = None
        result = pd.DataFrame()
        attempt_count = 0
        for attempt in range(1, int(cfg["source"]["max_attempts"]) + 1):
            attempt_count = attempt
            try:
                result = ak.stock_fhps_detail_em(symbol=code)
                source_state = "SUCCESS_EMPTY" if result is None or result.empty else "SUCCESS"
                error_type = None
                error_message = None
                break
            except Exception as exc:
                error_type = type(exc).__name__
                error_message = str(exc)[:500]
                if attempt < int(cfg["source"]["max_attempts"]):
                    time.sleep(float(cfg["source"]["initial_backoff_seconds"]) * attempt)
        retrieved_at = datetime.now(TZ).isoformat(timespec="seconds")
        if source_state == "SUCCESS":
            normalized = normalize_dividend_frame(symbol, name, result, retrieved_at, cfg)
            if len(normalized):
                event_parts.append(normalized)
        attempts.append({
            "symbol": symbol,
            "name": name,
            "shard_id": f"{shard_id:02d}",
            "source_state": source_state,
            "attempt_count": attempt_count,
            "source_row_count": int(len(result)) if result is not None else 0,
            "normalized_event_count": int(len(event_parts[-1])) if event_parts and source_state == "SUCCESS" else 0,
            "error_type": error_type,
            "error_message": error_message,
            "elapsed_seconds": time.monotonic() - started,
            "retrieved_at": retrieved_at,
            "source_id": cfg["source"]["dividend_source_id"],
            "source_adapter": cfg["source"]["dividend_source_adapter"],
            "authority": cfg["authority"],
            "trade_authority": "NONE",
        })

    events = pd.concat(event_parts, ignore_index=True) if event_parts else pd.DataFrame()
    attempts_frame = pd.DataFrame(attempts)
    events.to_parquet(out / "DIVIDEND_EVENTS.parquet", index=False, compression="zstd")
    attempts_frame.to_csv(out / "DIVIDEND_SOURCE_ATTEMPTS.csv", index=False, encoding="utf-8-sig")
    success_ratio = float(attempts_frame["source_state"].isin(["SUCCESS", "SUCCESS_EMPTY"]).mean()) if len(attempts_frame) else 1.0
    decision = {
        "shard_id": f"{shard_id:02d}",
        "status": "PASS" if success_ratio >= 0.90 else "FAIL",
        "hard_failures": [] if success_ratio >= 0.90 else ["DIVIDEND_SOURCE_ATTEMPT_RATIO_BELOW_SHARD_GATE"],
        "symbol_count": int(len(selected)),
        "attempt_row_count": int(len(attempts_frame)),
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
