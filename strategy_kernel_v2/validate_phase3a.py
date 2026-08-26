"""Independent acceptance validator for Strategy Kernel v2 Phase 3A."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

from strategy_kernel_v2.build_phase3a_ledger import POINTS, REGISTRY, build

ROOT = Path(__file__).resolve().parent
VALIDATION = ROOT / "PHASE3A_VALIDATION.json"
DERIVED_LEDGER = ROOT / "generated" / "PHASE3A_POINT_IN_TIME_EVIDENCE_LEDGER.json"
REPO_ROOT = ROOT.parent


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _derived_ledger_is_tracked() -> bool:
    relative = DERIVED_LEDGER.relative_to(REPO_ROOT)
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(relative)],
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return False
    return result.returncode == 0


def validate_phase3a() -> list[str]:
    errors: list[str] = []
    registry = load_json(REGISTRY)
    points = load_json(POINTS)
    validation = load_json(VALIDATION)

    first = build()
    second = build()
    if canonical_json(first) != canonical_json(second):
        errors.append("NON_DETERMINISTIC_LEDGER_REBUILD")

    records = registry.get("records", [])
    decision_points = points.get("decision_points", [])
    scope = validation.get("scope", {})
    declared = validation.get("validation", {})
    promotion = validation.get("promotion", {})
    boundaries = validation.get("authority_boundaries", {})

    if validation.get("status") != "PASS_SCOPE_BOUNDED":
        errors.append("PHASE3A_STATUS_NOT_SCOPE_BOUNDED_PASS")
    if first.get("phase") != "3A" or first.get("mode") != "POINT_IN_TIME_EVIDENCE_LEDGER":
        errors.append("LEDGER_IDENTITY_MISMATCH")
    if first.get("authority_domains_included") != ["CANONICAL_MAIN"]:
        errors.append("NON_CANONICAL_AUTHORITY_INCLUDED")

    expected_records = scope.get("canonical_evidence_records")
    expected_points = scope.get("canonical_replay_checkpoints")
    if len(records) != expected_records or first.get("evidence_record_count") != expected_records:
        errors.append("EVIDENCE_RECORD_COUNT_MISMATCH")
    if len(decision_points) != expected_points or first.get("decision_point_count") != expected_points:
        errors.append("DECISION_POINT_COUNT_MISMATCH")

    snapshots = first.get("snapshots", [])
    complete_count = sum(bool(x.get("snapshot_complete_for_declared_requirements")) for x in snapshots)
    if complete_count != declared.get("declared_checkpoint_requirement_sets_complete"):
        errors.append("DECLARED_CHECKPOINT_COMPLETENESS_MISMATCH")

    if first.get("model_output_generated") is not False:
        errors.append("MODEL_OUTPUT_GENERATED")
    if first.get("investment_recommendation_generated") is not False:
        errors.append("INVESTMENT_RECOMMENDATION_GENERATED")
    if first.get("user_decision_generated") is not False:
        errors.append("USER_DECISION_GENERATED")

    controls = first.get("controls", {})
    false_controls = [
        "hindsight_allowed",
        "retrospective_probability_backfill_allowed",
        "retrospective_scenario_backfill_allowed",
        "candidate_mutation_allowed",
        "real_position_mutation_allowed",
        "simulation_position_mutation_allowed",
        "target_portfolio_writeback_allowed",
        "user_decision_generation_allowed",
        "investment_recommendation_generation_allowed",
        "order_authorized",
    ]
    for key in false_controls:
        if controls.get(key) is not False:
            errors.append("CONTROL_NOT_FALSE_" + key)
    if controls.get("orders") != 0 or controls.get("trade_authority") != "NONE":
        errors.append("LEDGER_TRADE_AUTHORITY_BOUNDARY_BROKEN")

    if declared.get("hindsight_contamination_detected") != 0:
        errors.append("DECLARED_HINDSIGHT_CONTAMINATION")
    if declared.get("retrospective_probability_backfills") != 0:
        errors.append("DECLARED_PROBABILITY_BACKFILL")
    if declared.get("retrospective_scenario_backfills") != 0:
        errors.append("DECLARED_SCENARIO_BACKFILL")
    if declared.get("derived_ledger_committed_as_authority") is not False:
        errors.append("DERIVED_LEDGER_DECLARED_AS_AUTHORITY")
    if declared.get("derived_ledger_rebuild_required") is not True:
        errors.append("DERIVED_LEDGER_REBUILD_NOT_REQUIRED")
    if _derived_ledger_is_tracked():
        errors.append("DERIVED_LEDGER_TRACKED_IN_GIT")

    if promotion.get("phase3b_start_allowed") is not True:
        errors.append("PHASE3B_NOT_ALLOWED_AFTER_ACCEPTED_3A")
    for key in ("phase3_historical_validation_complete", "phase3f_promotion_eligible", "phase4_entry_allowed", "phase5_migration_allowed"):
        if promotion.get(key) is not False:
            errors.append("PREMATURE_PROMOTION_" + key)
    if promotion.get("historical_coverage_expansion_required_before_phase3f") is not True:
        errors.append("PHASE3F_COVERAGE_EXPANSION_GUARD_MISSING")

    zero_boundaries = [
        "effective_core_static_changes",
        "candidate_membership_mutations",
        "real_account_mutations",
        "simulation_mutations",
        "target_portfolio_writebacks",
        "user_decisions_generated",
        "orders",
    ]
    for key in zero_boundaries:
        if boundaries.get(key) != 0:
            errors.append("AUTHORITY_BOUNDARY_NONZERO_" + key)
    if boundaries.get("trade_authority") != "NONE":
        errors.append("VALIDATION_TRADE_AUTHORITY_NOT_NONE")

    return errors


def main() -> int:
    errors = validate_phase3a()
    if errors:
        raise AssertionError(";".join(errors))
    ledger = build()
    print(
        "PHASE3A_ACCEPTANCE_PASS",
        f"records={ledger['evidence_record_count']}",
        f"checkpoints={ledger['decision_point_count']}",
        "deterministic_rebuild=true",
        "orders=0",
        "trade_authority=NONE",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
