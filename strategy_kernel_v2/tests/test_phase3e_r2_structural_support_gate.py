import inspect
import unittest

import strategy_kernel_v2.phase3e_r2_structural_support_gate as gate
from strategy_kernel_v2.phase3e_r2_structural_support_gate import load_contract, validate_contract


class Phase3ER2StructuralSupportGateTests(unittest.TestCase):
    def test_contract_is_result_value_blind(self):
        contract = load_contract()
        self.assertEqual(validate_contract(contract), [])
        firewall = contract["result_value_firewall"]
        self.assertFalse(firewall["concordance_rates_may_be_read_by_gate"])
        self.assertFalse(firewall["edge_spread_values_may_be_read_by_gate"])
        self.assertFalse(firewall["endpoint_return_values_may_be_read_by_gate"])
        self.assertFalse(firewall["post_result_numeric_threshold_may_be_created"])

    def test_gate_source_does_not_reference_observed_performance_value_fields(self):
        source = inspect.getsource(gate)
        forbidden = [
            "phase3d_r2_h1_concordance_rate",
            "phase3d_r2_h3_concordance_rate",
            "phase3d_r2_h5_concordance_rate",
            "phase3d_r2_pooled_concordance_rate",
            "phase3d_r2_h1_mean_edge_return_spread",
            "phase3d_r2_h3_mean_edge_return_spread",
            "phase3d_r2_h5_mean_edge_return_spread",
            "phase3d_r2_pooled_mean_edge_return_spread",
        ]
        for field in forbidden:
            self.assertNotIn(field, source)

    def test_five_predeclared_robustness_axes(self):
        contract = load_contract()
        tests = contract["predefined_robustness_plan"]["tests"]
        self.assertEqual(len(tests), 5)
        self.assertTrue(contract["predefined_robustness_plan"]["one_axis_at_a_time"])
        self.assertFalse(contract["predefined_robustness_plan"]["simultaneous_multi_axis_search_allowed"])
        self.assertFalse(contract["predefined_robustness_plan"]["result_driven_subset_selection_allowed"])

    def test_support_gate_is_structural_only(self):
        result = gate.build_structural_support_gate()
        self.assertEqual(result["result_value_reads_for_gate_decision"], 0)
        self.assertEqual(result["post_result_numeric_thresholds_created"], 0)
        self.assertFalse(result["economic_performance_support_claimed"])
        self.assertFalse(result["model_robustness_claimed"])
        self.assertFalse(result["phase4_promotion_claimed"])

    def test_current_structure_supports_all_axes(self):
        result = gate.build_structural_support_gate()
        self.assertEqual(result["status"], "PASS_R2_STRUCTURAL_SUPPORT_FOR_ROBUSTNESS")
        self.assertTrue(result["phase3e_r2_structurally_supported"])
        self.assertTrue(result["phase3e_r2_robustness_execution_authorized"])
        self.assertEqual(sum(row["structurally_evaluable"] for row in result["robustness_axis_feasibility"]), 5)


if __name__ == "__main__":
    unittest.main()
