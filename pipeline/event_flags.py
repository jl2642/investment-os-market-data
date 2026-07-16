"""Deterministic event flags for FMDL operational releases."""

from __future__ import annotations

from typing import Any

import pandas as pd


EVENT_COLUMNS = [
    "as_of_date",
    "symbol",
    "event_type",
    "severity",
    "metric",
    "value",
    "threshold",
    "explanation",
]


def build_market_event_flags(
    snapshot: pd.DataFrame,
    *,
    extreme_return_threshold_pct: float = 35.0,
) -> pd.DataFrame:
    """Return reviewable market-event flags without changing source observations."""

    rows: list[dict[str, Any]] = []
    for _, row in snapshot.iterrows():
        as_of_date = str(row.get("as_of_date", ""))
        symbol = str(row.get("symbol", ""))
        status = str(row.get("data_status", "UNKNOWN"))
        pct_change = pd.to_numeric(row.get("pct_change"), errors="coerce")
        turnover = pd.to_numeric(row.get("turnover_cny"), errors="coerce")

        if status == "SUSPENDED":
            rows.append(
                {
                    "as_of_date": as_of_date,
                    "symbol": symbol,
                    "event_type": "SUSPENDED_SECURITY",
                    "severity": "INFO",
                    "metric": "data_status",
                    "value": "SUSPENDED",
                    "threshold": None,
                    "explanation": "Source semantics indicate no valid completed-session trade.",
                }
            )

        if pd.notna(pct_change) and abs(float(pct_change)) > extreme_return_threshold_pct:
            rows.append(
                {
                    "as_of_date": as_of_date,
                    "symbol": symbol,
                    "event_type": "EXTREME_RETURN_REVIEW",
                    "severity": "REVIEW",
                    "metric": "pct_change",
                    "value": float(pct_change),
                    "threshold": extreme_return_threshold_pct,
                    "explanation": "Large absolute return requires corporate-action, IPO, resumption or source review.",
                }
            )

        if status == "TRADED" and pd.notna(turnover) and float(turnover) == 0.0:
            rows.append(
                {
                    "as_of_date": as_of_date,
                    "symbol": symbol,
                    "event_type": "ZERO_TURNOVER_REVIEW",
                    "severity": "REVIEW",
                    "metric": "turnover_cny",
                    "value": 0.0,
                    "threshold": 0.0,
                    "explanation": "A traded row with zero turnover requires source or market-status review.",
                }
            )

    return pd.DataFrame(rows, columns=EVENT_COLUMNS)
