import unittest
from decimal import Decimal

from strategy_kernel_v2.phase3d_r2_performance_measurement import (
    _summary,
    edge_measurement,
    endpoint_return,
    load_contract,
    validate_contract,
)


class Phase3DR2PerformanceMeasurementTests(unittest.TestCase):
    def test_contract_is_frozen_before_measurement_result(self):
        contract = load_contract()
        self.assertEqual(validate_contract(contract), [])
        self.assertFalse(
            contract["economic_interpretation_boundary"]["phase3e_r2_support_threshold_defined_here"]
        )
        self.assertTrue(
            contract["economic_interpretation_boundary"][
                "support_gate_must_be_frozen_before_using_measurement_result_to_decide_phase3e_r2"
            ]
        )

    def test_endpoint_return_formula(self):
        self.assertEqual(endpoint_return("100", "105"), Decimal("0.05"))

    def test_edge_spread_and_concordance(self):
        spread, concordant = edge_measurement(Decimal("0.03"), Decimal("0.01"))
        self.assertEqual(spread, Decimal("0.02"))
        self.assertTrue(concordant)

    def test_tie_is_concordant(self):
        spread, concordant = edge_measurement(Decimal("0.01"), Decimal("0.01"))
        self.assertEqual(spread, Decimal("0"))
        self.assertTrue(concordant)

    def test_summary_is_equal_edge_descriptive(self):
        rows = [
            {
                "edge_return_spread": "0.020000000000",
                "dominator_return": "0.030000000000",
                "dominated_return": "0.010000000000",
                "concordant": True,
            },
            {
                "edge_return_spread": "-0.010000000000",
                "dominator_return": "0.000000000000",
                "dominated_return": "0.010000000000",
                "concordant": False,
            },
        ]
        result = _summary(rows)
        self.assertEqual(result["edge_count"], 2)
        self.assertEqual(result["concordant_count"], 1)
        self.assertEqual(result["concordance_rate"], "0.500000000000")
        self.assertEqual(result["mean_edge_return_spread"], "0.005000000000")
        self.assertEqual(result["median_edge_return_spread"], "0.005000000000")


if __name__ == "__main__":
    unittest.main()
