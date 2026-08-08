#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

TRADE_AUTHORITY = "NONE"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(root: Path, p5c_dir: Path, out: Path) -> dict[str, Any]:
    contract = read_json(root / "config/hkcu_p5d_manual_staged_execution_support_contract.json")
    p5c_contract = read_json(root / contract["authoritative_inputs"]["p5c_contract"])
    prefix = p5c_contract["output_prefix"]
    p5c_decision = read_json(p5c_dir / f"{prefix}_DECISION.json")
    packet = pd.read_csv(p5c_dir / f"{prefix}_DECISION_PACKET.csv", keep_default_na=False)
    decision = read_json(out / "HKCU_P5D_NO_EXECUTION_DECISION.json")
    synthetic = read_json(out / "HKCU_P5D_NO_EXECUTION_SYNTHETIC_ENGINE_CAPABILITY.json")

    errors: list[str] = []
    entry = contract["entry_contract"]
    acceptance = contract["acceptance"]
    if p5c_decision.get("status") != entry["required_p5c_status"]:
        errors.append("P5C_STATUS")
    if p5c_decision.get("gate_state") != entry["required_p5c_gate_state"]:
        errors.append("P5C_GATE_STATE")
    if int(p5c_decision.get("user_decision_recorded_count", -1)) != 0:
        errors.append("P5C_DECISION_COUNT_NOT_ZERO")
    if "user_decision" not in packet.columns or packet["user_decision"].astype(str).str.strip().ne("").any():
        errors.append("P5C_PACKET_HAS_USER_DECISION")

    if decision.get("status") != acceptance["pass_status"]:
        errors.append("P5D_STATUS")
    if decision.get("production_execution_state") != acceptance["production_execution_state"]:
        errors.append("PRODUCTION_STATE")
    if bool(decision.get("explicit_user_trade_approval_present")):
        errors.append("APPROVAL_INFERRED")
    if bool(decision.get("production_manual_execution_checklist_produced")):
        errors.append("REAL_CHECKLIST_PRODUCED")
    if int(decision.get("production_real_execution_checklist_rows", -1)) != 0:
        errors.append("REAL_CHECKLIST_ROWS")
    if int(decision.get("orders_created", -1)) != 0:
        errors.append("ORDERS_CREATED")
    if int(decision.get("fills_inferred", -1)) != 0:
        errors.append("FILLS_INFERRED")
    if int(decision.get("real_account_mutations", -1)) != 0:
        errors.append("REAL_MUTATION")
    if decision.get("trade_authority") != TRADE_AUTHORITY:
        errors.append("TRADE_AUTHORITY")
    if decision.get("next_gate") != acceptance["next_gate_on_pass"]:
        errors.append("NEXT_GATE")

    if synthetic.get("status") != acceptance["synthetic_capability_status"]:
        errors.append("SYNTHETIC_STATUS")
    if bool(synthetic.get("executable")):
        errors.append("SYNTHETIC_EXECUTABLE")
    rows = synthetic.get("rows", [])
    if len(rows) != acceptance["synthetic_security_count"]:
        errors.append("SYNTHETIC_COUNT")
    for row in rows:
        sid = str(row.get("security_id", ""))
        if not sid.startswith("TEST_"):
            errors.append("SYNTHETIC_NON_TEST_ID")
        if bool(row.get("executable")):
            errors.append("SYNTHETIC_ROW_EXECUTABLE")
        lot = int(row.get("board_lot", 0))
        shares = int(row.get("rounded_shares", -1))
        batches = [int(x) for x in row.get("batch_shares", [])]
        if lot <= 0 or shares < 0 or shares % lot != 0:
            errors.append("SYNTHETIC_LOT_ROUNDING")
        if sum(batches) != shares or any(x % lot != 0 for x in batches):
            errors.append("SYNTHETIC_BATCH_INTEGRITY")
        if float(row.get("rounded_capital_hkd", -1)) > float(row.get("target_capital_hkd", -1)) + 1e-9:
            errors.append("SYNTHETIC_CAPITAL_OVERSHOOT")
        if float(row.get("drift_lower_hkd", 0)) <= 0 or float(row.get("drift_upper_hkd", 0)) <= float(row.get("drift_lower_hkd", 0)):
            errors.append("SYNTHETIC_DRIFT_GUARD")

    forbidden_real_outputs = [
        out / "HKCU_P5D_REAL_EXECUTION_CHECKLIST.csv",
        out / "HKCU_P5D_REAL_ORDER_LIST.csv",
        out / "HKCU_P5D_REAL_TARGET_PORTFOLIO.csv",
    ]
    if any(path.exists() for path in forbidden_real_outputs):
        errors.append("FORBIDDEN_REAL_OUTPUT_PRESENT")

    result = {
        "status": "PASS" if not errors else "FAIL",
        "errors": sorted(set(errors)),
        "production_execution_state": decision.get("production_execution_state"),
        "synthetic_capability_status": synthetic.get("status"),
        "next_gate": decision.get("next_gate"),
        "trade_authority": decision.get("trade_authority"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if errors:
        raise SystemExit(1)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--p5c-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    validate(Path(args.repo_root), Path(args.p5c_dir), Path(args.output))


if __name__ == "__main__":
    main()
