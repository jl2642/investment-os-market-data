from __future__ import annotations

import json
import unittest
from pathlib import Path

from strategy_kernel_v2.phase3d_r2_measurability import (
    ROUND1_PASS,
    build_round1_evidence_audit,
    load_contract,
    validate_contract,
)

ROOT = Path(__file__).resolve().parents[1]


class Phase3DR2Round1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_contract()
        cls.result = build_round1_evidence_audit()
        cls.state = json.loads((ROOT / "PROGRAM_STATE.json").read_text(encoding="utf-8"))
        cls.current = json.loads((ROOT / "CURRENT_PHASE_STATUS.json").read_text(encoding="utf-8"))

    def test_contract_is_frozen_before_r2_outcome_acquisition(self):
        self.assertEqual(validate_contract(self.contract), [])
        self.assertFalse(self.contract["freeze_order"]["realized_outcomes_read_at_freeze"])
        self.assertFalse(self.contract["freeze_order"]["future_returns_computed_at_freeze"])
        self.assertFalse(self.contract["freeze_order"]["performance_metrics_computed_at_freeze"])

    def test_r2_outputs_are_not_rewritten_as_trades_or_portfolio(self):
        semantic = self.contract["semantic_scope"]
        self.assertTrue(semantic["dominance_edge_is_not_a_hypothetical_trade"])
        self.assertTrue(semantic["pareto_frontier_is_not_a_target_portfolio"])
        self.assertFalse(semantic["r2_output_is_portfolio_or_trade_instruction"])

        forbidden = self.contract["forbidden_metrics_or_claims"]
        self.assertTrue(forbidden["synthetic_trade_return"])
        self.assertTrue(forbidden["portfolio_return"])
        self.assertTrue(forbidden["winner_selection"])

    def test_parent_holdout_structure_is_bound_exactly(self):
        self.assertEqual(self.result["checkpoint_count"], 14)
        self.assertEqual(self.result["r2_profile_count"], 105)
        self.assertEqual(self.result["comparable_group_count"], 27)
        self.assertEqual(self.result["comparable_profile_count"], 85)
        self.assertEqual(self.result["dominance_edge_count"], 54)
        self.assertEqual(self.result["dominance_edge_count_recounted"], 54)

    def test_round1_is_outcome_blind(self):
        self.assertEqual(self.result["outcome_manifest_content_read_count"], 0)
        self.assertEqual(self.result["realized_outcome_value_read_count"], 0)
        self.assertEqual(self.result["future_return_compute_count"], 0)
        self.assertEqual(self.result["performance_metric_compute_count"], 0)
        self.assertFalse(self.result["r2_outcome_manifest_present_at_parent_freeze"])
        self.assertTrue(self.result["legacy_phase3d_outcome_manifest_present_at_parent_freeze"])
        self.assertFalse(self.result["legacy_phase3d_outcome_manifest_authorized_for_r2"])

    def test_round1_classifies_acquisition_requirement_without_calling_it_performance(self):
        self.assertEqual(self.result["status"], ROUND1_PASS)
        self.assertEqual(
            self.result["measurability_status"],
            "PENDING_OUTCOME_EVIDENCE_ACQUISITION",
        )
        self.assertEqual(
            self.result["next_step"],
            "PHASE_3D_R2_OUTCOME_EVIDENCE_ACQUISITION_UNDER_FROZEN_CONTRACT",
        )
        self.assertEqual(
            self.result["economic_performance_measurement_status"],
            "NOT_AUTHORIZED_IN_ROUND_1",
        )

    def test_downstream_authority_remains_blocked(self):
        self.assertFalse(self.result["phase3e_r2_start_allowed"])
        self.assertFalse(self.result["repeat_phase3f_start_allowed"])
        self.assertFalse(self.result["phase3_historical_validation_complete"])
        self.assertFalse(self.result["phase4_entry_allowed"])
        self.assertEqual(self.result["orders"], 0)
        self.assertEqual(self.result["trade_authority"], "NONE")

        # Before first remote acceptance, governed state remains at the parent
        # boundary. This prevents a contract freeze from masquerading as a
        # completed Phase 3D-R2 execution.
        self.assertTrue(self.state["phase3d_r2_start_allowed"])
        self.assertFalse(self.state["phase3d_r2_started"])
        self.assertFalse(self.current["validation"]["phase3d_r2_started"])


if __name__ == "__main__":
    unittest.main()
