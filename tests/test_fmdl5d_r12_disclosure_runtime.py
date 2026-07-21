from __future__ import annotations

import importlib.util
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


matrix_module = load_module("fmdl5d_r12_matrix", "fmdl5d_r12_matrix.py")
month_module = load_module("fmdl5d_r12_month", "fmdl5d_r12_month.py")


def test_build_month_matrix_is_complete_and_ordered() -> None:
    rows = matrix_module.build_month_matrix(date(2023, 1, 15), date(2023, 3, 3))
    assert rows == [
        {"month_key": "2023-01", "start_date": "2023-01-15", "end_date": "2023-01-31"},
        {"month_key": "2023-02", "start_date": "2023-02-01", "end_date": "2023-02-28"},
        {"month_key": "2023-03", "start_date": "2023-03-01", "end_date": "2023-03-03"},
    ]


def test_split_windows_has_no_gaps_or_overlaps() -> None:
    start = date(2024, 2, 1)
    end = date(2024, 2, 29)
    windows = month_module.split_windows(start, end, 7)
    flattened = [day for window_start, window_end in windows for day in _days(window_start, window_end)]
    assert flattened[0] == start
    assert flattened[-1] == end
    assert len(flattened) == 29
    assert len(set(flattened)) == 29
    assert all((right - left).days == 1 for left, right in zip(flattened, flattened[1:]))


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def test_remaining_timeout_fails_closed_after_deadline() -> None:
    try:
        month_module.remaining_timeout(time.monotonic() - 0.01, 30)
    except TimeoutError as exc:
        assert "HARD_DEADLINE" in str(exc)
    else:
        raise AssertionError("expired deadline did not fail closed")
