from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class HoldoutCoverageExpansionV2ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v2 = load("PHASE3_R2_HOLDOUT_COVERAGE_EXPANSION_V2_CONTRACT.json")
        cls.h0 = load("PHASE3_R2_HOLDOUT_SELECTION_CONTRACT.json")
        cls.state = load("PROGRAM_STATE.json")
        cls.current = load("CURRENT_PHASE_STATUS.json")

    def test_parent_h1_negative_result_is_preserved(self):
        p = self.v2["parent_h1"]
        self.assertEqual(p["pr"], 322)
        self.assertEqual(p["final_head"], "f7647e199a286ed76c31cc207d7f2855ef31739e")
        self.assertEqual(p["result"], "FAIL_SELECTION_SUFFICIENCY")
        self.assertEqual(p["selected_checkpoint_count"], 8)
        self.assertEqual(p["minimum_checkpoint_requirement"], 12)
        self.assertEqual(p["failed_thresholds"], ["minimum_holdout_checkpoints"])
        self.assertFalse(p["threshold_relaxation_after_result_allowed"])
        self.assertEqual(p["r2_holdout_replay_count"], 0)
        self.assertEqual(p["realized_outcomes_used_for_selection_count"], 0)

    def test_v1_universe_selector_and_thresholds_are_unchanged(self):
        u = self.v2["unchanged_v1_contract"]
        self.assertEqual(
            u["protected_main_universe"]["start_commit_inclusive"],
            self.h0["frozen_repository_universe"]["start_commit_inclusive"],
        )
        self.assertEqual(
            u["protected_main_universe"]["end_commit_inclusive"],
            self.h0["frozen_repository_universe"]["end_commit_inclusive"],
        )
        self.assertEqual(
            u["selector"]["mode"],
            self.h0["deterministic_selector"]["mode"],
        )
        q = u["quantitative_sufficiency_gate"]
        hq = self.h0["quantitative_sufficiency_gate"]
        for key in (
            "minimum_holdout_checkpoints",
            "minimum_distinct_utc_dates",
            "minimum_distinct_iso_weeks",
            "minimum_distinct_evidence_regime_signatures",
            "minimum_unique_securities",
            "minimum_opportunity_profile_instances",
            "minimum_checkpoints_strictly_outside_seed_time_span",
            "maximum_single_utc_date_fraction",
            "maximum_single_evidence_regime_fraction",
        ):
            self.assertEqual(q[key], hq[key], key)
        self.assertTrue(q["threshold_change_after_h1_result_forbidden"])

    def test_seed_firewall_is_unchanged(self):
        v2 = self.v2["unchanged_v1_contract"]["seed_firewall"]
        h0 = self.h0["seed_firewall"]
        self.assertEqual(v2["excluded_commit_shas"], h0["excluded_commit_shas"])
        self.assertTrue(v2["exact_seed_source_identity_set_reuse_forbidden"])
        self.assertFalse(v2["seven_seed_checkpoints_may_count_as_holdout"])

    def test_only_four_substantive_families_are_added(self):
        exp = self.v2["coverage_expansion"]
        rows = exp["added_substantive_families"]
        self.assertEqual(exp["added_substantive_family_count"], 4)
        self.assertEqual(exp["expected_total_family_count_after_expansion"], 14)
        self.assertEqual(
            [row["family_id"] for row in rows],
            [
                "RESEARCH_OBJECTS_CURRENT",
                "R1_DECISION_COVERAGE_PACK_CURRENT",
                "RESEARCH_QUEUE_D1_CURRENT",
                "RESEARCH_QUEUE_D2_CURRENT",
            ],
        )
        self.assertTrue(exp["v1_family_catalog_preserved"])
        r1 = next(row for row in rows if row["family_id"] == "R1_DECISION_COVERAGE_PACK_CURRENT")
        self.assertFalse(r1["contributes_to_security_scope"])

    def test_operational_lineage_and_outcomes_are_excluded(self):
        excluded = self.v2["coverage_expansion"]["explicitly_excluded_paths_or_classes"]
        joined = "\n".join(excluded)
        self.assertIn("RESEARCH_QUEUE_D2_LIVENESS_CURRENT.json", joined)
        self.assertIn("D2_SEMANTIC_LINEAGE_", joined)
        self.assertIn("RESEARCH_QUEUE_D2_EVIDENCE_", joined)
        self.assertIn("realized_outcomes", excluded)
        self.assertIn("future_returns", excluded)
        self.assertIn("regret", excluded)
        self.assertIn("calibration", excluded)

    def test_expanded_security_scope_is_exact_and_contains_v1_scope(self):
        scope = self.v2["v2_security_scope"]
        self.assertEqual(scope["security_count"], 18)
        self.assertEqual(len(scope["security_ids"]), 18)
        self.assertEqual(len(set(scope["security_ids"])), 18)
        v1 = set(load("PHASE3A_EVIDENCE_REGISTRY.json")["scope_security_ids"])
        self.assertTrue(v1.issubset(set(scope["security_ids"])))
        self.assertTrue(scope["r1_decision_coverage_pack_security_ids_must_not_expand_scope"])

    def test_pre_result_firewall_is_closed(self):
        fw = self.v2["pre_result_firewall"]
        for key in (
            "v2_selection_started",
            "result_based_family_addition_allowed",
            "result_based_security_addition_allowed",
            "threshold_relaxation_allowed",
            "model_transform_change_allowed",
            "model_signature_change_allowed",
        ):
            self.assertFalse(fw[key], key)
        for key in (
            "v2_candidate_ledger_count",
            "r2_profile_compute_count",
            "r2_holdout_replay_count",
            "realized_outcome_read_count",
            "future_return_read_count",
            "phase3d_result_read_count",
        ):
            self.assertEqual(fw[key], 0, key)

    def test_h2_and_phase4_remain_blocked(self):
        gate = self.v2["next_gate"]
        self.assertTrue(gate["v2_selection_start_allowed_after_contract_acceptance"])
        self.assertFalse(gate["v2_r2_replay_allowed_before_v2_selection_sufficiency_pass"])
        self.assertFalse(gate["h2_start_allowed_now"])
        self.assertFalse(gate["phase3d_r2_start_allowed_now"])
        self.assertFalse(gate["phase3e_r2_start_allowed_now"])
        self.assertFalse(gate["repeat_phase3f_start_allowed_now"])
        self.assertFalse(gate["phase4_entry_allowed"])

    def test_zero_authority(self):
        a = self.v2["authority_boundaries"]
        for key in (
            "effective_core_static_changes",
            "candidate_membership_mutations",
            "real_account_mutations",
            "simulation_mutations",
            "target_portfolio_writebacks",
            "user_decisions_generated",
            "investment_recommendations_generated",
            "orders",
        ):
            self.assertEqual(a[key], 0, key)
        self.assertEqual(a["trade_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
