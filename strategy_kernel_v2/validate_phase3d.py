import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from strategy_kernel_v2.historical_replay import CachingRegisteredSourceLoader, build_phase3c_replay, load_default_phase3c_inputs
from strategy_kernel_v2.phase3d_outcome_analysis import build_phase3d_outcomes, CANDIDATE_SENTINEL
from strategy_kernel_v2.program_consistency import validate_program_consistency

SK = ROOT / "strategy_kernel_v2"

def load(name): return json.loads((SK/name).read_text(encoding="utf-8"))

def validate():
    errors = list(validate_program_consistency())
    v=load("PHASE3D_VALIDATION.json"); s=load("PROGRAM_STATE.json"); c=load("CURRENT_PHASE_STATUS.json"); m=load("PHASE3D_OUTCOME_SOURCE_MANIFEST.json")
    if v["status"] != "PASS_COMPLETE_BOUNDED_NEGATIVE_RESULT_MEASURABILITY_NO_COMPARATIVE_MODEL_PERFORMANCE": errors.append("PHASE3D_STATUS_MISMATCH")
    if m["controls"]["horizon_change_count"] != 0: errors.append("HORIZON_CHANGED_AFTER_FREEZE")
    if m["controls"]["candidate_output_synthesis_count"] != 0: errors.append("CANDIDATE_OUTPUT_SYNTHESIZED")
    registry, points = load_default_phase3c_inputs(ROOT); loader=CachingRegisteredSourceLoader(ROOT); replay=build_phase3c_replay(registry, points, source_loader=loader); r=build_phase3d_outcomes(replay,m)
    if loader.read_count != 29 or r["legacy_instance_count"] != 29: errors.append("REAL_REPLAY_COUNT_MISMATCH")
    if r["candidate_security_model_checkpoint_count"] != 100 or r["candidate_group_record_count"] != 14: errors.append("CANDIDATE_COVERAGE_MISMATCH")
    classes=Counter(x["outcome_class"] for x in r["legacy_instance_results"])
    expected={"MEASURABLE_FORWARD_PRICE_RETURN_IF_PRICES_AVAILABLE":5,"OPPORTUNITY_OBSERVATION_ONLY":23,"POSTURE_OUTCOME_OBSERVATION_ONLY_NO_EXECUTED_COUNTERFACTUAL":1}
    if dict(classes) != expected: errors.append("LEGACY_MEASURABILITY_CLASS_MISMATCH")
    if r["retained_only_forward_price_summary"] != v["legacy_measurability"]["retained_only_forward_price_summary"]: errors.append("RETAINED_SUMMARY_DRIFT")
    for row in r["candidate_not_measurable_records"]:
        if any(row[k] != CANDIDATE_SENTINEL for k in ("calibration","regret","return_attribution")): errors.append("CANDIDATE_SENTINEL_DRIFT")
    if r["interpretation_controls"]["candidate_performance_comparison_available"] or r["interpretation_controls"]["cross_model_winner_selected"]: errors.append("INVALID_COMPARATIVE_CONCLUSION")
    if v["legacy_measurability"]["measurable_regret_instances"] != 0 or v["legacy_measurability"]["measurable_calibration_instances"] != 0: errors.append("UNSUPPORTED_LEGACY_METRIC")
    if not s["phase3d_complete"] or not s["phase3d_outcomes_loaded"] or not s["phase3e_start_allowed"] or s["phase3e_started"]: errors.append("PROGRAM_STATE_PHASE3D_CLOSEOUT_MISMATCH")
    if not c["validation"]["phase3d_complete"] or not c["validation"]["phase3e_start_allowed"] or c["validation"]["phase3f_promotion_eligible"]: errors.append("CURRENT_STATUS_PHASE3D_CLOSEOUT_MISMATCH")
    if s["phase3f_promotion_eligible"] or s["phase4_forward_validation_complete"] or s["phase5_migration_allowed"]: errors.append("DOWNSTREAM_GATE_PREMATURE")
    if r["orders"] != 0 or r["trade_authority"] != "NONE": errors.append("AUTHORITY_CHANGED")
    return errors

if __name__ == "__main__":
    e=validate()
    if e: raise AssertionError(";".join(e))
    print("PHASE3D_ACCEPTANCE_PASS legacy=29 retained=5 opportunity_only=23 reduced_observation=1 candidate_instances=100 measurable_regret=0 measurable_calibration=0 phase3e_allowed=true orders=0 trade_authority=NONE")
