from datetime import datetime
from zoneinfo import ZoneInfo

from pipeline.hkcu1_r2e_refresh_research_inputs import (
    _filter_action_rows,
    _filter_observation_rows,
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
