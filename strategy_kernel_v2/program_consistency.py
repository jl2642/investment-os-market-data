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


def j(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def validate_program_consistency():
    errors = []
    contract = j("PROGRAM_CONTRACT.json")
    state = j("PROGRAM_STATE.json")
    current = j("CURRENT_PHASE_STATUS.json")
    roadmap = (ROOT / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    execution = (ROOT / "PHASE_EXECUTION_PLAN.md").read_text(encoding="utf-8")
    charter = (ROOT / "MASTER_PROGRAM_CHARTER.md").read_text(encoding="utf-8")

    if [(x["phase"], x["name"]) for x in contract["macro_lifecycle"]] != EXPECTED:
        errors.append("MACRO_LIFECYCLE_MISMATCH")

    for phase, _ in EXPECTED:
        for name, text in [("CHARTER", charter), ("ROADMAP", roadmap), ("EXECUTION", execution)]:
            if f"Phase {phase}" not in text:
                errors.append(f"{name}_MISSING_PHASE_{phase}")

    gates = contract["mandatory_gates"]
    if not gates["phase4_forward_validation_required_for_phase5"]:
        errors.append("PHASE4_NOT_REQUIRED_FOR_PHASE5")
    if not gates["direct_phase3_to_phase5_forbidden"]:
        errors.append("DIRECT_PHASE3_TO_PHASE5_NOT_FORBIDDEN")

    if state["macro_phase"] != 2 or state["next_macro_phase"] != 3:
        errors.append("PROGRAM_STATE_PHASE_MISMATCH")
    if not state["phase4_required"]:
        errors.append("PROGRAM_STATE_PHASE4_NOT_REQUIRED")
    if state["phase5_migration_allowed"]:
        errors.append("PROGRAM_STATE_PHASE5_PREMATURE")
    if state["direct_phase3_to_phase5_allowed"]:
        errors.append("PROGRAM_STATE_DIRECT_3_TO_5")

    if current["current_macro_phase"] != state["macro_phase"] or current["next_macro_phase"] != state["next_macro_phase"]:
        errors.append("CURRENT_STATUS_PHASE_MISMATCH")
    if not current["phase4_required"] or current["phase5_migration_allowed"]:
        errors.append("CURRENT_STATUS_PROMOTION_GUARD_BROKEN")

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

    if "PROMOTE_TO_PHASE_4_FORWARD_VALIDATION" not in execution or "`PROMOTE_TO_PHASE_5` is forbidden" not in execution:
        errors.append("PHASE3_EXIT_GUARD_MISSING")

    return errors


def assert_program_consistent():
    errors = validate_program_consistency()
    if errors:
        raise AssertionError(";".join(errors))


if __name__ == "__main__":
    assert_program_consistent()
    print("PROGRAM_CONSISTENCY_PASS")
