#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from pipeline import hkcu_p4_1r_portfolio_context_completion as base
from scripts.fmdl2b4_history import load_composite_shard, load_current_manifest
from scripts.run_full_backfill_shard import shard_for_symbol


def load_hk_histories_compat(path: Path) -> tuple[dict[str, pd.Series], str, str]:
    """Read accepted FMDL-5C history using the current Canonical schema.

    P4-1R originally accepted date/trade_date/market_date but the accepted
    FMDL-5C store uses observation_date. Keep the adapter schema-tolerant while
    preserving exact security identity and accepted price semantics.
    """

    df = pd.read_parquet(path)
    sid_col = next((c for c in ["security_id", "stock_code_5d", "symbol", "code"] if c in df.columns), None)
    date_col = next((c for c in ["observation_date", "date", "trade_date", "market_date"] if c in df.columns), None)
    price_col = next((c for c in ["adj_close", "adjusted_close", "close", "latest_close"] if c in df.columns), None)
    if not sid_col or not date_col or not price_col:
        raise RuntimeError("FMDL5C_HISTORY_SCHEMA_UNSUPPORTED:" + ",".join(map(str, df.columns)))

    dates = pd.to_datetime(df[date_col], errors="coerce")
    valid_dates = dates.dropna()
    if valid_dates.empty:
        raise RuntimeError("FMDL5C_HISTORY_HAS_NO_VALID_DATES")

    out: dict[str, pd.Series] = {}
    for key, g in df.groupby(sid_col):
        raw = str(key).strip()
        sid = raw if raw.startswith("HKEX:") else "HKEX:" + base.code5(raw)
        x = pd.DataFrame(
            {
                "date": pd.to_datetime(g[date_col], errors="coerce"),
                "price": pd.to_numeric(g[price_col], errors="coerce"),
            }
        ).dropna()
        x = x[x["price"] > 0].drop_duplicates("date").sort_values("date")
        if not x.empty:
            out[sid] = pd.Series(x["price"].values, index=x["date"], dtype=float)

    return out, str(valid_dates.min().date()), str(valid_dates.max().date())


def load_canonical_a_share_histories(root: Path, holdings: list[dict[str, Any]]) -> dict[str, pd.Series]:
    """Load only held A-share stocks from the accepted Composite History.

    This avoids rebuilding a second live-market history dependency for portfolio
    risk. ETFs/funds that are not members of the A-share stock history store are
    intentionally left to the existing governed fallback path.
    """

    target = sorted(
        {
            str(h.get("security_id") or "")
            for h in holdings
            if str(h.get("security_id") or "").endswith((".SH", ".SZ"))
            and "ETF" not in str(h.get("asset_class") or "").upper()
            and "ETF" not in str(h.get("security_name") or "").upper()
        }
    )
    if not target:
        return {}

    manifest = load_current_manifest(root=root)
    logical_shards = int(manifest["logical_shards"])
    by_shard: dict[int, set[str]] = {}
    for sid in target:
        by_shard.setdefault(shard_for_symbol(sid, logical_shards), set()).add(sid)

    histories: dict[str, pd.Series] = {}
    for shard_id, shard_targets in sorted(by_shard.items()):
        frame = load_composite_shard(manifest, shard_id, root=root)
        if frame.empty:
            continue
        local = frame[frame["symbol"].astype(str).isin(shard_targets)].copy()
        for sid, g in local.groupby(local["symbol"].astype(str)):
            x = pd.DataFrame(
                {
                    "date": pd.to_datetime(g["trade_date"], errors="coerce"),
                    "price": pd.to_numeric(g["close"], errors="coerce"),
                }
            ).dropna()
            x = x[x["price"] > 0].drop_duplicates("date").sort_values("date")
            if not x.empty:
                histories[str(sid)] = pd.Series(x["price"].values, index=x["date"], dtype=float)
    return histories


def canonical_first_holding_fetcher(
    canonical_histories: dict[str, pd.Series],
    fallback: Callable[[dict[str, Any], str], pd.Series],
) -> Callable[[dict[str, Any], str], pd.Series]:
    """Return Canonical history when available; otherwise use existing fallback."""

    def fetch(h: dict[str, Any], as_of: str) -> pd.Series:
        sid = str(h.get("security_id") or "")
        canonical = canonical_histories.get(sid)
        if canonical is not None and not canonical.empty:
            cutoff = pd.Timestamp(as_of)
            return canonical.loc[canonical.index <= cutoff].copy()
        return fallback(h, as_of)

    return fetch


def build(root: Path, out: Path) -> dict[str, Any]:
    contract = base.read_json(root / "config/hkcu_p4_1r_portfolio_context_completion_contract.json")
    inputs = contract["authoritative_inputs"]
    real = base.read_json(root / inputs["real_positions_current"])
    simulation = base.read_json(root / inputs["simulation_positions_current"])
    holdings = [*real.get("holdings", []), *simulation.get("holdings", [])]

    canonical_a = load_canonical_a_share_histories(root, holdings)
    original_fallback = base.fetch_holding_history
    base.load_hk_histories = load_hk_histories_compat
    base.fetch_holding_history = canonical_first_holding_fetcher(canonical_a, original_fallback)
    return base.build(root, out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
