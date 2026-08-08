from __future__ import annotations

import hashlib
import json
from pathlib import Path

from automation.cross_market.apply_round3_sec_observer_results import validate_inbox
from automation.cross_market.collect_round3_sec_official import RETRIEVAL_ENVIRONMENT, TICKER_URL, collect


def _queue() -> dict:
    return {
        "run_id": "ROUND3_TEST_SEC_COLLECTOR",
        "as_of_date": "2026-08-07",
        "execution_environment_required": "CHATGPT_WEB_CONTROLLED_OFFICIAL_RETRIEVAL",
        "queue": [
            {
                "canonical_issuer_id": "USISS-ABC",
                "symbol": "ABC",
                "cik": "",
                "official_resolution_route": "SYMBOL_TO_SEC_OFFICIAL_TICKER_MAP_TO_CIK",
                "required_sources": ["SEC_COMPANY_TICKERS", "SEC_SUBMISSIONS", "SEC_COMPANYFACTS"],
            },
            {
                "canonical_issuer_id": "USISS-XYZ",
                "symbol": "XYZ",
                "cik": "0002222222",
                "official_resolution_route": "CIK_DIRECT",
                "required_sources": ["SEC_SUBMISSIONS", "SEC_COMPANYFACTS"],
            },
        ],
        "orders": 0,
        "trade_authority": "NONE",
    }


def _payloads() -> dict[str, bytes]:
    ticker = json.dumps({
        "0": {"ticker": "ABC", "cik_str": 1234567},
        "1": {"ticker": "XYZ", "cik_str": 2222222},
    }, sort_keys=True).encode()
    submissions_abc = json.dumps({
        "filings": {"recent": {"form": ["10-Q"], "filingDate": ["2026-08-01"]}}
    }, sort_keys=True).encode()
    submissions_xyz = json.dumps({
        "filings": {"recent": {"form": ["8-K"], "filingDate": ["2026-08-02"]}}
    }, sort_keys=True).encode()
    facts_abc = json.dumps({"facts": {"us-gaap": {"Assets": {}}}}, sort_keys=True).encode()
    facts_xyz = json.dumps({"facts": {"dei": {"EntityPublicFloat": {}}}}, sort_keys=True).encode()
    return {
        TICKER_URL: ticker,
        "https://data.sec.gov/submissions/CIK0001234567.json": submissions_abc,
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0001234567.json": facts_abc,
        "https://data.sec.gov/submissions/CIK0002222222.json": submissions_xyz,
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0002222222.json": facts_xyz,
    }


def test_collector_hashes_actual_raw_response_bytes_and_validates_inbox(tmp_path: Path) -> None:
    queue = _queue()
    payloads = _payloads()

    def fetcher(url: str, headers: dict[str, str]) -> bytes:
        assert headers["User-Agent"] == "investment-os-test contact:test@example.com"
        assert headers["Accept-Encoding"] == "identity"
        return payloads[url]

    raw_dir = tmp_path / "raw"
    inbox, manifest = collect(
        queue,
        raw_dir=raw_dir,
        user_agent="investment-os-test contact:test@example.com",
        fetcher=fetcher,
        retrieved_at="2026-08-08T03:00:00+00:00",
    )

    assert inbox["retrieval_environment"] == RETRIEVAL_ENVIRONMENT
    assert len(inbox["issuers"]) == 2
    assert inbox["failures"] == []
    assert manifest["raw_response_count"] == 5
    assert manifest["official_success_count"] == 2
    assert manifest["orders"] == 0
    assert manifest["trade_authority"] == "NONE"

    for url, raw in payloads.items():
        recorded = manifest["responses"][url]
        assert recorded["bytes"] == len(raw)
        assert recorded["sha256"] == hashlib.sha256(raw).hexdigest()
        path = Path(recorded["raw_file"])
        assert path.read_bytes() == raw

    normalized = validate_inbox(inbox, queue)
    assert normalized["retrieval_environment"] == RETRIEVAL_ENVIRONMENT
    by_symbol = {row["symbol"]: row for row in normalized["issuers"]}
    assert by_symbol["ABC"]["cik"] == "0001234567"
    assert by_symbol["ABC"]["cik_resolution_source"] == "SEC_COMPANY_TICKERS"
    assert by_symbol["XYZ"]["cik"] == "0002222222"
    assert by_symbol["XYZ"]["cik_resolution_source"] == "ACCEPTED_EVIDENCE"


def test_collector_fails_closed_per_issuer_without_fabricating_hashes(tmp_path: Path) -> None:
    queue = _queue()
    payloads = _payloads()
    blocked_url = "https://data.sec.gov/api/xbrl/companyfacts/CIK0002222222.json"

    def fetcher(url: str, headers: dict[str, str]) -> bytes:
        if url == blocked_url:
            raise OSError("controlled test outage")
        return payloads[url]

    inbox, manifest = collect(
        queue,
        raw_dir=tmp_path / "raw",
        user_agent="investment-os-test contact:test@example.com",
        fetcher=fetcher,
        retrieved_at="2026-08-08T03:00:00+00:00",
    )

    assert len(inbox["issuers"]) == 1
    assert len(inbox["failures"]) == 1
    assert inbox["failures"][0]["symbol"] == "XYZ"
    assert inbox["failures"][0]["status"] == "SEC_DATA_GAP"
    assert blocked_url not in manifest["responses"]
    assert manifest["official_success_count"] == 1
    assert manifest["official_failure_count"] == 1
    validate_inbox(inbox, queue)
