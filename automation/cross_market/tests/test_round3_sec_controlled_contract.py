from __future__ import annotations

import json
from pathlib import Path

from automation.cross_market.apply_round3_sec_observer_results import (
    CONTROLLED_EXTERNAL_ENVIRONMENT,
    PASS_CONTROLLED,
    apply,
)
from automation.cross_market.tests.test_round3_sec_observer import official_row, prepare_completed_market_cycle
from automation.cross_market.tests.test_round3_limited_production import write_json
from automation.cross_market.validate_round3_outputs import validate


def test_controlled_external_sec_inbox_completes_round3_without_legacy_web_claim(tmp_path: Path) -> None:
    configured, evidence_dir = prepare_completed_market_cycle(tmp_path)
    queue = json.loads((evidence_dir / "ROUND3_SEC_OFFICIAL_RETRIEVAL_QUEUE.json").read_text())
    inbox = {
        "schema_version": "1.0.0",
        "run_id": queue["run_id"],
        "as_of_date": queue["as_of_date"],
        "retrieval_environment": CONTROLLED_EXTERNAL_ENVIRONMENT,
        "retrieved_at": "2026-08-08T03:00:00+00:00",
        "issuers": [official_row(row) for row in queue["queue"]],
        "failures": [],
        "orders": 0,
        "trade_authority": "NONE",
    }
    inbox_path = evidence_dir / "ROUND3_SEC_OBSERVER_INBOX.json"
    write_json(inbox_path, inbox)

    result = apply(tmp_path, inbox_path.relative_to(tmp_path), Path("automation/cross_market/round3_policy.json"))

    base = tmp_path / "investment_os_runtime/30_STATE_CURRENT/46_CROSS_MARKET_OPERATIONS"
    ledger = json.loads((base / "CROSS_MARKET_LIMITED_LEDGER_CURRENT.json").read_text())
    run_current = json.loads((base / "CROSS_MARKET_LIMITED_RUN_CURRENT.json").read_text())
    proposal = json.loads((base / "CROSS_MARKET_RESEARCH_PROPOSAL_CURRENT.json").read_text())
    cycle = ledger["weekly_cycles"]["2026-W32"]

    assert result["cycle_completed"] is True
    assert result["sec_official_retrieval_status"] == PASS_CONTROLLED
    assert cycle["sec_official_retrieval_status"] == PASS_CONTROLLED
    assert proposal["sec_official_retrieval_status"] == PASS_CONTROLLED
    assert run_current["united_states"]["sec_official_retrieval_status"] == PASS_CONTROLLED
    assert run_current["united_states"]["sec_retrieval_environment"] == CONTROLLED_EXTERNAL_ENVIRONMENT
    assert run_current["united_states"]["sec_official_success_claimed"] is True
    assert "CHATGPT_WEB" not in cycle["sec_official_retrieval_status"]
    assert validate(run_current, proposal, ledger, configured)["status"] == "ROUND3_OUTPUTS_VALID"
    assert result["orders"] == 0
    assert result["trade_authority"] == "NONE"
