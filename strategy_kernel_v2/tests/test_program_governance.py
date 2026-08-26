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
        self.roadmap = (ROOT / "DEVELOPMENT_ROADMAP.md").read_text()
        self.execution = (ROOT / "PHASE_EXECUTION_PLAN.md").read_text()

    def test_consistency(self):
        self.assertEqual(validate_program_consistency(), [])

    def test_lifecycle(self):
        self.assertEqual([x["phase"] for x in self.contract["macro_lifecycle"]], [0, 1, 2, 3, 4, 5])

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

    def test_roadmap_phase4(self):
        self.assertIn("Phase 4", self.roadmap)
        self.assertIn("Forward Parallel Shadow", self.roadmap)

    def test_execution_exit_guard(self):
        self.assertIn("PROMOTE_TO_PHASE_4_FORWARD_VALIDATION", self.execution)
        self.assertIn("`PROMOTE_TO_PHASE_5` is forbidden", self.execution)

    def test_trade_none(self):
        self.assertEqual(self.contract["authority_boundaries_through_phase4"]["orders"], 0)
        self.assertEqual(self.contract["authority_boundaries_through_phase4"]["trade_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
