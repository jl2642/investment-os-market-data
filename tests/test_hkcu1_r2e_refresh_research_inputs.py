from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from pipeline.hkcu1_r2e_refresh_research_inputs import (
    _filter_action_rows,
    _filter_observation_rows,
    _load_hkma_fx_lkg,
    _refresh_summary,
    latest_completed_service_date,
)

HK = ZoneInfo("Asia/Hong_Kong")


def _calendar():
    return {
        "full_day_non_service_dates": [
            "2026-04-03", "2026-04-06", "2026-04-07", "2026-07-01"
        ]
    }


def test_mid_session_uses_previous_completed_service_day():
    now = datetime(2026, 8, 7, 11, 55, tzinfo=HK)
    assert latest_completed_service_date(_calendar(), now).isoformat() == "2026-08-06"


def test_after_close_uses_same_service_day():
    now = datetime(2026, 8, 7, 18, 30, tzinfo=HK)
    assert latest_completed_service_date(_calendar(), now).isoformat() == "2026-08-07"


def test_weekend_uses_prior_friday():
    now = datetime(2026, 8, 9, 18, 30, tzinfo=HK)
    assert latest_completed_service_date(_calendar(), now).isoformat() == "2026-08-07"


def test_official_non_service_run_skips_back_to_prior_service_day():
    now = datetime(2026, 7, 1, 18, 30, tzinfo=HK)
    assert latest_completed_service_date(_calendar(), now).isoformat() == "2026-06-30"


def test_vendor_price_rows_are_hard_cut_to_completed_session():
    rows = [
        {"observation_date": "2026-08-05", "close": 1},
        {"observation_date": "2026-08-06", "close": 2},
        {"observation_date": "2026-08-07", "close": 3},
    ]
    kept = _filter_observation_rows(rows, "2026-08-06")
    assert [row["observation_date"] for row in kept] == ["2026-08-05", "2026-08-06"]
    summary = _refresh_summary({"row_count": 3, "latest_date": "2026-08-07"}, kept, "observation_date")
    assert summary["row_count"] == 2
    assert summary["latest_date"] == "2026-08-06"


def test_vendor_actions_after_cutoff_do_not_enter_completed_session_candidate():
    actions = [
        {"action_date": "2026-08-06", "action_type": "CASH_DIVIDEND"},
        {"action_date": "2026-08-07", "action_type": "CASH_DIVIDEND"},
        {"action_date": "", "action_type": "UNKNOWN"},
    ]
    kept = _filter_action_rows(actions, "2026-08-06")
    assert [row["action_date"] for row in kept] == ["2026-08-06"]


def _write_fx_fixture(root, dates, *, provider="HKMA_ER_EERI_DAILY", tier="OFFICIAL_OPEN_API"):
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "outputs/fmdl5c/current").mkdir(parents=True, exist_ok=True)
    (root / "config/fmdl5c_price_volume_corporate_action_fx_contract.json").write_text(
        '{"acceptance":{"fx_row_count_min":3,"fx_latest_max_age_calendar_days":40}}',
        encoding="utf-8",
    )
    rows = []
    for idx, day in enumerate(dates):
        rows.append({
            "observation_date": day,
            "hkd_per_usd": 7.80 + idx / 1000,
            "hkd_per_cny": 1.08 + idx / 1000,
            "provider": provider,
            "source_tier": tier,
            "retrieved_at_utc": "2026-07-21T00:00:00+00:00",
            "source_page_sha256": "a" * 64,
        })
    pd.DataFrame(rows).to_csv(root / "outputs/fmdl5c/current/FMDL5C_FX_DAILY.csv", index=False, encoding="utf-8-sig")


def test_hkma_fx_lkg_may_bridge_transient_api_failure_within_contract(tmp_path):
    _write_fx_fixture(tmp_path, ["2026-07-29", "2026-07-30", "2026-07-31"])
    rows, summary, diag = _load_hkma_fx_lkg(tmp_path, "2026-01-01", date(2026, 8, 6))
    assert len(rows) == 3
    assert summary["acquisition_mode"] == "LAST_KNOWN_GOOD_OFFICIAL_CURRENT"
    assert summary["latest_date"] == "2026-07-31"
    assert diag["age_calendar_days"] == 6
    assert diag["source_tier"] == "OFFICIAL_OPEN_API"


def test_hkma_fx_lkg_fails_closed_when_stale(tmp_path):
    _write_fx_fixture(tmp_path, ["2026-05-01", "2026-05-02", "2026-05-04"])
    with pytest.raises(RuntimeError, match="HKMA_FX_LKG_STALE"):
        _load_hkma_fx_lkg(tmp_path, "2026-01-01", date(2026, 8, 6))


def test_hkma_fx_lkg_rejects_non_official_provenance(tmp_path):
    _write_fx_fixture(tmp_path, ["2026-07-29", "2026-07-30", "2026-07-31"], provider="OTHER")
    with pytest.raises(RuntimeError, match="HKMA_FX_LKG_AUTHORITY_MISMATCH"):
        _load_hkma_fx_lkg(tmp_path, "2026-01-01", date(2026, 8, 6))
