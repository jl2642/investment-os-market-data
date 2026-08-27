from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

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


class Phase3CR2ATests(unittest.TestCase):
    def test_r2a_contract_is_reconstruction_only(self):
        contract = r2a.load_replay_contract()
        self.assertEqual(r2a.validate_replay_contract(contract), [])
        self.assertEqual(contract["development_corpus"]["checkpoint_count"], 7)
        self.assertIs(contract["development_corpus"]["independent_holdout"], False)
        self.assertEqual(contract["transform_contract"]["transform_rule_count"], 20)
        self.assertIs(contract["phase_boundary"]["r2a_executes_pareto"], False)
        self.assertIs(contract["phase_boundary"]["r2a_loads_phase3d_realized_outcomes"], False)
        self.assertIs(contract["phase_boundary"]["r2a_builds_independent_holdout"], False)
        self.assertIs(contract["phase_boundary"]["phase4_entry_allowed"], False)

    def test_missing_rule_is_unknown_applicability_not_zero_or_not_applicable(self):
        r2_contract = load_r2_contract()
        source = _row(candidate_archive_evidence_score=91)
        profile = r2a.transform_model_neutral_row(source, r2_contract)
        states = r2a._dimension_state_ledger(source, profile, r2_contract)
        by_rule = {item["rule_id"]: item for item in states}
        present = by_rule["R2_CANDIDATE_ARCHIVE_EVIDENCE_SCORE_V1"]
        missing = by_rule["R2_CANDIDATE_ARCHIVE_QUALITY_SCORE_V1"]
        self.assertEqual(present["state"], "PRESENT")
        self.assertEqual(present["value"], 91.0)
        self.assertEqual(present["provenance_evidence_ids"], ["E1"])
        self.assertEqual(missing["state"], "MISSING")
        self.assertEqual(missing["applicability_state"], "UNKNOWN_APPLICABILITY")
        self.assertNotIn("value", missing)
        self.assertEqual(missing["provenance_evidence_ids"], [])

    def test_transform_failure_remains_explicit(self):
        r2_contract = load_r2_contract()
        source = _row(candidate_archive_evidence_score=101)
        profile = r2a.transform_model_neutral_row(source, r2_contract)
        states = r2a._dimension_state_ledger(source, profile, r2_contract)
        target = next(item for item in states if item["rule_id"] == "R2_CANDIDATE_ARCHIVE_EVIDENCE_SCORE_V1")
        self.assertEqual(target["state"], "TRANSFORM_FAILURE")
        self.assertEqual(target["applicability_state"], "UNKNOWN_APPLICABILITY")
        self.assertEqual(target["provenance_evidence_ids"], ["E1"])

    def test_builder_reconstructs_profiles_without_pareto_or_holdout(self):
        snapshot = {
            "decision_point_id": "DP1",
            "at": "2026-08-01T00:00:00Z",
            "opportunity_security_ids": ["TEST.SEC"],
            "selected_evidence_ids": ["E1"],
            "selected_evidence": [],
        }
        fake_feature_layer = {
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
        }

        class Loader:
            read_count = 1

            def __call__(self, record):
                raise AssertionError("patched extractor must not call loader")

        with patch.object(
            r2a,
            "build_point_in_time_ledger",
            return_value={"snapshots": [deepcopy(snapshot)]},
        ), patch.object(
            r2a,
            "extract_model_neutral_features",
            return_value=fake_feature_layer,
        ):
            result = r2a.build_phase3c_r2a_reconstruction(
                {"records": []},
                {"decision_points": []},
                source_loader=Loader(),
            )

        self.assertEqual(result["checkpoint_count"], 1)
        self.assertEqual(result["r2_profile_instances"], 1)
        self.assertEqual(result["present_dimension_instances"], 3)
        self.assertEqual(result["pareto_comparison_count"], 0)
        self.assertEqual(result["cross_signature_comparison_count"], 0)
        self.assertEqual(result["historical_performance_metric_count"], 0)
        self.assertEqual(result["realized_outcome_record_count"], 0)
        self.assertEqual(result["holdout_checkpoint_count"], 0)
        self.assertIs(result["winner_selected"], False)
        self.assertIs(result["phase4_entry_allowed"], False)
        self.assertEqual(result["controls"]["trade_authority"], "NONE")

    def test_r2a_does_not_import_or_call_pareto_comparator(self):
        self.assertNotIn("compare_r2_profiles", r2a.__dict__)
        self.assertIs(r2a.FALSE_CONTROLS["pareto_dominance_execution_allowed"], False)
        self.assertIs(r2a.FALSE_CONTROLS["winner_selection_allowed"], False)
        self.assertIs(r2a.FALSE_CONTROLS["holdout_build_allowed"], False)


if __name__ == "__main__":
    unittest.main()
