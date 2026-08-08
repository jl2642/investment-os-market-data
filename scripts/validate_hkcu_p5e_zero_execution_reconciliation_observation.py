#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

TRADE_AUTHORITY = "NONE"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(root: Path, p5c_dir: Path, p5d_dir: Path, out: Path) -> dict[str, Any]:
    contract = read_json(root / "config/hkcu_p5e_zero_execution_reconciliation_observation_contract.json")
    acceptance = contract["acceptance"]
    entry = contract["entry_contract"]
    p5c_contract = read_json(root / contract["authoritative_inputs"]["p5c_contract"])
    p5d_contract = read_json(root / contract["authoritative_inputs"]["p5d_contract"])
    p5c_prefix = p5c_contract["output_prefix"]
    p5d_prefix = p5d_contract["output_prefix"]

    p5c_decision = read_json(p5c_dir / f"{p5c_prefix}_DECISION.json")
    p5c_packet = pd.read_csv(p5c_dir / f"{p5c_prefix}_DECISION_PACKET.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    p5d_decision = read_json(p5d_dir / f"{p5d_prefix}_DECISION.json")
    decision = read_json(out / "HKCU_P5E_ZERO_EXECUTION_DECISION.json")
    observation = pd.read_csv(out / "HKCU_P5E_ZERO_EXECUTION_OPERATING_OBSERVATION.csv", dtype={"stock_code_5d": str}, keep_default_na=False)

    errors: list[str] = []
    if p5d_decision.get("status") != entry["required_p5d_status"]:
        errors.append("P5D_STATUS")
    if p5d_decision.get("production_execution_state") != entry["required_p5d_production_execution_state"]:
        errors.append("P5D_PRODUCTION_STATE")
    if p5d_decision.get("next_gate") != entry["required_p5d_next_gate"]:
        errors.append("P5D_NEXT_GATE")
    if int(p5d_decision.get("orders_created", -1)) != 0 or int(p5d_decision.get("fills_inferred", -1)) != 0:
        errors.append("P5D_EXECUTION_NOT_ZERO")

    if int(p5c_decision.get("user_decision_recorded_count", -1)) != 0:
        errors.append("P5C_DECISION_COUNT_NOT_ZERO")
    if "user_decision" not in p5c_packet.columns or p5c_packet["user_decision"].astype(str).str.strip().ne("").any():
        errors.append("P5C_PACKET_HAS_USER_DECISION")

    if decision.get("status") != acceptance["pass_status"]:
        errors.append("P5E_STATUS")
    if decision.get("phase_5_close_status") != acceptance["phase_5_close_status"]:
        errors.append("PHASE5_CLOSE_STATUS")
    if decision.get("post_p5e_operating_state") != acceptance["post_p5e_operating_state"]:
        errors.append("OPERATING_STATE")
    if decision.get("next_business_gate") is not None:
        errors.append("UNEXPECTED_NEXT_BUSINESS_GATE")
    if bool(decision.get("additional_phase_5_business_gates_allowed")):
        errors.append("ADDITIONAL_P5_GATE_ALLOWED")
    if bool(decision.get("p5f_or_later_business_gate_authorized")):
        errors.append("P5F_AUTHORIZED")
    if bool(decision.get("phase_6_creation_authorized")):
        errors.append("PHASE6_AUTHORIZED")
    if decision.get("trade_authority") != TRADE_AUTHORITY:
        errors.append("TRADE_AUTHORITY")

    zero_fields = [
        "user_supplied_real_execution_fact_count",
        "explicit_simulation_activation_record_count",
        "real_execution_reconciled_count",
        "simulation_activation_reconciled_count",
        "real_account_mutations",
        "simulation_mutations",
        "candidate_pool_mutations",
        "target_writebacks",
        "orders_created",
        "fills_inferred",
    ]
    for field in zero_fields:
        if int(decision.get(field, -1)) != 0:
            errors.append("NONZERO_" + field.upper())

    current_paths = {
        "REAL_CURRENT": root / contract["authoritative_inputs"]["real_positions_current"],
        "SIMULATION_CURRENT": root / contract["authoritative_inputs"]["simulation_positions_current"],
        "HK_CANDIDATE_CURRENT": root / contract["authoritative_inputs"]["hk_candidate_current"],
    }
    before = decision.get("protected_hashes_before", {})
    after = decision.get("protected_hashes_after", {})
    for key, path in current_paths.items():
        actual = sha256_file(path)
        if before.get(key) != actual:
            errors.append(f"{key}_BEFORE_HASH")
        if after.get(key) != actual:
            errors.append(f"{key}_AFTER_HASH")
        if before.get(key) != after.get(key):
            errors.append(f"{key}_HASH_CHANGED")
    if decision.get("protected_hash_mismatches"):
        errors.append("PROTECTED_HASH_MISMATCH_RECORDED")

    candidates = pd.read_csv(current_paths["HK_CANDIDATE_CURRENT"], dtype={"stock_code_5d": str}, keep_default_na=False)
    if len(candidates) != acceptance["formal_candidate_observation_count"]:
        errors.append("CANONICAL_CANDIDATE_COUNT")
    if len(observation) != acceptance["formal_candidate_observation_count"]:
        errors.append("OBSERVATION_COUNT")
    if set(observation["security_id"].astype(str)) != set(candidates["security_id"].astype(str)):
        errors.append("OBSERVATION_MEMBERSHIP_DRIFT")
    if not observation["observation_state"].astype(str).eq(contract["observation_policy"]["observation_state"]).all():
        errors.append("OBSERVATION_STATE")
    if observation["candidate_membership_mutated"].astype(str).str.lower().ne("false").any():
        errors.append("CANDIDATE_MUTATION_FLAG")
    if observation["candidate_tier_mutated"].astype(str).str.lower().ne("false").any():
        errors.append("CANDIDATE_TIER_MUTATION_FLAG")
    if observation["portfolio_writeback"].astype(str).str.lower().ne("false").any():
        errors.append("PORTFOLIO_WRITEBACK_FLAG")
    if observation["trade_instruction"].astype(str).str.lower().ne("false").any():
        errors.append("TRADE_INSTRUCTION_FLAG")
    if observation["trade_authority"].astype(str).ne(TRADE_AUTHORITY).any():
        errors.append("OBSERVATION_TRADE_AUTHORITY")

    focus_ids = set(p5c_packet["security_id"].astype(str))
    observed_focus = set(observation.loc[observation["p5c_focus"].astype(str).str.lower().eq("true"), "security_id"].astype(str))
    if len(focus_ids) != acceptance["p5c_focus_observation_count"]:
        errors.append("P5C_FOCUS_INPUT_COUNT")
    if observed_focus != focus_ids:
        errors.append("P5C_FOCUS_OBSERVATION_SET")
    if int(decision.get("formal_candidate_observation_count", -1)) != len(observation):
        errors.append("DECISION_OBSERVATION_COUNT")
    if int(decision.get("p5c_focus_observation_count", -1)) != len(observed_focus):
        errors.append("DECISION_FOCUS_COUNT")

    forbidden = [
        out / "HKCU_P5E_REAL_WRITEBACK.json",
        out / "HKCU_P5E_SIMULATION_WRITEBACK.json",
        out / "HKCU_P5E_CANDIDATE_WRITEBACK.csv",
        out / "HKCU_P5E_ORDER_LIST.csv",
        out / "HKCU_P5E_FILL_LEDGER.csv",
    ]
    if any(path.exists() for path in forbidden):
        errors.append("FORBIDDEN_WRITEBACK_OR_EXECUTION_OUTPUT")

    result = {
        "status": "PASS" if not errors else "FAIL",
        "errors": sorted(set(errors)),
        "phase_5_close_status": decision.get("phase_5_close_status"),
        "post_p5e_operating_state": decision.get("post_p5e_operating_state"),
        "formal_candidate_observation_count": decision.get("formal_candidate_observation_count"),
        "p5c_focus_observation_count": decision.get("p5c_focus_observation_count"),
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
    parser.add_argument("--p5d-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    validate(Path(args.repo_root), Path(args.p5c_dir), Path(args.p5d_dir), Path(args.output))


if __name__ == "__main__":
    main()
