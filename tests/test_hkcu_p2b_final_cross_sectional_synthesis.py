from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/hkcu_p2b_final_cross_sectional_synthesis_contract.json"
BUILDER = ROOT / "pipeline/hkcu_p2b_final_cross_sectional_synthesis.py"
VALIDATOR = ROOT / "scripts/validate_hkcu_p2b_final_cross_sectional_synthesis.py"


def test_contract_freezes_p2b_boundary_and_counts():
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert c["program_id"] == "HKCU-P2B-FINAL"
    assert c["expected_counts"]["security_count"] == 77
    assert c["expected_counts"]["company_dimension_rows"] == 231
    assert c["expected_counts"]["advance_security_count"] == 72
    assert c["expected_counts"]["blocked_security_count"] == 5
    assert set(c["expected_counts"]["blocked_security_ids"]) == {
        "HKEX:00551", "HKEX:01114", "HKEX:09636", "HKEX:02313", "HKEX:06110"
    }
    assert c["expected_counts"]["transaction_tax_complete_count"] == 77
    assert c["expected_counts"]["true_ah_pair_count"] == 13
    assert c["expected_counts"]["ah_numeric_completed_count"] == 13
    assert c["cross_section_policy"]["preserve_p2a_rank"] is True
    assert c["cross_section_policy"]["no_new_composite_alpha_score"] is True
    assert c["cross_section_policy"]["ah_relative_value_is_context_not_alpha"] is True
    assert c["cross_section_policy"]["ah_price_date"] == "2026-08-07"
    assert c["acceptance"]["formal_candidate_graduation_allowed"] is False
    assert c["acceptance"]["trade_authority"] == "NONE"
    assert c["next_gate"] == "P3_0_CANDIDATE_GRADUATION_CONTRACT"


def test_builder_rebuilds_all_accepted_lineage_and_no_alpha():
    text = BUILDER.read_text(encoding="utf-8")
    for token in [
        "hkcu_p2a_build_longlist.py", "validate_hkcu_p2a.py",
        "hkcu_p2b_apply_e1_evidence.py", "validate_hkcu_p2b_e1.py",
        "hkcu_p2b_e2_top20_decision_synthesis.py",
        "hkcu_p2b_e2_window_decision_synthesis.py",
        "ranks21_40", "ranks41_60", "ranks61_77",
    ]:
        assert token in text
    assert "alpha_score\"] = pd.NA" in text
    assert "formal_candidate_graduation_allowed\"] = False" in text
    assert "READY_FOR_P3_CONTRACT_EVALUATION_WITH_CONFIDENCE_CAP" in text
    assert "HOLD_RETAINED_INVESTMENT_BLOCKER" in text


def test_p2a_security_name_schema_is_normalized_fail_closed():
    b = BUILDER.read_text(encoding="utf-8")
    assert "normalize_p2a_security_name" in b
    assert "official_security_name_en" in b
    assert "P2A_SECURITY_NAME_COLUMN_MISSING" in b
    assert "P2A_SECURITY_NAME_MISSING" in b
    assert 'p2a = normalize_p2a_security_name(p2a)' in b
    assert 'security_name_source_column' in b


def test_ah_stage_is_synchronized_and_context_only():
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    b = BUILDER.read_text(encoding="utf-8")
    v = VALIDATOR.read_text(encoding="utf-8")
    assert c["cross_section_policy"]["ah_relative_value_formula"] == "A_close_CNY / (H_close_HKD * CNY_per_HKD) - 1"
    assert "stock_hk_hist" in b
    assert "currency_boc_safe" in b
    assert "HK_PRICE_DATE_MISMATCH" in b
    assert "SAFE_FX_DATE_MISMATCH" in b
    assert "2026-08-07" in v
    assert "AH_FORMULA_RATIO" in v
    assert "AH_FORMULA_DISCOUNT" in v
    assert "AH_ALPHA_SCORE" in v


def test_validator_protects_exact_blockers_and_no_graduation():
    v = VALIDATOR.read_text(encoding="utf-8")
    for sid in ["HKEX:00551", "HKEX:01114", "HKEX:09636", "HKEX:02313", "HKEX:06110"]:
        assert sid in v
    assert "P3_0_CANDIDATE_GRADUATION_CONTRACT" in v
    assert "SEC_CANDIDATE_GRADUATION" in v
    assert "DIM_CANDIDATE_GRADUATION" in v
    assert "TRADE_AUTHORITY" in v
