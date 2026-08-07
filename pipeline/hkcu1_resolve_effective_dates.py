#!/usr/bin/env python3
"""Resolve HKCU-1 adjustment-event effective dates against official Stock Connect calendar rules."""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd


def is_service_day(day: date, calendar: dict) -> bool:
    if day.weekday() >= 5:
        return False
    return day.isoformat() not in set(calendar.get("full_day_non_service_dates", []))


def next_service_day(after: date, calendar: dict) -> date:
    candidate = after + timedelta(days=1)
    for _ in range(370):
        if candidate.year != int(calendar["year"]):
            raise ValueError(f"calendar does not cover {candidate.isoformat()}")
        if is_service_day(candidate, calendar):
            return candidate
        candidate += timedelta(days=1)
    raise ValueError("unable to resolve next Stock Connect service day")


def resolve_events(events: pd.DataFrame, calendar: dict, as_of_date: str | None = None) -> pd.DataFrame:
    if events.empty:
        return events.copy()
    required = {"security_code", "channel", "direction", "announcement_date", "effective_from", "effective_rule"}
    if not required.issubset(events.columns):
        raise ValueError(f"events missing {sorted(required - set(events.columns))}")
    result = events.copy()
    cutoff = date.fromisoformat(as_of_date) if as_of_date else None

    for idx, row in result.iterrows():
        effective = row.get("effective_from")
        if pd.notna(effective) and str(effective).strip():
            resolved = date.fromisoformat(str(effective)[:10])
        else:
            rule = str(row.get("effective_rule") or "")
            ann = row.get("announcement_date")
            if not ann or pd.isna(ann):
                continue
            announced = date.fromisoformat(str(ann)[:10])
            if rule == "NEXT_STOCK_CONNECT_TRADING_DAY":
                resolved = next_service_day(announced, calendar)
            elif rule == "SAME_DAY_IN_NOTICE":
                resolved = announced
            else:
                continue
        result.at[idx, "effective_from"] = resolved.isoformat()
        result.at[idx, "effective_rule"] = str(row.get("effective_rule") or "") + "|CALENDAR_RESOLVED"

    if cutoff is not None:
        result["future_event"] = result["effective_from"].map(
            lambda x: bool(pd.notna(x) and str(x).strip() and date.fromisoformat(str(x)[:10]) > cutoff)
        )
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--events", type=Path, required=True)
    p.add_argument("--calendar", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--as-of-date")
    a = p.parse_args()

    events = pd.read_csv(a.events, dtype=str)
    calendar = json.loads(a.calendar.read_text(encoding="utf-8"))
    resolved = resolve_events(events, calendar, a.as_of_date)
    a.output_dir.mkdir(parents=True, exist_ok=True)
    resolved.to_csv(a.output_dir / "HKCU1_ADJUSTMENT_EVENTS_RESOLVED.csv", index=False)

    unresolved = 0
    future = 0
    if not resolved.empty:
        unresolved = int(resolved["effective_from"].fillna("").astype(str).str.strip().eq("").sum())
        if "future_event" in resolved.columns:
            future = int(resolved["future_event"].sum())
    decision = {
        "status": "PASS" if unresolved == 0 else "BLOCKED",
        "rows": int(len(resolved)),
        "unresolved_effective_date_rows": unresolved,
        "future_event_rows": future,
        "future_events_must_not_apply": True,
        "calendar_id": calendar.get("calendar_id"),
        "trade_authority": "NONE",
    }
    (a.output_dir / "HKCU1_R2C_EFFECTIVE_DATE_DECISION.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if unresolved == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
