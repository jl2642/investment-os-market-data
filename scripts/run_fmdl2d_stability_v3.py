#!/usr/bin/env python3
"""Canonical FMDL-2D entrypoint with robust Longlist semantic identity.

The published Longlist is CSV. Re-parsing decimal values can change binary
floating representation even when the accepted row content is unchanged.
Longlist rows already carry a canonical ``longlist_row_hash`` computed before
CSV serialization. Same-date replay therefore compares the ordered
(rank, symbol, row-hash) identity, while the other artifacts retain full
semantic-frame hashing.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from scripts import run_fmdl2d_stability as engine
from scripts.run_fmdl2d_stability_v2 import rank_transition

_ORIGINAL_SEMANTIC_HASH = engine.semantic_frame_hash


def semantic_frame_hash(
    frame: pd.DataFrame,
    *,
    sort_by: list[str],
    exclude: set[str] | None = None,
) -> str:
    if (
        sort_by == ["overall_rank", "symbol"]
        and "longlist_row_hash" in frame.columns
    ):
        ordered = frame.sort_values(sort_by).reset_index(drop=True)
        identity = [
            {
                "overall_rank": int(row["overall_rank"]),
                "symbol": str(row["symbol"]),
                "longlist_row_hash": str(row["longlist_row_hash"]),
            }
            for row in ordered.to_dict(orient="records")
        ]
        return engine.canonical_hash(identity)
    return _ORIGINAL_SEMANTIC_HASH(frame, sort_by=sort_by, exclude=exclude)


def install() -> None:
    engine.rank_transition = rank_transition
    engine.semantic_frame_hash = semantic_frame_hash


def run(*args: Any, **kwargs: Any):
    install()
    return engine.run(*args, **kwargs)


concentration = engine.concentration
fragility_review = engine.fragility_review
sleeve_transition = engine.sleeve_transition


if __name__ == "__main__":
    run()
