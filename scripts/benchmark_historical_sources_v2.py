#!/usr/bin/env python3
"""FMDL-2A benchmark v2: retry-aware and scope-aware provider selection."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd

from scripts import benchmark_historical_sources as base

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs/benchmark/fmdl2a"
BUSINESS_TZ = ZoneInfo("Asia/Shanghai")


def run_with_retries(provider, call, row, *, timeout_seconds: int, requested_end: date, attempts: int) -> dict:
    errors: list[str] = []
    total_latency = 0.0
    for attempt in range(1, attempts + 1):
        record = base.run_one(
            provider, call, row, timeout_seconds=timeout_seconds, requested_end=requested_end
        )
        if record.get("latency_seconds") is not None:
            total_latency += float(record["latency_seconds"])
        if record["success"]:
            record["source_attempts"] = attempt
            record["prior_errors"] = errors
            record["total_attempt_latency_seconds"] = round(total_latency, 4)
            return record
        errors.append(str(record.get("error")))
        if attempt < attempts:
            time.sleep(1.5 * attempt)
    record["source_attempts"] = attempts
    record["prior_errors"] = errors[:-1]
    record["total_attempt_latency_seconds"] = round(total_latency, 4)
    return record


def scoped_summaries(details: pd.DataFrame, scale_size: int) -> list[dict]:
    summaries = base.summarize(details, details)
    for item in summaries:
        item["scale_scope"] = "FULL_SCALE" if item["attempts"] >= scale_size else "FALLBACK_SUBSAMPLE"
        item["capabilities"] = {
            "qfq_price": item["ohlc_schema_ratio"] >= 0.95,
            "historical_volume": item["volume_schema_ratio"] >= 0.95,
            "historical_amount": item["amount_schema_ratio"] >= 0.95,
        }
    return summaries


def make_recommendation(scale_summaries: list[dict], smoke_summaries: list[dict], scale_size: int) -> dict:
    full_scale = [item for item in scale_summaries if item["attempts"] >= scale_size]
    ranked_full = sorted(
        full_scale,
        key=lambda item: (
            item["success_ratio"],
            item["latest_session_ratio"],
            item["volume_schema_ratio"],
            item["amount_schema_ratio"],
            -(item["median_latency_seconds"] or 999),
        ),
        reverse=True,
    )
    primary = ranked_full[0] if ranked_full else None
    other = [item for item in scale_summaries if primary is None or item["provider"] != primary["provider"]]
    fallback_ranked = sorted(
        other,
        key=lambda item: (
            item["success_ratio"], item["latest_session_ratio"],
            item["ohlc_schema_ratio"], item["amount_schema_ratio"],
            -(item["median_latency_seconds"] or 999),
        ),
        reverse=True,
    )

    readiness = "BLOCKED"
    reasons: list[str] = []
    if primary:
        board_values = [value for value in primary["board_success_ratio"].values() if value is not None]
        min_board = min(board_values) if board_values else 0.0
        if primary["success_ratio"] >= 0.95 and primary["latest_session_ratio"] >= 0.98 and min_board >= 0.85:
            readiness = "READY_FOR_FMDL_2B"
        elif primary["success_ratio"] >= 0.85:
            readiness = "CONDITIONAL_RETRY_AND_BOARD_ROUTING_REQUIRED"
            reasons.append("Full-scale primary did not meet all preferred thresholds")
        else:
            reasons.append("No full-scale provider reached minimum reliability")
    else:
        reasons.append("No provider was tested over the full 120-symbol scale sample")

    primary_name = None if primary is None else primary["provider"]
    fallback_specs = []
    for item in fallback_ranked:
        if item["success_ratio"] < 0.60:
            continue
        capability = "FULL_HISTORY" if item["volume_schema_ratio"] >= 0.95 else "QFQ_PRICE_AND_AMOUNT_ONLY"
        fallback_specs.append({
            "provider": item["provider"],
            "capability": capability,
            "sample_scope": item.get("scale_scope"),
            "excluded_boards": [board for board, ratio in item["board_success_ratio"].items() if ratio == 0],
        })

    board_routes = {}
    for board in base.BOARD_QUOTAS:
        primary_ratio = None if primary is None else primary["board_success_ratio"].get(board)
        board_routes[board] = {
            "primary": primary_name if primary_ratio is not None and primary_ratio >= 0.75 else None,
            "price_fallback": None,
        }
        candidates = [
            item for item in fallback_ranked
            if item["ohlc_schema_ratio"] >= 0.95
            and (item["board_success_ratio"].get(board) or 0) >= 0.75
        ]
        if candidates:
            board_routes[board]["price_fallback"] = candidates[0]["provider"]

    return {
        "production_readiness": readiness,
        "primary_provider": primary_name,
        "primary_scope_requirement": "FULL_120_SYMBOL_CROSS_BOARD_SAMPLE",
        "fallbacks": fallback_specs,
        "board_routes": board_routes,
        "reasons": reasons,
        "interpretation": {
            "eastmoney_hist": "Not selected when GitHub runner disconnections keep smoke success below threshold.",
            "sina_daily": "Preferred full-market route when it passes the full cross-board scale test; retry transient timeouts and JSON failures.",
            "tencent_hist": "Price/amount fallback only when volume is absent; do not use for BSE unless separately validated.",
        },
        "required_fmdl2b_controls": [
            "partitioned historical cache",
            "two-attempt per-symbol retry with backoff before quarantine",
            "incremental daily append after initial backfill",
            "qfq adjusted price plus source-reported liquidity lineage",
            "provider, board route and adjustment lineage per symbol",
            "new-listing partial-history handling",
            "hash, duplicate-date, impossible-OHLC and freshness gates",
            "failed symbols isolated without failing the entire market",
            "Sina primary and Tencent price-only fallback must never be silently mixed",
        ],
        "trade_authority": "NONE",
    }


def write_markdown(payload: dict) -> None:
    recommendation = payload["recommendation"]
    lines = [
        "# FMDL-2A Historical Source Benchmark — Retry-Aware Final",
        "",
        f"- Run ID: `{payload['run_id']}`",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Current as-of date: `{payload['current_as_of_date']}`",
        f"- AKShare version: `{payload['akshare_version']}`",
        f"- Scale sample: `{payload['sample']['scale_size']}` symbols",
        f"- Production readiness: `{recommendation['production_readiness']}`",
        f"- Primary provider: `{recommendation['primary_provider']}`",
        "",
        "## Scale results",
        "",
        "| Provider | Scope | Attempts | Success | Latest | Volume | Amount | Median sec | P95 sec |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in payload["scale_summary"]:
        lines.append(
            f"| {item['provider']} | {item['scale_scope']} | {item['attempts']} | "
            f"{item['success_ratio']:.1%} | {item['latest_session_ratio']:.1%} | "
            f"{item['volume_schema_ratio']:.1%} | {item['amount_schema_ratio']:.1%} | "
            f"{item['median_latency_seconds']} | {item['p95_latency_seconds']} |"
        )
    lines.extend(["", "## Routing decision", ""])
    for board, route in recommendation["board_routes"].items():
        lines.append(f"- `{board}`: primary=`{route['primary']}`, price fallback=`{route['price_fallback']}`")
    lines.extend([
        "",
        "## Decision boundary",
        "",
        "The benchmark selects a technical data route only. It does not demonstrate alpha, rank stocks, change a portfolio or create trade permission.",
    ])
    (OUTPUT_DIR / "FMDL2A_HISTORICAL_SOURCE_BENCHMARK.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-seconds", type=int, default=15)
    parser.add_argument("--pause-seconds", type=float, default=0.15)
    parser.add_argument("--fallback-scale-size", type=int, default=40)
    parser.add_argument("--scale-attempts", type=int, default=2)
    args = parser.parse_args()

    universe, release = base.load_current()
    current_end = date.fromisoformat(release["as_of_date"])
    start = current_end - timedelta(days=550)
    providers = base.provider_functions(start.strftime("%Y%m%d"), current_end.strftime("%Y%m%d"))
    if not providers:
        raise RuntimeError("Installed AKShare exposes no benchmark candidate functions")

    scale = base.select_sample(universe)
    smoke = base.smoke_sample(scale)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    scale_path = OUTPUT_DIR / "FMDL2A_BENCHMARK_SAMPLE.csv"
    scale.to_csv(scale_path, index=False, encoding="utf-8-sig")

    smoke_details = []
    for provider, call in providers.items():
        for _, row in smoke.iterrows():
            record = run_with_retries(provider, call, row, timeout_seconds=args.timeout_seconds, requested_end=current_end, attempts=1)
            record["stage"] = "SMOKE"
            smoke_details.append(record)
            time.sleep(args.pause_seconds)
    smoke_df = pd.DataFrame(smoke_details)
    smoke_summaries = base.summarize(smoke_df, smoke)
    eligible = [item for item in smoke_summaries if item["success_ratio"] >= 0.60 and item["ohlc_schema_ratio"] >= 0.90]
    eligible = sorted(eligible, key=base.smoke_score, reverse=True)[:2]

    scale_details = []
    for index, summary in enumerate(eligible):
        provider = summary["provider"]
        subset = scale if index == 0 else scale.head(args.fallback_scale_size)
        for _, row in subset.iterrows():
            record = run_with_retries(
                provider, providers[provider], row,
                timeout_seconds=args.timeout_seconds,
                requested_end=current_end,
                attempts=args.scale_attempts,
            )
            record["stage"] = "SCALE_PRIMARY" if index == 0 else "SCALE_FALLBACK"
            scale_details.append(record)
            time.sleep(args.pause_seconds)

    scale_df = pd.DataFrame(scale_details)
    all_details = pd.concat([smoke_df, scale_df], ignore_index=True)
    all_details.to_csv(OUTPUT_DIR / "FMDL2A_HISTORICAL_SOURCE_DETAILS.csv", index=False, encoding="utf-8-sig")
    scale_summaries = scoped_summaries(scale_df, len(scale)) if not scale_df.empty else []
    rec = make_recommendation(scale_summaries, smoke_summaries, len(scale))

    now = datetime.now(tz=BUSINESS_TZ)
    payload = {
        "benchmark_version": "2.0.0",
        "run_id": now.strftime("FMDL2A_R2_%Y%m%dT%H%M%S%z"),
        "generated_at": now.isoformat(timespec="seconds"),
        "current_run_id": release["run_id"],
        "current_as_of_date": release["as_of_date"],
        "akshare_version": getattr(ak, "__version__", "unknown"),
        "request": {
            "start_date": start.strftime("%Y%m%d"),
            "end_date": current_end.strftime("%Y%m%d"),
            "adjust": "qfq",
            "timeout_seconds": args.timeout_seconds,
            "scale_attempts": args.scale_attempts,
        },
        "installed_candidates": sorted(providers),
        "sample": {
            "scale_size": int(len(scale)),
            "smoke_size": int(len(smoke)),
            "board_counts": {key: int(value) for key, value in scale["board"].value_counts().to_dict().items()},
            "sample_sha256": hashlib.sha256(scale_path.read_bytes()).hexdigest(),
        },
        "smoke_summary": smoke_summaries,
        "scale_summary": scale_summaries,
        "recommendation": rec,
        "known_limitations": [
            "Free providers may throttle or reject GitHub-hosted runner IP ranges.",
            "A 120-symbol benchmark is not the 5,529-symbol initial backfill.",
            "Tencent fallback was not full-scale and lacks normalized historical volume in this interface.",
            "Corporate-action correctness still requires FMDL-2B replay and adjustment regression tests.",
            "Technical source readiness does not demonstrate factor alpha.",
        ],
    }
    (OUTPUT_DIR / "FMDL2A_HISTORICAL_SOURCE_BENCHMARK.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    write_markdown(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if rec["production_readiness"] != "BLOCKED" else 2


if __name__ == "__main__":
    sys.exit(main())
