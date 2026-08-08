from pathlib import Path
import json
import re

import pandas as pd


FIXED_MULTIPLE_RE = re.compile(r"(?:<=|>=|<|>)\s*\d+(?:\.\d+)?x\b", re.I)


def test_p5b_contract_freezes_phase_boundary_and_valuation_policy():
    root = Path(__file__).resolve().parents[1]
    c = json.loads((root / "config/hkcu_p5b_real_pretrade_memo_contract.json").read_text())
    assert c["entry_contract"]["required_p5a_next_gate"] == "P5B_REAL_PRETRADE_MEMO"
    assert c["memo_policy"]["next_gate_on_pass"] == "P5C_USER_DECISION_GATE"
    assert c["memo_policy"]["deferred_weight_may_be_reallocated_automatically"] is False
    assert c["memo_policy"]["exact_asof_close_may_be_fabricated"] is False
    assert c["memo_policy"]["undocumented_fixed_valuation_multiple_allowed"] is False
    assert set(c["memo_policy"]["valuation_context_required_at_p5c"]) == {
        "LIVE_EXECUTABLE_PRICE",
        "LATEST_OFFICIAL_EARNINGS",
        "COMPANY_HISTORICAL_VALUATION",
        "RELEVANT_PEER_CONTEXT",
    }
    assert c["phase_boundary"]["user_trade_confirmation_record_authorized"] is False
    assert c["phase_boundary"]["manual_execution_checklist_authorized"] is False
    assert c["phase_boundary"]["target_portfolio_writeback_authorized"] is False
    assert c["phase_boundary"]["trade_authority"] == "NONE"


def test_p5b_evidence_surface_has_exact_four_softcare_defer_and_sitc_annual_lineage():
    root = Path(__file__).resolve().parents[1]
    e = pd.read_csv(
        root / "evidence/hkcu_p5b/HKCU_P5B_REAL_PRETRADE_EVIDENCE_20260807.csv",
        dtype={"stock_code_5d": str},
        keep_default_na=False,
    )
    assert set(e["security_id"]) == {"HKEX:03698", "HKEX:01308", "HKEX:02698", "HKEX:00669"}
    assert len(e) == 4
    assert e["official_source_url"].str.contains("hkexnews.hk/").all()
    supporting = e["supporting_official_source_url"].astype(str).str.strip()
    assert supporting.map(lambda x: (not x) or ("hkexnews.hk/" in x)).all()
    assert (pd.to_datetime(e["disclosure_date"]) <= pd.Timestamp("2026-08-07")).all()
    states = dict(zip(e["security_id"], e["memo_state"]))
    assert states["HKEX:02698"] == "DEFER_SECURITY"
    assert sum(v == "ADVANCE_WITH_PRICE_GATE" for v in states.values()) == 3
    soft = e[e["security_id"].eq("HKEX:02698")].iloc[0]
    assert str(soft["fresh_interim_results_required"]).lower() == "true"
    sitc = e[e["security_id"].eq("HKEX:01308")].iloc[0]
    assert "2026031000179.pdf" in sitc["supporting_official_source_url"]
    assert "OFFICIAL_2025_ANNUAL" in sitc["evidence_maturity"]


def test_p5b_evidence_has_no_undocumented_fixed_multiple_gate():
    root = Path(__file__).resolve().parents[1]
    e = pd.read_csv(
        root / "evidence/hkcu_p5b/HKCU_P5B_REAL_PRETRADE_EVIDENCE_20260807.csv",
        keep_default_na=False,
    )
    assert not e["valuation_gate"].astype(str).map(lambda x: bool(FIXED_MULTIPLE_RE.search(x))).any()
    advanced = e[e["memo_state"].eq("ADVANCE_WITH_PRICE_GATE")]
    assert advanced["valuation_gate"].str.contains("live executable price", case=False).all()
    assert advanced["valuation_gate"].str.contains("history", case=False).all()
    assert advanced["valuation_gate"].str.contains("peer", case=False).all()


def test_pipeline_and_validator_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "pipeline/hkcu_p5b_real_pretrade_memo.py").exists()
    assert (root / "scripts/validate_hkcu_p5b_real_pretrade_memo.py").exists()
