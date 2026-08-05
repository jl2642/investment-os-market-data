#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json"
SIM = ROOT / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"
EQUITY = ROOT / "investment_os_runtime/30_STATE_CURRENT/12_EQUITY_COMPENSATION/EQUITY_COMPENSATION_CURRENT.json"
DELTA = ROOT / "investment_os_runtime/30_STATE_CURRENT/15_PORTFOLIO_INPUT/USER_TRANSACTION_DELTA_LEDGER_CURRENT.json"
RUN = ROOT / "investment_os_runtime/30_STATE_CURRENT/70_OPERATIONS/PORTFOLIO_CURRENT_RUN_CURRENT.json"
BASELINE = ROOT / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/POSITION_UPDATE_2026_08_04/PROTECTED_STATE_BASELINE.json"
SCHEMA = ROOT / "investment_os_runtime/20_SCHEMAS_AND_INTERFACES/equity_compensation_state.schema.json"
REGISTRY = ROOT / "investment_os_runtime/20_SCHEMAS_AND_INTERFACES/SCHEMA_REGISTRY.json"

EXPECTED_SIM = {
    "600406": (1800, 22.58),
    "600938": (1800, 26.26),
    "600660": (1600, 49.87),
    "600690": (1800, 20.37),
    "600036": (1600, 35.42),
    "000333": (800, 77.38),
    "600941": (700, 86.97),
    "300124": (400, 79.02),
    "600309": (700, 70.01),
    "002463": (200, 132.47),
    "600276": (800, 50.27),
    "300750": (100, 452.26),
    "601899": (1000, 30.66),
    "510500": (7100, 8.276),
    "601138": (600, 76.43),
    "600900": (2200, 26.47),
}


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    return hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest()


def authority_values(value: Any) -> list[Any]:
    values: list[Any] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "trade_authority":
                values.append(item)
            values.extend(authority_values(item))
    elif isinstance(value, list):
        for item in value:
            values.extend(authority_values(item))
    return values


def require_close(actual: float, expected: float, tolerance: float = 0.01) -> None:
    assert abs(float(actual) - expected) <= tolerance, (actual, expected)


def main() -> None:
    real = read(REAL)
    sim = read(SIM)
    equity = read(EQUITY)
    delta = read(DELTA)
    run = read(RUN)
    baseline = read(BASELINE)
    schema = read(SCHEMA)
    registry = read(REGISTRY)

    for label, payload in {
        "real": real,
        "simulation": sim,
        "equity": equity,
        "delta": delta,
        "run": run,
        "protected_baseline": baseline,
    }.items():
        values = authority_values(payload)
        assert values and set(values) == {"NONE"}, (label, values)

    assert real["snapshot_type"] == "USER_CONFIRMED_INTRADAY"
    assert sim["snapshot_type"] == "USER_CONFIRMED_INTRADAY"
    assert real.get("eod_snapshot_written", False) is False
    assert sim.get("eod_snapshot_written", False) is False

    real_by_code = {row["security_code"]: row for row in real["holdings"]}
    assert len(real_by_code) == 8
    assert real_by_code["605090"]["quantity"] == 4950
    assert real_by_code["605090"]["available_quantity"] == 4950
    assert real_by_code["605090"]["batch_identity"] == "UNKNOWN_STOCK_INCENTIVE_OR_OPTION"
    assert "Q99460" not in real_by_code and "Q99461" not in real_by_code
    assert sum(row["quantity"] for row in real["holdings"] if row["security_code"] == "605090") == 4950
    require_close(sum(row["market_value"] for row in real["holdings"]), 614383.30)
    require_close(real["summary"]["listed_security_line_sum"], 299152.70)
    require_close(real["summary"]["listed_security_total_broker_reported"], 299390.20)
    require_close(real["summary"]["reconciliation_exception_amount"], 237.50)
    require_close(
        real["summary"]["holding_line_market_value_sum"]
        + real["summary"]["execution_cash_balance"]
        + real["summary"]["reconciliation_exception_amount"],
        real["summary"]["total_assets_broker_reported"],
    )
    assert real["summary"]["pending_entitlement_market_value_included"] == 0
    assert real["summary"]["pending_entitlement_quantity_included"] == 0

    current = equity["current_recognition"]
    assert current["ordinary_share_position"]["quantity"] == 4950
    assert current["ordinary_share_position"]["included_in_real_account_current"] is True
    assert current["ordinary_share_position"]["batch_identity"] == "UNKNOWN_STOCK_INCENTIVE_OR_OPTION"
    assert current["pending_entitlement"]["quantity"] == 4950
    assert current["pending_entitlement"]["market_value"] == 0
    assert current["pending_entitlement"]["included_in_real_account_current"] is False
    assert current["pending_entitlement"]["included_in_total_assets"] is False
    rights = {row["code"]: row for row in current["technical_entitlement_codes"]}
    assert set(rights) == {"Q99460", "Q99461"}
    assert all(row["market_value"] == 0 for row in rights.values())
    closed = equity["historical_closed_batches"][0]
    assert closed["total_sold_quantity"] == 13200
    assert closed["current_position_quantity"] == 0
    require_close(closed["sale_proceeds"], 378847.78)
    require_close(closed["cash_economic_cost"], 218064.00)
    require_close(closed["pre_tax_pre_fee_gross_profit"], 160783.78)
    assert equity["cost_basis_policy"]["prohibited_override"].startswith("BROKER_DISPLAY_UNIT_COST_32_55")

    sim_by_code = {row["security_code"]: row for row in sim["holdings"]}
    assert set(sim_by_code) == set(EXPECTED_SIM)
    for code, (quantity, unit_cost) in EXPECTED_SIM.items():
        assert sim_by_code[code]["quantity"] == quantity, code
        require_close(sim_by_code[code]["broker_display_unit_cost"], unit_cost, tolerance=0.0001)
    require_close(sum(row["market_value"] for row in sim["holdings"]), 799538.10)
    require_close(sim["summary"]["total_market_value_top_reported"], 799495.10)
    require_close(sim["summary"]["market_value_reconciliation_exception_amount"], -43.00)
    require_close(
        sim["summary"]["total_market_value_top_reported"] + sim["summary"]["available_cash"],
        sim["summary"]["total_assets_top_reported"],
    )
    assert sim["summary"]["new_confirmed_trades"] == 0
    assert sim["summary"]["quantity_mutations_from_market_refresh"] == 0

    delta_by_id = {row["delta_id"]: row for row in delta["entries"]}
    assert delta_by_id["JOVO_2026_SETTLED_ORDINARY_SHARES_UNKNOWN_BATCH"]["current_position_effect"] == 4950
    assert delta_by_id["JOVO_2026_PENDING_ENTITLEMENT"]["current_position_effect"] == 0
    assert delta_by_id["JOVO_2026_PENDING_ENTITLEMENT"]["market_value_effect"] == 0
    assert delta_by_id["JOVO_2025_STOCK_INCENTIVE_CLOSED"]["current_position_effect"] == 0
    assert delta_by_id["JOVO_2025_OPTION_EXERCISE_CLOSED"]["current_position_effect"] == 0
    require_close(delta_by_id["JOVO_2026_OPTION_EXERCISE_PAYMENT"]["cash_amount"], 95139.00)

    assert run["orders"] == 0
    assert run["trade_authority"] == "NONE"
    assert run["snapshot_type"] == "USER_CONFIRMED_INTRADAY"
    assert run["eod_snapshot_written"] is False

    for item in baseline["protected_files"]:
        path = ROOT / item["path"]
        assert git_blob_sha(path) == item["git_blob_sha"], item["path"]
        assert item["expected_mutation"] is False

    schema_names = {item["name"]: item for item in registry["schemas"]}
    assert "equity_compensation_state.schema.json" in schema_names
    assert schema["$id"] == "equity_compensation_state.schema.json"
    assert schema["properties"]["trade_authority"]["const"] == "NONE"
    assert schema["properties"]["orders"]["const"] == 0

    print(json.dumps({
        "status": "PASS",
        "real_holding_count": len(real_by_code),
        "simulation_holding_count": len(sim_by_code),
        "ordinary_605090_quantity": real_by_code["605090"]["quantity"],
        "pending_605090_quantity": current["pending_entitlement"]["quantity"],
        "candidate_mutations": 0,
        "decision_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "eod_snapshot_written": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
