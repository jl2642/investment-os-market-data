#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from automation.wp3_2a.acquire_universe import sina
from automation.wp3_r.refresh_candidate_price_ledger import BENCHMARK_ID, fetch_quotes


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def normalize_security_id(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip().upper()
    if not raw:
        return None
    if "." in raw:
        code, suffix = raw.split(".", 1)
        return f"{code.zfill(6)}.{suffix}"
    code = raw.zfill(6)
    if code.startswith(("4", "8", "92")):
        return f"{code}.BJ"
    if code.startswith(("5", "6")):
        return f"{code}.SH"
    return f"{code}.SZ"


def collect_candidate_rows(value: Any, route: str = "ROOT") -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if isinstance(value, dict):
        raw = None
        for key in ("security_id", "security_code", "stock_code", "code", "symbol"):
            if key in value:
                raw = value[key]
                break
        sid = normalize_security_id(raw)
        if sid:
            rows.append(
                {
                    "security_id": sid,
                    "security_name": str(value.get("security_name") or value.get("stock_name") or ""),
                    "route": route,
                }
            )
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                rows.extend(collect_candidate_rows(child, key.upper()))
    elif isinstance(value, list):
        for child in value:
            rows.extend(collect_candidate_rows(child, route))
    return rows


def tracked_candidates(candidate: dict[str, Any]) -> list[dict[str, str]]:
    allowed = {"CANDIDATE_CORE_MEMBERS", "SHADOW_TRACK_MEMBERS", "RESEARCH_QUEUE_MEMBERS"}
    result: dict[str, dict[str, str]] = {}
    for row in collect_candidate_rows(candidate):
        if row["route"] in allowed:
            result[row["security_id"]] = row
    return sorted(result.values(), key=lambda row: (row["route"], row["security_id"]))


def as_float(value: Any) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--candidate-current", default="investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json")
    parser.add_argument("--output", default="investment_os_runtime/30_STATE_CURRENT/45_CANDIDATE_OPERATIONS/WEEKLY_PRICE_SCREEN_CURRENT.json")
    parser.add_argument("--run-output", default="investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_R/CANDIDATE_MARKET_SCREEN_RUN_CURRENT.json")
    parser.add_argument("--timeout", type=int, default=35)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    candidate = read_json(root / args.candidate_current)
    tracked = tracked_candidates(candidate)
    if len(tracked) != 73:
        raise ValueError(f"EXPECTED_73_TRACKED_CANDIDATES_GOT:{len(tracked)}")

    # The Sina market-centre endpoint carries current price, liquidity and valuation
    # fields but not a row-level trading date. Anchor the snapshot to the CSI 300
    # quote date returned by Sina's dated quote endpoint, then use that accepted
    # completed session for every row in the same provider snapshot.
    benchmark_quotes = fetch_quotes([BENCHMARK_ID])
    if len(benchmark_quotes) != 1:
        raise ValueError("BENCHMARK_SESSION_QUOTE_NOT_UNIQUE")
    accepted_session = str(benchmark_quotes[0]["trade_date"])

    with tempfile.TemporaryDirectory(prefix="wp3r-candidate-market-") as tmp:
        all_rows, provider_meta = sina(Path(tmp), 100, args.timeout, accepted_session)

    by_code = {str(row["security_code"]).zfill(6): row for row in all_rows}
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for target in tracked:
        code = target["security_id"].split(".", 1)[0]
        source = by_code.get(code)
        if source is None:
            missing.append(target["security_id"])
            continue
        price = as_float(source.get("last_price"))
        if price is None or price <= 0:
            raise ValueError(f"INVALID_CANDIDATE_PRICE:{target['security_id']}")
        rows.append(
            {
                "security_id": target["security_id"],
                "security_name": target["security_name"] or str(source.get("security_name") or ""),
                "candidate_route": target["route"],
                "price": price,
                "price_as_of": accepted_session,
                "price_age_calendar_days": 0,
                "one_day_change_pct": as_float(source.get("change_pct")),
                "turnover_amount": as_float(source.get("turnover_amount")),
                "turnover_rate_pct": as_float(source.get("turnover_rate_pct")),
                "pe_ttm": as_float(source.get("pe_ttm")),
                "pb": as_float(source.get("pb")),
                "freshness_status": "FRESH",
                "screen_role": "PRICE_VALUATION_AND_LIQUIDITY_MONITOR_ONLY",
            }
        )

    if missing:
        raise ValueError("MISSING_CANDIDATE_QUOTES:" + ",".join(sorted(missing)))
    if len(rows) != 73 or len({row["security_id"] for row in rows}) != 73:
        raise ValueError("CANDIDATE_MARKET_SCREEN_COVERAGE_OR_DUPLICATE_FAILURE")

    payload = {
        "state_id": "WP3R_WEEKLY_PRICE_SCREEN_CURRENT",
        "status": "PASS_WEEKLY_PRICE_SCREEN_NO_MEMBERSHIP_MUTATION",
        "as_of_date": accepted_session,
        "tracked_count": 73,
        "covered_count": 73,
        "missing_security_ids": [],
        "stale_security_ids": [],
        "rows": rows,
        "candidate_membership_mutations": 0,
        "research_object_mutations": 0,
        "buy_signals": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    write_json(root / args.output, payload)

    run = {
        "state_id": "WP3R_CANDIDATE_MARKET_SCREEN_RUN_CURRENT",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS_CANDIDATE_MARKET_SCREEN_CURRENT",
        "accepted_session": accepted_session,
        "session_authority": "SINA_DATED_CSI300_QUOTE",
        "snapshot_provider": provider_meta.get("provider"),
        "snapshot_row_count": len(all_rows),
        "tracked_count": 73,
        "covered_count": 73,
        "candidate_membership_mutations": 0,
        "research_object_mutations": 0,
        "portfolio_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    write_json(root / args.run_output, run)
    print(json.dumps(run, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
