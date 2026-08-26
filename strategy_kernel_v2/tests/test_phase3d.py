import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(n): return json.loads((ROOT/n).read_text())

class Phase3DCloseoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v=load('PHASE3D_VALIDATION.json'); cls.s=load('PROGRAM_STATE.json'); cls.c=load('CURRENT_PHASE_STATUS.json'); cls.m=load('PHASE3D_OUTCOME_SOURCE_MANIFEST.json')
    def test_complete(self): self.assertTrue(self.s['phase3d_complete']); self.assertTrue(self.s['phase3d_outcomes_loaded'])
    def test_phase3e_only_next(self): self.assertTrue(self.s['phase3e_start_allowed']); self.assertFalse(self.s['phase3e_started']); self.assertFalse(self.s['phase3f_promotion_eligible'])
    def test_horizons_unchanged(self): self.assertEqual(self.v['contract']['fixed_horizons_trading_sessions'],[1,3,5]); self.assertEqual(self.v['contract']['horizon_change_count_after_outcome_loading'],0)
    def test_candidate_nonmeasurable(self): self.assertEqual(self.v['candidate_measurability']['phase2_probabilistic_vector'],'NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS'); self.assertEqual(self.v['candidate_measurability']['simple_non_probabilistic_pareto'],'NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS')
    def test_no_comparative_performance(self): self.assertFalse(self.v['candidate_measurability']['candidate_comparative_performance_available']); self.assertFalse(self.v['interpretation']['legacy_winner_conclusion']); self.assertFalse(self.v['interpretation']['candidate_winner_conclusion'])
    def test_counts(self): self.assertEqual(self.v['realized_outcome_build']['legacy_instance_count'],29); self.assertEqual(self.v['legacy_measurability']['retained_forward_price_instances'],5); self.assertEqual(self.v['realized_outcome_build']['candidate_security_model_checkpoint_count'],100)
    def test_no_regret_or_calibration(self): self.assertEqual(self.v['legacy_measurability']['measurable_regret_instances'],0); self.assertEqual(self.v['legacy_measurability']['measurable_calibration_instances'],0)
    def test_no_authority(self): self.assertEqual(self.v['authority_boundaries']['orders'],0); self.assertEqual(self.v['authority_boundaries']['trade_authority'],'NONE')

if __name__=='__main__': unittest.main()
