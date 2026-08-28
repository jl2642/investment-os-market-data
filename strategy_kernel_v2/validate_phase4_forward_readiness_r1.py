from __future__ import annotations

from strategy_kernel_v2.phase4_forward_readiness_r1 import (
    build_forward_readiness_audit,
    load_adapter,
    write_default,
)
from strategy_kernel_v2.program_consistency import validate_program_consistency
from strategy_kernel_v2.validate_phase4_forward_shadow_contract import validate as validate_phase4_contract


def validate():
    errors = list(validate_program_consistency())
    errors.extend(validate_phase4_contract())
    adapter = load_adapter()
    if adapter.get("status") != "FROZEN_BEFORE_P4_1_DISCOVERY_AUDIT":
        errors.append("P4_R1_CONTRACT_NOT_FROZEN")
    if adapter["source_universe"].get("source_branch") != "main":
        errors.append("P4_R1_SOURCE_BRANCH_DRIFT")
    if adapter["source_universe"].get("first_parent_only") is not True:
        errors.append("P4_R1_FIRST_PARENT_GUARD_MISSING")
    if adapter["source_universe"].get("open_pr_heads_allowed") is not False:
        errors.append("P4_R1_OPEN_PR_HEADS_ALLOWED")
    if adapter["selector_semantics"].get("discretionary_subsampling_allowed") is not False:
        errors.append("P4_R1_DISCRETIONARY_SUBSAMPLING_OPEN")
    if adapter["selector_semantics"].get("manual_cherry_pick_allowed") is not False:
        errors.append("P4_R1_MANUAL_CHERRY_PICK_OPEN")
    if adapter["selector_semantics"].get("pre_cutoff_source_alone_may_trigger_checkpoint") is not False:
        errors.append("P4_R1_PRE_CUTOFF_SOURCE_CAN_TRIGGER")
    if adapter["selector_semantics"].get("pre_cutoff_source_may_remain_visible_as_point_in_time_context") is not True:
        errors.append("P4_R1_CONTEXT_CARRY_FORWARD_FORBIDDEN")

    result = build_forward_readiness_audit()
    allowed_status = {
        "WAITING_FOR_FIRST_POST_CUTOFF_CANONICAL_MAIN_COMMIT",
        "WAITING_FOR_ELIGIBLE_FORWARD_CHECKPOINT",
        "FORWARD_CHECKPOINTS_DISCOVERED_READY_FOR_PARALLEL_REPLAY",
    }
    if result.get("status") not in allowed_status:
        errors.append("P4_R1_STATUS_INVALID")
    if result.get("legacy_runner_execution_count") != 0:
        errors.append("P4_R1_LEGACY_PREMATURE_EXECUTION")
    if result.get("r2_profile_compute_count") != 0 or result.get("r2_pareto_compute_count") != 0:
        errors.append("P4_R1_R2_PREMATURE_EXECUTION")
    if result.get("realized_outcome_read_count") != 0 or result.get("future_return_read_count") != 0:
        errors.append("P4_R1_OUTCOME_PREMATURE_READ")
    if result.get("phase4_started") is not False:
        errors.append("P4_R1_PREMATURE_PHASE4_START")
    if result.get("phase4_forward_validation_complete") is not False:
        errors.append("P4_R1_PREMATURE_PHASE4_COMPLETE")
    if result.get("phase5_migration_allowed") is not False:
        errors.append("P4_R1_PREMATURE_PHASE5")
    controls = result.get("controls", {})
    if controls.get("orders") != 0 or controls.get("trade_authority") != "NONE":
        errors.append("P4_R1_AUTHORITY_DRIFT")

    if not errors:
        write_default(result)
    return errors, result


if __name__ == "__main__":
    errors, result = validate()
    if errors:
        raise AssertionError(";".join(errors))
    print(
        "PHASE4_FORWARD_READINESS_R1_ACCEPTANCE "
        f"status={result['status']} post_cutoff_commits={result['post_cutoff_first_parent_commit_count']} "
        f"selected={result['selected_forward_checkpoint_count']} "
        f"parallel_start={str(result['phase4_parallel_replay_start_allowed_from_this_audit']).lower()} "
        "phase4_started=false phase5=false orders=0 trade_authority=NONE "
        f"sha256={result['readiness_audit_sha256']}"
    )
