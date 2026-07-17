#!/usr/bin/env python3
"""Board-identity-safe FMDL-2C screening entrypoint.

The accepted factor table may contain a temporary UNKNOWN board label. A
single-name board produces meaningless board-neutral percentiles, so unknown
boards are review-only and cannot enter any sleeve. The frozen screening engine
is otherwise reused unchanged.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from scripts import run_screening_funnel as engine

_ORIGINAL_CLASSIFY = engine.classify_investability


def classify_investability(
    row: pd.Series,
    config: dict[str, Any],
) -> tuple[str, list[str]]:
    board = str(row.get("board", "UNKNOWN"))
    known = set(config["investability"].get("known_boards", []))
    quality = str(row.get("factor_record_quality", "UNKNOWN"))
    if quality not in set(config["investability"]["excluded_factor_record_quality"]):
        if board not in known:
            return "REVIEW_ONLY", ["UNKNOWN_BOARD_REVIEW_ONLY"]
    return _ORIGINAL_CLASSIFY(row, config)


def install_board_identity_gate() -> None:
    engine.classify_investability = classify_investability


def run(*args: Any, **kwargs: Any):
    install_board_identity_gate()
    return engine.run(*args, **kwargs)


# Re-export deterministic helpers for tests and downstream use.
evaluate_sleeve = engine.evaluate_sleeve
build_longlist = engine.build_longlist


if __name__ == "__main__":
    run()
