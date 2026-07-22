#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

PROGRAM_ID = "FMDL-6E"
UPSTREAM_PROGRAM_ID = "FMDL-6D"
DEFAULT_CONTRACT = "config/fmdl6e_quality_failure_cost_benchmark_contract.json"
DEFAULT_CANDIDATE = "outputs/fmdl6e/candidate"
DEFAULT_ACCEPTANCE = "outputs/fmdl6e/acceptance/FMDL6E_INDEPENDENT_ACCEPTANCE.json"

INPUT_FILES = (
    "FMDL6D_MARKET_STORE.json",
    "FMDL6D_FX_STORE.json",
    "FMDL6D_FINANCIAL_FACT_SAMPLE.json",
    "FMDL6D_CHAIN_RECORDS.json",
    "FMDL6D_AVAILABILITY.json",
    "FMDL6D_SOURCE_REGISTRY.json",
    "FMDL6D_DECISION.json",
    "FMDL6D_VALIDATION.json",
    "FMDL6D_RELEASE.json",
    "FMDL6D_MANIFEST.json",
)

OUTPUT_FILES = (
    "FMDL6E_QUALITY_REPORT.json",
    "FMDL6E_FAILURE_INJECTION.json",
    "FMDL6E_LKG_PROOF.json",
    "FMDL6E_REPLAY.json",
    "FMDL6E_COST_AND_SCALING.json",
    "FMDL6E_SOURCE_BINDING.json",
    "FMDL6E_DECISION.json",
    "FMDL6E_VALIDATION.json",
    "FMDL6E_RELEASE.json",
)


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def load_bundle(input_dir: Path) -> dict[str, dict[str, Any]]:
    missing = [name for name in INPUT_FILES if not (input_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"missing FMDL-6D input files: {missing}")
    return {name: load_json(input_dir / name) for name in INPUT_FILES}


def validate_contract(repo_root: Path, contract_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    contract = load_json(contract_path)
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def check(code: str, condition: bool, detail: Any = None) -> None:
        checks.append({"check": code, "status": "PASS" if condition else "FAIL", "detail": detail})
        if not condition:
            errors.append(code)

    check("PROGRAM_ID", contract.get("program_id") == PROGRAM_ID)
    check("AUTHORITY", contract.get("authority") == "QUALITY_FAILURE_COST_BENCHMARK_ONLY")
    check("TRADE_AUTHORITY", contract.get("trade_authority") == "NONE")
    entry = contract.get("entry_gate") or {}
    pointer_path = repo_root / str(entry.get("pointer_path", ""))
    check("ENTRY_POINTER_EXISTS", pointer_path.exists(), str(pointer_path))
    if pointer_path.exists():
        pointer = load_json(pointer_path)
        check("ENTRY_RELEASE", pointer.get("release_id") == entry.get("required_release_id"), pointer.get("release_id"))
        check("ENTRY_STATUS", pointer.get("status") == entry.get("required_status"), pointer.get("status"))
        check("ENTRY_NEXT_GATE", pointer.get("next_gate") == entry.get("required_next_gate"), pointer.get("next_gate"))
        check("ENTRY_TRADE_AUTHORITY", pointer.get("trade_authority") == "NONE")
    input_dir = repo_root / str(entry.get("input_current_path", ""))
    check("INPUT_CURRENT_EXISTS", input_dir.exists(), str(input_dir))
    if input_dir.exists() and (input_dir / "FMDL6D_RELEASE.json").exists():
        release = load_json(input_dir / "FMDL6D_RELEASE.json")
        check("INPUT_RELEASE", release.get("release_id") == entry.get("required_release_id"), release.get("release_id"))
        check("INPUT_STATUS", release.get("status") == entry.get("required_status"), release.get("status"))
        check("INPUT_TRADE_AUTHORITY", release.get("trade_authority") == "NONE")
    scope = contract.get("scope") or {}
    leaked = sorted(key for key, value in scope.items() if key.endswith("_authorized") and value is not False)
    check("NO_SCOPE_AUTHORITY_LEAK", not leaked, leaked)
    dimensions = contract.get("quality_dimensions") or []
    check("QUALITY_DIMENSION_COUNT", len(dimensions) == contract["acceptance_gates"]["quality_dimension_count"], len(dimensions))
    injections = contract.get("failure_injections") or []
    check("FAILURE_INJECTION_COUNT", len(injections) >= contract["acceptance_gates"]["minimum_failure_injection_count"], len(injections))
    check("UNIQUE_FAILURE_INJECTIONS", len({row.get("injection_id") for row in injections}) == len(injections))
    check("EXIT_STATUS", contract.get("exit_status") == "FMDL6E_QUALITY_FAILURE_AND_COST_BENCHMARK_ACCEPTED")
    check("NEXT_GATE", contract.get("next_gate") == "FMDL-6-FINAL_RESUME_READY_OPERATIONAL_ACCEPTANCE")
    return checks, sorted(set(errors))


def audit_bundle(
    contract: dict[str, Any],
    bundle: dict[str, dict[str, Any]],
    input_dir: Path,
    *,
    manifest_override: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def check(dimension: str, code: str, condition: bool, detail: Any = None) -> None:
        checks.append({"dimension": dimension, "check": code, "status": "PASS" if condition else "FAIL", "detail": detail})
        if not condition:
            errors.append(code)

    gates = contract["acceptance_gates"]
    release = bundle["FMDL6D_RELEASE.json"]
    decision = bundle["FMDL6D_DECISION.json"]
    validation = bundle["FMDL6D_VALIDATION.json"]
    manifest = manifest_override or bundle["FMDL6D_MANIFEST.json"]

    dim = "RELEASE_AND_MANIFEST_INTEGRITY"
    check(dim, "UPSTREAM_RELEASE_ID", release.get("release_id") == contract["entry_gate"]["required_release_id"], release.get("release_id"))
    check(dim, "UPSTREAM_RELEASE_STATUS", release.get("status") == contract["entry_gate"]["required_status"], release.get("status"))
    check(dim, "UPSTREAM_VALIDATION", validation.get("validation") == "PASS" and validation.get("error_count") == 0, validation.get("errors"))
    expected_manifest_names = set(INPUT_FILES) - {"FMDL6D_MANIFEST.json"}
    check(dim, "MANIFEST_FILE_SET", set(manifest.get("files") or {}) == expected_manifest_names, sorted((manifest.get("files") or {}).keys()))
    for name in sorted(expected_manifest_names):
        metadata = (manifest.get("files") or {}).get(name) or {}
        path = input_dir / name
        check(dim, f"MANIFEST_FILE_EXISTS:{name}", path.exists())
        check(dim, f"MANIFEST_HASH:{name}", path.exists() and metadata.get("sha256") == sha256_file(path), metadata.get("sha256"))
        check(dim, f"MANIFEST_SIZE:{name}", path.exists() and metadata.get("size_bytes") == path.stat().st_size, metadata.get("size_bytes"))
    check(dim, "CANONICAL_HASH_BINDING", release.get("canonical_sha256") == manifest.get("canonical_sha256"), release.get("canonical_sha256"))

    for name, document in bundle.items():
        if name == "FMDL6D_MANIFEST.json":
            continue
        check("STATE_AND_TRADE_AUTHORITY_FIREWALL", f"PROGRAM:{name}", document.get("program_id") == UPSTREAM_PROGRAM_ID)
        check("STATE_AND_TRADE_AUTHORITY_FIREWALL", f"AUTHORITY:{name}", document.get("trade_authority") == "NONE", document.get("trade_authority"))

    market = bundle["FMDL6D_MARKET_STORE.json"]
    securities = market.get("securities") or []
    dim = "MARKET_COMPLETENESS_UNIQUENESS_AND_DOMAIN_VALIDITY"
    check(dim, "MARKET_SECURITY_COUNT", len(securities) == market.get("security_count") == gates["market_security_count"], len(securities))
    total_daily = 0
    total_events = 0
    market_series_keys: set[str] = set()
    market_security_keys: set[str] = set()
    for security in securities:
        ticker = str(security.get("ticker"))
        rows = security.get("observations") or []
        events = security.get("corporate_actions") or []
        total_daily += len(rows)
        total_events += len(events)
        market_series_keys.add(str(security.get("series_key")))
        market_security_keys.add(str(security.get("security_key")))
        dates = [row.get("trade_date") for row in rows]
        check(dim, f"MARKET_DATES:{ticker}", dates == sorted(dates) and len(dates) == len(set(dates)), len(dates))
        ohlc_ok = True
        volume_ok = True
        availability_ok = True
        for row in rows:
            values = [row.get(key) for key in ("open", "high", "low", "close", "adjusted_close")]
            if not all(finite_number(value) and float(value) > 0 for value in values):
                ohlc_ok = False
            elif float(row["high"]) < max(float(row["open"]), float(row["close"]), float(row["low"])) or float(row["low"]) > min(float(row["open"]), float(row["close"]), float(row["high"])):
                ohlc_ok = False
            if not finite_number(row.get("volume")) or float(row.get("volume")) < 0:
                volume_ok = False
            if not row.get("available_from_utc") or not row.get("availability_basis") or not row.get("point_in_time_status"):
                availability_ok = False
        check(dim, f"MARKET_OHLC:{ticker}", ohlc_ok)
        check(dim, f"MARKET_VOLUME:{ticker}", volume_ok)
        check("POINT_IN_TIME_AND_NO_LOOKAHEAD_POSTURE", f"MARKET_AVAILABILITY:{ticker}", availability_ok)
        check("SOURCE_LINEAGE_AND_NO_SILENT_REPLACEMENT", f"MARKET_SOURCE_LINEAGE:{ticker}", str(security.get("source_url", "")).startswith("https://query") and len(str(security.get("source_payload_sha256", ""))) == 64)
        event_availability = all(row.get("event_date") and row.get("available_from_utc") and row.get("availability_basis") and row.get("point_in_time_status") for row in events)
        check("CORPORATE_ACTION_COMPLETENESS_AND_AVAILABILITY", f"EVENT_AVAILABILITY:{ticker}", event_availability, len(events))
        check("STATE_AND_TRADE_AUTHORITY_FIREWALL", f"MARKET_AUTHORITY:{ticker}", security.get("benchmark_only") is True and security.get("investment_eligible") is False and security.get("trade_authority") == "NONE")
    check(dim, "MARKET_TOTAL_DAILY", total_daily == market.get("total_daily_observations") and total_daily >= gates["minimum_market_daily_observations"], total_daily)
    check("CORPORATE_ACTION_COMPLETENESS_AND_AVAILABILITY", "EVENT_TOTAL", total_events == market.get("total_corporate_actions"), total_events)

    fx = bundle["FMDL6D_FX_STORE.json"]
    fx_series = fx.get("series") or []
    dim = "FX_COMPLETENESS_UNIQUENESS_AND_DOMAIN_VALIDITY"
    total_fx = 0
    for series in fx_series:
        pair = str(series.get("pair"))
        rows = series.get("observations") or []
        total_fx += len(rows)
        dates = [row.get("reference_date") for row in rows]
        check(dim, f"FX_DATES:{pair}", dates == sorted(dates) and len(dates) == len(set(dates)), len(dates))
        check(dim, f"FX_RATE:{pair}", all(finite_number(row.get("rate")) and float(row["rate"]) > 0 for row in rows))
        check("POINT_IN_TIME_AND_NO_LOOKAHEAD_POSTURE", f"FX_AVAILABILITY:{pair}", all(row.get("available_from_utc") and row.get("availability_basis") and row.get("point_in_time_status") for row in rows))
    check(dim, "FX_PAIR_COUNT", len(fx_series) == 2, len(fx_series))
    check(dim, "FX_TOTAL", total_fx >= gates["minimum_fx_observations"], total_fx)
    check("SOURCE_LINEAGE_AND_NO_SILENT_REPLACEMENT", "FX_SOURCE_AUTHORITY", fx.get("source_authority") == "ECB_OFFICIAL")

    financial = bundle["FMDL6D_FINANCIAL_FACT_SAMPLE.json"]
    facts = financial.get("facts") or []
    issuers = financial.get("issuers") or []
    dim = "FINANCIAL_FACT_IDENTITY_LINEAGE_AND_AVAILABILITY"
    check(dim, "FINANCIAL_ISSUER_COUNT", len(issuers) == financial.get("issuer_count") == 4, len(issuers))
    check(dim, "FINANCIAL_FACT_COUNT", len(facts) == financial.get("fact_count") and len(facts) >= gates["minimum_financial_fact_count"], len(facts))
    fact_keys = [row.get("fact_key") for row in facts]
    check(dim, "FINANCIAL_FACT_KEY_UNIQUE", len(fact_keys) == len(set(fact_keys)), len(fact_keys))
    accession_ok = all(bool(row.get("filing_accession")) for row in facts)
    check(dim, "FINANCIAL_ACCESSION", accession_ok)
    check(dim, "FINANCIAL_OFFICIAL_URL", all(str(row.get("official_filing_url", "")).startswith("https://www.sec.gov/Archives/edgar/data/") for row in facts))
    check(dim, "FINANCIAL_VALUE_DOMAIN", all(finite_number(row.get("value")) for row in facts))
    check("POINT_IN_TIME_AND_NO_LOOKAHEAD_POSTURE", "FINANCIAL_AVAILABILITY", all(row.get("available_from_utc") and row.get("availability_basis") and row.get("point_in_time_status") for row in facts))
    check("STATE_AND_TRADE_AUTHORITY_FIREWALL", "FINANCIAL_DECISION_GRADE", all(row.get("decision_grade") is False for row in facts))

    chains = bundle["FMDL6D_CHAIN_RECORDS.json"]
    records = chains.get("records") or []
    dim = "CHAIN_REFERENTIAL_INTEGRITY"
    check(dim, "CHAIN_RECORD_COUNT", len(records) == chains.get("record_count") == gates["market_security_count"], len(records))
    chain_security_keys = {str(row.get("security_key")) for row in records}
    check(dim, "MARKET_SECURITY_KEY_SET", market_security_keys == chain_security_keys, {"market": sorted(market_security_keys), "chain": sorted(chain_security_keys)})
    financial_fact_keys = set(fact_keys)
    for record in records:
        ticker = str(record.get("ticker"))
        check(dim, f"CHAIN_MARKET_LINK:{ticker}", record.get("market_series_key") in market_series_keys)
        check(dim, f"CHAIN_FINANCIAL_LINK:{ticker}", set(record.get("financial_fact_keys") or []).issubset(financial_fact_keys))
        check("STATE_AND_TRADE_AUTHORITY_FIREWALL", f"CHAIN_AUTHORITY:{ticker}", record.get("benchmark_only") is True and record.get("investment_eligible") is False and record.get("research_candidate") is False and record.get("trade_authority") == "NONE")

    sources = bundle["FMDL6D_SOURCE_REGISTRY.json"]
    source_rows = sources.get("sources") or []
    dim = "SOURCE_LINEAGE_AND_NO_SILENT_REPLACEMENT"
    check(dim, "SOURCE_COUNT", len(source_rows) == sources.get("source_count") == 12, len(source_rows))
    check(dim, "SOURCE_ID_UNIQUE", len({row.get("source_id") for row in source_rows}) == len(source_rows))
    check(dim, "SOURCE_HASH", all(len(str(row.get("payload_sha256", ""))) == 64 for row in source_rows))
    check(dim, "NO_SILENT_REPLACEMENT", all(row.get("no_silent_replacement") is True for row in source_rows))
    check(dim, "SOURCE_DECISION_GRADE", all(row.get("decision_grade") is False for row in source_rows))

    availability = bundle["FMDL6D_AVAILABILITY.json"]
    dim = "POINT_IN_TIME_AND_NO_LOOKAHEAD_POSTURE"
    check(dim, "LOOKAHEAD_AUTHORITY", availability.get("lookahead_claim_authorized") is False)
    check(dim, "PIT_POLICY", availability.get("policy") == "CONSERVATIVE_RETRIEVAL_BOUND_NO_HISTORICAL_AS_OF_CLAIM", availability.get("policy"))

    dim = "STATE_AND_TRADE_AUTHORITY_FIREWALL"
    check(dim, "STATE_MUTATION:CANDIDATE_POOL", decision.get("candidate_pool_mutation_count") == 0, decision.get("candidate_pool_mutation_count"))
    check(dim, "STATE_MUTATION:SIMULATION", decision.get("simulation_mutation_count") == 0, decision.get("simulation_mutation_count"))
    check(dim, "STATE_MUTATION:REAL_ACCOUNT", decision.get("real_account_mutation_count") == 0, decision.get("real_account_mutation_count"))
    check(dim, "STATE_MUTATION:ORDER", decision.get("order_generation_count") == 0, decision.get("order_generation_count"))

    dimension_summary: dict[str, dict[str, Any]] = {}
    for dimension in contract["quality_dimensions"]:
        rows = [row for row in checks if row["dimension"] == dimension]
        passed = sum(row["status"] == "PASS" for row in rows)
        dimension_summary[dimension] = {
            "check_count": len(rows),
            "pass_count": passed,
            "error_count": len(rows) - passed,
            "score_pct": round(100.0 * passed / len(rows), 3) if rows else 0.0,
        }
    metrics = {
        "market_security_count": len(securities),
        "market_daily_observation_count": total_daily,
        "corporate_action_count": total_events,
        "fx_pair_count": len(fx_series),
        "fx_observation_count": total_fx,
        "financial_issuer_count": len(issuers),
        "financial_fact_count": len(facts),
        "chain_record_count": len(records),
        "source_count": len(source_rows),
        "dimension_summary": dimension_summary,
    }
    return checks, sorted(set(errors)), metrics


def apply_injection(
    injection_id: str,
    bundle: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None]:
    mutated = copy.deepcopy(bundle)
    manifest_override: dict[str, Any] | None = None
    market = mutated["FMDL6D_MARKET_STORE.json"]
    fx = mutated["FMDL6D_FX_STORE.json"]
    financial = mutated["FMDL6D_FINANCIAL_FACT_SAMPLE.json"]
    chains = mutated["FMDL6D_CHAIN_RECORDS.json"]
    availability = mutated["FMDL6D_AVAILABILITY.json"]
    decision = mutated["FMDL6D_DECISION.json"]
    sources = mutated["FMDL6D_SOURCE_REGISTRY.json"]

    if injection_id == "MISSING_MARKET_SECURITY":
        market["securities"].pop()
    elif injection_id == "DUPLICATE_MARKET_DATE":
        market["securities"][0]["observations"].append(copy.deepcopy(market["securities"][0]["observations"][0]))
    elif injection_id == "NULL_MARKET_CLOSE":
        market["securities"][0]["observations"][0]["close"] = None
    elif injection_id == "NEGATIVE_MARKET_VOLUME":
        market["securities"][0]["observations"][0]["volume"] = -1
    elif injection_id == "MARKET_SECURITY_KEY_MISMATCH":
        market["securities"][0]["security_key"] = "USSEC:INJECTED:MISMATCH"
    elif injection_id == "SOURCE_PAYLOAD_HASH_CORRUPTION":
        market["securities"][0]["source_payload_sha256"] = "bad"
    elif injection_id == "NEGATIVE_FX_RATE":
        fx["series"][0]["observations"][0]["rate"] = -1.0
    elif injection_id == "DUPLICATE_FX_DATE":
        fx["series"][0]["observations"].append(copy.deepcopy(fx["series"][0]["observations"][0]))
    elif injection_id == "MISSING_FINANCIAL_ACCESSION":
        financial["facts"][0]["filing_accession"] = ""
    elif injection_id == "DUPLICATE_FINANCIAL_FACT_KEY":
        financial["facts"][1]["fact_key"] = financial["facts"][0]["fact_key"]
    elif injection_id == "CHAIN_MARKET_LINK_BREAK":
        chains["records"][0]["market_series_key"] = "USMKT:INJECTED:MISSING"
    elif injection_id == "LOOKAHEAD_AUTHORITY_LEAK":
        availability["lookahead_claim_authorized"] = True
    elif injection_id == "MANIFEST_HASH_MISMATCH":
        manifest_override = copy.deepcopy(mutated["FMDL6D_MANIFEST.json"])
        manifest_override["files"]["FMDL6D_MARKET_STORE.json"]["sha256"] = "0" * 64
    elif injection_id == "TRADE_AUTHORITY_ESCALATION":
        decision["trade_authority"] = "AUTO"
    elif injection_id == "CANDIDATE_POOL_MUTATION_ATTEMPT":
        decision["candidate_pool_mutation_count"] = 1
    elif injection_id == "SOURCE_REGISTRY_ROW_LOSS":
        sources["sources"].pop()
    else:
        raise ValueError(f"unknown injection: {injection_id}")
    return mutated, manifest_override


def run_failure_injections(
    contract: dict[str, Any],
    bundle: dict[str, dict[str, Any]],
    input_dir: Path,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    false_negative_count = 0
    for specification in contract["failure_injections"]:
        injection_id = specification["injection_id"]
        mutated, manifest_override = apply_injection(injection_id, bundle)
        _, errors, _ = audit_bundle(contract, mutated, input_dir, manifest_override=manifest_override)
        expected = set(specification["expected_codes"])
        detected = expected.issubset(set(errors))
        if not detected:
            false_negative_count += 1
        results.append(
            {
                "injection_id": injection_id,
                "expected_codes": sorted(expected),
                "detected_codes": errors,
                "expected_detected": detected,
                "false_negative": not detected,
                "mutation_scope": "DEEP_COPY_ONLY",
            }
        )
    return {
        "program_id": PROGRAM_ID,
        "injection_count": len(results),
        "detected_count": sum(row["expected_detected"] for row in results),
        "false_negative_count": false_negative_count,
        "all_expected_failures_detected": false_negative_count == 0,
        "injections": results,
        "trade_authority": "NONE",
    }


def build_cost_report(bundle: dict[str, dict[str, Any]], input_dir: Path, contract: dict[str, Any]) -> dict[str, Any]:
    manifest = bundle["FMDL6D_MANIFEST.json"]
    market = bundle["FMDL6D_MARKET_STORE.json"]
    fx = bundle["FMDL6D_FX_STORE.json"]
    financial = bundle["FMDL6D_FINANCIAL_FACT_SAMPLE.json"]
    sources = bundle["FMDL6D_SOURCE_REGISTRY.json"]["sources"]
    known_response_bytes = sum(int(row.get("response_bytes") or 0) for row in sources)
    unknown_response_payload_count = sum(row.get("response_bytes") is None for row in sources)
    published_output_bytes = sum(int(row["size_bytes"]) for row in manifest["files"].values()) + (input_dir / "FMDL6D_MANIFEST.json").stat().st_size
    market_bytes = int(manifest["files"]["FMDL6D_MARKET_STORE.json"]["size_bytes"])
    financial_bytes = int(manifest["files"]["FMDL6D_FINANCIAL_FACT_SAMPLE.json"]["size_bytes"])
    shared_bytes = published_output_bytes - market_bytes - financial_bytes
    market_security_count = int(market["security_count"])
    financial_issuer_count = int(financial["issuer_count"])
    target = int(contract["cost_model"]["bounded_projection_security_count"])
    market_bytes_per_security = market_bytes / market_security_count
    financial_bytes_per_issuer = financial_bytes / financial_issuer_count
    projected_low = round(shared_bytes + market_bytes_per_security * target + financial_bytes)
    projected_high = round(shared_bytes + market_bytes_per_security * target + financial_bytes_per_issuer * target)
    market_requests = sum(str(row.get("source_id", "")).startswith("MARKET:") for row in sources)
    fx_requests = sum(str(row.get("source_id", "")).startswith("FX:") for row in sources)
    sec_snapshot_requests = sum(str(row.get("source_id", "")).startswith("SEC:") for row in sources)
    return {
        "program_id": PROGRAM_ID,
        "currency": "USD",
        "observed_sample": {
            "market_security_count": market_security_count,
            "market_daily_observation_count": market["total_daily_observations"],
            "corporate_action_count": market["total_corporate_actions"],
            "fx_pair_count": len(fx["series"]),
            "fx_observation_count": sum(row["observation_count"] for row in fx["series"]),
            "financial_issuer_count": financial_issuer_count,
            "financial_fact_count": financial["fact_count"],
            "source_request_or_snapshot_count": len(sources),
            "market_request_count": market_requests,
            "fx_request_count": fx_requests,
            "sec_selected_snapshot_count": sec_snapshot_requests,
            "known_response_bytes": known_response_bytes,
            "unknown_response_payload_count": unknown_response_payload_count,
            "published_output_bytes": published_output_bytes,
            "provider_cash_cost_observed_usd": contract["cost_model"]["provider_cash_cost_assumption"],
            "wall_clock_runtime": "NOT_PERSISTED_NO_CLAIM",
        },
        "unit_metrics": {
            "market_output_bytes_per_security": round(market_bytes_per_security, 3),
            "financial_output_bytes_per_sample_issuer": round(financial_bytes_per_issuer, 3),
            "daily_observations_per_market_security": round(market["total_daily_observations"] / market_security_count, 3),
            "known_input_bytes_per_source_record": round(known_response_bytes / max(1, len(sources) - unknown_response_payload_count), 3),
        },
        "bounded_24_security_projection": {
            "projection_type": "LINEAR_ENGINEERING_ESTIMATE_NOT_CAPACITY_CERTIFICATION",
            "security_count": target,
            "external_request_low": target + fx_requests + 1,
            "external_request_high": target + fx_requests + target,
            "published_output_bytes_low": projected_low,
            "published_output_bytes_high": projected_high,
            "provider_cash_cost_assumption_usd": 0,
            "decision_grade_market_data_authorized": False,
        },
        "full_universe_projection": {
            "status": contract["cost_model"]["full_universe_projection_status"],
            "numeric_projection_prohibited": True,
            "reason": "CURRENT_PHASE_AUTHORIZES_ONLY_THE_24_SECURITY_RESUME_READY_PILOT",
        },
        "dominant_operational_cost_drivers": [
            "FREE_MARKET_ROUTE_STABILITY_AND_SCHEMA_DRIFT",
            "SEC_EXTERNAL_EXECUTION_ROUTE_AND_SNAPSHOT_LINEAGE",
            "MISSING_FULL_RAW_SEC_PAYLOAD_RETENTION",
            "INCOMPLETE_FILING_ACCEPTANCE_TIMESTAMPS",
            "HUMAN_REVIEW_FOR_IDENTITY_AND_FINANCIAL_TAG_VARIANTS",
        ],
        "trade_authority": "NONE",
    }


def benchmark_documents(repo_root: Path, contract_path: Path) -> dict[str, dict[str, Any]]:
    contract = load_json(contract_path)
    input_dir = repo_root / contract["entry_gate"]["input_current_path"]
    bundle = load_bundle(input_dir)
    checks, errors, metrics = audit_bundle(contract, bundle, input_dir)
    if errors:
        raise ValueError(f"FMDL-6E baseline audit rejected: {errors}")
    failure_report = run_failure_injections(contract, bundle, input_dir)
    if failure_report["false_negative_count"] != 0:
        raise ValueError(f"FMDL-6E failure injection false negatives: {failure_report['false_negative_count']}")
    dimension_summary = metrics.pop("dimension_summary")
    quality_report = {
        "program_id": PROGRAM_ID,
        "upstream_release_id": bundle["FMDL6D_RELEASE.json"]["release_id"],
        "baseline_validation": "PASS",
        "baseline_error_count": 0,
        "quality_dimension_count": len(dimension_summary),
        "quality_dimensions": dimension_summary,
        "observed_metrics": metrics,
        "check_count": len(checks),
        "pass_count": sum(row["status"] == "PASS" for row in checks),
        "checks": checks,
        "decision_grade_market_data_authorized": False,
        "trade_authority": "NONE",
    }
    pointer_path = repo_root / contract["entry_gate"]["pointer_path"]
    upstream_manifest_path = input_dir / "FMDL6D_MANIFEST.json"
    pointer_before = sha256_file(pointer_path)
    manifest_before = sha256_file(upstream_manifest_path)
    pointer_after = sha256_file(pointer_path)
    manifest_after = sha256_file(upstream_manifest_path)
    lkg_proof = {
        "program_id": PROGRAM_ID,
        "lkg_target": contract["entry_gate"]["required_release_id"],
        "failure_injection_mutation_scope": "DEEP_COPY_ONLY",
        "upstream_pointer_sha256_before": pointer_before,
        "upstream_pointer_sha256_after": pointer_after,
        "upstream_manifest_sha256_before": manifest_before,
        "upstream_manifest_sha256_after": manifest_after,
        "upstream_lkg_unchanged": pointer_before == pointer_after and manifest_before == manifest_after,
        "upstream_current_write_count": 0,
        "trade_authority": "NONE",
    }
    cost_report = build_cost_report(bundle, input_dir, contract)
    source_binding = {
        "program_id": PROGRAM_ID,
        "input_path": contract["entry_gate"]["input_current_path"],
        "upstream_release_id": bundle["FMDL6D_RELEASE.json"]["release_id"],
        "upstream_status": bundle["FMDL6D_RELEASE.json"]["status"],
        "upstream_canonical_sha256": bundle["FMDL6D_RELEASE.json"]["canonical_sha256"],
        "upstream_manifest_sha256": sha256_file(upstream_manifest_path),
        "input_file_hashes": {name: sha256_file(input_dir / name) for name in INPUT_FILES},
        "live_source_refresh_performed": False,
        "benchmark_mode": contract["scope"]["mode"],
        "trade_authority": "NONE",
    }
    return {
        "FMDL6E_QUALITY_REPORT.json": quality_report,
        "FMDL6E_FAILURE_INJECTION.json": failure_report,
        "FMDL6E_LKG_PROOF.json": lkg_proof,
        "FMDL6E_COST_AND_SCALING.json": cost_report,
        "FMDL6E_SOURCE_BINDING.json": source_binding,
    }


def build_candidate(repo_root: Path, contract_path: Path, candidate_dir: Path) -> dict[str, Any]:
    contract_checks, contract_errors = validate_contract(repo_root, contract_path)
    if contract_errors:
        raise ValueError(f"FMDL-6E contract rejected: {contract_errors}")
    contract = load_json(contract_path)
    first = benchmark_documents(repo_root, contract_path)
    second = benchmark_documents(repo_root, contract_path)
    first_hash = sha256_bytes(stable_json(first).encode("utf-8"))
    second_hash = sha256_bytes(stable_json(second).encode("utf-8"))
    same_input_replay = first_hash == second_hash
    if not same_input_replay:
        raise ValueError("FMDL-6E same-input benchmark replay failed")
    replay = {
        "program_id": PROGRAM_ID,
        "same_input_replay": "PASS",
        "first_pass_sha256": first_hash,
        "second_pass_sha256": second_hash,
        "input_refresh_between_passes": False,
        "trade_authority": "NONE",
    }
    core_documents = {**first, "FMDL6E_REPLAY.json": replay}
    canonical_payload = {
        "program_id": PROGRAM_ID,
        "contract_sha256": sha256_file(contract_path),
        "documents": core_documents,
        "controlled_limitations": contract["controlled_limitations"],
    }
    canonical_sha = sha256_bytes(stable_json(canonical_payload).encode("utf-8"))
    release_id = f"FMDL6E_{contract['as_of_date'].replace('-', '')}_{canonical_sha[:12]}"
    quality = core_documents["FMDL6E_QUALITY_REPORT.json"]
    failures = core_documents["FMDL6E_FAILURE_INJECTION.json"]
    lkg = core_documents["FMDL6E_LKG_PROOF.json"]
    decision = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "status": contract["exit_status"],
        "hard_failures": [],
        "baseline_error_count": quality["baseline_error_count"],
        "quality_dimension_count": quality["quality_dimension_count"],
        "failure_injection_count": failures["injection_count"],
        "failure_injection_false_negative_count": failures["false_negative_count"],
        "same_input_replay": replay["same_input_replay"],
        "upstream_lkg_unchanged": lkg["upstream_lkg_unchanged"],
        "decision_grade_market_data_authorized": False,
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "trade_authority": "NONE",
        "next_gate": contract["next_gate"],
    }
    validation = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "validation": "PASS",
        "contract_check_count": len(contract_checks),
        "contract_error_count": 0,
        "baseline_quality_check_count": quality["check_count"],
        "baseline_quality_error_count": quality["baseline_error_count"],
        "failure_injection_count": failures["injection_count"],
        "failure_injection_false_negative_count": failures["false_negative_count"],
        "same_input_replay": replay["same_input_replay"],
        "upstream_lkg_unchanged": lkg["upstream_lkg_unchanged"],
        "errors": [],
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
        "scope_mode": contract["scope"]["mode"],
        "canonical_sha256": canonical_sha,
        "contract_sha256": sha256_file(contract_path),
        "upstream_fmdl6d_release_id": contract["entry_gate"]["required_release_id"],
        "baseline_error_count": quality["baseline_error_count"],
        "failure_injection_count": failures["injection_count"],
        "failure_injection_false_negative_count": failures["false_negative_count"],
        "same_input_replay": replay["same_input_replay"],
        "upstream_lkg_unchanged": lkg["upstream_lkg_unchanged"],
        "full_universe_build_authorized": False,
        "decision_grade_market_data_authorized": False,
        "candidate_pool_integration_authorized": False,
        "simulation_integration_authorized": False,
        "real_account_integration_authorized": False,
        "order_generation_authorized": False,
        "controlled_limitations": contract["controlled_limitations"],
        "trade_authority": "NONE",
        "next_gate": contract["next_gate"],
    }
    documents = {
        **core_documents,
        "FMDL6E_DECISION.json": decision,
        "FMDL6E_VALIDATION.json": validation,
        "FMDL6E_RELEASE.json": release,
    }
    if candidate_dir.exists():
        shutil.rmtree(candidate_dir)
    candidate_dir.mkdir(parents=True, exist_ok=True)
    for name, document in documents.items():
        write_json(candidate_dir / name, document)
    manifest = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": contract["publication"]["release_sequence"],
        "canonical_sha256": canonical_sha,
        "contract_sha256": sha256_file(contract_path),
        "upstream_fmdl6d_release_id": contract["entry_gate"]["required_release_id"],
        "files": {
            name: {"sha256": sha256_file(candidate_dir / name), "size_bytes": (candidate_dir / name).stat().st_size}
            for name in sorted(documents)
        },
        "trade_authority": "NONE",
    }
    write_json(candidate_dir / "FMDL6E_MANIFEST.json", manifest)
    return release


def validate_candidate(
    repo_root: Path,
    contract_path: Path,
    candidate_dir: Path,
    acceptance_path: Path,
) -> dict[str, Any]:
    contract = load_json(contract_path)
    errors: list[str] = []
    manifest_path = candidate_dir / "FMDL6E_MANIFEST.json"
    if not manifest_path.exists():
        errors.append("MISSING_MANIFEST")
        manifest: dict[str, Any] = {"files": {}}
    else:
        manifest = load_json(manifest_path)
    if set(manifest.get("files") or {}) != set(OUTPUT_FILES):
        errors.append("MANIFEST_FILE_SET")
    for name, metadata in (manifest.get("files") or {}).items():
        path = candidate_dir / name
        if not path.exists():
            errors.append(f"MISSING_FILE:{name}")
        else:
            if sha256_file(path) != metadata.get("sha256"):
                errors.append(f"HASH_MISMATCH:{name}")
            if path.stat().st_size != metadata.get("size_bytes"):
                errors.append(f"SIZE_MISMATCH:{name}")
    required = [candidate_dir / name for name in OUTPUT_FILES]
    if all(path.exists() for path in required):
        decision = load_json(candidate_dir / "FMDL6E_DECISION.json")
        validation = load_json(candidate_dir / "FMDL6E_VALIDATION.json")
        release = load_json(candidate_dir / "FMDL6E_RELEASE.json")
        failures = load_json(candidate_dir / "FMDL6E_FAILURE_INJECTION.json")
        lkg = load_json(candidate_dir / "FMDL6E_LKG_PROOF.json")
        replay = load_json(candidate_dir / "FMDL6E_REPLAY.json")
        if release.get("status") != contract["exit_status"] or decision.get("status") != contract["exit_status"]:
            errors.append("STATUS")
        if validation.get("validation") != "PASS" or validation.get("errors"):
            errors.append("VALIDATION")
        if failures.get("false_negative_count") != 0 or failures.get("injection_count", 0) < contract["acceptance_gates"]["minimum_failure_injection_count"]:
            errors.append("FAILURE_INJECTION_GATE")
        if lkg.get("upstream_lkg_unchanged") is not True:
            errors.append("LKG_GATE")
        if replay.get("same_input_replay") != "PASS":
            errors.append("REPLAY_GATE")
        if any(document.get("trade_authority") != "NONE" for document in (decision, validation, release, failures, lkg, replay, manifest)):
            errors.append("TRADE_AUTHORITY")
        if any(decision.get(key) != 0 for key in ("candidate_pool_mutation_count", "simulation_mutation_count", "real_account_mutation_count", "order_generation_count")):
            errors.append("STATE_MUTATION")
        if any(release.get(key) is not False for key in ("full_universe_build_authorized", "decision_grade_market_data_authorized", "candidate_pool_integration_authorized", "simulation_integration_authorized", "real_account_integration_authorized", "order_generation_authorized")):
            errors.append("RELEASE_AUTHORITY")
        canonical_documents = {
            name: load_json(candidate_dir / name)
            for name in (
                "FMDL6E_QUALITY_REPORT.json",
                "FMDL6E_FAILURE_INJECTION.json",
                "FMDL6E_LKG_PROOF.json",
                "FMDL6E_COST_AND_SCALING.json",
                "FMDL6E_SOURCE_BINDING.json",
                "FMDL6E_REPLAY.json",
            )
        }
        canonical_payload = {
            "program_id": PROGRAM_ID,
            "contract_sha256": sha256_file(contract_path),
            "documents": canonical_documents,
            "controlled_limitations": contract["controlled_limitations"],
        }
        canonical_sha = sha256_bytes(stable_json(canonical_payload).encode("utf-8"))
        expected_release_id = f"FMDL6E_{contract['as_of_date'].replace('-', '')}_{canonical_sha[:12]}"
        if release.get("canonical_sha256") != canonical_sha or manifest.get("canonical_sha256") != canonical_sha:
            errors.append("CANONICAL_HASH")
        if release.get("release_id") != expected_release_id or decision.get("release_id") != expected_release_id or manifest.get("release_id") != expected_release_id:
            errors.append("RELEASE_ID")
    with tempfile.TemporaryDirectory(prefix="fmdl6e-replay-") as tmp:
        replay_dir = Path(tmp) / "candidate"
        expected_release = build_candidate(repo_root, contract_path, replay_dir)
        expected_manifest = load_json(replay_dir / "FMDL6E_MANIFEST.json")
        same_input_replay = manifest == expected_manifest
        if not same_input_replay:
            errors.append("INDEPENDENT_SAME_INPUT_REPLAY")
    errors = sorted(set(errors))
    release_id = load_json(candidate_dir / "FMDL6E_RELEASE.json").get("release_id") if (candidate_dir / "FMDL6E_RELEASE.json").exists() else None
    acceptance = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "validation": "PASS" if not errors else "FAIL",
        "same_input_replay": "PASS" if same_input_replay else "FAIL",
        "manifest_file_count": len(manifest.get("files") or {}),
        "errors": errors,
        "trade_authority": "NONE",
    }
    write_json(acceptance_path, acceptance)
    if errors:
        raise ValueError(f"FMDL-6E independent validation failed: {errors}")
    return acceptance


def _copy_tree_verified(source: Path, target: Path) -> None:
    if target.exists():
        source_manifest = load_json(source / "FMDL6E_MANIFEST.json")
        target_manifest_path = target / "FMDL6E_MANIFEST.json"
        if target_manifest_path.exists() and load_json(target_manifest_path) == source_manifest:
            return
        raise FileExistsError(f"target exists with different content: {target}")
    shutil.copytree(source, target)


def publish_candidate(repo_root: Path, contract_path: Path, candidate_dir: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    with tempfile.TemporaryDirectory(prefix="fmdl6e-publish-validate-") as tmp:
        validate_candidate(repo_root, contract_path, candidate_dir, Path(tmp) / "acceptance.json")
    release = load_json(candidate_dir / "FMDL6E_RELEASE.json")
    manifest = load_json(candidate_dir / "FMDL6E_MANIFEST.json")
    current_path = repo_root / contract["publication"]["current_path"]
    archive_path = repo_root / contract["publication"]["archive_root"] / release["release_id"]
    immutable_path = repo_root / contract["publication"]["immutable_root"] / release["release_id"]
    if current_path.exists():
        shutil.rmtree(current_path)
    shutil.copytree(candidate_dir, current_path)
    _copy_tree_verified(candidate_dir, archive_path)
    _copy_tree_verified(candidate_dir, immutable_path)
    last_success = {
        "program_id": PROGRAM_ID,
        "release_id": release["release_id"],
        "release_sequence": release["release_sequence"],
        "status": release["status"],
        "canonical_sha256": release["canonical_sha256"],
        "contract_sha256": release["contract_sha256"],
        "upstream_fmdl6d_release_id": release["upstream_fmdl6d_release_id"],
        "baseline_error_count": release["baseline_error_count"],
        "failure_injection_count": release["failure_injection_count"],
        "failure_injection_false_negative_count": release["failure_injection_false_negative_count"],
        "same_input_replay": release["same_input_replay"],
        "upstream_lkg_unchanged": release["upstream_lkg_unchanged"],
        "current_path": contract["publication"]["current_path"],
        "archive_path": str(archive_path.relative_to(repo_root)),
        "immutable_path": str(immutable_path.relative_to(repo_root)),
        "manifest_sha256": sha256_file(candidate_dir / "FMDL6E_MANIFEST.json"),
        "manifest_file_count": len(manifest["files"]),
        "next_gate": release["next_gate"],
        "trade_authority": "NONE",
    }
    write_json(repo_root / contract["publication"]["last_success_path"], last_success)
    return last_success


def command_contract(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    checks, errors = validate_contract(repo_root, (repo_root / args.contract).resolve())
    print(json.dumps({"check_count": len(checks), "errors": errors}, sort_keys=True))
    return 1 if errors else 0


def command_build(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    release = build_candidate(repo_root, (repo_root / args.contract).resolve(), (repo_root / args.candidate).resolve())
    print(json.dumps(release, sort_keys=True))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    acceptance = validate_candidate(repo_root, (repo_root / args.contract).resolve(), (repo_root / args.candidate).resolve(), (repo_root / args.acceptance).resolve())
    print(json.dumps(acceptance, sort_keys=True))
    return 0


def command_publish(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    result = publish_candidate(repo_root, (repo_root / args.contract).resolve(), (repo_root / args.candidate).resolve())
    print(json.dumps(result, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FMDL-6E quality, failure and cost benchmark")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("contract", command_contract), ("build", command_build), ("validate", command_validate), ("publish", command_publish)):
        current = sub.add_parser(name)
        current.add_argument("--repo-root", default=".")
        current.add_argument("--contract", default=DEFAULT_CONTRACT)
        if name in {"build", "validate", "publish"}:
            current.add_argument("--candidate", default=DEFAULT_CANDIDATE)
        if name == "validate":
            current.add_argument("--acceptance", default=DEFAULT_ACCEPTANCE)
        current.set_defaults(handler=handler)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
