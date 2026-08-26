import unittest
from strategy_kernel_v2 import RepoDecisionAdapter

MAIN_SHA = "5c5df9082688f65332c79fef3b9cbfa893a06908"

class Phase0B1BRegression(unittest.TestCase):
    def setUp(self): self.adapter = RepoDecisionAdapter(MAIN_SHA)
    def test_601138_consumed_review_remains_hold_no_trade(self):
        decision={"status":"TRIM_REVIEW_APPROVED_NO_TRADE_MONITORING_ACTIVE","formal_plan":{"current_action":"HOLD_600_SHARES_NO_ADD_NO_TRADE"},"fundamental_trigger_assessment":{"current_judgment":"HOLD","trim_or_exit_triggers":[]}}
        simulation={"holdings":[{"security_id":"601138.SH","market_value":39714.0,"mark_as_of":"2026-08-14"}],"summary":{"account_total_assets":1020196.39}}
        obj=self.adapter.industrial_fulian(decision,simulation); self.assertEqual(obj.economic_preference,"HOLD_CURRENT"); self.assertEqual(obj.research_action,"MONITOR"); self.assertEqual(obj.authority.orders,0); self.assertLess(obj.current_weight,.041)
    def test_00669_price_only_changes_research_not_authority(self):
        decision={"source_lineage":{"review_anchor_date":"2026-08-11"},"portfolio_sizing_review":{"board_lot_sizing_mismatch":True},"fundamental_monitoring":{"current_thesis_state":"PASS","buy_review_invalidates_if":[]}}
        for px in [145,135,130,125,119]:
            obj=self.adapter.techtronic(decision,px); self.assertEqual(obj.comparability_state,"NOT_COMPARABLE"); self.assertFalse(obj.authority.order_authorized); self.assertEqual(obj.authority.trade_authority,"NONE")
    def test_605090_concentration_is_diagnostic_not_sell_signal(self):
        real={"holdings":[{"security_id":"605090.SH","market_value":359469.0,"mark_as_of":"2026-08-14"}],"summary":{"account_total_assets":819057.162038}}
        obj=self.adapter.jovo_energy(real); self.assertGreater(obj.current_weight,.40); self.assertEqual(obj.economic_preference,"HOLD_CURRENT"); self.assertEqual(obj.comparability_state,"NOT_COMPARABLE")
    def test_d2_complete_is_not_buy_or_candidate_mutation(self):
        obj=self.adapter.d2_research({"security_id":"000719.SZ","status":"D2_RESEARCH_COMPLETE","research_disposition":"HOLD_RESEARCH_COMPLETE_NO_DECISION"}); self.assertEqual(obj.economic_preference,"UNRANKED"); self.assertFalse(obj.authority.candidate_membership_mutation_authorized)
    def test_missing_valuation_never_becomes_comparable(self):
        obj=self.adapter.d2_research({"security_id":"301215.SZ","status":"D2_RESEARCH_HOLD_EVIDENCE_GAP","evidence_gap":"PROJECT_UTILIZATION"}); self.assertIsNone(obj.expected_annualized_return()); self.assertEqual(obj.comparability_state,"NOT_COMPARABLE")

if __name__ == "__main__": unittest.main()
