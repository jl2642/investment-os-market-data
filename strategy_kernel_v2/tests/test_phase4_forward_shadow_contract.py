import unittest

from strategy_kernel_v2.validate_phase4_forward_shadow_contract import (
    load_contract,
    validate_contract,
)


class Phase4ForwardShadowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_contract()

    def test_contract_is_pre_execution_and_parent_is_repeat3f_pass(self):
        c = self.contract
        self.assertEqual(c["status"], "CANDIDATE_FORWARD_SHADOW_CONTRACT_PRE_EXECUTION")
        self.assertEqual(c["parent_repeat_phase3f"]["promotion_requirement_pass_count"], 4)
        self.assertEqual(c["parent_repeat_phase3f"]["promotion_requirement_total_count"], 4)
        self.assertEqual(c["parent_repeat_phase3f"]["gate_outcome"], "PROMOTE_TO_PHASE_4_FORWARD_VALIDATION")
        self.assertFalse(c["candidate_state_boundary"]["phase4_started"])
        self.assertEqual(c["candidate_state_boundary"]["phase4_forward_observation_count"], 0)
        self.assertEqual(c["candidate_state_boundary"]["phase4_realized_outcome_read_count"], 0)

    def test_future_firewall_forbids_history_and_result_driven_selection(self):
        f = self.contract["future_evidence_firewall"]
        self.assertFalse(f["pre_freeze_evidence_may_count_as_phase4"])
        self.assertFalse(f["historical_replay_may_substitute_for_phase4"])
        self.assertFalse(f["future_checkpoint_selection_may_use_realized_outcomes"])
        self.assertFalse(f["future_checkpoint_selection_may_use_r2_result_values"])
        self.assertFalse(f["future_checkpoint_selection_may_use_legacy_result_values"])
        self.assertEqual(f["selector"], "CENSUS_OF_ALL_ELIGIBLE_SUBSTANTIVE_FORWARD_DECISION_EVIDENCE_CHECKPOINTS")

    def test_runner_and_measurement_semantics_are_frozen(self):
        c = self.contract
        self.assertEqual(c["runner_set"]["legacy"]["model_form"], "LEGACY_POLICY_BASELINE")
        self.assertEqual(c["runner_set"]["candidate"]["model_version"], "R2.0.1_RESEARCH")
        self.assertEqual(c["economic_measurement_contract"]["fixed_horizon_exchange_trading_sessions"], [1, 3, 5])
        self.assertEqual(c["mandatory_forward_summaries"]["aggregation_schemes"], ["EQUAL_EDGE", "EQUAL_CHECKPOINT", "EQUAL_SIGNATURE"])
        self.assertTrue(c["mandatory_forward_summaries"]["leave_one_security_out_required"])
        self.assertTrue(c["mandatory_forward_summaries"]["leave_one_signature_out_required"])

    def test_phase4_gate_is_predeclared_and_does_not_auto_migrate(self):
        g = self.contract["phase4_to_phase5_gate"]
        d = g["directional_requirements"]
        self.assertEqual(d["minimum_concordance_rate"], 0.5)
        self.assertEqual(d["minimum_mean_edge_return_spread"], 0.0)
        self.assertTrue(d["apply_to_every_fixed_horizon"])
        self.assertTrue(d["apply_to_every_aggregation_scheme"])
        self.assertTrue(g["pass_does_not_authorize_migration"])
        self.assertTrue(g["pass_only_authorizes_separate_phase5_migration_proposal"])

    def test_static_contract_validation(self):
        self.assertEqual(validate_contract(self.contract), [])


if __name__ == "__main__":
    unittest.main()
