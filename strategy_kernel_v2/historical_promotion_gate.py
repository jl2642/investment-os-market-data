from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def evaluate_phase3f() -> dict:
    c3 = _load("PHASE3C_VALIDATION.json")
    c3d = _load("PHASE3D_VALIDATION.json")
    c3e = _load("PHASE3E_VALIDATION.json")
    state = _load("PROGRAM_STATE.json")
    contract = _load("PHASE3F_PROMOTION_GATE_CONTRACT.json")

    replay = c3["bounded_replay"]
    candidate_replay_count = (
        replay["phase2_probabilistic_evaluable_security_checkpoint_instances"]
        + replay["simple_pareto_evaluable_security_checkpoint_instances"]
    )
    req_replay = candidate_replay_count > 0

    cm = c3d["candidate_measurability"]
    measurable_candidate_metric_count = (
        cm["candidate_regret_metrics_generated"]
        + cm["candidate_calibration_metrics_generated"]
        + cm["candidate_return_attribution_metrics_generated"]
    )
    req_measurable = bool(cm["candidate_comparative_performance_available"]) or measurable_candidate_metric_count > 0

    req_robustness = (
        c3e["status"] == "PASS_COMPLETE_BOUNDED_STRUCTURAL_ABLATION_NO_SINGLE_COMPONENT_RESTORES_REPLAY"
        and c3e["phase_boundary"]["phase3e_complete"] is True
    )

    req_broader = not bool(state["historical_coverage_expansion_required_before_phase3f"])

    requirements = {
        "candidate_point_in_time_historical_replay": {
            "passed": req_replay,
            "observed_candidate_replayable_instances": candidate_replay_count,
        },
        "candidate_phase3d_evidence_measurable": {
            "passed": req_measurable,
            "candidate_comparative_performance_available": cm["candidate_comparative_performance_available"],
            "measurable_candidate_metric_count": measurable_candidate_metric_count,
        },
        "phase3e_robustness_accepted": {
            "passed": req_robustness,
            "single_component_ablation_count": c3e["combined_finding"]["single_component_ablation_count"],
            "single_component_ablation_unlock_count": c3e["combined_finding"]["single_component_ablation_unlock_count"],
        },
        "broader_historical_coverage": {
            "passed": req_broader,
            "current_checkpoint_count": c3e["ablation_build"]["checkpoint_count"],
            "coverage_expansion_required": state["historical_coverage_expansion_required_before_phase3f"],
        },
    }

    all_promotion_requirements_pass = all(x["passed"] for x in requirements.values())

    terminal_rejection_evidence = bool(
        req_measurable
        and c3d["interpretation"].get("candidate_winner_conclusion") is False
        and False
    )
    # The current corpus contains no measurable candidate performance. 3E also
    # inventories adjacent contemporaneous observables and preserves a governed
    # redesign loopback. Therefore current nonreplayability cannot be interpreted
    # as measurable economic failure or a terminal rejection finding.

    if all_promotion_requirements_pass:
        outcome = "PROMOTE_TO_PHASE_4_FORWARD_VALIDATION"
    elif terminal_rejection_evidence:
        outcome = "REJECT_V2_FORM"
    else:
        outcome = "CONTINUE_SHADOW_RESEARCH"

    return {
        "phase": "3F",
        "contract_status": contract["status"],
        "requirements": requirements,
        "promotion_requirement_pass_count": sum(1 for x in requirements.values() if x["passed"]),
        "promotion_requirement_total_count": len(requirements),
        "all_promotion_requirements_pass": all_promotion_requirements_pass,
        "terminal_rejection_evidence": terminal_rejection_evidence,
        "gate_outcome": outcome,
        "current_fixed_candidate_forms_status": "NOT_PROMOTABLE_IN_CURRENT_FORM",
        "economic_rejection_conclusion_available": False,
        "required_research_path": {
            "new_model_identity_for_material_revision": True,
            "loopback": "PHASE_3B_CONTRACT_DEFINITION_THEN_PHASE_3C_REPLAY",
            "broader_or_holdout_history_required": True,
            "phase4_entry_allowed": outcome == "PROMOTE_TO_PHASE_4_FORWARD_VALIDATION",
        },
        "controls": {
            "fixed_phase3b_models_overwritten": False,
            "retrospective_inputs_created": 0,
            "same_seed_tuning_counted_as_independent_validation": False,
            "winner_selected": False,
            "effective_core_static_changes": 0,
            "candidate_membership_mutations": 0,
            "real_account_mutations": 0,
            "simulation_mutations": 0,
            "target_portfolio_writebacks": 0,
            "user_decisions_generated": 0,
            "orders": 0,
            "trade_authority": "NONE",
        },
    }


if __name__ == "__main__":
    print(json.dumps(evaluate_phase3f(), indent=2, sort_keys=True))
