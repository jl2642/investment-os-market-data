from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_fmdl5f_public_equity_research import (  # noqa: E402
    build_registry,
    case_types,
    disclosure_score,
    select_public_sources,
    stable_hash,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "config/fmdl5f_public_equity_research_contract.json").read_text(encoding="utf-8"))
_spec = importlib.util.spec_from_file_location("fmdl5f_research_profiles", ROOT / "config/fmdl5f_research_profiles.py")
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
PROFILES = _module.load_profiles()


def test_profile_pack_is_complete_and_governed() -> None:
    assert PROFILES["profile_version"] == "1.0.0"
    assert len(PROFILES["profiles"]) == 20
    decisions = pd.Series([v["decision"] for v in PROFILES["profiles"].values()]).value_counts().to_dict()
    assert decisions == {"DEFERRED": 13, "GRADUATED": 4, "SHADOW_TRACK": 2, "REJECTED": 1}
    grad_shadow = [v for v in PROFILES["profiles"].values() if v["decision"] in {"GRADUATED", "SHADOW_TRACK"}]
    covered = {case for profile in grad_shadow for case in profile["case_types"]}
    assert set(CONTRACT["decision_policy"]["required_case_types"]).issubset(covered)
    assert all(len(v["prove_kill_checks"]) >= 4 for v in PROFILES["profiles"].values())


def test_case_types_adds_market_semantics() -> None:
    row = pd.Series({
        "a_share_class_exists": True,
        "h_share_flag": True,
        "dividend_yield_365d": 0.05,
        "wvr_flag": True,
        "corporate_action_count_365d": 2,
        "official_security_name_en": "INTERNET-W",
        "official_issuer_name_en": "Example",
    })
    assert case_types(row, {"case_types": []}) == ["A_H", "CORPORATE_ACTION", "HIGH_DIVIDEND", "WVR_OR_INTERNET"]


def test_disclosure_policy_penalizes_non_financial_material() -> None:
    good = pd.Series({"title": "ANNUAL RESULTS FOR 2025", "filing_type": "ANNUAL_RESULTS", "report_period_end": "2025-12-31", "available_from": "2026-03-01T09:30:00+08:00", "filing_id": "a"})
    bad = pd.Series({"title": "ESG REPORT AND GENERAL MEETING", "filing_type": "FINANCIAL_STATEMENTS", "report_period_end": "", "available_from": "2026-03-01T09:30:00+08:00", "filing_id": "b"})
    assert disclosure_score(good, CONTRACT["source_policy"])[0] > disclosure_score(bad, CONTRACT["source_policy"])[0]


def test_public_source_selection_blocks_future_and_uses_current_filing() -> None:
    disclosures = pd.DataFrame([
        {"stock_code_5d": "00001", "title": "2025 Annual Results", "filing_type": "ANNUAL_RESULTS", "report_period_end": "2025-12-31", "available_from": "2026-03-20T09:30:00+08:00", "filing_id": "f1", "news_id": "n1", "filing_url": "https://www1.hkexnews.hk/a.pdf", "source_tier": "OFFICIAL_PRIMARY", "source_record_sha256": "a" * 64},
        {"stock_code_5d": "00001", "title": "Future Interim Results", "filing_type": "INTERIM_RESULTS", "report_period_end": "2026-06-30", "available_from": "2026-08-20T09:30:00+08:00", "filing_id": "f2", "news_id": "n2", "filing_url": "https://www1.hkexnews.hk/future.pdf", "source_tier": "OFFICIAL_PRIMARY", "source_record_sha256": "b" * 64},
    ])
    financial = pd.Series({"official_filing_url": "https://www1.hkexnews.hk/current.pdf", "available_from": "2026-05-01T09:30:00+08:00", "official_filing_id": "fc", "period_end": "2025-12-31", "security_id": "HKEX:00001"})
    selected = select_public_sources("00001", disclosures, financial, pd.Timestamp("2026-07-21"), CONTRACT)
    assert [x["url"] for x in selected] == ["https://www1.hkexnews.hk/a.pdf", "https://www1.hkexnews.hk/current.pdf"]


def test_registry_never_mutates_investment_state() -> None:
    longlist = pd.DataFrame([
        {"as_of_date": "2026-07-21", "overall_rank": 1, "research_priority": "A_IMMEDIATE_RESEARCH", "security_id": "HKEX:02388", "stock_code_5d": "02388", "official_security_name_en": "BOC HONG KONG", "primary_sleeve": "DEFENSIVE_STABILITY"},
        {"as_of_date": "2026-07-21", "overall_rank": 2, "research_priority": "B_WATCH_OR_TRIGGER", "security_id": "HKEX:00001", "stock_code_5d": "00001", "official_security_name_en": "CKH HOLDINGS", "primary_sleeve": "TREND_LIQUIDITY"},
    ])
    registry = build_registry(longlist, PROFILES["profiles"], CONTRACT)
    assert registry.iloc[0]["research_decision"] == "GRADUATED"
    assert registry.iloc[1]["research_stage"] == "SCREENED"
    assert not registry[["candidate_pool_admission", "simulation_admission", "real_account_admission", "order_generation"]].to_numpy().any()
    assert set(registry["trade_authority"]) == {"NONE"}


def test_stable_hash_is_order_independent_for_mappings() -> None:
    assert stable_hash({"a": 1, "b": 2}) == stable_hash({"b": 2, "a": 1})
