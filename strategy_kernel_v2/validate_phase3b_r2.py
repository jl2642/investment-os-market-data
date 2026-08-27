from __future__ import annotations

import json
from pathlib import Path

from strategy_kernel_v2.phase3b_r2_contract import (
    compare_r2_profiles,
    load_contract,
    transform_model_neutral_row,
    validate_contract,
)
from strategy_kernel_v2.program_consistency import validate_program_consistency

ROOT = Path(__file__).resolve().parent


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def synthetic_row(security_id: str, evidence_id: str, **features):
    return {
        "security_id": security_id,
        "security_name": security_id,
        "features": features,
        "feature_provenance": {key: [evidence_id] for key in features},
        "provenance_evidence_ids": [evidence_id],
    }


def validate() -> list[str]:
    errors = list(validate_program_consistency())
    contract = load_contract()
    errors.extend(validate_contract(contract))
    old = load("PHASE3B_MODEL_FORMS.json")
    post3f = load("PHASE3_POST3F_RESEARCH_PATH_DECISION.json")
    state = load("PROGRAM_STATE.json")
    current = load("CURRENT_PHASE_STATUS.json")

    old_ids = [row["model_form"] for row in old.get("model_forms", [])]
    if old_ids != [
        "LEGACY_POLICY_BASELINE",
        "PHASE2_PROBABILISTIC_VECTOR",
        "SIMPLE_NON_PROBABILISTIC_PARETO",
    ]:
        errors.append("R2_PRIOR_MODEL_FORMS_MUTATED")
    if contract["model"]["model_form"] in old_ids:
        errors.append("R2_MODEL_IDENTITY_NOT_NEW")

    if post3f.get("status") != "APPROVED_GOVERNED_DUAL_TRACK_RESEARCH_LOOPBACK":
        errors.append("R2_WITHOUT_POST3F_APPROVAL")
    approved = post3f.get("approved_path", {})
    if "R2_PHASE3B_CONTRACT_DEFINITION" not in approved.get("priority_order", []):
        errors.append("R2_NOT_IN_APPROVED_PRIORITY_ORDER")
    direction = post3f.get("r2_architecture_direction", {})
    if direction.get("new_model_identity_required_before_execution") is not True:
        errors.append("R2_POST3F_NEW_IDENTITY_GUARD_MISSING")
    if direction.get("probability_required_as_universal_input") is not False:
        errors.append("R2_POST3F_PROBABILITY_DRIFT")
    if direction.get("realized_outcome_tuning_allowed") is not False:
        errors.append("R2_POST3F_OUTCOME_TUNING_DRIFT")

    # Synthetic mechanics prove only the frozen contract behavior; they are not replay evidence.
    a = transform_model_neutral_row(
        synthetic_row(
            "A", "EA",
            candidate_archive_evidence_score=95,
            candidate_archive_quality_score=92,
            candidate_archive_risk_penalty=3,
            candidate_archive_valuation_score_coarse=88,
            candidate_archive_portfolio_fit_score=90,
        ),
        contract,
    )
    b = transform_model_neutral_row(
        synthetic_row(
            "B", "EB",
            candidate_archive_evidence_score=90,
            candidate_archive_quality_score=88,
            candidate_archive_risk_penalty=6,
            candidate_archive_valuation_score_coarse=80,
            candidate_archive_portfolio_fit_score=82,
        ),
        contract,
    )
    mechanics = compare_r2_profiles([a, b], contract)
    if mechanics.get("mode") != "SYNTHETIC_CONTRACT_MECHANICS_ONLY":
        errors.append("R2_SYNTHETIC_MODE_DRIFT")
    if mechanics.get("comparable_profile_count") != 2:
        errors.append("R2_SYNTHETIC_PARETO_NOT_OPERATIONAL")
    if mechanics.get("cross_signature_comparison_count") != 0:
        errors.append("R2_CROSS_SIGNATURE_COMPARISON_NONZERO")
    if mechanics.get("ranking_generated") is not False or mechanics.get("winner_selected") is not False:
        errors.append("R2_SYNTHETIC_RANKING_OR_WINNER_GENERATED")
    if mechanics.get("historical_replay_generated") is not False or mechanics.get("historical_performance_claimed") is not False:
        errors.append("R2_SYNTHETIC_MISREPRESENTED_AS_HISTORY")

    # Explicit firewall against converting adjacent context into unlabeled objectives.
    mapped_sources = {row["source_feature_key"] for row in contract["transform_catalog"]}
    for key in contract.get("preserved_unmapped_context", []):
        if key in mapped_sources:
            errors.append("R2_UNMAPPED_CONTEXT_SILENTLY_MAPPED:" + key)
    for forbidden in (
        "candidate_archive_proxy_return_20260624_to_20260710_pct",
        "candidate_archive_legacy_60d_return_pct_20260624",
        "candidate_archive_race_confidence",
        "00669_valuation_interpretation",
    ):
        if forbidden in mapped_sources:
            errors.append("R2_FORBIDDEN_CONTEXT_MAPPED:" + forbidden)

    if state.get("r2_phase3b_contract_definition_started") is not True:
        errors.append("R2_STATE_NOT_STARTED")
    if state.get("r2_phase3b_contract_definition_complete") is not True:
        errors.append("R2_STATE_NOT_COMPLETE")
    if state.get("r2_model_identity") != contract["model"]["model_form"]:
        errors.append("R2_STATE_MODEL_IDENTITY_MISMATCH")
    if state.get("r2_phase3c_replay_start_allowed") is not True:
        errors.append("R2_PHASE3C_NOT_ALLOWED_AFTER_CONTRACT")
    r2b_downstream = state.get("r2_phase3c_r2b_complete") is True
    holdout_h1_downstream = state.get("holdout_h1_started") is True
    holdout_v2_downstream = state.get("holdout_v2_selection_complete") is True
    if r2b_downstream:
        if state.get("r2_phase3c_replay_started") is not True or state.get("r2_real_historical_replay_executed") is not True:
            errors.append("R2_LEGAL_R2B_DOWNSTREAM_REPLAY_STATE_INVALID")
        if state.get("r2_historical_performance_claimed") is not False:
            errors.append("R2_LEGAL_R2B_DOWNSTREAM_PERFORMANCE_DRIFT")
        if holdout_h1_downstream:
            if state.get("holdout_h1_complete") is not True or state.get("holdout_build_started") is not True:
                errors.append("R2_LEGAL_HOLDOUT_H1_DOWNSTREAM_STATE_INVALID")
            if state.get("holdout_h2_started") is not False:
                errors.append("R2_LEGAL_HOLDOUT_H1_PREMATURE_H2")
        elif state.get("holdout_build_started") is not False:
            errors.append("R2_LEGAL_R2B_DOWNSTREAM_PREMATURE_HOLDOUT")
    elif state.get("r2_phase3c_replay_started") is not False:
        errors.append("R2_PHASE3C_PREMATURELY_STARTED")
    if state.get("phase4_entry_allowed") is not False:
        errors.append("R2_STATE_PREMATURE_PHASE4")

    cv = current.get("validation", {})
    if r2b_downstream:
        if holdout_h1_downstream:
            if current.get("current_phase") != "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE":
                errors.append("R2_CURRENT_HOLDOUT_H1_PHASE_MISMATCH")
            expected_next = (
                "INDEPENDENT_POINT_IN_TIME_HOLDOUT_R2_REPLAY"
                if holdout_v2_downstream and state.get("holdout_v2_selection_outcome") == "PASS_SELECTION_SUFFICIENCY"
                else "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE_EXPANSION"
            )
            if current.get("next_phase") != expected_next:
                errors.append("R2_CURRENT_HOLDOUT_NEXT_PHASE_MISMATCH")
        else:
            if current.get("current_phase") != "PHASE_3C_R2_POINT_IN_TIME_REPLAY":
                errors.append("R2_CURRENT_R2B_PHASE_MISMATCH")
            if current.get("next_phase") != "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE":
                errors.append("R2_CURRENT_R2B_NEXT_PHASE_MISMATCH")
    else:
        if current.get("current_phase") != "PHASE_3B_R2_REVISED_MODEL_CONTRACT":
            errors.append("R2_CURRENT_PHASE_MISMATCH")
        if current.get("next_phase") != "PHASE_3C_R2_POINT_IN_TIME_REPLAY":
            errors.append("R2_NEXT_PHASE_MISMATCH")
    if cv.get("r2_phase3b_contract_definition_complete") is not True:
        errors.append("R2_CURRENT_NOT_COMPLETE")
    if cv.get("r2_model_identity") != contract["model"]["model_form"]:
        errors.append("R2_CURRENT_MODEL_IDENTITY_MISMATCH")
    if r2b_downstream:
        if cv.get("r2_real_historical_replay_executed") is not True:
            errors.append("R2_CURRENT_R2B_REPLAY_NOT_EXECUTED")
    elif cv.get("r2_real_historical_replay_executed") is not False:
        errors.append("R2_CURRENT_PREMATURE_REPLAY")
    if cv.get("r2_historical_performance_claimed") is not False:
        errors.append("R2_CURRENT_PREMATURE_PERFORMANCE")
    if cv.get("phase4_entry_allowed") is not False:
        errors.append("R2_CURRENT_PREMATURE_PHASE4")

    for surface_name, surface in [
        ("CONTRACT", contract["authority_boundaries"]),
        ("STATE", state),
        ("CURRENT", current),
        ("MECHANICS", mechanics["controls"]),
    ]:
        for key in [
            "effective_core_static_changes",
            "candidate_membership_mutations",
            "real_account_mutations",
            "simulation_mutations",
            "target_portfolio_writebacks",
            "user_decisions_generated",
            "orders",
        ]:
            if key in surface and surface[key] != 0:
                errors.append(f"{surface_name}_AUTHORITY_NONZERO_{key}")
        if surface.get("trade_authority") != "NONE":
            errors.append(f"{surface_name}_TRADE_AUTHORITY_CHANGED")
    return errors


if __name__ == "__main__":
    errors = validate()
    if errors:
        raise AssertionError(";".join(errors))
    contract = load_contract()
    print(
        "PHASE3B_R2_ACCEPTANCE_PASS model=EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2 "
        f"model_version={contract['model']['model_version']} "
        f"transform_rules={len(contract['transform_catalog'])} exact_signature_pareto=true "
        "real_historical_replay=false phase3c_r2_start_allowed=true phase4_entry_allowed=false "
        "orders=0 trade_authority=NONE"
    )
