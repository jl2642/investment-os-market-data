#!/usr/bin/env python3
"""SciPy-free FMDL-2D entrypoint.

Spearman rank correlation is Pearson correlation of ranked observations. This
adapter keeps the repository's lightweight dependency contract by calculating
it directly instead of relying on pandas' optional SciPy route.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from scripts import run_fmdl2d_stability as engine


def rank_transition(
    previous: pd.DataFrame,
    current: pd.DataFrame,
    previous_date: str,
    current_date: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    prev = previous.set_index("symbol")
    curr = current.set_index("symbol")
    common = sorted(set(prev.index).intersection(curr.index))
    overlap_denominator = max(1, min(len(prev), len(curr)))
    top_prev = set(previous.nsmallest(20, "overall_rank")["symbol"])
    top_curr = set(current.nsmallest(20, "overall_rank")["symbol"])
    if len(common) >= 2:
        ranks = pd.DataFrame(
            {
                "previous": pd.to_numeric(prev.loc[common, "overall_rank"]),
                "current": pd.to_numeric(curr.loc[common, "overall_rank"]),
            }
        )
        previous_ranked = ranks["previous"].rank(method="average")
        current_ranked = ranks["current"].rank(method="average")
        spearman = float(previous_ranked.corr(current_ranked, method="pearson"))
        median_abs = float((ranks["previous"] - ranks["current"]).abs().median())
    else:
        spearman = math.nan
        median_abs = math.nan
    primary_retention = (
        float(
            (
                prev.loc[common, "primary_sleeve"].astype(str).values
                == curr.loc[common, "primary_sleeve"].astype(str).values
            ).mean()
        )
        if common
        else 0.0
    )
    priority_retention = (
        float(
            (
                prev.loc[common, "research_priority"].astype(str).values
                == curr.loc[common, "research_priority"].astype(str).values
            ).mean()
        )
        if common
        else 0.0
    )
    summary = {
        "previous_date": previous_date,
        "current_date": current_date,
        "previous_rows": len(previous),
        "current_rows": len(current),
        "common_symbols": len(common),
        "overlap_ratio": len(common) / overlap_denominator,
        "entrants": len(set(curr.index).difference(prev.index)),
        "exits": len(set(prev.index).difference(curr.index)),
        "top20_overlap_ratio": len(top_prev.intersection(top_curr)) / 20.0,
        "common_rank_spearman": spearman,
        "median_absolute_rank_change": median_abs,
        "primary_sleeve_retention": primary_retention,
        "priority_bucket_retention": priority_retention,
    }
    migrations: list[dict[str, Any]] = []
    for symbol in common:
        migrations.append(
            {
                "previous_date": previous_date,
                "current_date": current_date,
                "symbol": symbol,
                "name": str(curr.loc[symbol, "name"]),
                "previous_rank": int(prev.loc[symbol, "overall_rank"]),
                "current_rank": int(curr.loc[symbol, "overall_rank"]),
                "rank_change": int(
                    prev.loc[symbol, "overall_rank"]
                    - curr.loc[symbol, "overall_rank"]
                ),
                "previous_priority": str(prev.loc[symbol, "research_priority"]),
                "current_priority": str(curr.loc[symbol, "research_priority"]),
                "previous_primary_sleeve": str(
                    prev.loc[symbol, "primary_sleeve"]
                ),
                "current_primary_sleeve": str(
                    curr.loc[symbol, "primary_sleeve"]
                ),
            }
        )
    return summary, migrations


def install() -> None:
    engine.rank_transition = rank_transition


def run(*args: Any, **kwargs: Any):
    install()
    return engine.run(*args, **kwargs)


semantic_frame_hash = engine.semantic_frame_hash
concentration = engine.concentration
fragility_review = engine.fragility_review
sleeve_transition = engine.sleeve_transition


if __name__ == "__main__":
    run()
