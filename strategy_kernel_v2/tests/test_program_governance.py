import unittest
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from strategy_kernel_v2.program_consistency import validate_program_consistency


class ProgramGovernanceTest(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((ROOT / "PROGRAM_CONTRACT.json").read_text())
        self.state = json.loads((ROOT / "PROGRAM_STATE.json").read_text())
        self.current = json.loads((ROOT / "CURRENT_PHASE_STATUS.json").read_text())
        self.roadmap = (ROOT / "DEVELOPMENT_ROADMAP.md").read_text()
        self.execution = (ROOT / "PHASE_EXECUTION_PLAN.md").read_text()
        self.changelog = (ROOT / "PLAN_CHANGELOG.md").read_text()

    def test_consistency(self):
        self.assertEqual(validate_program_consistency(), [])

    def test_lifecycle(self):
        self.assertEqual([x["phase"] for x in self.contract["macro_lifecycle"]], [0, 1, 2, 3, 4, 5])

    def test_all_mandatory_gates_true(self):
        gates = self.contract["mandatory_gates"]
        self.assertTrue(gates["phase3_historical_validation_required_for_phase4"])
        self.assertTrue(gates["phase4_forward_validation_required_for_phase5"])
        self.assertTrue(gates["direct_phase3_to_phase5_forbidden"])
        self.assertTrue(gates["macro_phase_omission_forbidden"])
        self.assertTrue(gates["program_amendment_required_for_macro_change"])

    def test_phase4_required(self):
        self.assertTrue(self.contract["mandatory_gates"]["phase4_forward_validation_required_for_phase5"])
        self.assertTrue(self.state["phase4_required"])

    def test_direct_3_5_forbidden(self):
        self.assertTrue(self.contract["mandatory_gates"]["direct_phase3_to_phase5_forbidden"])
        self.assertFalse(self.state["direct_phase3_to_phase5_allowed"])

    def test_phase5_not_authorized(self):
        self.assertFalse(self.state["phase5_migration_allowed"])

    def test_phase3_not_started(self):
        self.assertFalse(self.state["phase3_implementation_started"])
        self.assertEqual(self.state["macro_phase"], 2)

    def test_contract_promotion_edge_matches_state(self):
        lifecycle = {item["phase"]: item for item in self.contract["macro_lifecycle"]}
        self.assertEqual(
            self.state["next_macro_phase"],
            lifecycle[self.state["macro_phase"]]["promotion_target"],
        )

    def test_state_and_current_status_lockstep(self):
        self.assertEqual(self.current["current_macro_phase"], self.state["macro_phase"])
        self.assertEqual(self.current["next_macro_phase"], self.state["next_macro_phase"])
        self.assertEqual(self.current["phase4_required"], self.state["phase4_required"])
        self.assertEqual(self.current["phase5_migration_allowed"], self.state["phase5_migration_allowed"])
        self.assertEqual(
            self.current["direct_phase3_to_phase5_allowed"],
            self.state["direct_phase3_to_phase5_allowed"],
        )
        self.assertEqual(
            self.current["phase3_implementation_started"],
            self.state["phase3_implementation_started"],
        )

    def test_roadmap_phase4(self):
        self.assertIn("Phase 4", self.roadmap)
        self.assertIn("Forward Parallel Shadow", self.roadmap)

    def test_execution_exit_guard(self):
        self.assertIn("PROMOTE_TO_PHASE_4_FORWARD_VALIDATION", self.execution)
        self.assertIn("`PROMOTE_TO_PHASE_5` is forbidden", self.execution)

    def test_changelog_records_roadmap_drift(self):
        self.assertTrue(self.state["roadmap_drift_detected_and_corrected"])
        self.assertIn("ROADMAP_DRIFT_CORRECTION", self.changelog)
        self.assertIn("Phase 4", self.changelog)
        self.assertIn("Phase 3", self.changelog)

    def test_zero_economic_mutations(self):
        for key in [
            "effective_core_static_changes",
            "candidate_membership_mutations",
            "real_account_mutations",
            "simulation_mutations",
            "target_portfolio_writebacks",
            "user_decisions_generated",
        ]:
            self.assertEqual(self.state[key], 0)
            self.assertEqual(self.current[key], 0)

    def test_trade_none(self):
        self.assertEqual(self.contract["authority_boundaries_through_phase4"]["orders"], 0)
        self.assertEqual(self.contract["authority_boundaries_through_phase4"]["trade_authority"], "NONE")
        self.assertEqual(self.state["orders"], 0)
        self.assertEqual(self.state["trade_authority"], "NONE")
        self.assertEqual(self.current["orders"], 0)
        self.assertEqual(self.current["trade_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
