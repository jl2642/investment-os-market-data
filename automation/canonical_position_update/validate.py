#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REAL_SOURCE = ROOT / "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_CURRENT.json"
SIM_SOURCE = ROOT / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_LEDGER_CURRENT.json"
REAL = ROOT / "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json"
SIM = ROOT / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"
MARKS = ROOT / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP2_R/PORTFOLIO_MARKS_REFRESH_CANDIDATE.json"
EQUITY = ROOT / "investment_os_runtime/30_STATE_CURRENT/12_EQUITY_COMPENSATION/EQUITY_COMPENSATION_CURRENT.json"
DELTA = ROOT / "investment_os_runtime/30_STATE_CURRENT/15_PORTFOLIO_INPUT/USER_TRANSACTION_DELTA_LEDGER_CURRENT.json"
RUN = ROOT / "investment_os_runtime/30_STATE_CURRENT/70_OPERATIONS/PORTFOLIO_CURRENT_RUN_CURRENT.json"
BASELINE = ROOT / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/POSITION_UPDATE_2026_08_04/PROTECTED_STATE_BASELINE.json"
SCHEMA = ROOT / "investment_os_runtime/20_SCHEMAS_AND_INTERFACES/equity_compensation_state.schema.json"
REGISTRY = ROOT / "investment_os_runtime/20_SCHEMAS_AND_INTERFACES/SCHEMA_REGISTRY.json"

EXPECTED_SIM = {
    "600406": (1800, 22.58), "600938": (1800, 26.26),
    "600660": (1600, 49.87), "600690": (1800, 20.37),
    "600036": (1600, 35.42), "000333": (800, 77.38),
    "600941": (700, 86.97), "300124": (400, 79.02),
    "600309": (700, 70.01), "002463": (200, 132.47),
    "600276": (800, 50.27), "300750": (100, 452.26),
    "601899": (1000, 30.66), "510500": (7100, 8.276),
    "601138": (600, 76.43), "600900": (2200, 26.47),
}


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def code(row: dict[str, Any]) -> str:
    return str(row.get("code") or row.get("security_code") or row.get("security_id", "").split(".")[0]).zfill(6)


def unit_cost(row: dict[str, Any]) -> float:
    return float(row.get("unit_cost", row.get("broker_display_unit_cost", 0.0)))


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


def require_close(actual: float, expected: float, tolerance: float = 0.02) -> None:
    assert abs(float(actual) - expected) <= tolerance, (actual, expected)


def first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    raise KeyError(keys)


def main() -> None:
    real_source, sim_source = read(REAL_SOURCE), read(SIM_SOURCE)
    real, sim, marks = read(REAL), read(SIM), read(MARKS)
    equity, delta, run = read(EQUITY), read(DELTA), read(RUN)
    baseline, schema, registry = read(BASELINE), read(SCHEMA), read(REGISTRY)

    for label, payload in {
        "real_source": real_source, "simulation_source": sim_source,
        "real": real, "simulation": sim, "equity": equity,
        "delta": delta, "run": run, "protected_baseline": baseline,
    }.items():
        values = authority_values(payload)
        if values:
            assert set(values) == {"NONE"}, (label, values)

    assert real.get("snapshot_type") == "USER_CONFIRMED_INTRADAY"
    assert sim.get("snapshot_type") == "USER_CONFIRMED_INTRADAY"
    assert real.get("formal_eod_snapshot_written", real.get("eod_snapshot_written", False)) is False
    assert sim.get("formal_eod_snapshot_written", sim.get("eod_snapshot_written", False)) is False
    assert real_source.get("snapshot_type") == "USER_CONFIRMED_INTRADAY"
    assert sim_source.get("snapshot_type") == "USER_CONFIRMED_INTRADAY"

    real_by_code = {code(row): row for row in real["holdings"]}
    assert len(real_by_code) == 8
    jovo = real_by_code["605090"]
    assert float(jovo["quantity"]) == 4950
    assert float(jovo["available_quantity"]) == 4950
    assert jovo["batch_identity"] == "UNKNOWN_STOCK_INCENTIVE_OR_OPTION"
    assert "Q99460" not in real_by_code and "Q99461" not in real_by_code
    require_close(sum(float(row["market_value"]) for row in real["holdings"]), 614383.30)
    rs = real["summary"]
    require_close(first(rs, "listed_security_line_market_value_sum", "listed_security_line_sum"), 299152.70)
    require_close(first(rs, "broker_listed_security_total_reported", "listed_security_total_broker_reported"), 299390.20)
    require_close(first(rs, "broker_reconciliation_exception_amount", "reconciliation_exception_amount"), 237.50)
    require_close(first(rs, "broker_total_assets_reported", "total_assets_broker_reported"), 615390.25)
    assert first(rs, "pending_entitlement_market_value_included") == 0
    assert first(rs, "pending_entitlement_quantity_included") == 0

    source_real_codes = {str(row["code"]).zfill(6) for row in real_source["holdings"]}
    assert len(source_real_codes) == 8 and "605090" in source_real_codes
    source_sim = {str(row["security_code"]).zfill(6): row for row in sim_source["holdings"]}
    assert set(source_sim) == set(EXPECTED_SIM)
    for sec, (qty, cost) in EXPECTED_SIM.items():
        assert float(source_sim[sec]["quantity"]) == qty
        require_close(source_sim[sec]["cost_price"], cost, 0.0001)

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
    assert closed["total_sold_quantity"] == 13200 and closed["current_position_quantity"] == 0
    require_close(closed["sale_proceeds"], 378847.78)
    require_close(closed["cash_economic_cost"], 218064.00)
    require_close(closed["pre_tax_pre_fee_gross_profit"], 160783.78)

    sim_by_code = {code(row): row for row in sim["holdings"]}
    assert set(sim_by_code) == set(EXPECTED_SIM)
    for sec, (qty, cost) in EXPECTED_SIM.items():
        assert float(sim_by_code[sec]["quantity"]) == qty
        require_close(unit_cost(sim_by_code[sec]), cost, 0.0001)
    require_close(sum(float(row["market_value"]) for row in sim["holdings"]), 799538.10)
    ss = sim["summary"]
    require_close(first(ss, "top_market_value_reported", "total_market_value_top_reported"), 799495.10)
    require_close(first(ss, "market_value_reconciliation_exception_amount"), -43.00)
    require_close(first(ss, "top_total_assets_reported", "total_assets_top_reported"), 1021157.08)
    assert first(ss, "new_confirmed_trades") == 0

    allowed = {"PENDING_USER_CONFIRMATION", "CONFIRMED_BY_USER", "APPLIED_TO_POSITION_CURRENT", "REJECTED"}
    delta_by_id = {row["delta_id"]: row for row in delta["entries"]}
    assert len(delta_by_id) == len(delta["entries"])
    assert all(row["status"] in allowed for row in delta["entries"])
    assert all(row["status"] == "REJECTED" for row in delta["entries"])
    assert delta_by_id["JOVO_2026_SETTLED_ORDINARY_SHARES_UNKNOWN_BATCH"]["current_position_effect"] == 4950
    assert delta_by_id["JOVO_2026_PENDING_ENTITLEMENT"]["current_position_effect"] == 0
    assert delta_by_id["JOVO_2026_PENDING_ENTITLEMENT"]["market_value_effect"] == 0
    require_close(delta_by_id["JOVO_2026_OPTION_EXERCISE_PAYMENT"]["cash_amount"], 95139.00)

    assert marks["status"] == "PASS_COMPLETE"
    mark_ids = {row["security_id"] for row in marks["marks"]}
    required_ids = {row["security_id"] for row in real["holdings"] + sim["holdings"]}
    assert required_ids <= mark_ids
    assert all(row["freshness_status"] in {"FRESH", "ACCEPTABLE_LAG"} for row in marks["marks"] if row["security_id"] in required_ids)

    assert run["orders"] == 0 and run["trade_authority"] == "NONE"
    assert run["snapshot_type"] == "USER_CONFIRMED_INTRADAY"
    assert run.get("formal_eod_snapshot_written", run.get("eod_snapshot_written", False)) is False

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
        "status": "PASS", "real_holding_count": len(real_by_code),
        "simulation_holding_count": len(sim_by_code),
        "ordinary_605090_quantity": jovo["quantity"],
        "pending_605090_quantity": current["pending_entitlement"]["quantity"],
        "candidate_mutations": 0, "decision_mutations": 0,
        "orders": 0, "trade_authority": "NONE",
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "formal_eod_snapshot_written": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
