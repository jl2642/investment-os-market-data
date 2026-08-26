import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED = [
    (0, "SYSTEM_AUDIT"),
    (1, "DECISION_AND_UNDERWRITING"),
    (2, "CAPITAL_COMPARISON_INFRASTRUCTURE"),
    (3, "HISTORICAL_REPLAY_AND_CALIBRATION"),
    (4, "FORWARD_PARALLEL_SHADOW_VALIDATION"),
    (5, "GOVERNED_MIGRATION"),
]

CONTROLLED_TEXT_ARTIFACTS = {
    "CHARTER": "MASTER_PROGRAM_CHARTER.md",
    "ROADMAP": "DEVELOPMENT_ROADMAP.md",
    "EXECUTION": "PHASE_EXECUTION_PLAN.md",
    "CHANGELOG": "PLAN_CHANGELOG.md",
}

ZERO_MUTATION_FIELDS = [
    "effective_core_static_changes",
    "candidate_membership_mutations",
    "real_account_mutations",
    "simulation_mutations",
    "target_portfolio_writebacks",
    "user_decisions_generated",
]


def j(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def validate_program_consistency():
    errors = []
    contract = j("PROGRAM_CONTRACT.json")
    state = j("PROGRAM_STATE.json")
    current = j("CURRENT_PHASE_STATUS.json")
    texts = {
        name: (ROOT / filename).read_text(encoding="utf-8")
        for name, filename in CONTROLLED_TEXT_ARTIFACTS.items()
    }

    lifecycle = [(x["phase"], x["name"]) for x in contract["macro_lifecycle"]]
    if lifecycle != EXPECTED:
        errors.append("MACRO_LIFECYCLE_MISMATCH")

    for phase, _ in EXPECTED:
        for name in ("CHARTER", "ROADMAP", "EXECUTION"):
            if f"Phase {phase}" not in texts[name]:
                errors.append(f"{name}_MISSING_PHASE_{phase}")

    gates = contract["mandatory_gates"]
    required_true_gates = [
        "phase3_historical_validation_required_for_phase4",
        "phase4_forward_validation_required_for_phase5",
        "direct_phase3_to_phase5_forbidden",
        "macro_phase_omission_forbidden",
        "program_amendment_required_for_macro_change",
    ]
    for key in required_true_gates:
        if gates.get(key) is not True:
            errors.append("MANDATORY_GATE_FALSE_" + key)

    lifecycle_map = {item["phase"]: item for item in contract["macro_lifecycle"]}
    macro_phase = state["macro_phase"]
    if macro_phase not in lifecycle_map:
        errors.append("PROGRAM_STATE_UNKNOWN_MACRO_PHASE")
    else:
        expected_next = lifecycle_map[macro_phase]["promotion_target"]
        if state["next_macro_phase"] != expected_next:
            errors.append("PROGRAM_STATE_ILLEGAL_NEXT_PHASE")

    if not state["phase4_required"]:
        errors.append("PROGRAM_STATE_PHASE4_NOT_REQUIRED")
    if state["direct_phase3_to_phase5_allowed"]:
        errors.append("PROGRAM_STATE_DIRECT_3_TO_5")
    if state["phase5_migration_allowed"] and not state["phase4_forward_validation_complete"]:
        errors.append("PROGRAM_STATE_PHASE5_BEFORE_PHASE4")
    if state["phase4_forward_validation_complete"] and not state["phase3_historical_validation_complete"]:
        errors.append("PROGRAM_STATE_PHASE4_COMPLETE_BEFORE_PHASE3")
    if macro_phase >= 4 and not state["phase3_historical_validation_complete"]:
        errors.append("PROGRAM_STATE_PHASE4_ENTRY_WITHOUT_PHASE3")
    if macro_phase >= 5 and not state["phase4_forward_validation_complete"]:
        errors.append("PROGRAM_STATE_PHASE5_ENTRY_WITHOUT_PHASE4")
    if (macro_phase >= 3) != bool(state["phase3_implementation_started"]):
        errors.append("PROGRAM_STATE_PHASE3_STARTED_MISMATCH")

    state_current_pairs = [
        ("current_macro_phase", "macro_phase"),
        ("next_macro_phase", "next_macro_phase"),
        ("phase4_required", "phase4_required"),
        ("phase5_migration_allowed", "phase5_migration_allowed"),
        ("direct_phase3_to_phase5_allowed", "direct_phase3_to_phase5_allowed"),
        ("phase3_implementation_started", "phase3_implementation_started"),
        ("orders", "orders"),
        ("trade_authority", "trade_authority"),
    ]
    for current_key, state_key in state_current_pairs:
        if current[current_key] != state[state_key]:
            errors.append(f"CURRENT_STATUS_MISMATCH_{current_key}")

    for key in ZERO_MUTATION_FIELDS:
        if state[key] != 0 or current[key] != 0:
            errors.append("ECONOMIC_MUTATION_NONZERO_" + key)

    controls = contract["authority_boundaries_through_phase4"]
    if controls["orders"] != 0 or controls["trade_authority"] != "NONE":
        errors.append("AUTHORITY_BOUNDARY_BROKEN")
    for key in [
        "effective_core_static_change_authorized",
        "candidate_membership_change_authorized",
        "real_position_change_authorized",
        "simulation_position_change_authorized",
        "target_portfolio_writeback_authorized",
        "order_authorized",
        "implementation_ready",
    ]:
        if controls[key] is not False:
            errors.append("AUTHORITY_TRUE_" + key)

    execution = texts["EXECUTION"]
    if "PROMOTE_TO_PHASE_4_FORWARD_VALIDATION" not in execution:
        errors.append("PHASE3_TO_PHASE4_EXIT_GUARD_MISSING")
    if "`PROMOTE_TO_PHASE_5` is forbidden" not in execution:
        errors.append("DIRECT_PHASE3_TO_PHASE5_TEXT_GUARD_MISSING")

    changelog = texts["CHANGELOG"]
    if state.get("roadmap_drift_detected_and_corrected"):
        if "ROADMAP_DRIFT_CORRECTION" not in changelog:
            errors.append("CHANGELOG_MISSING_ROADMAP_DRIFT_CORRECTION")
        if "Phase 4" not in changelog or "Phase 3" not in changelog:
            errors.append("CHANGELOG_MISSING_PHASE_RESTORATION_RECORD")

    # Governed post-3C negative-result path.
    policy = contract.get("phase3_internal_evaluation_policy")
    if not policy:
        errors.append("PHASE3_INTERNAL_EVALUATION_POLICY_MISSING")
    else:
        if policy.get("phase3_subphase_sequence") != ["3A", "3B", "3C", "3D", "3E", "3F"]:
            errors.append("PHASE3_SUBPHASE_SEQUENCE_MISMATCH")
        for key in [
            "post3c_negative_replayability_may_complete_phase3c",
            "phase3d_missing_candidate_outputs_must_be_nonmeasurable",
            "phase3d_hypothetical_candidate_outputs_forbidden",
            "phase3d_outcome_definitions_must_be_preregistered_before_loading_realized_outcomes",
            "phase3e_revised_model_forms_must_be_versioned",
            "phase3e_revised_forms_must_return_to_phase3b_and_phase3c",
            "phase3f_promotion_requires_historically_replayable_candidate",
            "phase3f_promotion_requires_broader_historical_coverage",
        ]:
            if policy.get(key) is not True:
                errors.append("PHASE3_INTERNAL_POLICY_FALSE_" + key)

    decision_path = ROOT / "PHASE3_POST3C_EVALUATION_PATH_DECISION.json"
    if state.get("post3c_evaluation_path_decision_complete"):
        if not decision_path.exists():
            errors.append("POST3C_DECISION_ARTIFACT_MISSING")
        else:
            decision = json.loads(decision_path.read_text(encoding="utf-8"))
            approved = {row["id"]: row["decision"] for row in decision["alternatives"]}
            if approved.get("PHASE3D_NEGATIVE_RESULT_MEASURABILITY_PATH") != "APPROVED":
                errors.append("POST3C_APPROVED_PATH_MISSING")
            for rejected in [
                "RETROSPECTIVE_INPUT_SYNTHESIS",
                "SILENT_PHASE3B_CONTRACT_REWRITE",
                "SKIP_PHASE3D_TO_PHASE3E",
            ]:
                if approved.get(rejected) != "REJECTED":
                    errors.append("POST3C_REJECTED_PATH_NOT_REJECTED_" + rejected)
            if decision["approved_path"]["phase3d_rules"].get("candidate_metrics_without_contemporaneous_outputs") != "NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS":
                errors.append("POST3C_NONMEASURABLE_SENTINEL_MISSING")

        if not state.get("phase3c_complete"):
            errors.append("POST3C_DECISION_BEFORE_PHASE3C_COMPLETE")
        if state.get("governed_subsequent_evaluation_path_decision_required_before_phase3d"):
            errors.append("POST3C_GATE_STILL_MARKED_REQUIRED")
        if not state.get("phase3d_start_allowed"):
            errors.append("POST3C_DECISION_DID_NOT_UNLOCK_PHASE3D")
        if current["validation"].get("post3c_evaluation_path_decision_complete") is not True:
            errors.append("CURRENT_POST3C_DECISION_NOT_COMPLETE")
        if current["validation"].get("phase3d_start_allowed") is not True:
            errors.append("CURRENT_PHASE3D_NOT_ALLOWED")
        if state.get("phase3d_started") or current["validation"].get("phase3d_started"):
            errors.append("PHASE3D_STARTED_DURING_GOVERNANCE_GATE")
        if state.get("phase3f_promotion_eligible") or current["validation"].get("phase3f_promotion_eligible"):
            errors.append("PHASE3F_PREMATURELY_ELIGIBLE")

        for name in ("CHARTER", "ROADMAP", "EXECUTION", "CHANGELOG"):
            if "NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS" not in texts[name]:
                errors.append(f"{name}_MISSING_POST3C_NONMEASURABLE_POLICY")
        if "return through governed 3B" not in texts["ROADMAP"] or "return through governed 3B" not in texts["EXECUTION"]:
            errors.append("PHASE3E_RETURN_TO_3B_3C_TEXT_GUARD_MISSING")

    if state.get("phase3d_started") and not state.get("phase3d_start_allowed"):
        errors.append("PHASE3D_STARTED_WITHOUT_PERMISSION")

    return errors


def assert_program_consistent():
    errors = validate_program_consistency()
    if errors:
        raise AssertionError(";".join(errors))


if __name__ == "__main__":
    assert_program_consistent()
    print("PROGRAM_CONSISTENCY_PASS")
