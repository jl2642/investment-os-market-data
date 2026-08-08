#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROGRAM_ID = "HKCU-P3-0"
PASS_STATUS = "PASS_P3_0_CANDIDATE_GRADUATION_CONTRACT"
NEXT_GATE = "P3_1_CANDIDATE_GRADUATION_ASSESSMENT"
TRADE_AUTHORITY = "NONE"
EXPECTED_BLOCKERS = {
    "HKEX:00551",
    "HKEX:01114",
    "HKEX:02313",
    "HKEX:06110",
    "HKEX:09636",
}
EXPECTED_RULE_IDS = {f"P3R{i:02d}" for i in range(1, 13)}
EXPECTED_ASSESSMENT_STATES = {
    "PROPOSE_CORE_CANDIDATE",
    "PROPOSE_WATCH_CANDIDATE",
    "DEFER_RESEARCH_MONITOR",
    "HOLD_RETAINED_INVESTMENT_BLOCKER",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    root = Path(args.repo_root)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    contract_path = root / "config/hkcu_p3_0_candidate_graduation_contract.json"
    upstream_path = root / "config/hkcu_p2b_final_cross_sectional_synthesis_contract.json"
    contract = read_json(contract_path)
    upstream = read_json(upstream_path)
    errors: list[str] = []

    if contract.get("program_id") != PROGRAM_ID:
        errors.append("PROGRAM_ID")
    if contract.get("phase") != "P3_0_CANDIDATE_GRADUATION_CONTRACT":
        errors.append("PHASE")
    if contract.get("as_of_date") != upstream.get("as_of_date"):
        errors.append("AS_OF_DATE_LINEAGE")

    auth = contract.get("authoritative_upstream", {})
    upstream_counts = upstream.get("expected_counts", {})
    if upstream.get("program_id") != auth.get("required_program_id"):
        errors.append("UPSTREAM_PROGRAM")
    if upstream.get("pass_status") != auth.get("required_pass_status"):
        errors.append("UPSTREAM_PASS_STATUS")
    if upstream.get("next_gate") != auth.get("required_next_gate"):
        errors.append("UPSTREAM_NEXT_GATE")
    if int(upstream_counts.get("security_count", -1)) != int(auth.get("entry_security_count", -2)):
        errors.append("ENTRY_SECURITY_COUNT")
    if int(upstream_counts.get("advance_security_count", -1)) != int(auth.get("evaluation_eligible_security_count", -2)):
        errors.append("ELIGIBLE_SECURITY_COUNT")
    if int(upstream_counts.get("blocked_security_count", -1)) != int(auth.get("retained_blocker_security_count", -2)):
        errors.append("BLOCKED_SECURITY_COUNT")
    if set(upstream_counts.get("blocked_security_ids", [])) != EXPECTED_BLOCKERS:
        errors.append("UPSTREAM_BLOCKER_SET")
    if set(auth.get("retained_blocker_security_ids", [])) != EXPECTED_BLOCKERS:
        errors.append("CONTRACT_BLOCKER_SET")

    boundary = contract.get("phase_boundary", {})
    if boundary.get("contract_definition_authorized") is not True:
        errors.append("CONTRACT_DEFINITION_SCOPE")
    for k in [
        "security_assessment_authorized",
        "formal_candidate_graduation_authorized",
        "candidate_pool_mutation_authorized",
        "simulation_mutation_authorized",
        "real_account_mutation_authorized",
        "order_creation_authorized",
    ]:
        if boundary.get(k) is not False:
            errors.append("BOUNDARY_" + k.upper())
    if boundary.get("trade_authority") != TRADE_AUTHORITY:
        errors.append("BOUNDARY_TRADE_AUTHORITY")

    philosophy = contract.get("graduation_philosophy", {})
    required_true = [
        "all_applicable_hard_rules_must_pass",
        "p2a_rank_is_context_not_graduation_authority",
        "p2b_evidence_balance_is_context_not_score",
        "missing_consensus_is_not_bearish",
        "confidence_cap_is_not_automatic_rejection",
        "ah_relative_value_is_context_not_alpha",
        "candidate_graduation_is_not_portfolio_allocation",
        "candidate_graduation_is_not_trade_authority",
    ]
    required_false = [
        "weighted_composite_score_allowed",
        "neutral_fill_allowed",
        "automatic_waiver_allowed",
        "arbitrary_fixed_top_n_allowed",
    ]
    for k in required_true:
        if philosophy.get(k) is not True:
            errors.append("PHILOSOPHY_" + k.upper())
    for k in required_false:
        if philosophy.get(k) is not False:
            errors.append("PHILOSOPHY_" + k.upper())

    rules = contract.get("graduation_rules", [])
    rule_ids = [r.get("rule_id") for r in rules]
    if len(rules) != 12:
        errors.append("RULE_COUNT")
    if len(set(rule_ids)) != len(rule_ids):
        errors.append("DUPLICATE_RULE_ID")
    if set(rule_ids) != EXPECTED_RULE_IDS:
        errors.append("RULE_ID_SET")
    hard_rules = [r for r in rules if r.get("type") == "HARD"]
    decision_rules = [r for r in rules if r.get("type") == "DECISION"]
    if len(hard_rules) != 9 or len(decision_rules) != 3:
        errors.append("RULE_TYPE_COUNTS")
    if any(not str(r.get("requirement", "")).strip() for r in rules):
        errors.append("EMPTY_RULE_REQUIREMENT")

    states = set(contract.get("assessment_states", []))
    if states != EXPECTED_ASSESSMENT_STATES:
        errors.append("ASSESSMENT_STATE_SET")
    routing = contract.get("assessment_routing", {})
    if set(routing) != EXPECTED_ASSESSMENT_STATES:
        errors.append("ASSESSMENT_ROUTING_SET")

    promotion = contract.get("promotion_contract", {})
    if promotion.get("p3_1_is_assessment_only") is not True:
        errors.append("P3_1_ASSESSMENT_ONLY")
    if promotion.get("p3_1_candidate_pool_mutation_authorized") is not False:
        errors.append("P3_1_MUTATION_BOUNDARY")
    if promotion.get("formal_promotion_requires_separate_gate") != "P3_2_CANDIDATE_POOL_PROMOTION":
        errors.append("PROMOTION_GATE")
    if promotion.get("promotion_does_not_authorize_simulation_or_real_trade") is not True:
        errors.append("PROMOTION_TRADE_SEPARATION")
    if promotion.get("automatic_trade_authority_after_promotion") is not False:
        errors.append("PROMOTION_AUTO_TRADE")

    acceptance = contract.get("acceptance", {})
    if int(acceptance.get("graduation_rule_count", -1)) != 12:
        errors.append("ACCEPT_RULE_COUNT")
    if int(acceptance.get("entry_security_count", -1)) != 77:
        errors.append("ACCEPT_ENTRY_COUNT")
    if int(acceptance.get("evaluation_eligible_security_count", -1)) != 72:
        errors.append("ACCEPT_ELIGIBLE_COUNT")
    if int(acceptance.get("retained_blocker_security_count", -1)) != 5:
        errors.append("ACCEPT_BLOCKED_COUNT")
    if int(acceptance.get("formal_candidate_graduation_count", -1)) != 0:
        errors.append("FORMAL_GRADUATION_COUNT")
    for k in ["candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"]:
        if int(acceptance.get(k, -1)) != 0:
            errors.append("ACCEPT_" + k.upper())
    if acceptance.get("pass_status") != PASS_STATUS:
        errors.append("PASS_STATUS")
    if acceptance.get("next_gate") != NEXT_GATE:
        errors.append("NEXT_GATE")
    if acceptance.get("trade_authority") != TRADE_AUTHORITY:
        errors.append("TRADE_AUTHORITY")

    decision = {
        "program_id": PROGRAM_ID,
        "phase": contract.get("phase"),
        "status": PASS_STATUS if not errors else "BLOCKED_P3_0_CANDIDATE_GRADUATION_CONTRACT",
        "entry_security_count": auth.get("entry_security_count"),
        "evaluation_eligible_security_count": auth.get("evaluation_eligible_security_count"),
        "retained_blocker_security_count": auth.get("retained_blocker_security_count"),
        "retained_blocker_security_ids": sorted(auth.get("retained_blocker_security_ids", [])),
        "graduation_rule_count": len(rules),
        "formal_candidate_graduation_count": 0,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "next_gate": NEXT_GATE if not errors else None,
        "trade_authority": TRADE_AUTHORITY,
    }
    quality = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not errors else "FAIL",
        "hard_failures": sorted(set(errors)),
        "upstream_p2b_final_lineage_bound": not any(e.startswith("UPSTREAM_") or e.endswith("_COUNT") for e in errors),
        "no_weighted_score": philosophy.get("weighted_composite_score_allowed") is False,
        "no_neutral_fill": philosophy.get("neutral_fill_allowed") is False,
        "no_fixed_top_n": philosophy.get("arbitrary_fixed_top_n_allowed") is False,
        "missing_consensus_is_not_bearish": philosophy.get("missing_consensus_is_not_bearish") is True,
        "confidence_cap_is_not_rejection": philosophy.get("confidence_cap_is_not_automatic_rejection") is True,
        "p3_0_has_zero_candidate_mutation": acceptance.get("candidate_pool_mutations") == 0,
        "p3_1_is_assessment_only": promotion.get("p3_1_is_assessment_only") is True,
        "formal_promotion_separate_from_trade": promotion.get("promotion_does_not_authorize_simulation_or_real_trade") is True,
        "trade_authority": TRADE_AUTHORITY,
    }
    write_json(out / "HKCU_P3_0_CONTRACT_DECISION.json", decision)
    write_json(out / "HKCU_P3_0_CONTRACT_QUALITY_REPORT.json", quality)

    if errors:
        raise SystemExit("P3_0_CONTRACT_VALIDATION_FAILED:" + "|".join(sorted(set(errors))))
    print(PASS_STATUS)


if __name__ == "__main__":
    main()
