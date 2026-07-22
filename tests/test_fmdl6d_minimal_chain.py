from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from fmdl6d_minimal_chain import (  # noqa: E402
    build_candidate,
    load_json,
    publish_candidate,
    sha256_file,
    validate_candidate,
    validate_contract,
    write_json,
)

CONTRACT_REL = Path("config/fmdl6d_minimal_end_to_end_data_chain_contract.json")
SEC_REL = Path("datasets/fmdl6d/source_snapshots/sec_financial_fact_sample.json")


def _copy_static_assets(repo: Path) -> dict:
    for relative in (CONTRACT_REL, SEC_REL):
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return load_json(repo / CONTRACT_REL)


def _upstream_pool_rows(contract: dict) -> list[dict]:
    mic_by_ticker = {
        "AAPL": "XNAS",
        "BRK-B": "XNYS",
        "BABA": "XNYS",
        "ASML": "XNAS",
        "EQIX": "XNAS",
        "JPM": "XNYS",
        "GEV": "XNYS",
        "UEC": "XASE",
    }
    instrument_by_ticker = {
        "AAPL": "COMMON_STOCK",
        "BRK-B": "COMMON_STOCK",
        "BABA": "ADR",
        "ASML": "FOREIGN_PRIVATE_ISSUER_ORDINARY",
        "EQIX": "EQUITY_REIT_COMMON",
        "JPM": "COMMON_STOCK",
        "GEV": "COMMON_STOCK",
        "UEC": "COMMON_STOCK",
    }
    class_by_ticker = {
        "AAPL": "COMMON",
        "BRK-B": "CLASS_B",
        "BABA": "ADS",
        "ASML": "REGISTERED_SHARE",
        "EQIX": "COMMON",
        "JPM": "COMMON",
        "GEV": "COMMON",
        "UEC": "COMMON",
    }
    profile_by_ticker = {
        "AAPL": "DOMESTIC_10K_US_GAAP",
        "BRK-B": "DOMESTIC_10K_US_GAAP",
        "BABA": "FOREIGN_20F_US_GAAP",
        "ASML": "FOREIGN_20F_IFRS",
        "EQIX": "REIT_10K_US_GAAP",
        "JPM": "BANK_10K_US_GAAP",
        "GEV": "DOMESTIC_10K_US_GAAP",
        "UEC": "DOMESTIC_10K_US_GAAP",
    }
    rows = []
    for sample in contract["sample_securities"]:
        ticker = sample["ticker"]
        cik = sample["cik10"]
        rows.append(
            {
                "security_key": sample["security_key"],
                "issuer_key": f"SEC:CIK:{cik}",
                "share_class_key": f"USCLASS:SEC:CIK:{cik}:{class_by_ticker[ticker]}",
                "listing_observation_key": f"USLISTOBS:{mic_by_ticker[ticker]}:{ticker}:20260722",
                "ticker": ticker,
                "mic": mic_by_ticker[ticker],
                "instrument_type": instrument_by_ticker[ticker],
                "reporting_profile": profile_by_ticker[ticker],
                "cik10": cik,
                "benchmark_only": True,
                "investment_eligible": False,
                "research_candidate": False,
                "trade_authority": "NONE",
            }
        )
    return rows


def _write_upstream(repo: Path, contract: dict) -> None:
    b_pointer = {
        "program_id": "FMDL-6B",
        "release_id": contract["entry_gates"]["fmdl6b_release_id"],
        "status": contract["entry_gates"]["fmdl6b_status"],
        "trade_authority": "NONE",
    }
    c_pointer = {
        "program_id": "FMDL-6C",
        "release_id": contract["entry_gates"]["fmdl6c_release_id"],
        "status": contract["entry_gates"]["fmdl6c_status"],
        "trade_authority": "NONE",
    }
    write_json(repo / contract["entry_gates"]["fmdl6b_pointer"], b_pointer)
    write_json(repo / contract["entry_gates"]["fmdl6c_pointer"], c_pointer)
    write_json(
        repo / "outputs/fmdl6c/current/FMDL6C_BENCHMARK_POOL.json",
        {
            "program_id": "FMDL-6C",
            "release_id": c_pointer["release_id"],
            "benchmark_pool_is_not_candidate_pool": True,
            "securities": _upstream_pool_rows(contract),
            "trade_authority": "NONE",
        },
    )


def _daily_rows(count: int = 260) -> list[dict]:
    start = date(2025, 1, 2)
    rows = []
    for index in range(count):
        current = start + timedelta(days=index)
        base = 100.0 + index / 10.0
        rows.append(
            {
                "trade_date": current.isoformat(),
                "open": base,
                "high": base + 2.0,
                "low": base - 2.0,
                "close": base + 0.5,
                "adjusted_close": base + 0.4,
                "volume": 1_000_000 + index,
            }
        )
    return rows


def _fx_rows(count: int = 120, base: float = 7.0) -> list[dict]:
    start = date(2025, 1, 2)
    return [
        {"reference_date": (start + timedelta(days=index)).isoformat(), "rate": base + index / 10000.0}
        for index in range(count)
    ]


def _make_capture(repo: Path, contract: dict) -> Path:
    market = []
    for index, sample in enumerate(contract["sample_securities"]):
        market.append(
            {
                "sample": sample,
                "capture": {
                    "route_id": "YAHOO_QUERY1_CHART_EVENTS",
                    "source_authority": "YAHOO_FREE_UNOFFICIAL",
                    "official_or_fallback": "FREE_FALLBACK",
                    "url": f"https://query1.finance.yahoo.com/v8/finance/chart/{sample['market_symbol']}",
                    "http_status": 200,
                    "latency_ms": 10.0 + index,
                    "response_bytes": 10000 + index,
                    "payload_sha256": hashlib.sha256(sample["ticker"].encode()).hexdigest(),
                    "retrieved_headers": {"content-type": "application/json"},
                    "meta": {
                        "returned_symbol": sample["market_symbol"],
                        "currency": "USD",
                        "exchange_name": "Synthetic Test Exchange",
                        "instrument_type": "EQUITY",
                        "timezone": "America/New_York",
                    },
                    "observations": _daily_rows(),
                    "events": [
                        {
                            "event_type": "DIVIDEND",
                            "event_date": "2025-03-01",
                            "amount": 0.25,
                            "currency": "USD",
                        }
                    ]
                    if sample["ticker"] == "AAPL"
                    else [],
                },
            }
        )
    ecb_series = {}
    for index, currency in enumerate(contract["source_routes"]["fx"]["currencies"]):
        ecb_series[currency] = {
            "route_id": f"ECB_EXR_D_{currency}_EUR_SP00_A",
            "source_authority": "ECB_OFFICIAL",
            "official_or_fallback": "OFFICIAL_PRIMARY",
            "url": f"https://data-api.ecb.europa.eu/service/data/EXR/D.{currency}.EUR.SP00.A",
            "http_status": 200,
            "latency_ms": 20.0,
            "response_bytes": 5000,
            "payload_sha256": hashlib.sha256(currency.encode()).hexdigest(),
            "retrieved_headers": {"content-type": "text/csv"},
            "currency": currency,
            "observations": [
                {
                    "reference_date": (date(2025, 1, 2) + timedelta(days=row_index)).isoformat(),
                    "eur_per_unit_inverse": 1.0 + index + row_index / 10000.0,
                }
                for row_index in range(120)
            ],
        }
    sec_path = repo / SEC_REL
    capture = {
        "program_id": "FMDL-6D",
        "captured_at_utc": "2026-07-22T06:30:00Z",
        "as_of_date": "2026-07-22",
        "contract_sha256": sha256_file(repo / CONTRACT_REL),
        "contract_checks": [],
        "upstream": {
            "fmdl6b": load_json(repo / contract["entry_gates"]["fmdl6b_pointer"]),
            "fmdl6c": load_json(repo / contract["entry_gates"]["fmdl6c_pointer"]),
        },
        "market": market,
        "ecb_series": ecb_series,
        "fx_pairs": {"USD/CNY": _fx_rows(base=7.1), "USD/HKD": _fx_rows(base=7.8)},
        "sec_financial_snapshot": {
            "path": str(SEC_REL),
            "sha256": sha256_file(sec_path),
            "snapshot": load_json(sec_path),
        },
        "trade_authority": "NONE",
    }
    capture_path = repo / "outputs/fmdl6d/work/FMDL6D_RAW_CAPTURE.json"
    write_json(capture_path, capture)
    return capture_path


def _make_repo(tmp_path: Path) -> tuple[Path, dict, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    contract = _copy_static_assets(repo)
    _write_upstream(repo, contract)
    capture = _make_capture(repo, contract)
    return repo, contract, capture


def test_contract_passes_with_accepted_upstream(tmp_path: Path) -> None:
    repo, _, _ = _make_repo(tmp_path)
    checks, errors = validate_contract(repo, repo / CONTRACT_REL)
    assert not errors
    assert len(checks) >= 35
    assert all(row["status"] == "PASS" for row in checks)


def test_build_validate_replay_and_publish(tmp_path: Path) -> None:
    repo, contract, capture = _make_repo(tmp_path)
    candidate = repo / "outputs/fmdl6d/candidate"
    release = build_candidate(repo, repo / CONTRACT_REL, capture, candidate)
    assert release["status"] == contract["exit_status"]
    assert release["market_security_count"] == 8
    assert release["financial_sample_issuer_count"] == 4
    assert release["chain_record_count"] == 8
    assert release["small_sample_not_full_universe"] is True
    assert release["decision_grade_market_data_authorized"] is False
    assert release["trade_authority"] == "NONE"

    acceptance = validate_candidate(
        repo,
        repo / CONTRACT_REL,
        capture,
        candidate,
        repo / "outputs/fmdl6d/acceptance/FMDL6D_INDEPENDENT_ACCEPTANCE.json",
    )
    assert acceptance["validation"] == "PASS"
    assert acceptance["same_input_replay"] == "PASS"
    assert acceptance["errors"] == []

    last_success = publish_candidate(repo, repo / CONTRACT_REL, candidate)
    assert last_success["status"] == contract["exit_status"]
    assert last_success["trade_authority"] == "NONE"
    assert (repo / last_success["current_path"] / "FMDL6D_MANIFEST.json").exists()
    assert (repo / last_success["archive_path"] / "FMDL6D_MANIFEST.json").exists()
    assert (repo / last_success["immutable_path"] / "FMDL6D_MANIFEST.json").exists()


def test_availability_fields_are_conservative_and_complete(tmp_path: Path) -> None:
    repo, _, capture = _make_repo(tmp_path)
    candidate = repo / "outputs/fmdl6d/candidate"
    build_candidate(repo, repo / CONTRACT_REL, capture, candidate)
    market = load_json(candidate / "FMDL6D_MARKET_STORE.json")
    assert all(
        row["available_from_utc"] == "2026-07-22T06:30:00Z"
        and row["availability_basis"] == "CONSERVATIVE_RETRIEVAL_TIMESTAMP"
        and row["point_in_time_status"] == "RETRIEVAL_BOUND_ONLY_NOT_HISTORICAL_AS_OF"
        for security in market["securities"]
        for row in security["observations"]
    )
    financial = load_json(candidate / "FMDL6D_FINANCIAL_FACT_SAMPLE.json")
    assert all(fact["decision_grade"] is False for fact in financial["facts"])
    chain = load_json(candidate / "FMDL6D_CHAIN_RECORDS.json")
    assert all(
        record["benchmark_only"] is True
        and record["investment_eligible"] is False
        and record["research_candidate"] is False
        and record["trade_authority"] == "NONE"
        for record in chain["records"]
    )


def test_missing_market_security_fails_closed(tmp_path: Path) -> None:
    repo, _, capture_path = _make_repo(tmp_path)
    capture = load_json(capture_path)
    capture["market"] = capture["market"][:-1]
    write_json(capture_path, capture)
    with pytest.raises(ValueError, match="CAPTURE_MARKET_SECURITY_COUNT"):
        build_candidate(repo, repo / CONTRACT_REL, capture_path, repo / "outputs/fmdl6d/candidate")


def test_manifest_preserving_state_mutation_is_rejected(tmp_path: Path) -> None:
    repo, _, capture = _make_repo(tmp_path)
    candidate = repo / "outputs/fmdl6d/candidate"
    build_candidate(repo, repo / CONTRACT_REL, capture, candidate)
    decision_path = candidate / "FMDL6D_DECISION.json"
    decision = load_json(decision_path)
    decision["candidate_pool_mutation_count"] = 1
    write_json(decision_path, decision)
    manifest_path = candidate / "FMDL6D_MANIFEST.json"
    manifest = load_json(manifest_path)
    manifest["files"]["FMDL6D_DECISION.json"] = {
        "sha256": sha256_file(decision_path),
        "size_bytes": decision_path.stat().st_size,
    }
    write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="DECISION_MUTATION|STATE_MUTATION|CANONICAL_RECOMPUTE"):
        validate_candidate(
            repo,
            repo / CONTRACT_REL,
            capture,
            candidate,
            repo / "outputs/fmdl6d/acceptance/FMDL6D_INDEPENDENT_ACCEPTANCE.json",
        )
