#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

PROGRAM_ID = "HKCU-P5A"
TRADE_AUTHORITY = "NONE"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def finite(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def build(root: Path, p4_4_dir: Path, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    contract_path = root / "config/hkcu_p5a_phase5_contract_entry_freeze.json"
    contract = read_json(contract_path)
    p4_contract = read_json(root / contract["authoritative_inputs"]["p4_4_contract"])
    p4_prefix = p4_contract["output_prefix"]
    entry = contract["entry_contract"]
    acceptance = contract["acceptance"]
    prefix = contract["output_prefix"]

    p4_decision_path = p4_4_dir / f"{p4_prefix}_DECISION.json"
    p4_proposals_path = p4_4_dir / f"{p4_prefix}_PREFERRED_PROPOSALS.csv"
    p4_alloc_path = p4_4_dir / f"{p4_prefix}_PROPOSAL_ALLOCATIONS.csv"
    p4_decision = read_json(p4_decision_path)
    proposals = pd.read_csv(p4_proposals_path, keep_default_na=False)
    allocations = pd.read_csv(p4_alloc_path, dtype={"stock_code_5d": str}, keep_default_na=False)

    real_state_path = root / contract["authoritative_inputs"]["real_positions_current"]
    sim_state_path = root / contract["authoritative_inputs"]["simulation_positions_current"]

    errors: list[str] = []
    if p4_decision.get("status") != entry["required_p4_4_status"]: errors.append("P4_4_STATUS")
    if p4_decision.get("phase_close_status") != entry["required_p4_4_phase_close_status"]: errors.append("P4_4_PHASE_NOT_CLOSED")
    if p4_decision.get("additional_p4_subphases_allowed") is not entry["required_p4_4_additional_subphases_allowed"]: errors.append("P4_4_SUBPHASE_BOUNDARY")
    if p4_decision.get("trade_authority") != TRADE_AUTHORITY: errors.append("P4_4_AUTHORITY")
    if len(proposals) != entry["required_preferred_proposal_count"]: errors.append("PREFERRED_PROPOSAL_COUNT")
    if len(allocations) != entry["required_proposal_allocation_count"]: errors.append("PROPOSAL_ALLOCATION_COUNT")

    expected = {
        "REAL": (entry["required_real_preferred_scenario"], entry["required_real_hk_sleeve"], entry["required_real_position_count"]),
        "SIMULATION": (entry["required_simulation_preferred_scenario"], entry["required_simulation_hk_sleeve"], entry["required_simulation_position_count"]),
    }
    for account, (scenario, sleeve, count) in expected.items():
        p = proposals[proposals["account"].astype(str).eq(account)]
        if len(p) != 1:
            errors.append(f"PROPOSAL_ACCOUNT_COUNT:{account}")
            continue
        row = p.iloc[0]
        if str(row["preferred_scenario_id"]) != scenario: errors.append(f"SCENARIO:{account}")
        w = finite(row["hk_sleeve_proposed"])
        if w is None or abs(w - float(sleeve)) > 1e-9: errors.append(f"SLEEVE:{account}")
        if int(float(row["position_count"])) != int(count): errors.append(f"POSITION_COUNT:{account}")
        if str(row["permission"]) != "RESEARCH_ONLY": errors.append(f"PERMISSION:{account}")
        if str(row["trade_authority"]) != TRADE_AUTHORITY: errors.append(f"AUTHORITY:{account}")
        if str(row["portfolio_mutation"]).lower() not in {"false", "0"}: errors.append(f"PROPOSAL_MUTATION:{account}")
        if int(float(row["orders_created"])) != 0: errors.append(f"PROPOSAL_ORDERS:{account}")

        a = allocations[(allocations["account"].astype(str).eq(account)) & (allocations["proposal_scenario_id"].astype(str).eq(scenario))].copy()
        if len(a) != int(count): errors.append(f"ALLOCATION_COUNT:{account}")
        if len(a):
            weight_sum = pd.to_numeric(a["proposed_weight"], errors="coerce").sum()
            if abs(float(weight_sum) - float(sleeve)) > 1e-9: errors.append(f"ALLOCATION_WEIGHT_SUM:{account}")
            for col in ("portfolio_role", "funding_source_class", "principal_falsifier", "review_triggers", "alternative_route", "initial_review_date"):
                if a[col].astype(str).str.strip().eq("").any(): errors.append(f"ALLOCATION_MISSING:{account}:{col}")
            for col in ("candidate_portfolio_correlation", "downside_correlation"):
                vals = pd.to_numeric(a[col], errors="coerce")
                if vals.isna().any(): errors.append(f"ALLOCATION_NONFINITE:{account}:{col}")
            if a["portfolio_mutation"].astype(str).str.lower().isin({"true", "1"}).any(): errors.append(f"ALLOCATION_MUTATION:{account}")
            if pd.to_numeric(a["orders_created"], errors="coerce").fillna(0).ne(0).any(): errors.append(f"ALLOCATION_ORDERS:{account}")
            if not a["trade_authority"].astype(str).eq(TRADE_AUTHORITY).all(): errors.append(f"ALLOCATION_AUTHORITY:{account}")

    gates = pd.DataFrame(contract["phase_5_gate_sequence"])
    if list(gates["gate_id"].astype(str)) != contract["planning_governance"]["frozen_business_gate_ids"]:
        errors.append("GATE_SEQUENCE")
    if len(gates) != acceptance["phase_5_gate_count"]: errors.append("GATE_COUNT")
    if contract["planning_governance"]["additional_phase_5_business_gates_allowed"] is not False: errors.append("EXTRA_P5_GATES_ALLOWED")
    if contract["planning_governance"]["p5f_or_later_business_gate_authorized"] is not False: errors.append("P5F_AUTHORIZED")
    if contract["planning_governance"]["phase_6_creation_authorized"] is not False: errors.append("PHASE6_AUTHORIZED")
    if contract["phase_boundary"]["trade_authority"] != TRADE_AUTHORITY: errors.append("CONTRACT_AUTHORITY")

    frozen_proposals = proposals.copy()
    frozen_proposals.insert(0, "frozen_entry_phase", contract["phase"])
    frozen_proposals["frozen_from_p4_4_status"] = p4_decision.get("status", "")
    frozen_allocations = allocations.copy()
    frozen_allocations.insert(0, "frozen_entry_phase", contract["phase"])
    frozen_allocations["frozen_from_p4_4_status"] = p4_decision.get("status", "")

    gates_path = out / f"{prefix}_GATE_REGISTER.csv"
    proposals_path = out / f"{prefix}_PROPOSALS.csv"
    allocations_path = out / f"{prefix}_ALLOCATIONS.csv"
    gates.to_csv(gates_path, index=False)
    frozen_proposals.to_csv(proposals_path, index=False)
    frozen_allocations.to_csv(allocations_path, index=False)

    status = acceptance["pass_status"] if not errors else acceptance["fail_status"]
    decision = {
        "program_id": PROGRAM_ID,
        "phase": contract["phase"],
        "as_of_date": contract["as_of_date"],
        "status": status,
        "entry_p4_4_status": p4_decision.get("status"),
        "entry_p4_4_phase_close_status": p4_decision.get("phase_close_status"),
        "phase_5_gate_count": len(gates),
        "phase_5_plan_frozen": not errors,
        "additional_phase_5_business_gates_allowed": False,
        "p5f_or_later_business_gate_authorized": False,
        "phase_6_creation_authorized": False,
        "entry_preferred_proposal_count": len(proposals),
        "entry_proposal_allocation_count": len(allocations),
        "entry_real_scenario": entry["required_real_preferred_scenario"],
        "entry_simulation_scenario": entry["required_simulation_preferred_scenario"],
        "pretrade_memo_produced": False,
        "user_trade_confirmation_recorded": False,
        "manual_execution_checklist_produced": False,
        "target_portfolio_writeback": False,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "next_gate": acceptance["next_gate_on_pass"] if not errors else acceptance["repair_gate"],
        "integrity_failures": errors,
        "trade_authority": TRADE_AUTHORITY,
    }
    quality = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not errors else "FAIL",
        "complete_p5a_to_p5e_sequence_frozen": True,
        "new_business_gate_after_p5e_allowed": False,
        "repair_gate_may_change_business_objective": False,
        "technical_pass_may_substitute_user_approval": False,
        "proposal_may_be_treated_as_execution": False,
        "real_cash_treated_as_strategic_target": False,
        "pretrade_memo_produced": False,
        "user_trade_confirmation_recorded": False,
        "manual_execution_checklist_produced": False,
        "portfolio_mutations": 0,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
        "hard_failures": errors,
    }
    manifest = {
        "program_id": PROGRAM_ID,
        "contract_sha256": sha256_file(contract_path),
        "p4_4_decision_sha256": sha256_file(p4_decision_path),
        "p4_4_preferred_proposals_sha256": sha256_file(p4_proposals_path),
        "p4_4_proposal_allocations_sha256": sha256_file(p4_alloc_path),
        "real_positions_current_sha256": sha256_file(real_state_path),
        "simulation_positions_current_sha256": sha256_file(sim_state_path),
        "gate_register_sha256": sha256_file(gates_path),
        "entry_proposals_sha256": sha256_file(proposals_path),
        "entry_allocations_sha256": sha256_file(allocations_path),
        "trade_authority": TRADE_AUTHORITY,
    }

    write_json(out / f"{prefix}_DECISION.json", decision)
    write_json(out / f"{prefix}_QUALITY_REPORT.json", quality)
    write_json(out / f"{prefix}_MANIFEST.json", manifest)
    if errors:
        raise SystemExit("P5A_ENTRY_FREEZE_FAILED:" + "|".join(errors))
    return decision


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--p4-4-dir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.p4_4_dir).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
