import unittest
from strategy_kernel_v2.current_shadow_pack import build_current_shadow_pack
INV={"inventory_id":"I","as_of":"2026-08-26T12:44:00+08:00"}
def obj(sid,state="READY_AFTER_REFRESH"): return {"security_id":sid,"readiness":{"comparison_readiness":state}}
def gate(o):
    st=o["readiness"]["comparison_readiness"]
    return {"security_id":o["security_id"],"eligible":st=="READY_NOW","gate_state":"ELIGIBLE" if st=="READY_NOW" else "BLOCKED"}
def refresh(o,p):
    if not p.get("ok"):
        return {"security_id":o["security_id"],"refresh_state":"BLOCKED_REFRESH_INCOMPLETE","eligible_for_comparator":False}
    n=dict(o); n["readiness"]={"comparison_readiness":"READY_NOW"}
    return {"security_id":o["security_id"],"refresh_state":"READY_FOR_SHADOW_COMPARISON","eligible_for_comparator":True,"refreshed_object":n}
def compare(items):
    e=[x for x in items if x.get("eligible")]
    return {"pareto_frontier":[x["security_id"] for x in e],"vectors":{x["security_id"]:{} for x in e},"blocked":[x for x in items if not x.get("eligible")]}
class T(unittest.TestCase):
    def call(self,objects,packets=None): return build_current_shadow_pack(objects,INV,packets,refresh_apply=refresh,gate_fn=gate,compare_fn=compare)
    def test_zero_is_no_comparison(self): self.assertEqual(self.call({"A":obj("A"),"B":obj("B")})["mode"],"NO_COMPARISON")
    def test_one_is_no_comparison(self): self.assertEqual(self.call({"A":obj("A"),"B":obj("B")},{"A":{"ok":1}})["mode"],"NO_COMPARISON")
    def test_two_compare(self): self.assertEqual(self.call({"A":obj("A"),"B":obj("B")},{"A":{"ok":1},"B":{"ok":1}})["mode"],"SHADOW_COMPARISON")
    def test_no_recommendation(self): self.assertFalse(self.call({"A":obj("A")})["investment_recommendation_generated"])
    def test_no_user_decision(self): self.assertFalse(self.call({"A":obj("A")})["user_decision_generated"])
    def test_orders_zero(self): self.assertEqual(self.call({"A":obj("A")})["controls"]["orders"],0)
    def test_trade_none(self): self.assertEqual(self.call({"A":obj("A")})["controls"]["trade_authority"],"NONE")
    def test_failed_refresh_not_applied(self): self.assertEqual(self.call({"A":obj("A")},{"A":{"ok":0}})["real_governed_refresh_packets_applied"],0)
    def test_success_refresh_applied(self): self.assertEqual(self.call({"A":obj("A")},{"A":{"ok":1}})["real_governed_refresh_packets_applied"],1)
    def test_inventory_provenance(self): self.assertEqual(self.call({"A":obj("A")})["evidence_inventory_id"],"I")
