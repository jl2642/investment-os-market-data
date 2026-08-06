#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from automation.cross_market.build_round3_limited_production import (
    EVIDENCE_ROOT,
    LEDGER_PATH,
    PROPOSAL_PATH,
    RUN_PATH,
    read_json,
    sha256_file,
    write_json,
)

ALLOWED_RETRIEVAL_ENVIRONMENT = "CHATGPT_WEB_CONTROLLED_OFFICIAL_RETRIEVAL"
ALLOWED_CIK_RESOLUTION_SOURCES = {"ACCEPTED_EVIDENCE", "SEC_COMPANY_TICKERS"}
ALLOWED_SOURCE_PREFIXES = (
    "https://www.sec.gov/files/company_tickers",
    "https://www.sec.gov/Archives/edgar/data/",
    "https://data.sec.gov/submissions/CIK",
    "https://data.sec.gov/api/xbrl/companyfacts/CIK",
)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
CIK10 = re.compile(r"^[0-9]{10}$")


def normalized_json_sha256(payload: Any) -> str:
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def parse_iso_datetime(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise SystemExit("ROUND3_SEC_OBSERVER_RETRIEVED_AT_MUST_HAVE_TIMEZONE")
    return parsed.isoformat()


def queue_key(row: dict[str, Any]) -> str:
    return str(row.get("canonical_issuer_id") or row.get("symbol") or row.get("cik") or "").strip()


def validate_official_sources(sources: Any, cik: str, resolution_source: str) -> list[str]:
    if not isinstance(sources, list) or not sources:
        raise SystemExit("ROUND3_SEC_OBSERVER_OFFICIAL_SOURCES_REQUIRED")
    values = sorted({str(value).strip() for value in sources if str(value).strip()})
    if not values or any(not value.startswith(ALLOWED_SOURCE_PREFIXES) for value in values):
        raise SystemExit("ROUND3_SEC_OBSERVER_NON_OFFICIAL_SOURCE")
    required = {
        f"https://data.sec.gov/submissions/CIK{cik}.json",
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
    }
    if not required.issubset(set(values)):
        raise SystemExit("ROUND3_SEC_OBSERVER_REQUIRED_SEC_ENDPOINT_MISSING")
    if resolution_source == "SEC_COMPANY_TICKERS" and not any(value.startswith("https://www.sec.gov/files/company_tickers") for value in values):
        raise SystemExit("ROUND3_SEC_OBSERVER_TICKER_MAP_SOURCE_MISSING")
    return values


def validate_inbox(inbox: dict[str, Any], queue_payload: dict[str, Any]) -> dict[str, Any]:
    if inbox.get("schema_version") != "1.0.0":
        raise SystemExit("ROUND3_SEC_OBSERVER_SCHEMA_VERSION_INVALID")
    if inbox.get("run_id") != queue_payload.get("run_id"):
        raise SystemExit("ROUND3_SEC_OBSERVER_RUN_ID_MISMATCH")
    if inbox.get("as_of_date") != queue_payload.get("as_of_date"):
        raise SystemExit("ROUND3_SEC_OBSERVER_AS_OF_MISMATCH")
    if inbox.get("retrieval_environment") != ALLOWED_RETRIEVAL_ENVIRONMENT:
        raise SystemExit("ROUND3_SEC_OBSERVER_ENVIRONMENT_INVALID")
    retrieved_at = parse_iso_datetime(str(inbox.get("retrieved_at") or ""))
    if inbox.get("orders") != 0 or inbox.get("trade_authority") != "NONE":
        raise SystemExit("ROUND3_SEC_OBSERVER_AUTHORITY_VIOLATION")

    queue_rows = queue_payload.get("queue") or []
    if not isinstance(queue_rows, list) or not queue_rows:
        raise SystemExit("ROUND3_SEC_OBSERVER_QUEUE_EMPTY")
    queue_map = {queue_key(row): row for row in queue_rows if queue_key(row)}
    if len(queue_map) != len(queue_rows):
        raise SystemExit("ROUND3_SEC_OBSERVER_QUEUE_KEY_INVALID_OR_DUPLICATE")

    issuers = inbox.get("issuers") or []
    failures = inbox.get("failures") or []
    if not isinstance(issuers, list) or not isinstance(failures, list):
        raise SystemExit("ROUND3_SEC_OBSERVER_RESULT_LIST_INVALID")
    if len(issuers) + len(failures) > len(queue_rows):
        raise SystemExit("ROUND3_SEC_OBSERVER_RESULT_EXCEEDS_QUEUE")

    normalized_issuers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in issuers:
        key = queue_key(row)
        if not key or key not in queue_map or key in seen:
            raise SystemExit("ROUND3_SEC_OBSERVER_ISSUER_NOT_QUEUED_OR_DUPLICATE")
        seen.add(key)
        queued = queue_map[key]
        symbol = str(row.get("symbol") or "").strip().upper()
        queued_symbol = str(queued.get("symbol") or "").strip().upper()
        if not symbol or symbol != queued_symbol:
            raise SystemExit("ROUND3_SEC_OBSERVER_SYMBOL_MISMATCH")
        issuer_id = str(row.get("canonical_issuer_id") or "").strip()
        queued_issuer_id = str(queued.get("canonical_issuer_id") or "").strip()
        if not issuer_id or issuer_id != queued_issuer_id:
            raise SystemExit("ROUND3_SEC_OBSERVER_ISSUER_ID_MISMATCH")
        cik = str(row.get("cik") or "").strip()
        if not CIK10.fullmatch(cik):
            raise SystemExit("ROUND3_SEC_OBSERVER_CIK_INVALID")
        resolution_source = str(row.get("cik_resolution_source") or "").strip()
        if resolution_source not in ALLOWED_CIK_RESOLUTION_SOURCES:
            raise SystemExit("ROUND3_SEC_OBSERVER_CIK_RESOLUTION_SOURCE_INVALID")
        expected_route = str(queued.get("official_resolution_route") or "")
        if expected_route == "SYMBOL_TO_SEC_OFFICIAL_TICKER_MAP_TO_CIK" and resolution_source != "SEC_COMPANY_TICKERS":
            raise SystemExit("ROUND3_SEC_OBSERVER_CIK_ROUTE_MISMATCH")
        if expected_route == "CIK_DIRECT" and resolution_source != "ACCEPTED_EVIDENCE":
            raise SystemExit("ROUND3_SEC_OBSERVER_CIK_ROUTE_MISMATCH")
        if row.get("status") != "PASS_OFFICIAL_SEC_REFRESH":
            raise SystemExit("ROUND3_SEC_OBSERVER_SUCCESS_STATUS_INVALID")
        filing_date = str(row.get("latest_filing_date") or "").strip()
        if filing_date:
            date.fromisoformat(filing_date)
        taxonomy_count = int(row.get("companyfacts_taxonomy_count", 0))
        if taxonomy_count < 0:
            raise SystemExit("ROUND3_SEC_OBSERVER_TAXONOMY_COUNT_INVALID")
        sources = validate_official_sources(row.get("official_sources"), cik, resolution_source)
        normalized_issuers.append({
            "canonical_issuer_id": issuer_id,
            "symbol": symbol,
            "cik": cik,
            "cik_resolution_source": resolution_source,
            "latest_filing_form": str(row.get("latest_filing_form") or "").strip(),
            "latest_filing_date": filing_date,
            "companyfacts_taxonomy_count": taxonomy_count,
            "official_sources": sources,
            "status": "PASS_OFFICIAL_SEC_REFRESH",
            "decision_grade": False,
        })

    normalized_failures: list[dict[str, Any]] = []
    for row in failures:
        key = queue_key(row)
        if not key or key not in queue_map or key in seen:
            raise SystemExit("ROUND3_SEC_OBSERVER_FAILURE_NOT_QUEUED_OR_DUPLICATE")
        seen.add(key)
        normalized_failures.append({
            "canonical_issuer_id": str(row.get("canonical_issuer_id") or "").strip(),
            "symbol": str(row.get("symbol") or "").strip().upper(),
            "status": "SEC_DATA_GAP",
            "reason": str(row.get("reason") or "UNSPECIFIED_OFFICIAL_RETRIEVAL_FAILURE").strip()[:500],
        })

    normalized_issuers.sort(key=lambda row: (row["canonical_issuer_id"], row["symbol"]))
    normalized_failures.sort(key=lambda row: (row["canonical_issuer_id"], row["symbol"]))
    return {
        "schema_version": "1.0.0",
        "run_id": inbox["run_id"],
        "as_of_date": inbox["as_of_date"],
        "retrieval_environment": ALLOWED_RETRIEVAL_ENVIRONMENT,
        "retrieved_at": retrieved_at,
        "issuers": normalized_issuers,
        "failures": normalized_failures,
        "official_success_count": len(normalized_issuers),
        "official_failure_count": len(normalized_failures),
        "orders": 0,
        "trade_authority": "NONE",
    }


def update_operating_state(root: Path, result: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    ledger = read_json(root / LEDGER_PATH)
    as_of = date.fromisoformat(result["as_of_date"])
    iso_year, iso_week, _ = as_of.isocalendar()
    cycle_id = f"{iso_year}-W{iso_week:02d}"
    cycle = (ledger.get("weekly_cycles") or {}).get(cycle_id)
    if not cycle:
        raise SystemExit("ROUND3_SEC_OBSERVER_CYCLE_NOT_FOUND")

    completed_ids = set(str(value) for value in cycle.get("official_sec_issuer_ids", []) if str(value))
    completed_ids.update(row["canonical_issuer_id"] for row in result["issuers"])
    cycle["official_sec_issuer_ids"] = sorted(completed_ids)
    cycle["sec_official_completed_issuer_count"] = len(completed_ids)
    minimum = int(policy["united_states"]["minimum_weekly_official_sec_completed_count"])
    if len(completed_ids) >= minimum:
        cycle["sec_official_retrieval_status"] = "PASS_CHATGPT_WEB_OFFICIAL_RETRIEVAL"
    elif completed_ids:
        cycle["sec_official_retrieval_status"] = "PARTIAL_CHATGPT_WEB_OFFICIAL_RETRIEVAL"
    else:
        cycle["sec_official_retrieval_status"] = "PENDING_CHATGPT_WEB_OFFICIAL_RETRIEVAL"
    cycle["completed"] = bool(cycle.get("market_rotation_completed")) and len(completed_ids) >= minimum

    ledger["completed_weekly_cycle_count"] = sum(bool(item.get("completed")) for item in ledger["weekly_cycles"].values())
    ledger["market_rotation_completed_weekly_cycle_count"] = sum(bool(item.get("market_rotation_completed")) for item in ledger["weekly_cycles"].values())
    acceptance_required = int(policy["acceptance"]["completed_weekly_cycles_for_limited_production_acceptance"])
    operating_state = "ROUND3_LIMITED_PRODUCTION_ACCEPTED" if ledger["completed_weekly_cycle_count"] >= acceptance_required else "ROUND3_OPERATING_OBSERVATION"

    run_current = read_json(root / RUN_PATH)
    run_current["completed_weekly_cycle_count"] = ledger["completed_weekly_cycle_count"]
    run_current["market_rotation_completed_weekly_cycle_count"] = ledger["market_rotation_completed_weekly_cycle_count"]
    run_current["operating_state"] = operating_state
    current_as_of = date.fromisoformat(str(run_current.get("as_of_date")))
    current_iso_year, current_iso_week, _ = current_as_of.isocalendar()
    current_cycle_id = f"{current_iso_year}-W{current_iso_week:02d}"
    if current_cycle_id == cycle_id:
        run_current.setdefault("united_states", {})["sec_official_completed_issuer_count"] = len(completed_ids)
        run_current["united_states"]["sec_official_retrieval_status"] = cycle["sec_official_retrieval_status"]
        run_current["united_states"]["sec_official_success_claimed"] = cycle["sec_official_retrieval_status"] == "PASS_CHATGPT_WEB_OFFICIAL_RETRIEVAL"

    proposal = read_json(root / PROPOSAL_PATH)
    if proposal.get("cycle_id") == cycle_id:
        proposal["cycle_completed"] = bool(cycle["completed"])
        proposal["sec_official_retrieval_status"] = cycle["sec_official_retrieval_status"]
        proposal["status"] = (
            "WEEKLY_RESEARCH_REVIEW_READY" if cycle["completed"]
            else "WEEKLY_RESEARCH_REVIEW_READY_SEC_ENRICHMENT_PENDING" if cycle.get("market_rotation_completed")
            else "DAILY_BATCH_CAPTURED_NO_WEEKLY_PROPOSAL_YET"
        )

    write_json(root / LEDGER_PATH, ledger)
    write_json(root / RUN_PATH, run_current)
    write_json(root / PROPOSAL_PATH, proposal)
    return {
        "cycle_id": cycle_id,
        "cycle_completed": bool(cycle["completed"]),
        "sec_official_completed_issuer_count": len(completed_ids),
        "sec_official_retrieval_status": cycle["sec_official_retrieval_status"],
        "operating_state": operating_state,
    }


def apply(root: Path, inbox_path: Path, policy_path: Path) -> dict[str, Any]:
    inbox = read_json(root / inbox_path)
    run_id = str(inbox.get("run_id") or "").strip()
    if not run_id:
        raise SystemExit("ROUND3_SEC_OBSERVER_RUN_ID_REQUIRED")
    evidence_dir = root / EVIDENCE_ROOT / run_id
    queue_path = evidence_dir / "ROUND3_SEC_OFFICIAL_RETRIEVAL_QUEUE.json"
    if not queue_path.exists():
        raise SystemExit("ROUND3_SEC_OBSERVER_QUEUE_NOT_FOUND")
    queue_payload = read_json(queue_path)
    normalized = validate_inbox(inbox, queue_payload)
    normalized["normalized_evidence_sha256"] = normalized_json_sha256(normalized)
    result_path = evidence_dir / "ROUND3_SEC_OFFICIAL_RETRIEVAL_RESULT.json"
    write_json(result_path, normalized)

    policy = read_json(root / policy_path)
    state = update_operating_state(root, normalized, policy)
    manifest = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "input_sha256": {
            str(inbox_path): sha256_file(root / inbox_path),
            str(queue_path.relative_to(root)): sha256_file(queue_path),
            str(policy_path): sha256_file(root / policy_path),
        },
        "output_sha256": {
            str(result_path.relative_to(root)): sha256_file(result_path),
            str(LEDGER_PATH): sha256_file(root / LEDGER_PATH),
            str(RUN_PATH): sha256_file(root / RUN_PATH),
            str(PROPOSAL_PATH): sha256_file(root / PROPOSAL_PATH),
        },
        "orders": 0,
        "trade_authority": "NONE",
    }
    manifest_path = evidence_dir / "ROUND3_SEC_OBSERVER_MANIFEST.json"
    write_json(manifest_path, manifest)
    return {
        "status": "ROUND3_SEC_OBSERVER_RESULTS_APPLIED",
        "run_id": run_id,
        **state,
        "official_success_count_this_run": normalized["official_success_count"],
        "official_failure_count_this_run": normalized["official_failure_count"],
        "orders": 0,
        "trade_authority": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--inbox", required=True)
    parser.add_argument("--policy", default="automation/cross_market/round3_policy.json")
    args = parser.parse_args()
    result = apply(Path(args.repo_root), Path(args.inbox), Path(args.policy))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
