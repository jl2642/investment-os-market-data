from __future__ import annotations

import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def load(name):
    return json.loads((ROOT/name).read_text(encoding="utf-8"))

def validate():
    e=[]
    c=load("PHASE4_P4_5_CLEAN_BASELINE_FORWARD_VALIDATION_CONTRACT.json")
    s=load("PROGRAM_STATE.json")
    a=load("PROGRAM_AMENDMENT_A1.json")

    if c.get("status")!="FROZEN_PRE_BASELINE_IMPLEMENTATION": e.append("P45_NOT_FROZEN")
    p=c.get("parent",{})
    if p.get("p4_4_status")!="COMPLETE_ACCEPTED": e.append("P45_P44_NOT_ACCEPTED")
    if p.get("p4_4_contract_exact_head_workflows_success")!=34 or p.get("p4_4_contract_exact_head_workflows_failure")!=0:
        e.append("P45_P44_WORKFLOWS")
    if p.get("phase4_forward_observation_count")!=0 or p.get("phase4_realized_outcome_read_count")!=0:
        e.append("P45_PREBASELINE_EVIDENCE_NONZERO")

    old=c.get("superseded_v1_forward_contract",{})
    if old.get("pr")!=333 or old.get("v1_forward_observation_count")!=0 or old.get("v1_realized_outcome_read_count")!=0:
        e.append("P45_V1_AUDIT_BOUNDARY")
    if old.get("old_cutoff_eligible_for_effective_phase4_observations") is not False:
        e.append("P45_OLD_CUTOFF_STILL_ACTIVE")
    if old.get("semantics_preserved_except_new_clean_cutoff_and_production_source_binding") is not True:
        e.append("P45_V1_SEMANTICS_NOT_PRESERVED")

    base=c.get("clean_baseline_materialization",{})
    if base.get("accepted_cutoff_value_rule")!="EXACT_OPERATING_CURRENT_BASELINE_RECEIPT_PUBLISHED_AT_UTC":
        e.append("P45_CUTOFF_RULE")
    for k in [
        "baseline_is_immutable_after_first_acceptance",
        "accepted_cutoff_is_materialized_only_by_first_successful_main_based_baseline_publication",
        "cutoff_may_not_be_backdated",
        "cutoff_may_not_equal_old_pr333_cutoff",
        "pre_cutoff_recommendation_or_shadow_events_permanently_ineligible",
    ]:
        if base.get(k) is not True: e.append("P45_BASELINE_"+k)
    if base.get("baseline_freeze_may_not_increment_forward_observation_count") is not True:
        e.append("P45_BASELINE_OBSERVATION_LEAK")
    if base.get("baseline_freeze_may_not_read_realized_outcomes") is not True:
        e.append("P45_BASELINE_OUTCOME_LEAK")

    selector=c.get("forward_checkpoint_selector",{})
    if selector.get("selector")!="CENSUS_OF_ALL_ELIGIBLE_DISTINCT_POST_CUTOFF_GOVERNED_D2_SOURCE_COMMITS":
        e.append("P45_SELECTOR")
    if selector.get("primary_trigger_domain")!="RESEARCH_D2": e.append("P45_TRIGGER_DOMAIN")
    if selector.get("mere_schedule_rerun_may_create_checkpoint") is not False:
        e.append("P45_RERUN_FALSE_FRESHNESS")
    if selector.get("same_semantic_d2_state_with_new_runtime_timestamp_may_create_checkpoint") is not False:
        e.append("P45_TIMESTAMP_FALSE_FRESHNESS")
    if selector.get("manual_result_driven_checkpoint_selection_allowed") is not False:
        e.append("P45_RESULT_DRIVEN_SELECTION")
    if selector.get("incomplete_eligible_checkpoint_may_be_silently_dropped") is not False:
        e.append("P45_SILENT_DROP")
    if selector.get("model_output_failure_is_evidence_not_exclusion") is not True:
        e.append("P45_MODEL_FAILURE_EXCLUSION")

    packet=c.get("shared_parallel_packet",{})
    for k in [
        "model_specific_evidence_fetch_forbidden",
        "later_evidence_backfill_forbidden",
        "same_packet_for_legacy_and_r2",
        "missingness_preserved",
        "source_commit_path_blob_identity_required",
        "new_feature_mapping_during_phase4_forbidden",
        "unsupported_evidence_remains_uninterpreted",
    ]:
        if packet.get(k) is not True: e.append("P45_PACKET_"+k)

    runners=c.get("runner_set",{})
    legacy=runners.get("legacy",{})
    r2=runners.get("candidate",{})
    if legacy.get("model_form")!="LEGACY_POLICY_BASELINE" or legacy.get("ordinalization_forbidden") is not True:
        e.append("P45_LEGACY")
    if r2.get("model_form")!="EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2":
        e.append("P45_R2_IDENTITY")
    if r2.get("model_version")!="R2.0.1_RESEARCH" or r2.get("transform_rule_count")!=20:
        e.append("P45_R2_VERSION")
    if r2.get("comparison_method")!="PARETO_WITHIN_EXACT_COMPARISON_SIGNATURE":
        e.append("P45_R2_COMPARISON")
    for k in ["scalar_policy_score_allowed","dimension_weights_allowed","cross_signature_dominance_allowed"]:
        if r2.get(k) is not False: e.append("P45_R2_FORBIDDEN_"+k)

    meas=c.get("economic_measurement",{})
    if meas.get("fixed_horizon_exchange_sessions")!=[1,3,5]: e.append("P45_HORIZONS")
    if meas.get("outcomes_may_be_loaded_only_after_horizon_maturity") is not True:
        e.append("P45_OUTCOME_MATURITY")
    if meas.get("result_based_endpoint_dropping_allowed") is not False:
        e.append("P45_RESULT_DROP")

    suff=c.get("forward_sufficiency_gate",{})
    expected={
        "minimum_complete_economically_mature_parallel_cycles":12,
        "minimum_distinct_utc_dates":6,
        "minimum_distinct_iso_weeks":4,
        "minimum_distinct_evidence_regimes":4,
        "minimum_unique_securities":6,
        "minimum_r2_profile_instances":48,
        "minimum_distinct_r2_dominance_edges":24,
        "minimum_distinct_comparison_signatures":2,
        "minimum_distinct_edges_per_observed_signature":6,
    }
    for k,v in expected.items():
        if suff.get(k)!=v: e.append("P45_SUFF_"+k)
    if suff.get("thresholds_may_change_after_forward_results") is not False:
        e.append("P45_THRESHOLD_MUTATION")

    summaries=c.get("mandatory_forward_summaries",{})
    if summaries.get("aggregation_schemes")!=["EQUAL_EDGE","EQUAL_CHECKPOINT","EQUAL_SIGNATURE"]:
        e.append("P45_AGG")
    for k in ["signature_stratum_summaries_required","leave_one_security_out_required","leave_one_signature_out_required"]:
        if summaries.get(k) is not True: e.append("P45_SUMMARY_"+k)
    if summaries.get("legacy_disposition_ordinalization_forbidden") is not True:
        e.append("P45_LEGACY_ORDINAL")

    gate=c.get("completion_gate",{})
    d=gate.get("directional_requirements",{})
    if float(d.get("minimum_concordance_rate",-1))!=0.5 or float(d.get("minimum_mean_edge_return_spread",-1))!=0.0:
        e.append("P45_DIRECTIONAL_THRESHOLDS")
    if gate.get("pass_does_not_authorize_migration_execution") is not True:
        e.append("P45_MIGRATION_EXECUTION_OPEN")
    if gate.get("pass_only_authorizes_separate_phase5_governed_migration_proposal") is not True:
        e.append("P45_PHASE5_PROPOSAL_BOUNDARY")

    if a["effective_execution_control"].get("effective_forward_observation_start_allowed"):
        e.append("P45_A1_PREBASELINE_START_OPEN")
    if s.get("phase4_p4_4_complete") is not True: e.append("P45_STATE_P44")
    if s.get("phase4_reconciliation_current_stage")!="P4_5_CLEAN_BASELINE_FORWARD_PARALLEL_SHADOW_VALIDATION":
        e.append("P45_STATE_STAGE")
    if s.get("phase4_p4_5_contract_frozen") is not True: e.append("P45_STATE_CONTRACT")
    if s.get("phase4_p4_5_baseline_implementation_started") is not False:
        e.append("P45_STATE_IMPL")
    if s.get("phase4_p4_5_clean_baseline_accepted") is not False:
        e.append("P45_STATE_BASELINE_PREMATURE")
    if s.get("phase4_p4_5_effective_cutoff_utc") is not None:
        e.append("P45_STATE_CUTOFF_PREMATURE")
    if s.get("phase4_effective_forward_observation_start_allowed") is not False:
        e.append("P45_STATE_START_PREMATURE")
    if s.get("phase4_forward_observation_count")!=0 or s.get("phase4_realized_outcome_read_count")!=0:
        e.append("P45_STATE_EVIDENCE_NONZERO")
    if s.get("phase5_migration_allowed") is not False:
        e.append("P45_STATE_PHASE5_PREMATURE")

    for k,v in c.get("protected_state",{}).items():
        if k=="trade_authority":
            if v!="NONE": e.append("P45_TRADE")
        elif v!=0:
            e.append("P45_PROTECTED_"+k)
    return sorted(set(e))

if __name__=="__main__":
    err=validate()
    if err: raise AssertionError(";".join(err))
    print("PHASE4_P4_5_CLEAN_BASELINE_FORWARD_VALIDATION_CONTRACT_PASS baseline=pending observations=0 outcomes=0 phase5=false orders=0 trade_authority=NONE")
