from __future__ import annotations

from pathlib import Path
import unittest

import strategy_kernel_v2.phase3_r2_holdout_v2_selection as v2s

ROOT = Path(__file__).resolve().parents[1]


class HoldoutV2SelectionTests(unittest.TestCase):
    def setUp(self):
        self.h0 = v2s._load_json(ROOT / "PHASE3_R2_HOLDOUT_SELECTION_CONTRACT.json")
        self.v2 = v2s.load_v2_contract()
        self.registry = v2s._load_json(ROOT / "PHASE3A_EVIDENCE_REGISTRY.json")

    def test_v2_family_catalog_preserves_v1_and_adds_exact_four(self):
        v1 = v2s.build_family_catalog(self.registry, self.h0)
        expanded = v2s.build_v2_family_catalog(self.registry, self.h0, self.v2)
        self.assertEqual(len(v1), 10)
        self.assertEqual(len(expanded), 14)
        self.assertTrue(set(v1).issubset(expanded))
        self.assertEqual(
            set(expanded) - set(v1),
            {
                "RESEARCH_OBJECTS_CURRENT",
                "R1_DECISION_COVERAGE_PACK_CURRENT",
                "RESEARCH_QUEUE_D1_CURRENT",
                "RESEARCH_QUEUE_D2_CURRENT",
            },
        )

    def test_selection_contract_extends_research_families_without_mutating_h0(self):
        before = list(self.h0["frozen_evidence_families"]["research_or_decision_families"])
        selection = v2s._selection_contract(self.h0, self.v2)
        after = selection["frozen_evidence_families"]["research_or_decision_families"]
        self.assertEqual(
            self.h0["frozen_evidence_families"]["research_or_decision_families"],
            before,
        )
        for row in self.v2["coverage_expansion"]["added_substantive_families"]:
            self.assertIn(row["family_id"], after)

    def test_v2_security_scope_is_frozen_exact_18(self):
        scope = self.v2["v2_security_scope"]
        self.assertEqual(scope["security_count"], 18)
        self.assertEqual(len(scope["security_ids"]), 18)
        self.assertEqual(scope["security_ids"], sorted(scope["security_ids"]))
        self.assertEqual(len(set(scope["security_ids"])), 18)
        self.assertTrue(set(self.registry["scope_security_ids"]).issubset(scope["security_ids"]))

    def test_h0_thresholds_and_seed_firewall_are_not_changed(self):
        u = self.v2["unchanged_v1_contract"]
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
            self.assertEqual(q[key], hq[key])
        self.assertEqual(
            u["seed_firewall"]["excluded_commit_shas"],
            self.h0["seed_firewall"]["excluded_commit_shas"],
        )

    def test_controls_forbid_model_outcome_and_post_h1_tuning(self):
        for key in (
            "realized_outcomes_read",
            "phase3d_results_read",
            "r2_profile_values_computed",
            "r2_pareto_replay_executed",
            "r2_replayability_used_for_selection",
            "future_returns_used_for_selection",
            "regret_or_calibration_used_for_selection",
            "discretionary_subsampling_used",
            "random_sampling_used",
            "manual_cherry_pick_used",
            "v1_h1_result_used_to_relax_threshold",
            "v1_h1_result_used_to_select_family",
            "v1_h1_result_used_to_select_security",
            "v2_contract_mutated_during_selection",
        ):
            self.assertFalse(v2s.FALSE_CONTROLS[key], key)
        self.assertEqual(v2s.FALSE_CONTROLS["orders"], 0)
        self.assertEqual(v2s.FALSE_CONTROLS["trade_authority"], "NONE")

    def test_module_does_not_import_r2_replay_or_phase3d_outcomes(self):
        source = (ROOT / "phase3_r2_holdout_v2_selection.py").read_text(encoding="utf-8")
        forbidden = [
            "phase3c_r2b_replay",
            "phase3c_r2a_reconstruction",
            "phase3d_realized",
            "PHASE3D_RESULTS",
        ]
        for token in forbidden:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
