from pathlib import Path
import json

import pandas as pd


def test_p5b_contract_freezes_phase_boundary():
    root = Path(__file__).resolve().parents[1]
    c = json.loads((root / "config/hkcu_p5b_real_pretrade_memo_contract.json").read_text())
    assert c["entry_contract"]["required_p5a_next_gate"] == "P5B_REAL_PRETRADE_MEMO"
    assert c["memo_policy"]["next_gate_on_pass"] == "P5C_USER_DECISION_GATE"
    assert c["memo_policy"]["deferred_weight_may_be_reallocated_automatically"] is False
    assert c["memo_policy"]["exact_asof_close_may_be_fabricated"] is False
    assert c["phase_boundary"]["user_trade_confirmation_record_authorized"] is False
    assert c["phase_boundary"]["manual_execution_checklist_authorized"] is False
    assert c["phase_boundary"]["target_portfolio_writeback_authorized"] is False
    assert c["phase_boundary"]["trade_authority"] == "NONE"


def test_p5b_evidence_surface_has_exact_four_and_softcare_defer():
    root = Path(__file__).resolve().parents[1]
    e = pd.read_csv(root / "evidence/hkcu_p5b/HKCU_P5B_REAL_PRETRADE_EVIDENCE_20260807.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    assert set(e["security_id"]) == {"HKEX:03698", "HKEX:01308", "HKEX:02698", "HKEX:00669"}
    assert len(e) == 4
    assert e["official_source_url"].str.startswith("https://www1.hkexnews.hk/").all()
    assert (pd.to_datetime(e["disclosure_date"]) <= pd.Timestamp("2026-08-07")).all()
    states = dict(zip(e["security_id"], e["memo_state"]))
    assert states["HKEX:02698"] == "DEFER_SECURITY"
    assert sum(v == "ADVANCE_WITH_PRICE_GATE" for v in states.values()) == 3
    soft = e[e["security_id"].eq("HKEX:02698")].iloc[0]
    assert str(soft["fresh_interim_results_required"]).lower() == "true"


def test_pipeline_and_validator_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "pipeline/hkcu_p5b_real_pretrade_memo.py").exists()
    assert (root / "scripts/validate_hkcu_p5b_real_pretrade_memo.py").exists()
