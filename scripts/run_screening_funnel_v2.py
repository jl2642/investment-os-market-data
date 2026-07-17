#!/usr/bin/env python3
"""Identity-safe and cross-sleeve-comparable FMDL-2C entrypoint.

Unknown boards are review-only because a one-name board makes board-neutral
percentiles meaningless. Security-master names are bound into all usable
screening outputs. Final Longlist ranking uses within-sleeve rank percentiles
plus raw sleeve scores, avoiding direct comparison of differently distributed
sleeve scores.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from scripts import run_screening_funnel as engine

_ORIGINAL_LOAD_INPUTS = engine.load_inputs
_ORIGINAL_CLASSIFY = engine.classify_investability
_ORIGINAL_EVALUATE = engine.evaluate_sleeve
_ORIGINAL_QUALITY = engine.quality_payload


def load_inputs(
    root: Path = engine.ROOT,
) -> tuple[dict[str, Any], dict[str, Any], pd.DataFrame]:
    config, contracts, table = _ORIGINAL_LOAD_INPUTS(root)
    universe = pd.read_csv(
        root / "outputs/current/A_SHARE_UNIVERSE.csv", dtype={"symbol": str}
    )
    if universe["symbol"].astype(str).duplicated().any():
        raise RuntimeError("DUPLICATE_SECURITY_MASTER_SYMBOL")
    if set(universe["symbol"].astype(str)) != set(table["symbol"].astype(str)):
        raise RuntimeError("SECURITY_MASTER_FACTOR_SYMBOL_SET_MISMATCH")
    if set(universe["as_of_date"].astype(str)) != {
        str(contracts["release"]["as_of_date"])
    }:
        raise RuntimeError("SECURITY_MASTER_FACTOR_AS_OF_MISMATCH")
    identity_fields = [
        "symbol",
        "name",
        "exchange",
        "listing_status",
        "industry_name",
    ]
    missing = {"name", "exchange", "listing_status"}.difference(universe.columns)
    if missing:
        raise RuntimeError(f"SECURITY_MASTER_IDENTITY_COLUMNS_MISSING_{sorted(missing)}")
    available = [field for field in identity_fields if field in universe.columns]
    identity = universe[available].copy()
    identity["name"] = identity["name"].astype(str).str.strip()
    if identity["name"].eq("").any() or identity["name"].str.lower().eq("nan").any():
        raise RuntimeError("EMPTY_SECURITY_NAME")
    table = table.merge(identity, on="symbol", how="left", validate="one_to_one")
    if table["name"].isna().any():
        raise RuntimeError("UNBOUND_SECURITY_NAME")
    return config, contracts, table


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


def evaluate_sleeve(
    frame: pd.DataFrame,
    sleeve_id: str,
    sleeve: dict[str, Any],
    config: dict[str, Any],
) -> pd.DataFrame:
    result = _ORIGINAL_EVALUATE(frame, sleeve_id, sleeve, config)
    if result.empty:
        return result
    identity_fields = [
        field
        for field in ["symbol", "name", "exchange", "listing_status", "industry_name"]
        if field in frame.columns
    ]
    identity = frame[identity_fields].drop_duplicates("symbol")
    result = result.merge(identity, on="symbol", how="left", validate="many_to_one")
    first = [
        field
        for field in [
            "as_of_date",
            "symbol",
            "name",
            "exchange",
            "board",
            "listing_status",
            "industry_name",
        ]
        if field in result.columns
    ]
    return result[first + [column for column in result.columns if column not in first]]


def build_longlist(
    sleeve_detail: pd.DataFrame,
    screening_universe: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    if sleeve_detail.empty:
        return pd.DataFrame(columns=["as_of_date", "symbol", "name"])
    detail = sleeve_detail.copy()
    detail["sleeve_population"] = detail.groupby("sleeve_id")["symbol"].transform("count")
    detail["sleeve_rank_percentile"] = (
        detail["sleeve_population"] - detail["sleeve_rank"] + 1
    ) / detail["sleeve_population"]
    comparison = config["funnel"]["cross_sleeve_comparison"]
    rank_weight = float(comparison["rank_percentile_weight"])
    raw_weight = float(comparison["raw_score_weight"])
    if abs(rank_weight + raw_weight - 1.0) > 1e-9:
        raise RuntimeError("CROSS_SLEEVE_COMPARISON_WEIGHT_SUM")
    detail["normalized_sleeve_score"] = (
        detail["sleeve_rank_percentile"] * rank_weight
        + detail["sleeve_score"] * raw_weight
    )
    metadata = screening_universe.set_index("symbol")
    bonus_per = float(config["funnel"]["cross_sleeve_bonus_per_extra_sleeve"])
    bonus_max = float(config["funnel"]["cross_sleeve_bonus_maximum"])
    rows: list[dict[str, Any]] = []
    for symbol, group in detail.groupby("symbol", sort=True):
        ordered = group.sort_values(
            ["normalized_sleeve_score", "sleeve_score", "sleeve_id"],
            ascending=[False, False, True],
        )
        best = ordered.iloc[0]
        sleeves = ordered["sleeve_id"].astype(str).tolist()
        sleeve_count = len(sleeves)
        bonus = min(bonus_max, max(0, sleeve_count - 1) * bonus_per)
        meta = metadata.loc[str(symbol)]
        rows.append(
            {
                "as_of_date": str(best["as_of_date"]),
                "symbol": str(symbol),
                "name": str(meta["name"]),
                "exchange": str(meta["exchange"]),
                "board": str(best["board"]),
                "listing_status": str(meta["listing_status"]),
                "industry_name": (
                    None
                    if "industry_name" not in meta.index or pd.isna(meta["industry_name"])
                    else str(meta["industry_name"])
                ),
                "primary_sleeve": str(best["sleeve_id"]),
                "sleeves": "|".join(sleeves),
                "sleeve_count": sleeve_count,
                "primary_sleeve_rank": int(best["sleeve_rank"]),
                "primary_sleeve_rank_percentile": round(
                    float(best["sleeve_rank_percentile"]), 8
                ),
                "best_sleeve_score": round(float(best["sleeve_score"]), 8),
                "normalized_primary_score": round(
                    float(best["normalized_sleeve_score"]), 8
                ),
                "cross_sleeve_bonus": round(bonus, 8),
                "aggregate_score": round(
                    float(best["normalized_sleeve_score"]) + bonus, 8
                ),
                "score_basis": str(comparison["method"]),
                "investability_status": str(best["investability_status"]),
                "factor_record_quality": str(best["factor_record_quality"]),
                "confidence_grade": str(best["confidence_grade"]),
                "event_flag_count": int(engine.finite(best["event_flag_count"]) or 0),
                "avg_turnover_cny_20d": engine.finite(best["avg_turnover_cny_20d"]),
                "return_20d": engine.finite(best.get("return_20d")),
                "return_60d": engine.finite(best.get("return_60d")),
                "return_120d": engine.finite(best.get("return_120d")),
                "return_250d": engine.finite(best.get("return_250d")),
                "distance_52w_high": engine.finite(best.get("distance_52w_high")),
                "volatility_60d": engine.finite(best.get("volatility_60d")),
                "max_drawdown_120d": engine.finite(best.get("max_drawdown_120d")),
                "screen_row_hash": str(meta.get("screen_row_hash", "")),
                "next_workflow": config["funnel"]["next_workflow"],
                "authority": config["authority_boundary"],
            }
        )
    longlist = (
        pd.DataFrame(rows)
        .sort_values(
            [
                "aggregate_score",
                "normalized_primary_score",
                "best_sleeve_score",
                "avg_turnover_cny_20d",
                "symbol",
            ],
            ascending=[False, False, False, False, True],
        )
        .head(int(config["funnel"]["longlist_maximum"]))
        .reset_index(drop=True)
    )
    longlist["overall_rank"] = range(1, len(longlist) + 1)
    counts = config["funnel"]["priority_bucket_counts"]
    a_end = int(counts["A_IMMEDIATE_RESEARCH"])
    b_end = a_end + int(counts["B_WATCH_OR_TRIGGER"])
    longlist["research_priority"] = longlist["overall_rank"].map(
        lambda rank: (
            "A_IMMEDIATE_RESEARCH"
            if rank <= a_end
            else "B_WATCH_OR_TRIGGER"
            if rank <= b_end
            else "C_SCREEN_FLAG_ONLY"
        )
    )
    ordered_columns = [
        "as_of_date",
        "overall_rank",
        "research_priority",
        "symbol",
        "name",
    ] + [
        column
        for column in longlist.columns
        if column
        not in {"as_of_date", "overall_rank", "research_priority", "symbol", "name"}
    ]
    return longlist[ordered_columns]


def quality_payload(
    screen: pd.DataFrame,
    detail: pd.DataFrame,
    longlist: pd.DataFrame,
    funnel: pd.DataFrame,
    config: dict[str, Any],
    as_of_date: str,
) -> dict[str, Any]:
    payload = _ORIGINAL_QUALITY(
        screen, detail, longlist, funnel, config, as_of_date
    )
    if screen["name"].isna().any() or screen["name"].astype(str).str.strip().eq("").any():
        payload["hard_failures"].append("MISSING_SCREEN_SECURITY_NAME")
    if not longlist.empty and (
        longlist["name"].isna().any()
        or longlist["name"].astype(str).str.strip().eq("").any()
    ):
        payload["hard_failures"].append("MISSING_LONGLIST_SECURITY_NAME")
    primary_counts = (
        longlist["primary_sleeve"].value_counts().astype(int).to_dict()
        if not longlist.empty and "primary_sleeve" in longlist.columns
        else {}
    )
    membership_counts: dict[str, int] = {}
    if not detail.empty and not longlist.empty:
        selected = set(longlist["symbol"].astype(str))
        for sleeve_id, group in detail.groupby("sleeve_id"):
            membership_counts[str(sleeve_id)] = len(
                selected.intersection(set(group["symbol"].astype(str)))
            )
    payload["metrics"]["primary_sleeve_counts"] = {
        str(key): int(value) for key, value in primary_counts.items()
    }
    payload["metrics"]["longlist_membership_by_sleeve"] = membership_counts
    payload["metrics"]["named_screen_rows"] = int(screen["name"].notna().sum())
    payload["metrics"]["named_longlist_rows"] = int(
        longlist["name"].notna().sum() if not longlist.empty else 0
    )
    for sleeve_id, hit_count in payload["metrics"]["sleeve_counts"].items():
        if int(hit_count) > 0 and int(primary_counts.get(sleeve_id, 0)) == 0:
            payload["controlled_warnings"].append(
                f"NO_PRIMARY_LONGLIST_REPRESENTATION_{sleeve_id}"
            )
    if payload["hard_failures"]:
        payload["status"] = "FAIL"
    elif payload["controlled_warnings"]:
        payload["status"] = "PASS_WITH_WARNINGS"
    else:
        payload["status"] = "PASS"
    payload["cross_sleeve_comparison"] = config["funnel"][
        "cross_sleeve_comparison"
    ]
    return payload


def install_hardening() -> None:
    engine.load_inputs = load_inputs
    engine.classify_investability = classify_investability
    engine.evaluate_sleeve = evaluate_sleeve
    engine.build_longlist = build_longlist
    engine.quality_payload = quality_payload


def run(*args: Any, **kwargs: Any):
    install_hardening()
    return engine.run(*args, **kwargs)


if __name__ == "__main__":
    run()
