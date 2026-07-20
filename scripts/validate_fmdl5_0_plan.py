#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("program_id") != "FMDL-5-0": errors.append("PROGRAM_ID")
    if plan.get("trade_authority") != "NONE": errors.append("TRADE_AUTHORITY")
    if plan.get("base_release", {}).get("release_sequence") != 8: errors.append("BASE_RELEASE")
    if len(plan.get("fmdl5", {}).get("formal_subphases", [])) != 8: errors.append("FMDL5_PHASE_COUNT")
    if plan.get("fmdl5", {}).get("maximum_total_rounds_including_repairs", 99) > 10: errors.append("FMDL5_ROUND_CAP")
    if len(plan.get("fmdl6", {}).get("formal_subphases", [])) != 10: errors.append("FMDL6_PHASE_COUNT")
    if plan.get("fmdl6", {}).get("maximum_total_rounds_including_repairs", 99) > 13: errors.append("FMDL6_ROUND_CAP")
    if plan.get("next_gate") != "FMDL-5A_MARKET_CONTRACT_AND_UNIVERSE_BOUNDARY": errors.append("NEXT_GATE")
    boundaries = plan.get("shared_state_boundaries", {})
    for key in (
        "research_graduation_is_not_candidate_admission",
        "candidate_admission_is_not_simulation_admission",
        "simulation_admission_is_not_real_account_admission",
        "real_account_action_requires_user_confirmation",
    ):
        if boundaries.get(key) is not True: errors.append(f"BOUNDARY:{key}")
    requirements = set(plan.get("phase_split_policy", {}).get("one_subphase_requires", []))
    if requirements != {"CONTRACT", "IMPLEMENTATION", "TESTS", "CI", "ACCEPTANCE_DECISION", "MAIN_PUBLICATION"}:
        errors.append("SUBPHASE_EXIT_CONTRACT")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", default="config/fmdl5_0_cross_market_master_plan.json")
    parser.add_argument("--output", default="outputs/fmdl5_0/candidate/FMDL5_0_DECISION.json")
    args = parser.parse_args()
    path = Path(args.plan)
    plan = load(path)
    errors = validate(plan)
    decision = {
        "program_id": "FMDL-5-0",
        "status": "FMDL5_0_CROSS_MARKET_ADAPTER_MASTER_PLAN_ACCEPTED" if not errors else "FAIL",
        "hard_failures": errors,
        "plan_sha256": sha256(path),
        "fmdl5_formal_subphase_count": len(plan["fmdl5"]["formal_subphases"]),
        "fmdl6_formal_subphase_count": len(plan["fmdl6"]["formal_subphases"]),
        "fmdl5_max_rounds": plan["fmdl5"]["maximum_total_rounds_including_repairs"],
        "fmdl6_max_rounds": plan["fmdl6"]["maximum_total_rounds_including_repairs"],
        "next_gate": plan["next_gate"],
        "trade_authority": "NONE",
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
