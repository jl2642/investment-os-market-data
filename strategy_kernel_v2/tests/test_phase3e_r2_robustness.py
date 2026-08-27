import unittest

from strategy_kernel_v2.phase3e_r2_robustness import (
    _axis_range,
    _cluster_weighted_summary,
    _edge_summary,
    load_contract,
    validate_contract,
)


class Phase3ER2RobustnessTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {
                "edge_id": "E1",
                "checkpoint_id": "C1",
                "comparison_signature_sha256": "S1",
                "dominator_security_id": "A",
                "dominated_security_id": "B",
                "horizon_sessions": 1,
                "dominator_return": "0.030000000000",
                "dominated_return": "0.010000000000",
                "edge_return_spread": "0.020000000000",
                "concordant": True,
            },
            {
                "edge_id": "E2",
                "checkpoint_id": "C2",
                "comparison_signature_sha256": "S2",
                "dominator_security_id": "C",
                "dominated_security_id": "D",
                "horizon_sessions": 1,
                "dominator_return": "0.000000000000",
                "dominated_return": "0.010000000000",
                "edge_return_spread": "-0.010000000000",
                "concordant": False,
            },
        ]

    def test_contract_reuses_exact_frozen_plan(self):
        contract = load_contract()
        self.assertEqual(validate_contract(contract), [])
        self.assertTrue(contract["execution_plan"]["one_axis_at_a_time"])
        self.assertFalse(contract["execution_plan"]["new_test_axes_allowed"])
        self.assertFalse(contract["execution_plan"]["result_driven_subset_selection_allowed"])

    def test_equal_edge_summary(self):
        summary = _edge_summary(self.rows)
        self.assertEqual(summary["distinct_edge_count"], 2)
        self.assertEqual(summary["concordance_rate"], "0.500000000000")
        self.assertEqual(summary["mean_edge_return_spread"], "0.005000000000")

    def test_equal_checkpoint_summary(self):
        summary = _cluster_weighted_summary(self.rows, "checkpoint_id")
        self.assertEqual(summary["cluster_count"], 2)
        self.assertEqual(summary["concordance_rate"], "0.500000000000")
        self.assertEqual(summary["mean_edge_return_spread"], "0.005000000000")

    def test_axis_range_is_descriptive_only(self):
        records = [
            {"summary": {"concordance_rate": "0.40", "mean_edge_return_spread": "-0.01"}},
            {"summary": {"concordance_rate": "0.60", "mean_edge_return_spread": "0.02"}},
        ]
        result = _axis_range(records)
        self.assertEqual(result["min_concordance_rate"], "0.400000000000")
        self.assertEqual(result["max_concordance_rate"], "0.600000000000")
        self.assertEqual(result["min_mean_edge_return_spread"], "-0.010000000000")
        self.assertEqual(result["max_mean_edge_return_spread"], "0.020000000000")


if __name__ == "__main__":
    unittest.main()
