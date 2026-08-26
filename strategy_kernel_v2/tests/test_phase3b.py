import unittest

from strategy_kernel_v2.build_phase3a_ledger import build as build_phase3a
from strategy_kernel_v2.competing_model_forms import (
    MODEL_ORDER,
    build_shared_observation_packet,
    run_competing_model_suite,
    run_legacy_policy_baseline,
    run_phase2_probabilistic_vector,
    run_simple_non_probabilistic_pareto,
)


def evidence(evidence_id):
    return {
        "evidence_id": evidence_id,
        "evidence_key": evidence_id,
        "evidence_class": "RESEARCH",
        "security_ids": [],
        "evidence_as_of": "2026-01-01",
        "available_at": "2026-01-01T00:00:00Z",
        "availability_basis": "CANONICAL_MAIN_COMMIT",
        "authority_domain": "CANONICAL_MAIN",
        "source": {
            "repository": "o/r",
            "path": "x.json",
            "commit_sha": "a" * 40,
            "provenance_status": "CANONICAL_MAIN",
        },
    }


def snapshot():
    rows = [evidence("E1"), evidence("E2")]
    return {
        "decision_point_id": "P1",
        "at": "2026-01-02T00:00:00Z",
        "opportunity_security_ids": ["B", "A"],
        "selected_evidence_ids": ["E2", "E1"],
        "selected_evidence": rows,
        "unavailable_required_evidence_keys": [],
    }


def phase2_inputs(expected_high=True):
    returns = [0.20, -0.05] if expected_high else [0.08, -0.10]
    return {
        "valuation_scenarios": [
            {"name": "UP", "probability": 0.6, "annualized_total_return": returns[0]},
            {"name": "DOWN", "probability": 0.4, "annualized_total_return": returns[1]},
        ],
        "confidence": 0.8,
        "portfolio_concentration_cost": 0.2,
        "execution_friction": 0.1,
    }


def simple_inputs(stronger=True):
    if stronger:
        return {
            "return_proxy": 0.8,
            "downside_resilience": 0.8,
            "evidence_quality": 0.9,
            "concentration_cost": 0.1,
            "execution_friction": 0.1,
        }
    return {
        "return_proxy": 0.5,
        "downside_resilience": 0.5,
        "evidence_quality": 0.7,
        "concentration_cost": 0.3,
        "execution_friction": 0.2,
    }


class Phase3BSharedPacketTest(unittest.TestCase):
    def test_packet_canonicalizes_opportunity_and_evidence_order(self):
        packet = build_shared_observation_packet(snapshot())
        self.assertEqual(packet["opportunity_security_ids"], ["A", "B"])
        self.assertEqual(packet["selected_evidence_ids"], ["E1", "E2"])

    def test_packet_fingerprint_is_deterministic(self):
        first = build_shared_observation_packet(snapshot())
        second = build_shared_observation_packet(snapshot())
        self.assertEqual(first["input_packet_sha256"], second["input_packet_sha256"])

    def test_observation_security_must_be_in_opportunity_set(self):
        with self.assertRaisesRegex(ValueError, "OBSERVATION_SECURITY_OUTSIDE_OPPORTUNITY_SET"):
            build_shared_observation_packet(
                snapshot(),
                structured_observations={"C": {"provenance_evidence_ids": ["E1"]}},
            )

    def test_observation_provenance_must_be_inside_shared_evidence(self):
        with self.assertRaisesRegex(ValueError, "OBSERVATION_USES_EVIDENCE_OUTSIDE_SHARED_PACKET"):
            build_shared_observation_packet(
                snapshot(),
                structured_observations={"A": {"provenance_evidence_ids": ["FUTURE"]}},
            )

    def test_reference_asset_requires_identity(self):
        with self.assertRaisesRegex(ValueError, "REFERENCE_ASSET_ID_AND_AS_OF_REQUIRED"):
            build_shared_observation_packet(
                snapshot(),
                reference_asset={"provenance_evidence_ids": ["E1"]},
            )

    def test_reference_asset_uses_shared_evidence_only(self):
        with self.assertRaisesRegex(ValueError, "OBSERVATION_USES_EVIDENCE_OUTSIDE_SHARED_PACKET"):
            build_shared_observation_packet(
                snapshot(),
                reference_asset={
                    "security_id": "CASH",
                    "as_of": "2026-01-02",
                    "provenance_evidence_ids": ["FUTURE"],
                },
            )

    def test_packet_deepcopies_structured_observation(self):
        observations = {
            "A": {
                "provenance_evidence_ids": ["E1"],
                "legacy_disposition": "HOLD",
            }
        }
        packet = build_shared_observation_packet(snapshot(), structured_observations=observations)
        observations["A"]["legacy_disposition"] = "BUY"
        self.assertEqual(packet["structured_observations"]["A"]["legacy_disposition"], "HOLD")


class Phase3BModelFormsTest(unittest.TestCase):
    def packet(self, observations):
        return build_shared_observation_packet(snapshot(), structured_observations=observations)

    def test_legacy_is_passthrough_not_reinterpretation(self):
        packet = self.packet({
            "A": {
                "provenance_evidence_ids": ["E1"],
                "legacy_disposition": "HOLD_NO_TRADE",
                "legacy_reason_codes": ["CANONICAL_STATE"],
            }
        })
        out = run_legacy_policy_baseline(packet)
        row = next(row for row in out["rows"] if row["security_id"] == "A")
        self.assertEqual(row["legacy_disposition"], "HOLD_NO_TRADE")
        self.assertFalse(out["ranking_generated"])

    def test_legacy_missing_disposition_fails_closed(self):
        packet = self.packet({"A": {"provenance_evidence_ids": ["E1"]}})
        out = run_legacy_policy_baseline(packet)
        self.assertEqual(out["evaluable_count"], 0)
        self.assertEqual(out["rows"][0]["status"], "NOT_EVALUABLE")

    def test_phase2_probability_vector_uses_only_explicit_inputs(self):
        packet = self.packet({
            "A": {"provenance_evidence_ids": ["E1"], "phase2_inputs": phase2_inputs(True)}
        })
        out = run_phase2_probabilistic_vector(packet)
        self.assertEqual(out["evaluable_count"], 1)
        self.assertAlmostEqual(out["rows"]["A"]["expected_annualized_total_return"], 0.10)
        self.assertIsNone(out["policy_score"])

    def test_phase2_missing_inputs_fails_closed_without_defaults(self):
        packet = self.packet({"A": {"provenance_evidence_ids": ["E1"]}})
        out = run_phase2_probabilistic_vector(packet)
        self.assertEqual(out["evaluable_count"], 0)
        self.assertIn("PHASE2_INPUTS_NOT_CONTEMPORANEOUSLY_STRUCTURED", out["blocked"][0]["reason_codes"])

    def test_phase2_invalid_probability_sum_rejected(self):
        raw = phase2_inputs(True)
        raw["valuation_scenarios"][0]["probability"] = 0.5
        packet = self.packet({"A": {"provenance_evidence_ids": ["E1"], "phase2_inputs": raw}})
        with self.assertRaisesRegex(ValueError, "PHASE2_SCENARIO_PROBABILITIES_MUST_SUM_TO_ONE"):
            run_phase2_probabilistic_vector(packet)

    def test_phase2_pareto_frontier_is_weight_free(self):
        packet = self.packet({
            "A": {"provenance_evidence_ids": ["E1"], "phase2_inputs": phase2_inputs(True)},
            "B": {"provenance_evidence_ids": ["E2"], "phase2_inputs": phase2_inputs(False)},
        })
        out = run_phase2_probabilistic_vector(packet)
        self.assertNotIn("policy_score", out["rows"]["A"])
        self.assertFalse(out["ranking_generated"])
        self.assertTrue(out["pareto_frontier"])

    def test_simple_pareto_does_not_use_probabilities(self):
        packet = self.packet({
            "A": {"provenance_evidence_ids": ["E1"], "simple_pareto_inputs": simple_inputs(True)}
        })
        out = run_simple_non_probabilistic_pareto(packet)
        self.assertFalse(out["probability_inputs_used"])
        self.assertEqual(out["evaluable_count"], 1)

    def test_simple_pareto_detects_dominance(self):
        packet = self.packet({
            "A": {"provenance_evidence_ids": ["E1"], "simple_pareto_inputs": simple_inputs(True)},
            "B": {"provenance_evidence_ids": ["E2"], "simple_pareto_inputs": simple_inputs(False)},
        })
        out = run_simple_non_probabilistic_pareto(packet)
        self.assertEqual(out["pareto_frontier"], ["A"])
        self.assertEqual(out["rows"]["B"]["dominated_by"], ["A"])

    def test_simple_missing_dimension_fails_closed(self):
        raw = simple_inputs(True)
        raw.pop("evidence_quality")
        packet = self.packet({"A": {"provenance_evidence_ids": ["E1"], "simple_pareto_inputs": raw}})
        out = run_simple_non_probabilistic_pareto(packet)
        self.assertEqual(out["evaluable_count"], 0)
        self.assertIn("MISSING_EXPLICIT_SIMPLE_INPUT:evidence_quality", out["blocked"][0]["reason_codes"])

    def test_suite_uses_exact_same_input_fingerprint_for_all_models(self):
        packet = self.packet({
            "A": {
                "provenance_evidence_ids": ["E1"],
                "legacy_disposition": "HOLD",
                "phase2_inputs": phase2_inputs(True),
                "simple_pareto_inputs": simple_inputs(True),
            }
        })
        suite = run_competing_model_suite(packet)
        self.assertEqual(
            {model["input_packet_sha256"] for model in suite["models"]},
            {packet["input_packet_sha256"]},
        )

    def test_suite_has_exact_three_required_model_forms(self):
        suite = run_competing_model_suite(build_shared_observation_packet(snapshot()))
        self.assertEqual(tuple(suite["model_order"]), MODEL_ORDER)
        self.assertEqual(len(suite["models"]), 3)

    def test_no_model_generates_scalar_target_weight_decision_or_recommendation(self):
        suite = run_competing_model_suite(build_shared_observation_packet(snapshot()))
        for model in suite["models"]:
            self.assertIsNone(model["policy_score"])
            self.assertIsNone(model["target_weights"])
            self.assertFalse(model["decision_replay_generated"])
            self.assertFalse(model["investment_recommendation_generated"])
            self.assertFalse(model["user_decision_generated"])

    def test_suite_preserves_zero_authority(self):
        suite = run_competing_model_suite(build_shared_observation_packet(snapshot()))
        self.assertEqual(suite["controls"]["orders"], 0)
        self.assertEqual(suite["controls"]["trade_authority"], "NONE")
        self.assertEqual(suite["model_specific_evidence_fetches"], 0)


class Phase3BRealLedgerSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = build_phase3a()

    def test_all_seven_phase3a_checkpoints_build_shared_packets(self):
        self.assertEqual(len(self.ledger["snapshots"]), 7)
        for snapshot_row in self.ledger["snapshots"]:
            packet = build_shared_observation_packet(snapshot_row)
            self.assertEqual(packet["source_phase3a_decision_point_id"], snapshot_row["decision_point_id"])

    def test_real_seed_without_feature_extraction_fails_closed_for_all_models(self):
        for snapshot_row in self.ledger["snapshots"]:
            suite = run_competing_model_suite(build_shared_observation_packet(snapshot_row))
            for model in suite["models"]:
                self.assertEqual(model["evaluable_count"], 0)

    def test_real_seed_model_suite_is_deterministic(self):
        snapshot_row = self.ledger["snapshots"][-1]
        packet = build_shared_observation_packet(snapshot_row)
        self.assertEqual(run_competing_model_suite(packet), run_competing_model_suite(packet))


if __name__ == "__main__":
    unittest.main()
