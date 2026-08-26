import json
import unittest
from pathlib import Path

from strategy_kernel_v2.source_registry import SPECS, build_all
from strategy_kernel_v2.underwriting_extractor import FALSE_CONTROLS, extract_underwriting


class Phase1CUnderwritingExtractionTests(unittest.TestCase):
    def setUp(self):
        self.objects = build_all()

    def test_exact_coverage(self):
        self.assertEqual(
            set(self.objects),
            {"601138.SH", "605090.SH", "HKEX:00669", "000719.SZ", "002039.SZ", "301215.SZ", "000333.SZ", "600900.SH"},
        )
        self.assertEqual(len(self.objects), 8)

    def test_all_authority_boundaries_are_false(self):
        for obj in self.objects.values():
            self.assertEqual(obj["controls"], FALSE_CONTROLS)
            self.assertEqual(obj["controls"]["orders"], 0)
            self.assertEqual(obj["controls"]["trade_authority"], "NONE")

    def test_missing_valuation_never_fabricates_scenarios(self):
        for sid in ("605090.SH", "301215.SZ"):
            obj = self.objects[sid]
            self.assertEqual(obj["valuation"]["status"], "UNAVAILABLE")
            self.assertEqual(obj["valuation"]["scenarios"], [])
            self.assertEqual(obj["readiness"]["comparison_readiness"], "NOT_READY")

    def test_601138_preserves_accepted_no_trade_semantics(self):
        obj = self.objects["601138.SH"]
        self.assertEqual(obj["portfolio_context"]["canonical_action"], "HOLD_600_SHARES_NO_ADD_NO_TRADE")
        self.assertFalse(obj["controls"]["position_change_authorized"] if "position_change_authorized" in obj["controls"] else False)
        self.assertEqual(obj["readiness"]["decision_readiness"], "RESEARCH_ONLY")

    def test_605090_concentration_is_diagnostic_only(self):
        obj = self.objects["605090.SH"]
        self.assertFalse(obj["portfolio_context"]["concentration_is_automatic_sell_signal"])
        self.assertEqual(obj["readiness"]["decision_readiness"], "EVIDENCE_GAP")

    def test_00669_price_bands_are_research_gates_not_orders(self):
        obj = self.objects["HKEX:00669"]
        self.assertTrue(obj["valuation"]["price_bands_are_research_gates"])
        self.assertFalse(obj["valuation"]["research_triggers_are_orders"])
        self.assertEqual(obj["portfolio_context"]["canonical_action"], "WATCH_NO_TRADE_WAIT_FOR_PRICE_OR_POSITION_SIZING_GATE")

    def test_d2_complete_is_not_decision_permission(self):
        for sid in ("000719.SZ", "002039.SZ"):
            obj = self.objects[sid]
            self.assertEqual(obj["readiness"]["decision_readiness"], "RESEARCH_ONLY")
            self.assertNotEqual(obj["readiness"]["comparison_readiness"], "READY_NOW")

    def test_301215_material_gap_blocks_comparison(self):
        obj = self.objects["301215.SZ"]
        self.assertEqual(obj["research_quality"]["completeness"], "MATERIAL_EVIDENCE_GAP")
        self.assertEqual(obj["readiness"]["decision_readiness"], "EVIDENCE_GAP")
        self.assertEqual(obj["readiness"]["comparison_readiness"], "NOT_READY")

    def test_core2_scenario_completion_flag_does_not_invent_payload(self):
        for sid in ("000333.SZ", "600900.SH"):
            obj = self.objects[sid]
            self.assertTrue(obj["valuation"]["framework"]["wp4b_driver_based_scenarios_complete"])
            self.assertFalse(obj["valuation"]["framework"]["scenario_payload_extractable_from_current_state"])
            self.assertEqual(obj["valuation"]["scenarios"], [])
            self.assertEqual(obj["readiness"]["comparison_readiness"], "READY_AFTER_REFRESH")

    def test_extractor_is_deterministic(self):
        first = {sid: extract_underwriting(spec) for sid, spec in SPECS.items()}
        second = {sid: extract_underwriting(spec) for sid, spec in SPECS.items()}
        self.assertEqual(
            json.dumps(first, ensure_ascii=False, sort_keys=True),
            json.dumps(second, ensure_ascii=False, sort_keys=True),
        )

    def test_generated_bundle_if_present_matches_registry(self):
        path = Path(__file__).resolve().parents[1] / "generated" / "UNDERWRITING_OBJECTS_PHASE1C.json"
        if not path.exists():
            self.skipTest("generated bundle is added after generator validation")
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["object_count"], 8)
        self.assertEqual(payload["orders"], 0)
        self.assertEqual(payload["trade_authority"], "NONE")
        self.assertEqual(payload["objects"], self.objects)


if __name__ == "__main__":
    unittest.main()
