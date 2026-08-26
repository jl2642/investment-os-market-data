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

EXPECTED_STATUS = "PARTIAL_REPLAY_MODEL_INPUT_COVERAGE_BLOCKED"


def _legacy_statuses(replay: dict, security_id: str) -> set[str]:
    statuses: set[str] = set()
    for checkpoint in replay["checkpoint_results"]:
        for model in checkpoint["model_summaries"]:
            if model["model_form"] != "LEGACY_POLICY_BASELINE":
                continue
            for row in model["outcomes"]:
                if row["security_id"] == security_id:
                    statuses.add(row["status"])
    return statuses


def main() -> None:
    registry, points = load_default_phase3c_inputs(REPO_ROOT)
    loader = CachingRegisteredSourceLoader(REPO_ROOT)
    replay = build_phase3c_replay(registry, points, source_loader=loader)

    if replay["checkpoint_count"] != 7:
        raise AssertionError("PHASE3C_REQUIRES_SEVEN_SEED_CHECKPOINTS")
    if replay["replay_status"] != EXPECTED_STATUS:
        raise AssertionError("UNEXPECTED_PHASE3C_REPLAY_STATUS:" + replay["replay_status"])
    if replay["feature_extraction_mode"] != "EXACT_REGISTERED_COMMIT_PATH_GIT_SHOW":
        raise AssertionError("HISTORICAL_SOURCE_MODE_DRIFT")
    if loader.read_count <= 0:
        raise AssertionError("NO_REGISTERED_HISTORICAL_SOURCES_READ")
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
    if phase2 != 0:
        raise AssertionError("UNEXPECTED_PHASE2_EVALUABLE_INPUT_REVIEW_REQUIRED")
    if simple != 0:
        raise AssertionError("UNEXPECTED_SIMPLE_PARETO_EVALUABLE_INPUT_REVIEW_REQUIRED")
    if replay["candidate_model_evaluable_security_instances"] != 0:
        raise AssertionError("CANDIDATE_MODEL_COVERAGE_MUST_REMAIN_ZERO_ON_CURRENT_SEED")
    if replay["comparative_candidate_replay_available"]:
        raise AssertionError("MULTI_MODEL_COMPARISON_MUST_REMAIN_BLOCKED_ON_CURRENT_SEED")

    # Preserve semantic distinctions: investment HOLD is retained; research HOLD with
    # explicit NO_DECISION / NOT_DECISION_GRADE is NO_ACTION, not a portfolio hold.
    if "RETAINED" not in _legacy_statuses(replay, "601138.SH"):
        raise AssertionError("601138_CONTEMPORANEOUS_HOLD_NOT_REPLAYED_AS_RETAINED")
    if "NO_ACTION" not in _legacy_statuses(replay, "HKEX:00669"):
        raise AssertionError("00669_WATCH_NO_TRADE_NOT_REPLAYED_AS_NO_ACTION")
    if "NO_ACTION" not in _legacy_statuses(replay, "000719.SZ"):
        raise AssertionError("000719_RESEARCH_NO_DECISION_SEMANTICS_BROKEN")
    if "NO_ACTION" not in _legacy_statuses(replay, "301215.SZ"):
        raise AssertionError("301215_NOT_DECISION_GRADE_SEMANTICS_BROKEN")

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
        f"status={replay['replay_status']} "
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
