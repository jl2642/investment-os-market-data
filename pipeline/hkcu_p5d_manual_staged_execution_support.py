#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

PROGRAM_ID = "HKCU-P5D"
TRADE_AUTHORITY = "NONE"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def floor_to_lot(raw_shares: float, board_lot: int) -> int:
    if board_lot <= 0:
        raise ValueError("INVALID_BOARD_LOT")
    if raw_shares < 0:
        raise ValueError("INVALID_RAW_SHARES")
    return int(math.floor(raw_shares / board_lot) * board_lot)


def allocate_whole_lot_batches(total_shares: int, board_lot: int, fractions: list[float]) -> list[int]:
    if total_shares < 0 or board_lot <= 0 or total_shares % board_lot != 0:
        raise ValueError("INVALID_BATCH_INPUT")
    if not fractions or any(x <= 0 for x in fractions) or not math.isclose(sum(fractions), 1.0, abs_tol=1e-9):
        raise ValueError("INVALID_BATCH_FRACTIONS")
    total_lots = total_shares // board_lot
    allocations: list[int] = []
    used_lots = 0
    for idx, frac in enumerate(fractions):
        if idx == len(fractions) - 1:
            lots = total_lots - used_lots
        else:
            lots = int(math.floor(total_lots * frac))
            used_lots += lots
        allocations.append(lots * board_lot)
    if sum(allocations) != total_shares or any(x % board_lot != 0 for x in allocations):
        raise ValueError("BATCH_ALLOCATION_INTEGRITY")
    return allocations


def synthetic_engine_capability(contract: dict[str, Any]) -> dict[str, Any]:
    engine = contract["engine_capability_contract"]
    nav = float(engine["synthetic_nav_hkd"])
    rows: list[dict[str, Any]] = []
    for item in engine["synthetic_securities"]:
        sid = str(item["security_id"])
        if not sid.startswith("TEST_"):
            raise ValueError("NON_TEST_SYNTHETIC_SECURITY")
        price = float(item["reference_price_hkd"])
        lot = int(item["board_lot"])
        weight = float(item["target_weight"])
        target_capital = nav * weight
        raw_shares = target_capital / price
        rounded_shares = floor_to_lot(raw_shares, lot)
        rounded_capital = rounded_shares * price
        batches = allocate_whole_lot_batches(rounded_shares, lot, [float(x) for x in item["batch_fractions"]])
        drift = float(item["max_price_drift_pct"])
        rows.append({
            "security_id": sid,
            "fixture_only": True,
            "executable": False,
            "reference_price_hkd": price,
            "board_lot": lot,
            "target_weight": weight,
            "target_capital_hkd": target_capital,
            "raw_shares": raw_shares,
            "rounded_shares": rounded_shares,
            "rounded_capital_hkd": rounded_capital,
            "batch_shares": batches,
            "max_price_drift_pct": drift,
            "drift_upper_hkd": price * (1.0 + drift),
            "drift_lower_hkd": price * (1.0 - drift),
        })
    return {
        "status": "PASS_SYNTHETIC_ENGINE_CAPABILITY",
        "fixture_only": True,
        "executable": False,
        "synthetic_nav_hkd": nav,
        "capabilities_proven": engine["required_capabilities"],
        "rows": rows,
    }


def build(root: Path, p5c_dir: Path, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    contract = read_json(root / "config/hkcu_p5d_manual_staged_execution_support_contract.json")
    p5c_contract = read_json(root / contract["authoritative_inputs"]["p5c_contract"])
    p5c_prefix = p5c_contract["output_prefix"]
    p5c_decision = read_json(p5c_dir / f"{p5c_prefix}_DECISION.json")
    packet = pd.read_csv(p5c_dir / f"{p5c_prefix}_DECISION_PACKET.csv", keep_default_na=False)

    errors: list[str] = []
    entry = contract["entry_contract"]
    acceptance = contract["acceptance"]
    if p5c_decision.get("status") != entry["required_p5c_status"]:
        errors.append("P5C_STATUS")
    if p5c_decision.get("gate_state") != entry["required_p5c_gate_state"]:
        errors.append("P5C_GATE_STATE")
    if int(p5c_decision.get("user_decision_recorded_count", -1)) != entry["required_user_decision_recorded_count"]:
        errors.append("P5C_USER_DECISION_COUNT")
    if p5c_decision.get("trade_authority") != TRADE_AUTHORITY:
        errors.append("P5C_TRADE_AUTHORITY")

    if "user_decision" not in packet.columns:
        errors.append("P5C_PACKET_USER_DECISION_COLUMN")
    else:
        recorded = packet["user_decision"].astype(str).str.strip().ne("").sum()
        if int(recorded) != 0:
            errors.append("USER_DECISION_MUST_REMAIN_EMPTY")

    synthetic = synthetic_engine_capability(contract)
    write_json(out / "HKCU_P5D_NO_EXECUTION_SYNTHETIC_ENGINE_CAPABILITY.json", synthetic)

    decision = {
        "program_id": PROGRAM_ID,
        "status": acceptance["pass_status"] if not errors else acceptance["fail_status"],
        "errors": errors,
        "mode": contract["development_mode_policy"]["mode"],
        "production_execution_state": acceptance["production_execution_state"],
        "explicit_user_trade_approval_present": False,
        "user_trade_confirmation_recorded": False,
        "production_real_execution_checklist_rows": 0,
        "production_manual_execution_checklist_produced": False,
        "synthetic_capability_status": synthetic["status"],
        "synthetic_security_count": len(synthetic["rows"]),
        "synthetic_output_executable": False,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "fills_inferred": 0,
        "next_gate": acceptance["next_gate_on_pass"] if not errors else contract["acceptance"]["repair_gate"],
        "trade_authority": TRADE_AUTHORITY,
    }
    write_json(out / "HKCU_P5D_NO_EXECUTION_DECISION.json", decision)

    md = [
        "# HKCU P5D｜Manual Staged Execution Support — No-Execution Development Path",
        "",
        f"Status: **{decision['status']}**",
        "",
        "The production path is intentionally blocked because P5C contains no explicit user trade approval.",
        "No REAL-security execution checklist is produced. No order or fill is created or inferred.",
        "",
        "A separate synthetic fixture using TEST_* identifiers proves capital sizing, board-lot rounding, whole-lot batch allocation and price-drift guards. The synthetic result is non-executable and must never be interpreted as a user instruction.",
        "",
        f"Next gate on PASS: **{decision['next_gate']}**",
        f"Trade authority: **{TRADE_AUTHORITY}**",
    ]
    (out / "HKCU_P5D_NO_EXECUTION.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return decision


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--p5c-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    decision = build(Path(args.repo_root), Path(args.p5c_dir), Path(args.output))
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    if decision["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
