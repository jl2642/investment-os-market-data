from pathlib import Path

from scripts.summarize_occ_r2b2_valuation_context import build_summary

ROOT = Path(__file__).resolve().parents[1]


def _valid_payloads():
    market = {
        "status": "PASS",
        "data_watermark": "2026-08-28",
        "trade_authority": "NONE",
    }
    financial = {
        "status": "PASS",
        "market_as_of_date": "2026-08-28",
        "financial_report_period_watermark": "2026-06-30",
        "releases": {"financial_factor_release_id": "FMDL3CB_TEST"},
        "trade_authority": "NONE",
    }
    cap_release = {
        "release_id": "FMDL3DB_TEST",
        "source_release": {"as_of_date": "2026-08-28"},
    }
    cap_decision = {
        "status": "FMDL3DB_EFFECTIVE_SHARE_COUNT_AND_CAPITALIZATION_ENGINE_ACCEPTED",
        "trade_authority": "NONE",
    }
    valuation_release = {"release_id": "FMDL3DC_TEST"}
    valuation_decision = {
        "status": "FMDL3DC_VALUATION_ENGINE_CURRENT_ACCEPTED",
        "trade_authority": "NONE",
        "metrics": {
            "market_as_of_date": "2026-08-28",
            "factor_engine_release_id": "FMDL3CB_TEST",
            "future_selected_denominator_count": 0,
            "metric_valid_counts": {
                "VAL_EV_SALES_TTM": 100,
                "VAL_EV_OPERATING_INCOME_TTM": 50,
            },
        },
    }
    return market, financial, cap_release, cap_decision, valuation_release, valuation_decision


def test_occ_r2b2_summary_requires_exact_market_financial_lineage_and_ev_restoration():
    payloads = _valid_payloads()
    summary = build_summary(
        market_context=payloads[0],
        financial_context=payloads[1],
        capitalization_release=payloads[2],
        capitalization_decision=payloads[3],
        valuation_release=payloads[4],
        valuation_decision=payloads[5],
        market_source_branch="market-branch",
        market_source_commit="market-commit",
        financial_source_branch="financial-branch",
        financial_source_commit="financial-commit",
    )
    assert summary["status"] == "PASS"
    assert summary["financial_event_propagation"] == "COMPLETE"
    assert summary["financial_report_period_watermark"] == "2026-06-30"
    assert summary["hard_failures"] == []
    assert summary["checks"]["ZERO_FUTURE_SELECTED_DENOMINATOR"]
    assert summary["checks"]["EV_SALES_RESTORED"]
    assert summary["checks"]["EV_OPERATING_INCOME_RESTORED"]
    assert summary["trade_authority"] == "NONE"


def test_occ_r2b2_summary_fails_closed_on_future_denominator():
    payloads = list(_valid_payloads())
    payloads[5]["metrics"]["future_selected_denominator_count"] = 1
    summary = build_summary(
        market_context=payloads[0],
        financial_context=payloads[1],
        capitalization_release=payloads[2],
        capitalization_decision=payloads[3],
        valuation_release=payloads[4],
        valuation_decision=payloads[5],
        market_source_branch="market-branch",
        market_source_commit="market-commit",
        financial_source_branch="financial-branch",
        financial_source_commit="financial-commit",
    )
    assert summary["status"] == "FAIL"
    assert summary["financial_event_propagation"] == "INCOMPLETE"
    assert "ZERO_FUTURE_SELECTED_DENOMINATOR" in summary["hard_failures"]


def test_occ_r2b2_workflow_is_governed_and_does_not_reopen_methodology():
    text = (
        ROOT
        / ".github/workflows/occ-r2b2-capitalization-valuation-rebuild.yml"
    ).read_text(encoding="utf-8")
    assert 'shard_id: ["00","01","02","03","04","05","06","07","08","09","10","11","12","13","14","15"]' in text
    assert "operating_current/domains/A_SHARE_FULL_MARKET.json" in text
    assert "operating_current/domains/FINANCIAL_STATEMENT_CONTEXT.json" in text
    assert "run_fmdl3db_shard" in text
    assert "aggregate_fmdl3db" in text
    assert "run_fmdl3dc_valuation_engine" in text
    assert "summarize_occ_r2b2_valuation_context" in text
    assert "--domain FINANCIAL_VALUATION_CONTEXT" in text
    assert "financial_event_propagation=COMPLETE" in text
    assert "git push origin HEAD:main" not in text
    assert "TRADE_AUTHORITY: NONE" in text
