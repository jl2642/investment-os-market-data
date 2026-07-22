from __future__ import annotations

from pathlib import Path
from typing import Any

from fmdl6b_core import PROGRAM_ID, load_json, sha256_bytes, sha256_file, stable_json, write_json

SEC_REQUIRED_ROUTES = (
    "SEC_COMPANY_TICKERS_EXCHANGE",
    "SEC_SUBMISSIONS_AAPL",
    "SEC_COMPANYFACTS_AAPL",
)


def _is_repeatable_sec_hosted_runner_block(row: dict[str, Any] | None) -> bool:
    return bool(
        row
        and row.get("access_status") == "FAIL"
        and row.get("http_status") == 403
        and row.get("failure_mode") == "HTTP_4XX_AUTH_OR_BLOCK"
    )


def controlled_normalize_observations(contract: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    observations = raw.get("observations", [])
    by_id = {row["route_id"]: row for row in observations}
    successful = {route_id for route_id, row in by_id.items() if row.get("access_status") == "SUCCESS"}
    hard_failures: list[str] = []
    controlled_limitations: list[str] = []

    policy = contract["capability_acceptance"]
    sec_hosted_runner_blocked = (
        raw.get("environment") == "GITHUB_ACTIONS"
        and policy.get("github_hosted_sec_403_controlled_limitation_allowed") is True
        and all(_is_repeatable_sec_hosted_runner_block(by_id.get(route_id)) for route_id in SEC_REQUIRED_ROUTES)
    )
    for route_id in policy["required_official_route_ids"]:
        if route_id not in successful and not sec_hosted_runner_blocked:
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

    if sec_hosted_runner_blocked:
        controlled_limitations.extend([
            "SEC_OFFICIAL_APIS_RETURN_403_ON_GITHUB_HOSTED_RUNNER",
            "SEC_OFFICIAL_DATA_REQUIRES_CHATGPT_WEB_LOCAL_OR_SELF_HOSTED_EXECUTION_ROUTE",
            "SEC_DATA_MUST_ENTER_FMDL6C_AND_FMDL6D_AS_HASHED_OFFICIAL_SNAPSHOT_WITH_SOURCE_URL_AND_RETRIEVAL_TIME",
        ])
    if not successful & {"NASDAQ_TRADER_NASDAQLISTED", "NASDAQ_TRADER_OTHERLISTED"} and "SEC_COMPANY_TICKERS_EXCHANGE_SUPPORT" in successful:
        controlled_limitations.append("NASDAQ_CURRENT_DIRECTORY_UNAVAILABLE_USING_SEC_CURRENT_SUPPORT")
    if "ECB_REFERENCE_FX" not in successful and "FRANKFURTER_USD_CNY_HKD" in successful:
        controlled_limitations.append("ECB_FX_UNAVAILABLE_USING_FREE_FALLBACK")
    controlled_limitations.extend([
        "FREE_MARKET_DATA_PILOT_ONLY_NOT_DECISION_GRADE",
        "CURRENT_DIRECTORY_DOES_NOT_ESTABLISH_HISTORICAL_MEMBERSHIP",
        "COMPANY_FACTS_NORMALIZATION_DEFERRED_TO_FMDL6D_AND_FMDL6E",
    ])

    execution_route_decision = {
        "github_hosted_actions": "UNAVAILABLE_FOR_SEC_OFFICIAL_APIS_403" if sec_hosted_runner_blocked else "AVAILABLE_OR_NOT_CONCLUSIVELY_BLOCKED",
        "sec_official_primary": "REQUIRED_AND_RETAINED",
        "approved_pilot_execution_route": "CHATGPT_WEB_OR_LOCAL_OR_SELF_HOSTED_RUNNER" if sec_hosted_runner_blocked else "GITHUB_ACTIONS",
        "approved_external_execution_routes": policy.get("approved_external_execution_routes", []),
        "third_party_sec_proxy_authorized": policy.get("third_party_sec_proxy_authorized", False),
        "official_snapshot_requirements": policy.get("official_snapshot_requirements", []),
        "official_snapshot_hash_and_lineage_required": True,
    }
    routes = [
        {
            **row,
            "route_decision": (
                "ACCEPTED_FOR_PILOT"
                if row.get("access_status") == "SUCCESS"
                else "OFFICIAL_EXTERNAL_EXECUTION_REQUIRED"
                if sec_hosted_runner_blocked and row.get("route_id") in SEC_REQUIRED_ROUTES
                else "UNAVAILABLE_OR_QUARANTINED"
            ),
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
            "sec_identity_and_submissions": all(route_id in successful for route_id in SEC_REQUIRED_ROUTES[:2]),
            "sec_companyfacts": SEC_REQUIRED_ROUTES[2] in successful,
            "current_security_directory": directory_ok,
            "daily_ohlcv": daily_ok,
            "corporate_actions": corporate_action_ok,
            "usd_cny_hkd_fx": fx_ok,
        },
        "execution_route_decision": execution_route_decision,
        "controlled_limitations": sorted(set(controlled_limitations)),
        "hard_failures": sorted(set(hard_failures)),
        "routes": routes,
        "trade_authority": "NONE",
    }


def controlled_canonical_payload(contract: dict[str, Any], normalized: dict[str, Any]) -> dict[str, Any]:
    return {
        "program_id": PROGRAM_ID,
        "entry_release_id": contract["entry_gate"]["required_release_id"],
        "contract_sha256": normalized["contract_sha256"],
        "raw_observation_sha256": normalized["raw_observation_sha256"],
        "capability_summary": normalized["capability_summary"],
        "execution_route_decision": normalized["execution_route_decision"],
        "route_decisions": [
            (row["route_id"], row["access_status"], row["payload_sha256"], row["route_decision"])
            for row in normalized["routes"]
        ],
        "controlled_limitations": normalized["controlled_limitations"],
        "next_gate": contract["next_gate"],
        "trade_authority": "NONE",
    }


def _rewrite_manifest(candidate_root: Path) -> None:
    manifest_path = candidate_root / "FMDL6B_MANIFEST.json"
    manifest = load_json(manifest_path)
    manifest["files"] = {
        path.name: {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
        for path in sorted(candidate_root.iterdir())
        if path.is_file() and path.name != manifest_path.name
    }
    write_json(manifest_path, manifest)


def install_controlled_access_policy(release_module: Any) -> None:
    if getattr(release_module, "_fmdl6b_controlled_policy_installed", False):
        return
    release_module._fmdl6b_controlled_policy_installed = True
    original_build = release_module.build_candidate
    original_publish = release_module.publish_candidate
    release_module.normalize_observations = controlled_normalize_observations
    release_module.canonical_payload = controlled_canonical_payload

    def governed_build(repo_root: Path, contract_path: Path, raw_path: Path, candidate_root: Path) -> dict[str, Any]:
        original_build(repo_root, contract_path, raw_path, candidate_root)
        normalized = load_json(candidate_root / "FMDL6B_INTERFACE_BENCHMARK.json")
        execution = normalized["execution_route_decision"]
        decision_path = candidate_root / "FMDL6B_DECISION.json"
        release_path = candidate_root / "FMDL6B_RELEASE.json"
        registry_path = candidate_root / "FMDL6B_SOURCE_REGISTRY.json"
        decision = load_json(decision_path)
        release = load_json(release_path)
        registry = load_json(registry_path)
        decision["execution_route_decision"] = execution
        release["execution_route_decision"] = execution
        release["sec_official_github_actions_compatible"] = execution["github_hosted_actions"] != "UNAVAILABLE_FOR_SEC_OFFICIAL_APIS_403"
        registry["execution_route_decision"] = execution
        write_json(decision_path, decision)
        write_json(release_path, release)
        write_json(registry_path, registry)
        _rewrite_manifest(candidate_root)
        return release

    def governed_publish(repo_root: Path, contract_path: Path, candidate_root: Path) -> dict[str, Any]:
        last_success = original_publish(repo_root, contract_path, candidate_root)
        contract = load_json(contract_path)
        release = load_json(candidate_root / "FMDL6B_RELEASE.json")
        last_success["execution_route_decision"] = release["execution_route_decision"]
        last_success["sec_official_github_actions_compatible"] = release["sec_official_github_actions_compatible"]
        write_json(repo_root / contract["publication"]["last_success"], last_success)
        return last_success

    release_module.build_candidate = governed_build
    release_module.publish_candidate = governed_publish
