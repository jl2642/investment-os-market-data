#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

PROGRAM_ID = "HKCU-P5E"
TRADE_AUTHORITY = "NONE"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(root: Path, p5c_dir: Path, p5d_dir: Path, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    contract = read_json(root / "config/hkcu_p5e_zero_execution_reconciliation_observation_contract.json")
    entry = contract["entry_contract"]
    acceptance = contract["acceptance"]
    policy = contract["zero_execution_reconciliation_policy"]
    observation_policy = contract["observation_policy"]

    p5c_contract = read_json(root / contract["authoritative_inputs"]["p5c_contract"])
    p5d_contract = read_json(root / contract["authoritative_inputs"]["p5d_contract"])
    p5c_prefix = p5c_contract["output_prefix"]
    p5d_prefix = p5d_contract["output_prefix"]

    p5c_decision = read_json(p5c_dir / f"{p5c_prefix}_DECISION.json")
    p5c_packet = pd.read_csv(
        p5c_dir / f"{p5c_prefix}_DECISION_PACKET.csv",
        dtype={"stock_code_5d": str},
        keep_default_na=False,
    )
    p5d_decision = read_json(p5d_dir / f"{p5d_prefix}_DECISION.json")

    real_path = root / contract["authoritative_inputs"]["real_positions_current"]
    sim_path = root / contract["authoritative_inputs"]["simulation_positions_current"]
    candidate_path = root / contract["authoritative_inputs"]["hk_candidate_current"]

    protected_paths = {
        "REAL_CURRENT": real_path,
        "SIMULATION_CURRENT": sim_path,
        "HK_CANDIDATE_CURRENT": candidate_path,
    }
    hashes_before = {key: sha256_file(path) for key, path in protected_paths.items()}

    candidates = pd.read_csv(candidate_path, dtype={"stock_code_5d": str}, keep_default_na=False)
    focus_ids = sorted(set(p5c_packet["security_id"].astype(str))) if "security_id" in p5c_packet.columns else []
    focus_set = set(focus_ids)

    errors: list[str] = []
    if p5d_decision.get("status") != entry["required_p5d_status"]:
        errors.append("P5D_STATUS")
    if p5d_decision.get("production_execution_state") != entry["required_p5d_production_execution_state"]:
        errors.append("P5D_PRODUCTION_EXECUTION_STATE")
    if p5d_decision.get("next_gate") != entry["required_p5d_next_gate"]:
        errors.append("P5D_NEXT_GATE")
    if int(p5d_decision.get("production_real_execution_checklist_rows", -1)) != entry["required_real_execution_checklist_rows"]:
        errors.append("P5D_REAL_CHECKLIST_ROWS")
    if int(p5d_decision.get("orders_created", -1)) != entry["required_orders_created"]:
        errors.append("P5D_ORDERS")
    if int(p5d_decision.get("fills_inferred", -1)) != entry["required_fills_inferred"]:
        errors.append("P5D_FILLS")
    if p5d_decision.get("trade_authority") != TRADE_AUTHORITY:
        errors.append("P5D_TRADE_AUTHORITY")

    if int(p5c_decision.get("user_decision_recorded_count", -1)) != entry["required_user_decision_recorded_count"]:
        errors.append("P5C_USER_DECISION_COUNT")
    if "user_decision" not in p5c_packet.columns:
        errors.append("P5C_PACKET_USER_DECISION_COLUMN")
    elif p5c_packet["user_decision"].astype(str).str.strip().ne("").any():
        errors.append("P5C_PACKET_HAS_USER_DECISION")

    if len(candidates) != entry["required_candidate_count"]:
        errors.append("HK_CANDIDATE_COUNT")
    if "candidate_status" not in candidates.columns or not candidates["candidate_status"].astype(str).eq("ACTIVE").all():
        errors.append("HK_CANDIDATE_ACTIVE_STATE")
    if "formal_candidate_graduation" not in candidates.columns or not candidates["formal_candidate_graduation"].astype(str).str.lower().eq("true").all():
        errors.append("HK_CANDIDATE_FORMAL_GRADUATION_STATE")
    if len(focus_ids) != entry["required_p5c_focus_security_count"]:
        errors.append("P5C_FOCUS_SECURITY_COUNT")
    candidate_ids = set(candidates["security_id"].astype(str)) if "security_id" in candidates.columns else set()
    if not focus_set.issubset(candidate_ids):
        errors.append("P5C_FOCUS_NOT_SUBSET_OF_CANDIDATE")

    if int(policy["user_supplied_real_execution_fact_count"]) != 0:
        errors.append("REAL_EXECUTION_FACT_COUNT_NOT_ZERO")
    if int(policy["explicit_simulation_activation_record_count"]) != 0:
        errors.append("SIMULATION_ACTIVATION_COUNT_NOT_ZERO")

    observation = candidates[[c for c in ["p2a_overall_rank", "security_id", "stock_code_5d", "security_name", "candidate_tier", "candidate_status", "as_of_date", "primary_sleeve", "principal_falsifier", "monitor_triggers"] if c in candidates.columns]].copy()
    observation["observation_state"] = observation_policy["observation_state"]
    observation["p5c_focus"] = observation["security_id"].astype(str).isin(focus_set)
    observation["focus_state"] = observation["p5c_focus"].map(
        {True: observation_policy["focus_state"], False: "STANDARD_CANDIDATE_OPERATING_OBSERVATION"}
    )
    observation["candidate_membership_mutated"] = False
    observation["candidate_tier_mutated"] = False
    observation["portfolio_writeback"] = False
    observation["trade_instruction"] = False
    observation["trade_authority"] = TRADE_AUTHORITY
    observation.to_csv(out / "HKCU_P5E_ZERO_EXECUTION_OPERATING_OBSERVATION.csv", index=False)

    hashes_after = {key: sha256_file(path) for key, path in protected_paths.items()}
    hash_mismatches = sorted(key for key in hashes_before if hashes_before[key] != hashes_after[key])
    if hash_mismatches:
        errors.append("PROTECTED_CURRENT_HASH_MISMATCH:" + ",".join(hash_mismatches))

    focus_count = int(observation["p5c_focus"].sum())
    if len(observation) != acceptance["formal_candidate_observation_count"]:
        errors.append("OBSERVATION_CANDIDATE_COUNT")
    if focus_count != acceptance["p5c_focus_observation_count"]:
        errors.append("OBSERVATION_FOCUS_COUNT")

    decision = {
        "program_id": PROGRAM_ID,
        "status": acceptance["pass_status"] if not errors else acceptance["fail_status"],
        "errors": sorted(set(errors)),
        "reconciliation_mode": "ZERO_EXECUTION_NO_WRITEBACK",
        "explicit_user_trade_approval_present": False,
        "user_supplied_real_execution_fact_count": 0,
        "explicit_simulation_activation_record_count": 0,
        "real_execution_reconciled_count": 0,
        "simulation_activation_reconciled_count": 0,
        "real_account_mutations": 0,
        "simulation_mutations": 0,
        "candidate_pool_mutations": 0,
        "target_writebacks": 0,
        "orders_created": 0,
        "fills_inferred": 0,
        "protected_hashes_before": hashes_before,
        "protected_hashes_after": hashes_after,
        "protected_hash_mismatches": hash_mismatches,
        "formal_candidate_observation_count": len(observation),
        "p5c_focus_observation_count": focus_count,
        "p5c_focus_security_ids": focus_ids,
        "phase_5_close_status": acceptance["phase_5_close_status"] if not errors else "PHASE_5_NOT_CLOSED",
        "post_p5e_operating_state": acceptance["post_p5e_operating_state"] if not errors else "P5E_REPAIR_REQUIRED",
        "next_business_gate": acceptance["next_business_gate"] if not errors else acceptance["repair_gate"],
        "additional_phase_5_business_gates_allowed": False,
        "p5f_or_later_business_gate_authorized": False,
        "phase_6_creation_authorized": False,
        "trade_authority": TRADE_AUTHORITY,
    }
    write_json(out / "HKCU_P5E_ZERO_EXECUTION_DECISION.json", decision)

    md = [
        "# HKCU P5E｜Zero-Execution Reconciliation & Operating Observation",
        "",
        f"Status: **{decision['status']}**",
        f"Phase 5: **{decision['phase_5_close_status']}**",
        f"Operating state: **{decision['post_p5e_operating_state']}**",
        "",
        "No user trade decision or user-supplied execution fact exists, and no SIMULATION activation is recorded. P5E therefore performs zero execution reconciliation and zero writeback; it does not infer trades from the proposal, Pre-trade Memo, P5C technical PASS or P5D synthetic fixture.",
        "",
        f"REAL/SIMULATION/HK Candidate protected hash mismatches: **{len(hash_mismatches)}**.",
        f"Formal HK Candidates in operating observation: **{len(observation)}**.",
        f"Current P5C focus securities in operating observation: **{focus_count}**.",
        "",
        "No P5F business gate or HKCU Phase 6 is authorized. Further activity belongs to normal operating observation and future governed reviews, not continued special-development gate expansion.",
        f"Trade authority: **{TRADE_AUTHORITY}**",
    ]
    (out / "HKCU_P5E_ZERO_EXECUTION.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return decision


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--p5c-dir", required=True)
    parser.add_argument("--p5d-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    decision = build(Path(args.repo_root), Path(args.p5c_dir), Path(args.p5d_dir), Path(args.output))
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    if decision["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
