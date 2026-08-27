from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any

from strategy_kernel_v2.phase3_r2_holdout_h1 import _blob_at
from strategy_kernel_v2.program_consistency import validate_program_consistency
from strategy_kernel_v2.validate_phase3_r2_holdout_h0 import validate as validate_h0
from strategy_kernel_v2.validate_phase3_r2_holdout_h1 import validate as validate_h1

ROOT = Path(__file__).resolve().parent
CONTRACT = ROOT / "PHASE3_R2_HOLDOUT_COVERAGE_EXPANSION_V2_CONTRACT.json"
V2_LEDGER = ROOT / "generated/PHASE3_R2_HOLDOUT_V2_SELECTION_LEDGER.json"


def load(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _git_show_json(repo: Path, sha: str, path: str) -> dict[str, Any]:
    proc = subprocess.run(
        ["git", "show", f"{sha}:{path}"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError("V2_CONTRACT_SOURCE_NOT_AVAILABLE:" + path)
    return json.loads(proc.stdout)


def _collect_security_ids(value: Any, out: set[str] | None = None) -> set[str]:
    if out is None:
        out = set()
    if isinstance(value, list):
        for row in value:
            _collect_security_ids(row, out)
    elif isinstance(value, dict):
        for key, row in value.items():
            if key in {"security_id", "security", "stock_code"} and isinstance(row, str):
                out.add(row)
            _collect_security_ids(row, out)
    return out


def _normalize_security_id(value: str) -> str:
    if len(value) == 6 and value.isdigit():
        if value.startswith("6"):
            return value + ".SH"
        if value[0] in {"0", "1", "2", "3"}:
            return value + ".SZ"
    return value


def _derive_v2_scope(repo: Path, contract: dict[str, Any]) -> list[str]:
    end_sha = contract["unchanged_v1_contract"]["protected_main_universe"]["end_commit_inclusive"]
    registry = load("PHASE3A_EVIDENCE_REGISTRY.json")
    security_ids = {_normalize_security_id(x) for x in registry["scope_security_ids"]}
    contributing_paths = [
        "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_OBJECTS_CURRENT.json",
        "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_QUEUE_D1_CURRENT.json",
        "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_QUEUE_D2_CURRENT.json",
    ]
    for path in contributing_paths:
        data = _git_show_json(repo, end_sha, path)
        security_ids.update(_normalize_security_id(x) for x in _collect_security_ids(data))
    return sorted(security_ids)


def validate() -> list[str]:
    errors = list(validate_program_consistency())
    errors.extend(validate_h0())
    h1_errors, h1 = validate_h1()
    errors.extend(h1_errors)

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    h0 = load("PHASE3_R2_HOLDOUT_SELECTION_CONTRACT.json")
    registry = load("PHASE3A_EVIDENCE_REGISTRY.json")
    state = load("PROGRAM_STATE.json")
    current = load("CURRENT_PHASE_STATUS.json")
    cv = current["validation"]

    if contract.get("status") != "FROZEN_PRE_RESULT_COVERAGE_EXPANSION_NO_R2_NO_OUTCOMES":
        errors.append("V2_CONTRACT_NOT_FROZEN_PRE_RESULT")

    parent = contract["parent_h1"]
    if parent.get("pr") != 322:
        errors.append("V2_PARENT_H1_PR_DRIFT")
    if parent.get("final_head") != "f7647e199a286ed76c31cc207d7f2855ef31739e":
        errors.append("V2_PARENT_H1_HEAD_DRIFT")
    if parent.get("result") != "FAIL_SELECTION_SUFFICIENCY":
        errors.append("V2_PARENT_H1_RESULT_DRIFT")
    if parent.get("selection_ledger_sha256") != h1.get("selection_ledger_sha256"):
        errors.append("V2_PARENT_H1_LEDGER_SHA_DRIFT")
    if parent.get("selected_checkpoint_count") != h1.get("selected_checkpoint_count"):
        errors.append("V2_PARENT_H1_CHECKPOINT_COUNT_DRIFT")
    if parent.get("selected_checkpoint_count") != 8:
        errors.append("V2_PARENT_H1_EXPECTED_8_DRIFT")
    if parent.get("minimum_checkpoint_requirement") != 12:
        errors.append("V2_PARENT_MINIMUM_CHECKPOINT_DRIFT")
    if parent.get("threshold_relaxation_after_result_allowed") is not False:
        errors.append("V2_PARENT_THRESHOLD_RELAXATION_ALLOWED")
    if parent.get("r2_holdout_replay_count") != 0:
        errors.append("V2_PARENT_R2_REPLAY_NONZERO")
    if parent.get("realized_outcomes_used_for_selection_count") != 0:
        errors.append("V2_PARENT_OUTCOME_USE_NONZERO")

    unchanged = contract["unchanged_v1_contract"]
    if unchanged["protected_main_universe"]["start_commit_inclusive"] != h0["frozen_repository_universe"]["start_commit_inclusive"]:
        errors.append("V2_UNIVERSE_START_CHANGED")
    if unchanged["protected_main_universe"]["end_commit_inclusive"] != h0["frozen_repository_universe"]["end_commit_inclusive"]:
        errors.append("V2_UNIVERSE_END_CHANGED")
    if unchanged["selector"]["mode"] != h0["deterministic_selector"]["mode"]:
        errors.append("V2_SELECTOR_MODE_CHANGED")
    if unchanged["selector"]["protected_main_first_parent_only"] is not True:
        errors.append("V2_FIRST_PARENT_GUARD_MISSING")
    for key in (
        "discretionary_subsampling_allowed",
        "random_sampling_allowed",
        "manual_cherry_pick_allowed",
    ):
        if unchanged["selector"][key] is not False:
            errors.append("V2_SELECTOR_DISCRETION_OPEN:" + key)

    v2_seed = unchanged["seed_firewall"]
    h0_seed = h0["seed_firewall"]
    if v2_seed["excluded_commit_shas"] != h0_seed["excluded_commit_shas"]:
        errors.append("V2_SEED_FIREWALL_CHANGED")
    if v2_seed["seven_seed_checkpoints_may_count_as_holdout"] is not False:
        errors.append("V2_SEED_CAN_COUNT_AS_HOLDOUT")
    if v2_seed["exact_seed_source_identity_set_reuse_forbidden"] is not True:
        errors.append("V2_SEED_SOURCE_REUSE_GUARD_MISSING")

    v2q = unchanged["quantitative_sufficiency_gate"]
    h0q = h0["quantitative_sufficiency_gate"]
    for key in (
        "minimum_holdout_checkpoints",
        "minimum_distinct_utc_dates",
        "minimum_distinct_iso_weeks",
        "minimum_distinct_evidence_regime_signatures",
        "minimum_unique_securities",
        "minimum_opportunity_profile_instances",
        "minimum_checkpoints_strictly_outside_seed_time_span",
        "maximum_single_utc_date_fraction",
        "maximum_single_evidence_regime_fraction",
    ):
        if v2q[key] != h0q[key]:
            errors.append("V2_THRESHOLD_CHANGED:" + key)
    if v2q["minimum_holdout_checkpoints"] != 12:
        errors.append("V2_MINIMUM_CHECKPOINT_NOT_12")
    if v2q["threshold_change_after_h1_result_forbidden"] is not True:
        errors.append("V2_POST_RESULT_THRESHOLD_CHANGE_NOT_FORBIDDEN")

    exp = contract["coverage_expansion"]
    added = exp["added_substantive_families"]
    expected_added = [
        "RESEARCH_OBJECTS_CURRENT",
        "R1_DECISION_COVERAGE_PACK_CURRENT",
        "RESEARCH_QUEUE_D1_CURRENT",
        "RESEARCH_QUEUE_D2_CURRENT",
    ]
    if [row["family_id"] for row in added] != expected_added:
        errors.append("V2_ADDED_FAMILY_SET_DRIFT")
    if exp["added_substantive_family_count"] != 4:
        errors.append("V2_ADDED_FAMILY_COUNT_DRIFT")
    if exp["expected_total_family_count_after_expansion"] != 14:
        errors.append("V2_TOTAL_FAMILY_COUNT_DRIFT")
    if exp["v1_family_catalog_preserved"] is not True:
        errors.append("V2_V1_FAMILY_CATALOG_NOT_PRESERVED")

    end_sha = unchanged["protected_main_universe"]["end_commit_inclusive"]
    for row in added:
        if _blob_at(ROOT.parent, end_sha, row["path"]) is None:
            errors.append("V2_ADDED_FAMILY_NOT_AVAILABLE_AT_FROZEN_END:" + row["family_id"])

    r1 = next(row for row in added if row["family_id"] == "R1_DECISION_COVERAGE_PACK_CURRENT")
    if r1["contributes_to_security_scope"] is not False:
        errors.append("V2_R1_MIXED_PACK_EXPANDS_SECURITY_SCOPE")

    excluded = "\n".join(exp["explicitly_excluded_paths_or_classes"])
    for token in (
        "RESEARCH_QUEUE_D2_LIVENESS_CURRENT.json",
        "D2_SEMANTIC_LINEAGE_",
        "RESEARCH_QUEUE_D2_EVIDENCE_",
        "realized_outcomes",
        "future_returns",
        "regret",
        "calibration",
    ):
        if token not in excluded:
            errors.append("V2_REQUIRED_EXCLUSION_MISSING:" + token)

    derived_scope = _derive_v2_scope(ROOT.parent, contract)
    frozen_scope = contract["v2_security_scope"]["security_ids"]
    if derived_scope != frozen_scope:
        errors.append(
            "V2_SECURITY_SCOPE_DERIVATION_DRIFT:"
            + json.dumps({"derived": derived_scope, "frozen": frozen_scope}, ensure_ascii=False)
        )
    if len(frozen_scope) != 18 or contract["v2_security_scope"]["security_count"] != 18:
        errors.append("V2_SECURITY_SCOPE_COUNT_DRIFT")
    if not set(registry["scope_security_ids"]).issubset(set(frozen_scope)):
        errors.append("V2_SECURITY_SCOPE_LOST_V1_MEMBER")

    fw = contract["pre_result_firewall"]
    if fw["v2_selection_started"] is not False:
        errors.append("V2_SELECTION_PREMATURELY_STARTED")
    for key in (
        "v2_candidate_ledger_count",
        "r2_profile_compute_count",
        "r2_holdout_replay_count",
        "realized_outcome_read_count",
        "future_return_read_count",
        "phase3d_result_read_count",
    ):
        if fw[key] != 0:
            errors.append("V2_PRE_RESULT_ACTIVITY_NONZERO:" + key)
    for key in (
        "result_based_family_addition_allowed",
        "result_based_security_addition_allowed",
        "threshold_relaxation_allowed",
        "model_transform_change_allowed",
        "model_signature_change_allowed",
    ):
        if fw[key] is not False:
            errors.append("V2_PRE_RESULT_FIREWALL_OPEN:" + key)
    if V2_LEDGER.exists() and state.get("holdout_v2_selection_complete") is not True:
        errors.append("V2_SELECTION_LEDGER_PREMATURELY_EXISTS")

    gate = contract["next_gate"]
    if gate["v2_selection_start_allowed_after_contract_acceptance"] is not True:
        errors.append("V2_SELECTION_NOT_ALLOWED_AFTER_ACCEPTANCE")
    for key in (
        "v2_r2_replay_allowed_before_v2_selection_sufficiency_pass",
        "h2_start_allowed_now",
        "phase3d_r2_start_allowed_now",
        "phase3e_r2_start_allowed_now",
        "repeat_phase3f_start_allowed_now",
        "phase4_entry_allowed",
    ):
        if gate[key] is not False:
            errors.append("V2_DOWNSTREAM_GATE_PREMATURE:" + key)

    selection_downstream = state.get("holdout_v2_selection_started") is True
    expected_state = {
        "holdout_v2_contract_frozen": True,
        "holdout_v2_contract_status": "FROZEN_PRE_RESULT_COVERAGE_EXPANSION_NO_R2_NO_OUTCOMES",
        "holdout_v2_parent_h1_result": "FAIL_SELECTION_SUFFICIENCY",
        "holdout_v2_v1_thresholds_preserved": True,
        "holdout_v2_protected_main_universe_preserved": True,
        "holdout_v2_seed_firewall_preserved": True,
        "holdout_v2_selector_preserved": True,
        "holdout_v2_added_substantive_family_count": 4,
        "holdout_v2_expanded_security_scope_count": 18,
        "holdout_v2_selection_start_allowed": True,
        "holdout_v2_r2_replay_count": 0,
        "holdout_v2_realized_outcome_read_count": 0,
        "phase3_historical_validation_complete": False,
        "phase4_entry_allowed": False,
    }
    for key, expected in expected_state.items():
        if state.get(key) != expected:
            errors.append("V2_STATE_DRIFT:" + key)
        if cv.get(key) != expected:
            errors.append("V2_CURRENT_VALIDATION_DRIFT:" + key)

    if selection_downstream:
        if state.get("holdout_v2_selection_complete") is not True:
            errors.append("V2_LEGAL_SELECTION_DOWNSTREAM_NOT_COMPLETE")
        if state.get("holdout_v2_candidate_ledger_count", 0) <= 0:
            errors.append("V2_LEGAL_SELECTION_DOWNSTREAM_LEDGER_EMPTY")
        if state.get("holdout_h2_started") is not False:
            errors.append("V2_LEGAL_SELECTION_DOWNSTREAM_PREMATURE_H2")
        selection_pass = state.get("holdout_v2_selection_outcome") == "PASS_SELECTION_SUFFICIENCY"
        if state.get("holdout_h2_start_allowed") is not selection_pass:
            errors.append("V2_LEGAL_SELECTION_DOWNSTREAM_H2_GATE_DRIFT")
        if state.get("holdout_coverage_expansion_required") is not (not selection_pass):
            errors.append("V2_LEGAL_SELECTION_DOWNSTREAM_COVERAGE_GATE_DRIFT")
        expected_next = (
            "INDEPENDENT_POINT_IN_TIME_HOLDOUT_R2_REPLAY"
            if selection_pass
            else "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE_EXPANSION"
        )
        if current.get("next_phase") != expected_next:
            errors.append("V2_LEGAL_SELECTION_DOWNSTREAM_NEXT_PHASE_DRIFT")
    else:
        for key, expected in (
            ("holdout_v2_selection_started", False),
            ("holdout_v2_candidate_ledger_count", 0),
            ("holdout_h2_start_allowed", False),
            ("holdout_coverage_expansion_required", True),
        ):
            if state.get(key) != expected or cv.get(key) != expected:
                errors.append("V2_PRESELECTION_STATE_DRIFT:" + key)
        if current.get("next_phase") != "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE_EXPANSION":
            errors.append("V2_NEXT_PHASE_DRIFT")

    if current.get("current_phase") != "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE":
        errors.append("V2_CURRENT_PHASE_DRIFT")

    for surface_name, surface in (
        ("CONTRACT", contract["authority_boundaries"]),
        ("STATE", state),
        ("CURRENT", current),
    ):
        for key in (
            "effective_core_static_changes",
            "candidate_membership_mutations",
            "real_account_mutations",
            "simulation_mutations",
            "target_portfolio_writebacks",
            "user_decisions_generated",
            "orders",
        ):
            if key in surface and surface[key] != 0:
                errors.append(f"{surface_name}_AUTHORITY_NONZERO_{key}")
        if surface.get("trade_authority") != "NONE":
            errors.append(f"{surface_name}_TRADE_AUTHORITY_CHANGED")

    return errors


if __name__ == "__main__":
    errors = validate()
    if errors:
        raise AssertionError(";".join(errors))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    print(
        "PHASE3_R2_HOLDOUT_V2_CONTRACT_ACCEPTANCE_PASS "
        "parent_h1=FAIL_SELECTION_SUFFICIENCY parent_checkpoints=8 minimum_checkpoints=12 "
        "added_families=4 expanded_securities=18 v2_selection_started=false "
        "v2_ledger=0 r2_replays=0 outcomes_read=0 h2_start_allowed=false "
        "phase3_historical_validation_complete=false phase4_entry_allowed=false "
        "orders=0 trade_authority=NONE"
    )
