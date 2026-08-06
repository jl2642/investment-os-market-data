#!/usr/bin/env python3
from __future__ import annotations

import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json"
SIM = ROOT / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"
DELTA = ROOT / "investment_os_runtime/30_STATE_CURRENT/15_PORTFOLIO_INPUT/USER_TRANSACTION_DELTA_LEDGER_CURRENT.json"
APPLY = ROOT / "automation/canonical_position_update/apply_20260806_user_update.py"
REQUIRED = {
    "REAL_605090_SECOND_4950_SETTLEMENT_20260806",
    "SIM_20260806_SELL_002463_200",
    "SIM_20260806_SELL_300124_200",
    "SIM_20260806_BUY_300012_1000",
}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def code(row: dict) -> str:
    return str(row.get("code") or row.get("security_id", "").split(".")[0]).zfill(6)


def already_applied() -> bool:
    real = {code(row): row for row in read(REAL)["holdings"]}
    sim = {code(row): row for row in read(SIM)["holdings"]}
    delta_ids = {row["delta_id"] for row in read(DELTA).get("entries", [])}
    return (
        real.get("605090", {}).get("quantity") == 9900
        and "002463" not in sim
        and sim.get("300124", {}).get("quantity") == 200
        and sim.get("300012", {}).get("quantity") == 1000
        and REQUIRED <= delta_ids
    )


def main() -> None:
    if already_applied():
        print(json.dumps({"status": "NO_OP_ALREADY_APPLIED", "required_deltas": 4}, ensure_ascii=False))
        return
    runpy.run_path(str(APPLY), run_name="__main__")
    assert already_applied()
    print(json.dumps({"status": "PASS_NEWLY_APPLIED", "required_deltas": 4}, ensure_ascii=False))


if __name__ == "__main__":
    main()
