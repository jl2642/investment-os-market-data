from __future__ import annotations

from copy import deepcopy

import strategy_kernel_v2.phase3c_r2a_reconstruction as r2a
from strategy_kernel_v2.phase3b_r2_contract import load_contract as load_r2_contract


def _row(**features):
    return {
        "security_id": "TEST.SEC",
        "security_name": "Test Security",
        "features": features,
        "feature_provenance": {key: ["E1"] for key in features},
        "provenance_evidence_ids": ["E1"],
    }


def test_r2a_contract_is_reconstruction_only():
    contract = r2a.load_replay_contract()
    assert r2a.validate_replay_contract(contract) == []
    assert contract["development_corpus"]["checkpoint_count"] == 7
    assert contract["development_corpus"]["independent_holdout"] is False
    assert contract["transform_contract"]["transform_rule_count"] == 20
    assert contract["phase_boundary"]["r2a_executes_pareto"] is False
    assert contract["phase_boundary"]["r2a_loads_phase3d_realized_outcomes"] is False
    assert contract["phase_boundary"]["r2a_builds_independent_holdout"] is False
    assert contract["phase_boundary"]["phase4_entry_allowed"] is False


def test_missing_rule_is_unknown_applicability_not_zero_or_not_applicable():
    r2_contract = load_r2_contract()
    source = _row(candidate_archive_evidence_score=91)
    profile = r2a.transform_model_neutral_row(source, r2_contract)
    states = r2a._dimension_state_ledger(source, profile, r2_contract)
    by_rule = {item["rule_id"]: item for item in states}
    present = by_rule["R2_CANDIDATE_ARCHIVE_EVIDENCE_SCORE_V1"]
    missing = by_rule["R2_CANDIDATE_ARCHIVE_QUALITY_SCORE_V1"]
    assert present["state"] == "PRESENT"
    assert present["value"] == 91.0
    assert present["provenance_evidence_ids"] == ["E1"]
    assert missing["state"] == "MISSING"
    assert missing["applicability_state"] == "UNKNOWN_APPLICABILITY"
    assert "value" not in missing
    assert missing["provenance_evidence_ids"] == []


def test_transform_failure_remains_explicit():
    r2_contract = load_r2_contract()
    source = _row(candidate_archive_evidence_score=101)
    profile = r2a.transform_model_neutral_row(source, r2_contract)
    states = r2a._dimension_state_ledger(source, profile, r2_contract)
    target = next(item for item in states if item["rule_id"] == "R2_CANDIDATE_ARCHIVE_EVIDENCE_SCORE_V1")
    assert target["state"] == "TRANSFORM_FAILURE"
    assert target["applicability_state"] == "UNKNOWN_APPLICABILITY"
    assert target["provenance_evidence_ids"] == ["E1"]


def test_builder_reconstructs_profiles_without_pareto_or_holdout(monkeypatch):
    snapshot = {
        "decision_point_id": "DP1",
        "at": "2026-08-01T00:00:00Z",
        "opportunity_security_ids": ["TEST.SEC"],
        "selected_evidence_ids": ["E1"],
        "selected_evidence": [],
    }
    monkeypatch.setattr(
        r2a,
        "build_point_in_time_ledger",
        lambda records, points: {"snapshots": [deepcopy(snapshot)]},
    )
    monkeypatch.setattr(
        r2a,
        "extract_model_neutral_features",
        lambda snap, source_loader: {
            "feature_rows": {
                "TEST.SEC": _row(
                    candidate_archive_evidence_score=90,
                    candidate_archive_quality_score=85,
                    candidate_archive_risk_penalty=4,
                )
            },
            "unsupported_selected_evidence_ids": [],
            "subjective_feature_fill_count": 0,
            "retrospective_probability_backfill_count": 0,
            "retrospective_scenario_backfill_count": 0,
        },
    )

    class Loader:
        read_count = 1

        def __call__(self, record):
            raise AssertionError("patched extractor must not call loader")

    result = r2a.build_phase3c_r2a_reconstruction(
        {"records": []},
        {"decision_points": []},
        source_loader=Loader(),
    )
    assert result["checkpoint_count"] == 1
    assert result["r2_profile_instances"] == 1
    assert result["present_dimension_instances"] == 3
    assert result["pareto_comparison_count"] == 0
    assert result["cross_signature_comparison_count"] == 0
    assert result["historical_performance_metric_count"] == 0
    assert result["realized_outcome_record_count"] == 0
    assert result["holdout_checkpoint_count"] == 0
    assert result["winner_selected"] is False
    assert result["phase4_entry_allowed"] is False
    assert result["controls"]["trade_authority"] == "NONE"


def test_r2a_does_not_import_or_call_pareto_comparator():
    assert "compare_r2_profiles" not in r2a.__dict__
    assert r2a.FALSE_CONTROLS["pareto_dominance_execution_allowed"] is False
    assert r2a.FALSE_CONTROLS["winner_selection_allowed"] is False
    assert r2a.FALSE_CONTROLS["holdout_build_allowed"] is False
