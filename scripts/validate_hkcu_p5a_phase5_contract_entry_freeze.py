#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

PROGRAM_ID = "HKCU-P5A"
TRADE_AUTHORITY = "NONE"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate(root: Path, p4_4_dir: Path, out: Path) -> dict[str, Any]:
    contract_path = root / "config/hkcu_p5a_phase5_contract_entry_freeze.json"
    contract = read_json(contract_path)
    p4_contract = read_json(root / contract["authoritative_inputs"]["p4_4_contract"])
    p4_prefix = p4_contract["output_prefix"]
    prefix = contract["output_prefix"]
    entry = contract["entry_contract"]
    acceptance = contract["acceptance"]

    decision = read_json(out / f"{prefix}_DECISION.json")
    quality = read_json(out / f"{prefix}_QUALITY_REPORT.json")
    manifest = read_json(out / f"{prefix}_MANIFEST.json")
    gates = pd.read_csv(out / f"{prefix}_GATE_REGISTER.csv", keep_default_na=False)
    proposals = pd.read_csv(out / f"{prefix}_PROPOSALS.csv", keep_default_na=False)
    allocations = pd.read_csv(out / f"{prefix}_ALLOCATIONS.csv", dtype={"stock_code_5d": str}, keep_default_na=False)

    p4_decision_path = p4_4_dir / f"{p4_prefix}_DECISION.json"
    p4_proposals_path = p4_4_dir / f"{p4_prefix}_PREFERRED_PROPOSALS.csv"
    p4_alloc_path = p4_4_dir / f"{p4_prefix}_PROPOSAL_ALLOCATIONS.csv"
    p4_decision = read_json(p4_decision_path)
    p4_proposals = pd.read_csv(p4_proposals_path, keep_default_na=False)
    p4_alloc = pd.read_csv(p4_alloc_path, dtype={"stock_code_5d": str}, keep_default_na=False)

    errors: list[str] = []
    if decision.get("program_id") != PROGRAM_ID: errors.append("PROGRAM_ID")
    if decision.get("status") != acceptance["pass_status"]: errors.append("DECISION_STATUS")
    if quality.get("status") != "PASS": errors.append("QUALITY_STATUS")
    if p4_decision.get("status") != entry["required_p4_4_status"]: errors.append("ENTRY_P4_4_STATUS")
    if p4_decision.get("phase_close_status") != entry["required_p4_4_phase_close_status"]: errors.append("ENTRY_P4_4_PHASE")
    if p4_decision.get("additional_p4_subphases_allowed") is not False: errors.append("ENTRY_MORE_P4_ALLOWED")

    expected_ids = contract["planning_governance"]["frozen_business_gate_ids"]
    if list(gates["gate_id"].astype(str)) != expected_ids: errors.append("GATE_IDS")
    if len(gates) != acceptance["phase_5_gate_count"]: errors.append("GATE_COUNT")
    if len(proposals) != acceptance["entry_preferred_proposal_count"]: errors.append("PROPOSAL_COUNT")
    if len(allocations) != acceptance["entry_proposal_allocation_count"]: errors.append("ALLOCATION_COUNT")
    if len(allocations[allocations["account"].eq("REAL")]) != acceptance["entry_real_allocation_count"]: errors.append("REAL_ALLOCATION_COUNT")
    if len(allocations[allocations["account"].eq("SIMULATION")]) != acceptance["entry_simulation_allocation_count"]: errors.append("SIM_ALLOCATION_COUNT")

    for account, scenario, sleeve, count in (
        ("REAL", entry["required_real_preferred_scenario"], entry["required_real_hk_sleeve"], entry["required_real_position_count"]),
        ("SIMULATION", entry["required_simulation_preferred_scenario"], entry["required_simulation_hk_sleeve"], entry["required_simulation_position_count"]),
    ):
        p = proposals[proposals["account"].eq(account)]
        if len(p) != 1: errors.append(f"PROPOSAL_ACCOUNT:{account}"); continue
        row = p.iloc[0]
        if str(row["preferred_scenario_id"]) != scenario: errors.append(f"SCENARIO:{account}")
        if abs(float(row["hk_sleeve_proposed"]) - float(sleeve)) > 1e-9: errors.append(f"SLEEVE:{account}")
        if int(float(row["position_count"])) != int(count): errors.append(f"POSITION_COUNT:{account}")
        if str(row["permission"]) != "RESEARCH_ONLY": errors.append(f"PERMISSION:{account}")
        if str(row["trade_authority"]) != TRADE_AUTHORITY: errors.append(f"AUTHORITY:{account}")
        a = allocations[(allocations["account"].eq(account)) & (allocations["proposal_scenario_id"].eq(scenario))]
        if len(a) != int(count): errors.append(f"ALLOCATION_ACCOUNT_COUNT:{account}")
        if abs(float(pd.to_numeric(a["proposed_weight"], errors="coerce").sum()) - float(sleeve)) > 1e-9: errors.append(f"WEIGHT_SUM:{account}")
        for col in ("portfolio_role", "funding_source_class", "principal_falsifier", "review_triggers", "alternative_route", "initial_review_date"):
            if a[col].astype(str).str.strip().eq("").any(): errors.append(f"MISSING:{account}:{col}")
        for col in ("candidate_portfolio_correlation", "downside_correlation"):
            if pd.to_numeric(a[col], errors="coerce").isna().any(): errors.append(f"NONFINITE:{account}:{col}")

    # The frozen entry must be a byte-semantic copy of the accepted P4-4 proposal surface,
    # apart from the two explicit lineage columns added by P5A.
    if set(proposals.columns) - {"frozen_entry_phase", "frozen_from_p4_4_status"} != set(p4_proposals.columns): errors.append("PROPOSAL_SCHEMA_DRIFT")
    if set(allocations.columns) - {"frozen_entry_phase", "frozen_from_p4_4_status"} != set(p4_alloc.columns): errors.append("ALLOCATION_SCHEMA_DRIFT")
    p5p = proposals.drop(columns=["frozen_entry_phase", "frozen_from_p4_4_status"], errors="ignore").reset_index(drop=True)
    p5a = allocations.drop(columns=["frozen_entry_phase", "frozen_from_p4_4_status"], errors="ignore").reset_index(drop=True)
    try:
        pd.testing.assert_frame_equal(p5p[p4_proposals.columns], p4_proposals, check_dtype=False, check_exact=False, atol=1e-15, rtol=1e-15)
    except AssertionError:
        errors.append("PROPOSAL_ENTRY_DRIFT")
    try:
        pd.testing.assert_frame_equal(p5a[p4_alloc.columns], p4_alloc, check_dtype=False, check_exact=False, atol=1e-15, rtol=1e-15)
    except AssertionError:
        errors.append("ALLOCATION_ENTRY_DRIFT")

    if decision.get("phase_5_plan_frozen") is not True: errors.append("PLAN_NOT_FROZEN")
    if decision.get("additional_phase_5_business_gates_allowed") is not False: errors.append("EXTRA_P5_GATES")
    if decision.get("p5f_or_later_business_gate_authorized") is not False: errors.append("P5F_ALLOWED")
    if decision.get("phase_6_creation_authorized") is not False: errors.append("PHASE6_ALLOWED")
    if decision.get("next_gate") != acceptance["next_gate_on_pass"]: errors.append("NEXT_GATE")
    for field in ("candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"):
        if int(decision.get(field, -1)) != int(acceptance[field]): errors.append(f"DECISION_{field}")
    for field in ("target_portfolio_writeback", "pretrade_memo_produced", "user_trade_confirmation_recorded", "manual_execution_checklist_produced"):
        if decision.get(field) is not acceptance[field]: errors.append(f"DECISION_{field}")
    if decision.get("trade_authority") != TRADE_AUTHORITY: errors.append("DECISION_AUTHORITY")

    for flag in ("complete_p5a_to_p5e_sequence_frozen",):
        if quality.get(flag) is not True: errors.append(f"QUALITY_TRUE:{flag}")
    for flag in ("new_business_gate_after_p5e_allowed", "repair_gate_may_change_business_objective", "technical_pass_may_substitute_user_approval", "proposal_may_be_treated_as_execution", "real_cash_treated_as_strategic_target", "pretrade_memo_produced", "user_trade_confirmation_recorded", "manual_execution_checklist_produced"):
        if quality.get(flag) is not False: errors.append(f"QUALITY_FALSE:{flag}")
    if int(quality.get("portfolio_mutations", -1)) != 0: errors.append("QUALITY_MUTATION")
    if int(quality.get("orders_created", -1)) != 0: errors.append("QUALITY_ORDERS")
    if quality.get("trade_authority") != TRADE_AUTHORITY: errors.append("QUALITY_AUTHORITY")

    checks = {
        "contract_sha256": root / "config/hkcu_p5a_phase5_contract_entry_freeze.json",
        "p4_4_decision_sha256": p4_decision_path,
        "p4_4_preferred_proposals_sha256": p4_proposals_path,
        "p4_4_proposal_allocations_sha256": p4_alloc_path,
        "real_positions_current_sha256": root / contract["authoritative_inputs"]["real_positions_current"],
        "simulation_positions_current_sha256": root / contract["authoritative_inputs"]["simulation_positions_current"],
        "gate_register_sha256": out / f"{prefix}_GATE_REGISTER.csv",
        "entry_proposals_sha256": out / f"{prefix}_PROPOSALS.csv",
        "entry_allocations_sha256": out / f"{prefix}_ALLOCATIONS.csv",
    }
    for field, path in checks.items():
        if manifest.get(field) != sha256_file(path): errors.append(f"MANIFEST:{field}")
    if manifest.get("trade_authority") != TRADE_AUTHORITY: errors.append("MANIFEST_AUTHORITY")

    result = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not errors else "FAIL",
        "operational_status": decision.get("status"),
        "entry_p4_4_status": p4_decision.get("status"),
        "phase_5_gate_count": len(gates),
        "entry_preferred_proposal_count": len(proposals),
        "entry_proposal_allocation_count": len(allocations),
        "next_gate": decision.get("next_gate"),
        "errors": errors,
        "trade_authority": TRADE_AUTHORITY,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if errors:
        raise SystemExit(1)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--p4-4-dir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    validate(Path(args.repo_root).resolve(), Path(args.p4_4_dir).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
