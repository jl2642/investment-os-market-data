#!/usr/bin/env python3
"""Benchmark free AKShare A-share historical daily sources on GitHub Linux.

The benchmark is deterministic, fail-closed and evidence-producing. It does not
create factor scores or investment recommendations.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import signal
import statistics
import sys
import time
from typing import Any, Callable
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BUSINESS_TZ = ZoneInfo("Asia/Shanghai")
CURRENT_UNIVERSE = ROOT / "outputs/current/A_SHARE_UNIVERSE.csv"
CURRENT_RELEASE = ROOT / "outputs/current/CURRENT_RELEASE.json"
OUTPUT_DIR = ROOT / "outputs/benchmark/fmdl2a"

BOARD_QUOTAS = {"SH_MAIN": 30, "SZ_MAIN": 30, "STAR": 20, "CHINEXT": 20, "BSE": 20}
SMOKE_PER_BOARD = 3


class CallTimeout(TimeoutError):
    pass


def _alarm_handler(_signum: int, _frame: Any) -> None:
    raise CallTimeout("source call timed out")


def timed_call(call: Callable[[], pd.DataFrame], timeout_seconds: int) -> tuple[pd.DataFrame, float]:
    old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    started = time.perf_counter()
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        frame = call()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
    return frame, time.perf_counter() - started


def stable_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_current() -> tuple[pd.DataFrame, dict[str, Any]]:
    if not CURRENT_UNIVERSE.exists() or not CURRENT_RELEASE.exists():
        raise RuntimeError("Accepted FMDL-1 Current release is missing")
    universe = pd.read_csv(CURRENT_UNIVERSE, dtype={"symbol": str})
    release = json.loads(CURRENT_RELEASE.read_text(encoding="utf-8"))
    if release.get("status") not in {"PUBLISHED", "PUBLISHED_WITH_WARNINGS"}:
        raise RuntimeError("Current release is not published")
    if release.get("hard_failures"):
        raise RuntimeError("Current release contains hard failures")
    return universe, release


def select_sample(universe: pd.DataFrame) -> pd.DataFrame:
    required = {"symbol", "board", "is_st", "is_suspended", "list_date"}
    missing = required.difference(universe.columns)
    if missing:
        raise RuntimeError(f"Universe missing sample fields: {sorted(missing)}")

    selected: list[pd.DataFrame] = []
    used: set[str] = set()
    for board, quota in BOARD_QUOTAS.items():
        group = universe.loc[universe["board"] == board].copy()
        group["special_priority"] = (
            group["is_st"].astype(str).str.lower().eq("true").astype(int) * 2
            + group["is_suspended"].astype(str).str.lower().eq("true").astype(int)
        )
        group["stable_key"] = group["symbol"].map(stable_key)
        group = group.sort_values(["special_priority", "stable_key"], ascending=[False, True])
        take = group.head(quota).copy()
        selected.append(take)
        used.update(take["symbol"].tolist())

    result = pd.concat(selected, ignore_index=True)
    target = sum(BOARD_QUOTAS.values())
    if len(result) < target:
        remainder = universe.loc[~universe["symbol"].isin(used)].copy()
        remainder["stable_key"] = remainder["symbol"].map(stable_key)
        result = pd.concat([result, remainder.sort_values("stable_key").head(target - len(result))], ignore_index=True)
    result = result.head(target).copy()
    result["sample_order"] = range(1, len(result) + 1)
    return result


def smoke_sample(scale_sample: pd.DataFrame) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    for board in BOARD_QUOTAS:
        pieces.append(scale_sample.loc[scale_sample["board"] == board].head(SMOKE_PER_BOARD))
    return pd.concat(pieces, ignore_index=True)


def prefixed_symbol(symbol: str) -> str:
    code, suffix = symbol.split(".")
    return {"SH": "sh", "SZ": "sz", "BJ": "bj"}[suffix] + code


def provider_functions(start_date: str, end_date: str) -> dict[str, Callable[[str], pd.DataFrame]]:
    providers: dict[str, Callable[[str], pd.DataFrame]] = {}
    if hasattr(ak, "stock_zh_a_hist"):
        providers["eastmoney_hist"] = lambda symbol: ak.stock_zh_a_hist(
            symbol=symbol.split(".")[0], period="daily", start_date=start_date,
            end_date=end_date, adjust="qfq"
        )
    if hasattr(ak, "stock_zh_a_daily"):
        providers["sina_daily"] = lambda symbol: ak.stock_zh_a_daily(
            symbol=prefixed_symbol(symbol), start_date=start_date, end_date=end_date,
            adjust="qfq"
        )
    if hasattr(ak, "stock_zh_a_hist_tx"):
        providers["tencent_hist"] = lambda symbol: ak.stock_zh_a_hist_tx(
            symbol=prefixed_symbol(symbol), start_date=start_date, end_date=end_date,
            adjust="qfq"
        )
    return providers


def find_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {str(column).strip().lower(): str(column) for column in frame.columns}
    for candidate in candidates:
        if candidate.lower() in normalized:
            return normalized[candidate.lower()]
    return None


def normalize_history(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError("empty_or_non_dataframe")
    data = frame.reset_index().copy()
    date_col = find_column(data, ["日期", "date", "day", "index"])
    mappings = {
        "open": ["开盘", "open"],
        "high": ["最高", "high"],
        "low": ["最低", "low"],
        "close": ["收盘", "close"],
        "volume": ["成交量", "volume", "vol"],
        "amount": ["成交额", "amount", "turnover"],
    }
    columns = {name: find_column(data, names) for name, names in mappings.items()}
    if date_col is None or columns["close"] is None:
        raise ValueError(f"unrecognized_schema columns={list(map(str, data.columns))}")

    normalized = pd.DataFrame({"date": pd.to_datetime(data[date_col], errors="coerce")})
    for name, source in columns.items():
        normalized[name] = pd.to_numeric(data[source], errors="coerce") if source else math.nan
    normalized = normalized.dropna(subset=["date", "close"]).sort_values("date")
    duplicates = int(normalized["date"].duplicated().sum())
    normalized = normalized.drop_duplicates("date", keep="last").reset_index(drop=True)
    invalid_close = int((normalized["close"] <= 0).sum())
    impossible_ohlc = 0
    if all(columns.get(key) for key in ("open", "high", "low", "close")):
        valid = normalized[["open", "high", "low", "close"]].dropna()
        impossible_ohlc = int(((valid["high"] < valid[["open", "close", "low"]].max(axis=1)) |
                               (valid["low"] > valid[["open", "close", "high"]].min(axis=1))).sum())
    meta = {
        "recognized_date": date_col is not None,
        "recognized_close": columns["close"] is not None,
        "recognized_ohlc": all(columns.get(key) for key in ("open", "high", "low", "close")),
        "recognized_volume": columns["volume"] is not None,
        "recognized_amount": columns["amount"] is not None,
        "duplicate_dates": duplicates,
        "invalid_close_rows": invalid_close,
        "impossible_ohlc_rows": impossible_ohlc,
    }
    return normalized, meta


def run_one(
    provider: str,
    call: Callable[[str], pd.DataFrame],
    row: pd.Series,
    *,
    timeout_seconds: int,
    requested_end: date,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "provider": provider,
        "symbol": row["symbol"],
        "board": row["board"],
        "list_date": row.get("list_date"),
        "success": False,
        "latency_seconds": None,
        "row_count": 0,
        "latest_date": None,
        "latest_date_matches_current": False,
        "has_251_observations": False,
        "recognized_ohlc": False,
        "recognized_volume": False,
        "recognized_amount": False,
        "duplicate_dates": None,
        "invalid_close_rows": None,
        "impossible_ohlc_rows": None,
        "error": None,
    }
    try:
        frame, latency = timed_call(lambda: call(str(row["symbol"])), timeout_seconds)
        normalized, meta = normalize_history(frame)
        if normalized.empty:
            raise ValueError("normalized_history_empty")
        latest = normalized["date"].max().date()
        result.update({
            "success": True,
            "latency_seconds": round(latency, 4),
            "row_count": int(len(normalized)),
            "latest_date": latest.isoformat(),
            "latest_date_matches_current": latest == requested_end,
            "has_251_observations": len(normalized) >= 251,
            **meta,
        })
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"[:1000]
    return result


def summarize(details: pd.DataFrame, sample: pd.DataFrame) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for provider, group in details.groupby("provider"):
        successful = group.loc[group["success"] == True]  # noqa: E712
        latencies = successful["latency_seconds"].dropna().astype(float).tolist()
        board_success = {}
        for board in BOARD_QUOTAS:
            board_group = group.loc[group["board"] == board]
            board_success[board] = None if board_group.empty else round(float(board_group["success"].mean()), 4)
        summaries.append({
            "provider": provider,
            "attempts": int(len(group)),
            "success_count": int(group["success"].sum()),
            "success_ratio": round(float(group["success"].mean()), 4),
            "latest_session_ratio": round(float(successful["latest_date_matches_current"].mean()), 4) if len(successful) else 0.0,
            "ohlc_schema_ratio": round(float(successful["recognized_ohlc"].mean()), 4) if len(successful) else 0.0,
            "volume_schema_ratio": round(float(successful["recognized_volume"].mean()), 4) if len(successful) else 0.0,
            "amount_schema_ratio": round(float(successful["recognized_amount"].mean()), 4) if len(successful) else 0.0,
            "median_latency_seconds": round(statistics.median(latencies), 4) if latencies else None,
            "p95_latency_seconds": round(float(pd.Series(latencies).quantile(0.95)), 4) if latencies else None,
            "median_rows": int(successful["row_count"].median()) if len(successful) else 0,
            "seasoned_251_ratio": round(float(successful["has_251_observations"].mean()), 4) if len(successful) else 0.0,
            "duplicate_date_rows": int(successful["duplicate_dates"].fillna(0).sum()) if len(successful) else 0,
            "invalid_close_rows": int(successful["invalid_close_rows"].fillna(0).sum()) if len(successful) else 0,
            "impossible_ohlc_rows": int(successful["impossible_ohlc_rows"].fillna(0).sum()) if len(successful) else 0,
            "board_success_ratio": board_success,
        })
    return sorted(summaries, key=lambda item: item["provider"])


def smoke_score(summary: dict[str, Any]) -> float:
    latency = summary.get("median_latency_seconds")
    latency_score = 0.0 if latency is None else max(0.0, 1.0 - min(float(latency), 10.0) / 10.0)
    board_values = [value for value in summary["board_success_ratio"].values() if value is not None]
    board_score = sum(board_values) / len(board_values) if board_values else 0.0
    return (
        0.45 * summary["success_ratio"]
        + 0.25 * summary["latest_session_ratio"]
        + 0.15 * summary["ohlc_schema_ratio"]
        + 0.10 * board_score
        + 0.05 * latency_score
    )


def recommendation(scale_summaries: list[dict[str, Any]], smoke_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    scale_ranked = sorted(scale_summaries, key=lambda item: (
        item["success_ratio"], item["latest_session_ratio"], item["amount_schema_ratio"],
        -(item["median_latency_seconds"] or 999)
    ), reverse=True)
    ranked = scale_ranked or sorted(smoke_summaries, key=smoke_score, reverse=True)
    primary = ranked[0]["provider"] if ranked else None
    fallback = [item["provider"] for item in ranked[1:]]
    readiness = "BLOCKED"
    reasons: list[str] = []
    if ranked:
        first = ranked[0]
        board_values = [value for value in first["board_success_ratio"].values() if value is not None]
        min_board = min(board_values) if board_values else 0.0
        if first["success_ratio"] >= 0.90 and first["latest_session_ratio"] >= 0.90 and min_board >= 0.75:
            readiness = "READY_FOR_FMDL_2B"
        elif first["success_ratio"] >= 0.75:
            readiness = "CONDITIONAL_BOARD_ROUTING_OR_RETRY_REQUIRED"
            reasons.append("Primary source does not meet all production thresholds")
        else:
            reasons.append("No free source reached minimum scale reliability")
    else:
        reasons.append("No source completed benchmark calls")

    board_routes: dict[str, str | None] = {}
    all_ranked = scale_summaries or smoke_summaries
    for board in BOARD_QUOTAS:
        candidates = sorted(
            all_ranked,
            key=lambda item: (
                item["board_success_ratio"].get(board) or 0.0,
                item["latest_session_ratio"],
                -(item["median_latency_seconds"] or 999),
            ),
            reverse=True,
        )
        board_routes[board] = candidates[0]["provider"] if candidates and (candidates[0]["board_success_ratio"].get(board) or 0) > 0 else None

    return {
        "production_readiness": readiness,
        "primary_provider": primary,
        "fallback_order": fallback,
        "board_routes": board_routes,
        "reasons": reasons,
        "required_fmdl2b_controls": [
            "partitioned historical cache",
            "per-symbol retry and timeout",
            "incremental daily append after initial backfill",
            "qfq price series plus unadjusted liquidity series",
            "provider and adjustment lineage per symbol",
            "new-listing partial-history handling",
            "hash, duplicate-date, impossible-OHLC and freshness gates",
            "failed symbols isolated without failing the entire market",
        ],
        "trade_authority": "NONE",
    }


def write_markdown(payload: dict[str, Any]) -> None:
    lines = [
        "# FMDL-2A Historical Source Benchmark",
        "",
        f"- Run ID: `{payload['run_id']}`",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Current as-of date: `{payload['current_as_of_date']}`",
        f"- AKShare version: `{payload['akshare_version']}`",
        f"- Scale sample: `{payload['sample']['scale_size']}` symbols",
        f"- Smoke sample: `{payload['sample']['smoke_size']}` symbols",
        f"- Production readiness: `{payload['recommendation']['production_readiness']}`",
        f"- Primary provider: `{payload['recommendation']['primary_provider']}`",
        f"- Fallback order: `{', '.join(payload['recommendation']['fallback_order']) or 'NONE'}`",
        "",
        "## Smoke results",
        "",
        "| Provider | Attempts | Success | Latest session | OHLC | Amount | Median sec | P95 sec |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in payload["smoke_summary"]:
        lines.append(
            f"| {item['provider']} | {item['attempts']} | {item['success_ratio']:.1%} | "
            f"{item['latest_session_ratio']:.1%} | {item['ohlc_schema_ratio']:.1%} | "
            f"{item['amount_schema_ratio']:.1%} | {item['median_latency_seconds']} | {item['p95_latency_seconds']} |"
        )
    lines.extend(["", "## Scale results", "", "| Provider | Attempts | Success | Latest session | Median rows | Median sec | P95 sec |", "|---|---:|---:|---:|---:|---:|---:|"])
    for item in payload["scale_summary"]:
        lines.append(
            f"| {item['provider']} | {item['attempts']} | {item['success_ratio']:.1%} | "
            f"{item['latest_session_ratio']:.1%} | {item['median_rows']} | "
            f"{item['median_latency_seconds']} | {item['p95_latency_seconds']} |"
        )
    lines.extend(["", "## Board routing", ""])
    for board, provider in payload["recommendation"]["board_routes"].items():
        lines.append(f"- `{board}`: `{provider}`")
    lines.extend([
        "",
        "## Decision boundary",
        "",
        "This benchmark selects a technical historical-data route only. It does not validate alpha, rank stocks, alter the candidate pool or create trade permission.",
    ])
    (OUTPUT_DIR / "FMDL2A_HISTORICAL_SOURCE_BENCHMARK.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-seconds", type=int, default=15)
    parser.add_argument("--pause-seconds", type=float, default=0.15)
    parser.add_argument("--fallback-scale-size", type=int, default=40)
    args = parser.parse_args()

    universe, release = load_current()
    current_end = date.fromisoformat(release["as_of_date"])
    start = current_end - timedelta(days=550)
    start_text = start.strftime("%Y%m%d")
    end_text = current_end.strftime("%Y%m%d")
    providers = provider_functions(start_text, end_text)
    if not providers:
        raise RuntimeError("Installed AKShare exposes no benchmark candidate functions")

    scale = select_sample(universe)
    smoke = smoke_sample(scale)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    scale.to_csv(OUTPUT_DIR / "FMDL2A_BENCHMARK_SAMPLE.csv", index=False, encoding="utf-8-sig")

    details: list[dict[str, Any]] = []
    for provider, call in providers.items():
        for _, row in smoke.iterrows():
            record = run_one(provider, call, row, timeout_seconds=args.timeout_seconds, requested_end=current_end)
            record["stage"] = "SMOKE"
            details.append(record)
            time.sleep(args.pause_seconds)

    smoke_df = pd.DataFrame(details)
    smoke_summaries = summarize(smoke_df, smoke)
    eligible = [item for item in smoke_summaries if item["success_ratio"] >= 0.60 and item["ohlc_schema_ratio"] >= 0.90]
    eligible = sorted(eligible, key=smoke_score, reverse=True)[:2]

    scale_details: list[dict[str, Any]] = []
    for index, summary in enumerate(eligible):
        provider = summary["provider"]
        subset = scale if index == 0 else scale.head(args.fallback_scale_size)
        for _, row in subset.iterrows():
            record = run_one(provider, providers[provider], row, timeout_seconds=args.timeout_seconds, requested_end=current_end)
            record["stage"] = "SCALE_PRIMARY" if index == 0 else "SCALE_FALLBACK"
            scale_details.append(record)
            time.sleep(args.pause_seconds)

    all_details = pd.concat([smoke_df, pd.DataFrame(scale_details)], ignore_index=True)
    all_details.to_csv(OUTPUT_DIR / "FMDL2A_HISTORICAL_SOURCE_DETAILS.csv", index=False, encoding="utf-8-sig")
    scale_df = pd.DataFrame(scale_details)
    scale_summaries = summarize(scale_df, scale) if not scale_df.empty else []

    generated_at = datetime.now(tz=BUSINESS_TZ).isoformat(timespec="seconds")
    run_id = datetime.now(tz=BUSINESS_TZ).strftime("FMDL2A_%Y%m%dT%H%M%S%z")
    payload = {
        "benchmark_version": "1.0.0",
        "run_id": run_id,
        "generated_at": generated_at,
        "current_run_id": release["run_id"],
        "current_as_of_date": release["as_of_date"],
        "akshare_version": getattr(ak, "__version__", "unknown"),
        "request": {"start_date": start_text, "end_date": end_text, "adjust": "qfq", "timeout_seconds": args.timeout_seconds},
        "installed_candidates": sorted(providers),
        "sample": {
            "scale_size": int(len(scale)),
            "smoke_size": int(len(smoke)),
            "board_counts": {key: int(value) for key, value in scale["board"].value_counts().to_dict().items()},
            "sample_sha256": hashlib.sha256((OUTPUT_DIR / "FMDL2A_BENCHMARK_SAMPLE.csv").read_bytes()).hexdigest(),
        },
        "smoke_summary": smoke_summaries,
        "scale_summary": scale_summaries,
        "recommendation": recommendation(scale_summaries, smoke_summaries),
        "known_limitations": [
            "Public free providers may throttle or reject GitHub-hosted runner IP ranges.",
            "Benchmark success establishes technical usability, not commercial SLA or permanent availability.",
            "The sample is deterministic and cross-board but is not a proof of all 5,529-symbol backfill completion.",
            "Corporate-action correctness requires FMDL-2B replay and adjustment regression tests.",
        ],
    }
    (OUTPUT_DIR / "FMDL2A_HISTORICAL_SOURCE_BENCHMARK.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    write_markdown(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["recommendation"]["production_readiness"] != "BLOCKED" else 2


if __name__ == "__main__":
    sys.exit(main())
