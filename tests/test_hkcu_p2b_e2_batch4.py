from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/hkcu_p2b_e2_batch4_contract.json"
EVIDENCE = ROOT / "evidence/hkcu_p2b/HKCU_P2B_E2_COMPANY_EVIDENCE_RANKS_61_77_20260807.csv"
DIRECT_CODES = {"01208", "02157", "03759", "02313", "03339"}


def test_batch4_contract_is_final_first_pass_and_protected():
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert c["batch_policy"]["required_rank_start"] == 61
    assert c["batch_policy"]["required_rank_end"] == 77
    assert c["batch_policy"]["batch_security_count"] == 17
    assert c["batch_policy"]["required_evidence_rows"] == 51
    assert c["expected_batch_counts"] == {
        "EVIDENCE_COMPLETE": 5,
        "EVIDENCE_PARTIAL": 43,
        "RESEARCH_REQUIRED": 3,
        "evidence_collected_rows": 48,
    }
    assert c["expected_cumulative_after_batch4"]["cumulative_security_count_started"] == 77
    assert c["acceptance"]["first_pass_company_coverage_complete"] is True
    assert c["acceptance"]["formal_candidate_graduation_allowed"] is False
    assert c["next_gate"] == "P2B_E2_COMPANY_EVIDENCE_DEEPENING"
    assert c["trade_authority"] == "NONE"


def test_batch4_registry_exact_surface_dates_and_sources():
    df = pd.read_csv(EVIDENCE, dtype={"stock_code_5d": str}, keep_default_na=False)
    assert len(df) == 17
    assert df["security_id"].nunique() == 17
    assert set(df["p2a_overall_rank"].astype(int)) == set(range(61, 78))
    for prefix in ["governance", "earnings", "catalyst"]:
        dates = pd.to_datetime(df[f"{prefix}_date"], errors="raise")
        assert (dates <= pd.Timestamp("2026-08-07")).all()
        assert df[f"{prefix}_title"].astype(str).str.len().gt(0).all()
        assert df[f"{prefix}_summary"].astype(str).str.len().gt(0).all()
    assert df["source_url"].str.startswith("https://www1.hkexnews.hk/").all()


def test_batch4_status_counts_and_direct_expectation_codes():
    df = pd.read_csv(EVIDENCE, dtype={"stock_code_5d": str}, keep_default_na=False)
    statuses = []
    for prefix in ["governance", "earnings", "catalyst"]:
        statuses.extend(df[f"{prefix}_status"].tolist())
    s = pd.Series(statuses)
    assert int((s == "EVIDENCE_COMPLETE").sum()) == 5
    assert int((s == "EVIDENCE_PARTIAL").sum()) == 43
    assert int((s == "RESEARCH_REQUIRED").sum()) == 3
    direct = set(
        df.loc[df["earnings_status"] == "EVIDENCE_COMPLETE", "stock_code_5d"]
        .astype(str).str.zfill(5)
    )
    assert direct == DIRECT_CODES


def test_ordinary_results_do_not_masquerade_as_complete_revision():
    df = pd.read_csv(EVIDENCE, dtype={"stock_code_5d": str}, keep_default_na=False)
    complete = df[df["earnings_status"] == "EVIDENCE_COMPLETE"]
    assert complete["earnings_title"].str.contains(
        "profit|estimate|forecast", case=False, regex=True
    ).all()
    partial = df[df["earnings_status"] == "EVIDENCE_PARTIAL"]
    assert not partial["earnings_title"].str.contains(
        "profit alert|profit warning|results forecast|estimate for interim results", case=False, regex=True
    ).any()


def test_research_required_catalysts_are_only_nondirectional_rows():
    df = pd.read_csv(EVIDENCE, dtype={"stock_code_5d": str}, keep_default_na=False)
    rr = set(df.loc[df["catalyst_status"] == "RESEARCH_REQUIRED", "stock_code_5d"].astype(str).str.zfill(5))
    assert rr == {"00371", "03328", "02799"}
