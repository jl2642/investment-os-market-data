import json
import unittest
from pathlib import Path

from strategy_kernel_v2.phase3d_r2_measurability import (
    build_measurability_audit,
    load_contract,
    validate_contract,
)

ROOT = Path(__file__).resolve().parents[1]


class Phase3DR2MeasurabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_contract()
        cls.audit = build_measurability_audit()

    def test_contract_is_frozen_before_performance(self):
        self.assertEqual(validate_contract(self.contract), [])
        self.assertEqual(
            self.contract["status"],
            "FROZEN_BEFORE_R2_OUTCOME_PERFORMANCE_CALCULATION",
        )
        self.assertFalse(
            self.contract["preexisting_governed_outcome_inventory"]["round1_return_calculation_allowed"]
        )

    def test_parent_holdout_is_bound_exactly(self):
        parent = self.contract["parent_holdout"]
        self.assertEqual(self.audit["parent_holdout_replay_sha256"], parent["replay_sha256"])
        self.assertEqual(self.audit["checkpoint_count"], 14)
        self.assertEqual(self.audit["frozen_dominance_edge_count"], 54)

    def test_edge_population_is_structurally_measurable(self):
        self.assertTrue(self.audit["structurally_measurable"])
        self.assertGreater(self.audit["required_edge_endpoint_instances"], 0)
        self.assertGreater(self.audit["required_edge_endpoint_security_count"], 0)

    def test_round1_does_not_calculate_performance(self):
        controls = self.audit["controls"]
        self.assertEqual(controls["return_calculation_count"], 0)
        self.assertEqual(controls["performance_metric_count"], 0)
        self.assertEqual(controls["portfolio_pnl_count"], 0)
        self.assertEqual(controls["external_outcome_fetch_count"], 0)

    def test_fail_closed_readiness_gate(self):
        if self.audit["complete_outcome_evidence_ready"]:
            self.assertEqual(
                self.audit["status"],
                "PASS_R2_MEASURABILITY_EVIDENCE_READY_FOR_PERFORMANCE",
            )
            self.assertTrue(self.audit["performance_calculation_authorized"])
        else:
            self.assertEqual(
                self.audit["status"],
                "PARTIAL_R2_MEASURABILITY_OUTCOME_EVIDENCE_ACQUISITION_REQUIRED",
            )
            self.assertFalse(self.audit["performance_calculation_authorized"])

    def test_partial_is_not_underperformance(self):
        self.assertFalse(self.audit["partial_result_is_economic_underperformance"])
        self.assertFalse(self.audit["not_measurable_result_is_economic_underperformance"])

    def test_round1_preserves_downstream_blocks(self):
        self.assertFalse(self.audit["phase3d_r2_governed_state_started"])
        self.assertFalse(self.audit["phase3d_r2_performance_started"])
        self.assertFalse(self.audit["phase3e_r2_started"])
        self.assertFalse(self.audit["repeat_phase3f_started"])
        self.assertFalse(self.audit["phase4_entry_allowed"])
        self.assertEqual(self.audit["controls"]["orders"], 0)
        self.assertEqual(self.audit["controls"]["trade_authority"], "NONE")

    def test_audit_is_deterministic(self):
        again = build_measurability_audit()
        self.assertEqual(self.audit, again)
        self.assertEqual(self.audit["audit_sha256"], again["audit_sha256"])


if __name__ == "__main__":
    unittest.main()
