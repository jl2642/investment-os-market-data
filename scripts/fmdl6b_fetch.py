from __future__ import annotations

import csv
import io
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from fmdl6b_core import (
    PROGRAM_ID,
    classify_failure,
    load_json,
    make_session,
    sha256_bytes,
    sha256_file,
    utc_now,
    validate_contract,
    write_json,
)


def parse_sec_tickers(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8-sig"))
    fields = data.get("fields", [])
    rows = data.get("data", [])
    if len(rows) < 1000 or not fields:
        raise ValueError("insufficient SEC ticker rows")
    items = [dict(zip(fields, row)) for row in rows[:10000]]
    if not any(str(item.get("ticker", "")).upper() == "AAPL" for item in items):
        raise ValueError("AAPL missing")
    return {
        "sample_count": len(rows),
        "field_coverage": fields,
        "capabilities": ["CIK_TICKER_EXCHANGE_REFERENCE"],
        "point_in_time_support": "RETRIEVAL_SNAPSHOT_ONLY",
        "revision_support": "CURRENT_REFERENCE_ONLY",
    }


def parse_submissions(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8-sig"))
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    if not forms or not accessions:
        raise ValueError("submissions missing recent filings")
    return {
        "sample_count": len(forms),
        "field_coverage": sorted(recent),
        "capabilities": ["SUBMISSIONS_HISTORY", "ACCESSION_AND_ACCEPTANCE_METADATA"],
        "history_start": min(recent.get("filingDate", []), default=None),
        "history_end": max(recent.get("filingDate", []), default=None),
        "point_in_time_support": "FILING_AND_ACCEPTANCE_METADATA",
        "revision_support": "AMENDMENT_FORMS_VISIBLE",
    }


def parse_companyfacts(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8-sig"))
    facts = data.get("facts", {})
    concepts = sum(len(namespace) for namespace in facts.values() if isinstance(namespace, dict))
    if not facts or concepts < 10:
        raise ValueError("company facts insufficient")
    accessions: set[str] = set()
    forms: set[str] = set()
    units: set[str] = set()
    dates: list[str] = []
    for namespace in facts.values():
        for fact in namespace.values():
            for unit, rows in fact.get("units", {}).items():
                units.add(unit)
                for row in rows[:500]:
                    if row.get("accn"):
                        accessions.add(row["accn"])
                    if row.get("form"):
                        forms.add(row["form"])
                    if row.get("filed"):
                        dates.append(row["filed"])
    return {
        "sample_count": concepts,
        "field_coverage": sorted(facts),
        "capabilities": ["COMPANY_FACTS", "TAXONOMY_AND_UNITS", "ACCESSION_LINEAGE"],
        "history_start": min(dates, default=None),
        "history_end": max(dates, default=None),
        "point_in_time_support": "FILED_DATE_AND_ACCESSION",
        "revision_support": "MULTIPLE_ACCESSIONS_PRESERVABLE",
        "detail": {"unit_count": len(units), "form_count": len(forms), "accession_count": len(accessions)},
    }


def parse_nasdaq(payload: bytes) -> dict[str, Any]:
    text = payload.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text), delimiter="|"))
    if len(rows) < 100 or len(rows[0]) < 4:
        raise ValueError("Nasdaq directory insufficient")
    return {
        "sample_count": len(rows) - 2,
        "field_coverage": rows[0],
        "capabilities": ["LISTED_SYMBOL", "EXCHANGE_OR_VENUE", "INSTRUMENT_TYPE_FLAGS", "RETRIEVAL_TIMESTAMP"],
        "point_in_time_support": "CURRENT_RETRIEVAL_SNAPSHOT",
        "revision_support": "NO_HISTORICAL_REVISION_CHAIN",
    }


def parse_stooq(payload: bytes) -> dict[str, Any]:
    rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig", errors="replace"))))
    if len(rows) < 100:
        raise ValueError("Stooq history insufficient")
    required = {"Date", "Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(rows[0]):
        raise ValueError("Stooq fields missing")
    dates = [row["Date"] for row in rows if row.get("Date")]
    return {
        "sample_count": len(rows),
        "field_coverage": sorted(rows[0]),
        "capabilities": ["DAILY_OHLCV"],
        "history_start": min(dates),
        "history_end": max(dates),
        "point_in_time_support": "NOT_GUARANTEED_BY_FREE_ROUTE",
        "revision_support": "NOT_DOCUMENTED",
    }


def parse_yahoo(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8-sig"))
    results = data.get("chart", {}).get("result") or []
    if not results:
        raise ValueError("Yahoo chart missing result")
    result = results[0]
    timestamps = result.get("timestamp", [])
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    if len(timestamps) < 100 or not all(key in quote for key in ("open", "high", "low", "close", "volume")):
        raise ValueError("Yahoo OHLCV insufficient")
    events = result.get("events", {})
    event_count = sum(len(value) for value in events.values() if isinstance(value, dict))
    capabilities = ["DAILY_OHLCV"]
    if event_count > 0:
        capabilities.append("DIVIDEND_OR_SPLIT_EVENTS")
    return {
        "sample_count": len(timestamps),
        "field_coverage": sorted(quote),
        "capabilities": capabilities,
        "history_start": datetime.fromtimestamp(min(timestamps), timezone.utc).date().isoformat(),
        "history_end": datetime.fromtimestamp(max(timestamps), timezone.utc).date().isoformat(),
        "point_in_time_support": "NOT_GUARANTEED_BY_FREE_ROUTE",
        "revision_support": "EVENT_REVISIONS_NOT_DOCUMENTED",
        "detail": {"event_count": event_count},
    }


def parse_frankfurter(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8-sig"))
    rates = data.get("rates", {})
    if not {"CNY", "HKD"}.issubset(rates):
        raise ValueError("FX pairs missing")
    return {
        "sample_count": 2,
        "field_coverage": ["amount", "base", "date", "rates.CNY", "rates.HKD"],
        "capabilities": ["USD_CNY_AND_USD_HKD_FX"],
        "history_start": data.get("date"),
        "history_end": data.get("date"),
        "point_in_time_support": "REFERENCE_DATE",
        "revision_support": "NOT_DOCUMENTED",
    }


PARSERS = {
    "SEC_COMPANY_TICKERS_EXCHANGE": parse_sec_tickers,
    "SEC_SUBMISSIONS": parse_submissions,
    "SEC_COMPANYFACTS": parse_companyfacts,
    "NASDAQ_PIPE_DIRECTORY": parse_nasdaq,
    "STOOQ_DAILY_CSV": parse_stooq,
    "YAHOO_CHART_EVENTS": parse_yahoo,
    "FRANKFURTER_FX": parse_frankfurter,
}


def base_observation(interface: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    return {
        "program_id": PROGRAM_ID,
        "interface_id": interface["interface_id"],
        "route_id": route["route_id"],
        "source_authority": route["source_authority"],
        "official_or_fallback": route["official_or_fallback"],
        "endpoint": route["endpoint"],
        "required": bool(route["required"]),
        "parser": route["parser"],
        "access_status": "FAIL",
        "http_status": None,
        "latency_ms": None,
        "response_bytes": 0,
        "payload_sha256": None,
        "sample_count": 0,
        "field_coverage": [],
        "capabilities": [],
        "history_start": None,
        "history_end": None,
        "rate_limit_headers": {},
        "github_actions_compatibility": False,
        "point_in_time_support": "NOT_EVALUATED",
        "revision_support": "NOT_EVALUATED",
        "failure_mode": None,
        "error": None,
        "retrieved_at_utc": utc_now(),
    }


def fetch_simple(session: requests.Session, interface: dict[str, Any], route: dict[str, Any], timeout: int) -> dict[str, Any]:
    observation = base_observation(interface, route)
    started = time.perf_counter()
    payload = b""
    response: requests.Response | None = None
    try:
        response = session.get(route["endpoint"], timeout=timeout)
        payload = response.content
        observation["http_status"] = response.status_code
        observation["rate_limit_headers"] = {
            key: value for key, value in response.headers.items()
            if key.lower().startswith(("x-ratelimit", "retry-after"))
        }
        if response.status_code >= 400:
            raise requests.HTTPError(f"HTTP {response.status_code}")
        observation.update(PARSERS[route["parser"]](payload))
        observation["access_status"] = "SUCCESS"
        observation["github_actions_compatibility"] = True
    except Exception as error:
        observation["error"] = f"{type(error).__name__}: {error}"[:1000]
        if response is not None and response.status_code < 400 and payload:
            observation["failure_mode"] = "SCHEMA_OR_PARSE_DRIFT"
        else:
            observation["failure_mode"] = classify_failure(error, getattr(response, "status_code", None), payload)
    observation["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    observation["response_bytes"] = len(payload)
    if payload:
        observation["payload_sha256"] = sha256_bytes(payload)
    return observation


def fetch_ecb(session: requests.Session, interface: dict[str, Any], route: dict[str, Any], timeout: int, start_date: str) -> dict[str, Any]:
    observation = base_observation(interface, route)
    started = time.perf_counter()
    payloads: list[bytes] = []
    dates: list[str] = []
    try:
        for currency in ("USD", "CNY", "HKD"):
            url = route["endpoint"].replace("<CURRENCY>", currency).replace("<START>", start_date)
            response = session.get(url, timeout=timeout)
            observation["http_status"] = response.status_code
            if response.status_code >= 400:
                raise requests.HTTPError(f"HTTP {response.status_code} {currency}")
            payloads.append(response.content)
            rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig", errors="replace"))))
            if not rows:
                raise ValueError(f"empty ECB rows {currency}")
            for row in rows:
                date = row.get("TIME_PERIOD") or row.get("TIME PERIOD")
                if date:
                    dates.append(date)
        payload = b"\n--SERIES--\n".join(payloads)
        observation.update({
            "access_status": "SUCCESS",
            "github_actions_compatibility": True,
            "sample_count": len(dates),
            "field_coverage": ["TIME_PERIOD", "OBS_VALUE", "CURRENCY", "CURRENCY_DENOM"],
            "capabilities": ["USD_CNY_AND_USD_HKD_FX"],
            "history_start": min(dates, default=None),
            "history_end": max(dates, default=None),
            "point_in_time_support": "REFERENCE_DATE",
            "revision_support": "OFFICIAL_SERIES_RETRIEVABLE",
            "response_bytes": len(payload),
            "payload_sha256": sha256_bytes(payload),
        })
    except Exception as error:
        observation["error"] = f"{type(error).__name__}: {error}"[:1000]
        observation["failure_mode"] = classify_failure(error, observation.get("http_status"), b"")
    observation["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return observation


def fetch_live(repo_root: Path, contract_path: Path, raw_path: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    checks, errors = validate_contract(repo_root, contract_path)
    if errors:
        raise ValueError(f"contract invalid: {errors}")
    session = make_session(contract)
    benchmark_started = utc_now()
    timeout = int(contract["network_policy"]["timeout_seconds"])
    observations: list[dict[str, Any]] = []
    for interface in contract["interfaces"]:
        for route in interface["routes"]:
            if route["parser"] == "ECB_REFERENCE_FX":
                observation = fetch_ecb(session, interface, route, timeout, contract["probe_window"]["fx_start_date"])
            else:
                observation = fetch_simple(session, interface, route, timeout)
            observations.append(observation)
    raw = {
        "program_id": PROGRAM_ID,
        "benchmark_started_at_utc": benchmark_started,
        "benchmark_completed_at_utc": utc_now(),
        "environment": "GITHUB_ACTIONS" if os.getenv("GITHUB_ACTIONS") == "true" else "LOCAL_OR_OTHER",
        "contract_sha256": sha256_file(contract_path),
        "observation_count": len(observations),
        "observations": observations,
        "contract_check_count": len(checks),
        "trade_authority": "NONE",
    }
    write_json(raw_path, raw)
    return raw
