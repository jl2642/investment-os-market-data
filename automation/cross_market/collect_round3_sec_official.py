#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from automation.cross_market.apply_round3_sec_observer_results import validate_inbox
from automation.cross_market.build_round3_limited_production import read_json, write_json

RETRIEVAL_ENVIRONMENT = "CONTROLLED_LOCAL_OR_SELF_HOSTED_OFFICIAL_RETRIEVAL"
TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
CIK10 = re.compile(r"^[0-9]{10}$")
Fetcher = Callable[[str, dict[str, str]], bytes]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def default_fetcher(url: str, headers: dict[str, str]) -> bytes:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def safe_name(url: str) -> str:
    if url == TICKER_URL:
        return "SEC_COMPANY_TICKERS.json"
    if "/submissions/CIK" in url:
        return f"SEC_SUBMISSIONS_{url.rsplit('/', 1)[-1]}"
    if "/companyfacts/CIK" in url:
        return f"SEC_COMPANYFACTS_{url.rsplit('/', 1)[-1]}"
    return hashlib.sha256(url.encode("utf-8")).hexdigest() + ".bin"


def ticker_map(payload: bytes) -> dict[str, str]:
    data = json.loads(payload)
    result: dict[str, str] = {}
    rows = data.values() if isinstance(data, dict) else data
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("ticker") or "").strip().upper()
        digits = "".join(ch for ch in str(row.get("cik_str") or "") if ch.isdigit())
        if symbol and digits:
            result[symbol] = digits.zfill(10)
    return result


def fetch_and_record(
    url: str,
    headers: dict[str, str],
    fetcher: Fetcher,
    raw_dir: Path,
    raw_manifest: dict[str, Any],
) -> bytes:
    payload = fetcher(url, headers)
    if not isinstance(payload, (bytes, bytearray)) or not payload:
        raise ValueError(f"EMPTY_RAW_RESPONSE:{url}")
    raw = bytes(payload)
    digest = sha256_bytes(raw)
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / safe_name(url)
    path.write_bytes(raw)
    raw_manifest["responses"][url] = {
        "bytes": len(raw),
        "sha256": digest,
        "raw_file": path.name,
        "source_authority": "SEC_OFFICIAL",
    }
    return raw


def collect(
    queue_payload: dict[str, Any],
    *,
    raw_dir: Path,
    user_agent: str,
    fetcher: Fetcher = default_fetcher,
    retrieved_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not user_agent.strip():
        raise ValueError("SEC_USER_AGENT_REQUIRED")
    queue_rows = queue_payload.get("queue") or []
    if not isinstance(queue_rows, list) or not queue_rows:
        raise ValueError("ROUND3_SEC_QUEUE_EMPTY")
    headers = {
        "User-Agent": user_agent.strip(),
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    }
    raw_manifest: dict[str, Any] = {
        "schema_version": "1.0.0",
        "run_id": queue_payload.get("run_id"),
        "retrieval_environment": RETRIEVAL_ENVIRONMENT,
        "raw_file_scope": "RELATIVE_TO_RAW_DIR",
        "responses": {},
        "orders": 0,
        "trade_authority": "NONE",
    }
    needs_ticker_map = any(
        str(row.get("official_resolution_route") or "") == "SYMBOL_TO_SEC_OFFICIAL_TICKER_MAP_TO_CIK"
        for row in queue_rows
    )
    ticker_raw: bytes | None = None
    symbol_to_cik: dict[str, str] = {}
    if needs_ticker_map:
        ticker_raw = fetch_and_record(TICKER_URL, headers, fetcher, raw_dir, raw_manifest)
        symbol_to_cik = ticker_map(ticker_raw)

    issuers: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for queued in queue_rows:
        symbol = str(queued.get("symbol") or "").strip().upper()
        issuer_id = str(queued.get("canonical_issuer_id") or "").strip()
        route = str(queued.get("official_resolution_route") or "")
        try:
            cik = "".join(ch for ch in str(queued.get("cik") or "") if ch.isdigit()).zfill(10) if queued.get("cik") else ""
            resolution_source = "ACCEPTED_EVIDENCE"
            sources: list[str] = []
            hashes: dict[str, str] = {}
            if route == "SYMBOL_TO_SEC_OFFICIAL_TICKER_MAP_TO_CIK":
                cik = symbol_to_cik.get(symbol, "")
                resolution_source = "SEC_COMPANY_TICKERS"
                if not cik:
                    raise ValueError(f"SEC_TICKER_MAP_CIK_NOT_FOUND:{symbol}")
                if ticker_raw is None:
                    raise ValueError("SEC_TICKER_MAP_NOT_FETCHED")
                sources.append(TICKER_URL)
                hashes[TICKER_URL] = sha256_bytes(ticker_raw)
            elif route != "CIK_DIRECT":
                raise ValueError(f"UNSUPPORTED_CIK_RESOLUTION_ROUTE:{route}")
            if not CIK10.fullmatch(cik):
                raise ValueError(f"INVALID_CIK:{cik}")

            submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            companyfacts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
            submissions_raw = fetch_and_record(submissions_url, headers, fetcher, raw_dir, raw_manifest)
            companyfacts_raw = fetch_and_record(companyfacts_url, headers, fetcher, raw_dir, raw_manifest)
            sources.extend([submissions_url, companyfacts_url])
            hashes[submissions_url] = sha256_bytes(submissions_raw)
            hashes[companyfacts_url] = sha256_bytes(companyfacts_raw)

            submissions = json.loads(submissions_raw)
            companyfacts = json.loads(companyfacts_raw)
            recent = ((submissions.get("filings") or {}).get("recent") or {})
            forms = recent.get("form") or []
            filing_dates = recent.get("filingDate") or []
            issuers.append({
                "canonical_issuer_id": issuer_id,
                "symbol": symbol,
                "cik": cik,
                "cik_resolution_source": resolution_source,
                "latest_filing_form": str(forms[0]) if forms else "",
                "latest_filing_date": str(filing_dates[0]) if filing_dates else "",
                "companyfacts_taxonomy_count": len(companyfacts.get("facts") or {}),
                "official_sources": sources,
                "official_source_sha256": hashes,
                "status": "PASS_OFFICIAL_SEC_REFRESH",
                "decision_grade": False,
            })
        except Exception as exc:  # noqa: BLE001
            failures.append({
                "canonical_issuer_id": issuer_id,
                "symbol": symbol,
                "status": "SEC_DATA_GAP",
                "reason": f"{type(exc).__name__}:{exc}"[:500],
            })

    observed = retrieved_at or datetime.now(timezone.utc).isoformat()
    inbox = {
        "schema_version": "1.0.0",
        "run_id": queue_payload.get("run_id"),
        "as_of_date": queue_payload.get("as_of_date"),
        "retrieval_environment": RETRIEVAL_ENVIRONMENT,
        "retrieved_at": observed,
        "issuers": sorted(issuers, key=lambda row: (row["canonical_issuer_id"], row["symbol"])),
        "failures": sorted(failures, key=lambda row: (row["canonical_issuer_id"], row["symbol"])),
        "orders": 0,
        "trade_authority": "NONE",
    }
    validate_inbox(inbox, queue_payload)
    raw_manifest["retrieved_at"] = observed
    raw_manifest["official_success_count"] = len(issuers)
    raw_manifest["official_failure_count"] = len(failures)
    raw_manifest["raw_response_count"] = len(raw_manifest["responses"])
    return inbox, raw_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--raw-manifest")
    parser.add_argument("--user-agent", default=os.getenv("SEC_USER_AGENT", ""))
    args = parser.parse_args()

    queue_path = Path(args.queue)
    output_path = Path(args.output)
    raw_dir = Path(args.raw_dir)
    queue_payload = read_json(queue_path)
    inbox, manifest = collect(
        queue_payload,
        raw_dir=raw_dir,
        user_agent=args.user_agent,
    )
    write_json(output_path, inbox)
    manifest_path = Path(args.raw_manifest) if args.raw_manifest else output_path.with_name("ROUND3_SEC_RAW_RESPONSE_MANIFEST.json")
    write_json(manifest_path, manifest)
    print(json.dumps({
        "status": "ROUND3_SEC_CONTROLLED_COLLECTION_COMPLETE",
        "run_id": inbox["run_id"],
        "official_success_count": len(inbox["issuers"]),
        "official_failure_count": len(inbox["failures"]),
        "raw_response_count": manifest["raw_response_count"],
        "orders": 0,
        "trade_authority": "NONE",
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
