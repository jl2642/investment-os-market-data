from __future__ import annotations

from strategy_kernel_v2.phase3d_r2_outcome_evidence import (
    build_outcome_evidence_ledger,
    load_contract,
    validate_contract,
    write_default,
)
from strategy_kernel_v2.program_consistency import validate_program_consistency
from strategy_kernel_v2.validate_phase3d_r2_measurability import validate as validate_round1


def validate():
    errors = list(validate_program_consistency())
    round1_errors, round1 = validate_round1()
    errors.extend(round1_errors)

    contract = load_contract()
    errors.extend(validate_contract(contract))
    result = build_outcome_evidence_ledger()

    if result.get("parent_round1_audit_sha256") != round1.get("audit_sha256"):
        errors.append("R2_OUTCOME_EVIDENCE_PARENT_AUDIT_BINDING_DRIFT")
    if result.get("frozen_dominance_edge_count") != 54:
        errors.append("R2_OUTCOME_EVIDENCE_EDGE_COUNT_DRIFT")
    if result.get("required_edge_endpoint_instances") != 55:
        errors.append("R2_OUTCOME_EVIDENCE_ENDPOINT_COUNT_DRIFT")
    if result.get("required_security_count") != 7:
        errors.append("R2_OUTCOME_EVIDENCE_SECURITY_COUNT_DRIFT")

    controls = result["controls"]
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
        if controls.get(key) != 0:
            errors.append("R2_OUTCOME_EVIDENCE_FORBIDDEN_ACTIVITY_NONZERO:" + key)
    if controls.get("trade_authority") != "NONE":
        errors.append("R2_OUTCOME_EVIDENCE_TRADE_AUTHORITY_CHANGED")

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
    print(
        "PHASE3D_R2_OUTCOME_EVIDENCE_ACCEPTANCE "
        f"status={result['status']} complete_endpoints={result['complete_endpoint_count']}/55 "
        f"complete_edges={result['complete_evidence_edge_count']}/54 "
        f"performance_authorized={str(result['performance_calculation_authorized']).lower()} "
        "returns=0 performance=0 phase4_entry_allowed=false orders=0 trade_authority=NONE"
    )
