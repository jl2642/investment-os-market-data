from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent
ADAPTER_FILE = ROOT / "REPEAT_PHASE3F_R2_EVIDENCE_ADAPTER.json"
ORIGINAL_CONTRACT_FILE = ROOT / "PHASE3F_PROMOTION_GATE_CONTRACT.json"
OUTPUT_FILE = ROOT / "generated/REPEAT_PHASE3F_R2_GATE_RESULT.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _git_blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("utf-8")
    return hashlib.sha1(header + content).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def validate_adapter(adapter: Mapping[str, Any], original_contract: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if adapter.get("status") != "FROZEN_R2_EVIDENCE_ADAPTER_TO_EXISTING_PHASE3F_CONTRACT":
        errors.append("REPEAT3F_ADAPTER_NOT_FROZEN")
    inherited = adapter.get("inherited_gate_contract", {})
    if original_contract.get("status") != "FROZEN_HISTORICAL_PROMOTION_GATE":
        errors.append("REPEAT3F_ORIGINAL_CONTRACT_NOT_FROZEN")
    original_blob = _git_blob_sha(ORIGINAL_CONTRACT_FILE.read_bytes())
    if inherited.get("git_blob_sha") != original_blob:
        errors.append("REPEAT3F_ORIGINAL_CONTRACT_BLOB_DRIFT")
    expected_requirements = {
        "candidate_point_in_time_historical_replay",
        "candidate_phase3d_evidence_measurable",
        "phase3e_robustness_accepted",
        "broader_historical_coverage",
    }
    if set(original_contract.get("mandatory_promotion_requirements", {})) != expected_requirements:
        errors.append("REPEAT3F_ORIGINAL_REQUIREMENT_SET_DRIFT")
    if set(adapter.get("r2_evidence_bindings", {})) != expected_requirements:
        errors.append("REPEAT3F_ADAPTER_REQUIREMENT_SET_DRIFT")
    for key in ("requirements_unchanged", "decision_logic_unchanged", "terminal_rejection_logic_unchanged", "allowed_outcomes_unchanged"):
        if inherited.get(key) is not True:
            errors.append("REPEAT3F_INHERITANCE_NOT_EXACT:" + key)
    discipline = adapter.get("interpretation_discipline", {})
    for key in ("no_new_promotion_requirement", "no_post_result_numeric_threshold", "descriptive_performance_direction_is_not_a_new_gate", "robustness_axis_sensitivity_is_not_a_new_gate", "robustness_axis_sensitivity_must_inform_phase4_design_if_promoted", "phase4_cannot_start_until_repeat_gate_is_accepted"):
        if discipline.get(key) is not True:
            errors.append("REPEAT3F_INTERPRETATION_DISCIPLINE_DRIFT:" + key)
    authority = adapter.get("authority_boundaries", {})
    for key, value in authority.items():
        if key == "trade_authority":
            if value != "NONE":
                errors.append("REPEAT3F_TRADE_AUTHORITY_DRIFT")
        elif value != 0:
            errors.append("REPEAT3F_AUTHORITY_NONZERO:" + key)
    return errors


def evaluate_repeat_phase3f() -> dict[str, Any]:
    adapter = _load(ADAPTER_FILE)
    original = _load(ORIGINAL_CONTRACT_FILE)
    state = _load(ROOT / "PROGRAM_STATE.json")
    current = _load(ROOT / "CURRENT_PHASE_STATUS.json")
    errors = validate_adapter(adapter, original)

    if state.get("repeat_phase3f_start_allowed") is not True:
        errors.append("REPEAT3F_START_NOT_ALLOWED")
    if state.get("repeat_phase3f_started") is not False:
        errors.append("REPEAT3F_PREMATURE_STATE_START")
    if state.get("phase3_historical_validation_complete") is not False:
        errors.append("REPEAT3F_PREMATURE_PHASE3_COMPLETE")
    if state.get("phase4_entry_allowed") is not False:
        errors.append("REPEAT3F_PREMATURE_PHASE4")
    if current.get("next_phase") != "REPEAT_PHASE_3F_HISTORICAL_PROMOTION_GATE":
        errors.append("REPEAT3F_CURRENT_NEXT_DRIFT")

    bindings = adapter["r2_evidence_bindings"]

    replay_binding = bindings["candidate_point_in_time_historical_replay"]
    replay_checks = [
        state.get(k) == v for k, v in replay_binding["required_state"].items()
    ]
    replay_checks.append(state.get("independent_holdout_replay_sha256") == replay_binding["bound_replay_sha256"])
    req_replay = all(replay_checks)

    measurable_binding = bindings["candidate_phase3d_evidence_measurable"]
    measurable_checks = [
        state.get(k) == v for k, v in measurable_binding["required_state"].items()
    ]
    measurable_checks.append(state.get("phase3d_r2_performance_measurement_sha256") == measurable_binding["bound_measurement_sha256"])
    measurable_checks.append(int(state.get("phase3d_r2_edge_horizon_record_count", 0)) >= int(measurable_binding["minimum_measurable_metric_records"]))
    measurable_checks.append(int(state.get("phase3d_r2_edge_horizon_record_count", 0)) == int(measurable_binding["expected_edge_horizon_record_count"]))
    req_measurable = all(measurable_checks)

    robustness_binding = bindings["phase3e_robustness_accepted"]
    robustness_checks = [
        state.get(k) == v for k, v in robustness_binding["required_state"].items()
    ]
    robustness_checks.append(state.get("phase3e_r2_robustness_sha256") == robustness_binding["bound_robustness_sha256"])
    robustness_checks.append(state.get("phase3e_r2_robustness_pass_fail_threshold_defined") is False)
    robustness_checks.append(state.get("phase3e_r2_observed_predeclared_axis_sensitivity") is True)
    req_robustness = all(robustness_checks)

    coverage_binding = bindings["broader_historical_coverage"]
    coverage_checks = [
        state.get(k) == v for k, v in coverage_binding["required_state"].items()
    ]
    mins = coverage_binding["inherited_frozen_minimums"]
    coverage_checks.extend([
        int(state.get("holdout_v2_selected_checkpoint_count", 0)) >= mins["checkpoints"],
        int(state.get("holdout_v2_distinct_utc_dates", 0)) >= mins["distinct_utc_dates"],
        int(state.get("holdout_v2_distinct_iso_weeks", 0)) >= mins["distinct_iso_weeks"],
        int(state.get("holdout_v2_distinct_evidence_regimes", 0)) >= mins["distinct_evidence_regimes"],
        int(state.get("holdout_v2_unique_securities", 0)) >= mins["unique_securities"],
        int(state.get("holdout_v2_opportunity_profile_instances", 0)) >= mins["opportunity_profile_instances"],
        int(state.get("holdout_v2_checkpoints_outside_seed_span", 0)) >= mins["checkpoints_strictly_outside_seed_time_span"],
        float(state.get("holdout_v2_max_single_utc_date_fraction", 1.0)) <= mins["max_single_utc_date_fraction"],
        float(state.get("holdout_v2_max_single_evidence_regime_fraction", 1.0)) <= mins["max_single_evidence_regime_fraction"],
        state.get("holdout_v2_failed_thresholds") == [],
    ])
    req_broader = all(coverage_checks)

    requirements = {
        "candidate_point_in_time_historical_replay": {
            "passed": req_replay,
            "accepted_holdout_checkpoints": state.get("independent_holdout_replay_checkpoint_count"),
            "replay_status": state.get("independent_holdout_replay_outcome"),
            "replay_sha256": state.get("independent_holdout_replay_sha256"),
        },
        "candidate_phase3d_evidence_measurable": {
            "passed": req_measurable,
            "structurally_measurable": state.get("phase3d_r2_structurally_measurable"),
            "edge_horizon_record_count": state.get("phase3d_r2_edge_horizon_record_count"),
            "measurement_status": state.get("phase3d_r2_performance_measurement_status"),
            "measurement_sha256": state.get("phase3d_r2_performance_measurement_sha256"),
        },
        "phase3e_robustness_accepted": {
            "passed": req_robustness,
            "evaluation_accepted": state.get("phase3e_r2_robustness_evaluation_accepted"),
            "positive_robustness_claimed": state.get("phase3e_r2_positive_robustness_claimed"),
            "observed_predeclared_axis_sensitivity": state.get("phase3e_r2_observed_predeclared_axis_sensitivity"),
            "robustness_sha256": state.get("phase3e_r2_robustness_sha256"),
            "interpretation": "ACCEPTED_EVIDENCE_COMPLETION_WITH_MATERIAL_PREDECLARED_AXIS_SENSITIVITY_NO_POST_RESULT_THRESHOLD",
        },
        "broader_historical_coverage": {
            "passed": req_broader,
            "selected_checkpoints": state.get("holdout_v2_selected_checkpoint_count"),
            "distinct_utc_dates": state.get("holdout_v2_distinct_utc_dates"),
            "distinct_iso_weeks": state.get("holdout_v2_distinct_iso_weeks"),
            "distinct_evidence_regimes": state.get("holdout_v2_distinct_evidence_regimes"),
            "unique_securities": state.get("holdout_v2_unique_securities"),
            "opportunity_profile_instances": state.get("holdout_v2_opportunity_profile_instances"),
            "failed_thresholds": state.get("holdout_v2_failed_thresholds"),
        },
    }

    pass_count = sum(1 for value in requirements.values() if value["passed"])
    all_pass = pass_count == 4

    rejection_components = {
        "measurable_candidate_economic_failure": False,
        "validated_structural_incoherence_without_governed_redesign_path": False,
        "governed_program_decision_to_abandon_candidate_family": False,
    }
    terminal_rejection = any(rejection_components.values())

    if all_pass:
        outcome = "PROMOTE_TO_PHASE_4_FORWARD_VALIDATION"
    elif terminal_rejection:
        outcome = "REJECT_V2_FORM"
    else:
        outcome = "CONTINUE_SHADOW_RESEARCH"

    result = {
        "schema_version": "1.0.0",
        "phase": "REPEAT_PHASE_3F",
        "status": "COMPLETE_REPEAT_PHASE3F_R2_HISTORICAL_PROMOTION_GATE" if not errors else "FAIL_REPEAT_PHASE3F_R2_GATE_INTEGRITY",
        "inherited_contract_status": original["status"],
        "requirements": requirements,
        "promotion_requirement_pass_count": pass_count,
        "promotion_requirement_total_count": 4,
        "all_promotion_requirements_pass": all_pass,
        "terminal_rejection_evidence": terminal_rejection,
        "terminal_rejection_components": rejection_components,
        "gate_outcome": outcome,
        "phase4_entry_authorized_by_gate_result": outcome == "PROMOTE_TO_PHASE_4_FORWARD_VALIDATION",
        "robustness_sensitivity_carry_forward_required": bool(state.get("phase3e_r2_observed_predeclared_axis_sensitivity")),
        "robustness_sensitivity_note": "52-vs-2 exact-signature imbalance and security/signature/weighting sensitivity remain mandatory Phase 4 design and monitoring constraints; they are not retroactively added as a fifth Phase 3F gate.",
        "economic_winner_selected": False,
        "statistical_significance_claimed": False,
        "post_result_promotion_threshold_created": False,
        "state_closeout_applied": False,
        "repeat_phase3f_started": False,
        "repeat_phase3f_complete": False,
        "phase3_historical_validation_complete": False,
        "phase4_started": False,
        "orders": 0,
        "trade_authority": "NONE",
        "integrity_errors": sorted(set(errors)),
        "controls": dict(adapter["authority_boundaries"]),
    }
    result["repeat_phase3f_gate_sha256"] = _sha256({k: v for k, v in result.items() if k != "repeat_phase3f_gate_sha256"})
    return result


def write_default(result: Mapping[str, Any]) -> Path:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return OUTPUT_FILE


if __name__ == "__main__":
    result = evaluate_repeat_phase3f()
    path = write_default(result)
    print(
        "REPEAT_PHASE3F_R2_RESULT "
        f"status={result['status']} pass={result['promotion_requirement_pass_count']}/4 "
        f"outcome={result['gate_outcome']} phase4_gate={str(result['phase4_entry_authorized_by_gate_result']).lower()} "
        "state_closeout=false phase4_started=false orders=0 trade_authority=NONE "
        f"sha256={result['repeat_phase3f_gate_sha256']} path={path}"
    )
