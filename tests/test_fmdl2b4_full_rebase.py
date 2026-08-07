import pytest

from scripts.build_fmdl2b4_full_rebase_candidate import validate_recovery_gap


def test_full_rebase_rejects_same_day_and_single_session() -> None:
    with pytest.raises(RuntimeError, match="FULL_REBASE_TARGET_NOT_AFTER_CURRENT"):
        validate_recovery_gap("2026-08-06", "2026-08-06", [])
    with pytest.raises(RuntimeError, match="FULL_REBASE_NOT_REQUIRED_GAP_1"):
        validate_recovery_gap("2026-08-05", "2026-08-06", ["2026-08-06"])


def test_full_rebase_accepts_multi_session_gap() -> None:
    sessions = [
        "2026-07-20", "2026-07-21", "2026-07-22", "2026-07-23", "2026-07-24",
        "2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31",
        "2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06",
    ]
    validate_recovery_gap("2026-07-17", "2026-08-06", sessions)


def test_full_rebase_rejects_calendar_not_ending_at_target() -> None:
    with pytest.raises(RuntimeError, match="FULL_REBASE_SESSION_CALENDAR_NOT_AT_TARGET"):
        validate_recovery_gap("2026-07-17", "2026-08-06", ["2026-07-20", "2026-08-05"])
