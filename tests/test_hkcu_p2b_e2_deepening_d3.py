from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/hkcu_p2b_e2_deepening_d3_contract.json"
EVIDENCE = ROOT / "evidence/hkcu_p2b/HKCU_P2B_E2_D3_TOP20_HIGH_BLOCKER_EVIDENCE_20260807.csv"


def load():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    df = pd.read_csv(EVIDENCE, dtype={"stock_code_5d": str}, keep_default_na=False)
    return contract, df


def truthy(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().isin(["true", "1"])


def test_contract_and_exact_high_blocker_surface():
    c, df = load()
    assert c["program_id"] == "HKCU-P2B-E2-D3"
    assert c["selection_policy"]["expected_target_rows"] == 14
    assert c["selection_policy"]["expected_security_count"] == 9
    assert len(df) == 14
    assert df["security_id"].nunique() == 9
    assert not df.duplicated(["security_id", "research_dimension"]).any()


def test_resolution_status_and_post_blocker_are_fail_closed():
    c, df = load()
    allowed = set(c["evidence_policy"]["allowed_resolution_statuses"])
    cleared = set(c["evidence_policy"]["cleared_statuses"])
    retained = set(c["evidence_policy"]["retained_statuses"])
    assert set(df["resolution_status"]).issubset(allowed)
    post = truthy(df["post_blocker"])
    assert (~post).sum() == 9
    assert post.sum() == 5
    assert df.loc[~post, "resolution_status"].isin(cleared).all()
    assert df.loc[post, "resolution_status"].isin(retained).all()


def test_sources_are_primary_official_and_not_future_dated():
    c, df = load()
    as_of = pd.Timestamp(c["selection_policy"]["as_of_date"])
    assert pd.to_datetime(df["evidence_date"], errors="raise").le(as_of).all()
    assert df["source_url"].str.startswith(("https://www1.hkexnews.hk/", "https://www.hkexnews.hk/")).all()
    secondary = df["secondary_source_url"].astype(str).str.strip()
    assert secondary[(secondary != "")].str.startswith(("https://www1.hkexnews.hk/", "https://www.hkexnews.hk/")).all()
    for col in ["evidence_title", "evidence_summary", "resolution_rationale", "monitor_trigger", "remaining_question", "cross_dimension_signal"]:
        assert df[col].astype(str).str.strip().ne("").all()


def test_pending_spinoffs_and_material_connected_exposure_are_not_cleared():
    _, df = load()
    midea = df[(df.security_id == "HKEX:00300") & (df.research_dimension == "CATALYST")].iloc[0]
    sbio = df[(df.security_id == "HKEX:01530") & (df.research_dimension == "CATALYST")].iloc[0]
    yue = df[(df.security_id == "HKEX:00551") & (df.research_dimension == "GOVERNANCE_VALUE_TRAP")].iloc[0]
    assert str(midea.post_blocker).lower() in ("true", "1")
    assert str(sbio.post_blocker).lower() in ("true", "1")
    assert yue.resolution_status == "RECLASSIFIED_TARGETED"
    assert str(yue.post_blocker).lower() in ("true", "1")


def test_fresh_brilliance_warning_is_preserved_not_silently_dropped():
    _, df = load()
    r = df[(df.security_id == "HKEX:01114") & (df.research_dimension == "CATALYST")].iloc[0]
    assert r.evidence_date == "2026-08-05"
    assert r.resolution_direction == "NEGATIVE"
    assert r.cross_dimension_signal == "FRESH_NEGATIVE_EARNINGS_ALERT"
    assert str(r.post_blocker).lower() in ("true", "1")


def test_guangdong_earnings_lineage_is_reconciled_without_alpha_inference():
    _, df = load()
    r = df[(df.security_id == "HKEX:00270") & (df.research_dimension == "EARNINGS_EXPECTATION_REVISION")].iloc[0]
    assert r.secondary_source_url.endswith("2026012800497.pdf")
    assert r.cross_dimension_signal == "LINEAGE_RECONCILED_CURRENT_OPERATING_GROWTH"
    assert str(r.post_blocker).lower() in ("false", "0")
    assert r.resolution_status == "CLEARED_MONITOR"
