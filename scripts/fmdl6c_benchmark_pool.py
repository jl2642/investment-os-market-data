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
from typing import Any

import requests

PROGRAM_ID = "FMDL-6C"
CONTRACT_DEFAULT = "config/fmdl6c_24_security_benchmark_pool_contract.json"


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
        checks.append({"check_id": check_id, "status": "PASS" if condition else "FAIL", "actual": actual, "expected": expected})
        if not condition:
            errors.append(check_id)

    check("PROGRAM_ID", contract.get("program_id") == PROGRAM_ID, contract.get("program_id"), PROGRAM_ID)
    check("STATUS", contract.get("status") == "POOL_CONTRACT_CANDIDATE", contract.get("status"), "POOL_CONTRACT_CANDIDATE")
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


    for binding_key, expected_release in (
        ("fmdl6a_pointer", contract.get("source_bindings", {}).get("fmdl6a_release_id")),
        ("fmdl6b_pointer", contract.get("source_bindings", {}).get("fmdl6b_release_id")),
    ):
        bound_path = repo_root / str(contract.get("source_bindings", {}).get(binding_key, ""))
        check(f"SOURCE_POINTER_EXISTS:{binding_key}", bound_path.is_file(), str(bound_path), "existing file")
        if bound_path.is_file():
            bound_pointer = load_json(bound_path)
            check(f"SOURCE_POINTER_RELEASE:{binding_key}", bound_pointer.get("release_id") == expected_release, bound_pointer.get("release_id"), expected_release)
            check(f"SOURCE_POINTER_AUTHORITY:{binding_key}", bound_pointer.get("trade_authority") == "NONE", bound_pointer.get("trade_authority"), "NONE")

    scope = contract.get("scope", {})
    check("SCOPE_MODE", scope.get("mode") == "24_SECURITY_TECHNICAL_BENCHMARK_ONLY", scope.get("mode"), "24_SECURITY_TECHNICAL_BENCHMARK_ONLY")
    check("SCOPE_COUNT", scope.get("security_count") == 24, scope.get("security_count"), 24)
    for key in (
        "full_universe_build_authorized", "historical_warehouse_build_authorized",
        "financial_fact_normalization_authorized", "factor_or_screening_build_authorized",
        "research_longlist_authorized", "candidate_pool_integration_authorized",
        "simulation_integration_authorized", "real_account_integration_authorized",
        "order_generation_authorized",
    ):
        check(f"AUTHORIZATION_FALSE:{key}", scope.get(key) is False, scope.get(key), False)

    pool = contract.get("pool", [])
    check("POOL_COUNT", len(pool) == 24, len(pool), 24)
    tickers = [row.get("ticker") for row in pool]
    security_keys = [row.get("security_key") for row in pool]
    listing_observation_keys = [row.get("listing_observation_key") for row in pool]
    check("TICKERS_UNIQUE", len(tickers) == len(set(tickers)), len(tickers) - len(set(tickers)), 0)
    check("SECURITY_KEYS_UNIQUE", len(security_keys) == len(set(security_keys)), len(security_keys) - len(set(security_keys)), 0)
    check("LISTING_OBSERVATION_KEYS_UNIQUE", len(listing_observation_keys) == len(set(listing_observation_keys)), len(listing_observation_keys) - len(set(listing_observation_keys)), 0)
    check("ORDERS_CONTIGUOUS", sorted(row.get("pool_order") for row in pool) == list(range(1, 25)), sorted(row.get("pool_order") for row in pool), list(range(1, 25)))
    check("CIK10_VALID", all(isinstance(row.get("cik10"), str) and len(row["cik10"]) == 10 and row["cik10"].isdigit() for row in pool), None, "all CIK10")
    check("ALL_BENCHMARK_ONLY", all(row.get("benchmark_only") is True and row.get("investment_eligible") is False and row.get("research_candidate") is False for row in pool), None, True)
    check("CANONICAL_LISTING_KEYS_DEFERRED", all(row.get("canonical_listing_key") is None and row.get("listing_history_status") == "CURRENT_SNAPSHOT_ONLY" for row in pool), None, True)
    check("OBSERVED_ACTIVE_DATE", all(row.get("listing_observed_active_on") == contract.get("as_of_date") for row in pool), None, contract.get("as_of_date"))
    check("ALL_TRADE_AUTHORITY_NONE", all(row.get("trade_authority") == "NONE" for row in pool), None, "NONE")

    requirements = contract.get("pool_requirements", {})
    unique_issuers = {row.get("issuer_key") for row in pool}
    check("UNIQUE_ISSUER_MIN", len(unique_issuers) >= requirements.get("required_unique_issuer_count_min", 20), len(unique_issuers), f">={requirements.get('required_unique_issuer_count_min', 20)}")
    venue_counts = {mic: sum(row.get("mic") == mic for row in pool) for mic in ("XNAS", "XNYS", "XASE")}
    for mic, minimum in requirements.get("required_venues", {}).items():
        check(f"VENUE_MIN:{mic}", venue_counts.get(mic, 0) >= minimum, venue_counts.get(mic, 0), f">={minimum}")
    instrument_types = {row.get("instrument_type") for row in pool}
    for instrument_type in requirements.get("required_instrument_types", []):
        check(f"INSTRUMENT_TYPE:{instrument_type}", instrument_type in instrument_types, instrument_type in instrument_types, True)
    tags = {tag for row in pool for tag in row.get("case_tags", [])}
    for tag in requirements.get("required_case_tags", []):
        check(f"CASE_TAG:{tag}", tag in tags, tag in tags, True)
    fpi_count = sum(row.get("reporting_profile", "").startswith("FOREIGN_") for row in pool)
    multiple_class_count = sum("MULTIPLE_SHARE_CLASSES" in row.get("case_tags", []) for row in pool)
    reit_count = sum(row.get("instrument_type") == "EQUITY_REIT_COMMON" for row in pool)
    spinoff_count = sum(any(tag.startswith("SPINOFF_") for tag in row.get("case_tags", [])) for row in pool)
    check("FPI_MIN", fpi_count >= requirements.get("minimum_foreign_private_issuer_security_count", 9), fpi_count, f">={requirements.get('minimum_foreign_private_issuer_security_count', 9)}")
    check("MULTI_CLASS_MIN", multiple_class_count >= requirements.get("minimum_multiple_share_class_security_count", 6), multiple_class_count, f">={requirements.get('minimum_multiple_share_class_security_count', 6)}")
    check("REIT_MIN", reit_count >= requirements.get("minimum_reit_security_count", 2), reit_count, f">={requirements.get('minimum_reit_security_count', 2)}")
    check("SPINOFF_MIN", spinoff_count >= requirements.get("minimum_spinoff_lineage_security_count", 2), spinoff_count, f">={requirements.get('minimum_spinoff_lineage_security_count', 2)}")

    source_path = repo_root / contract["source_bindings"]["sec_selected_reference_path"]
    check("SEC_SELECTION_EXISTS", source_path.is_file(), str(source_path), "existing file")
    if source_path.is_file():
        source = load_json(source_path)
        selection_hash = sha256_bytes(stable_json(source.get("selection_rows", [])).encode("utf-8"))
        check("SEC_SELECTION_HASH", source.get("selection_sha256") == selection_hash, source.get("selection_sha256"), selection_hash)
        check("SEC_SELECTION_COUNT", len(source.get("selection_rows", [])) == 24, len(source.get("selection_rows", [])), 24)
        source_identity = [(row.get("ticker"), row.get("cik10"), row.get("mic")) for row in source.get("selection_rows", [])]
        pool_identity = [(row.get("ticker"), row.get("cik10"), row.get("mic")) for row in pool]
        check("SEC_SELECTION_MATCHES_POOL", source_identity == pool_identity, source_identity, pool_identity)
        check("SEC_SOURCE_URL", source.get("source_url") == "https://www.sec.gov/files/company_tickers_exchange.json", source.get("source_url"), "SEC official URL")
        check("SEC_NO_SILENT_REPLACEMENT", source.get("no_silent_replacement") is True, source.get("no_silent_replacement"), True)

    gates = contract.get("acceptance_gates", {})
    for key in ("candidate_pool_mutation_count", "simulation_mutation_count", "real_account_mutation_count", "order_generation_count"):
        check(f"ZERO:{key}", gates.get(key) == 0, gates.get(key), 0)
    check("GATE_AUTHORITY", gates.get("trade_authority") == "NONE", gates.get("trade_authority"), "NONE")
    check("RELEASE_SEQUENCE", contract.get("publication", {}).get("release_sequence") == 22, contract.get("publication", {}).get("release_sequence"), 22)
    check("EXIT_STATUS", contract.get("exit_status") == "FMDL6C_24_SECURITY_BENCHMARK_POOL_ACCEPTED", contract.get("exit_status"), "FMDL6C_24_SECURITY_BENCHMARK_POOL_ACCEPTED")
    check("NEXT_GATE", contract.get("next_gate") == "FMDL-6D_MINIMAL_END_TO_END_DATA_CHAIN", contract.get("next_gate"), "FMDL-6D_MINIMAL_END_TO_END_DATA_CHAIN")
    return checks, errors


def parse_pipe_directory(payload: bytes, source_id: str) -> list[dict[str, str]]:
    text = payload.decode("utf-8-sig", errors="replace").replace("\r\n", "\n")
    lines = [line for line in text.splitlines() if line.strip() and not line.startswith("File Creation Time")]
    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter="|")
    rows = []
    for row in reader:
        if not row:
            continue
        cleaned = {str(k).strip(): (str(v).strip() if v is not None else "") for k, v in row.items() if k is not None}
        cleaned["_source_id"] = source_id
        rows.append(cleaned)
    if len(rows) < 1000:
        raise ValueError(f"{source_id} directory row count too small: {len(rows)}")
    return rows


def fetch_directories(contract: dict[str, Any], output_path: Path) -> dict[str, Any]:
    session = requests.Session()
    session.headers.update({"User-Agent": "InvestmentOS-FMDL6C/1.0 jl2642@users.noreply.github.com", "Accept": "text/plain,*/*"})
    observations: list[dict[str, Any]] = []
    selected: dict[str, dict[str, Any]] = {}
    for source_id, url in (
        ("NASDAQ_LISTED", contract["source_bindings"]["nasdaq_listed_url"]),
        ("OTHER_LISTED", contract["source_bindings"]["other_listed_url"]),
    ):
        started = time.perf_counter()
        response = session.get(url, timeout=30)
        response.raise_for_status()
        payload = response.content
        rows = parse_pipe_directory(payload, source_id)
        observations.append({
            "source_id": source_id,
            "source_url": url,
            "retrieved_at_utc": utc_now(),
            "http_status": response.status_code,
            "payload_sha256": sha256_bytes(payload),
            "response_bytes": len(payload),
            "row_count": len(rows),
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "github_actions_compatible": os.getenv("GITHUB_ACTIONS") == "true",
        })
        for row in rows:
            if source_id == "NASDAQ_LISTED":
                symbol = row.get("Symbol", "")
                key = symbol.upper()
                if key:
                    selected[key] = {
                        "source_id": source_id,
                        "directory_symbol": symbol,
                        "security_name": row.get("Security Name"),
                        "exchange_code": "Q",
                        "etf": row.get("ETF"),
                        "test_issue": row.get("Test Issue"),
                        "financial_status": row.get("Financial Status"),
                    }
            else:
                symbol = row.get("ACT Symbol", "")
                key = symbol.upper()
                if key:
                    selected[key] = {
                        "source_id": source_id,
                        "directory_symbol": symbol,
                        "security_name": row.get("Security Name"),
                        "exchange_code": row.get("Exchange"),
                        "etf": row.get("ETF"),
                        "test_issue": row.get("Test Issue"),
                        "financial_status": None,
                    }
    selected_rows = []
    for pool_row in contract["pool"]:
        match = selected.get(pool_row["directory_symbol"].upper())
        selected_rows.append({
            "ticker": pool_row["ticker"],
            "directory_symbol": pool_row["directory_symbol"],
            "expected_mic": pool_row["mic"],
            "found": match is not None,
            "directory_row": match,
        })
    result = {
        "program_id": PROGRAM_ID,
        "captured_at_utc": utc_now(),
        "environment": "GITHUB_ACTIONS" if os.getenv("GITHUB_ACTIONS") == "true" else "LOCAL_OR_OTHER",
        "source_observations": observations,
        "selected_rows": selected_rows,
        "trade_authority": "NONE",
    }
    write_json(output_path, result)
    return result


def validate_directory_capture(contract: dict[str, Any], capture: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    expected_exchange_code = {"XNYS": "N", "XASE": "A"}

    def check(check_id: str, condition: bool, actual: Any, expected: Any) -> None:
        checks.append({"check_id": check_id, "status": "PASS" if condition else "FAIL", "actual": actual, "expected": expected})
        if not condition:
            errors.append(check_id)

    by_ticker = {row["ticker"]: row for row in capture.get("selected_rows", [])}
    check("CAPTURE_SECURITY_COUNT", len(by_ticker) == 24, len(by_ticker), 24)
    for pool_row in contract["pool"]:
        ticker = pool_row["ticker"]
        captured = by_ticker.get(ticker, {})
        directory_row = captured.get("directory_row") or {}
        check(f"LISTING_FOUND:{ticker}", captured.get("found") is True, captured.get("found"), True)
        if not captured.get("found"):
            continue
        check(f"ETF_FALSE:{ticker}", directory_row.get("etf") == "N", directory_row.get("etf"), "N")
        check(f"TEST_ISSUE_FALSE:{ticker}", directory_row.get("test_issue") == "N", directory_row.get("test_issue"), "N")
        if pool_row["mic"] == "XNAS":
            check(f"NASDAQ_SOURCE:{ticker}", directory_row.get("source_id") == "NASDAQ_LISTED", directory_row.get("source_id"), "NASDAQ_LISTED")
        else:
            check(f"OTHERLISTED_SOURCE:{ticker}", directory_row.get("source_id") == "OTHER_LISTED", directory_row.get("source_id"), "OTHER_LISTED")
            check(f"EXCHANGE_CODE:{ticker}", directory_row.get("exchange_code") == expected_exchange_code[pool_row["mic"]], directory_row.get("exchange_code"), expected_exchange_code[pool_row["mic"]])
    return checks, errors


def case_coverage(contract: dict[str, Any]) -> dict[str, Any]:
    pool = contract["pool"]
    tag_counts: dict[str, int] = {}
    for row in pool:
        for tag in row["case_tags"]:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    return {
        "program_id": PROGRAM_ID,
        "security_count": len(pool),
        "unique_issuer_count": len({row["issuer_key"] for row in pool}),
        "venue_counts": {mic: sum(row["mic"] == mic for row in pool) for mic in ("XNAS", "XNYS", "XASE")},
        "instrument_type_counts": {kind: sum(row["instrument_type"] == kind for row in pool) for kind in sorted({row["instrument_type"] for row in pool})},
        "reporting_profile_counts": {profile: sum(row["reporting_profile"] == profile for row in pool) for profile in sorted({row["reporting_profile"] for row in pool})},
        "case_tag_counts": dict(sorted(tag_counts.items())),
        "multi_security_issuers": {
            issuer: [row["ticker"] for row in pool if row["issuer_key"] == issuer]
            for issuer in sorted({row["issuer_key"] for row in pool})
            if sum(row["issuer_key"] == issuer for row in pool) > 1
        },
        "trade_authority": "NONE",
    }


def identity_graph(contract: dict[str, Any]) -> dict[str, Any]:
    issuers: dict[str, dict[str, Any]] = {}
    securities = []
    listings = []
    for row in contract["pool"]:
        issuers.setdefault(row["issuer_key"], {"issuer_key": row["issuer_key"], "cik10": row["cik10"], "name": row["name"]})
        securities.append({
            "issuer_key": row["issuer_key"],
            "share_class_key": row["share_class_key"],
            "security_key": row["security_key"],
            "instrument_type": row["instrument_type"],
            "class_token": row["class_token"],
            "ticker_locator": row["ticker"],
        })
        listings.append({
            "security_key": row["security_key"],
            "listing_observation_key": row["listing_observation_key"],
            "canonical_listing_key": row["canonical_listing_key"],
            "ticker": row["ticker"],
            "directory_symbol": row["directory_symbol"],
            "mic": row["mic"],
            "observed_active_on": row["listing_observed_active_on"],
            "effective_from": row["listing_effective_from"],
            "effective_to": row["listing_effective_to"],
            "listing_history_status": row["listing_history_status"],
        })
    return {
        "program_id": PROGRAM_ID,
        "issuer_count": len(issuers),
        "security_count": len(securities),
        "listing_count": len(listings),
        "issuers": list(issuers.values()),
        "securities": securities,
        "listings": listings,
        "ticker_is_identity": False,
        "exchange_is_identity": False,
        "trade_authority": "NONE",
    }


def build_candidate(repo_root: Path, contract_path: Path, capture_path: Path, candidate_root: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    contract_checks, contract_errors = validate_contract(repo_root, contract_path)
    if contract_errors:
        raise ValueError(f"contract validation failed: {contract_errors}")
    capture = load_json(capture_path)
    listing_checks, listing_errors = validate_directory_capture(contract, capture)
    if listing_errors:
        raise ValueError(f"listing validation failed: {listing_errors}")
    if candidate_root.exists():
        shutil.rmtree(candidate_root)
    candidate_root.mkdir(parents=True, exist_ok=True)

    contract_sha = sha256_file(contract_path)
    sec_snapshot_path = repo_root / contract["source_bindings"]["sec_selected_reference_path"]
    sec_snapshot_sha = sha256_file(sec_snapshot_path)
    capture_sha = sha256_file(capture_path)
    coverage = case_coverage(contract)
    graph = identity_graph(contract)
    canonical_payload = {
        "program_id": PROGRAM_ID,
        "contract_sha256": contract_sha,
        "sec_snapshot_sha256": sec_snapshot_sha,
        "directory_capture_sha256": capture_sha,
        "pool_security_keys": [row["security_key"] for row in contract["pool"]],
        "listing_observation_keys": [row["listing_observation_key"] for row in contract["pool"]],
        "coverage": coverage,
        "next_gate": contract["next_gate"],
        "trade_authority": "NONE",
    }
    canonical_sha = sha256_bytes(stable_json(canonical_payload).encode("utf-8"))
    release_id = f"FMDL6C_{contract['as_of_date'].replace('-', '')}_{canonical_sha[:12]}"

    pool_output = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "pool_type": "TECHNICAL_BENCHMARK_ONLY",
        "security_count": 24,
        "benchmark_pool_is_not_candidate_pool": True,
        "securities": contract["pool"],
        "trade_authority": "NONE",
    }
    listing_output = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "capture_sha256": capture_sha,
        "source_observations": capture["source_observations"],
        "selected_rows": capture["selected_rows"],
        "validation_check_count": len(listing_checks),
        "trade_authority": "NONE",
    }
    decision = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "status": contract["exit_status"],
        "hard_failures": [],
        "security_count": 24,
        "unique_issuer_count": coverage["unique_issuer_count"],
        "venue_counts": coverage["venue_counts"],
        "instrument_type_counts": coverage["instrument_type_counts"],
        "multiple_security_issuer_count": len(coverage["multi_security_issuers"]),
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "next_gate": contract["next_gate"],
        "trade_authority": "NONE",
    }
    validation = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "validation": "PASS",
        "contract_check_count": len(contract_checks),
        "listing_check_count": len(listing_checks),
        "pass_count": len(contract_checks) + len(listing_checks),
        "error_count": 0,
        "errors": [],
        "trade_authority": "NONE",
    }
    source_registry = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "sources": [
            {
                "source_id": "SEC_SELECTED_24_REFERENCE",
                "source_authority": "SEC_OFFICIAL",
                "path": contract["source_bindings"]["sec_selected_reference_path"],
                "sha256": sec_snapshot_sha,
                "retrieval_route": "CHATGPT_WEB",
                "scope": "SELECTED_24_LISTING_ROWS_AND_CURATED_TECHNICAL_METADATA",
            },
            *capture["source_observations"],
        ],
        "sec_official_github_actions_compatible": False,
        "sec_external_execution_route_inherited_from_fmdl6b": True,
        "trade_authority": "NONE",
    }
    release = {
        "program_id": PROGRAM_ID,
        "program_name": contract["program_name"],
        "release_id": release_id,
        "release_sequence": contract["publication"]["release_sequence"],
        "as_of_date": contract["as_of_date"],
        "status": contract["exit_status"],
        "authority": contract["authority"],
        "canonical_sha256": canonical_sha,
        "contract_sha256": contract_sha,
        "sec_snapshot_sha256": sec_snapshot_sha,
        "directory_capture_sha256": capture_sha,
        "scope_mode": contract["scope"]["mode"],
        "security_count": 24,
        "unique_issuer_count": coverage["unique_issuer_count"],
        "benchmark_pool_is_not_candidate_pool": True,
        "historical_listing_effective_dates_resolved": False,
        "decision_grade_market_data_authorized": False,
        "candidate_pool_integration_authorized": False,
        "simulation_integration_authorized": False,
        "real_account_integration_authorized": False,
        "order_generation_authorized": False,
        "next_gate": contract["next_gate"],
        "trade_authority": "NONE",
    }

    write_json(candidate_root / "FMDL6C_RELEASE.json", release)
    write_json(candidate_root / "FMDL6C_DECISION.json", decision)
    write_json(candidate_root / "FMDL6C_VALIDATION.json", validation)
    write_json(candidate_root / "FMDL6C_BENCHMARK_POOL.json", pool_output)
    write_json(candidate_root / "FMDL6C_IDENTITY_GRAPH.json", {**graph, "release_id": release_id})
    write_json(candidate_root / "FMDL6C_CASE_COVERAGE.json", {**coverage, "release_id": release_id})
    write_json(candidate_root / "FMDL6C_LISTING_OBSERVATIONS.json", listing_output)
    write_json(candidate_root / "FMDL6C_SOURCE_REGISTRY.json", source_registry)
    shutil.copy2(sec_snapshot_path, candidate_root / "FMDL6C_SEC_SELECTED_REFERENCE.json")

    files = {}
    for path in sorted(candidate_root.iterdir()):
        if path.name == "FMDL6C_MANIFEST.json" or not path.is_file():
            continue
        files[path.name] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
    manifest = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": release["release_sequence"],
        "canonical_sha256": canonical_sha,
        "contract_sha256": contract_sha,
        "sec_snapshot_sha256": sec_snapshot_sha,
        "directory_capture_sha256": capture_sha,
        "files": files,
        "trade_authority": "NONE",
    }
    write_json(candidate_root / "FMDL6C_MANIFEST.json", manifest)
    return release


def compare_dirs(left: Path, right: Path) -> list[str]:
    errors: list[str] = []
    left_files = {path.name for path in left.iterdir() if path.is_file()}
    right_files = {path.name for path in right.iterdir() if path.is_file()}
    if left_files != right_files:
        return [f"REPLAY_FILE_SET_MISMATCH:{sorted(left_files)}:{sorted(right_files)}"]
    for name in sorted(left_files):
        if sha256_file(left / name) != sha256_file(right / name):
            errors.append(f"REPLAY_HASH_MISMATCH:{name}")
    return errors


def independent_validate(repo_root: Path, contract_path: Path, capture_path: Path, candidate_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    required = {
        "FMDL6C_RELEASE.json", "FMDL6C_DECISION.json", "FMDL6C_VALIDATION.json",
        "FMDL6C_BENCHMARK_POOL.json", "FMDL6C_IDENTITY_GRAPH.json",
        "FMDL6C_CASE_COVERAGE.json", "FMDL6C_LISTING_OBSERVATIONS.json",
        "FMDL6C_SOURCE_REGISTRY.json", "FMDL6C_SEC_SELECTED_REFERENCE.json",
        "FMDL6C_MANIFEST.json",
    }
    found = {path.name for path in candidate_root.iterdir() if path.is_file()}
    if found != required:
        errors.append("CANDIDATE_FILE_SET_MISMATCH")
    release = load_json(candidate_root / "FMDL6C_RELEASE.json")
    decision = load_json(candidate_root / "FMDL6C_DECISION.json")
    validation = load_json(candidate_root / "FMDL6C_VALIDATION.json")
    pool = load_json(candidate_root / "FMDL6C_BENCHMARK_POOL.json")
    graph = load_json(candidate_root / "FMDL6C_IDENTITY_GRAPH.json")
    manifest = load_json(candidate_root / "FMDL6C_MANIFEST.json")
    if release.get("status") != "FMDL6C_24_SECURITY_BENCHMARK_POOL_ACCEPTED":
        errors.append("RELEASE_STATUS")
    if release.get("security_count") != 24 or pool.get("security_count") != 24:
        errors.append("SECURITY_COUNT")
    if pool.get("benchmark_pool_is_not_candidate_pool") is not True:
        errors.append("POOL_BOUNDARY")
    if graph.get("issuer_count", 0) < 20 or graph.get("security_count") != 24 or graph.get("listing_count") != 24:
        errors.append("IDENTITY_GRAPH_COUNTS")
    if decision.get("hard_failures"):
        errors.append("DECISION_HARD_FAILURES")
    if validation.get("validation") != "PASS" or validation.get("error_count") != 0:
        errors.append("VALIDATION_NOT_PASS")
    for key in ("candidate_pool_integration_authorized", "simulation_integration_authorized", "real_account_integration_authorized", "order_generation_authorized"):
        if release.get(key) is not False:
            errors.append(f"UNAUTHORIZED:{key}")
    if release.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")
    manifest_files = manifest.get("files", {})
    if set(manifest_files) != required - {"FMDL6C_MANIFEST.json"}:
        errors.append("MANIFEST_FILE_SET")
    for name, row in manifest_files.items():
        path = candidate_root / name
        if row.get("sha256") != sha256_file(path) or row.get("size_bytes") != path.stat().st_size:
            errors.append(f"MANIFEST_MISMATCH:{name}")
    with tempfile.TemporaryDirectory(prefix="fmdl6c_replay_") as temp:
        replay = Path(temp) / "candidate"
        build_candidate(repo_root, contract_path, capture_path, replay)
        errors.extend(compare_dirs(candidate_root, replay))
    return {
        "program_id": PROGRAM_ID,
        "release_id": release.get("release_id"),
        "validation": "PASS" if not errors else "FAIL",
        "same_input_replay": "PASS" if not any(error.startswith("REPLAY_") for error in errors) else "FAIL",
        "error_count": len(errors),
        "errors": errors,
        "trade_authority": "NONE",
    }


def publish(repo_root: Path, candidate_root: Path) -> dict[str, Any]:
    release = load_json(candidate_root / "FMDL6C_RELEASE.json")
    contract = load_json(repo_root / CONTRACT_DEFAULT)
    release_id = release["release_id"]
    for target in (
        repo_root / contract["publication"]["current_root"],
        repo_root / contract["publication"]["archive_root"] / release_id,
        repo_root / contract["publication"]["release_root"] / release_id,
    ):
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(candidate_root, target)
    last_success = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": release["release_sequence"],
        "status": release["status"],
        "canonical_sha256": release["canonical_sha256"],
        "contract_sha256": release["contract_sha256"],
        "sec_snapshot_sha256": release["sec_snapshot_sha256"],
        "directory_capture_sha256": release["directory_capture_sha256"],
        "security_count": 24,
        "unique_issuer_count": release["unique_issuer_count"],
        "benchmark_pool_is_not_candidate_pool": True,
        "current_path": contract["publication"]["current_root"],
        "immutable_path": f"{contract['publication']['release_root']}/{release_id}",
        "archive_path": f"{contract['publication']['archive_root']}/{release_id}",
        "next_gate": release["next_gate"],
        "trade_authority": "NONE",
    }
    write_json(repo_root / contract["publication"]["last_success"], last_success)
    return last_success


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("fetch", "build", "validate", "publish"):
        item = sub.add_parser(command)
        item.add_argument("--repo-root", default=".")
        item.add_argument("--contract", default=CONTRACT_DEFAULT)
        item.add_argument("--capture", default="outputs/fmdl6c/work/FMDL6C_DIRECTORY_CAPTURE.json")
        item.add_argument("--candidate", default="outputs/fmdl6c/candidate")
        item.add_argument("--acceptance", default="outputs/fmdl6c/acceptance/FMDL6C_INDEPENDENT_ACCEPTANCE.json")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    contract_path = repo_root / args.contract
    capture_path = repo_root / args.capture
    candidate_root = repo_root / args.candidate

    if args.command == "fetch":
        result = fetch_directories(load_json(contract_path), capture_path)
    elif args.command == "build":
        result = build_candidate(repo_root, contract_path, capture_path, candidate_root)
    elif args.command == "validate":
        result = independent_validate(repo_root, contract_path, capture_path, candidate_root)
        write_json(repo_root / args.acceptance, result)
        if result["validation"] != "PASS":
            print(json.dumps(result, indent=2))
            return 1
    else:
        result = publish(repo_root, candidate_root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
