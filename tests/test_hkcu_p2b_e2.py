from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def load_evidence():
    return pd.read_csv(
        ROOT / "evidence/hkcu_p2b/HKCU_P2B_E2_COMPANY_EVIDENCE_TOP_QUARTILE_20260807.csv",
        dtype={"stock_code_5d": str}, keep_default_na=False,
    )


def test_e2_contract_is_top_quartile_and_non_trading():
    c = json.loads((ROOT / "config/hkcu_p2b_e2_company_evidence_contract.json").read_text())
    assert c["batch_policy"]["selection_method"] == "P2A_TOP_QUARTILE_BY_ACCEPTED_OVERALL_RANK"
    assert c["batch_policy"]["batch_security_count"] == 20
    assert c["batch_policy"]["required_evidence_rows"] == 60
    assert c["evidence_policy"]["no_alpha_score_in_e2"] is True
    assert c["acceptance"]["formal_candidate_graduation_allowed"] is False
    assert c["trade_authority"] == "NONE"


def test_e2_wide_registry_is_exact_top_quartile():
    x = load_evidence()
    assert len(x) == 20
    assert x["security_id"].is_unique
    assert set(x["p2a_overall_rank"].astype(int)) == set(range(1, 21))
    for prefix in ["governance", "earnings", "catalyst"]:
        assert f"{prefix}_status" in x.columns
        assert f"{prefix}_date" in x.columns
        assert f"{prefix}_title" in x.columns
        assert f"{prefix}_summary" in x.columns
    assert x["source_url"].str.startswith("https://www1.hkexnews.hk/").all()


def test_e2_status_counts_and_direct_expectation_changes():
    x = load_evidence()
    statuses = []
    for prefix in ["governance", "earnings", "catalyst"]:
        statuses.extend(x[f"{prefix}_status"].tolist())
    s = pd.Series(statuses)
    assert (s == "EVIDENCE_COMPLETE").sum() == 3
    assert (s == "EVIDENCE_PARTIAL").sum() == 51
    assert (s == "RESEARCH_REQUIRED").sum() == 6
    complete = x[x["earnings_status"] == "EVIDENCE_COMPLETE"]
    assert set(complete["stock_code_5d"].astype(str).str.zfill(5)) == {"00551", "00966", "01114"}


def test_no_future_evidence_dates():
    x = load_evidence()
    as_of = pd.Timestamp("2026-08-07")
    for prefix in ["governance", "earnings", "catalyst"]:
        dates = pd.to_datetime(x[f"{prefix}_date"], errors="raise")
        assert (dates <= as_of).all()
