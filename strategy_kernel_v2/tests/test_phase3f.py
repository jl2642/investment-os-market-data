import json
import unittest
from pathlib import Path

from strategy_kernel_v2.historical_promotion_gate import evaluate_phase3f

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class Phase3FPromotionGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = evaluate_phase3f()
        cls.contract = load("PHASE3F_PROMOTION_GATE_CONTRACT.json")

    def test_contract_frozen(self):
        self.assertEqual(self.contract["status"], "FROZEN_HISTORICAL_PROMOTION_GATE")

    def test_four_mandatory_requirements(self):
        self.assertEqual(len(self.result["requirements"]), 4)
        self.assertEqual(self.result["promotion_requirement_total_count"], 4)

    def test_current_requirement_vector(self):
        r = self.result["requirements"]
        self.assertFalse(r["candidate_point_in_time_historical_replay"]["passed"])
        self.assertFalse(r["candidate_phase3d_evidence_measurable"]["passed"])
        self.assertTrue(r["phase3e_robustness_accepted"]["passed"])
        self.assertFalse(r["broader_historical_coverage"]["passed"])
        self.assertEqual(self.result["promotion_requirement_pass_count"], 1)

    def test_promotion_blocked(self):
        self.assertFalse(self.result["all_promotion_requirements_pass"])
        self.assertFalse(self.result["required_research_path"]["phase4_entry_allowed"])

    def test_no_terminal_economic_rejection_claim(self):
        self.assertFalse(self.result["terminal_rejection_evidence"])
        self.assertFalse(self.result["economic_rejection_conclusion_available"])

    def test_gate_outcome_continue_shadow_research(self):
        self.assertEqual(self.result["gate_outcome"], "CONTINUE_SHADOW_RESEARCH")
        self.assertEqual(self.result["current_fixed_candidate_forms_status"], "NOT_PROMOTABLE_IN_CURRENT_FORM")

    def test_revision_loopback_guard(self):
        p = self.result["required_research_path"]
        self.assertTrue(p["new_model_identity_for_material_revision"])
        self.assertEqual(p["loopback"], "PHASE_3B_CONTRACT_DEFINITION_THEN_PHASE_3C_REPLAY")
        self.assertTrue(p["broader_or_holdout_history_required"])

    def test_no_authority(self):
        c = self.result["controls"]
        for key in [
            "retrospective_inputs_created",
            "effective_core_static_changes",
            "candidate_membership_mutations",
            "real_account_mutations",
            "simulation_mutations",
            "target_portfolio_writebacks",
            "user_decisions_generated",
            "orders",
        ]:
            self.assertEqual(c[key], 0)
        self.assertFalse(c["fixed_phase3b_models_overwritten"])
        self.assertFalse(c["same_seed_tuning_counted_as_independent_validation"])
        self.assertFalse(c["winner_selected"])
        self.assertEqual(c["trade_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
