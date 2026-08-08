#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

# Direct script execution is restarted as a package module from repository root
# so absolute automation.cross_market imports resolve deterministically.
if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[2]
    os.chdir(repo_root)
    os.execv(
        sys.executable,
        [sys.executable, "-m", "automation.cross_market.apply_round3_sec_observer_results", *sys.argv[1:]],
    )

from . import apply_round3_sec_observer_results_impl as _impl

LEGACY_WEB_ENVIRONMENT = "CHATGPT_WEB_CONTROLLED_OFFICIAL_RETRIEVAL"
CONTROLLED_EXTERNAL_ENVIRONMENT = "CONTROLLED_LOCAL_OR_SELF_HOSTED_OFFICIAL_RETRIEVAL"
ALLOWED_RETRIEVAL_ENVIRONMENTS = {LEGACY_WEB_ENVIRONMENT, CONTROLLED_EXTERNAL_ENVIRONMENT}
PENDING_CONTROLLED = "PENDING_CONTROLLED_OFFICIAL_RETRIEVAL"
PARTIAL_CONTROLLED = "PARTIAL_CONTROLLED_OFFICIAL_RETRIEVAL"
PASS_CONTROLLED = "PASS_CONTROLLED_OFFICIAL_RETRIEVAL"


def _environment(inbox: dict[str, Any]) -> str:
    value = str(inbox.get("retrieval_environment") or "").strip()
    if value not in ALLOWED_RETRIEVAL_ENVIRONMENTS:
        raise SystemExit("ROUND3_SEC_OBSERVER_ENVIRONMENT_INVALID")
    return value


def _cycle_id(value: str) -> str:
    iso_year, iso_week, _ = date.fromisoformat(value[:10]).isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def validate_inbox(inbox: dict[str, Any], queue_payload: dict[str, Any]) -> dict[str, Any]:
    environment = _environment(inbox)
    prior = _impl.ALLOWED_RETRIEVAL_ENVIRONMENT
    _impl.ALLOWED_RETRIEVAL_ENVIRONMENT = environment
    try:
        return _impl.validate_inbox(inbox, queue_payload)
    finally:
        _impl.ALLOWED_RETRIEVAL_ENVIRONMENT = prior


def _generic_status(completed: int, minimum: int) -> str:
    if completed >= minimum:
        return PASS_CONTROLLED
    if completed > 0:
        return PARTIAL_CONTROLLED
    return PENDING_CONTROLLED


def apply(root: Path, inbox_path: Path, policy_path: Path) -> dict[str, Any]:
    inbox = _impl.read_json(root / inbox_path)
    environment = _environment(inbox)
    prior_env = _impl.ALLOWED_RETRIEVAL_ENVIRONMENT
    prior_update = _impl.update_operating_state
    _impl.ALLOWED_RETRIEVAL_ENVIRONMENT = environment

    def update_with_transport_neutral_status(
        update_root: Path,
        result: dict[str, Any],
        policy: dict[str, Any],
    ) -> dict[str, Any]:
        state = prior_update(update_root, result, policy)
        if environment != CONTROLLED_EXTERNAL_ENVIRONMENT:
            return state

        ledger = _impl.read_json(update_root / _impl.LEDGER_PATH)
        cycle = (ledger.get("weekly_cycles") or {}).get(state["cycle_id"])
        if not cycle:
            raise SystemExit("ROUND3_SEC_OBSERVER_CYCLE_NOT_FOUND")
        minimum = int(policy["united_states"]["minimum_weekly_official_sec_completed_count"])
        completed = int(cycle.get("sec_official_completed_issuer_count", 0))
        status = _generic_status(completed, minimum)
        cycle["sec_official_retrieval_status"] = status
        cycle["completed"] = bool(cycle.get("market_rotation_completed")) and completed >= minimum
        ledger["completed_weekly_cycle_count"] = sum(bool(item.get("completed")) for item in ledger["weekly_cycles"].values())
        ledger["market_rotation_completed_weekly_cycle_count"] = sum(bool(item.get("market_rotation_completed")) for item in ledger["weekly_cycles"].values())

        run_current = _impl.read_json(update_root / _impl.RUN_PATH)
        run_current["completed_weekly_cycle_count"] = ledger["completed_weekly_cycle_count"]
        run_current["market_rotation_completed_weekly_cycle_count"] = ledger["market_rotation_completed_weekly_cycle_count"]
        current_as_of = str(run_current.get("as_of_date") or "")
        if current_as_of and _cycle_id(current_as_of) == state["cycle_id"]:
            us = run_current.setdefault("united_states", {})
            us["sec_official_completed_issuer_count"] = completed
            us["sec_official_retrieval_status"] = status
            us["sec_official_success_claimed"] = status == PASS_CONTROLLED
            us["sec_retrieval_environment"] = environment

        proposal = _impl.read_json(update_root / _impl.PROPOSAL_PATH)
        if proposal.get("cycle_id") == state["cycle_id"]:
            proposal["cycle_completed"] = bool(cycle["completed"])
            proposal["sec_official_retrieval_status"] = status
            proposal["status"] = (
                "WEEKLY_RESEARCH_REVIEW_READY" if cycle["completed"]
                else "WEEKLY_RESEARCH_REVIEW_READY_SEC_ENRICHMENT_PENDING" if cycle.get("market_rotation_completed")
                else "DAILY_BATCH_CAPTURED_NO_WEEKLY_PROPOSAL_YET"
            )

        _impl.write_json(update_root / _impl.LEDGER_PATH, ledger)
        _impl.write_json(update_root / _impl.RUN_PATH, run_current)
        _impl.write_json(update_root / _impl.PROPOSAL_PATH, proposal)
        state["cycle_completed"] = bool(cycle["completed"])
        state["sec_official_retrieval_status"] = status
        return state

    _impl.update_operating_state = update_with_transport_neutral_status
    try:
        return _impl.apply(root, inbox_path, policy_path)
    finally:
        _impl.ALLOWED_RETRIEVAL_ENVIRONMENT = prior_env
        _impl.update_operating_state = prior_update


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
