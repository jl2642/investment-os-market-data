import json
import unittest
from pathlib import Path

from strategy_kernel_v2.validate_post3c_evaluation_path import validate

ROOT = Path(__file__).resolve().parents[1]


class Post3CEvaluationPathTest(unittest.TestCase):
    def setUp(self):
        self.decision = json.loads((ROOT / "PHASE3_POST3C_EVALUATION_PATH_DECISION.json").read_text())
        self.state = json.loads((ROOT / "PROGRAM_STATE.json").read_text())
        self.current = json.loads((ROOT / "CURRENT_PHASE_STATUS.json").read_text())

    def test_full_validator(self):
        self.assertEqual(validate(), [])

    def test_phase3_sequence_unchanged(self):
        self.assertEqual(self.decision["phase3_subphase_sequence_unchanged"], ["3A", "3B", "3C", "3D", "3E", "3F"])

    def test_macro_lifecycle_unchanged(self):
        self.assertTrue(self.decision["macro_lifecycle_unchanged"])

    def test_unsafe_paths_rejected(self):
        alternatives = {row["id"]: row["decision"] for row in self.decision["alternatives"]}
        self.assertEqual(alternatives["RETROSPECTIVE_INPUT_SYNTHESIS"], "REJECTED")
        self.assertEqual(alternatives["SILENT_PHASE3B_CONTRACT_REWRITE"], "REJECTED")
        self.assertEqual(alternatives["SKIP_PHASE3D_TO_PHASE3E"], "REJECTED")

    def test_negative_result_path_approved(self):
        alternatives = {row["id"]: row["decision"] for row in self.decision["alternatives"]}
        self.assertEqual(alternatives["PHASE3D_NEGATIVE_RESULT_MEASURABILITY_PATH"], "APPROVED")

    def test_candidate_metrics_fail_closed(self):
        rules = self.decision["approved_path"]["phase3d_rules"]
        self.assertEqual(rules["candidate_metrics_without_contemporaneous_outputs"], "NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS")
        self.assertTrue(rules["hypothetical_candidate_decisions_forbidden"])
        self.assertTrue(rules["retrospective_candidate_output_generation_forbidden"])

    def test_phase3d_ready_not_started(self):
        self.assertTrue(self.state["phase3d_start_allowed"])
        self.assertFalse(self.state["phase3d_started"])
        self.assertTrue(self.current["validation"]["phase3d_start_allowed"])
        self.assertFalse(self.current["validation"]["phase3d_started"])

    def test_phase3e_revised_forms_loop_back(self):
        rules = self.decision["approved_path"]["phase3e_rules"]
        self.assertTrue(rules["revised_model_forms_must_be_versioned_new_forms"])
        self.assertTrue(rules["revised_forms_require_return_to_phase3b_and_phase3c_before_any_phase3f_promotion"])
        self.assertTrue(rules["broader_or_holdout_historical_validation_required_for_revised_forms"])

    def test_phase3f_still_blocked(self):
        self.assertFalse(self.state["phase3f_promotion_eligible"])
        self.assertFalse(self.current["validation"]["phase3f_promotion_eligible"])

    def test_zero_authority(self):
        self.assertEqual(self.state["orders"], 0)
        self.assertEqual(self.state["trade_authority"], "NONE")
        self.assertEqual(self.current["orders"], 0)
        self.assertEqual(self.current["trade_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
