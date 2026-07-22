#!/usr/bin/env python3
"""Deterministic validator for the FMDL-6X1-A dual activation contract."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_PHASES = [
    "FMDL-6X1-A_EXISTING_PILOT_AUDIT_AND_DUAL_ACTIVATION_CONTRACT",
    "FMDL-6X1-B_ANTICIPATED_RESEARCH_UNIVERSE_AND_INSTRUMENT_BOUNDARY",
    "FMDL-6X1-C_SOURCE_COST_AND_EXECUTION_ROUTE_REVALIDATION",
    "FMDL-6X1-D_FULL_BUILD_CONTRACT_AND_FMDL6X2_HANDOFF",
    "FMDL-6X1-FINAL_OPERATIONAL_ACCEPTANCE",
]
EXPECTED_SHA = "479d375da1586419a98bb2821342cf691b0d1358882b66bc1601fd717ab2a9aa"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("contract root must be an object")
    return value


def canonical_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    def expect(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    expect(contract.get("phase_id") == "FMDL-6X1-A", "phase_id mismatch")
    expect(contract.get("trade_authority") == "NONE", "trade authority must remain NONE")

    base = contract.get("investment_os_base", {})
    expect(base.get("release_id") == "INVESTMENT_OS_R8_20260720_501345e84562", "Release-8 identity mismatch")
    expect(base.get("release_sequence") == 8, "release sequence must be 8")
    expect(base.get("package_sha256") == EXPECTED_SHA, "canonical package SHA mismatch")
    expect(base.get("manifest_file_count") == 61, "manifest file count mismatch")
    expect(base.get("nested_runtime_package_count") == 4, "nested runtime package count mismatch")
    expect(base.get("integrity_status") == "PASS", "package integrity is not PASS")

    channel = contract.get("user_channel_fact", {})
    expect(channel.get("has_current_us_brokerage_channel") is False, "current channel fact must remain false")
    expect(channel.get("channel_status") == "NO_CURRENT_CHANNEL", "channel status mismatch")

    activation = contract.get("dual_activation", {})
    research = activation.get("research_production_gate", {})
    brokerage = activation.get("brokerage_real_account_gate", {})
    expect(research.get("status") == "OPEN_FOR_CONTROLLED_BUILD", "research-production gate is not open")
    expect(brokerage.get("status") == "CLOSED_NO_CHANNEL", "brokerage gate must remain closed")
    expect(len(brokerage.get("required_conditions", [])) >= 5, "brokerage gate conditions incomplete")

    rules = contract.get("no_channel_rules", {})
    expect(rules.get("default_channel_status") == "CHANNEL_ELIGIBILITY_PENDING", "default channel status mismatch")
    for key in ("candidate_admission_authorized", "simulation_admission_authorized", "real_account_admission_authorized", "order_generation_authorized"):
        expect(rules.get(key) is False, f"{key} must be false")

    plan = contract.get("fixed_execution_plan", {})
    expect(plan.get("planned_subphases") == EXPECTED_PHASES, "fixed phase sequence mismatch")
    expect(plan.get("planned_round_count") == 5, "planned round count must be 5")
    expect(plan.get("maximum_targeted_repair_rounds") == 2, "repair cap must be 2")

    mutations = contract.get("zero_mutation_proof", {})
    for key in ("candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders"):
        expect(mutations.get(key) == 0, f"{key} must equal zero")

    expect(contract.get("required_exit_status") == "FMDL6X1A_EXISTING_PILOT_AUDIT_AND_DUAL_ACTIVATION_CONTRACT_ACCEPTED", "exit status mismatch")
    expect(contract.get("next_gate") == "FMDL-6X1-B_ANTICIPATED_RESEARCH_UNIVERSE_AND_INSTRUMENT_BOUNDARY", "next gate mismatch")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", default="config/fmdl6x1a_existing_pilot_audit_dual_activation_contract.json")
    parser.add_argument("--output")
    args = parser.parse_args()

    contract = load_json(Path(args.contract))
    errors = validate(contract)
    result = {
        "phase_id": "FMDL-6X1-A",
        "status": "PASS" if not errors else "FAIL",
        "error_count": len(errors),
        "errors": errors,
        "contract_sha256": canonical_hash(contract),
        "trade_authority": "NONE",
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
