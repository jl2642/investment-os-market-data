from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/hkcu_p2b_e2_rank21_40_contract.json"
EVIDENCE = ROOT / "evidence/hkcu_p2b/HKCU_P2B_E2_COMPANY_EVIDENCE_RANK21_40_20260807.csv"


def test_rank21_40_contract_is_bounded():
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert c["batch_policy"]["required_rank_start"] == 21
    assert c["batch_policy"]["required_rank_end"] == 40
    assert c["batch_policy"]["batch_security_count"] == 20
    assert c["batch_policy"]["required_evidence_rows"] == 60
    assert c["cumulative_acceptance"]["covered_security_count"] == 40
    assert c["protected_state"]["trade_authority"] == "NONE"
    assert c["protected_state"]["formal_candidate_graduation_allowed"] is False


def test_evidence_registry_exact_surface_and_no_future_dates():
    df = pd.read_csv(EVIDENCE, dtype={"stock_code_5d": str}, keep_default_na=False)
    assert len(df) == 20
    assert df["security_id"].nunique() == 20
    assert set(df["p2a_overall_rank"].astype(int)) == set(range(21, 41))
    for prefix in ["governance", "earnings", "catalyst"]:
        dates = pd.to_datetime(df[f"{prefix}_date"], errors="raise")
        assert (dates <= pd.Timestamp("2026-08-07")).all()
        assert df[f"{prefix}_title"].astype(str).str.len().gt(0).all()
        assert df[f"{prefix}_summary"].astype(str).str.len().gt(0).all()
    assert df["source_url"].str.startswith("https://www1.hkexnews.hk/").all()


def test_direct_expectation_change_only_when_explicit():
    df = pd.read_csv(EVIDENCE, dtype={"stock_code_5d": str}, keep_default_na=False)
    complete = df[df["earnings_status"] == "EVIDENCE_COMPLETE"]
    assert len(complete) == 5
    titles = " ".join(complete["earnings_title"].str.upper())
    assert "POSITIVE PROFIT ALERT" in titles
    assert "ESTIMATED RESULTS" in titles
    assert "ESTIMATED PROFIT INCREASE" in titles
    assert "PROFIT WARNING" in titles
    partial = df[df["earnings_status"] == "EVIDENCE_PARTIAL"]
    assert not partial["earnings_title"].str.contains("profit alert|profit warning|profit increase", case=False, regex=True).any()


def test_batch_status_counts_are_expected():
    df = pd.read_csv(EVIDENCE, dtype={"stock_code_5d": str}, keep_default_na=False)
    statuses = []
    for prefix in ["governance", "earnings", "catalyst"]:
        statuses.extend(df[f"{prefix}_status"].tolist())
    s = pd.Series(statuses)
    assert int((s == "EVIDENCE_COMPLETE").sum()) == 5
    assert int((s == "EVIDENCE_PARTIAL").sum()) == 49
    assert int((s == "RESEARCH_REQUIRED").sum()) == 6
