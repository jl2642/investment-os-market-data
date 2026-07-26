from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "automation/wp3_3_4/config.json"
ENGINE = ROOT / "automation/wp3_3_4/build_milestone_v4.py"
OVERRIDES = ROOT / "automation/wp3_3_4/core20_strategy_sleeve_overrides.json"


def output_root() -> Path:
    value = os.environ.get(
        "WP3_3_4_OUTPUT_DIR",
        "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_3_4/PROPOSALS/WP3_3_4_PROPOSAL_20260724_V4",
    )
    return ROOT / value


def test_contract_is_proposal_only_and_zero_mutation():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    authority = cfg["authority"]
    assert cfg["contract_version"] == "3.0.0"
    assert set(cfg["strategy_sleeve_gates"]) == {
        "QUALITY_GROWTH",
        "DEFENSIVE_INFRA_YIELD",
        "RESOURCE_CYCLE",
    }
    assert cfg["longlist"]["historical_core20_grandfathering"] is False
    assert overrides["automatic_candidate_decision"] is False
    assert overrides["trade_authority"] == "NONE"
    assert authority["investment_ranking"] is False
    assert authority["research_priority_only"] is True
    assert authority["candidate_membership_mutations"] == 0
    assert authority["research_object_mutations"] == 0
    assert authority["simulation_trade_mutations"] == 0
    assert authority["real_account_mutations"] == 0
    assert authority["orders"] == 0
    assert authority["trade_authority"] == "NONE"


def test_engine_preserves_missing_evidence_profile_separation_and_core20_neutrality():
    text = ENGINE.read_text(encoding="utf-8")
    assert "enhanced_apply_strategy_sleeves" in text
    assert "core20_strategy_sleeve_overrides.json" in text
    assert "THESIS_REBUILD_REQUIRED_BEFORE_CANDIDATE_DECISION" in text
    assert "NOT_AUTOMATIC_REMOVAL" in text
    assert "automatic_removal" in text
    assert "automatic_readmission" in text
    assert "candidate_membership_mutation" in text
    assert "trade_authority" in text


def test_generated_manifest_and_outputs():
    root = output_root()
    manifest = json.loads((root / "WP3_3_4_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "PROPOSAL_ONLY_PENDING_HUMAN_REVIEW"
    assert manifest["as_of_date"] == "2026-07-24"
    assert manifest["contract_version"] == "4.0.0"
    assert manifest["method"] == "INDUSTRY_SLEEVE_TIERED_MULTIDIMENSIONAL_RESEARCH_PRIORITY_NOT_INVESTMENT_RANKING"
    assert manifest["valuation_refresh"] == "PRICE_LINKED_REBASE_ONLY_UNDERLYING_FINANCIAL_PERIOD_UNCHANGED"
    assert manifest["core20_strategy_sleeve_overrides"] == "HISTORICAL_CORE20_REVIEW_ROUTING_ONLY"
    assert manifest["trade_authority"] == "NONE"
    metrics = manifest["metrics"]
    assert metrics["full_market_rows"] == 5525
    assert metrics["historical_core20_review_rows"] == 20
    assert 1 <= metrics["industry_longlist_rows"] <= 60
    assert metrics["deep_dive_rows"] <= 20
    assert metrics["structured_research_rows"] <= 20
    assert metrics["strategy_sleeve_count"] >= 2
    assert metrics["unified_research_workplan_rows"] >= metrics["industry_longlist_rows"]
    assert metrics["candidate_membership_mutations"] == 0
    assert metrics["research_object_mutations"] == 0
    assert metrics["simulation_trade_mutations"] == 0
    assert metrics["real_account_mutations"] == 0
    assert metrics["orders"] == 0


def test_generated_longlist_core20_and_workplan_are_unique_and_non_mutating():
    root = output_root()
    longlist = pd.read_csv(root / "WP3_3_INDUSTRY_LONGLIST.csv", dtype={"security_code": str}, encoding="utf-8-sig")
    core = pd.read_csv(root / "WP3_4_HISTORICAL_CORE20_REVIEW.csv", dtype={"security_code": str}, encoding="utf-8-sig")
    comparison = pd.read_csv(root / "WP3_4_NEW_VS_OLD_CANDIDATE_COMPARISON.csv", dtype={"security_code": str}, encoding="utf-8-sig")
    workplan = pd.read_csv(root / "WP3_3_4_UNIFIED_RESEARCH_WORKPLAN.csv", dtype={"security_code": str}, encoding="utf-8-sig")

    assert len(longlist) <= 60
    assert longlist["security_code"].nunique() == len(longlist)
    assert longlist["candidate_membership_mutation"].fillna(0).astype(int).eq(0).all()
    assert longlist["trade_authority"].eq("NONE").all()
    assert set(longlist["strategy_sleeve"]).issubset(
        {"QUALITY_GROWTH", "DEFENSIVE_INFRA_YIELD", "RESOURCE_CYCLE"}
    )
    deep = longlist[longlist["research_bucket"].eq("A_DEEP_DIVE")]
    if len(deep):
        assert deep["current_market_cap_cny"].ge(10_000_000_000.0).all()
        assert deep["deep_dive_liquidity_gate"].astype(str).str.lower().eq("true").all()
    assert len(core) == 20
    assert core["security_code"].nunique() == 20
    assert core["automatic_removal"].astype(str).str.lower().eq("false").all()
    assert core["automatic_readmission"].astype(str).str.lower().eq("false").all()
    assert core["candidate_membership_mutation"].fillna(0).astype(int).eq(0).all()
    assert comparison["candidate_membership_mutation"].fillna(0).astype(int).eq(0).all()
    assert comparison["trade_authority"].eq("NONE").all()
    assert workplan["security_code"].nunique() == len(workplan)
    assert set(core["security_code"]).issubset(set(workplan["security_code"]))
    assert workplan["candidate_membership_mutation"].fillna(0).astype(int).eq(0).all()
    assert workplan["trade_authority"].eq("NONE").all()


def test_generated_full_market_assessment_has_no_forced_neutral_fill():
    root = output_root()
    frame = pd.read_csv(root / "WP3_3_4_FULL_MARKET_ASSESSMENT.csv", dtype={"security_code": str}, encoding="utf-8-sig")
    assert len(frame) == 5525
    assert frame["security_code"].nunique() == 5525
    assert frame["investment_ranking"].astype(str).str.lower().eq("false").all()
    assert frame["candidate_admission_authority"].astype(str).str.lower().eq("false").all()
    assert frame["trade_authority"].eq("NONE").all()
    financial = frame[frame["strategy_sleeve"].eq("FINANCIAL_SEPARATE_PROFILE")]
    if len(financial):
        assert financial["multidimensional_disposition"].eq("SEPARATE_PROFILE_REVIEW_REQUIRED").all()
        assert financial["financial_score"].isna().all()
    core_overrides = frame[frame["core20_sleeve_override_applied"].astype(str).str.lower().eq("true")]
    assert len(core_overrides) == 8
    rebased = frame[frame["valuation_price_rebase_status"].eq("PRICE_LINKED_REBASE_FROM_FMDL3E_TO_20260724_CURRENT")]
    assert len(rebased) > 0
