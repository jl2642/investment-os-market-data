from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "pipeline/hkcu_p2b_e2_collect_company_evidence.py"
spec = importlib.util.spec_from_file_location("p2b_e2", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_contract_guards():
    c = json.loads((ROOT / "config/hkcu_p2b_e2_company_evidence_contract.json").read_text(encoding="utf-8"))
    assert c["expected_counts"]["security_count"] == 77
    assert c["expected_counts"]["company_dimension_rows"] == 231
    assert c["evidence_policy"]["trailing_growth_may_proxy_earnings_revision"] is False
    assert c["evidence_policy"]["secondary_data_may_close_primary_governance"] is False
    assert c["trade_authority"] == "NONE"


def test_governance_flags_are_leads_not_score():
    profile = {"auditor": "Example Audit", "chairman": "Example"}
    fin = {
        "roe_pct": -2.0,
        "operating_cash_flow_per_share": -1.0,
        "net_profit_rolling_qoq_growth_pct": -40.0,
        "payout_ratio_pct": 150.0,
        "pe": -5.0,
    }
    flags = mod.governance_flags(profile, fin)
    assert "NEGATIVE_ROE" in flags
    assert "NEGATIVE_OPERATING_CASH_FLOW_PER_SHARE" in flags
    assert "NET_PROFIT_ROLLING_DECLINE_GT_30PCT" in flags
    assert "PAYOUT_RATIO_OUTLIER" in flags
    assert "NEGATIVE_EARNINGS_PE" in flags


def test_catalyst_requires_primary_verification():
    status, reason, count = mod.catalyst_context({
        "latest_dividend_announcement_date": "2026-07-01",
        "latest_ex_date": "2026-08-20",
        "latest_payment_date": "2026-09-01",
    })
    assert status == "EVIDENCE_PARTIAL"
    assert "PRIMARY_VERIFICATION_REQUIRED" in reason
    assert count == 1


def test_no_dividend_is_not_fabricated_catalyst():
    status, reason, count = mod.catalyst_context({
        "latest_dividend_announcement_date": "",
        "latest_ex_date": "",
        "latest_payment_date": "",
    })
    assert status == "RESEARCH_REQUIRED"
    assert count == 0
