#!/usr/bin/env python3
"""NaT-safe entrypoint for the FMDL-2B-1 history pilot."""

from __future__ import annotations

from datetime import date, timedelta
import sys
from typing import Any

import pandas as pd

from scripts import run_history_pilot as pilot


def select_pilot_sample(universe: pd.DataFrame, config: dict[str, Any], as_of: date) -> pd.DataFrame:
    required = {"symbol", "board", "is_st", "is_suspended", "list_date"}
    missing = required.difference(universe.columns)
    if missing:
        raise RuntimeError(f"Universe missing pilot fields: {sorted(missing)}")

    quotas = config["pilot"]["board_quotas"]
    selected: list[pd.DataFrame] = []
    for board, quota in quotas.items():
        group = universe.loc[universe["board"] == board].copy()
        if len(group) < int(quota):
            raise RuntimeError(f"Board {board} has {len(group)} rows, below quota {quota}")
        list_dates = pd.to_datetime(group["list_date"], errors="coerce").dt.date
        recent_cutoff = as_of - timedelta(days=config["history_policy"]["seasoned_listing_calendar_days"])
        recent_listing = list_dates.map(
            lambda value: int(pd.notna(value) and value >= recent_cutoff)
        )
        group["special_priority"] = (
            group["is_st"].astype(str).str.lower().eq("true").astype(int) * 4
            + group["is_suspended"].astype(str).str.lower().eq("true").astype(int) * 3
            + recent_listing * 2
            + list_dates.isna().astype(int)
        )
        group["stable_key"] = group["symbol"].map(pilot.stable_key)
        group = group.sort_values(["special_priority", "stable_key"], ascending=[False, True])
        selected.append(group.head(int(quota)).copy())

    sample = pd.concat(selected, ignore_index=True)
    sample["stable_key"] = sample["symbol"].map(pilot.stable_key)
    sample = sample.sort_values(["board", "stable_key"]).reset_index(drop=True)
    sample["sample_order"] = range(1, len(sample) + 1)
    shard_size = int(config["pilot"]["shard_size"])
    sample["shard_id"] = ((sample["sample_order"] - 1) // shard_size).map(
        lambda value: f"shard_{value:02d}"
    )
    expected = int(config["pilot"]["sample_size"])
    if len(sample) != expected:
        raise RuntimeError(f"Pilot sample size {len(sample)} != expected {expected}")
    return sample


pilot.select_pilot_sample = select_pilot_sample


if __name__ == "__main__":
    sys.exit(pilot.main())
