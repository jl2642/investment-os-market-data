from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fmdl6b_core import (
    CONTRACT_DEFAULT,
    PROGRAM_ID,
    REQUIRED_CANDIDATE_FILES,
    load_json,
    sha256_bytes,
    sha256_file,
    stable_json,
    write_json,
)
from fmdl6b_fetch import fetch_live


def normalize_observations(contract: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    observations = raw.get("observations", [])
    by_id = {row["route_id"]: row for row in observations}
    successful = {route_id for route_id, row in by_id.items() if row.get("access_status") == "SUCCESS"}
    hard_failures: list[str] = []
    controlled_limitations: list[str] = []

    for route_id in contract["capability_acceptance"]["required_official_route_ids"]:
        if route_id not in successful:
            hard_failures.append(f"REQUIRED_OFFICIAL_ROUTE_FAILED:{route_id}")

    directory_ok = bool(successful & {
        "NASDAQ_TRADER_NASDAQLISTED",
        "NASDAQ_TRADER_OTHERLISTED",
        "SEC_COMPANY_TICKERS_EXCHANGE_SUPPORT",
    })
    daily_ok = bool(successful & {
        "STOOQ_AAPL_DAILY",
        "YAHOO_QUERY1_AAPL_CHART_EVENTS",
        "YAHOO_QUERY2_AAPL_CHART_EVENTS",
    })
    corporate_action_ok = any(
        route_id in successful and "DIVIDEND_OR_SPLIT_EVENTS" in by_id[route_id].get("capabilities", [])
        for route_id in ("YAHOO_QUERY1_AAPL_CHART_EVENTS", "YAHOO_QUERY2_AAPL_CHART_EVENTS")
    )
    fx_ok = bool(successful & {"ECB_REFERENCE_FX", "FRANKFURTER_USD_CNY_HKD"})

    if not directory_ok:
        hard_failures.append("NO_CURRENT_SECURITY_DIRECTORY_ROUTE")
    if not daily_ok:
        hard_failures.append("NO_DAILY_OHLCV_ROUTE")
    if not corporate_action_ok:
        hard_failures.append("NO_CORPORATE_ACTION_EVENT_ROUTE")
    if not fx_ok:
        hard_failures.append("NO_USD_CNY_HKD_FX_ROUTE")
    if not all(by_id[route_id].get("github_actions_compatibility") for route_id in successful):
        hard_failures.append("SUCCESS_ROUTE_NOT_GITHUB_ACTIONS_COMPATIBLE")

    if not successful & {"NASDAQ_TRADER_NASDAQLISTED", "NASDAQ_TRADER_OTHERLISTED"} and "SEC_COMPANY_TICKERS_EXCHANGE_SUPPORT" in successful:
        controlled_limitations.append("NASDAQ_CURRENT_DIRECTORY_UNAVAILABLE_USING_SEC_CURRENT_SUPPORT")
    if "ECB_REFERENCE_FX" not in successful and "FRANKFURTER_USD_CNY_HKD" in successful:
        controlled_limitations.append("ECB_FX_UNAVAILABLE_USING_FREE_FALLBACK")
    controlled_limitations.extend([
        "FREE_MARKET_DATA_PILOT_ONLY_NOT_DECISION_GRADE",
        "CURRENT_DIRECTORY_DOES_NOT_ESTABLISH_HISTORICAL_MEMBERSHIP",
        "COMPANY_FACTS_NORMALIZATION_DEFERRED_TO_FMDL6D_AND_FMDL6E",
    ])

    routes = [
        {
            **row,
            "route_decision": "ACCEPTED_FOR_PILOT" if row.get("access_status") == "SUCCESS" else "UNAVAILABLE_OR_QUARANTINED",
        }
        for row in observations
    ]
    return {
        "program_id": PROGRAM_ID,
        "contract_sha256": raw.get("contract_sha256"),
        "raw_observation_sha256": sha256_bytes(stable_json(raw).encode("utf-8")),
        "benchmark_started_at_utc": raw.get("benchmark_started_at_utc"),
        "benchmark_completed_at_utc": raw.get("benchmark_completed_at_utc"),
        "environment": raw.get("environment"),
        "route_count": len(routes),
        "route_success_count": len(successful),
        "route_failure_count": len(routes) - len(successful),
        "capability_summary": {
            "sec_identity_and_submissions": all(route_id in successful for route_id in ("SEC_COMPANY_TICKERS_EXCHANGE", "SEC_SUBMISSIONS_AAPL")),
            "sec_companyfacts": "SEC_COMPANYFACTS_AAPL" in successful,
            "current_security_directory": directory_ok,
            "daily_ohlcv": daily_ok,
            "corporate_actions": corporate_action_ok,
            "usd_cny_hkd_fx": fx_ok,
        },
        "controlled_limitations": sorted(set(controlled_limitations)),
        "hard_failures": sorted(set(hard_failures)),
        "routes": routes,
        "trade_authority": "NONE",
    }


def canonical_payload(contract: dict[str, Any], normalized: dict[str, Any]) -> dict[str, Any]:
    return {
        "program_id": PROGRAM_ID,
        "entry_release_id": contract["entry_gate"]["required_release_id"],
        "contract_sha256": normalized["contract_sha256"],
        "raw_observation_sha256": normalized["raw_observation_sha256"],
        "capability_summary": normalized["capability_summary"],
        "route_decisions": [
            (row["route_id"], row["access_status"], row["payload_sha256"], row["route_decision"])
            for row in normalized["routes"]
        ],
        "controlled_limitations": normalized["controlled_limitations"],
        "next_gate": contract["next_gate"],
        "trade_authority": "NONE",
    }


def build_candidate(repo_root: Path, contract_path: Path, raw_path: Path, candidate_root: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    raw = load_json(raw_path)
    if raw.get("contract_sha256") != sha256_file(contract_path):
        raise ValueError("raw observations contract mismatch")
    normalized = normalize_observations(contract, raw)
    if normalized["hard_failures"]:
        raise ValueError(f"live benchmark failed: {normalized['hard_failures']}")
    if candidate_root.exists():
        shutil.rmtree(candidate_root)
    candidate_root.mkdir(parents=True, exist_ok=True)

    canonical_sha = sha256_bytes(stable_json(canonical_payload(contract, normalized)).encode("utf-8"))
    release_id = f"FMDL6B_{contract['as_of_date'].replace('-', '')}_{canonical_sha[:12]}"
    decision = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "status": contract["exit_status"],
        "hard_failures": [],
        "controlled_limitations": normalized["controlled_limitations"],
        "route_count": normalized["route_count"],
        "route_success_count": normalized["route_success_count"],
        "route_failure_count": normalized["route_failure_count"],
        "capability_summary": normalized["capability_summary"],
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "decision_grade_market_data_authorized": False,
        "next_gate": contract["next_gate"],
        "trade_authority": "NONE",
    }
    validation = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "validation": "PASS",
        "error_count": 0,
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
        "canonical_sha256": canonical_sha,
        "contract_sha256": normalized["contract_sha256"],
        "raw_observation_sha256": normalized["raw_observation_sha256"],
        "scope_mode": contract["scope"]["mode"],
        "route_count": normalized["route_count"],
        "route_success_count": normalized["route_success_count"],
        "decision_grade_market_data_authorized": False,
        "candidate_pool_integration_authorized": False,
        "simulation_integration_authorized": False,
        "real_account_integration_authorized": False,
        "order_generation_authorized": False,
        "next_gate": contract["next_gate"],
        "trade_authority": "NONE",
    }
    registry = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "interfaces": contract["interfaces"],
        "accepted_routes": [row for row in normalized["routes"] if row["route_decision"] == "ACCEPTED_FOR_PILOT"],
        "unavailable_routes": [row for row in normalized["routes"] if row["route_decision"] != "ACCEPTED_FOR_PILOT"],
        "decision_grade_claimed": False,
        "trade_authority": "NONE",
    }
    failure = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "taxonomy": contract["failure_taxonomy"],
        "observed_failures": [
            {"route_id": row["route_id"], "failure_mode": row["failure_mode"], "error": row["error"]}
            for row in normalized["routes"] if row["access_status"] != "SUCCESS"
        ],
        "failed_route_may_replace_last_known_good": False,
        "trade_authority": "NONE",
    }

    write_json(candidate_root / "FMDL6B_RAW_OBSERVATIONS.json", raw)
    write_json(candidate_root / "FMDL6B_INTERFACE_BENCHMARK.json", normalized)
    write_json(candidate_root / "FMDL6B_SOURCE_REGISTRY.json", registry)
    write_json(candidate_root / "FMDL6B_FAILURE_TAXONOMY.json", failure)
    write_json(candidate_root / "FMDL6B_DECISION.json", decision)
    write_json(candidate_root / "FMDL6B_VALIDATION.json", validation)
    write_json(candidate_root / "FMDL6B_RELEASE.json", release)
    files = {
        path.name: {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
        for path in sorted(candidate_root.iterdir())
        if path.is_file() and path.name != "FMDL6B_MANIFEST.json"
    }
    write_json(candidate_root / "FMDL6B_MANIFEST.json", {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": release["release_sequence"],
        "canonical_sha256": canonical_sha,
        "contract_sha256": normalized["contract_sha256"],
        "raw_observation_sha256": normalized["raw_observation_sha256"],
        "files": files,
        "trade_authority": "NONE",
    })
    return release


def independent_validate(repo_root: Path, contract_path: Path, raw_path: Path, candidate_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    found = {path.name for path in candidate_root.iterdir() if path.is_file()}
    if found != REQUIRED_CANDIDATE_FILES:
        errors.append(f"FILE_SET:{sorted(found)}")
    release = load_json(candidate_root / "FMDL6B_RELEASE.json")
    decision = load_json(candidate_root / "FMDL6B_DECISION.json")
    manifest = load_json(candidate_root / "FMDL6B_MANIFEST.json")
    if release.get("status") != "FMDL6B_SOURCE_INTERFACE_AND_ACCESS_BENCHMARK_ACCEPTED":
        errors.append("STATUS")
    if decision.get("hard_failures"):
        errors.append("HARD_FAILURES")
    if decision.get("decision_grade_market_data_authorized") is not False:
        errors.append("PREMATURE_AUTHORITY")
    mutation_keys = ("candidate_pool_mutation_count", "simulation_mutation_count", "real_account_mutation_count", "order_generation_count")
    if any(decision.get(key) != 0 for key in mutation_keys):
        errors.append("STATE_MUTATION")
    if release.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")

    expected = REQUIRED_CANDIDATE_FILES - {"FMDL6B_MANIFEST.json"}
    if set(manifest.get("files", {})) != expected:
        errors.append("MANIFEST_SET")
    for name in expected:
        row = manifest.get("files", {}).get(name, {})
        path = candidate_root / name
        if row.get("sha256") != sha256_file(path):
            errors.append(f"HASH:{name}")
        if row.get("size_bytes") != path.stat().st_size:
            errors.append(f"SIZE:{name}")

    replay_errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="fmdl6b_replay_") as temp:
        replay = Path(temp) / "candidate"
        build_candidate(repo_root, contract_path, raw_path, replay)
        for name in REQUIRED_CANDIDATE_FILES:
            if sha256_file(candidate_root / name) != sha256_file(replay / name):
                replay_errors.append(f"REPLAY:{name}")
    errors.extend(replay_errors)
    return {
        "program_id": PROGRAM_ID,
        "release_id": release.get("release_id"),
        "canonical_sha256": release.get("canonical_sha256"),
        "validation": "PASS" if not errors else "FAIL",
        "same_input_replay": "PASS" if not replay_errors else "FAIL",
        "error_count": len(errors),
        "errors": errors,
        "trade_authority": "NONE",
    }


def publish_candidate(repo_root: Path, contract_path: Path, candidate_root: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    release = load_json(candidate_root / "FMDL6B_RELEASE.json")
    release_id = release["release_id"]
    targets = [
        repo_root / contract["publication"]["current_root"],
        repo_root / contract["publication"]["release_root"] / release_id,
        repo_root / contract["publication"]["archive_root"] / release_id,
    ]
    for target in targets:
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
        "raw_observation_sha256": release["raw_observation_sha256"],
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
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("fetch", "build", "validate", "publish"):
        child = subparsers.add_parser(command)
        child.add_argument("--repo-root", default=".")
        child.add_argument("--contract", default=CONTRACT_DEFAULT)
        child.add_argument("--raw", default="outputs/fmdl6b/work/FMDL6B_RAW_OBSERVATIONS.json")
        child.add_argument("--candidate", default="outputs/fmdl6b/candidate")
        child.add_argument("--acceptance", default="outputs/fmdl6b/acceptance/FMDL6B_INDEPENDENT_ACCEPTANCE.json")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    contract_path = repo_root / args.contract
    raw_path = repo_root / args.raw
    candidate_root = repo_root / args.candidate
    if args.command == "fetch":
        result = fetch_live(repo_root, contract_path, raw_path)
    elif args.command == "build":
        result = build_candidate(repo_root, contract_path, raw_path, candidate_root)
    elif args.command == "validate":
        result = independent_validate(repo_root, contract_path, raw_path, candidate_root)
        write_json(repo_root / args.acceptance, result)
    else:
        result = publish_candidate(repo_root, contract_path, candidate_root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if args.command == "validate" and result["validation"] != "PASS":
        return 1
    return 0
