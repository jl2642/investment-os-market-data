from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3dd_engine.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-id", required=True)
    args = parser.parse_args()
    cfg = load_json(CONFIG)
    shard = f"{int(args.shard_id):02d}"
    root = ROOT / cfg["publication"]["shard_root"] / f"shard-{shard}"
    decision = load_json(root / "SHARD_DECISION.json")
    attempts = pd.read_csv(root / "DIVIDEND_SOURCE_ATTEMPTS.csv", encoding="utf-8-sig", dtype={"symbol": str})
    events = pd.read_parquet(root / "DIVIDEND_EVENTS.parquet")
    allowed_states = {"SUCCESS", "SUCCESS_EMPTY", "FAILED"}
    failures = []
    checks = {
        "DECISION_PASS": decision.get("status") == "PASS",
        "ATTEMPT_KEYS_UNIQUE": not attempts["symbol"].duplicated().any(),
        "ATTEMPT_STATES_CONTROLLED": set(attempts["source_state"].astype(str)).issubset(allowed_states),
        "ATTEMPT_AUTHORITY_CONTROLLED": set(attempts["trade_authority"].astype(str)).issubset({"NONE"}),
        "EVENT_KEYS_UNIQUE": events.empty or not events["event_id"].duplicated().any(),
        "EVENT_SYMBOLS_WITHIN_ATTEMPTS": events.empty or set(events["symbol"].astype(str)).issubset(set(attempts["symbol"].astype(str))),
        "EVENT_STAGE_CONTROLLED": events.empty or set(events["event_stage"].astype(str)).issubset({"ANNOUNCED", "IMPLEMENTED"}),
        "IMPLEMENTED_DIVIDENDS_HAVE_POSITIVE_CASH": events.empty or (pd.to_numeric(events.loc[events["shareholder_yield_effective"].eq(True), "cash_amount_per_share"], errors="coerce") > 0).all(),
        "EVENT_TRADE_AUTHORITY_NONE": events.empty or set(events["trade_authority"].astype(str)).issubset({"NONE"}),
    }
    failures = [key for key, value in checks.items() if not bool(value)]
    result = {
        "shard_id": shard,
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": failures,
        "checks": [{"check_id": key, "status": "PASS" if value else "FAIL"} for key, value in checks.items()],
        "symbol_count": int(len(attempts)),
        "event_count": int(len(events)),
        "source_success_ratio": float(attempts["source_state"].isin(["SUCCESS", "SUCCESS_EMPTY"]).mean()) if len(attempts) else 1.0,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    (root / "SHARD_VALIDATION.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
