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

import sys

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from automation.cross_market.apply_round3_sec_observer_results import validate_inbox
from automation.cross_market.build_round3_limited_production import read_json, write_json

RETRIEVAL_ENVIRONMENT = "CONTROLLED_LOCAL_OR_SELF_HOSTED_OFFICIAL_RETRIEVAL"
TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
TICKER_EXCHANGE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SPECIAL_CIK_EVIDENCE = {
    "BAIG": {"cik": "0001976322", "url": "https://www.sec.gov/Archives/edgar/data/1976322/000089418926007231/leverageshares2xlongbbaida.htm", "issuer_name": "Leverage Shares 2X Long BBAI Daily ETF", "security_type": "ETF_SERIES"},
    "XE": {"cik": "0002088896", "url": "https://www.sec.gov/Archives/edgar/data/2088896/000119312526347752/R1.htm", "issuer_name": "X-Energy, Inc.", "security_type": "OPERATING_COMPANY"},
}
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
    if url == TICKER_EXCHANGE_URL:
        return "SEC_COMPANY_TICKERS_EXCHANGE.json"
    if "/submissions/CIK" in url:
        return f"SEC_SUBMISSIONS_{url.rsplit('/', 1)[-1]}"
    if "/companyfacts/CIK" in url:
        return f"SEC_COMPANYFACTS_{url.rsplit('/', 1)[-1]}"
    return hashlib.sha256(url.encode("utf-8")).hexdigest() + ".bin"


def ticker_records(payload: bytes) -> dict[str, dict[str, Any]]:
    """Parse both SEC company_tickers.json and company_tickers_exchange.json."""
    data = json.loads(payload)
    rows: list[dict[str, Any]] = []
    if isinstance(data, dict) and isinstance(data.get("data"), list) and isinstance(data.get("fields"), list):
        fields = [str(value).strip().lower() for value in data["fields"]]
        indexes = {name: index for index, name in enumerate(fields)}
        for raw in data["data"]:
            if not isinstance(raw, list):
                continue
            rows.append({
                "ticker": raw[indexes["ticker"]] if "ticker" in indexes and indexes["ticker"] < len(raw) else "",
                "cik_str": raw[indexes["cik"]] if "cik" in indexes and indexes["cik"] < len(raw) else "",
                "title": raw[indexes["name"]] if "name" in indexes and indexes["name"] < len(raw) else "",
                "exchange": raw[indexes["exchange"]] if "exchange" in indexes and indexes["exchange"] < len(raw) else "",
            })
    else:
        source_rows = data.values() if isinstance(data, dict) else data
        rows = [row for row in source_rows if isinstance(row, dict)]
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        symbol = str(row.get("ticker") or "").strip().upper()
        digits = "".join(ch for ch in str(row.get("cik_str") or "") if ch.isdigit())
        if symbol and digits:
            grouped.setdefault(symbol, []).append({
                "cik": digits.zfill(10),
                "issuer_name": str(row.get("title") or row.get("name") or "").strip(),
                "exchange": str(row.get("exchange") or "").strip(),
            })
    result: dict[str, dict[str, Any]] = {}
    for symbol, matches in grouped.items():
        ciks = sorted({item["cik"] for item in matches})
        if len(ciks) != 1:
            result[symbol] = {"ambiguous": True, "candidate_ciks": ciks}
            continue
        names = sorted({item["issuer_name"] for item in matches if item["issuer_name"]})
        exchanges = sorted({item["exchange"] for item in matches if item["exchange"]})
        result[symbol] = {"cik": ciks[0], "issuer_name": names[0] if names else "", "exchange": exchanges[0] if len(exchanges) == 1 else "", "ambiguous": False}
    return result


def ticker_map(payload: bytes) -> dict[str, str]:
    """Compatibility helper returning only unique ticker-to-CIK mappings."""
    return {symbol: row["cik"] for symbol, row in ticker_records(payload).items() if row.get("cik") and not row.get("ambiguous")}


def security_type_from_name(name: str) -> str:
    normalized = str(name or "").upper()
    if "ETF" in normalized or "EXCHANGE TRADED FUND" in normalized:
        return "ETF"
    if "FUND" in normalized or "TRUST" in normalized:
        return "FUND"
    return "OPERATING_COMPANY"


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
    exchange_raw: bytes | None = None
    symbol_records: dict[str, dict[str, Any]] = {}
    ambiguous_symbols: set[str] = set()
    ticker_map_errors: list[str] = []
    ticker_source_by_symbol: dict[str, list[str]] = {}
    if needs_ticker_map:
        for ticker_url in (TICKER_URL, TICKER_EXCHANGE_URL):
            try:
                raw = fetch_and_record(ticker_url, headers, fetcher, raw_dir, raw_manifest)
                if ticker_url == TICKER_URL:
                    ticker_raw = raw
                else:
                    exchange_raw = raw
                for symbol, record in ticker_records(raw).items():
                    if record.get("ambiguous"):
                        ambiguous_symbols.add(symbol)
                        symbol_records.pop(symbol, None)
                        continue
                    existing = symbol_records.get(symbol)
                    if existing and existing.get("cik") != record.get("cik"):
                        ambiguous_symbols.add(symbol)
                        symbol_records.pop(symbol, None)
                        continue
                    if symbol not in ambiguous_symbols:
                        symbol_records[symbol] = record
                        ticker_source_by_symbol.setdefault(symbol, []).append(ticker_url)
            except Exception as exc:  # noqa: BLE001
                ticker_map_errors.append(f"{ticker_url}:{type(exc).__name__}:{exc}"[:500])
        raw_manifest["ticker_map_status"] = "PASS" if symbol_records else "SEC_DATA_GAP"
        raw_manifest["ticker_map_sources_attempted"] = [TICKER_URL, TICKER_EXCHANGE_URL]
        raw_manifest["ticker_map_failure_reason"] = ticker_map_errors
    else:
        raw_manifest["ticker_map_status"] = "NOT_REQUIRED"

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
            issuer_name = str(queued.get("issuer_name") or "").strip()
            security_type = str(queued.get("security_type") or "OPERATING_COMPANY").strip().upper()
            if route == "SYMBOL_TO_SEC_OFFICIAL_TICKER_MAP_TO_CIK":
                if symbol in SPECIAL_CIK_EVIDENCE:
                    special = SPECIAL_CIK_EVIDENCE[symbol]
                    evidence_raw = fetch_and_record(special["url"], headers, fetcher, raw_dir, raw_manifest)
                    evidence_text = evidence_raw.decode("utf-8", errors="replace")
                    path_match = re.search(r"/edgar/data/(\d+)/", special["url"])
                    if symbol not in evidence_text or not path_match or path_match.group(1).zfill(10) != special["cik"]:
                        raise ValueError(f"SEC_SPECIAL_CIK_EVIDENCE_MISMATCH:{symbol}")
                    cik = special["cik"]
                    issuer_name = special["issuer_name"]
                    security_type = special["security_type"]
                    resolution_source = "SEC_OFFICIAL_FILING_CIK_MAP"
                    sources.append(special["url"])
                    hashes[special["url"]] = sha256_bytes(evidence_raw)
                else:
                    if symbol in ambiguous_symbols:
                        raise ValueError(f"SEC_TICKER_MAP_AMBIGUOUS:{symbol}")
                    record = symbol_records.get(symbol)
                    if not record:
                        if not symbol_records and ticker_map_errors:
                            raise ValueError(f"SEC_TICKER_MAP_UNAVAILABLE:{';'.join(ticker_map_errors)}")
                        raise ValueError(f"SEC_TICKER_MAP_CIK_NOT_FOUND:{symbol}")
                    cik = str(record["cik"])
                    issuer_name = str(record.get("issuer_name") or issuer_name)
                    security_type = security_type_from_name(issuer_name)
                    resolution_source = "SEC_COMPANY_TICKERS"
                    for source_url in ticker_source_by_symbol.get(symbol, []):
                        raw_source = ticker_raw if source_url == TICKER_URL else exchange_raw
                        if raw_source is not None:
                            sources.append(source_url)
                            hashes[source_url] = sha256_bytes(raw_source)
            elif route != "CIK_DIRECT":
                raise ValueError(f"UNSUPPORTED_CIK_RESOLUTION_ROUTE:{route}")
            if not CIK10.fullmatch(cik):
                raise ValueError(f"INVALID_CIK:{cik}")

            submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            submissions_raw = fetch_and_record(submissions_url, headers, fetcher, raw_dir, raw_manifest)
            sources.append(submissions_url)
            hashes[submissions_url] = sha256_bytes(submissions_raw)
            submissions = json.loads(submissions_raw)
            companyfacts: dict[str, Any] = {}
            if security_type not in {"ETF", "ETF_SERIES", "FUND"}:
                companyfacts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
                companyfacts_raw = fetch_and_record(companyfacts_url, headers, fetcher, raw_dir, raw_manifest)
                sources.append(companyfacts_url)
                hashes[companyfacts_url] = sha256_bytes(companyfacts_raw)
                companyfacts = json.loads(companyfacts_raw)
            recent = ((submissions.get("filings") or {}).get("recent") or {})
            forms = recent.get("form") or []
            filing_dates = recent.get("filingDate") or []
            issuers.append({
                "canonical_issuer_id": issuer_id,
                "symbol": symbol,
                "cik": cik,
                "cik_resolution_source": resolution_source,
                "issuer_name": issuer_name,
                "security_type": security_type,
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
