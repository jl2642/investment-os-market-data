#!/usr/bin/env python3
"""Identity- and integrity-safe FMDL-2B-4 refresh entrypoint.

The production engine indexes the current snapshot by canonical symbol. This
adapter preserves that identity and rejects impossible current-session OHLC
before the fast append path, so the engine routes the symbol to its controlled
full-history repair path instead of contaminating the composite store.
"""

from __future__ import annotations

import math
import sys
from typing import Any

import pandas as pd

from scripts import run_incremental_history_refresh as engine

_ORIGINAL_CANONICAL_INCREMENTAL_ROW = engine.canonical_incremental_row
_ORIGINAL_CONTINUITY_PASSES = engine.continuity_passes


def _number(value: Any) -> float | None:
    converted = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(converted):
        return None
    number = float(converted)
    return number if math.isfinite(number) else None


def snapshot_ohlc_is_valid(snapshot_row: pd.Series) -> bool:
    values = {name: _number(snapshot_row.get(name)) for name in ("open", "high", "low", "close")}
    if any(value is None or value <= 0 for value in values.values()):
        return False
    return bool(
        values["high"] >= max(values["open"], values["close"], values["low"])
        and values["low"] <= min(values["open"], values["close"], values["high"])
    )


def continuity_passes(
    snapshot_row: pd.Series,
    prior_close: float,
    config: dict[str, Any],
) -> tuple[bool, float | None, float | None]:
    if not snapshot_ohlc_is_valid(snapshot_row):
        return False, None, None
    return _ORIGINAL_CONTINUITY_PASSES(snapshot_row, prior_close, config)


def canonical_incremental_row(
    snapshot_row: pd.Series,
    generated_at: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    row = snapshot_row.copy()
    if "symbol" not in row.index:
        if row.name is None:
            raise KeyError("symbol")
        row["symbol"] = str(row.name)
    return _ORIGINAL_CANONICAL_INCREMENTAL_ROW(row, generated_at, config)


def install_refresh_adapters() -> None:
    engine.canonical_incremental_row = canonical_incremental_row
    engine.continuity_passes = continuity_passes


def main() -> int:
    install_refresh_adapters()
    return engine.main()


if __name__ == "__main__":
    sys.exit(main())
