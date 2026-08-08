#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

PROGRAM_ID = "HKCU-P4-0"
PASS_STATUS = "PASS_P4_0_PORTFOLIO_FIT_CONTRACT"
NEXT_GATE = "P4_1_PORTFOLIO_FIT_ASSESSMENT"
TRADE_AUTHORITY = "NONE"
EXPECTED_RULE_IDS = {f"P4R{i:02d}" for i in range(1, 16)}
EXPECTED_ACCOUNT_STATES = {
    "FIT",
    "FIT_WITH_CONSTRAINTS",
    "NO_INCREMENTAL_ROLE",
    "DEFER_PORTFOLIO_CONTEXT",
    "BLOCK_PORTFOLIO_FIT",
}
EXPECTED_COMBINED_ROUTES = {
    "ADVANCE_DUAL_CONSTRUCTION_REVIEW",
    "ADVANCE_SIMULATION_CONSTRUCTION_REVIEW",
    "ADVANCE_REAL_ACCOUNT_REVIEW",
    "HOLD_PORTFOLIO_WATCH",
    "DEFER_PORTFOLIO_CONTEXT",
    "BLOCK_PORTFOLIO_FIT",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def as_bool(value: object) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "y"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    root = Path(args.repo_root)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    contract = read_json(root / "config/hkcu_p4_0_portfolio_fit_contract.json")
    auth = contract.get("authoritative_upstream", {})
    context = contract.get("portfolio_context", {})
    errors: list[str] = []

    p3_contract = read_json(root / auth["p3_2_contract"])
    p3_decision = read_json(root / auth["p3_2_decision"])
    p3_manifest = read_json(root / auth["p3_2_manifest"])
    candidate_path = root / auth["p3_2_candidate_current"]
    real = read_json(root / context["real_positions_current"])
    sim = read_json(root / context["simulation_positions_current"])

    if contract.get("program_id") != PROGRAM_ID:
        errors.append("PROGRAM_ID")
    if contract.get("phase") != "P4_0_PORTFOLIO_FIT_CONTRACT":
        errors.append("PHASE")
    if contract.get("as_of_date") != p3_decision.get("as_of_date"):
        errors.append("AS_OF_DATE_LINEAGE")

    if p3_contract.get("program_id") != auth.get("required_program_id"):
        errors.append("UPSTREAM_CONTRACT_PROGRAM")
    if p3_decision.get("program_id") != auth.get("required_program_id"):
        errors.append("UPSTREAM_DECISION_PROGRAM")
    if p3_decision.get("status") != auth.get("required_pass_status"):
        errors.append("UPSTREAM_PASS_STATUS")
    if p3_decision.get("next_gate") != auth.get("required_next_gate"):
        errors.append("UPSTREAM_NEXT_GATE")
    if int(p3_decision.get("formal_candidate_count", -1)) != int(auth.get("entry_candidate_count", -2)):
        errors.append("ENTRY_CANDIDATE_COUNT")
    tier_counts = p3_decision.get("candidate_tier_counts", {})
    if int(tier_counts.get("CORE", -1)) != int(auth.get("core_candidate_count", -2)):
        errors.append("CORE_CANDIDATE_COUNT")
    if int(tier_counts.get("WATCH", -1)) != int(auth.get("watch_candidate_count", -2)):
        errors.append("WATCH_CANDIDATE_COUNT")
    if p3_decision.get("trade_authority") != TRADE_AUTHORITY:
        errors.append("UPSTREAM_TRADE_AUTHORITY")

    expected_candidate_sha = auth.get("accepted_candidate_current_sha256")
    manifest_candidate = p3_manifest.get("files", {}).get("HK_CANDIDATE_CURRENT.csv", {}).get("sha256")
    observed_candidate_sha = sha256_file(candidate_path)
    if manifest_candidate != expected_candidate_sha:
        errors.append("MANIFEST_CANDIDATE_SHA")
    if observed_candidate_sha != expected_candidate_sha:
        errors.append("CANDIDATE_CURRENT_SHA")

    with candidate_path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != int(auth.get("entry_candidate_count", -1)):
        errors.append("CANDIDATE_ROW_COUNT")
    if len({r.get("security_id") for r in rows}) != len(rows):
        errors.append("DUPLICATE_CANDIDATE_SECURITY")
    if sum(r.get("candidate_tier") == "CORE" for r in rows) != int(auth.get("core_candidate_count", -1)):
        errors.append("CANDIDATE_CSV_CORE_COUNT")
    if sum(r.get("candidate_tier") == "WATCH" for r in rows) != int(auth.get("watch_candidate_count", -1)):
        errors.append("CANDIDATE_CSV_WATCH_COUNT")
    for row in rows:
        if row.get("candidate_status") != "ACTIVE":
            errors.append("INACTIVE_ENTRY_CANDIDATE")
        if not as_bool(row.get("formal_candidate_graduation")):
            errors.append("NONFORMAL_ENTRY_CANDIDATE")
        if as_bool(row.get("portfolio_allocation_authorized")):
            errors.append("PREMATURE_PORTFOLIO_ALLOCATION_AUTHORITY")
        if as_bool(row.get("simulation_admission_authorized")):
            errors.append("PREMATURE_SIMULATION_AUTHORITY")
        if as_bool(row.get("real_account_admission_authorized")):
            errors.append("PREMATURE_REAL_ACCOUNT_AUTHORITY")
        if int(row.get("orders_created") or 0) != 0:
            errors.append("UPSTREAM_ORDERS_CREATED")
        if row.get("trade_authority") != TRADE_AUTHORITY:
            errors.append("CANDIDATE_TRADE_AUTHORITY")

    for label, state, required_id in [
        ("REAL", real, context.get("required_real_state_id")),
        ("SIMULATION", sim, context.get("required_simulation_state_id")),
    ]:
        if state.get("state_id") != required_id:
            errors.append(f"{label}_STATE_ID")
        if state.get("status") != context.get("required_position_status"):
            errors.append(f"{label}_POSITION_STATUS")
        if state.get("permissions", {}).get("portfolio_fit") is not True:
            errors.append(f"{label}_PORTFOLIO_FIT_PERMISSION")
        if state.get("trade_authority") != context.get("required_trade_authority"):
            errors.append(f"{label}_TRADE_AUTHORITY")
        if state.get("position_watermark", {}).get("position_state_current") is not True:
            errors.append(f"{label}_POSITION_NOT_CURRENT")
        mark = state.get("mark_watermark", {})
        if mark.get("all_positions_marked") is not True:
            errors.append(f"{label}_UNMARKED_POSITIONS")
        if mark.get("all_marks_fresh_or_acceptable") is not True:
            errors.append(f"{label}_STALE_MARKS")
        latest_mark = str(mark.get("latest_mark_date", ""))
        if latest_mark < str(contract.get("as_of_date", "")):
            errors.append(f"{label}_MARK_BEFORE_CONTRACT_ASOF")
        holdings = state.get("holdings", [])
        if int(state.get("summary", {}).get("holding_count", -1)) != len(holdings):
            errors.append(f"{label}_HOLDING_COUNT_RECONCILIATION")

    if real.get("cash_policy") != context.get("real_cash_semantics"):
        errors.append("REAL_CASH_POLICY")
    if real.get("summary", {}).get("cash_semantics") != context.get("real_cash_semantics"):
        errors.append("REAL_CASH_SUMMARY_SEMANTICS")
    if sim.get("summary", {}).get("cash_semantics") != context.get("simulation_cash_semantics"):
        errors.append("SIMULATION_CASH_SEMANTICS")
    if context.get("real_account_fixed_strategic_cash_target_allowed") is not False:
        errors.append("REAL_STRATEGIC_CASH_TARGET_POLICY")

    boundary = contract.get("phase_boundary", {})
    if boundary.get("contract_definition_authorized") is not True:
        errors.append("CONTRACT_DEFINITION_SCOPE")
    for key in [
        "portfolio_fit_assessment_authorized",
        "candidate_pool_mutation_authorized",
        "simulation_admission_authorized",
        "simulation_mutation_authorized",
        "real_account_admission_authorized",
        "real_account_mutation_authorized",
        "portfolio_sizing_authorized",
        "portfolio_allocation_authorized",
        "order_creation_authorized",
    ]:
        if boundary.get(key) is not False:
            errors.append("BOUNDARY_" + key.upper())
    if boundary.get("trade_authority") != TRADE_AUTHORITY:
        errors.append("BOUNDARY_TRADE_AUTHORITY")

    philosophy = contract.get("portfolio_fit_philosophy", {})
    required_true = [
        "candidate_quality_is_not_portfolio_fit",
        "candidate_core_is_not_automatic_allocation",
        "candidate_watch_is_not_automatic_rejection",
        "portfolio_fit_is_marginal_not_standalone",
        "real_and_simulation_fit_must_be_assessed_separately",
        "existing_exposure_is_not_automatic_rejection",
        "cross_listing_discount_is_not_alpha",
        "diversification_claim_requires_explicit_portfolio_evidence",
        "strong_company_thesis_can_have_no_incremental_portfolio_role",
        "missing_decision_critical_portfolio_context_requires_defer",
        "simulation_cash_is_available_funding_context_not_alpha",
        "fit_assessment_is_not_position_sizing",
        "fit_assessment_is_not_trade_authority",
    ]
    required_false = [
        "weighted_composite_score_allowed",
        "neutral_fill_allowed",
        "automatic_waiver_allowed",
        "arbitrary_fixed_top_n_allowed",
        "real_account_fixed_strategic_cash_target_allowed",
    ]
    for key in required_true:
        if philosophy.get(key) is not True:
            errors.append("PHILOSOPHY_" + key.upper())
    for key in required_false:
        if philosophy.get(key) is not False:
            errors.append("PHILOSOPHY_" + key.upper())

    rules = contract.get("portfolio_fit_rules", [])
    rule_ids = [r.get("rule_id") for r in rules]
    if len(rules) != 15:
        errors.append("RULE_COUNT")
    if set(rule_ids) != EXPECTED_RULE_IDS or len(set(rule_ids)) != len(rule_ids):
        errors.append("RULE_ID_SET")
    hard = [r for r in rules if r.get("type") == "HARD"]
    decision = [r for r in rules if r.get("type") == "DECISION"]
    if len(hard) != 7 or len(decision) != 8:
        errors.append("RULE_TYPE_COUNTS")
    if any(not str(r.get("requirement", "")).strip() for r in rules):
        errors.append("EMPTY_RULE_REQUIREMENT")

    if set(contract.get("account_fit_states", [])) != EXPECTED_ACCOUNT_STATES:
        errors.append("ACCOUNT_FIT_STATE_SET")
    if set(contract.get("combined_routing_states", [])) != EXPECTED_COMBINED_ROUTES:
        errors.append("COMBINED_ROUTE_SET")

    routing = contract.get("routing_contract", {})
    for key in [
        "positive_fit_requires_all_applicable_hard_rules_pass",
        "simulation_and_real_account_states_must_both_be_explicit",
        "fit_with_constraints_requires_named_constraints",
        "no_incremental_role_is_not_bearish_company_rejection",
        "defer_requires_missing_or_stale_decision_critical_context",
        "block_requires_substantive_portfolio_or_investment_blocker",
        "combined_route_must_be_derived_from_account_states",
        "p4_1_is_assessment_only",
        "construction_or_admission_requires_separate_later_gate",
    ]:
        if routing.get(key) is not True:
            errors.append("ROUTING_" + key.upper())
    if routing.get("p4_1_portfolio_mutation_authorized") is not False:
        errors.append("P4_1_MUTATION_BOUNDARY")

    acceptance = contract.get("acceptance", {})
    expected_accept = {
        "portfolio_fit_rule_count": 15,
        "hard_rule_count": 7,
        "decision_rule_count": 8,
        "entry_candidate_count": 70,
        "core_candidate_count": 2,
        "watch_candidate_count": 68,
        "portfolio_fit_assessment_count": 0,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "portfolio_allocations": 0,
        "orders_created": 0,
    }
    for key, expected in expected_accept.items():
        if int(acceptance.get(key, -1)) != expected:
            errors.append("ACCEPT_" + key.upper())
    if acceptance.get("pass_status") != PASS_STATUS:
        errors.append("PASS_STATUS")
    if acceptance.get("next_gate") != NEXT_GATE:
        errors.append("NEXT_GATE")
    if acceptance.get("trade_authority") != TRADE_AUTHORITY:
        errors.append("TRADE_AUTHORITY")

    gate_decision = {
        "program_id": PROGRAM_ID,
        "phase": contract.get("phase"),
        "status": PASS_STATUS if not errors else "BLOCKED_P4_0_PORTFOLIO_FIT_CONTRACT",
        "as_of_date": contract.get("as_of_date"),
        "entry_candidate_count": len(rows),
        "candidate_tier_counts": {
            "CORE": sum(r.get("candidate_tier") == "CORE" for r in rows),
            "WATCH": sum(r.get("candidate_tier") == "WATCH" for r in rows),
        },
        "real_holding_count_at_validation": len(real.get("holdings", [])),
        "simulation_holding_count_at_validation": len(sim.get("holdings", [])),
        "portfolio_fit_rule_count": len(rules),
        "portfolio_fit_assessment_count": 0,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "portfolio_allocations": 0,
        "orders_created": 0,
        "next_gate": NEXT_GATE if not errors else None,
        "trade_authority": TRADE_AUTHORITY,
    }
    quality = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not errors else "FAIL",
        "hard_failures": sorted(set(errors)),
        "p3_2_candidate_lineage_bound": observed_candidate_sha == expected_candidate_sha,
        "real_portfolio_state_current": real.get("position_watermark", {}).get("position_state_current") is True,
        "simulation_portfolio_state_current": sim.get("position_watermark", {}).get("position_state_current") is True,
        "real_cash_is_execution_balance_only": real.get("cash_policy") == context.get("real_cash_semantics"),
        "no_fixed_real_cash_target": context.get("real_account_fixed_strategic_cash_target_allowed") is False,
        "separate_real_and_simulation_fit": philosophy.get("real_and_simulation_fit_must_be_assessed_separately") is True,
        "no_weighted_score": philosophy.get("weighted_composite_score_allowed") is False,
        "no_fixed_top_n": philosophy.get("arbitrary_fixed_top_n_allowed") is False,
        "p4_0_has_zero_state_mutation": all(int(acceptance.get(k, -1)) == 0 for k in ["candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "portfolio_allocations", "orders_created"]),
        "trade_authority": TRADE_AUTHORITY,
    }
    write_json(out / "HKCU_P4_0_CONTRACT_DECISION.json", gate_decision)
    write_json(out / "HKCU_P4_0_CONTRACT_QUALITY_REPORT.json", quality)

    if errors:
        raise SystemExit("P4_0_CONTRACT_VALIDATION_FAILED:" + "|".join(sorted(set(errors))))
    print(PASS_STATUS)


if __name__ == "__main__":
    main()
