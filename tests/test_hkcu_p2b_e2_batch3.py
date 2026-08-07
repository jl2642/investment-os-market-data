from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/hkcu_p2b_e2_batch3_contract.json"
EVIDENCE = ROOT / "evidence/hkcu_p2b/HKCU_P2B_E2_COMPANY_EVIDENCE_RANKS_41_60_20260807.csv"


def test_batch3_contract_is_bounded_and_protected():
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert c["batch_policy"]["required_rank_start"] == 41
    assert c["batch_policy"]["required_rank_end"] == 60
    assert c["batch_policy"]["batch_security_count"] == 20
    assert c["batch_policy"]["required_evidence_rows"] == 60
    assert c["expected_batch_counts"] == {
        "EVIDENCE_COMPLETE": 7,
        "EVIDENCE_PARTIAL": 46,
        "RESEARCH_REQUIRED": 7,
        "evidence_collected_rows": 53,
    }
    assert c["acceptance"]["formal_candidate_graduation_allowed"] is False
    assert c["trade_authority"] == "NONE"


def test_batch3_registry_exact_surface_dates_and_sources():
    df = pd.read_csv(EVIDENCE, dtype={"stock_code_5d": str}, keep_default_na=False)
    assert len(df) == 20
    assert df["security_id"].nunique() == 20
    assert set(df["p2a_overall_rank"].astype(int)) == set(range(41, 61))
    for prefix in ["governance", "earnings", "catalyst"]:
        dates = pd.to_datetime(df[f"{prefix}_date"], errors="raise")
        assert (dates <= pd.Timestamp("2026-08-07")).all()
        assert df[f"{prefix}_title"].astype(str).str.len().gt(0).all()
        assert df[f"{prefix}_summary"].astype(str).str.len().gt(0).all()
    assert df["source_url"].str.startswith("https://www1.hkexnews.hk/").all()


def test_batch3_status_counts_and_direct_expectation_codes():
    df = pd.read_csv(EVIDENCE, dtype={"stock_code_5d": str}, keep_default_na=False)
    statuses = []
    for prefix in ["governance", "earnings", "catalyst"]:
        statuses.extend(df[f"{prefix}_status"].tolist())
    s = pd.Series(statuses)
    assert int((s == "EVIDENCE_COMPLETE").sum()) == 7
    assert int((s == "EVIDENCE_PARTIAL").sum()) == 46
    assert int((s == "RESEARCH_REQUIRED").sum()) == 7
    direct = set(
        df.loc[df["earnings_status"] == "EVIDENCE_COMPLETE", "stock_code_5d"]
        .astype(str).str.zfill(5)
    )
    assert direct == {"03939", "02269", "02145", "02314", "00917", "09696", "09911"}


def test_ordinary_results_do_not_masquerade_as_complete_revision():
    df = pd.read_csv(EVIDENCE, dtype={"stock_code_5d": str}, keep_default_na=False)
    complete = df[df["earnings_status"] == "EVIDENCE_COMPLETE"]
    assert complete["earnings_title"].str.contains(
        "profit alert|results forecast", case=False, regex=True
    ).all()
    partial = df[df["earnings_status"] == "EVIDENCE_PARTIAL"]
    assert not partial["earnings_title"].str.contains(
        "profit alert|results forecast", case=False, regex=True
    ).any()
