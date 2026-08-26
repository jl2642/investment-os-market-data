import json
from pathlib import Path
import unittest

from strategy_kernel_v2.phase3e_ablation import build_default

ROOT = Path(__file__).resolve().parents[1]


class Phase3EAblationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((ROOT / "PHASE3E_ABLATION_CONTRACT.json").read_text(encoding="utf-8"))
        cls.result = build_default(ROOT.parent)

    def test_contract_forbids_outcome_tuning(self):
        rules = self.contract["rules"]
        corpus = self.contract["evaluation_corpus"]
        self.assertFalse(corpus["phase3d_realized_outcomes_may_select_ablation"])
        self.assertFalse(corpus["phase3d_returns_may_tune_requirements"])
        self.assertFalse(rules["proxy_substitution_allowed"])
        self.assertFalse(rules["subjective_mapping_allowed"])
        self.assertFalse(rules["winner_selection_allowed"])

    def test_exactly_one_component_removed_per_ablation(self):
        for family in ("phase2_variants", "simple_variants"):
            baseline = self.contract[family][0]
            baseline_keys = set(baseline["required_feature_keys"])
            self.assertIsNone(baseline["removed_component"])
            for variant in self.contract[family][1:]:
                self.assertIsNotNone(variant["removed_component"])
                # P2 probability ablation swaps weighted scenarios for contemporaneous
                # unweighted scenario payload rather than fabricating probabilities.
                if variant["variant_id"] == "P2_DROP_PROBABILITY":
                    self.assertNotIn("explicit_probability_scenarios", variant["required_feature_keys"])
                    self.assertIn("wp5_unweighted_scenarios", variant["required_feature_keys"])
                else:
                    self.assertEqual(len(baseline_keys) - len(set(variant["required_feature_keys"])), 1)

    def test_same_point_in_time_corpus_is_used(self):
        self.assertEqual(self.result["checkpoint_count"], 7)
        self.assertGreater(self.result["feature_security_instance_count"], 0)
        self.assertEqual(self.result["historical_source_reads"], 29)

    def test_fixed_candidates_remain_nonreplayable(self):
        self.assertEqual(self.result["phase2_ablation"][0]["evaluable_security_instance_count"], 0)
        self.assertEqual(self.result["simple_ablation"][0]["evaluable_security_instance_count"], 0)

    def test_single_component_ablation_does_not_unlock_replay(self):
        self.assertEqual(self.result["single_component_ablation_unlock_count"], 0)
        self.assertEqual(self.result["finding"], "NO_SINGLE_COMPONENT_ABLATION_RESTORES_HISTORICAL_REPLAY")
        for row in self.result["phase2_ablation"][1:] + self.result["simple_ablation"][1:]:
            self.assertEqual(row["evaluable_security_instance_count"], 0)
            self.assertEqual(row["delta_vs_fixed_baseline"], 0)

    def test_adjacent_observables_do_not_count_as_contract_inputs(self):
        adjacent = self.result["adjacent_observable_inventory"]
        self.assertTrue(any(v["security_instance_count_with_adjacent_observable"] > 0 for v in adjacent.values()))
        self.assertTrue(all(v["contract_substitution_allowed"] is False for v in adjacent.values()))
        self.assertFalse(self.result["interpretation"]["proxy_fields_count_as_contract_inputs"])

    def test_material_revision_requires_loopback(self):
        self.assertTrue(self.result["interpretation"]["material_revision_requires_loopback"])
        self.assertEqual(
            self.result["interpretation"]["loopback_target"],
            "PHASE_3B_CONTRACT_DEFINITION_THEN_PHASE_3C_REPLAY",
        )

    def test_zero_authority(self):
        controls = self.result["controls"]
        self.assertFalse(controls["candidate_mutation_allowed"])
        self.assertFalse(controls["real_position_mutation_allowed"])
        self.assertFalse(controls["simulation_position_mutation_allowed"])
        self.assertFalse(controls["user_decision_generation_allowed"])
        self.assertEqual(controls["orders"], 0)
        self.assertEqual(controls["trade_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
