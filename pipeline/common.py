"""Shared deterministic helpers for the FMDL pipeline."""

from __future__ import annotations

from datetime import date, datetime, time
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

BUSINESS_TZ = ZoneInfo("Asia/Shanghai")
SYMBOL_PATTERN = re.compile(r"^[0-9]{6}\.(SH|SZ|BJ)$")


def now_shanghai() -> datetime:
    return datetime.now(tz=BUSINESS_TZ)


def iso_shanghai(value: datetime | None = None) -> str:
    current = value or now_shanghai()
    return current.astimezone(BUSINESS_TZ).isoformat(timespec="seconds")


def clean_scalar(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            pass
    return value


def safe_float(value: Any) -> float | None:
    cleaned = clean_scalar(value)
    if cleaned is None or cleaned == "":
        return None
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def stable_row_hash(row: dict[str, Any]) -> str:
    payload = {key: clean_scalar(value) for key, value in row.items() if key != "row_hash"}
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def exchange_and_board(code: str) -> tuple[str, str]:
    code = str(code).zfill(6)
    if code.startswith(("688", "689")):
        return "SH", "STAR"
    if code.startswith(("600", "601", "603", "605")):
        return "SH", "SH_MAIN"
    if code.startswith(("300", "301")):
        return "SZ", "CHINEXT"
    if code.startswith(("000", "001", "002", "003")):
        return "SZ", "SZ_MAIN"
    if code.startswith(("4", "8", "9")):
        return "BJ", "BSE"
    if code.startswith("6"):
        return "SH", "UNKNOWN"
    if code.startswith(("0", "3")):
        return "SZ", "UNKNOWN"
    return "BJ", "UNKNOWN"


def canonical_symbol(code: str) -> str:
    normalized = str(code).split(".")[0].zfill(6)
    exchange, _ = exchange_and_board(normalized)
    return f"{normalized}.{exchange}"


def latest_completed_trade_date(calendar: pd.DataFrame, current: datetime | None = None) -> date:
    """Return the most recent completed Chinese trading session.

    Before 16:10 Asia/Shanghai on a trading day, the current date is excluded so
    an intraday spot table is not mislabeled as a completed daily snapshot.
    """

    now = (current or now_shanghai()).astimezone(BUSINESS_TZ)
    dates: list[date] = []
    if not calendar.empty:
        candidate_column = None
        for column in ("trade_date", "交易日", "date"):
            if column in calendar.columns:
                candidate_column = column
                break
        if candidate_column:
            parsed = pd.to_datetime(calendar[candidate_column], errors="coerce").dropna()
            dates = sorted({value.date() for value in parsed})
    if not dates:
        candidate = now.date()
        while candidate.weekday() >= 5:
            candidate = candidate.fromordinal(candidate.toordinal() - 1)
        if candidate == now.date() and now.time() < time(16, 10):
            candidate = candidate.fromordinal(candidate.toordinal() - 1)
            while candidate.weekday() >= 5:
                candidate = candidate.fromordinal(candidate.toordinal() - 1)
        return candidate
    eligible = [item for item in dates if item <= now.date()]
    if now.date() in eligible and now.time() < time(16, 10):
        eligible = [item for item in eligible if item < now.date()]
    if not eligible:
        raise RuntimeError("No completed trading date is available in the calendar")
    return max(eligible)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
