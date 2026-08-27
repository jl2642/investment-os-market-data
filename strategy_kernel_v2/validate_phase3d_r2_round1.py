from __future__ import annotations

import json
from pathlib import Path

from strategy_kernel_v2.phase3d_r2_measurability import (
    ROUND1_PASS,
    build_round1_evidence_audit,
    load_contract,
    validate_contract,
    write_default,
)
from strategy_kernel_v2.program_consistency import validate_program_consistency
from strategy_kernel_v2.validate_phase3_r2_independent_holdout_replay import validate as validate_holdout_replay

ROOT = Path(__file__).resolve().parent


def _load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def validate() -> tuple[list[str], dict]:
    errors = list(validate_program_consistency())

    holdout_errors, holdout = validate_holdout_replay()
    errors.extend(holdout_errors)

    contract = load_contract()
    errors.extend(validate_contract(contract))

    state = _load("PROGRAM_STATE.json")
    current = _load("CURRENT_PHASE_STATUS.json")
    result = build_round1_evidence_audit()

    if holdout.get("status") != "PASS_INDEPENDENT_HOLDOUT_REPLAY_OPERATIONAL":
        errors.append("PHASE3D_R2_PARENT_HOLDOUT_NOT_PASS")
    if state.get("independent_holdout_final_acceptance_complete") is not True:
        errors.append("PHASE3D_R2_PARENT_HOLDOUT_NOT_ACCEPTED")
    if state.get("phase3d_r2_start_allowed") is not True:
        errors.append("PHASE3D_R2_START_NOT_AUTHORIZED")

    # Monotonic two-step discipline. Before first remote acceptance, governed
    # state remains at the parent boundary. After acceptance, only descriptive
    # Round-1 state may advance; the frozen contract itself is unchanged.
    cv = current.get("validation", {})
    round1_closed = state.get("phase3d_r2_round1_evidence_audit_complete") is True
    if round1_closed:
        if state.get("phase3d_r2_started") is not True or cv.get("phase3d_r2_started") is not True:
            errors.append("PHASE3D_R2_CLOSEOUT_STARTED_STATE_DRIFT")
        if state.get("phase3d_r2_round1_contract_frozen") is not True:
            errors.append("PHASE3D_R2_CLOSEOUT_CONTRACT_FLAG_FALSE")
        if state.get("phase3d_r2_round1_outcome") != ROUND1_PASS:
            errors.append("PHASE3D_R2_CLOSEOUT_OUTCOME_DRIFT")
        if state.get("phase3d_r2_measurability_status") != "PENDING_OUTCOME_EVIDENCE_ACQUISITION":
            errors.append("PHASE3D_R2_CLOSEOUT_MEASURABILITY_DRIFT")
        if state.get("phase3d_r2_outcome_evidence_acquisition_start_allowed") is not True:
            errors.append("PHASE3D_R2_CLOSEOUT_ACQUISITION_GATE_NOT_OPEN")
        if state.get("phase3d_r2_outcome_evidence_acquisition_started") is not False:
            errors.append("PHASE3D_R2_CLOSEOUT_PREMATURE_ACQUISITION")
        if state.get("phase3d_r2_performance_measurement_start_allowed") is not False:
            errors.append("PHASE3D_R2_CLOSEOUT_PREMATURE_PERFORMANCE_GATE")
        if current.get("current_phase") != "PHASE_3D_R2_MEASURABILITY_AND_PERFORMANCE_IF_SUPPORTED":
            errors.append("PHASE3D_R2_CLOSEOUT_CURRENT_PHASE_DRIFT")
        if current.get("next_phase") != "PHASE_3D_R2_OUTCOME_EVIDENCE_ACQUISITION":
            errors.append("PHASE3D_R2_CLOSEOUT_NEXT_PHASE_DRIFT")
    else:
        if state.get("phase3d_r2_started") is not False:
            errors.append("PHASE3D_R2_PRE_CLOSEOUT_STATE_ALREADY_STARTED")
        if cv.get("phase3d_r2_started") is not False:
            errors.append("PHASE3D_R2_PRE_CLOSEOUT_CURRENT_ALREADY_STARTED")
        if current.get("next_phase") != "PHASE_3D_R2_MEASURABILITY_AND_PERFORMANCE_IF_SUPPORTED":
            errors.append("PHASE3D_R2_PRE_CLOSEOUT_NEXT_PHASE_DRIFT")

    if result.get("status") != ROUND1_PASS:
        errors.append("PHASE3D_R2_ROUND1_RESULT_NOT_PASS")
    if result.get("measurability_status") != "PENDING_OUTCOME_EVIDENCE_ACQUISITION":
        errors.append("PHASE3D_R2_ROUND1_MEASURABILITY_CLASS_DRIFT")

    for key in (
        "outcome_manifest_content_read_count",
        "realized_outcome_value_read_count",
        "future_return_compute_count",
        "performance_metric_compute_count",
        "synthetic_trade_count",
        "portfolio_return_metric_count",
        "winner_selection_count",
    ):
        if result.get(key) != 0:
            errors.append("PHASE3D_R2_ROUND1_FORBIDDEN_ACTIVITY_NONZERO:" + key)

    if result.get("r2_outcome_manifest_present_at_parent_freeze") is not False:
        errors.append("PHASE3D_R2_R2_OUTCOME_MANIFEST_PREEXISTED")
    if result.get("legacy_phase3d_outcome_manifest_authorized_for_r2") is not False:
        errors.append("PHASE3D_R2_LEGACY_MANIFEST_REUSED")
    if result.get("phase3e_r2_start_allowed") is not False:
        errors.append("PHASE3D_R2_PREMATURE_3E_R2")
    if result.get("repeat_phase3f_start_allowed") is not False:
        errors.append("PHASE3D_R2_PREMATURE_REPEAT_3F")
    if result.get("phase4_entry_allowed") is not False:
        errors.append("PHASE3D_R2_PREMATURE_PHASE4")
    if result.get("orders") != 0 or result.get("trade_authority") != "NONE":
        errors.append("PHASE3D_R2_AUTHORITY_CHANGED")

    if not errors:
        write_default(result)
    return errors, result


if __name__ == "__main__":
    errors, result = validate()
    if errors:
        raise AssertionError(";".join(errors))
    print(
        "PHASE3D_R2_ROUND1_ACCEPTANCE_PASS "
        f"status={result['status']} checkpoints={result['checkpoint_count']} "
        f"profiles={result['r2_profile_count']} comparable_groups={result['comparable_group_count']} "
        f"comparable_checkpoints={result['comparable_checkpoint_count']} "
        f"signatures={result['distinct_comparable_signature_count']} "
        f"dominance_edges={result['dominance_edge_count']} "
        f"edge_securities={result['edge_endpoint_security_count']} "
        "outcomes_read=0 performance=0 phase3e_r2_start_allowed=false "
        "repeat_phase3f_start_allowed=false phase4_entry_allowed=false "
        "orders=0 trade_authority=NONE"
    )
