from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/hkcu_p2b_e2_final_contract.json"
EVIDENCE = ROOT / "evidence/hkcu_p2b/HKCU_P2B_E2_COMPANY_EVIDENCE_RANKS_61_77_20260807.csv"


def test_final_contract_is_bounded_and_protected():
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert c["batch_policy"]["required_rank_start"] == 61
    assert c["batch_policy"]["required_rank_end"] == 77
    assert c["batch_policy"]["batch_security_count"] == 17
    assert c["batch_policy"]["required_evidence_rows"] == 51
    assert c["expected_batch_counts"] == {
        "EVIDENCE_COMPLETE": 5,
        "EVIDENCE_PARTIAL": 42,
        "RESEARCH_REQUIRED": 4,
        "evidence_collected_rows": 47,
    }
    assert c["expected_cumulative_after_final"]["cumulative_security_count_started"] == 77
    assert c["acceptance"]["formal_candidate_graduation_allowed"] is False
    assert c["trade_authority"] == "NONE"


def test_final_registry_exact_surface_dates_and_sources():
    df = pd.read_csv(EVIDENCE, dtype={"stock_code_5d": str}, keep_default_na=False)
    assert len(df) == 17
    assert df["security_id"].nunique() == 17
    assert set(df["p2a_overall_rank"].astype(int)) == set(range(61, 78))
    assert "00489" not in set(df["stock_code_5d"].astype(str).str.zfill(5))
    for prefix in ["governance", "earnings", "catalyst"]:
        dates = pd.to_datetime(df[f"{prefix}_date"], errors="raise")
        assert (dates <= pd.Timestamp("2026-08-07")).all()
        assert df[f"{prefix}_title"].astype(str).str.len().gt(0).all()
        assert df[f"{prefix}_summary"].astype(str).str.len().gt(0).all()
    assert df["source_url"].str.startswith("https://www1.hkexnews.hk/").all()


def test_final_status_counts_and_direct_expectation_codes():
    df = pd.read_csv(EVIDENCE, dtype={"stock_code_5d": str}, keep_default_na=False)
    statuses = []
    for prefix in ["governance", "earnings", "catalyst"]:
        statuses.extend(df[f"{prefix}_status"].tolist())
    s = pd.Series(statuses)
    assert int((s == "EVIDENCE_COMPLETE").sum()) == 5
    assert int((s == "EVIDENCE_PARTIAL").sum()) == 42
    assert int((s == "RESEARCH_REQUIRED").sum()) == 4
    direct = set(
        df.loc[df["earnings_status"] == "EVIDENCE_COMPLETE", "stock_code_5d"]
        .astype(str).str.zfill(5)
    )
    assert direct == {"01208", "02157", "03759", "06110", "03339"}


def test_topsports_material_forward_impact_is_explicit_not_inferred():
    df = pd.read_csv(EVIDENCE, dtype={"stock_code_5d": str}, keep_default_na=False)
    row = df[df["stock_code_5d"].astype(str).str.zfill(5) == "06110"].iloc[0]
    assert row["earnings_status"] == "EVIDENCE_COMPLETE"
    text = (row["earnings_title"] + " " + row["earnings_summary"]).lower()
    assert "nike" in text
    assert "significant" in text
    assert "22%" in text


def test_ordinary_results_do_not_masquerade_as_complete_revision():
    df = pd.read_csv(EVIDENCE, dtype={"stock_code_5d": str}, keep_default_na=False)
    partial = df[df["earnings_status"] == "EVIDENCE_PARTIAL"]
    assert not partial["earnings_title"].str.contains(
        "profit alert|profit warning|results estimate|results forecast",
        case=False,
        regex=True,
    ).any()
