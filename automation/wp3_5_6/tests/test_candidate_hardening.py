from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / os.environ.get(
    "WP3_5_6_OUTPUT_DIR",
    "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_5_6/PROPOSALS/WP3_5_6_CANDIDATE_REBUILD_20260724_V1",
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def stable(payload):
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_qualitative_core_retain_policy_is_general_and_source_backed():
    state = read_json(ROOT / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json")
    assert state["counts"]["candidate_core"] == 2
    assert state["counts"]["shadow_track"] == 38
    assert state["counts"]["ready_for_user_decision"] == 0
    assert set(state["qualitative_core_retain_codes"]) == {"000333", "600900"}
    assert state["qualitative_core_retain_policy"] == "PRIOR_GRADUATED_RESEARCH_PLUS_ACTIVE_MEMO_PLUS_COMPLETE_PROSPECTIVE_BASELINE"
    names = {row["security_name"] for row in state["candidate_core_members"]}
    assert names == {"美的集团", "长江电力"}
    assert all(row["entry_baseline_status"] == "COMPLETE" for row in state["candidate_core_members"])
    assert all(row["ready_for_user_decision"] is False for row in state["candidate_core_members"])


def test_candidate_current_semantic_hash_covers_final_payload():
    state = read_json(ROOT / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json")
    claimed = state.pop("semantic_hash")
    assert stable(state) == claimed


def test_candidate_alpha_remains_fail_closed_after_baseline_creation():
    contract = read_json(ROOT / "investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION/CANDIDATE_OUTCOME_CONTRACT.json")
    assert contract["alpha_claim_allowed"] is False
    if "valid_entry_baseline_count" in contract:
        assert contract["valid_entry_baseline_count"] == 2
        assert contract["current_status"] == "BLOCKED_INSUFFICIENT_COMPLETED_EVALUATION_WINDOWS"
        assert contract["completed_evaluation_windows"] == []
        assert contract["fail_closed_until_observation_windows_complete"] is True
    else:
        assert contract["pending_valid_entry_baseline_count_if_pr_merged"] == 2
        assert contract["pending_status_if_pr_merged"] == "BLOCKED_INSUFFICIENT_COMPLETED_EVALUATION_WINDOWS"
        assert contract["current_status_remains_fail_closed_until_merge_and_observation"] is True
    assert contract["trade_authority"] == "NONE"


def test_manifest_records_hardened_core_counts():
    manifest = read_json(OUTPUT / "WP3_5_6_MANIFEST.json")
    assert manifest["metrics"]["candidate_core_proposed"] == 2
    assert manifest["metrics"]["shadow_track_proposed"] == 38
    assert manifest["metrics"]["complete_entry_baselines"] == 2
    assert set(manifest["qualitative_core_retain_codes"]) == {"000333", "600900"}
    if manifest["status"] == "ACCEPTED_ON_MAIN":
        assert manifest["acceptance"]["candidate_state_effective"] is True
        assert manifest["acceptance"]["ready_for_user_decision"] == 0
