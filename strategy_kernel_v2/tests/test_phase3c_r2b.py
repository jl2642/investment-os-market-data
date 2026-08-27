from __future__ import annotations

import unittest

from strategy_kernel_v2.phase3b_r2_contract import (
    load_contract as load_r2_contract,
    transform_model_neutral_row,
)
import strategy_kernel_v2.phase3c_r2a_reconstruction as r2a
import strategy_kernel_v2.phase3c_r2b_replay as r2b


class Phase3CR2BTests(unittest.TestCase):
    def test_r2b_contract_is_second_and_final_phase3c_r2_round(self):
        contract = r2b.load_replay_contract()
        self.assertEqual(r2b.validate_replay_contract(contract), [])
        execution = contract["execution_round_contract"]
        self.assertEqual(execution["phase3c_r2_total_execution_rounds"], 2)
        self.assertEqual(
            execution["this_round"],
            "R2B_MECHANICAL_REPLAY_FULL_AUDIT_AND_FINAL_ACCEPTANCE",
        )
        self.assertTrue(execution["mechanical_r2_replay_starts_in_this_round"])
        self.assertTrue(execution["no_additional_phase3c_r2_execution_round_is_created"])

    def test_r2b_contract_forbids_outcomes_holdout_and_global_winner(self):
        contract = r2b.load_replay_contract()
        boundary = contract["phase_boundary"]
        comparison = contract["comparison_contract"]
        self.assertFalse(boundary["r2b_generates_historical_performance"])
        self.assertFalse(boundary["r2b_loads_phase3d_realized_outcomes"])
        self.assertFalse(boundary["r2b_builds_independent_holdout"])
        self.assertFalse(boundary["r2b_selects_global_winner"])
        self.assertFalse(comparison["scalar_policy_score_allowed"])
        self.assertFalse(comparison["dimension_weights_allowed"])
        self.assertFalse(comparison["ranking_allowed"])
        self.assertFalse(comparison["global_winner_selection_allowed"])
        self.assertFalse(comparison["target_weight_generation_allowed"])

    def test_classification_is_pre_registered_and_not_count_tuned(self):
        self.assertEqual(
            r2b._classify([], 1, 2),
            "PASS_MECHANICAL_REPLAY_OPERATIONAL",
        )
        self.assertEqual(
            r2b._classify([], 0, 0),
            "PARTIAL_VALID_REPLAY_NO_MULTI_PROFILE_EXACT_SIGNATURE_GROUP",
        )
        self.assertEqual(
            r2b._classify(["AUDIT_ERROR"], 5, 10),
            "FAIL_REPLAY_CONTRACT_OR_AUDIT",
        )

    def test_r2a_profile_adapter_preserves_exact_signature(self):
        contract = load_r2_contract()
        row = {
            "security_id": "TEST.SEC",
            "security_name": "Test Security",
            "features": {
                "candidate_archive_evidence_score": 90,
                "candidate_archive_quality_score": 85,
                "candidate_archive_risk_penalty": 5,
                "candidate_archive_valuation_score_coarse": 80,
            },
            "feature_provenance": {
                "candidate_archive_evidence_score": ["E1"],
                "candidate_archive_quality_score": ["E1"],
                "candidate_archive_risk_penalty": ["E1"],
                "candidate_archive_valuation_score_coarse": ["E1"],
            },
            "provenance_evidence_ids": ["E1"],
        }
        transformed = transform_model_neutral_row(row, contract)
        states = r2a._dimension_state_ledger(row, transformed, contract)
        parent_profile = {
            "security_id": "TEST.SEC",
            "security_name": "Test Security",
            "provenance_evidence_ids": ["E1"],
            "dimension_states": states,
            "profile_evaluable": transformed["profile_evaluable"],
            "comparison_contract_evaluable": transformed["comparison_contract_evaluable"],
            "comparison_signature": transformed["comparison_signature"],
            "comparison_signature_sha256": transformed["comparison_signature_sha256"],
            "preserved_unmapped_context": {},
        }
        replay_profile = r2b._to_comparator_profile(parent_profile, contract)
        self.assertEqual(
            replay_profile["comparison_signature_sha256"],
            transformed["comparison_signature_sha256"],
        )
        self.assertEqual(
            replay_profile["comparison_signature"],
            transformed["comparison_signature"],
        )
        self.assertTrue(replay_profile["comparison_contract_evaluable"])

    def test_missing_dimensions_are_not_inserted_into_comparison_signature(self):
        contract = load_r2_contract()
        row = {
            "security_id": "TEST.SEC",
            "features": {"candidate_archive_evidence_score": 90},
            "feature_provenance": {"candidate_archive_evidence_score": ["E1"]},
            "provenance_evidence_ids": ["E1"],
        }
        transformed = transform_model_neutral_row(row, contract)
        states = r2a._dimension_state_ledger(row, transformed, contract)
        parent_profile = {
            "security_id": "TEST.SEC",
            "provenance_evidence_ids": ["E1"],
            "dimension_states": states,
            "profile_evaluable": transformed["profile_evaluable"],
            "comparison_contract_evaluable": transformed["comparison_contract_evaluable"],
            "comparison_signature": transformed["comparison_signature"],
            "comparison_signature_sha256": transformed["comparison_signature_sha256"],
            "preserved_unmapped_context": {},
        }
        replay_profile = r2b._to_comparator_profile(parent_profile, contract)
        self.assertEqual(len(replay_profile["dimensions"]), 1)
        self.assertEqual(
            replay_profile["dimensions"][0]["dimension_id"],
            "EVIDENCE_ARCHIVE_SCORE",
        )
        self.assertFalse(replay_profile["comparison_contract_evaluable"])

    def test_authority_and_cross_boundary_controls_remain_closed(self):
        self.assertFalse(r2b.CONTROLS["realized_outcome_loading_allowed"])
        self.assertFalse(r2b.CONTROLS["holdout_build_allowed"])
        self.assertFalse(r2b.CONTROLS["cross_checkpoint_comparison_allowed"])
        self.assertFalse(r2b.CONTROLS["cross_signature_comparison_allowed"])
        self.assertFalse(r2b.CONTROLS["ranking_allowed"])
        self.assertFalse(r2b.CONTROLS["global_winner_selection_allowed"])
        self.assertEqual(r2b.CONTROLS["orders"], 0)
        self.assertEqual(r2b.CONTROLS["trade_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
