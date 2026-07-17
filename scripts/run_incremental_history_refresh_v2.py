#!/usr/bin/env python3
"""Identity-safe FMDL-2B-4 incremental refresh entrypoint.

The snapshot is indexed by canonical symbol during full-market processing. This
entrypoint preserves that index identity when the canonical row constructor is
called, then delegates all production logic to the frozen refresh engine.
"""

from __future__ import annotations

import sys
from typing import Any

import pandas as pd

from scripts import run_incremental_history_refresh as engine

_ORIGINAL_CANONICAL_INCREMENTAL_ROW = engine.canonical_incremental_row


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


def install_identity_adapter() -> None:
    engine.canonical_incremental_row = canonical_incremental_row


def main() -> int:
    install_identity_adapter()
    return engine.main()


if __name__ == "__main__":
    sys.exit(main())
