from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / os.environ.get(
    "WP3_5_6_OUTPUT_DIR",
    "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_5_6/PROPOSALS/WP3_5_6_CANDIDATE_REBUILD_20260724_V1",
)

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def test_manifest_and_authority_boundaries():
    manifest = read_json(OUTPUT / "WP3_5_6_MANIFEST.json")
    assert manifest["status"] == "CANDIDATE_STATE_CHANGE_PROPOSAL_PENDING_USER_MERGE"
    assert manifest["as_of_date"] == "2026-07-24"
    assert manifest["candidate_state_change_authority"] == "USER_MERGE_OF_GOVERNED_PR"
    assert manifest["metrics"]["unified_workplan_rows"] == 73
    assert manifest["metrics"]["research_object_proposals"] == 73
    assert manifest["metrics"]["historical_core20_review_rows"] == 20
    assert manifest["metrics"]["real_account_mutations"] == 0
    assert manifest["metrics"]["simulation_trade_mutations"] == 0
    assert manifest["metrics"]["orders"] == 0
    assert manifest["trade_authority"] == "NONE"

def test_research_objects_are_not_silently_decision_grade():
    rows = read_jsonl(OUTPUT / "WP3_5_RESEARCH_OBJECT_PROPOSALS.jsonl")
    assert len(rows) == 73
    assert len({row["security_id"] for row in rows}) == 73
    assert all(row["decision_grade"] is False for row in rows)
    assert all(row["trade_authority"] == "NONE" for row in rows)
    assert any(row["lifecycle_state"] == "ACTIVE_RESEARCH" for row in rows)
    assert any(row["research_gaps"] for row in rows)

def test_entry_baselines_are_prospective_and_gated():
    rows = read_jsonl(OUTPUT / "WP3_5_ENTRY_BASELINE_PROPOSALS.jsonl")
    assert len(rows) == 73
    assert all(row["prospective_only"] is True for row in rows)
    assert all(row["historical_backfill"] is False for row in rows)
    for row in [x for x in rows if x["status"] == "COMPLETE"]:
        assert row["entry_date"] == "2026-07-24"
        assert row["entry_price"] is not None
        assert row["entry_valuation"] is not None
        assert row["benchmark"]
        assert row["thesis_id"]
        assert row["trade_authority"] == "NONE"

def test_candidate_rebuild_is_explicit_and_no_ready_overclaim():
    proposal = pd.read_csv(OUTPUT / "WP3_6_CANDIDATE_REBUILD_PROPOSAL.csv", dtype={"security_code": str}, encoding="utf-8-sig")
    assert len(proposal) == 73
    assert proposal["security_code"].nunique() == 73
    assert proposal["buy_signal"].eq("NO").all()
    assert proposal["real_account_permission"].astype(str).str.lower().eq("false").all()
    assert proposal["simulation_admission_permission"].astype(str).str.lower().eq("false").all()
    assert proposal["trade_authority"].eq("NONE").all()
    assert len(proposal[proposal["ready_for_user_decision"].astype(str).str.lower().eq("true")]) == 0
    core = proposal[proposal["proposed_candidate_route"].eq("CANDIDATE_CORE_PROPOSED")]
    assert len(core) >= 1
    assert core["entry_baseline_status"].eq("COMPLETE").all()

def test_historical_core20_has_no_grandfathering_or_automatic_removal():
    migration = pd.read_csv(OUTPUT / "WP3_6_HISTORICAL_CORE20_MIGRATION.csv", dtype={"security_code": str}, encoding="utf-8-sig")
    assert len(migration) == 20
    assert migration["security_code"].nunique() == 20
    assert migration["automatic_removal"].astype(str).str.lower().eq("false").all()
    assert migration["automatic_readmission"].astype(str).str.lower().eq("false").all()
    assert migration["user_merge_required"].astype(str).str.lower().eq("true").all()
    assert migration["trade_authority"].eq("NONE").all()

def test_candidate_current_preserves_history_and_requires_user_merge():
    state = read_json(ROOT / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json")
    assert state["status"] == "ACCEPTED_ON_MAIN_IF_GOVERNED_PR_MERGED"
    assert state["candidate_state_change_authority"] == "USER_MERGE_OF_GOVERNED_PR"
    assert state["historical_core20_grandfathering"] is False
    assert len(state["historical_core20_archive"]) == 20
    assert state["counts"]["historical_core20"] == 20
    assert state["counts"]["candidate_core"] >= 1
    assert state["counts"]["ready_for_user_decision"] == 0
    assert state["state_boundaries"]["real_account_mutations"] == 0
    assert state["state_boundaries"]["simulation_trade_mutations"] == 0
    assert state["state_boundaries"]["orders"] == 0
    assert state["state_boundaries"]["trade_authority"] == "NONE"
