from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

MAIN_SCHEMA = "2.1.0-shadow"

@dataclass(frozen=True)
class AuthorityBoundary:
    orders: int = 0
    trade_authority: str = "NONE"
    economic_state_mutation_authorized: bool = False
    candidate_membership_mutation_authorized: bool = False
    target_portfolio_writeback_authorized: bool = False
    real_position_change_authorized: bool = False
    simulation_position_change_authorized: bool = False
    order_authorized: bool = False
    implementation_ready: bool = False
    def validate(self) -> None:
        if self.orders != 0 or self.trade_authority != "NONE": raise ValueError("shadow authority boundary violated")
        if any((self.economic_state_mutation_authorized,self.candidate_membership_mutation_authorized,self.target_portfolio_writeback_authorized,self.real_position_change_authorized,self.simulation_position_change_authorized,self.order_authorized,self.implementation_ready)): raise ValueError("shadow object cannot authorize economic writeback")

@dataclass(frozen=True)
class Scenario:
    name: str
    probability: float
    annualized_total_return: float

@dataclass
class DecisionObject:
    security_id: str
    as_of: str
    main_sha: str
    evidence_completeness: float
    evidence_confidence: float
    material_gaps: List[str]
    thesis: str
    kill_conditions: List[str]
    valuation_state: str
    valuation_method: str
    valuation_confidence: float
    scenarios: List[Scenario]
    current_weight: float
    execution_feasibility: str
    comparability_state: str
    research_action: str
    economic_preference: str
    reason_codes: List[str]
    source_paths: List[str] = field(default_factory=list)
    authority: AuthorityBoundary = field(default_factory=AuthorityBoundary)
    schema_version: str = MAIN_SCHEMA
    def validate(self) -> None:
        if self.schema_version != MAIN_SCHEMA or not self.main_sha: raise ValueError("invalid shadow provenance")
        if self.valuation_state not in {"UNAVAILABLE","INCOMPLETE","AVAILABLE_SHADOW","DECISION_GRADE"}: raise ValueError("invalid valuation_state")
        if self.scenarios:
            if abs(sum(s.probability for s in self.scenarios)-1.0)>1e-6: raise ValueError("scenario probabilities must sum to 1")
        elif self.valuation_state in {"AVAILABLE_SHADOW","DECISION_GRADE"}: raise ValueError("available valuation requires explicit scenarios")
        if not self.scenarios and self.comparability_state != "NOT_COMPARABLE": raise ValueError("missing valuation cannot be capital-comparable")
        self.authority.validate()
    def expected_annualized_return(self) -> Optional[float]:
        self.validate()
        if not self.scenarios: return None
        return sum(s.probability*s.annualized_total_return for s in self.scenarios)
    def to_dict(self) -> Dict[str, Any]:
        self.validate(); return asdict(self)

class RepoDecisionAdapter:
    """Pure adapter over already-read Canonical payloads. No GitHub I/O and no writeback."""
    def __init__(self, main_sha: str):
        if not main_sha: raise ValueError("main_sha required")
        self.main_sha=main_sha
    @staticmethod
    def _holding(payload: Dict[str, Any], security_id: str) -> Dict[str, Any]:
        for h in payload.get("holdings",[]):
            if h.get("security_id")==security_id: return h
        raise KeyError(security_id)
    def industrial_fulian(self, decision: Dict[str, Any], simulation: Dict[str, Any]) -> DecisionObject:
        h=self._holding(simulation,"601138.SH"); total=float(simulation.get("summary",{}).get("account_total_assets") or 0); weight=float(h.get("market_value",0))/total if total else 0.0
        canonical_hold=decision.get("status")=="TRIM_REVIEW_APPROVED_NO_TRADE_MONITORING_ACTIVE" and decision.get("formal_plan",{}).get("current_action")=="HOLD_600_SHARES_NO_ADD_NO_TRADE"
        return DecisionObject("601138.SH",h.get("mark_as_of","UNKNOWN"),self.main_sha,.72,.72,["NO_CURRENT_PROBABILITY_WEIGHTED_VALUATION_SCENARIOS"],decision.get("fundamental_trigger_assessment",{}).get("current_judgment","LEGACY_THESIS_NOT_FULLY_MAPPED"),list(decision.get("fundamental_trigger_assessment",{}).get("trim_or_exit_triggers",[])),"INCOMPLETE","LEGACY_BASE_CASE_REFERENCE_ONLY",.45,[],weight,"FEASIBLE","NOT_COMPARABLE","MONITOR" if canonical_hold else "REUNDERWRITE","HOLD_CURRENT" if canonical_hold else "UNRANKED",["LEGACY_USER_DECISION_CONSUMED","NO_TRADE_MONITORING_ACTIVE"] if canonical_hold else ["LEGACY_STATE_UNMAPPED"],["investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_INDUSTRIAL_FULIAN_TRIM_REVIEW_CURRENT.json","investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"])
    def jovo_energy(self, real: Dict[str, Any]) -> DecisionObject:
        h=self._holding(real,"605090.SH"); total=float(real.get("summary",{}).get("account_total_assets") or 0); weight=float(h.get("market_value",0))/total if total else 0.0; reasons=["PORTFOLIO_CONCENTRATION_DIAGNOSTIC_ONLY"]
        if weight>=.40: reasons.append("HIGH_SINGLE_NAME_CONCENTRATION")
        return DecisionObject("605090.SH",h.get("mark_as_of","UNKNOWN"),self.main_sha,.45,.55,["NO_CANONICAL_DECISION_GRADE_VALUATION_SCENARIOS","H1_FUNDAMENTAL_REUNDERWRITE_REQUIRED_BEFORE_POSITION_CHANGE"],"Position state establishes concentration, not a complete investment underwriting.",[],"UNAVAILABLE","UNAVAILABLE_FROM_CURRENT_POSITION_STATE",0.0,[],weight,"FEASIBLE","NOT_COMPARABLE","REUNDERWRITE","HOLD_CURRENT",reasons,["investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json"])
    def techtronic(self, decision: Dict[str, Any], latest_completed_close_hkd: Optional[float]=None) -> DecisionObject:
        action="MONITOR"; reasons=["BUY_REVIEW_ACCEPTED_NO_TRADE","PRICE_TRIGGER_IS_RESEARCH_ONLY","SIZING_GATE_ACTIVE"]
        if latest_completed_close_hkd is not None and latest_completed_close_hkd<=135: action="REUNDERWRITE"; reasons.append("PRICE_REOPENS_RESEARCH_ONLY")
        return DecisionObject("HKEX:00669",str(decision.get("source_lineage",{}).get("review_anchor_date","UNKNOWN")),self.main_sha,.75,.75,["FRESH_COMPLETED_CLOSE_REQUIRED_BEFORE_FUTURE_TRADE_DECISION","ACTUAL_BROKER_POSITION_GRANULARITY_UNCONFIRMED"],decision.get("fundamental_monitoring",{}).get("current_thesis_state","LEGACY_THESIS_NOT_FULLY_MAPPED"),list(decision.get("fundamental_monitoring",{}).get("buy_review_invalidates_if",[])),"INCOMPLETE","LEGACY_PRICE_BAND_REVIEW_NOT_EXPECTED_RETURN_MODEL",.55,[],0.0,"CONSTRAINED" if decision.get("portfolio_sizing_review",{}).get("board_lot_sizing_mismatch") else "UNKNOWN","NOT_COMPARABLE",action,"UNRANKED",reasons,["investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/HKCU_TTI_00669_BUY_REVIEW_CURRENT.json"])
    def d2_research(self, item: Dict[str, Any]) -> DecisionObject:
        status=item.get("status",""); gaps=[]
        if item.get("evidence_gap"): gaps.append(str(item["evidence_gap"]))
        gaps.append("NO_DECISION_GRADE_PROBABILITY_WEIGHTED_VALUATION_IMPORTED"); complete=status=="D2_RESEARCH_COMPLETE"
        return DecisionObject(item.get("security_id","UNKNOWN"),"D2_CURRENT",self.main_sha,.80 if complete else .60,.75 if complete else .55,gaps,str(item.get("research_disposition","D2 research state; no capital preference inferred")),[item["first_rejection"]] if item.get("first_rejection") else [],"UNAVAILABLE","D2_RESEARCH_NOT_IMPORTED_AS_DECISION_VALUATION",0.0,[],0.0,"UNKNOWN","NOT_COMPARABLE","HOLD_RESEARCH" if complete else "DEEPEN_RESEARCH","UNRANKED",["D2_RESEARCH_COMPLETE","NO_DECISION_PROMOTION"] if complete else ["D2_MATERIAL_EVIDENCE_GAP","RESEARCH_STATUS_NOT_INVESTMENT_PREFERENCE"],["investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_QUEUE_D2_CURRENT.json"])
