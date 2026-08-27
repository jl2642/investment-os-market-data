from __future__ import annotations

from copy import deepcopy
import unittest

from strategy_kernel_v2.phase3b_r2_contract import (
    compare_r2_profiles,
    load_contract,
    transform_model_neutral_row,
    validate_contract,
)


class Phase3BR2ContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_contract()

    def row(self, security_id: str, features: dict, evidence_id: str = "E1") -> dict:
        return {
            "security_id": security_id,
            "security_name": security_id,
            "features": deepcopy(features),
            "feature_provenance": {key: [evidence_id] for key in features},
            "provenance_evidence_ids": [evidence_id],
        }

    def test_contract_valid(self):
        self.assertEqual(validate_contract(self.contract), [])

    def test_new_identity_does_not_overwrite_v1(self):
        self.assertEqual(
            self.contract["model"]["model_form"],
            "EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2",
        )
        self.assertFalse(self.contract["model"]["overwrites_prior_model"])
        self.assertEqual(self.contract["model"]["model_version"], "R2.0.1_RESEARCH")
        self.assertEqual(
            self.contract["preserved_reference_forms"],
            [
                "LEGACY_POLICY_BASELINE",
                "PHASE2_PROBABILISTIC_VECTOR",
                "SIMPLE_NON_PROBABILISTIC_PARETO",
            ],
        )

    def test_wp5_transforms_are_deterministic_and_provenanced(self):
        row = self.row(
            "601138.SH",
            {
                "wp5_base_case_expected_return": 0.18,
                "wp5_unweighted_scenarios": [
                    {"scenario": "BEAR", "return_vs_completed_close": -0.25},
                    {"scenario": "BASE", "return_vs_completed_close": 0.18},
                    {"scenario": "BULL", "return_vs_completed_close": 0.42},
                ],
                "wp5_source_count": 4,
                "wp5_all_primary_documents": True,
                "wp5_current_weight": 0.03,
                "wp5_implementation_ready": False,
                "wp5_broker_verified": False,
            },
        )
        profile = transform_model_neutral_row(row, self.contract)
        dims = {d["dimension_id"]: d for d in profile["dimensions"]}
        self.assertEqual(dims["REWARD_EXPECTED_RETURN"]["value"], 0.18)
        self.assertEqual(dims["DOWNSIDE_WORST_SCENARIO_RETURN"]["value"], -0.25)
        self.assertEqual(dims["EVIDENCE_SOURCE_COUNT"]["value"], 4.0)
        self.assertEqual(dims["EVIDENCE_ALL_PRIMARY_DOCUMENTS"]["value"], 1.0)
        self.assertEqual(dims["PORTFOLIO_WP5_CURRENT_WEIGHT"]["value"], 0.03)
        self.assertEqual(dims["EXECUTION_WP5_IMPLEMENTATION_READY"]["value"], 0.0)
        self.assertTrue(profile["comparison_contract_evaluable"])
        for dim in profile["dimensions"]:
            self.assertEqual(dim["provenance_evidence_ids"], ["E1"])

    def test_d2_gate_mapping_is_prefix_bounded(self):
        clear = transform_model_neutral_row(
            self.row(
                "000719.SZ",
                {
                    "d2_source_count": 4,
                    "d2_first_rejection_test": "NOT_TRIGGERED_ON_CURRENT_EVIDENCE_BUT_GATES_ACTIVE",
                },
            ),
            self.contract,
        )
        dims = {d["dimension_id"]: d for d in clear["dimensions"]}
        self.assertEqual(dims["DOWNSIDE_REJECTION_GATE_CLEAR"]["value"], 1.0)

        formally_clear = transform_model_neutral_row(
            self.row(
                "301215.SZ",
                {
                    "d2_source_count": 2,
                    "d2_first_rejection_test": "NOT_FORMALLY_TRIGGERED_BUT_CAPACITY_ROIC_EVIDENCE_INSUFFICIENT",
                },
            ),
            self.contract,
        )
        dims = {d["dimension_id"]: d for d in formally_clear["dimensions"]}
        self.assertEqual(dims["DOWNSIDE_REJECTION_GATE_CLEAR"]["value"], 1.0)

        failed = transform_model_neutral_row(
            self.row(
                "301215.SZ",
                {
                    "d2_source_count": 2,
                    "d2_first_rejection_test": "TRIGGERED_EVIDENCE_GAP",
                },
            ),
            self.contract,
        )
        dims = {d["dimension_id"]: d for d in failed["dimensions"]}
        self.assertEqual(dims["DOWNSIDE_REJECTION_GATE_CLEAR"]["value"], 0.0)

        formally_failed = transform_model_neutral_row(
            self.row(
                "X",
                {
                    "d2_source_count": 2,
                    "d2_first_rejection_test": "FORMALLY_TRIGGERED_EVIDENCE_GAP",
                },
            ),
            self.contract,
        )
        dims = {d["dimension_id"]: d for d in formally_failed["dimensions"]}
        self.assertEqual(dims["DOWNSIDE_REJECTION_GATE_CLEAR"]["value"], 0.0)

    def test_unrecognized_categorical_gate_fails_closed(self):
        profile = transform_model_neutral_row(
            self.row(
                "X",
                {"d2_source_count": 2, "d2_first_rejection_test": "AMBIGUOUS"},
            ),
            self.contract,
        )
        self.assertEqual(len(profile["transform_failures"]), 1)
        self.assertFalse(profile["comparison_contract_evaluable"])

    def test_candidate_archive_profile_is_weight_free(self):
        profile = transform_model_neutral_row(
            self.row(
                "000333.SZ",
                {
                    "candidate_archive_evidence_score": 92,
                    "candidate_archive_quality_score": 90,
                    "candidate_archive_risk_penalty": 6,
                    "candidate_archive_valuation_score_coarse": 84,
                    "candidate_archive_portfolio_fit_score": 86,
                },
            ),
            self.contract,
        )
        self.assertTrue(profile["comparison_contract_evaluable"])
        self.assertNotIn("policy_score", profile)
        self.assertNotIn("target_weights", profile)
        self.assertFalse(profile["controls"]["dimension_weights_allowed"])

    def test_missing_is_not_zero_or_not_applicable(self):
        profile = transform_model_neutral_row(
            self.row("X", {"candidate_archive_evidence_score": 80}),
            self.contract,
        )
        self.assertTrue(profile["profile_evaluable"])
        self.assertFalse(profile["comparison_contract_evaluable"])
        self.assertFalse(profile["absent_dimensions_treated_as_zero"])
        self.assertFalse(profile["absent_dimensions_treated_as_not_applicable"])
        self.assertGreater(len(profile["missing_rule_ids"]), 0)

    def test_unmapped_context_is_preserved_but_not_a_dimension(self):
        profile = transform_model_neutral_row(
            self.row(
                "X",
                {
                    "candidate_archive_evidence_score": 90,
                    "candidate_archive_risk_penalty": 5,
                    "candidate_archive_proxy_return_20260624_to_20260710_pct": -5.1,
                    "candidate_archive_race_confidence": "MEDIUM_LOW",
                },
            ),
            self.contract,
        )
        self.assertIn(
            "candidate_archive_proxy_return_20260624_to_20260710_pct",
            profile["preserved_unmapped_context"],
        )
        source_keys = {d["source_feature_key"] for d in profile["dimensions"]}
        self.assertNotIn("candidate_archive_proxy_return_20260624_to_20260710_pct", source_keys)
        self.assertNotIn("candidate_archive_race_confidence", source_keys)

    def test_exact_signature_group_pareto(self):
        a = transform_model_neutral_row(
            self.row(
                "A",
                {
                    "candidate_archive_evidence_score": 95,
                    "candidate_archive_quality_score": 92,
                    "candidate_archive_risk_penalty": 3,
                    "candidate_archive_valuation_score_coarse": 88,
                    "candidate_archive_portfolio_fit_score": 90,
                },
                "EA",
            ),
            self.contract,
        )
        b = transform_model_neutral_row(
            self.row(
                "B",
                {
                    "candidate_archive_evidence_score": 90,
                    "candidate_archive_quality_score": 88,
                    "candidate_archive_risk_penalty": 6,
                    "candidate_archive_valuation_score_coarse": 80,
                    "candidate_archive_portfolio_fit_score": 82,
                },
                "EB",
            ),
            self.contract,
        )
        result = compare_r2_profiles([a, b], self.contract)
        self.assertEqual(result["comparable_profile_count"], 2)
        group = result["groups"][0]
        self.assertEqual(group["status"], "COMPARABLE_EXACT_SIGNATURE")
        self.assertEqual(group["pareto_frontier"], ["A"])
        self.assertEqual(group["dominated_by"]["B"], ["A"])
        self.assertFalse(result["ranking_generated"])
        self.assertFalse(result["winner_selected"])

    def test_cross_signature_comparison_is_forbidden(self):
        archive = transform_model_neutral_row(
            self.row(
                "A",
                {
                    "candidate_archive_evidence_score": 90,
                    "candidate_archive_risk_penalty": 4,
                    "candidate_archive_valuation_score_coarse": 80,
                },
                "EA",
            ),
            self.contract,
        )
        d2 = transform_model_neutral_row(
            self.row(
                "B",
                {"d2_source_count": 4, "d2_first_rejection_test": "NOT_TRIGGERED_OK"},
                "EB",
            ),
            self.contract,
        )
        result = compare_r2_profiles([archive, d2], self.contract)
        self.assertEqual(result["cross_signature_comparison_count"], 0)
        self.assertEqual(result["comparable_profile_count"], 0)
        self.assertEqual(len(result["groups"]), 2)
        self.assertTrue(all(g["status"] == "INSUFFICIENT_GROUP_SIZE" for g in result["groups"]))

    def test_overlay_presence_changes_signature_instead_of_being_ignored(self):
        base_features = {
            "candidate_archive_evidence_score": 90,
            "candidate_archive_risk_penalty": 4,
            "candidate_archive_valuation_score_coarse": 80,
        }
        a = transform_model_neutral_row(self.row("A", base_features, "EA"), self.contract)
        b_features = dict(base_features)
        b_features["real_account_weight_mechanical"] = 0.2
        b = transform_model_neutral_row(self.row("B", b_features, "EB"), self.contract)
        self.assertNotEqual(a["comparison_signature_sha256"], b["comparison_signature_sha256"])
        result = compare_r2_profiles([a, b], self.contract)
        self.assertEqual(result["comparable_profile_count"], 0)

    def test_feature_provenance_outside_row_rejected(self):
        row = self.row("X", {"candidate_archive_evidence_score": 90})
        row["feature_provenance"]["candidate_archive_evidence_score"] = ["OTHER"]
        with self.assertRaisesRegex(ValueError, "R2_FEATURE_PROVENANCE_OUTSIDE_ROW"):
            transform_model_neutral_row(row, self.contract)

    def test_phase_boundary_has_no_real_replay_or_authority(self):
        boundary = self.contract["phase_boundary"]
        self.assertFalse(boundary["phase3b_r2_reads_historical_sources"])
        self.assertFalse(boundary["phase3b_r2_executes_real_historical_replay"])
        self.assertFalse(boundary["phase3b_r2_claims_replay_coverage"])
        self.assertFalse(boundary["phase3b_r2_claims_performance"])
        self.assertFalse(boundary["phase4_entry_allowed"])
        authority = self.contract["authority_boundaries"]
        self.assertEqual(authority["orders"], 0)
        self.assertEqual(authority["trade_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
