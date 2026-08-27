import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class Post3FResearchPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.decision = load("PHASE3_POST3F_RESEARCH_PATH_DECISION.json")
        cls.state = load("PROGRAM_STATE.json")
        cls.current = load("CURRENT_PHASE_STATUS.json")

    def test_phase3f_negative_gate_is_preserved(self):
        trigger = self.decision["trigger"]
        self.assertEqual(trigger["phase3f_gate_outcome"], "CONTINUE_SHADOW_RESEARCH")
        self.assertEqual(trigger["promotion_requirements_passed"], 1)
        self.assertEqual(trigger["promotion_requirements_total"], 4)
        self.assertFalse(trigger["terminal_rejection_evidence"])
        self.assertFalse(trigger["phase4_entry_allowed"])

    def test_approved_path_is_dual_track(self):
        alternatives = {row["id"]: row["decision"] for row in self.decision["alternatives"]}
        self.assertEqual(alternatives["NEW_IDENTITY_EVIDENCE_NATIVE_R2_PLUS_INDEPENDENT_HOLDOUT_EXPANSION"], "APPROVED")
        self.assertEqual(alternatives["HISTORY_EXPANSION_ONLY_FIRST"], "REJECTED_AS_PRIMARY_PATH")
        self.assertEqual(alternatives["MODEL_REDESIGN_ONLY_WITHOUT_HOLDOUT"], "REJECTED_AS_PROMOTION_PATH")
        self.assertEqual(alternatives["RETROSPECTIVE_PROXY_SUBSTITUTION_OR_OUTCOME_TUNING"], "REJECTED")

    def test_r2_design_has_no_hindsight_or_scalar_score(self):
        r2 = self.decision["r2_architecture_direction"]
        self.assertTrue(r2["new_model_identity_required_before_execution"])
        self.assertFalse(r2["probability_required_as_universal_input"])
        self.assertFalse(r2["scalar_policy_score_allowed"])
        self.assertFalse(r2["silent_proxy_substitution_allowed"])
        self.assertFalse(r2["subjective_mapping_allowed"])
        self.assertFalse(r2["retrospective_probability_creation_allowed"])
        self.assertFalse(r2["realized_outcome_tuning_allowed"])
        self.assertTrue(r2["missingness_must_remain_explicit"])

    def test_fixed_phase3b_forms_are_preserved(self):
        r2 = self.decision["r2_architecture_direction"]
        self.assertTrue(r2["fixed_phase3b_forms_preserved_for_audit"])
        self.assertIn("PRESERVE", r2["phase2_probabilistic_vector_treatment"])
        self.assertIn("PRESERVE", r2["simple_pareto_v1_treatment"])

    def test_seed_corpus_cannot_be_holdout(self):
        firewall = self.decision["development_corpus_firewall"]
        self.assertTrue(firewall["seven_seed_checkpoints_may_inform_contract_design"])
        self.assertFalse(firewall["phase3d_realized_outcomes_may_inform_contract_design"])
        self.assertFalse(firewall["seven_seed_checkpoints_may_count_as_independent_holdout"])
        self.assertFalse(firewall["same_seed_tuning_may_count_as_validation"])
        self.assertTrue(firewall["all_r2_transforms_must_be_frozen_before_any_claimed_holdout_evaluation"])

    def test_holdout_contract_is_point_in_time_and_outcome_blind(self):
        holdout = self.decision["holdout_coverage_contract_requirements"]
        self.assertTrue(holdout["disjoint_from_seven_seed_checkpoints"])
        self.assertFalse(holdout["checkpoint_selection_may_use_realized_outcomes"])
        self.assertTrue(holdout["point_in_time_availability_provenance_required"])
        self.assertTrue(holdout["exact_source_identity_required"])
        self.assertTrue(holdout["later_evidence_backfill_forbidden"])
        self.assertTrue(holdout["quantitative_sufficiency_threshold_must_be_frozen_before_holdout_results"])

    def test_state_and_current_are_synchronized(self):
        self.assertTrue(self.state["post3f_research_path_decision_complete"])
        self.assertEqual(self.state["post3f_research_path"], self.current["validation"]["post3f_research_path"])
        self.assertEqual(self.state["r2_working_architecture_identity"], self.current["validation"]["r2_working_architecture_identity"])
        self.assertTrue(self.state["r2_phase3b_contract_definition_start_allowed"])

        phase = self.current["current_phase"]
        if phase == "POST_PHASE3F_RESEARCH_PATH_DECISION":
            self.assertFalse(self.state["r2_phase3b_contract_definition_started"])
            self.assertEqual(self.current["next_phase"], "PHASE_3B_R2_REVISED_MODEL_CONTRACT")
        elif phase == "PHASE_3B_R2_REVISED_MODEL_CONTRACT":
            contract = load("PHASE3B_R2_MODEL_CONTRACT.json")
            self.assertEqual(contract["status"], "FROZEN_REVISED_MODEL_CONTRACT_NO_HISTORICAL_REPLAY")
            self.assertEqual(contract["model"]["model_form"], "EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2")
            self.assertTrue(self.state["r2_phase3b_contract_definition_started"])
            self.assertTrue(self.state["r2_phase3b_contract_definition_complete"])
            self.assertTrue(self.current["validation"]["r2_phase3b_contract_definition_complete"])
            self.assertFalse(self.state["r2_phase3c_replay_started"])
            self.assertFalse(self.current["validation"]["r2_real_historical_replay_executed"])
            self.assertFalse(self.current["validation"]["r2_historical_performance_claimed"])
            self.assertEqual(self.current["next_phase"], "PHASE_3C_R2_POINT_IN_TIME_REPLAY")
        elif phase == "PHASE_3C_R2_POINT_IN_TIME_REPLAY":
            contract = load("PHASE3B_R2_MODEL_CONTRACT.json")
            self.assertEqual(contract["status"], "FROZEN_REVISED_MODEL_CONTRACT_NO_HISTORICAL_REPLAY")
            self.assertEqual(contract["model"]["model_form"], "EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2")
            self.assertTrue(self.state["r2_phase3b_contract_definition_complete"])
            self.assertTrue(self.state["r2_phase3c_replay_started"])
            self.assertTrue(self.state["r2_phase3c_r2b_complete"])
            self.assertTrue(self.current["validation"]["r2_real_historical_replay_executed"])
            self.assertFalse(self.current["validation"]["r2_historical_performance_claimed"])
            self.assertFalse(self.current["validation"]["holdout_build_started"])
            self.assertEqual(self.current["next_phase"], "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE")
        elif phase == "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE":
            self.assertTrue(self.state["r2_phase3c_r2b_complete"])
            self.assertTrue(self.state["holdout_h1_started"])
            self.assertTrue(self.state["holdout_h1_complete"])
            self.assertTrue(self.current["validation"]["holdout_build_started"])
            self.assertEqual(self.current["validation"]["holdout_h1_outcome"], "FAIL_SELECTION_SUFFICIENCY")
            self.assertFalse(self.current["validation"]["r2_historical_performance_claimed"])
            if self.state.get("independent_holdout_replay_complete"):
                self.assertTrue(self.current["validation"]["holdout_h2_started"])
                self.assertEqual(
                    self.current["validation"]["independent_holdout_replay_outcome"],
                    "PASS_INDEPENDENT_HOLDOUT_REPLAY_OPERATIONAL",
                )
                self.assertTrue(self.current["validation"]["phase3d_r2_start_allowed"])
                if self.current["validation"].get("phase3d_r2_started"):
                    self.assertTrue(self.current["validation"]["phase3d_r2_round1_complete"])
                    self.assertEqual(
                        self.current["validation"]["phase3d_r2_round1_status"],
                        "PARTIAL_R2_MEASURABILITY_OUTCOME_EVIDENCE_ACQUISITION_REQUIRED",
                    )
                    self.assertFalse(self.current["validation"]["phase3d_r2_performance_started"])
                    self.assertEqual(
                        self.current["next_phase"],
                        "PHASE_3D_R2_OUTCOME_EVIDENCE_ACQUISITION",
                    )
                else:
                    self.assertFalse(self.current["validation"]["phase3d_r2_started"])
                    self.assertEqual(
                        self.current["next_phase"],
                        "PHASE_3D_R2_MEASURABILITY_AND_PERFORMANCE_IF_SUPPORTED",
                    )
            elif self.state.get("holdout_v2_selection_complete"):
                self.assertFalse(self.current["validation"]["holdout_h2_started"])
                self.assertEqual(self.state["holdout_v2_selection_outcome"], "PASS_SELECTION_SUFFICIENCY")
                self.assertTrue(self.current["validation"]["holdout_h2_start_allowed"])
                self.assertEqual(self.current["next_phase"], "INDEPENDENT_POINT_IN_TIME_HOLDOUT_R2_REPLAY")
            else:
                self.assertFalse(self.current["validation"]["holdout_h2_start_allowed"])
                self.assertEqual(self.current["next_phase"], "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE_EXPANSION")
        elif phase == "PHASE_3D_R2_MEASURABILITY_AND_PERFORMANCE_IF_SUPPORTED":
            self.assertTrue(self.state["independent_holdout_replay_complete"])
            self.assertTrue(self.current["validation"]["phase3d_r2_start_allowed"])
            self.assertTrue(self.current["validation"]["phase3d_r2_started"])
            self.assertTrue(self.current["validation"]["phase3d_r2_round1_complete"])
            self.assertEqual(
                self.current["validation"]["phase3d_r2_round1_status"],
                "PARTIAL_R2_MEASURABILITY_OUTCOME_EVIDENCE_ACQUISITION_REQUIRED",
            )
            self.assertTrue(self.current["validation"]["phase3d_r2_structurally_measurable"])
            self.assertFalse(self.current["validation"]["phase3d_r2_performance_start_allowed"])
            self.assertFalse(self.current["validation"]["phase3d_r2_performance_started"])
            self.assertEqual(
                self.current["next_phase"],
                "PHASE_3D_R2_OUTCOME_EVIDENCE_ACQUISITION",
            )
        else:
            self.fail("unexpected current phase for Post-3F monotonic regression: " + str(phase))

        self.assertFalse(self.state["phase4_entry_allowed"])
        self.assertFalse(self.current["validation"]["phase4_entry_allowed"])

    def test_zero_authority(self):
        controls = self.decision["authority_boundaries"]
        for key in ["effective_core_static_changes", "candidate_membership_mutations", "real_account_mutations", "simulation_mutations", "target_portfolio_writebacks", "user_decisions_generated", "investment_recommendations_generated", "orders"]:
            self.assertEqual(controls[key], 0)
        self.assertEqual(controls["trade_authority"], "NONE")
        self.assertEqual(self.state["orders"], 0)
        self.assertEqual(self.current["orders"], 0)
        self.assertEqual(self.state["trade_authority"], "NONE")
        self.assertEqual(self.current["trade_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
