from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PROGRAM_ID = "FMDL-6B"
CONTRACT_DEFAULT = "config/fmdl6b_source_interface_access_benchmark_contract.json"
REQUIRED_CANDIDATE_FILES = {
    "FMDL6B_RAW_OBSERVATIONS.json",
    "FMDL6B_INTERFACE_BENCHMARK.json",
    "FMDL6B_SOURCE_REGISTRY.json",
    "FMDL6B_FAILURE_TAXONOMY.json",
    "FMDL6B_DECISION.json",
    "FMDL6B_VALIDATION.json",
    "FMDL6B_RELEASE.json",
    "FMDL6B_MANIFEST.json",
}


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


def validate_contract(repo_root: Path, contract_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    contract = load_json(contract_path)
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def check(check_id: str, condition: bool, actual: Any, expected: Any) -> None:
        checks.append({
            "check_id": check_id,
            "status": "PASS" if condition else "FAIL",
            "actual": actual,
            "expected": expected,
        })
        if not condition:
            errors.append(check_id)

    check("PROGRAM_ID", contract.get("program_id") == PROGRAM_ID, contract.get("program_id"), PROGRAM_ID)
    check("STATUS", contract.get("status") == "BENCHMARK_CONTRACT_CANDIDATE", contract.get("status"), "BENCHMARK_CONTRACT_CANDIDATE")
    check("TRADE_AUTHORITY", contract.get("trade_authority") == "NONE", contract.get("trade_authority"), "NONE")

    entry = contract.get("entry_gate", {})
    pointer_path = repo_root / str(entry.get("pointer_path", ""))
    check("ENTRY_POINTER_EXISTS", pointer_path.is_file(), str(pointer_path), "existing file")
    if pointer_path.is_file():
        pointer = load_json(pointer_path)
        check("ENTRY_RELEASE", pointer.get("release_id") == entry.get("required_release_id"), pointer.get("release_id"), entry.get("required_release_id"))
        check("ENTRY_STATUS", pointer.get("status") == entry.get("required_status"), pointer.get("status"), entry.get("required_status"))
        check("ENTRY_GATE", pointer.get("next_gate") == entry.get("required_next_gate"), pointer.get("next_gate"), entry.get("required_next_gate"))
        check("ENTRY_AUTHORITY", pointer.get("trade_authority") == "NONE", pointer.get("trade_authority"), "NONE")

    scope = contract.get("scope", {})
    check("SCOPE", scope.get("mode") == "LIVE_INTERFACE_BENCHMARK_ONLY", scope.get("mode"), "LIVE_INTERFACE_BENCHMARK_ONLY")
    check("BENCHMARK_TARGET", scope.get("benchmark_security_target_reserved_for_fmdl6c") == 24, scope.get("benchmark_security_target_reserved_for_fmdl6c"), 24)
    for key in (
        "live_security_master_build_authorized",
        "full_history_build_authorized",
        "financial_fact_store_build_authorized",
        "factor_or_screening_build_authorized",
        "candidate_pool_integration_authorized",
        "simulation_integration_authorized",
        "real_account_integration_authorized",
        "order_generation_authorized",
    ):
        check(f"AUTH_FALSE:{key}", scope.get(key) is False, scope.get(key), False)

    interfaces = contract.get("interfaces", [])
    check("INTERFACE_COUNT", len(interfaces) == 4, len(interfaces), 4)
    route_ids = [route.get("route_id") for interface in interfaces for route in interface.get("routes", [])]
    check("ROUTE_COUNT", len(route_ids) == 11, len(route_ids), 11)
    check("ROUTE_IDS_UNIQUE", len(route_ids) == len(set(route_ids)), len(route_ids) - len(set(route_ids)), 0)
    required = set(contract.get("capability_acceptance", {}).get("required_official_route_ids", []))
    expected_required = {"SEC_COMPANY_TICKERS_EXCHANGE", "SEC_SUBMISSIONS_AAPL", "SEC_COMPANYFACTS_AAPL"}
    check("REQUIRED_SEC_SET", required == expected_required, sorted(required), sorted(expected_required))
    check("FAILURE_TAXONOMY", len(contract.get("failure_taxonomy", [])) >= 10, len(contract.get("failure_taxonomy", [])), ">=10")

    gates = contract.get("acceptance_gates", {})
    for key in ("candidate_pool_mutation_count", "simulation_mutation_count", "real_account_mutation_count", "order_generation_count"):
        check(f"ZERO:{key}", gates.get(key) == 0, gates.get(key), 0)
    check("GATE_AUTHORITY", gates.get("trade_authority") == "NONE", gates.get("trade_authority"), "NONE")
    check("RELEASE_SEQUENCE", contract.get("publication", {}).get("release_sequence") == 21, contract.get("publication", {}).get("release_sequence"), 21)
    check("EXIT_STATUS", contract.get("exit_status") == "FMDL6B_SOURCE_INTERFACE_AND_ACCESS_BENCHMARK_ACCEPTED", contract.get("exit_status"), "accepted status")
    check("NEXT_GATE", contract.get("next_gate") == "FMDL-6C_24_SECURITY_BENCHMARK_POOL", contract.get("next_gate"), "FMDL-6C_24_SECURITY_BENCHMARK_POOL")
    return checks, errors


def make_session(contract: dict[str, Any]) -> requests.Session:
    network = contract["network_policy"]
    retries = max(int(network["max_attempts"]) - 1, 0)
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=float(network["backoff_seconds"]),
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({
        "User-Agent": os.getenv(network["sec_user_agent_env"], network["default_sec_user_agent"]),
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json,text/csv,text/plain,*/*",
    })
    return session


def classify_failure(exc: Exception | None, status: int | None, payload: bytes) -> str:
    if isinstance(exc, requests.Timeout):
        return "TIMEOUT"
    if isinstance(exc, requests.exceptions.SSLError):
        return "TLS_OR_CERTIFICATE"
    if isinstance(exc, requests.ConnectionError):
        return "DNS_OR_CONNECTIVITY"
    if status == 429:
        return "HTTP_429_RATE_LIMIT"
    if status is not None and 400 <= status < 500:
        return "HTTP_4XX_AUTH_OR_BLOCK"
    if status is not None and status >= 500:
        return "HTTP_5XX_UPSTREAM"
    if not payload:
        return "EMPTY_RESPONSE"
    return "UNKNOWN_FAILURE"
