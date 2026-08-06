#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SIM_SOURCE = ROOT / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_LEDGER_CURRENT.json"
RUN_ID = "POSITION_UPDATE_20260806_USER_INTRADAY"


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main() -> None:
    payload = read(SIM_SOURCE)
    bindings = payload.get("source_bindings", [])
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for row in bindings:
        key = (row.get("role"), row.get("run_id"), row.get("release_id"), row.get("state_run_id"), row.get("as_of"))
        if key in seen:
            continue
        seen.add(key)
        normalized.append(row)
    current = [row for row in normalized if row.get("run_id") == RUN_ID]
    assert len(current) == 1, current
    payload["source_bindings"] = normalized
    write(SIM_SOURCE, payload)
    print(json.dumps({"status": "PASS", "source_bindings": len(normalized), "current_run_bindings": 1}, ensure_ascii=False))


if __name__ == "__main__":
    main()
