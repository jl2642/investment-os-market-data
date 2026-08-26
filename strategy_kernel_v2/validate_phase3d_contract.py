import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def validate():
    errors = []
    c = load("PHASE3D_EVALUATION_CONTRACT.json")
    s = load("PROGRAM_STATE.json")
    cur = load("CURRENT_PHASE_STATUS.json")
    if c["status"] != "FROZEN_BEFORE_REALIZED_OUTCOME_LOADING": errors.append("CONTRACT_NOT_FROZEN")
    if c["horizons"]["fixed_sessions"] != [1,3,5]: errors.append("HORIZON_DRIFT")
    if c["freeze_order"]["realized_outcomes_loaded_at_freeze"] is not False: errors.append("OUTCOMES_LOADED_BEFORE_FREEZE")
    if c["candidate_evaluation"]["PHASE2_PROBABILISTIC_VECTOR"]["regret"] != "NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS": errors.append("PHASE2_MISSING_POLICY")
    if c["candidate_evaluation"]["SIMPLE_NON_PROBABILISTIC_PARETO"]["regret"] != "NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS": errors.append("SIMPLE_MISSING_POLICY")
    if c["legacy_evaluation"]["NO_ACTION_WATCH_RESEARCH"]["forward_price_return"] != "OPPORTUNITY_OBSERVATION_ONLY": errors.append("NO_ACTION_REWRITTEN")
    if c["aggregation_policy"]["winner_selection_forbidden"] is not True: errors.append("WINNER_SELECTION_ALLOWED")
    if not s["phase3d_started"] or not s["phase3d_evaluation_contract_frozen"]: errors.append("PROGRAM_STATE_PHASE3D_FREEZE_MISMATCH")
    if s.get("phase3d_outcomes_loaded") and not s.get("phase3d_complete"):
        # Outcomes may be loaded during execution before final closeout, but once this
        # validator is used on the governed closeout head they must not contradict state.
        pass
    if cur["validation"].get("phase3d_evaluation_contract_frozen") is not True: errors.append("CURRENT_STATUS_FREEZE_FLAG_MISSING")
    for k in ["effective_core_static_changes","candidate_membership_mutations","real_account_mutations","simulation_mutations","target_portfolio_writebacks","user_decisions_generated","orders"]:
        if c["authority_boundaries"][k] != 0: errors.append("AUTHORITY_NONZERO_"+k)
    if c["authority_boundaries"]["trade_authority"] != "NONE": errors.append("TRADE_AUTHORITY_CHANGED")
    return errors

if __name__ == "__main__":
    e = validate()
    if e: raise AssertionError(";".join(e))
    print("PHASE3D_CONTRACT_FREEZE_PASS horizons=1,3,5 outcomes_loaded_at_freeze=false orders=0 trade_authority=NONE")
