#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

HK_UNIVERSE = Path("outputs/fmdl5a/current/FMDL5A_CANONICAL_UNIVERSE.csv")
HK_LONGLIST = Path("outputs/fmdl5e/current/FMDL5E_RESEARCH_LONGLIST.csv")
HK_DUPLICATION = Path("outputs/fmdl5g/integration/current/FMDL5G_CROSS_MARKET_DUPLICATION_REVIEW.csv")
US_BENCHMARK = Path("outputs/fmdl6x3/current/screening_research_cards/FMDL6X3E_US_BENCHMARK_POOL.json")
US_MARKET_INITIAL = Path("outputs/fmdl6x2/current/market_reference/FMDL6X2D_INITIAL_COHORT.json")
US_MARKET_QUEUE = Path("outputs/fmdl6x2/current/market_reference/FMDL6X2D_BACKFILL_QUEUE.jsonl.gz")
US_SEC_INITIAL = Path("evidence/fmdl6x2e/2026-07-22/FMDL6X2E_FILINGS.csv")
US_SEC_QUEUE = Path("outputs/fmdl6x2/current/sec_filings_facts/FMDL6X2E_BACKFILL_QUEUE.jsonl.gz")
US_IDENTITY_LINEAGE = Path("outputs/fmdl6x2/current/identity/FMDL6X2B_IDENTITY_LINEAGE.jsonl.gz")
OPS_ROOT = Path("investment_os_runtime/30_STATE_CURRENT/46_CROSS_MARKET_OPERATIONS")
EVIDENCE_ROOT = Path("investment_os_runtime/40_EVIDENCE_AND_LINEAGE/CROSS_MARKET_LIMITED")
LEDGER_PATH = OPS_ROOT / "CROSS_MARKET_LIMITED_LEDGER_CURRENT.json"
RUN_PATH = OPS_ROOT / "CROSS_MARKET_LIMITED_RUN_CURRENT.json"
PROPOSAL_PATH = OPS_ROOT / "CROSS_MARKET_RESEARCH_PROPOSAL_CURRENT.json"

Fetcher = Callable[[str, dict[str, str] | None], bytes]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def stable_bucket(value: str, count: int) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:16], 16) % count


def first_value(row: dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def default_fetcher(url: str, headers: dict[str, str] | None = None) -> bytes:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=35) as response:
        return response.read()


def yahoo_symbol(market: str, raw_symbol: str) -> str:
    symbol = raw_symbol.strip().upper()
    if market == "HK":
        digits = "".join(ch for ch in symbol if ch.isdigit())
        if not digits:
            raise ValueError(f"invalid HK symbol: {raw_symbol}")
        return f"{int(digits):04d}.HK"
    return symbol.replace(".", "-")


def parse_latest_yahoo(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload)
    result = ((data.get("chart") or {}).get("result") or [None])[0]
    if not result:
        raise ValueError("empty Yahoo chart result")
    timestamps = result.get("timestamp") or []
    quote = (((result.get("indicators") or {}).get("quote") or [{}])[0])
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []
    for idx in range(min(len(timestamps), len(closes)) - 1, -1, -1):
        close = closes[idx]
        if close is None or float(close) <= 0:
            continue
        ts = int(timestamps[idx])
        return {
            "trade_date": datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat(),
            "close": round(float(close), 8),
            "volume": int(volumes[idx] or 0) if idx < len(volumes) else 0,
            "currency": str((result.get("meta") or {}).get("currency") or ""),
        }
    raise ValueError("no positive close in Yahoo payload")


def fetch_dual_route_market(market: str, symbol: str, as_of: date, fetcher: Fetcher) -> dict[str, Any]:
    vendor_symbol = yahoo_symbol(market, symbol)
    period2 = int(datetime.combine(as_of + timedelta(days=2), datetime.min.time(), tzinfo=timezone.utc).timestamp())
    period1 = int(datetime.combine(as_of - timedelta(days=14), datetime.min.time(), tzinfo=timezone.utc).timestamp())
    template = "https://query{route}.finance.yahoo.com/v8/finance/chart/{symbol}?period1={p1}&period2={p2}&interval=1d&events=div%2Csplits"
    payloads: list[bytes] = []
    parsed: list[dict[str, Any]] = []
    for route in (1, 2):
        raw = fetcher(template.format(route=route, symbol=vendor_symbol, p1=period1, p2=period2), {"User-Agent": "Mozilla/5.0"})
        payloads.append(raw)
        parsed.append(parse_latest_yahoo(raw))
    left, right = parsed
    if left["trade_date"] != right["trade_date"] or abs(left["close"] - right["close"]) > max(1e-8, left["close"] * 1e-8):
        raise ValueError("dual Yahoo routes diverged")
    trade_date = date.fromisoformat(left["trade_date"])
    if trade_date > as_of:
        raise ValueError("future market observation")
    if trade_date != as_of:
        raise ValueError(f"SESSION_NOT_COMPLETED_FOR_AS_OF:expected={as_of.isoformat()},observed={trade_date.isoformat()}")
    return {
        "market": market,
        "symbol": symbol,
        "vendor_symbol": vendor_symbol,
        **left,
        "route_1_sha256": sha256_bytes(payloads[0]),
        "route_2_sha256": sha256_bytes(payloads[1]),
        "route_reconciliation": "PASS_DUAL_ROUTE",
        "data_grade": "UNOFFICIAL_FREE_VENDOR_RESEARCH_ONLY" if market == "HK" else "NON_DECISION_GRADE_FALLBACK",
        "decision_grade": False,
    }


def sec_cik(row: dict[str, Any]) -> str:
    raw = first_value(row, ("cik", "cik10", "cik_str", "issuer_cik", "sec_cik", "sec_cik10", "CIK"))
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits.zfill(10) if digits else ""


def sec_symbol(row: dict[str, Any]) -> str:
    return first_value(row, ("symbol", "ticker", "selected_symbol", "primary_symbol", "primary_ticker", "listing_symbol", "security_symbol")).upper()


def market_symbol(row: dict[str, Any]) -> str:
    direct = sec_symbol(row)
    if direct:
        return direct
    values = row.get("symbols")
    if isinstance(values, str):
        values = [values]
    if isinstance(values, list):
        for item in values:
            if isinstance(item, str) and item.strip():
                return item.strip().upper()
            if isinstance(item, dict):
                value = first_value(item, ("symbol", "ticker", "selected_symbol", "primary_symbol"))
                if value:
                    return value.upper()
    return ""


def identity_preference(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        0 if str(row.get("row_disposition") or "") == "INCLUDED" else 1,
        0 if not bool(row.get("test_issue")) else 1,
        0 if str(row.get("listing_lifecycle_status") or "") == "ACTIVE_LISTED_OBSERVED" else 1,
        0 if str(row.get("instrument_type") or "") == "COMMON_EQUITY" else 1,
        str(row.get("venue") or ""),
        sec_symbol(row),
        first_value(row, ("canonical_security_id", "security_id")),
    )


def build_identity_maps(rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    issuer_candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    symbol_candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        issuer_id = first_value(row, ("canonical_issuer_id", "issuer_id"))
        symbol = sec_symbol(row)
        if issuer_id and symbol:
            issuer_candidates[issuer_id].append(row)
        if symbol:
            symbol_candidates[symbol].append(row)
    issuer_map = {key: min(values, key=identity_preference) for key, values in issuer_candidates.items()}
    symbol_map = {key: min(values, key=identity_preference) for key, values in symbol_candidates.items()}
    return issuer_map, symbol_map


def fetch_sec_metadata(row: dict[str, Any], fetcher: Fetcher) -> dict[str, Any]:
    cik = sec_cik(row)
    symbol = sec_symbol(row)
    if not cik:
        return {"symbol": symbol, "cik": "", "status": "CIK_UNAVAILABLE", "data_grade": "OFFICIAL_SEC_RESEARCH_EVIDENCE"}
    headers = {"User-Agent": os.getenv("SEC_USER_AGENT", "investment-os-market-data/1.0 contact:ljjx2020@gmail.com")}
    submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    companyfacts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    submissions = fetcher(submissions_url, headers)
    companyfacts = fetcher(companyfacts_url, headers)
    sub = json.loads(submissions)
    recent = (((sub.get("filings") or {}).get("recent") or {}))
    forms = recent.get("form") or []
    dates = recent.get("filingDate") or []
    latest_form = str(forms[0]) if forms else ""
    latest_date = str(dates[0]) if dates else ""
    facts = json.loads(companyfacts)
    return {
        "symbol": symbol,
        "cik": cik,
        "status": "PASS_OFFICIAL_SEC_REFRESH",
        "latest_filing_form": latest_form,
        "latest_filing_date": latest_date,
        "companyfacts_taxonomy_count": len(facts.get("facts") or {}),
        "submissions_sha256": sha256_bytes(submissions),
        "companyfacts_sha256": sha256_bytes(companyfacts),
        "data_grade": "OFFICIAL_SEC_RESEARCH_EVIDENCE",
        "decision_grade": False,
    }


def circular_slice(rows: list[dict[str, Any]], size: int, offset: int) -> list[dict[str, Any]]:
    if not rows or size <= 0:
        return []
    if len(rows) <= size:
        return list(rows)
    start = offset % len(rows)
    return [rows[(start + idx) % len(rows)] for idx in range(size)]


def plan_batches(root: Path, policy: dict[str, Any], as_of: date) -> dict[str, Any]:
    bucket = as_of.weekday()
    if bucket not in range(5):
        raise ValueError("Round 3 runs only for Monday-Friday market dates")
    hk_rows = read_csv(root / HK_UNIVERSE)
    hk_selected = [row for row in hk_rows if stable_bucket(first_value(row, ("canonical_security_id", "stock_code")), 5) == bucket]

    initial_payload = read_json(root / US_MARKET_INITIAL)
    initial_market_rows = initial_payload.get("securities", []) if isinstance(initial_payload, dict) else initial_payload
    market_sources = list(initial_market_rows) + read_jsonl_gz(root / US_MARKET_QUEUE)
    market_pool: dict[str, dict[str, Any]] = {}
    for row in market_sources:
        symbol = market_symbol(row)
        security_id = first_value(row, ("canonical_security_id", "security_id", "security_key")) or symbol
        if symbol and security_id:
            market_pool[security_id] = {**row, "symbol": symbol, "_security_key": security_id}
    normalized_us = list(market_pool.values())
    bucket_rows = sorted((row for row in normalized_us if stable_bucket(row["_security_key"], 5) == bucket), key=lambda row: row["_security_key"])
    iso_year, iso_week, _ = as_of.isocalendar()
    week_index = iso_year * 53 + iso_week
    us_size = int(policy["united_states"]["daily_rotation_batch_size"])
    us_selected = circular_slice(bucket_rows, us_size, week_index * us_size)

    identity_rows = read_jsonl_gz(root / US_IDENTITY_LINEAGE)
    identity_by_issuer, identity_by_symbol = build_identity_maps(identity_rows)
    sec_sources = read_csv(root / US_SEC_INITIAL) + read_jsonl_gz(root / US_SEC_QUEUE)
    sec_pool: dict[str, dict[str, Any]] = {}
    for row in sec_sources:
        source_issuer_id = first_value(row, ("canonical_issuer_id", "issuer_id"))
        source_symbol = sec_symbol(row)
        identity = identity_by_issuer.get(source_issuer_id) or identity_by_symbol.get(source_symbol) or {}
        enriched = {**identity, **row}
        issuer_id = source_issuer_id or first_value(enriched, ("canonical_issuer_id", "issuer_id"))
        symbol = sec_symbol(enriched)
        cik = sec_cik(enriched)
        key = issuer_id or cik or symbol
        if key and symbol:
            sec_pool[key] = {**enriched, "canonical_issuer_id": issuer_id, "symbol": symbol, "cik": cik, "_issuer_key": key}
    normalized_sec = list(sec_pool.values())
    sec_bucket = sorted((row for row in normalized_sec if stable_bucket(row["_issuer_key"], 5) == bucket), key=lambda row: row["_issuer_key"])
    sec_size = int(policy["united_states"]["daily_sec_batch_size"])
    sec_selected = circular_slice(sec_bucket, sec_size, week_index * sec_size)

    benchmark_payload = read_json(root / US_BENCHMARK)
    benchmark = benchmark_payload.get("members", [])
    return {
        "bucket": bucket,
        "hk_universe_count": len(hk_rows),
        "hk_selected": hk_selected,
        "us_rotation_pool_count": len(normalized_us),
        "us_selected": us_selected,
        "us_sec_pool_count": len(normalized_sec),
        "us_sec_selected": sec_selected,
        "us_benchmark": benchmark,
    }


def build_sec_retrieval_queue(rows: list[dict[str, Any]], as_of: date) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for row in rows:
        symbol = sec_symbol(row)
        cik = sec_cik(row)
        issuer_id = first_value(row, ("canonical_issuer_id", "issuer_id"))
        cik_status = "RESOLVED_FROM_ACCEPTED_EVIDENCE" if cik else "PENDING_OFFICIAL_SEC_TICKER_MAP_RESOLUTION"
        required_sources = ["SEC_SUBMISSIONS", "SEC_COMPANYFACTS"] if cik else ["SEC_COMPANY_TICKERS", "SEC_SUBMISSIONS", "SEC_COMPANYFACTS"]
        queue.append({
            "symbol": symbol,
            "cik": cik,
            "canonical_issuer_id": issuer_id,
            "as_of_date": as_of.isoformat(),
            "status": "PENDING_CHATGPT_WEB_OFFICIAL_RETRIEVAL",
            "cik_resolution_status": cik_status,
            "official_resolution_route": "CIK_DIRECT" if cik else "SYMBOL_TO_SEC_OFFICIAL_TICKER_MAP_TO_CIK",
            "required_sources": required_sources,
            "data_grade_required": "OFFICIAL_SEC_RESEARCH_EVIDENCE",
            "candidate_pool_mutation_authorized": False,
            "trade_authority": "NONE",
        })
    queue.sort(key=lambda row: (row["symbol"], row["cik"], row["canonical_issuer_id"]))
    return queue

def execute_market_rows(
    market: str,
    symbols: list[str],
    as_of: date,
    fetcher: Fetcher,
    max_workers: int = 12,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    successes: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(symbols) or 1))) as executor:
        futures = {executor.submit(fetch_dual_route_market, market, symbol, as_of, fetcher): symbol for symbol in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                successes.append(future.result())
            except Exception as exc:
                failures.append({"market": market, "symbol": symbol, "status": "DATA_GAP", "reason": str(exc)[:300]})
    successes.sort(key=lambda row: row["symbol"])
    failures.sort(key=lambda row: row["symbol"])
    return successes, failures


def execute_sec_rows(rows: list[dict[str, Any]], fetcher: Fetcher, max_workers: int = 2) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(rows) or 1))) as executor:
        futures = {executor.submit(fetch_sec_metadata, row, fetcher): row for row in rows}
        for future in as_completed(futures):
            source = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({
                    "symbol": sec_symbol(source),
                    "cik": sec_cik(source),
                    "status": "SEC_DATA_GAP",
                    "reason": str(exc)[:300],
                    "data_grade": "OFFICIAL_SEC_RESEARCH_EVIDENCE",
                })
    results.sort(key=lambda row: (str(row.get("symbol") or ""), str(row.get("cik") or "")))
    return results


def load_ledger(path: Path) -> dict[str, Any]:
    if path.exists():
        return read_json(path)
    return {
        "schema_version": "1.0.0",
        "policy_id": "ROUND3_HK_US_LIMITED_PRODUCTION_V1",
        "weekly_cycles": {},
        "daily_runs": [],
        "completed_weekly_cycle_count": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }


def update_cycle(ledger: dict[str, Any], as_of: date, bucket: int, hk_ok: list[dict[str, Any]], hk_fail: list[dict[str, Any]], us_ok: list[dict[str, Any]], us_fail: list[dict[str, Any]], sec_rows: list[dict[str, Any]], benchmark_symbols: list[str], policy: dict[str, Any]) -> dict[str, Any]:
    iso_year, iso_week, _ = as_of.isocalendar()
    cycle_id = f"{iso_year}-W{iso_week:02d}"
    cycle = ledger.setdefault("weekly_cycles", {}).setdefault(cycle_id, {
        "cycle_id": cycle_id,
        "hk_buckets": [],
        "us_buckets": [],
        "hk_attempted": 0,
        "hk_success": 0,
        "us_rotation_attempted": 0,
        "us_rotation_success": 0,
        "us_benchmark_success_symbols": [],
        "sec_queued": 0,
        "sec_official_completed_issuer_count": 0,
        "sec_official_retrieval_status": "PENDING_CHATGPT_WEB_OFFICIAL_RETRIEVAL",
        "observations": {"HK": {}, "US": {}, "SEC": {}},
        "market_rotation_completed": False,
        "completed": False,
    })
    hk_session_observed = bool(hk_ok)
    us_session_observed = bool(us_ok)
    if bucket not in cycle["hk_buckets"] and hk_session_observed:
        cycle["hk_buckets"].append(bucket)
        cycle["hk_attempted"] += len(hk_ok) + len(hk_fail)
        cycle["hk_success"] += len(hk_ok)
    new_us_bucket = bucket not in cycle["us_buckets"]
    if new_us_bucket and us_session_observed:
        cycle["us_buckets"].append(bucket)
        rotation = [row for row in us_ok if row["symbol"] not in benchmark_symbols]
        rotation_fail = [row for row in us_fail if row["symbol"] not in benchmark_symbols]
        cycle["us_rotation_attempted"] += len(rotation) + len(rotation_fail)
        cycle["us_rotation_success"] += len(rotation)
        cycle["sec_queued"] += len(sec_rows)
    for row in hk_ok:
        cycle["observations"]["HK"][row["symbol"]] = row
    for row in us_ok:
        cycle["observations"]["US"][row["symbol"]] = row
        if row["symbol"] in benchmark_symbols and row["symbol"] not in cycle["us_benchmark_success_symbols"]:
            cycle["us_benchmark_success_symbols"].append(row["symbol"])
    for row in sec_rows:
        cycle["observations"]["SEC"][row.get("symbol") or row.get("cik") or row.get("canonical_issuer_id") or "UNKNOWN"] = row
    hk_ratio = cycle["hk_success"] / cycle["hk_attempted"] if cycle["hk_attempted"] else 0.0
    us_ratio = cycle["us_rotation_success"] / cycle["us_rotation_attempted"] if cycle["us_rotation_attempted"] else 0.0
    cycle["hk_success_ratio"] = round(hk_ratio, 6)
    cycle["us_rotation_success_ratio"] = round(us_ratio, 6)
    cycle["market_rotation_completed"] = (
        sorted(cycle["hk_buckets"]) == [0, 1, 2, 3, 4]
        and sorted(cycle["us_buckets"]) == [0, 1, 2, 3, 4]
        and cycle["hk_attempted"] >= int(policy["hong_kong"]["minimum_weekly_attempted_count"])
        and hk_ratio >= float(policy["hong_kong"]["minimum_weekly_success_ratio"])
        and cycle["us_rotation_attempted"] >= int(policy["united_states"]["minimum_weekly_rotation_attempted_count"])
        and us_ratio >= float(policy["united_states"]["minimum_weekly_rotation_success_ratio"])
        and len(cycle["us_benchmark_success_symbols"]) >= int(policy["united_states"]["minimum_weekly_benchmark_success_count"])
        and cycle["sec_queued"] >= int(policy["united_states"]["minimum_weekly_sec_queued_count"])
    )
    cycle["completed"] = (
        cycle["market_rotation_completed"]
        and cycle.get("sec_official_completed_issuer_count", 0) >= int(policy["united_states"]["minimum_weekly_official_sec_completed_count"])
    )
    ledger["completed_weekly_cycle_count"] = sum(bool(item.get("completed")) for item in ledger["weekly_cycles"].values())
    ledger["market_rotation_completed_weekly_cycle_count"] = sum(bool(item.get("market_rotation_completed")) for item in ledger["weekly_cycles"].values())
    return cycle

def parse_rank(row: dict[str, str]) -> int:
    raw = first_value(row, ("overall_rank", "rank", "research_rank", "longlist_rank"))
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return 999999


def hk_longlist_map(root: Path) -> dict[str, dict[str, str]]:
    if not (root / HK_LONGLIST).exists():
        return {}
    result = {}
    for row in read_csv(root / HK_LONGLIST):
        key = first_value(row, ("canonical_security_id", "security_id", "stock_code", "symbol"))
        if key:
            result[key] = row
            digits = "".join(ch for ch in key if ch.isdigit())
            if digits:
                result[digits.zfill(5)] = row
    return result


def duplication_ids(root: Path) -> set[str]:
    if not (root / HK_DUPLICATION).exists():
        return set()
    values: set[str] = set()
    for row in read_csv(root / HK_DUPLICATION):
        for key in ("hk_security_id", "canonical_security_id", "hk_stock_code", "stock_code"):
            value = row.get(key)
            if value:
                values.add(str(value))
                digits = "".join(ch for ch in str(value) if ch.isdigit())
                if digits:
                    values.add(digits.zfill(5))
    return values


def build_proposal(root: Path, cycle: dict[str, Any], benchmark: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    hk_map = hk_longlist_map(root)
    dup = duplication_ids(root)
    hk_rows = []
    for symbol, observation in cycle["observations"]["HK"].items():
        digits = "".join(ch for ch in symbol if ch.isdigit()).zfill(5)
        source = hk_map.get(f"HKEX:{digits}") or hk_map.get(digits)
        if not source:
            continue
        rank = parse_rank(source)
        label = "DUPLICATION_REVIEW" if (f"HKEX:{digits}" in dup or digits in dup) else "RESEARCH_PRIORITY"
        hk_rows.append({
            "market": "HK",
            "security_id": f"HKEX:{digits}",
            "symbol": digits,
            "name": first_value(source, ("name_cn", "security_name", "name")),
            "label": label,
            "source_longlist_rank": rank,
            "latest_trade_date": observation["trade_date"],
            "latest_close": observation["close"],
            "data_grade": observation["data_grade"],
            "candidate_pool_mutation_authorized": False,
        })
    hk_rows.sort(key=lambda row: (row["source_longlist_rank"], row["security_id"]))
    hk_rows = hk_rows[: int(policy["research"]["maximum_hk_weekly_research_proposals"])]

    benchmark_by_symbol = {str(row.get("symbol")): row for row in benchmark}
    us_rows = []
    for symbol, observation in cycle["observations"]["US"].items():
        member = benchmark_by_symbol.get(symbol)
        if not member:
            continue
        layer = str(member.get("pool_layer") or "")
        if layer == "CORE_FINANCIAL_QUALITY_SANDBOX":
            label = "RESEARCH_PRIORITY"
        elif layer == "OFFICIAL_FILING_CLASSIFICATION_WATCH":
            label = "OFFICIAL_FILING_REFRESH_PRIORITY"
        else:
            label = "MARKET_RISK_SANDBOX_OBSERVATION"
        sec = cycle["observations"]["SEC"].get(symbol)
        us_rows.append({
            "market": "US",
            "security_id": member.get("canonical_security_id"),
            "symbol": symbol,
            "label": label,
            "benchmark_pool_layer": layer,
            "latest_trade_date": observation["trade_date"],
            "latest_close": observation["close"],
            "market_data_grade": observation["data_grade"],
            "official_sec_refresh_status": (sec or {}).get("status", "NOT_IN_CURRENT_SEC_BATCH"),
            "candidate_pool_mutation_authorized": False,
        })
    us_rows.sort(key=lambda row: row["symbol"])
    us_rows = us_rows[: int(policy["research"]["maximum_us_weekly_research_proposals"])]
    return {
        "schema_version": "1.0.0",
        "policy_id": policy["policy_id"],
        "cycle_id": cycle["cycle_id"],
        "cycle_completed": bool(cycle["completed"]),
        "market_rotation_completed": bool(cycle["market_rotation_completed"]),
        "sec_official_retrieval_status": cycle.get("sec_official_retrieval_status", "PENDING_CHATGPT_WEB_OFFICIAL_RETRIEVAL"),
        "status": (
            "WEEKLY_RESEARCH_REVIEW_READY" if cycle["completed"]
            else "WEEKLY_RESEARCH_REVIEW_READY_SEC_ENRICHMENT_PENDING" if cycle["market_rotation_completed"]
            else "DAILY_BATCH_CAPTURED_NO_WEEKLY_PROPOSAL_YET"
        ),
        "hong_kong": hk_rows if cycle["market_rotation_completed"] else [],
        "united_states": us_rows if cycle["market_rotation_completed"] else [],
        "scope_boundaries": {
            "hong_kong_scope": "SOUTHBOUND_STOCK_CONNECT_ONLY",
            "full_hkex_market_claimed": False,
            "united_states_scope": "BOUNDED_ROTATION_NOT_FULL_MARKET_WEEKLY_COVERAGE",
            "full_us_market_history_claimed": False,
            "formal_cross_section_rank_claimed": False,
        },
        "controls": {
            "candidate_pool_mutations": 0,
            "simulation_mutations": 0,
            "real_account_mutations": 0,
            "decision_mutations": 0,
            "orders": 0,
            "trade_authority": "NONE",
        },
    }


def run(root: Path, policy_path: Path, as_of: date, fetcher: Fetcher = default_fetcher, sleep_seconds: float = 0.05) -> dict[str, Any]:
    policy = read_json(root / policy_path)
    ledger = load_ledger(root / LEDGER_PATH)
    prior = next((item for item in ledger.get("daily_runs", []) if item.get("as_of_date") == as_of.isoformat()), None)
    if prior:
        cycle = ledger.get("weekly_cycles", {}).get(prior["cycle_id"], {})
        return {
            "due": False,
            "run_id": prior["run_id"],
            "status": "NOOP_ALREADY_CAPTURED",
            "operating_state": prior["operating_state"],
            "cycle_id": prior["cycle_id"],
            "cycle_completed": bool(cycle.get("completed")),
            "market_rotation_completed": bool(cycle.get("market_rotation_completed")),
            "orders": 0,
            "trade_authority": "NONE",
        }
    plan = plan_batches(root, policy, as_of)
    hk_symbols = [first_value(row, ("stock_code", "canonical_security_id")) for row in plan["hk_selected"]]
    benchmark_symbols = [str(row.get("symbol")) for row in plan["us_benchmark"]]
    rotation_symbols = [row["symbol"] for row in plan["us_selected"] if row["symbol"] not in benchmark_symbols]
    us_symbols = list(dict.fromkeys(benchmark_symbols + rotation_symbols))

    hk_ok, hk_fail = execute_market_rows("HK", hk_symbols, as_of, fetcher, max_workers=12)
    if sleep_seconds:
        time.sleep(sleep_seconds)
    us_ok, us_fail = execute_market_rows("US", us_symbols, as_of, fetcher, max_workers=10)
    sec_rows = build_sec_retrieval_queue(plan["us_sec_selected"], as_of)

    cycle = update_cycle(ledger, as_of, plan["bucket"], hk_ok, hk_fail, us_ok, us_fail, sec_rows, benchmark_symbols, policy)
    run_id = f"ROUND3_{as_of.isoformat()}_B{plan['bucket']}_{hashlib.sha256((as_of.isoformat()+str(plan['bucket'])).encode()).hexdigest()[:10]}"
    proposal = build_proposal(root, cycle, plan["us_benchmark"], policy)
    hk_bucket_captured = plan["bucket"] in cycle["hk_buckets"]
    us_bucket_captured = plan["bucket"] in cycle["us_buckets"]
    capture_complete = hk_bucket_captured and us_bucket_captured
    capture_status = "CAPTURED_BOTH_MARKETS" if capture_complete else "PARTIAL_RETRYABLE_MISSING_COMPLETED_SESSION"
    acceptance_required = int(policy["acceptance"]["completed_weekly_cycles_for_limited_production_acceptance"])
    operating_state = "ROUND3_LIMITED_PRODUCTION_ACCEPTED" if ledger["completed_weekly_cycle_count"] >= acceptance_required else "ROUND3_OPERATING_OBSERVATION"
    run_record = {
        "run_id": run_id,
        "as_of_date": as_of.isoformat(),
        "bucket": plan["bucket"],
        "capture_status": capture_status,
        "hong_kong_completed_session_captured": hk_bucket_captured,
        "united_states_completed_session_captured": us_bucket_captured,
        "operating_state": operating_state,
        "completed_weekly_cycle_count": ledger["completed_weekly_cycle_count"],
        "market_rotation_completed_weekly_cycle_count": ledger.get("market_rotation_completed_weekly_cycle_count", 0),
        "hong_kong": {"scope": "SOUTHBOUND_STOCK_CONNECT_ONLY", "universe_count": plan["hk_universe_count"], "attempted": len(hk_ok) + len(hk_fail), "success": len(hk_ok), "failures": len(hk_fail), "full_hkex_market_claimed": False},
        "united_states": {
            "scope": "BOUNDED_ROTATION",
            "security_master_reference_count": policy["united_states"]["expected_security_master_count"],
            "rotation_pool_count": plan["us_rotation_pool_count"],
            "rotation_attempted": len(rotation_symbols),
            "market_success": len(us_ok),
            "market_failures": len(us_fail),
            "benchmark_attempted": len(benchmark_symbols),
            "issuer_reference_count": policy["united_states"]["expected_issuer_count"],
            "sec_pool_count": plan["us_sec_pool_count"],
            "sec_queued": len(sec_rows),
            "sec_execution_mode": policy["united_states"]["sec_execution_mode"],
            "sec_official_success_claimed": False,
            "full_universe_market_history_claimed": False,
        },
        "controls": policy["authority"],
        "canonical_authority": "MERGE_OF_GOVERNED_PR_ONLY",
    }
    if capture_complete:
        ledger["daily_runs"].append({"run_id": run_id, "as_of_date": as_of.isoformat(), "bucket": plan["bucket"], "cycle_id": cycle["cycle_id"], "operating_state": operating_state, "capture_status": capture_status})
        ledger["daily_runs"] = ledger["daily_runs"][-60:]
    ledger["orders"] = 0
    ledger["trade_authority"] = "NONE"

    write_json(root / LEDGER_PATH, ledger)
    write_json(root / RUN_PATH, run_record)
    write_json(root / PROPOSAL_PATH, proposal)
    evidence_dir = root / EVIDENCE_ROOT / run_id
    write_json(evidence_dir / "ROUND3_SEC_OFFICIAL_RETRIEVAL_QUEUE.json", {"run_id": run_id, "as_of_date": as_of.isoformat(), "execution_environment_required": "CHATGPT_WEB_CONTROLLED_OFFICIAL_RETRIEVAL", "queue": sec_rows, "orders": 0, "trade_authority": "NONE"})
    write_json(evidence_dir / "ROUND3_RUN_EVIDENCE.json", {"run": run_record, "hk_market_successes": hk_ok, "hk_market_failures": hk_fail, "us_market_successes": us_ok, "us_market_failures": us_fail, "us_sec_retrieval_queue": sec_rows})
    manifest = {
        "run_id": run_id,
        "policy_sha256": sha256_file(root / policy_path),
        "input_sha256": {
            str(HK_UNIVERSE): sha256_file(root / HK_UNIVERSE),
            str(US_BENCHMARK): sha256_file(root / US_BENCHMARK),
            str(US_MARKET_INITIAL): sha256_file(root / US_MARKET_INITIAL),
            str(US_MARKET_QUEUE): sha256_file(root / US_MARKET_QUEUE),
            str(US_SEC_INITIAL): sha256_file(root / US_SEC_INITIAL),
            str(US_SEC_QUEUE): sha256_file(root / US_SEC_QUEUE),
            str(US_IDENTITY_LINEAGE): sha256_file(root / US_IDENTITY_LINEAGE),
        },
        "output_sha256": {
            str(LEDGER_PATH): sha256_file(root / LEDGER_PATH),
            str(RUN_PATH): sha256_file(root / RUN_PATH),
            str(PROPOSAL_PATH): sha256_file(root / PROPOSAL_PATH),
            str(evidence_dir / "ROUND3_SEC_OFFICIAL_RETRIEVAL_QUEUE.json"): sha256_file(evidence_dir / "ROUND3_SEC_OFFICIAL_RETRIEVAL_QUEUE.json"),
        },
        "orders": 0,
        "trade_authority": "NONE",
    }
    write_json(evidence_dir / "ROUND3_MANIFEST.json", manifest)
    return {"due": True, "run_id": run_id, "status": proposal["status"], "capture_status": capture_status, "operating_state": operating_state, "cycle_id": cycle["cycle_id"], "cycle_completed": cycle["completed"], "market_rotation_completed": cycle["market_rotation_completed"], "hk_success": len(hk_ok), "us_success": len(us_ok), "sec_queued": len(sec_rows), "orders": 0, "trade_authority": "NONE"}

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="automation/cross_market/round3_policy.json")
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()
    result = run(Path(args.repo_root), Path(args.policy), date.fromisoformat(args.as_of))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
