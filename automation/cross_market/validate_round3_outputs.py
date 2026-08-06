#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(run: dict[str, Any], proposal: dict[str, Any], ledger: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    authority = policy["authority"]
    for payload_name, payload in (("run", run), ("proposal", proposal)):
        controls = payload.get("controls", {})
        for key in ("candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "decision_mutations", "orders"):
            if controls.get(key) != 0:
                raise SystemExit(f"ROUND3_AUTHORITY_VIOLATION:{payload_name}:{key}")
        if controls.get("trade_authority") != "NONE":
            raise SystemExit(f"ROUND3_TRADE_AUTHORITY_VIOLATION:{payload_name}")
    if ledger.get("orders") != 0 or ledger.get("trade_authority") != "NONE":
        raise SystemExit("ROUND3_LEDGER_AUTHORITY_VIOLATION")
    boundaries = proposal.get("scope_boundaries", {})
    if boundaries.get("hong_kong_scope") != "SOUTHBOUND_STOCK_CONNECT_ONLY" or boundaries.get("full_hkex_market_claimed") is not False:
        raise SystemExit("ROUND3_HK_SCOPE_OVERCLAIM")
    if boundaries.get("united_states_scope") != "BOUNDED_ROTATION_NOT_FULL_MARKET_WEEKLY_COVERAGE" or boundaries.get("full_us_market_history_claimed") is not False:
        raise SystemExit("ROUND3_US_SCOPE_OVERCLAIM")
    if boundaries.get("formal_cross_section_rank_claimed") is not False:
        raise SystemExit("ROUND3_US_RANK_OVERCLAIM")
    allowed = set(policy["research"]["allowed_labels"])
    forbidden = set(policy["research"]["forbidden_labels"])
    seen: set[tuple[str, str]] = set()
    for market_key in ("hong_kong", "united_states"):
        for row in proposal.get(market_key, []):
            label = row.get("label")
            if label not in allowed or label in forbidden:
                raise SystemExit(f"ROUND3_FORBIDDEN_RESEARCH_LABEL:{label}")
            if row.get("candidate_pool_mutation_authorized") is not False:
                raise SystemExit("ROUND3_CANDIDATE_MUTATION_AUTHORIZED")
            key = (str(row.get("market")), str(row.get("security_id") or row.get("symbol")))
            if key in seen:
                raise SystemExit(f"ROUND3_DUPLICATE_PROPOSAL:{key}")
            seen.add(key)
    if run.get("hong_kong", {}).get("full_hkex_market_claimed") is not False:
        raise SystemExit("ROUND3_RUN_HK_OVERCLAIM")
    if run.get("united_states", {}).get("full_universe_market_history_claimed") is not False:
        raise SystemExit("ROUND3_RUN_US_OVERCLAIM")
    us_run = run.get("united_states", {})
    if us_run.get("sec_execution_mode") != "QUEUE_FOR_CHATGPT_WEB_OFFICIAL_RETRIEVAL":
        raise SystemExit("ROUND3_SEC_EXECUTION_ENVIRONMENT_MISMATCH")
    if us_run.get("sec_official_success_claimed") is not False:
        raise SystemExit("ROUND3_FALSE_SEC_SUCCESS_CLAIM")
    if int(us_run.get("rotation_pool_count", 0)) != int(policy["united_states"]["expected_security_master_count"]):
        raise SystemExit("ROUND3_US_ROTATION_POOL_COUNT_MISMATCH")
    if int(us_run.get("sec_pool_count", 0)) != int(policy["united_states"]["expected_issuer_count"]):
        raise SystemExit("ROUND3_US_SEC_POOL_COUNT_MISMATCH")
    if proposal.get("sec_official_retrieval_status") not in {
        "PENDING_CHATGPT_WEB_OFFICIAL_RETRIEVAL",
        "PARTIAL_CHATGPT_WEB_OFFICIAL_RETRIEVAL",
        "PASS_CHATGPT_WEB_OFFICIAL_RETRIEVAL",
    }:
        raise SystemExit("ROUND3_SEC_RETRIEVAL_STATUS_INVALID")
    for cycle in ledger.get("weekly_cycles", {}).values():
        if cycle.get("completed") and int(cycle.get("sec_official_completed_issuer_count", 0)) < int(policy["united_states"]["minimum_weekly_official_sec_completed_count"]):
            raise SystemExit("ROUND3_WEEKLY_ACCEPTANCE_WITHOUT_SEC_EVIDENCE")
    if authority.get("trade_authority") != "NONE" or authority.get("orders") != 0:
        raise SystemExit("ROUND3_POLICY_AUTHORITY_INVALID")
    return {"status": "ROUND3_OUTPUTS_VALID", "proposal_count": len(seen), "orders": 0, "trade_authority": "NONE"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--policy", default="automation/cross_market/round3_policy.json")
    args = parser.parse_args()
    result = validate(read(Path(args.run)), read(Path(args.proposal)), read(Path(args.ledger)), read(Path(args.policy)))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
