"""Real bounded Phase 3C acceptance validator against the seven Phase 3A checkpoints."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategy_kernel_v2.historical_replay import (
    CachingRegisteredSourceLoader,
    build_phase3c_replay,
    load_default_phase3c_inputs,
)


def main() -> None:
    registry, points = load_default_phase3c_inputs(REPO_ROOT)
    loader = CachingRegisteredSourceLoader(REPO_ROOT)
    replay = build_phase3c_replay(registry, points, source_loader=loader)

    if replay["checkpoint_count"] != 7:
        raise AssertionError("PHASE3C_REQUIRES_SEVEN_SEED_CHECKPOINTS")
    if replay["model_specific_evidence_fetches"] != 0:
        raise AssertionError("MODEL_SPECIFIC_EVIDENCE_FETCH_DETECTED")
    if replay["subjective_feature_fill_count"] != 0:
        raise AssertionError("SUBJECTIVE_FEATURE_FILL_DETECTED")
    if replay["retrospective_probability_backfill_count"] != 0:
        raise AssertionError("RETROSPECTIVE_PROBABILITY_BACKFILL_DETECTED")
    if replay["retrospective_scenario_backfill_count"] != 0:
        raise AssertionError("RETROSPECTIVE_SCENARIO_BACKFILL_DETECTED")

    aggregate = replay["aggregate_by_model"]
    legacy = aggregate["LEGACY_POLICY_BASELINE"]["evaluable_security_instances"]
    phase2 = aggregate["PHASE2_PROBABILISTIC_VECTOR"]["evaluable_security_instances"]
    simple = aggregate["SIMPLE_NON_PROBABILISTIC_PARETO"]["evaluable_security_instances"]

    if legacy <= 0:
        raise AssertionError("REAL_SEED_MUST_REPLAY_AT_LEAST_ONE_CONTEMPORANEOUS_LEGACY_STATE")

    # Current historical sources contain no explicit complete Phase-2 probability/vector
    # packet and no explicit complete five-field simple-Pareto packet. If these become
    # nonzero, the extraction contract or source set changed and must be reviewed rather
    # than silently changing the Phase 3C conclusion.
    if phase2 != 0:
        raise AssertionError("UNEXPECTED_PHASE2_EVALUABLE_INPUT_REVIEW_REQUIRED")
    if simple != 0:
        raise AssertionError("UNEXPECTED_SIMPLE_PARETO_EVALUABLE_INPUT_REVIEW_REQUIRED")

    if replay["historical_performance_metrics_generated"]:
        raise AssertionError("PHASE3D_METRICS_FORBIDDEN_IN_PHASE3C")
    if replay["regret_analysis_generated"] or replay["calibration_generated"]:
        raise AssertionError("PHASE3D_WORK_FORBIDDEN_IN_PHASE3C")
    if replay["user_decision_generated"] or replay["investment_recommendation_generated"]:
        raise AssertionError("USER_DECISION_OR_RECOMMENDATION_FORBIDDEN")
    if replay["controls"]["orders"] != 0 or replay["controls"]["trade_authority"] != "NONE":
        raise AssertionError("AUTHORITY_BOUNDARY_BROKEN")

    print(
        "PHASE3C_ACCEPTANCE_PASS "
        f"checkpoints={replay['checkpoint_count']} "
        f"historical_source_reads={loader.read_count} "
        f"legacy_evaluable={legacy} "
        f"phase2_evaluable={phase2} "
        f"simple_evaluable={simple} "
        "subjective_fills=0 probability_backfills=0 scenario_backfills=0 "
        "orders=0 trade_authority=NONE"
    )


if __name__ == "__main__":
    main()
