import unittest

from strategy_kernel_v2.phase4_forward_readiness_r1 import (
    build_forward_readiness_audit,
    load_adapter,
)


class Phase4ForwardReadinessR1Tests(unittest.TestCase):
    def test_selector_contract_is_result_blind_and_canonical_main_only(self):
        c = load_adapter()
        self.assertEqual(c["status"], "FROZEN_BEFORE_P4_1_DISCOVERY_AUDIT")
        self.assertEqual(c["source_universe"]["source_branch"], "main")
        self.assertTrue(c["source_universe"]["first_parent_only"])
        self.assertFalse(c["source_universe"]["open_pr_heads_allowed"])
        self.assertFalse(c["selector_semantics"]["discretionary_subsampling_allowed"])
        self.assertFalse(c["selector_semantics"]["manual_cherry_pick_allowed"])
        self.assertFalse(c["selector_semantics"]["random_sampling_allowed"])
        self.assertFalse(c["selector_semantics"]["pre_cutoff_source_alone_may_trigger_checkpoint"])
        self.assertTrue(c["selector_semantics"]["pre_cutoff_source_may_remain_visible_as_point_in_time_context"])

    def test_round1_readiness_audit_does_not_execute_models_or_outcomes(self):
        result = build_forward_readiness_audit()
        self.assertIn(
            result["status"],
            {
                "WAITING_FOR_FIRST_POST_CUTOFF_CANONICAL_MAIN_COMMIT",
                "WAITING_FOR_ELIGIBLE_FORWARD_CHECKPOINT",
                "FORWARD_CHECKPOINTS_DISCOVERED_READY_FOR_PARALLEL_REPLAY",
            },
        )
        self.assertEqual(result["legacy_runner_execution_count"], 0)
        self.assertEqual(result["r2_profile_compute_count"], 0)
        self.assertEqual(result["r2_pareto_compute_count"], 0)
        self.assertEqual(result["realized_outcome_read_count"], 0)
        self.assertEqual(result["future_return_read_count"], 0)
        self.assertFalse(result["phase4_started"])
        self.assertEqual(result["controls"]["orders"], 0)
        self.assertEqual(result["controls"]["trade_authority"], "NONE")

    def test_frozen_as_of_main_head_is_pre_cutoff_in_round1_snapshot(self):
        result = build_forward_readiness_audit()
        self.assertEqual(result["as_of_protected_main_head"], "5c5df9082688f65332c79fef3b9cbfa893a06908")
        self.assertEqual(result["as_of_protected_main_head_commit_time_utc"], "2026-08-18T01:46:25+00:00")
        self.assertEqual(result["frozen_cutoff_utc"], "2026-08-27T13:42:29Z")
        self.assertEqual(result["post_cutoff_first_parent_commit_count"], 0)
        self.assertEqual(result["selected_forward_checkpoint_count"], 0)
        self.assertEqual(result["status"], "WAITING_FOR_FIRST_POST_CUTOFF_CANONICAL_MAIN_COMMIT")


if __name__ == "__main__":
    unittest.main()
