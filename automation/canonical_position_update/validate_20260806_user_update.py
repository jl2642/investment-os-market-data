#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
P = {
    "real_source": ROOT / "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_CURRENT.json",
    "real": ROOT / "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json",
    "equity": ROOT / "investment_os_runtime/30_STATE_CURRENT/12_EQUITY_COMPENSATION/EQUITY_COMPENSATION_CURRENT.json",
    "delta": ROOT / "investment_os_runtime/30_STATE_CURRENT/15_PORTFOLIO_INPUT/USER_TRANSACTION_DELTA_LEDGER_CURRENT.json",
    "sim_source": ROOT / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_LEDGER_CURRENT.json",
    "sim": ROOT / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json",
    "candidate": ROOT / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json",
    "weekly": ROOT / "investment_os_runtime/30_STATE_CURRENT/45_CANDIDATE_OPERATIONS/WEEKLY_PRICE_SCREEN_CURRENT.json",
    "candidate_review": ROOT / "investment_os_runtime/30_STATE_CURRENT/45_CANDIDATE_OPERATIONS/CANDIDATE_ACTION_REVIEW_CURRENT.json",
    "confirmations": ROOT / "investment_os_runtime/30_STATE_CURRENT/61_DECISIONS/USER_CONFIRMATIONS_CURRENT.json",
    "evidence": ROOT / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/POSITION_UPDATE_2026_08_06/USER_CONFIRMED_INTRADAY_SNAPSHOT_20260806.json",
    "baseline": ROOT / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/POSITION_UPDATE_2026_08_06/PROTECTED_STATE_BASELINE.json",
    "status": ROOT / "investment_os_runtime/50_OPERATING_PRODUCTS/OBSERVATION/STATUS/POSITION_UPDATE_STATUS_20260806_USER_INTRADAY.json",
    "run_manifest": ROOT / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1/RUN_MANIFESTS/POSITION_UPDATE_20260806_USER_INTRADAY.json",
    "report_manifest": ROOT / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1/REPORT_MANIFESTS/POSITION_UPDATE_20260806_USER_INTRADAY.json",
}

EXPECTED_SIM = {
    "000333", "300012", "300124", "300750", "510500", "600036", "600276", "600309",
    "600406", "600660", "600690", "600900", "600938", "600941", "601138", "601899",
}
APPLIED_IDS = {
    "REAL_605090_SECOND_4950_SETTLEMENT_20260806",
    "SIM_20260806_SELL_002463_200",
    "SIM_20260806_SELL_300124_200",
    "SIM_20260806_BUY_300012_1000",
}


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def code(row: dict[str, Any]) -> str:
    return str(row.get("code") or row.get("security_code") or row.get("security_id", "").split(".")[0]).zfill(6)


def close(actual: float, expected: float, tolerance: float = 0.02) -> None:
    assert abs(float(actual) - expected) <= tolerance, (actual, expected)


def git_blob_sha(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def authority_values(value: Any) -> list[Any]:
    out: list[Any] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "trade_authority":
                out.append(item)
            out.extend(authority_values(item))
    elif isinstance(value, list):
        for item in value:
            out.extend(authority_values(item))
    return out


def main() -> None:
    payloads = {name: read(path) for name, path in P.items()}
    real, real_source = payloads["real"], payloads["real_source"]
    sim, sim_source = payloads["sim"], payloads["sim_source"]
    equity, delta = payloads["equity"], payloads["delta"]
    candidate, weekly, review = payloads["candidate"], payloads["weekly"], payloads["candidate_review"]
    confirmations, evidence, baseline = payloads["confirmations"], payloads["evidence"], payloads["baseline"]

    for name, payload in payloads.items():
        values = authority_values(payload)
        if values:
            assert set(values) == {"NONE"}, (name, values)
        assert payload.get("orders", 0) == 0, (name, payload.get("orders"))

    for payload in [real, real_source, sim, sim_source, evidence, payloads["status"], payloads["run_manifest"], payloads["report_manifest"]]:
        assert payload.get("snapshot_type") == "USER_CONFIRMED_INTRADAY"
        assert payload.get("formal_eod_snapshot_written", payload.get("formal_eod", False)) is False

    real_rows = {code(row): row for row in real["holdings"]}
    assert set(real_rows) == {"017534", "110017", "159352", "159612", "159655", "217003", "510500", "605090"}
    jovo = real_rows["605090"]
    assert jovo["quantity"] == jovo["available_quantity"] == 9900
    assert jovo["batch_identity"] == "AGGREGATE_2026_STOCK_INCENTIVE_AND_OPTION_SETTLED"
    close(jovo["market_value"], 332937.00)
    close(jovo["broker_display_unit_cost"], 33.055, 0.0001)
    close(jovo["economic_cash_cost"], 160330.50)
    assert all(code(row) not in {"Q99460", "Q99461"} for row in real["holdings"])
    rs = real["summary"]
    close(rs["position_market_value"], 790231.28)
    close(rs["execution_cash_balance"], 769.45)
    close(rs["broker_reconciliation_exception_amount"], -71.90)
    close(rs["account_total_assets"], 790928.83)
    close(rs["position_market_value"] + rs["execution_cash_balance"] + rs["broker_reconciliation_exception_amount"], rs["account_total_assets"])
    assert rs["pending_entitlement_quantity_included"] == 0

    current = equity["current_recognition"]
    assert current["ordinary_share_position"]["quantity"] == 9900
    assert current["ordinary_share_position"]["available_quantity"] == 9900
    assert current["pending_entitlement"]["quantity"] == 0
    assert current["pending_entitlement"]["market_value"] == 0
    settled_2026 = [tranche for program in equity["programs"] for tranche in program["tranches"] if tranche["year"] == 2026]
    assert len(settled_2026) == 2
    assert all(row["status"] == "SETTLED_AS_ORDINARY_SHARES" and row["current_position_quantity"] == 4950 for row in settled_2026)
    assert sum(row["current_position_quantity"] for row in settled_2026) == 9900

    sim_rows = {code(row): row for row in sim["holdings"]}
    assert set(sim_rows) == EXPECTED_SIM
    assert "002463" not in sim_rows
    assert sim_rows["300124"]["quantity"] == 200
    close(sim_rows["300124"]["unit_cost"], 79.02, 0.0001)
    close(sim_rows["300124"]["broker_display_unit_cost"], 94.07, 0.0001)
    assert sim_rows["300012"]["quantity"] == 1000
    assert sim_rows["300012"]["available_quantity"] == 0
    close(sim_rows["300012"]["unit_cost"], 14.08, 0.0001)
    close(sim_rows["300012"]["broker_display_unit_cost"], 14.09, 0.0001)
    ss = sim["summary"]
    close(ss["position_cost_basis"], 741669.60)
    close(ss["position_market_value_line_sum"], 776587.80)
    close(ss["position_market_value"], 776514.40)
    close(ss["execution_cash_balance"], 244332.59)
    close(ss["market_value_reconciliation_exception_amount"], -73.40)
    close(ss["account_total_assets"], 1020846.99)
    close(ss["position_market_value"] + ss["execution_cash_balance"], ss["account_total_assets"])
    assert ss["new_confirmed_trades"] == 3

    trade_ids = {row.get("delta_id") for row in sim_source.get("trade_ledger", [])}
    assert APPLIED_IDS - {"REAL_605090_SECOND_4950_SETTLEMENT_20260806"} <= trade_ids
    assert sim_source["summary"]["new_confirmed_trades"] == 3
    close(sim_source["summary"]["available_cash"], 244332.59)

    delta_by_id = {row["delta_id"]: row for row in delta["entries"]}
    assert APPLIED_IDS <= set(delta_by_id)
    assert all(delta_by_id[item]["status"] == "APPLIED_TO_POSITION_CURRENT" for item in APPLIED_IDS)
    assert delta["applied_delta_count"] == 4
    assert delta["unapplied_delta_count"] == 0

    confirmation_ids = {row["confirmation_id"] for row in confirmations["confirmations"]}
    assert {
        "CONF_REAL_605090_SECOND_4950_SETTLED_20260806",
        "CONF_REAL_NO_OTHER_CHANGES_THROUGH_20260806_1102",
        "CONF_SIM_20260806_SELL_002463_200",
        "CONF_SIM_20260806_SELL_300124_200",
        "CONF_SIM_20260806_BUY_300012_1000",
    } <= confirmation_ids

    assert candidate["counts"] == {
        "candidate_core": 2,
        "historical_core20": 20,
        "historical_core20_moved_to_shadow": 18,
        "historical_core20_retained_as_core": 2,
        "ready_for_user_decision": 0,
        "research_queue": 33,
        "shadow_track": 38,
    }
    assert weekly["as_of_date"] == "2026-08-05"
    assert weekly["covered_count"] == 73
    assert review["candidate_market_watermark"] == "2026-08-05_CLOSE"
    assert review["candidate_membership_mutations"] == 0
    assert review["ready_for_user_decision_mutations"] == 0
    hct = next(row for row in review["portfolio_linkages"] if row["security_id"] == "300012.SZ")
    assert hct["candidate_route"] == "SHADOW_TRACK_MEMBERS"
    assert hct["real_account_permission"] is False
    assert hct["ready_for_user_decision"] is False

    for item in baseline["protected_files"]:
        path = ROOT / item["path"]
        assert item["expected_mutation"] is False
        assert git_blob_sha(path) == item["git_blob_sha"], item["path"]

    assert evidence["eod_status"] == "NOT_EOD_DO_NOT_APPEND_TO_FORMAL_EOD_SERIES"
    assert evidence["input_evidence"][0]["count"] == 8
    assert evidence["non_mutation_scope"]["candidate_membership"] == "UNCHANGED"
    assert evidence["non_mutation_scope"]["formal_decisions"] == "UNCHANGED"

    print(json.dumps({
        "status": "PASS",
        "real_605090_quantity": 9900,
        "simulation_holding_count": len(sim_rows),
        "simulation_trades_applied": 3,
        "candidate_counts": candidate["counts"],
        "candidate_market_watermark": review["candidate_market_watermark"],
        "formal_eod_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
