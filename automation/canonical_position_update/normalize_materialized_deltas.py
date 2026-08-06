#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "investment_os_runtime/30_STATE_CURRENT/15_PORTFOLIO_INPUT/USER_TRANSACTION_DELTA_LEDGER_CURRENT.json"
MATERIALIZED_IDS = {
    "REAL_605090_SECOND_4950_SETTLEMENT_20260806",
    "SIM_20260806_SELL_002463_200",
    "SIM_20260806_SELL_300124_200",
    "SIM_20260806_BUY_300012_1000",
}


def main() -> None:
    payload = json.loads(LEDGER.read_text(encoding="utf-8"))
    found = set()
    for row in payload.get("entries", []):
        delta_id = row.get("delta_id")
        if delta_id not in MATERIALIZED_IDS:
            continue
        found.add(delta_id)
        row["status"] = "REJECTED"
        row["application_decision"] = "ALREADY_APPLIED_TO_POSITION_CURRENT_DO_NOT_REAPPLY"
        row["position_engine_treatment"] = "SOURCE_BASELINE_ALREADY_CONTAINS_DELTA"
        row["rejection_reason"] = (
            "The user-confirmed delta is already materialized in the canonical source and Position Current. "
            "Reapplying it during a market-mark rebuild would double count the economic event."
        )
    assert found == MATERIALIZED_IDS, sorted(MATERIALIZED_IDS - found)
    payload["applied_delta_count"] = 4
    payload["materialized_delta_ids"] = sorted(MATERIALIZED_IDS)
    payload["rejected_for_position_engine_count"] = sum(
        row.get("status") == "REJECTED" for row in payload.get("entries", [])
    )
    payload["status"] = "FOUR_USER_CONFIRMED_DELTAS_MATERIALIZED_DO_NOT_REAPPLY"
    payload.setdefault("policy", {})["materialized_delta_treatment"] = (
        "RETAIN_AUDIT_RECORD_WITH_STATUS_REJECTED_FOR_POSITION_ENGINE_AFTER_SOURCE_MATERIALIZATION"
    )
    payload["policy"]["note"] = (
        "Confirmed economic events are applied once to the canonical source baseline. After materialization, "
        "their ledger records remain auditable but are rejected for subsequent position-engine mutation."
    )
    payload["orders"] = 0
    payload["trade_authority"] = "NONE"
    LEDGER.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "PASS",
        "materialized_delta_count": 4,
        "active_position_engine_delta_count": sum(
            row.get("status") in {"CONFIRMED_BY_USER", "APPLIED_TO_POSITION_CURRENT"}
            for row in payload.get("entries", [])
        ),
        "orders": 0,
        "trade_authority": "NONE",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
