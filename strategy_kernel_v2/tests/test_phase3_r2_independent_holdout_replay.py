from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

import strategy_kernel_v2.phase3_r2_independent_holdout_replay as replay

ROOT = Path(__file__).resolve().parents[1]


class IndependentHoldoutReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = replay.load_replay_contract()

    def test_frozen_contract_accepts_without_errors(self):
        self.assertEqual(replay.validate_replay_contract(self.contract), [])

    def test_parent_selection_and_model_are_exact(self):
        parent = self.contract["parent_selection"]
        self.assertEqual(parent["pr"], 324)
        self.assertEqual(parent["final_head"], "ac828fc275162fad1376f538e3395b74633f4baa")
        self.assertEqual(parent["status"], "PASS_SELECTION_SUFFICIENCY")
        self.assertEqual(parent["checkpoint_count"], 14)
        self.assertEqual(
            parent["selection_ledger_sha256"],
            "241bb441a960b2ccfb46a708ae81f7b38d5b2389215362406255cd4945b337be",
        )
        model = self.contract["model_contract"]
        self.assertEqual(model["model_form"], "EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2")
        self.assertEqual(model["model_version"], "R2.0.1_RESEARCH")
        self.assertEqual(model["frozen_transform_rule_count"], 20)

    def test_coverage_only_families_gain_no_new_feature_semantics(self):
        firewall = self.contract["feature_semantics_firewall"]
        self.assertEqual(
            firewall["v2_coverage_only_families_that_may_not_gain_new_feature_semantics"],
            [
                "RESEARCH_OBJECTS_CURRENT",
                "R1_DECISION_COVERAGE_PACK_CURRENT",
                "RESEARCH_QUEUE_D1_CURRENT",
                "RESEARCH_QUEUE_D2_CURRENT",
            ],
        )
        self.assertFalse(firewall["unsupported_family_data_may_create_new_r2_dimension"])
        self.assertFalse(self.contract["replay_input_contract"]["new_family_feature_mapping_during_replay_forbidden"] is False)

    def test_no_outcome_or_model_mutation_openings(self):
        for key in (
            "new_transform_rules_allowed",
            "transform_threshold_changes_allowed",
            "transform_semantics_changes_allowed",
            "comparison_signature_changes_allowed",
        ):
            self.assertFalse(self.contract["model_contract"][key])
        for key in (
            "realized_outcomes_loaded",
            "phase3d_results_loaded",
            "future_returns_loaded",
            "regret_loaded",
            "calibration_loaded",
            "historical_performance_generated",
            "model_or_selection_tuning_from_outcomes",
        ):
            self.assertFalse(self.contract["outcome_firewall"][key])
        for key in (
            "model_specific_evidence_fetch_allowed",
            "later_evidence_backfill_allowed",
            "present_day_substitution_allowed",
            "new_family_feature_mapping_allowed",
            "new_security_scope_member_allowed",
            "subjective_mapping_allowed",
            "silent_proxy_allowed",
            "realized_outcome_loading_allowed",
            "phase3d_result_loading_allowed",
            "future_return_loading_allowed",
            "regret_loading_allowed",
            "calibration_loading_allowed",
            "cross_checkpoint_comparison_allowed",
            "cross_signature_comparison_allowed",
            "scalar_policy_score_allowed",
            "dimension_weights_allowed",
            "ranking_allowed",
            "global_winner_selection_allowed",
            "target_weight_generation_allowed",
        ):
            self.assertFalse(replay.CONTROLS[key], key)

    def test_classification_is_precommitted(self):
        self.assertEqual(
            replay._classify(
                audit_errors=[],
                transform_failures=0,
                comparable_groups=1,
                comparable_profiles=2,
            ),
            "PASS_INDEPENDENT_HOLDOUT_REPLAY_OPERATIONAL",
        )
        self.assertEqual(
            replay._classify(
                audit_errors=[],
                transform_failures=0,
                comparable_groups=0,
                comparable_profiles=0,
            ),
            "PARTIAL_VALID_HOLDOUT_REPLAY_NO_COMPARABLE_EXACT_SIGNATURE_GROUP",
        )
        self.assertEqual(
            replay._classify(
                audit_errors=["X"],
                transform_failures=0,
                comparable_groups=1,
                comparable_profiles=2,
            ),
            "FAIL_HOLDOUT_REPLAY_CONTRACT_OR_AUDIT",
        )
        self.assertEqual(
            replay._classify(
                audit_errors=[],
                transform_failures=1,
                comparable_groups=1,
                comparable_profiles=2,
            ),
            "FAIL_HOLDOUT_REPLAY_CONTRACT_OR_AUDIT",
        )

    def test_contract_mutation_is_detected(self):
        mutated = deepcopy(self.contract)
        mutated["model_contract"]["frozen_transform_rule_count"] = 21
        self.assertIn(
            "HOLDOUT_REPLAY_TRANSFORM_COUNT_DRIFT",
            replay.validate_replay_contract(mutated),
        )
        mutated = deepcopy(self.contract)
        mutated["comparison_contract"]["scalar_policy_score_allowed"] = True
        self.assertIn(
            "HOLDOUT_REPLAY_FORBIDDEN_COMPARISON_TRUE:scalar_policy_score_allowed",
            replay.validate_replay_contract(mutated),
        )

    def test_no_new_feature_extractor_function_is_defined_here(self):
        source = (ROOT / "phase3_r2_independent_holdout_replay.py").read_text(encoding="utf-8")
        self.assertNotIn("def _extract_research_objects", source)
        self.assertNotIn("def _extract_research_queue_d1", source)
        self.assertNotIn("def _extract_research_queue_d2_current", source)
        self.assertIn("extract_model_neutral_features", source)
        self.assertIn("transform_model_neutral_row", source)
        self.assertIn("compare_r2_profiles", source)


if __name__ == "__main__":
    unittest.main()
