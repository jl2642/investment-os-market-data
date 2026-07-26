from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "automation/wp3_3_4/config.json"
ENGINE = ROOT / "automation/wp3_3_4/build_milestone.py"


def output_root() -> Path:
    value = os.environ.get("WP3_3_4_OUTPUT_DIR", ".wp3_3_4_run/WP3_3_4_PROPOSAL_20260724")
    return ROOT / value


def test_contract_is_proposal_only_and_zero_mutation():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    authority = cfg["authority"]
    assert authority["investment_ranking"] is False
    assert authority["research_priority_only"] is True
    assert authority["candidate_membership_mutations"] == 0
    assert authority["research_object_mutations"] == 0
    assert authority["simulation_trade_mutations"] == 0
    assert authority["real_account_mutations"] == 0
    assert authority["orders"] == 0
    assert authority["trade_authority"] == "NONE"


def test_engine_preserves_missing_evidence_and_profile_separation():
    text = ENGINE.read_text(encoding="utf-8")
    assert "weighted_available_score" in text
    assert "SEPARATE_PROFILE_REVIEW_REQUIRED" in text
    assert "CONTROLLED_PROFILE_EXCLUSION" in text
    assert "PRIOR_RESEARCH_REJECTION_REQUIRES_NEW_EVIDENCE" in text
    assert "candidate_membership_mutation" in text
    assert "trade_authority" in text


def test_generated_manifest_and_outputs():
    root = output_root()
    manifest = json.loads((root / "WP3_3_4_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "PROPOSAL_ONLY_PENDING_HUMAN_REVIEW"
    assert manifest["as_of_date"] == "2026-07-24"
    assert manifest["method"] == "MULTIDIMENSIONAL_RESEARCH_PRIORITY_NOT_INVESTMENT_RANKING"
    assert manifest["trade_authority"] == "NONE"
    metrics = manifest["metrics"]
    assert metrics["full_market_rows"] == 5525
    assert metrics["historical_core20_review_rows"] == 20
    assert 1 <= metrics["industry_longlist_rows"] <= 60
    assert metrics["candidate_membership_mutations"] == 0
    assert metrics["research_object_mutations"] == 0
    assert metrics["simulation_trade_mutations"] == 0
    assert metrics["real_account_mutations"] == 0
    assert metrics["orders"] == 0


def test_generated_longlist_and_core20_are_unique_and_non_mutating():
    root = output_root()
    longlist = pd.read_csv(root / "WP3_3_INDUSTRY_LONGLIST.csv", dtype={"security_code": str}, encoding="utf-8-sig")
    core = pd.read_csv(root / "WP3_4_HISTORICAL_CORE20_REVIEW.csv", dtype={"security_code": str}, encoding="utf-8-sig")
    comparison = pd.read_csv(root / "WP3_4_NEW_VS_OLD_CANDIDATE_COMPARISON.csv", dtype={"security_code": str}, encoding="utf-8-sig")

    assert len(longlist) <= 60
    assert longlist["security_code"].nunique() == len(longlist)
    assert longlist["candidate_membership_mutation"].fillna(0).astype(int).eq(0).all()
    assert longlist["trade_authority"].eq("NONE").all()
    assert len(core) == 20
    assert core["security_code"].nunique() == 20
    assert core["automatic_removal"].astype(str).str.lower().eq("false").all()
    assert core["automatic_readmission"].astype(str).str.lower().eq("false").all()
    assert core["candidate_membership_mutation"].fillna(0).astype(int).eq(0).all()
    assert comparison["candidate_membership_mutation"].fillna(0).astype(int).eq(0).all()
    assert comparison["trade_authority"].eq("NONE").all()


def test_generated_full_market_assessment_has_no_forced_neutral_fill():
    root = output_root()
    frame = pd.read_csv(root / "WP3_3_4_FULL_MARKET_ASSESSMENT.csv", dtype={"security_code": str}, encoding="utf-8-sig")
    assert len(frame) == 5525
    assert frame["security_code"].nunique() == 5525
    assert frame["investment_ranking"].astype(str).str.lower().eq("false").all()
    assert frame["candidate_admission_authority"].astype(str).str.lower().eq("false").all()
    assert frame["trade_authority"].eq("NONE").all()
    separate = frame[frame["multidimensional_disposition"].eq("SEPARATE_PROFILE_REVIEW_REQUIRED")]
    if len(separate):
        assert separate["financial_score"].isna().all()
