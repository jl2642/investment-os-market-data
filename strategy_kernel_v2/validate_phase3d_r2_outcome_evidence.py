from __future__ import annotations

import json
from pathlib import Path

from strategy_kernel_v2.phase3d_r2_outcome_evidence import (
    build_outcome_evidence_ledger,
    load_contract,
    load_frozen_pack,
    validate_contract,
    validate_frozen_pack,
    write_default,
)
from strategy_kernel_v2.program_consistency import validate_program_consistency
from strategy_kernel_v2.validate_phase3d_r2_measurability import validate as validate_round1

ROOT = Path(__file__).resolve().parent


def _validate_zero_authority(errors, controls):
    for key in (
        "return_calculation_count",
        "edge_spread_calculation_count",
        "concordance_calculation_count",
        "performance_metric_count",
        "portfolio_pnl_count",
        "model_mutation_count",
        "dominance_relation_mutation_count",
        "result_based_drop_count",
        "orders",
    ):
        if key in controls and controls.get(key) != 0:
            errors.append("R2_OUTCOME_EVIDENCE_FORBIDDEN_ACTIVITY_NONZERO:" + key)
    if controls.get("trade_authority") != "NONE":
        errors.append("R2_OUTCOME_EVIDENCE_TRADE_AUTHORITY_CHANGED")


def validate():
    errors = list(validate_program_consistency())
    round1_errors, round1 = validate_round1()
    errors.extend(round1_errors)

    contract = load_contract()
    errors.extend(validate_contract(contract))
    state = json.loads((ROOT / "PROGRAM_STATE.json").read_text(encoding="utf-8"))
    current = json.loads((ROOT / "CURRENT_PHASE_STATUS.json").read_text(encoding="utf-8"))
    cv = current.get("validation", {})
    closeout = state.get("phase3d_r2_outcome_evidence_acquisition_complete") is True

    if closeout:
        result = load_frozen_pack()
        errors.extend(validate_frozen_pack(result, round1))
        expected = {
            "phase3d_r2_outcome_evidence_acquisition_started": True,
            "phase3d_r2_outcome_evidence_acquisition_complete": True,
            "phase3d_r2_outcome_evidence_acquisition_status": "PASS_R2_OUTCOME_EVIDENCE_READY_FOR_PERFORMANCE",
            "phase3d_r2_outcome_evidence_ledger_sha256": result["source_ledger_sha256"],
            "phase3d_r2_outcome_evidence_complete_endpoint_count": 55,
            "phase3d_r2_outcome_evidence_complete_edge_count": 54,
            "phase3d_r2_outcome_evidence_corporate_action_no_change_count": 55,
            "phase3d_r2_outcome_evidence_corporate_action_adjustment_count": 0,
            "phase3d_r2_outcome_evidence_corporate_action_unresolved_count": 0,
            "phase3d_r2_outcome_evidence_support_disagreement_count": 0,
            "phase3d_r2_performance_start_allowed": True,
            "phase3d_r2_performance_started": False,
            "phase3d_r2_complete": False,
            "phase3e_r2_started": False,
            "repeat_phase3f_started": False,
            "phase3_historical_validation_complete": False,
            "phase4_entry_allowed": False,
        }
        for key, value in expected.items():
            if state.get(key) != value:
                errors.append("R2_OUTCOME_EVIDENCE_STATE_DRIFT:" + key)
            if cv.get(key) != value:
                errors.append("R2_OUTCOME_EVIDENCE_CURRENT_DRIFT:" + key)
        if current.get("current_phase") != "PHASE_3D_R2_MEASURABILITY_AND_PERFORMANCE_IF_SUPPORTED":
            errors.append("R2_OUTCOME_EVIDENCE_CURRENT_PHASE_DRIFT")
        if current.get("next_phase") != "PHASE_3D_R2_PERFORMANCE_MEASUREMENT":
            errors.append("R2_OUTCOME_EVIDENCE_NEXT_PHASE_DRIFT")
        if state.get("orders") != 0 or current.get("orders") != 0:
            errors.append("R2_OUTCOME_EVIDENCE_ORDER_AUTHORITY_DRIFT")
        if state.get("trade_authority") != "NONE" or current.get("trade_authority") != "NONE":
            errors.append("R2_OUTCOME_EVIDENCE_TRADE_AUTHORITY_DRIFT")
        return errors, result

    result = build_outcome_evidence_ledger()
    if result.get("parent_round1_audit_sha256") != round1.get("audit_sha256"):
        errors.append("R2_OUTCOME_EVIDENCE_PARENT_AUDIT_BINDING_DRIFT")
    if result.get("frozen_dominance_edge_count") != 54:
        errors.append("R2_OUTCOME_EVIDENCE_EDGE_COUNT_DRIFT")
    if result.get("required_edge_endpoint_instances") != 55:
        errors.append("R2_OUTCOME_EVIDENCE_ENDPOINT_COUNT_DRIFT")
    if result.get("required_security_count") != 7:
        errors.append("R2_OUTCOME_EVIDENCE_SECURITY_COUNT_DRIFT")

    _validate_zero_authority(errors, result["controls"])
    expected_pass = result.get("complete_evidence_edge_count") == 54 and not result.get("integrity_errors")
    if result.get("performance_calculation_authorized") is not expected_pass:
        errors.append("R2_OUTCOME_EVIDENCE_PERFORMANCE_GATE_DRIFT")
    if result.get("return_calculation_count") != 0 or result.get("performance_metric_count") != 0:
        errors.append("R2_OUTCOME_EVIDENCE_PREMATURE_CALCULATION")
    if result.get("phase3d_r2_performance_started") is not False:
        errors.append("R2_OUTCOME_EVIDENCE_PREMATURE_PERFORMANCE")
    if result.get("phase3e_r2_started") is not False:
        errors.append("R2_OUTCOME_EVIDENCE_PREMATURE_3E")
    if result.get("repeat_phase3f_started") is not False:
        errors.append("R2_OUTCOME_EVIDENCE_PREMATURE_REPEAT_3F")
    if result.get("phase4_entry_allowed") is not False:
        errors.append("R2_OUTCOME_EVIDENCE_PREMATURE_PHASE4")
    if not errors:
        write_default(result)
    return errors, result


if __name__ == "__main__":
    errors, result = validate()
    if errors:
        raise AssertionError(";".join(errors))
    if result.get("pack_id"):
        print(
            "PHASE3D_R2_OUTCOME_EVIDENCE_ACCEPTANCE "
            "status=PASS_R2_OUTCOME_EVIDENCE_READY_FOR_PERFORMANCE "
            "complete_endpoints=55/55 complete_edges=54/54 "
            "performance_authorized=true returns=0 performance=0 "
            "phase4_entry_allowed=false orders=0 trade_authority=NONE frozen_pack=true"
        )
    else:
        print(
            "PHASE3D_R2_OUTCOME_EVIDENCE_ACCEPTANCE "
            f"status={result['status']} complete_endpoints={result['complete_endpoint_count']}/55 "
            f"complete_edges={result['complete_evidence_edge_count']}/54 "
            f"performance_authorized={str(result['performance_calculation_authorized']).lower()} "
            "returns=0 performance=0 phase4_entry_allowed=false orders=0 trade_authority=NONE"
        )
