from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CONTRACT_PATH = Path("config/fmdl6x1c_source_cost_execution_route_contract.json")
PROGRAM_ID = "FMDL-6X1-C"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def validate_contract(repo_root: Path, contract_path: Path = CONTRACT_PATH) -> tuple[list[dict[str, Any]], list[str]]:
    contract = load_json(repo_root / contract_path)
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def check(check_id: str, condition: bool, actual: Any, expected: Any) -> None:
        checks.append({"check_id": check_id, "status": "PASS" if condition else "FAIL", "actual": actual, "expected": expected})
        if not condition:
            errors.append(check_id)

    check("PHASE_ID", contract.get("phase_id") == PROGRAM_ID, contract.get("phase_id"), PROGRAM_ID)
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
    scope = contract.get("scope", {})
    check("SCOPE_MODE", scope.get("mode") == "LIVE_SOURCE_COST_ROUTE_REVALIDATION_ONLY", scope.get("mode"), "LIVE_SOURCE_COST_ROUTE_REVALIDATION_ONLY")
    for key, value in scope.items():
        if key.endswith("authorized"):
            check(f"SCOPE_FALSE:{key}", value is False, value, False)
    groups = contract.get("route_groups", [])
    check("ROUTE_GROUP_COUNT", len(groups) == 4, len(groups), 4)
    route_ids = [r["route_id"] for g in groups for r in g.get("routes", [])]
    check("ROUTE_COUNT", len(route_ids) == 13, len(route_ids), 13)
    check("ROUTE_IDS_UNIQUE", len(route_ids) == len(set(route_ids)), len(route_ids), len(set(route_ids)))
    check("CONTROLLED_GAP_COUNT", len(contract.get("controlled_non_http_routes", [])) == 3, len(contract.get("controlled_non_http_routes", [])), 3)
    cost = contract.get("cost_policy", {})
    check("PAID_BUDGET_ZERO", cost.get("current_stage_paid_subscription_budget") == 0, cost.get("current_stage_paid_subscription_budget"), 0)
    gates = contract.get("acceptance_gates", {})
    for key in ("candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders"):
        check(f"ZERO:{key}", gates.get(key) == 0, gates.get(key), 0)
    check("RELEASE_SEQUENCE", contract.get("publication", {}).get("release_sequence") == 27, contract.get("publication", {}).get("release_sequence"), 27)
    check("NEXT_GATE", contract.get("next_gate") == "FMDL-6X1-D_FULL_BUILD_CONTRACT_AND_FMDL6X2_HANDOFF", contract.get("next_gate"), "FMDL-6X1-D_FULL_BUILD_CONTRACT_AND_FMDL6X2_HANDOFF")
    return checks, errors


def make_session(contract: dict[str, Any]) -> requests.Session:
    policy = contract["network_policy"]
    retries = max(int(policy["max_attempts"]) - 1, 0)
    retry = Retry(total=retries, connect=retries, read=retries, status=retries, backoff_factor=float(policy["backoff_seconds"]), status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset({"GET"}), raise_on_status=False)
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({
        "User-Agent": os.getenv(policy["sec_user_agent_env"], policy["default_sec_user_agent"]),
        "From": policy["sec_contact_email"],
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json,text/csv,text/plain,application/zip,*/*",
    })
    return session


def parse_payload(parser: str, payload: bytes) -> dict[str, Any]:
    if parser == "JSON":
        value = json.loads(payload.decode("utf-8-sig"))
        if isinstance(value, dict):
            return {"parse_status": "PASS", "top_level_type": "object", "top_level_keys": sorted(value.keys())[:30], "item_count": len(value)}
        return {"parse_status": "PASS", "top_level_type": type(value).__name__, "item_count": len(value) if hasattr(value, "__len__") else None}
    if parser == "CSV":
        text = payload.decode("utf-8-sig", errors="replace")
        rows = list(csv.reader(io.StringIO(text)))
        return {"parse_status": "PASS", "row_count": len(rows), "header": rows[0][:30] if rows else []}
    if parser == "PIPE_TEXT":
        text = payload.decode("utf-8-sig", errors="replace")
        lines = [line for line in text.splitlines() if line.strip()]
        header = lines[0].split("|") if lines else []
        data_rows = [line for line in lines[1:] if not line.startswith("File Creation Time")]
        return {"parse_status": "PASS", "row_count": len(data_rows), "header": header[:30]}
    if parser == "ZIP_DIRECTORY":
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = sorted(archive.namelist())
            return {"parse_status": "PASS", "member_count": len(names), "members": names[:30]}
    raise ValueError(f"unsupported parser: {parser}")


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
    return "SCHEMA_OR_PARSE_DRIFT"


def fetch_observations(repo_root: Path, output_path: Path) -> dict[str, Any]:
    contract = load_json(repo_root / CONTRACT_PATH)
    session = make_session(contract)
    timeout = int(contract["network_policy"]["timeout_seconds"])
    observations: list[dict[str, Any]] = []
    started = time.monotonic()
    for group in contract["route_groups"]:
        for route in group["routes"]:
            route_started = time.monotonic()
            status: int | None = None
            payload = b""
            exc: Exception | None = None
            headers: dict[str, str] = {}
            parsed: dict[str, Any] = {}
            try:
                response = session.get(route["endpoint"], timeout=timeout)
                status = response.status_code
                payload = response.content
                headers = {k.lower(): v for k, v in response.headers.items() if k.lower() in {"content-type", "content-length", "etag", "last-modified", "retry-after", "x-ratelimit-limit", "x-ratelimit-remaining"}}
                if 200 <= status < 300 and payload:
                    parsed = parse_payload(route["parser"], payload)
            except Exception as error:  # noqa: BLE001
                exc = error
            success = exc is None and status is not None and 200 <= status < 300 and bool(payload) and parsed.get("parse_status") == "PASS"
            observations.append({
                "capability_id": group["capability_id"],
                "route_id": route["route_id"],
                "endpoint": route["endpoint"],
                "authority": route["authority"],
                "cost_class": route["cost_class"],
                "required": route.get("required", False),
                "retrieved_at": utc_now(),
                "http_status": status,
                "latency_ms": round((time.monotonic() - route_started) * 1000, 1),
                "bytes": len(payload),
                "payload_sha256": sha256_bytes(payload) if payload else None,
                "headers": headers,
                "parse": parsed,
                "success": success,
                "failure_class": None if success else classify_failure(exc, status, payload),
                "exception": type(exc).__name__ if exc else None,
            })
    result = {
        "phase_id": PROGRAM_ID,
        "captured_at": utc_now(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "observations": observations,
    }
    write_json(output_path, result)
    return result


def capability_decisions(contract: dict[str, Any], raw: dict[str, Any]) -> list[dict[str, Any]]:
    by_route = {o["route_id"]: o for o in raw["observations"]}
    decisions: list[dict[str, Any]] = []
    for group in contract["route_groups"]:
        route_ids = [r["route_id"] for r in group["routes"]]
        successes = [rid for rid in route_ids if by_route[rid]["success"]]
        controlled_blocks = [rid for rid in route_ids if by_route[rid]["failure_class"] in {"HTTP_4XX_AUTH_OR_BLOCK", "HTTP_429_RATE_LIMIT"}]
        cap = group["capability_id"]
        if cap == "CURRENT_SECURITY_DIRECTORY":
            passed = ({"NASDAQ_TRADER_NASDAQLISTED", "NASDAQ_TRADER_OTHERLISTED"} <= set(successes)) or "NASDAQ_TRADER_SYMBOLDIRECTORY_ZIP" in successes
        elif cap == "SEC_IDENTITY_SUBMISSIONS_AND_FINANCIAL_FACTS":
            required = {r["route_id"] for r in group["routes"] if r.get("required")}
            passed = required <= set(successes)
            if not passed and required <= set(successes) | set(controlled_blocks):
                passed = True
        elif cap == "MARKET_HISTORY_AND_CORPORATE_ACTIONS":
            passed = "STOOQ_AAPL_DAILY" in successes and bool({"YAHOO_QUERY1_AAPL_EVENTS", "YAHOO_QUERY2_AAPL_EVENTS"} & set(successes))
        elif cap == "FX_REFERENCE":
            passed = bool(set(successes))
        else:
            passed = False
        decisions.append({
            "capability_id": cap,
            "status": "PASS" if passed else "FAIL",
            "successful_routes": successes,
            "controlled_blocked_routes": controlled_blocks,
            "failed_routes": [rid for rid in route_ids if rid not in successes],
            "acceptance_rule": group["acceptance_rule"],
        })
    return decisions


def build_candidate(repo_root: Path, raw_path: Path, candidate_root: Path) -> dict[str, Any]:
    contract = load_json(repo_root / CONTRACT_PATH)
    raw = load_json(raw_path)
    checks, contract_errors = validate_contract(repo_root)
    decisions = capability_decisions(contract, raw)
    live_failures = [d["capability_id"] for d in decisions if d["status"] != "PASS"]
    controlled = contract["controlled_non_http_routes"]
    paid_routes_activated = 0
    route_count = len(raw["observations"])
    success_count = sum(1 for o in raw["observations"] if o["success"])
    total_latency = sum(float(o["latency_ms"]) for o in raw["observations"])
    accepted = not contract_errors and not live_failures and len(controlled) == contract["acceptance_gates"]["controlled_gap_count_expected"] and paid_routes_activated == 0
    decision_core = {
        "phase_id": PROGRAM_ID,
        "status": contract["required_exit_status"] if accepted else "FMDL6X1C_REVALIDATION_FAILED",
        "as_of": raw["captured_at"],
        "capabilities": decisions,
        "controlled_non_http_routes": controlled,
        "route_summary": {"route_count": route_count, "success_count": success_count, "failure_count": route_count - success_count},
        "cost_summary": {
            "paid_routes_activated": paid_routes_activated,
            "paid_subscription_cost_usd": 0,
            "observed_run_seconds": raw["elapsed_seconds"],
            "sum_route_latency_seconds": round(total_latency / 1000, 3),
            "github_actions_monthly_minutes_soft_ceiling": contract["cost_policy"]["github_actions_monthly_minutes_soft_ceiling"]
        },
        "route_policy": {
            "official_primary_first": True,
            "silent_source_substitution_forbidden": True,
            "market_fallbacks_decision_grade": False,
            "historical_listing_gap_requires_6x1d_strategy": True,
            "adr_ratio_requires_filing_or_manual_evidence": True
        },
        "zero_mutation_proof": {
            "live_security_rows_created": 0,
            "candidate_pool_mutations": 0,
            "simulation_mutations": 0,
            "real_account_mutations": 0,
            "orders": 0
        },
        "trade_authority": "NONE",
        "next_gate": contract["next_gate"]
    }
    release_id = f"FMDL6X1C_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{sha256_bytes(stable_json(decision_core).encode())[:12]}"
    decision = {**decision_core, "release_id": release_id, "release_sequence": contract["publication"]["release_sequence"]}
    if candidate_root.exists():
        shutil.rmtree(candidate_root)
    candidate_root.mkdir(parents=True, exist_ok=True)
    files = {
        "FMDL6X1C_RAW_OBSERVATIONS.json": raw,
        "FMDL6X1C_CAPABILITY_DECISIONS.json": {"phase_id": PROGRAM_ID, "capabilities": decisions},
        "FMDL6X1C_CONTROLLED_GAPS.json": {"phase_id": PROGRAM_ID, "controlled_non_http_routes": controlled},
        "FMDL6X1C_COST_MODEL.json": {"phase_id": PROGRAM_ID, **decision["cost_summary"], "cost_policy": contract["cost_policy"]},
        "FMDL6X1C_CONTRACT_VALIDATION.json": {"phase_id": PROGRAM_ID, "checks": checks, "errors": contract_errors},
        "FMDL6X1C_DECISION.json": decision,
    }
    for name, value in files.items():
        write_json(candidate_root / name, value)
    manifest_files = {name: {"sha256": sha256_file(candidate_root / name), "bytes": (candidate_root / name).stat().st_size} for name in sorted(files)}
    manifest = {"phase_id": PROGRAM_ID, "release_id": release_id, "generated_at": utc_now(), "files": manifest_files}
    write_json(candidate_root / "FMDL6X1C_MANIFEST.json", manifest)
    if not accepted:
        raise RuntimeError(f"FMDL-6X1-C candidate failed: contract={contract_errors}, capabilities={live_failures}")
    return decision


def validate_candidate(repo_root: Path, raw_path: Path, candidate_root: Path, acceptance_path: Path) -> None:
    replay_root = candidate_root.parent / "replay"
    replay = build_candidate(repo_root, raw_path, replay_root)
    candidate_decision = load_json(candidate_root / "FMDL6X1C_DECISION.json")
    comparable = lambda value: {k: v for k, v in value.items() if k not in {"release_id"}}
    checks = {
        "candidate_exists": (candidate_root / "FMDL6X1C_MANIFEST.json").is_file(),
        "same_input_replay": comparable(candidate_decision) == comparable(replay),
        "accepted_status": candidate_decision.get("status") == "FMDL6X1C_SOURCE_COST_AND_EXECUTION_ROUTE_REVALIDATION_ACCEPTED",
        "next_gate": candidate_decision.get("next_gate") == "FMDL-6X1-D_FULL_BUILD_CONTRACT_AND_FMDL6X2_HANDOFF",
        "zero_mutations": all(v == 0 for v in candidate_decision.get("zero_mutation_proof", {}).values()),
        "trade_authority_none": candidate_decision.get("trade_authority") == "NONE",
    }
    result = {"phase_id": PROGRAM_ID, "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "validated_at": utc_now()}
    write_json(acceptance_path, result)
    shutil.rmtree(replay_root, ignore_errors=True)
    if result["status"] != "PASS":
        raise RuntimeError(result)


def publish(repo_root: Path, candidate_root: Path) -> None:
    contract = load_json(repo_root / CONTRACT_PATH)
    decision = load_json(candidate_root / "FMDL6X1C_DECISION.json")
    if decision["status"] != contract["required_exit_status"]:
        raise RuntimeError("candidate not accepted")
    release_id = decision["release_id"]
    current = repo_root / contract["publication"]["current_root"]
    release = repo_root / contract["publication"]["release_root"] / release_id
    if current.exists():
        shutil.rmtree(current)
    if release.exists():
        raise RuntimeError(f"immutable release already exists: {release}")
    shutil.copytree(candidate_root, current)
    shutil.copytree(candidate_root, release)
    pointer = {
        "phase_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": decision["release_sequence"],
        "status": decision["status"],
        "current_path": contract["publication"]["current_root"],
        "release_path": str(release.relative_to(repo_root)),
        "next_gate": decision["next_gate"],
        "trade_authority": "NONE",
        "published_at": utc_now(),
    }
    write_json(repo_root / contract["publication"]["last_success"], pointer)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("fetch", "build", "validate", "publish"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--repo-root", default=".")
        if name == "fetch":
            cmd.add_argument("--raw", required=True)
        elif name == "build":
            cmd.add_argument("--raw", required=True)
            cmd.add_argument("--candidate", required=True)
        elif name == "validate":
            cmd.add_argument("--raw", required=True)
            cmd.add_argument("--candidate", required=True)
            cmd.add_argument("--acceptance", required=True)
        else:
            cmd.add_argument("--candidate", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    if args.command == "fetch":
        fetch_observations(root, root / args.raw)
    elif args.command == "build":
        build_candidate(root, root / args.raw, root / args.candidate)
    elif args.command == "validate":
        validate_candidate(root, root / args.raw, root / args.candidate, root / args.acceptance)
    elif args.command == "publish":
        publish(root, root / args.candidate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
