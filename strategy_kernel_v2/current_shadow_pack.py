"""Phase 2C current shadow comparison pack; research-only."""
from copy import deepcopy

FALSE_CONTROLS = {
 "candidate_membership_change_authorized":False,
 "real_position_change_authorized":False,
 "simulation_position_change_authorized":False,
 "target_portfolio_writeback_authorized":False,
 "order_authorized":False,"implementation_ready":False,
 "orders":0,"trade_authority":"NONE",
}

def build_current_shadow_pack(objects, evidence_inventory, refresh_packets=None,
                              reference_items=None, refresh_apply=None,
                              gate_fn=None, compare_fn=None):
    if refresh_apply is None:
        from .governed_refresh import apply_governed_refresh as refresh_apply
    if gate_fn is None or compare_fn is None:
        from .capital_comparator import gate_underwriting_object, compare_capital_uses
        gate_fn = gate_fn or gate_underwriting_object
        compare_fn = compare_fn or compare_capital_uses
    refresh_packets=dict(refresh_packets or {})
    reference_items=[deepcopy(dict(x)) for x in (reference_items or [])]
    gated=[]; applied=[]
    for sid in sorted(objects):
        obj=objects[sid]; packet=refresh_packets.get(sid)
        if packet is None:
            gate=gate_fn(obj)
        else:
            r=refresh_apply(obj,packet)
            applied.append({"security_id":sid,"refresh_state":r["refresh_state"],
                            "eligible_for_comparator":r["eligible_for_comparator"]})
            if r["eligible_for_comparator"]:
                gate=gate_fn(r["refreshed_object"])
            else:
                gate={"security_id":sid,"gate_state":r["refresh_state"],"eligible":False,
                      "missing_requirements":r.get("missing_requirements",[]),
                      "reason_codes":r.get("reason_codes",[])}
        gated.append(gate)
    eligible=[x for x in gated if x.get("eligible") is True]
    out={"schema_version":"1.0.0","phase":"2C",
         "evidence_inventory_id":evidence_inventory.get("inventory_id"),
         "current_evidence_as_of":evidence_inventory.get("as_of"),
         "real_governed_refresh_packets_supplied":len(refresh_packets),
         "real_governed_refresh_packets_applied":sum(x["eligible_for_comparator"] for x in applied),
         "eligible_non_reference_count":len(eligible),
         "blocked_non_reference_count":len(gated)-len(eligible),
         "applied_refreshes":applied,"user_decision_generated":False,
         "investment_recommendation_generated":False,
         "economic_preference_writeback":False,"controls":deepcopy(FALSE_CONTROLS)}
    if len(eligible)<2:
        out.update({"mode":"NO_COMPARISON",
                    "reason":"FEWER_THAN_TWO_MEANINGFUL_NON_REFERENCE_CAPITAL_USES_ELIGIBLE",
                    "pareto_frontier":[],"vectors":{},"blocked":gated})
        return out
    c=compare_fn(gated+reference_items)
    out.update({"mode":"SHADOW_COMPARISON","pareto_frontier":c["pareto_frontier"],
                "vectors":c["vectors"],"blocked":c["blocked"]})
    return out
