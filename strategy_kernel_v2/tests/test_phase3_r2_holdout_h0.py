from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class Phase3R2HoldoutH0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load("PHASE3_R2_HOLDOUT_SELECTION_CONTRACT.json")
        cls.state = load("PROGRAM_STATE.json")
        cls.current = load("CURRENT_PHASE_STATUS.json")

    def test_identity_and_parent_are_frozen(self):
        c = self.contract
        self.assertEqual(c["status"], "FROZEN_BEFORE_HOLDOUT_SELECTION_OR_R2_REPLAY")
        self.assertEqual(c["model_form"], "EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2")
        self.assertEqual(c["model_version"], "R2.0.1_RESEARCH")
        self.assertEqual(c["parent_program_plan_sync_pr"], 319)
        self.assertEqual(c["parent_r2b_pr"], 318)
        self.assertFalse(c["holdout_identity"]["holdout_is_macro_phase"])
        self.assertFalse(c["holdout_identity"]["holdout_is_phase3g"])
        self.assertFalse(c["holdout_identity"]["holdout_is_direct_phase4_gate"])

    def test_repository_universe_is_fixed_before_selection(self):
        u = self.contract["frozen_repository_universe"]
        self.assertEqual(u["source_branch"], "main")
        self.assertTrue(u["source_branch_must_be_protected"])
        self.assertFalse(u["open_pr_heads_allowed"])
        self.assertEqual(u["start_commit_inclusive"], "6323f4c0617b3df3907b4e76c36b441d666fc4b0")
        self.assertEqual(u["end_commit_inclusive"], "5c5df9082688f65332c79fef3b9cbfa893a06908")
        self.assertFalse(u["future_commits_may_enter_v1_holdout"])
        self.assertTrue(u["universe_extension_requires_new_version_and_pre_result_contract_amendment"])

    def test_seed_firewall_is_exact_and_non_relabelable(self):
        s = self.contract["seed_firewall"]
        self.assertEqual(len(s["excluded_checkpoint_ids"]), 7)
        self.assertEqual(len(s["excluded_commit_shas"]), 7)
        self.assertTrue(s["exact_seed_commit_reuse_forbidden"])
        self.assertTrue(s["exact_seed_source_identity_set_reuse_forbidden"])
        self.assertTrue(s["seed_checkpoint_relabeling_forbidden"])
        self.assertTrue(s["same_seed_outcome_tuning_as_holdout_forbidden"])

    def test_selector_is_census_not_cherry_pick(self):
        s = self.contract["deterministic_selector"]
        self.assertEqual(s["mode"], "CENSUS_OF_ALL_ELIGIBLE_DISTINCT_DECISION_EVIDENCE_FINGERPRINTS")
        self.assertTrue(s["all_eligible_distinct_fingerprints_must_be_selected"])
        self.assertFalse(s["discretionary_subsampling_allowed"])
        self.assertFalse(s["random_sampling_allowed"])
        self.assertFalse(s["manual_cherry_pick_allowed"])
        self.assertTrue(s["regime_definition_may_not_use_prices_returns_or_outcomes"])

    def test_outcomes_and_r2_results_cannot_influence_selection(self):
        f = self.contract["outcome_and_model_firewall"]
        forbidden_true = [
            "realized_outcomes_may_be_read_during_selection",
            "phase3d_results_may_be_read_during_selection",
            "r2_profile_values_may_be_computed_during_selection",
            "r2_pareto_replay_may_run_during_selection",
            "r2_replayability_status_may_influence_selection",
            "future_return_may_influence_selection",
            "regret_or_calibration_may_influence_selection",
            "manual_include_or_exclude_based_on_expected_model_behavior",
        ]
        for key in forbidden_true:
            self.assertFalse(f[key], key)
        self.assertTrue(f["selector_changes_after_first_holdout_r2_result_forbidden"])

    def test_sufficiency_gate_is_quantitative_and_multi_axis(self):
        q = self.contract["quantitative_sufficiency_gate"]
        self.assertEqual(q["minimum_holdout_checkpoints"], 12)
        self.assertEqual(q["minimum_distinct_utc_dates"], 6)
        self.assertEqual(q["minimum_distinct_iso_weeks"], 4)
        self.assertEqual(q["minimum_distinct_evidence_regime_signatures"], 4)
        self.assertEqual(q["minimum_unique_securities"], 6)
        self.assertEqual(q["minimum_opportunity_profile_instances"], 48)
        self.assertEqual(q["minimum_checkpoints_strictly_outside_seed_time_span"], 2)
        self.assertLessEqual(q["maximum_single_utc_date_fraction"], 0.40)
        self.assertLessEqual(q["maximum_single_evidence_regime_fraction"], 0.50)
        self.assertTrue(q["all_thresholds_must_pass"])
        self.assertTrue(q["threshold_change_after_holdout_selection_or_replay_result_forbidden"])

    def test_downstream_sequence_preserves_d_r2_e_r2_and_repeat_3f(self):
        self.assertEqual(
            self.contract["downstream_sequence"],
            [
                "H1_HOLDOUT_CANDIDATE_LEDGER_BUILD_AND_SELECTION_ACCEPTANCE",
                "H2_FROZEN_R2_REPLAY_ON_ACCEPTED_HOLDOUT",
                "H3_HOLDOUT_COVERAGE_AND_REPLAY_FINAL_ACCEPTANCE",
                "PHASE_3D_R2_MEASURABILITY_AND_PERFORMANCE_IF_SUPPORTED",
                "PHASE_3E_R2_ROBUSTNESS_IF_SUPPORTED",
                "REPEAT_PHASE_3F_HISTORICAL_PROMOTION_GATE",
            ],
        )

    def test_authority_is_zero(self):
        a = self.contract["authority_boundaries"]
        for key in [
            "effective_core_static_changes",
            "candidate_membership_mutations",
            "real_account_mutations",
            "simulation_mutations",
            "target_portfolio_writebacks",
            "user_decisions_generated",
            "investment_recommendations_generated",
            "orders",
        ]:
            self.assertEqual(a[key], 0)
        self.assertEqual(a["trade_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
