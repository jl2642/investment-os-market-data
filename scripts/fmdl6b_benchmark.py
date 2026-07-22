from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PROGRAM_ID = "FMDL-6B"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_session(contract: dict[str, Any]) -> requests.Session:
    network = contract["network_policy"]
    retry = Retry(
        total=max(int(network["max_attempts"]) - 1, 0),
        connect=max(int(network["max_attempts"]) - 1, 0),
        read=max(int(network["max_attempts"]) - 1, 0),
        status=max(int(network["max_attempts"]) - 1, 0),
        backoff_factor=float(network["backoff_seconds"]),
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {
            "User-Agent": os.getenv(network["sec_user_agent_env"], network["default_sec_user_agent"]),
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json,text/csv,text/plain,*/*",
            "Connection": "keep-alive",
        }
    )
    return session


def classify_failure(exc: Exception | None, status_code: int | None, text: str = "") -> str:
    if isinstance(exc, requests.Timeout):
        return "TIMEOUT"
    if isinstance(exc, requests.exceptions.SSLError):
        return "TLS_OR_CERTIFICATE"
    if isinstance(exc, requests.ConnectionError):
        return "DNS_OR_CONNECTIVITY"
    if status_code == 429:
        return "HTTP_429_RATE_LIMIT"
    if status_code is not None and 400 <= status_code < 500:
        return "HTTP_4XX_AUTH_OR_BLOCK"
    if status_code is not None and status_code >= 500:
        return "HTTP_5XX_UPSTREAM"
    if not text.strip():
        return "EMPTY_RESPONSE"
    return "UNKNOWN_FAILURE"


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


def parse_sec_company_tickers(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8-sig"))
    fields = data.get("fields", [])
    rows = data.get("data", [])
    if not isinstance(fields, list) or not isinstance(rows, list) or len(rows) < 1000:
        raise ValueError("insufficient SEC ticker-exchange rows")
    row_dicts = [dict(zip(fields, row)) for row in rows[: min(len(rows), 10000)]]
    aapl = next((row for row in row_dicts if str(row.get("ticker", "")).upper() == "AAPL"), None)
    if not aapl:
        raise ValueError("AAPL not found in SEC ticker-exchange reference")
    return {
        "sample_count": len(rows),
        "field_coverage": fields,
        "capabilities": ["CIK_TICKER_EXCHANGE_REFERENCE"],
        "point_in_time_support": "RETRIEV