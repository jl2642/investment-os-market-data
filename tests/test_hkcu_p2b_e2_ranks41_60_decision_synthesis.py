from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/hkcu_p2b_e2_ranks41_60_decision_synthesis_s3_contract.json"
OVERRIDES = ROOT / "evidence/hkcu_p2b/HKCU_P2B_E2_S3_RANKS41_60_TARGETED_OVERRIDES_20260807.csv"


def test_contract_boundaries():
    c = json.loads(CONTRACT.read_text())
    assert c["program_id"] == "HKCU-P2B-E2-S3"
    assert c["phase"] == "P2B_E2_RANKS41_60_DECISION_SYNTHESIS"
    assert c["selection_policy"]["rank_start"] == 41
    assert c["selection_policy"]["rank_end"] == 60
    assert c["selection_policy"]["expected_security_count"] == 20
    assert c["selection_policy"]["expected_dimension_rows"] == 60
    assert c["selection_policy"]["expected_partial_rows"] == 45
    assert c["selection_policy"]["expected_non_partial_rows"] == 15
    assert c["selection_policy"]["expected_research_required_rows"] == 0
    assert c["selection_policy"]["expected_targeted_override_rows"] == 4
    assert c["expected_result"]["advance_security_count"] == 20
    assert c["expected_result"]["blocked_security_count"] == 0
    assert c["expected_result"]["retained_blocker_security_ids"] == []
    assert c["expected_result"]["retained_blocker_event_count"] == 0
    assert c["acceptance"]["formal_candidate_graduation_allowed"] is False
    assert c["acceptance"]["trade_authority"] == "NONE"
    assert c["next_gate"] == "P2B_E2_RANKS61_77_DECISION_SYNTHESIS"


def test_targeted_primary_overrides():
    x = pd.read_csv(OVERRIDES, dtype={"stock_code_5d": str}, keep_default_na=False)
    assert len(x) == 4
    assert not x.duplicated(["security_id", "research_dimension"]).any()
    assert x["source_url"].str.startswith("https://www1.hkexnews.hk/").all()
    assert (pd.to_datetime(x["evidence_date"]) <= pd.Timestamp("2026-08-07")).all()
    assert set(zip(x["security_id"], x["research_dimension"])) == {
        ("HKEX:03939", "EARNINGS_EXPECTATION_REVISION"),
        ("HKEX:03939", "CATALYST"),
        ("HKEX:09696", "EARNINGS_EXPECTATION_REVISION"),
        ("HKEX:09911", "EARNINGS_EXPECTATION_REVISION"),
    }
    assert not x["final_blocker"].astype(str).str.lower().eq("true").any()


def test_reusable_engine_guards_present():
    t = (ROOT / "pipeline/hkcu_p2b_e2_window_decision_synthesis.py").read_text()
    assert "cross_dimension_event_deduplication_enabled" in t
    assert "fresh_primary_override_guard" in t
    assert "formal_candidate_graduation_allowed=False" in t
    assert "alpha_score=pd.NA" in t
    assert "trade_authority=TRADE_AUTHORITY" in t
