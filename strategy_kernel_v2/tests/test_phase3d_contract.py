import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class Phase3DContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = json.loads((ROOT / "PHASE3D_EVALUATION_CONTRACT.json").read_text())
    def test_fixed_horizons(self): self.assertEqual(self.c["horizons"]["fixed_sessions"], [1,3,5])
    def test_outcomes_not_loaded_at_freeze(self): self.assertFalse(self.c["freeze_order"]["realized_outcomes_loaded_at_freeze"])
    def test_no_action_is_observation_only(self): self.assertEqual(self.c["legacy_evaluation"]["NO_ACTION_WATCH_RESEARCH"]["forward_price_return"], "OPPORTUNITY_OBSERVATION_ONLY")
    def test_candidate_phase2_unmeasurable(self): self.assertEqual(self.c["candidate_evaluation"]["PHASE2_PROBABILISTIC_VECTOR"]["regret"], "NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS")
    def test_candidate_simple_unmeasurable(self): self.assertEqual(self.c["candidate_evaluation"]["SIMPLE_NON_PROBABILISTIC_PARETO"]["regret"], "NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS")
    def test_no_winner(self): self.assertTrue(self.c["aggregation_policy"]["winner_selection_forbidden"])
    def test_no_statistics_claim(self): self.assertTrue(self.c["aggregation_policy"]["statistical_significance_claim_forbidden_on_current_bounded_corpus"])
    def test_no_authority(self): self.assertEqual(self.c["authority_boundaries"]["orders"], 0); self.assertEqual(self.c["authority_boundaries"]["trade_authority"], "NONE")

if __name__ == "__main__": unittest.main()
