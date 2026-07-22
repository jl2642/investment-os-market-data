from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from fmdl6b_benchmark import (  # noqa: E402
    build_candidate,
    independent_validate,
    load_json,
    normalize_observations,
    sha256_file,
    validate_contract,
    write_json,
)

CONTRACT_PATH = ROOT / "config/fmdl6b_source_interface_access_benchmark_contract.json"
SEC_REQUIRED = {"SEC_COMPANY_TICKERS_EXCHANGE", "SEC_SUBMISSIONS_AAPL", "SEC_COMPANYFACTS_AAPL"}


def synthetic_raw(failed_routes: set[str] | None = None) -> dict:
    failed_routes = failed_routes or set()
    contract = load_json(CONTRACT_PATH)
    capabilities = {
        "SEC_COMPANY_TICKERS_EXCHANGE": ["CIK_TICKER_EXCHANGE_REFERENCE"],
        "SEC_SUBMISSIONS_AAPL": ["SUBMISSIONS_HISTORY", "ACCESSION_AND_ACCEPTANCE_METADATA"],
        "SEC_COMPANYFACTS_AAPL": ["COMPANY_FACTS", "TAXONOMY_AND_UNITS", "ACCESSION_LINEAGE"],
        "NASDAQ_TRADER_NASDAQLISTED": ["LISTED_SYMBOL", "EXCHANGE_OR_VENUE", "INSTRUMENT_TYPE_FLAGS", "RETRIEVAL_TIMESTAMP"],
        "NASDAQ_TRADER_OTHERLISTED": ["LISTED_SYMBOL", "EXCHANGE_OR_VENUE", "INSTRUMENT_TYPE_FLAGS", "RETRIEVAL_TIMESTAMP"],
        "SEC_COMPANY_TICKERS_EXCHANGE_SUPPORT": ["CIK_TICKER_EXCHANGE_REFERENCE"],
        "STOOQ_AAPL_DAILY": ["DAILY_OHLCV"],
        "YAHOO_QUERY1_AAPL_CHART_EVENTS": ["DAILY_OHLCV", "DIVIDEND_OR_SPLIT_EVENTS"],
        "YAHOO_QUERY2_AAPL_CHART_EVENTS": ["DAILY_OHLCV", "DIVIDEND_OR_SPLIT_EVENTS"],
        "ECB_REFERENCE_FX": ["USD_CNY_AND_USD_HKD_FX"],
        "FRANKFURTER_USD_CNY_HKD": ["USD_CNY_AND_USD_HKD_FX"],
    }
    observations = []
    for interface in contract["interfaces"]:
        for route in interface["routes"]:
            failed = route["route_id"] in failed_routes
            observations.append({
                "program_id": "FMDL-6B",
                "interface_id": interface["interface_id"],
                "route_id": route["route_id"],
                "source_authority": route["source_authority"],
                "official_or_fallback": route["official_or_fallback"],
                "endpoint": route["endpoint"],
                "required": route["required"],
                "parser": route["parser"],
                "access_status": "FAIL" if failed else "SUCCESS",
                "http_status": 503 if failed else 200,
                "latency_ms": 100.0,
                "response_bytes": 1000,
                "payload_sha256": route["route_id"].lower().ljust(64, "0")[:64],
                "sample_count": 0 if failed else 100,
                "field_coverage": [] if failed else ["field"],
                "capabilities": [] if failed else capabilities[route["route_id"]],
                "history_start": "2025-01-01",
                "history_end": "2026-07-22",
                "rate_limit_headers": {},
                "github_actions_compatibility": not failed,
                "point_in_time_support": "TEST",
                "revision_support": "TEST",
                "failure_mode": "HTTP_5XX_UPSTREAM" if failed else None,
                "error": "synthetic" if failed else None,
                "retrieved_at_utc": "2026-07-22T00:00:00Z",
            })
    return {
        "program_id": "FMDL-6B",
        "benchmark_started_at_utc": "2026-07-22T00:00:00Z",
        "benchmark_completed_at_utc": "2026-07-22T00:01:00Z",
        "environment": "GITHUB_ACTIONS",
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "observation_count": len(observations),
        "observations": observations,
        "contract_check_count": 1,
        "trade_authority": "NONE",
    }


def sec_hosted_runner_block_raw() -> dict:
    raw = synthetic_raw(SEC_REQUIRED)
    for row in raw["observations"]:
        if row["route_id"] in SEC_REQUIRED:
            row["http_status"] = 403
            row["failure_mode"] = "HTTP_4XX_AUTH_OR_BLOCK"
            row["error"] = "HTTPError: HTTP 403"
    return raw


def test_contract_passes() -> None:
    checks, errors = validate_contract(ROOT, CONTRACT_PATH)
    assert not errors
    assert checks
    assert all(row["status"] == "PASS" for row in checks)


def test_successful_observations_accept_all_capabilities() -> None:
    normalized = normalize_observations(load_json(CONTRACT_PATH), synthetic_raw())
    assert normalized["hard_failures"] == []
    assert all(normalized["capability_summary"].values())
    assert "FREE_MARKET_DATA_PILOT_ONLY_NOT_DECISION_GRADE" in normalized["controlled_limitations"]


def test_nasdaq_degradation_is_controlled_when_sec_support_works() -> None:
    normalized = normalize_observations(
        load_json(CONTRACT_PATH),
        synthetic_raw({"NASDAQ_TRADER_NASDAQLISTED", "NASDAQ_TRADER_OTHERLISTED"}),
    )
    assert normalized["hard_failures"] == []
    assert "NASDAQ_CURRENT_DIRECTORY_UNAVAILABLE_USING_SEC_CURRENT_SUPPORT" in normalized["controlled_limitations"]


def test_required_sec_route_upstream_failure_is_hard_failure() -> None:
    normalized = normalize_observations(load_json(CONTRACT_PATH), synthetic_raw({"SEC_COMPANYFACTS_AAPL"}))
    assert "REQUIRED_OFFICIAL_ROUTE_FAILED:SEC_COMPANYFACTS_AAPL" in normalized["hard_failures"]


def test_repeatable_sec_403_on_hosted_runner_is_controlled_external_route() -> None:
    normalized = normalize_observations(load_json(CONTRACT_PATH), sec_hosted_runner_block_raw())
    assert normalized["hard_failures"] == []
    assert normalized["execution_route_decision"]["github_hosted_actions"] == "UNAVAILABLE_FOR_SEC_OFFICIAL_APIS_403"
    assert normalized["execution_route_decision"]["third_party_sec_proxy_authorized"] is False
    assert "SEC_OFFICIAL_APIS_RETURN_403_ON_GITHUB_HOSTED_RUNNER" in normalized["controlled_limitations"]
    decisions = {row["route_id"]: row["route_decision"] for row in normalized["routes"]}
    assert all(decisions[route_id] == "OFFICIAL_EXTERNAL_EXECUTION_REQUIRED" for route_id in SEC_REQUIRED)


def test_missing_corporate_action_route_is_hard_failure() -> None:
    normalized = normalize_observations(
        load_json(CONTRACT_PATH),
        synthetic_raw({"YAHOO_QUERY1_AAPL_CHART_EVENTS", "YAHOO_QUERY2_AAPL_CHART_EVENTS"}),
    )
    assert "NO_CORPORATE_ACTION_EVENT_ROUTE" in normalized["hard_failures"]


def test_candidate_build_and_replay_are_deterministic(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.json"
    write_json(raw_path, synthetic_raw())
    candidate = tmp_path / "candidate"
    release = build_candidate(ROOT, CONTRACT_PATH, raw_path, candidate)
    assert release["status"] == "FMDL6B_SOURCE_INTERFACE_AND_ACCESS_BENCHMARK_ACCEPTED"
    assert release["decision_grade_market_data_authorized"] is False
    acceptance = independent_validate(ROOT, CONTRACT_PATH, raw_path, candidate)
    assert acceptance["validation"] == "PASS"
    assert acceptance["same_input_replay"] == "PASS"


def test_controlled_sec_403_candidate_build_and_replay_are_deterministic(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.json"
    write_json(raw_path, sec_hosted_runner_block_raw())
    candidate = tmp_path / "candidate"
    release = build_candidate(ROOT, CONTRACT_PATH, raw_path, candidate)
    assert release["sec_official_github_actions_compatible"] is False
    assert release["execution_route_decision"]["approved_pilot_execution_route"] == "CHATGPT_WEB_OR_LOCAL_OR_SELF_HOSTED_RUNNER"
    acceptance = independent_validate(ROOT, CONTRACT_PATH, raw_path, candidate)
    assert acceptance["validation"] == "PASS"
    assert acceptance["same_input_replay"] == "PASS"


def test_failed_live_benchmark_cannot_build(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.json"
    write_json(raw_path, synthetic_raw({"SEC_SUBMISSIONS_AAPL"}))
    with pytest.raises(ValueError):
        build_candidate(ROOT, CONTRACT_PATH, raw_path, tmp_path / "candidate")
