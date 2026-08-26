import copy
import unittest

from strategy_kernel_v2.governed_refresh import apply_governed_refresh
from strategy_kernel_v2.capital_comparator import gate_underwriting_object

FALSE_CONTROLS = {"candidate_membership_change_authorized": False, "real_position_change_authorized": False, "simulation_position_change_authorized": False, "target_portfolio_writeback_authorized": False, "order_authorized": False, "implementation_ready": False, "orders": 0, "trade_authority": "NONE"}


def obj(sid="000719.SZ", readiness="READY_AFTER_REFRESH", gaps=None, req=None):
    pc = None
    val = {"status": "PARTIAL", "scenarios": [], "research_triggers_are_orders": False}
    if sid == "601138.SH": pc = {"canonical_action": "HOLD_600_SHARES_NO_ADD_NO_TRADE"}
    elif sid == "HKEX:00669":
        pc = {"canonical_action": "WATCH_NO_TRADE_WAIT_FOR_PRICE_OR_POSITION_SIZING_GATE"}
        val["price_bands_are_research_gates"] = True
    elif sid == "605090.SH": pc = {"concentration_is_automatic_sell_signal": False}
    return {"schema_version": "1.0.0", "security_id": sid, "security_name": sid,
            "underwriting": {"business_economics": {}, "normalized_earnings_cashflow": {}, "thesis": "x", "falsifiers": []},
            "valuation": val, "portfolio_context": pc,
            "research_quality": {"completeness": "PARTIAL", "evidence_gaps": gaps or []},
            "readiness": {"decision_readiness": "EVIDENCE_GAP" if readiness == "NOT_READY" else "RESEARCH_ONLY", "comparison_readiness": readiness, "refresh_requirements": req or ["fresh close"]},
            "controls": copy.deepcopy(FALSE_CONTROLS)}


def packet(sid="000719.SZ", classes=None, satisfied=None, resolved=None):
    return {"schema_version": "1.0.0", "security_id": sid, "as_of": "2026-08-25", "governed": True,
            "provenance": [{"source_type": "GOVERNED_PRODUCTION", "locator": "run://123"}],
            "evidence_classes": classes or ["PRICE_MARK", "VALUATION"],
            "satisfied_requirements": satisfied if satisfied is not None else ["fresh close"],
            "resolved_evidence_gaps": resolved or [],
            "valuation_scenarios": [{"name": "BEAR", "probability": 0.25, "annualized_total_return": -0.10}, {"name": "BASE", "probability": 0.50, "annualized_total_return": 0.10}, {"name": "BULL", "probability": 0.25, "annualized_total_return": 0.25}],
            "comparison_inputs": {"confidence": 0.7, "portfolio_concentration_cost": 0.1, "execution_friction": 0.05}}


class Phase2BTests(unittest.TestCase):
    def test_ready_after_refresh_complete_becomes_comparator_ready(self):
        source = obj(); result = apply_governed_refresh(source, packet())
        self.assertTrue(result["eligible_for_comparator"]); self.assertTrue(gate_underwriting_object(result["refreshed_object"])["eligible"])
    def test_incomplete_refresh_stays_blocked(self):
        result = apply_governed_refresh(obj(req=["fresh close", "fresh thesis check"]), packet(satisfied=["fresh close"]))
        self.assertFalse(result["eligible_for_comparator"]); self.assertIn("fresh thesis check", result["missing_requirements"])
    def test_not_ready_cannot_be_cured_by_price_only(self):
        source = obj("605090.SH", "NOT_READY", gaps=["issuer re-underwrite", "cash-flow model"], req=["issuer re-underwrite"])
        result = apply_governed_refresh(source, packet("605090.SH", classes=["PRICE_MARK", "VALUATION"], satisfied=["issuer re-underwrite"], resolved=["issuer re-underwrite", "cash-flow model"]))
        self.assertFalse(result["eligible_for_comparator"]); self.assertEqual(result["refresh_state"], "BLOCKED_MATERIAL_EVIDENCE_PRICE_OR_VALUATION_ONLY")
    def test_not_ready_requires_all_material_gaps_resolved(self):
        source = obj("301215.SZ", "NOT_READY", gaps=["utilization", "incremental margin"], req=["project disclosure"])
        result = apply_governed_refresh(source, packet("301215.SZ", classes=["FUNDAMENTAL_REUNDERWRITE", "VALUATION"], satisfied=["project disclosure"], resolved=["utilization"]))
        self.assertFalse(result["eligible_for_comparator"]); self.assertIn("incremental margin", result["missing_requirements"])
    def test_not_ready_can_be_comparison_ready_after_full_fundamental_refresh(self):
        source = obj("605090.SH", "NOT_READY", gaps=["issuer re-underwrite", "cash-flow model"], req=["issuer re-underwrite"])
        result = apply_governed_refresh(source, packet("605090.SH", classes=["FUNDAMENTAL_REUNDERWRITE", "VALUATION"], satisfied=["issuer re-underwrite"], resolved=["issuer re-underwrite", "cash-flow model"]))
        self.assertTrue(result["eligible_for_comparator"]); refreshed = result["refreshed_object"]
        self.assertEqual(refreshed["readiness"]["decision_readiness"], "EVIDENCE_GAP"); self.assertTrue(gate_underwriting_object(refreshed)["eligible"])
    def test_source_object_is_not_mutated(self):
        source = obj(); before = copy.deepcopy(source); apply_governed_refresh(source, packet()); self.assertEqual(source, before)
    def test_601138_action_preserved(self):
        result = apply_governed_refresh(obj("601138.SH"), packet("601138.SH")); self.assertEqual(result["refreshed_object"]["portfolio_context"]["canonical_action"], "HOLD_600_SHARES_NO_ADD_NO_TRADE")
    def test_00669_action_and_price_gate_preserved(self):
        result = apply_governed_refresh(obj("HKEX:00669"), packet("HKEX:00669")); refreshed = result["refreshed_object"]
        self.assertEqual(refreshed["portfolio_context"]["canonical_action"], "WATCH_NO_TRADE_WAIT_FOR_PRICE_OR_POSITION_SIZING_GATE"); self.assertTrue(refreshed["valuation"]["price_bands_are_research_gates"])
    def test_605090_concentration_not_sell_signal(self):
        source = obj("605090.SH", "NOT_READY", gaps=["issuer re-underwrite"], req=["issuer re-underwrite"])
        result = apply_governed_refresh(source, packet("605090.SH", classes=["FUNDAMENTAL_REUNDERWRITE", "VALUATION"], satisfied=["issuer re-underwrite"], resolved=["issuer re-underwrite"])); self.assertFalse(result["refreshed_object"]["portfolio_context"]["concentration_is_automatic_sell_signal"])
    def test_authority_controls_preserved(self):
        result = apply_governed_refresh(obj(), packet()); self.assertEqual(result["refreshed_object"]["controls"], FALSE_CONTROLS); self.assertEqual(result["orders"], 0); self.assertEqual(result["trade_authority"], "NONE")
    def test_ungoverned_packet_rejected(self):
        p = packet(); p["governed"] = False
        with self.assertRaises(ValueError): apply_governed_refresh(obj(), p)
    def test_missing_provenance_rejected(self):
        p = packet(); p["provenance"] = []
        with self.assertRaises(ValueError): apply_governed_refresh(obj(), p)
    def test_security_mismatch_rejected(self):
        with self.assertRaises(ValueError): apply_governed_refresh(obj(), packet("002039.SZ"))


if __name__ == "__main__": unittest.main()
