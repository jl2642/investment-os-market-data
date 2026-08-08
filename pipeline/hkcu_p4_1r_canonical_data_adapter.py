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
    """Read accepted FMDL-5C history using the current Canonical schema."""

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
    """Load only held A-share stocks from the accepted Composite History."""

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
    """Return Canonical history when available; otherwise use existing governed fallback."""

    def fetch(h: dict[str, Any], as_of: str) -> pd.Series:
        sid = str(h.get("security_id") or "")
        canonical = canonical_histories.get(sid)
        if canonical is not None and not canonical.empty:
            cutoff = pd.Timestamp(as_of)
            return canonical.loc[canonical.index <= cutoff].copy()
        return fallback(h, as_of)

    return fetch


def load_economic_sector_registry(path: Path) -> pd.DataFrame:
    """Load the bounded R2 sector registry and enforce exact-identity coverage."""

    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = {
        "scope",
        "security_id",
        "security_code",
        "security_name",
        "economic_sector",
        "industry_detail",
        "classification_status",
        "source_lineage",
        "as_of_date",
        "trade_authority",
    }
    missing = required.difference(df.columns)
    if missing:
        raise RuntimeError("P4_1R_SECTOR_REGISTRY_SCHEMA:" + ",".join(sorted(missing)))
    if len(df) != 86:
        raise RuntimeError(f"P4_1R_SECTOR_REGISTRY_ROW_COUNT:{len(df)}")
    if df["security_id"].duplicated().any():
        raise RuntimeError("P4_1R_SECTOR_REGISTRY_DUPLICATE_SECURITY_ID")
    if set(df["scope"]) != {"HK_CANDIDATE", "A_SHARE_DIRECT_HOLDING"}:
        raise RuntimeError("P4_1R_SECTOR_REGISTRY_SCOPE")
    if int(df["scope"].eq("HK_CANDIDATE").sum()) != 70:
        raise RuntimeError("P4_1R_SECTOR_REGISTRY_HK_COUNT")
    if int(df["scope"].eq("A_SHARE_DIRECT_HOLDING").sum()) != 16:
        raise RuntimeError("P4_1R_SECTOR_REGISTRY_A_COUNT")
    if (df["economic_sector"].str.strip() == "").any():
        raise RuntimeError("P4_1R_SECTOR_REGISTRY_EMPTY_SECTOR")
    if not df["classification_status"].eq("ACCEPTED_SECONDARY_RESEARCH_CLASSIFICATION").all():
        raise RuntimeError("P4_1R_SECTOR_REGISTRY_CLASSIFICATION_STATUS")
    if not df["trade_authority"].eq(base.TRADE_AUTHORITY).all():
        raise RuntimeError("P4_1R_SECTOR_REGISTRY_TRADE_AUTHORITY")
    return df


def build_static_ah_source(path: Path) -> pd.DataFrame:
    """Rehydrate the already-accepted P2B-E1 exact A/H registry into the base adapter schema."""

    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = {"security_id", "pair_status", "a_code", "h_code", "security_name"}
    missing = required.difference(df.columns)
    if missing:
        raise RuntimeError("P2B_AH_REGISTRY_SCHEMA:" + ",".join(sorted(missing)))
    true_pairs = df[df["pair_status"].eq("TRUE_AH_PAIR")].copy()
    if len(true_pairs) != 13:
        raise RuntimeError(f"P2B_AH_TRUE_PAIR_COUNT:{len(true_pairs)}")
    if true_pairs["security_id"].duplicated().any() or true_pairs["h_code"].duplicated().any():
        raise RuntimeError("P2B_AH_TRUE_PAIR_DUPLICATE")
    if (true_pairs["a_code"].str.len() != 6).any() or (~true_pairs["a_code"].str.isdigit()).any():
        raise RuntimeError("P2B_AH_TRUE_PAIR_A_CODE")
    return pd.DataFrame(
        {
            "H股代码": true_pairs["h_code"].map(base.code5),
            "A股代码": true_pairs["a_code"].str.zfill(6),
            "名称": true_pairs["security_name"],
        }
    )


def install_static_context_adapters(
    sector_registry: pd.DataFrame,
    ah_source: pd.DataFrame,
) -> None:
    """Replace live industry/AH lookups with exact-code accepted snapshots."""

    hk = sector_registry[sector_registry["scope"].eq("HK_CANDIDATE")].set_index("security_id")
    a = sector_registry[sector_registry["scope"].eq("A_SHARE_DIRECT_HOLDING")].copy()
    a_by_code = a.set_index(a["security_code"].str.zfill(6))

    def hk_profile(symbol: str) -> pd.DataFrame:
        sid = "HKEX:" + base.code5(symbol)
        if sid not in hk.index:
            raise RuntimeError(f"P4_1R_STATIC_HK_SECTOR_NOT_FOUND:{sid}")
        sector = str(hk.loc[sid, "economic_sector"])
        return pd.DataFrame([["所属行业", sector]], columns=["项目", "内容"])

    def a_info(symbol: str) -> pd.DataFrame:
        code = str(symbol).strip().zfill(6)
        if code not in a_by_code.index:
            raise RuntimeError(f"P4_1R_STATIC_A_SECTOR_NOT_FOUND:{code}")
        sector = str(a_by_code.loc[code, "economic_sector"])
        return pd.DataFrame([["行业", sector]], columns=["item", "value"])

    base.ak.stock_zh_ah_spot_em = lambda: ah_source.copy()
    base.ak.stock_hk_company_profile_em = hk_profile
    base.ak.stock_individual_info_em = a_info


def build(root: Path, out: Path) -> dict[str, Any]:
    contract = base.read_json(root / "config/hkcu_p4_1r_portfolio_context_completion_contract.json")
    inputs = contract["authoritative_inputs"]
    real = base.read_json(root / inputs["real_positions_current"])
    simulation = base.read_json(root / inputs["simulation_positions_current"])
    holdings = [*real.get("holdings", []), *simulation.get("holdings", [])]

    canonical_a = load_canonical_a_share_histories(root, holdings)
    sector_registry = load_economic_sector_registry(root / inputs["p4_1r_economic_sector_registry"])
    ah_source = build_static_ah_source(root / inputs["p2b_ah_pair_registry"])

    original_fallback = base.fetch_holding_history
    base.load_hk_histories = load_hk_histories_compat
    base.fetch_holding_history = canonical_first_holding_fetcher(canonical_a, original_fallback)
    install_static_context_adapters(sector_registry, ah_source)
    return base.build(root, out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
