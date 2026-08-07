from datetime import datetime
from zoneinfo import ZoneInfo

from pipeline.hkcu1_r2e_refresh_research_inputs import latest_completed_service_date

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
