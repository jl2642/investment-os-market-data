from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/hkcu_p2b_e2_ranks61_77_decision_synthesis_s4_contract.json"
OVERRIDES = ROOT / "evidence/hkcu_p2b/HKCU_P2B_E2_S4_RANKS61_77_TARGETED_OVERRIDES_20260807.csv"


def test_s4_contract_boundaries():
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert c["program_id"] == "HKCU-P2B-E2-S4"
    assert c["selection_policy"]["rank_start"] == 61
    assert c["selection_policy"]["rank_end"] == 77
    assert c["selection_policy"]["expected_security_count"] == 17
    assert c["selection_policy"]["expected_dimension_rows"] == 51
    assert c["selection_policy"]["expected_partial_rows"] == 43
    assert c["selection_policy"]["expected_non_partial_rows"] == 8
    assert c["selection_policy"]["expected_research_required_rows"] == 0
    assert c["selection_policy"]["expected_targeted_override_rows"] == 7
    assert c["synthesis_policy"]["negated_expectation_terms_must_not_create_blockers"] is True
    assert c["expected_result"]["advance_security_count"] == 15
    assert c["expected_result"]["blocked_security_count"] == 2
    assert set(c["expected_result"]["retained_blocker_security_ids"]) == {"HKEX:02313", "HKEX:06110"}
    assert c["expected_result"]["retained_blocker_event_count"] == 2
    assert c["acceptance"]["formal_candidate_graduation_allowed"] is False
    assert c["acceptance"]["trade_authority"] == "NONE"
    assert c["next_gate"] == "P2B_FINAL_CROSS_SECTIONAL_SYNTHESIS"


def test_targeted_overrides_are_primary_and_deterministic():
    x = pd.read_csv(OVERRIDES, dtype={"stock_code_5d": str}, keep_default_na=False)
    assert len(x) == 7
    assert not x.duplicated(["security_id", "research_dimension"]).any()
    assert x["source_url"].str.startswith("https://www1.hkexnews.hk/").all()
    assert (pd.to_datetime(x["evidence_date"]) <= pd.Timestamp("2026-08-07")).all()
    expected = {
        ("HKEX:01208", "EARNINGS_EXPECTATION_REVISION"),
        ("HKEX:03759", "EARNINGS_EXPECTATION_REVISION"),
        ("HKEX:03759", "CATALYST"),
        ("HKEX:02313", "EARNINGS_EXPECTATION_REVISION"),
        ("HKEX:02313", "CATALYST"),
        ("HKEX:06110", "EARNINGS_EXPECTATION_REVISION"),
        ("HKEX:06110", "CATALYST"),
    }
    assert set(zip(x["security_id"], x["research_dimension"])) == expected
    sh = x[x["security_id"] == "HKEX:02313"]
    assert sh["event_id"].nunique() == 1
    assert sh["final_blocker"].astype(str).str.lower().eq("true").sum() == 1
    ph = x[x["security_id"] == "HKEX:03759"]
    assert ph["event_id"].nunique() == 1
    assert ph["final_direction"].eq("POSITIVE").all()
    top = x[x["security_id"] == "HKEX:06110"]
    assert top["event_id"].nunique() == 1
    assert top["final_direction"].eq("NEGATIVE").all()
    assert top["final_blocker"].astype(str).str.lower().eq("true").sum() == 1


def test_reusable_engine_and_validator_guards_present():
    engine = (ROOT / "pipeline/hkcu_p2b_e2_window_decision_synthesis.py").read_text(encoding="utf-8")
    validator = (ROOT / "scripts/validate_hkcu_p2b_e2_ranks61_77_decision_synthesis.py").read_text(encoding="utf-8")
    assert "--contract" in engine
    assert "cross_dimension_event_deduplication_enabled" in engine
    assert "formal_candidate_graduation_allowed=False" in engine
    assert "alpha_score=pd.NA" in engine
    assert "SHENZHOU_EVENT_LINEAGE" in validator
    assert "TOPSPORTS_EVENT_LINEAGE" in validator
    assert "TOPSPORTS_EARNINGS_CONFIDENCE_CAP" in validator
    assert "P2B_FINAL_CROSS_SECTIONAL_SYNTHESIS" in validator
