import copy
import unittest

from strategy_kernel_v2.capital_comparator import (
    FALSE_CONTROLS,
    compare_capital_uses,
    gate_underwriting_object,
    make_cash_baseline,
)


def obj(sid, readiness="READY_AFTER_REFRESH", decision="RESEARCH_ONLY", requirements=None):
    return {
        "security_id": sid,
        "security_name": sid,
        "readiness": {
            "comparison_readiness": readiness,
            "decision_readiness": decision,
            "refresh_requirements": list(requirements or ["fresh valuation"]),
        },
        "valuation": {"scenarios": []},
    }


def refresh(sid, requirements, scenarios, **kwargs):
    payload = {
        "security_id": sid,
        "governed": True,
        "as_of": "2026-08-26",
        "provenance": "GOVERNED_TEST_FIXTURE",
        "satisfied_requirements": list(requirements),
        "valuation_scenarios": scenarios,
        "confidence": 0.7,
        "portfolio_concentration_cost": 0.2,
        "execution_friction": 0.1,
    }
    payload.update(kwargs)
    return payload


SCENARIOS_A = [
    {"name":"BEAR","probability":0.25,"annualized_total_return":-0.10},
    {"name":"BASE","probability":0.50,"annualized_total_return":0.15},
    {"name":"BULL","probability":0.25,"annualized_total_return":0.35},
]
SCENARIOS_B = [
    {"name":"BEAR","probability":0.25,"annualized_total_return":-0.15},
    {"name":"BASE","probability":0.50,"annualized_total_return":0.10},
    {"name":"BULL","probability":0.25,"annualized_total_return":0.25},
]


class Phase2ATests(unittest.TestCase):
    def test_ready_after_refresh_is_blocked_without_overlay(self):
        gate = gate_underwriting_object(obj("A"))
        self.assertFalse(gate["eligible"])
        self.assertEqual(gate["gate_state"], "BLOCKED_REFRESH_REQUIRED")

    def test_material_evidence_gap_cannot_be_unlocked_by_price_refresh(self):
        source = obj("GAP", readiness="NOT_READY", decision="EVIDENCE_GAP")
        gate = gate_underwriting_object(source, refresh("GAP", ["fresh valuation"], SCENARIOS_A))
        self.assertFalse(gate["eligible"])
        self.assertEqual(gate["gate_state"], "BLOCKED_MATERIAL_EVIDENCE")

    def test_refresh_must_be_governed(self):
        r = refresh("A", ["fresh valuation"], SCENARIOS_A)
        r["governed"] = False
        with self.assertRaises(ValueError):
            gate_underwriting_object(obj("A"), r)

    def test_refresh_requirements_must_all_be_satisfied(self):
        source = obj("A", requirements=["fresh valuation","fresh filing"])
        gate = gate_underwriting_object(source, refresh("A", ["fresh valuation"], SCENARIOS_A))
        self.assertFalse(gate["eligible"])
        self.assertEqual(gate["missing_requirements"], ["fresh filing"])

    def test_scenario_probabilities_must_sum_to_one(self):
        bad = copy.deepcopy(SCENARIOS_A)
        bad[0]["probability"] = 0.20
        with self.assertRaises(ValueError):
            gate_underwriting_object(obj("A"), refresh("A", ["fresh valuation"], bad))

    def test_vector_inputs_are_explicit_not_defaulted(self):
        r = refresh("A", ["fresh valuation"], SCENARIOS_A)
        del r["confidence"]
        gate = gate_underwriting_object(obj("A"), r)
        self.assertFalse(gate["eligible"])
        self.assertIn("confidence", gate["missing_requirements"])

    def test_eligible_vector_is_transparent(self):
        gate = gate_underwriting_object(obj("A"), refresh("A", ["fresh valuation"], SCENARIOS_A))
        self.assertTrue(gate["eligible"])
        self.assertAlmostEqual(gate["vector"]["expected_annualized_total_return"], 0.1375)
        self.assertAlmostEqual(gate["vector"]["probability_of_loss"], 0.25)
        self.assertEqual(gate["source_decision_readiness"], "RESEARCH_ONLY")

    def test_comparator_has_no_scalar_policy_score_and_no_decision(self):
        a = gate_underwriting_object(obj("A"), refresh("A", ["fresh valuation"], SCENARIOS_A))
        out = compare_capital_uses([a])
        self.assertIsNone(out["policy_score"])
        self.assertFalse(out["user_decision_generated"])
        self.assertFalse(out["economic_preference_writeback"])
        self.assertEqual(out["controls"], FALSE_CONTROLS)

    def test_pareto_frontier_detects_dominance(self):
        a = gate_underwriting_object(
            obj("A"),
            refresh("A", ["fresh valuation"], SCENARIOS_A, confidence=0.8, portfolio_concentration_cost=0.1, execution_friction=0.05),
        )
        b = gate_underwriting_object(
            obj("B"),
            refresh("B", ["fresh valuation"], SCENARIOS_B, confidence=0.7, portfolio_concentration_cost=0.2, execution_friction=0.1),
        )
        out = compare_capital_uses([a,b])
        self.assertIn("A", out["pareto_frontier"])
        self.assertNotIn("B", out["pareto_frontier"])
        self.assertEqual(out["vectors"]["B"]["pareto_status"], "DOMINATED")
        self.assertIn("A", out["vectors"]["B"]["dominated_by"])

    def test_cash_baseline_requires_explicit_rate_and_provenance(self):
        with self.assertRaises(ValueError):
            make_cash_baseline(security_id="CASH", annualized_return=0.02, as_of="", provenance="")
        cash = make_cash_baseline(security_id="CASH", annualized_return=0.02, as_of="2026-08-26", provenance="explicit test rate")
        self.assertTrue(cash["eligible"])
        self.assertEqual(cash["vector"]["expected_annualized_total_return"], 0.02)

    def test_excess_return_vs_cash_is_diagnostic_only(self):
        a = gate_underwriting_object(obj("A"), refresh("A", ["fresh valuation"], SCENARIOS_A))
        cash = make_cash_baseline(security_id="CASH", annualized_return=0.02, as_of="2026-08-26", provenance="explicit test rate")
        out = compare_capital_uses([a,cash], cash_baseline_id="CASH")
        self.assertAlmostEqual(out["vectors"]["A"]["excess_expected_return_vs_cash"], 0.1175)
        self.assertFalse(out["user_decision_generated"])

    def test_comparator_does_not_mutate_inputs(self):
        source = obj("A")
        r = refresh("A", ["fresh valuation"], SCENARIOS_A)
        source_before = copy.deepcopy(source)
        r_before = copy.deepcopy(r)
        gated = gate_underwriting_object(source, r)
        compare_capital_uses([gated])
        self.assertEqual(source, source_before)
        self.assertEqual(r, r_before)


if __name__ == "__main__":
    unittest.main()
