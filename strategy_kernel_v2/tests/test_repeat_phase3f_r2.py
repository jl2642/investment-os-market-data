import unittest

from strategy_kernel_v2.repeat_phase3f_r2_promotion_gate import (
    ADAPTER_FILE,
    ORIGINAL_CONTRACT_FILE,
    _load,
    evaluate_repeat_phase3f,
    validate_adapter,
)


class RepeatPhase3FR2Tests(unittest.TestCase):
    def test_adapter_inherits_original_four_requirements_without_change(self):
        adapter = _load(ADAPTER_FILE)
        original = _load(ORIGINAL_CONTRACT_FILE)
        self.assertEqual(validate_adapter(adapter, original), [])
        self.assertEqual(
            set(adapter["r2_evidence_bindings"]),
            set(original["mandatory_promotion_requirements"]),
        )
        self.assertTrue(adapter["inherited_gate_contract"]["requirements_unchanged"])
        self.assertTrue(adapter["interpretation_discipline"]["no_new_promotion_requirement"])
        self.assertTrue(adapter["interpretation_discipline"]["no_post_result_numeric_threshold"])

    def test_repeat_gate_is_deterministic_and_candidate_state_only(self):
        a = evaluate_repeat_phase3f()
        b = evaluate_repeat_phase3f()
        self.assertEqual(a["repeat_phase3f_gate_sha256"], b["repeat_phase3f_gate_sha256"])
        self.assertEqual(a["promotion_requirement_total_count"], 4)
        self.assertFalse(a["state_closeout_applied"])
        self.assertFalse(a["repeat_phase3f_started"])
        self.assertFalse(a["phase4_started"])
        self.assertEqual(a["orders"], 0)
        self.assertEqual(a["trade_authority"], "NONE")

    def test_robustness_sensitivity_is_carried_not_retrofit_as_gate(self):
        result = evaluate_repeat_phase3f()
        self.assertTrue(result["robustness_sensitivity_carry_forward_required"])
        self.assertFalse(result["post_result_promotion_threshold_created"])
        self.assertFalse(result["statistical_significance_claimed"])


if __name__ == "__main__":
    unittest.main()
