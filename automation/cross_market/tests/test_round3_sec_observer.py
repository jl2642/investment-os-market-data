from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from automation.cross_market.apply_round3_sec_observer_results import apply, validate_inbox
from automation.cross_market.build_round3_limited_production import run
from automation.cross_market.tests.test_round3_limited_production import fake_fetcher, install, policy, write_json
from automation.cross_market.validate_round3_outputs import validate


def official_row(queued: dict) -> dict:
    cik = str(queued.get("cik") or "0001234567")
    resolution_source = "ACCEPTED_EVIDENCE" if queued["official_resolution_route"] == "CIK_DIRECT" else "SEC_COMPANY_TICKERS"
    sources = [
        f"https://data.sec.gov/submissions/CIK{cik}.json",
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
    ]
    if resolution_source == "SEC_COMPANY_TICKERS":
        sources.append("https://www.sec.gov/files/company_tickers.json")
    return {
        "canonical_issuer_id": queued["canonical_issuer_id"],
        "symbol": queued["symbol"],
        "cik": cik,
        "cik_resolution_source": resolution_source,
        "latest_filing_form": "10-Q",
        "latest_filing_date": "2026-08-01",
        "companyfacts_taxonomy_count": 1,
        "official_sources": sources,
        "status": "PASS_OFFICIAL_SEC_REFRESH",
    }


def prepare_completed_market_cycle(root: Path) -> tuple[dict, Path]:
    install(root)
    configured = policy()
    configured["united_states"]["minimum_weekly_official_sec_completed_count"] = 2
    configured["acceptance"]["completed_weekly_cycles_for_limited_production_acceptance"] = 1
    write_json(root / "automation/cross_market/round3_policy.json", configured)
    for offset in range(5):
        run(root, Path("automation/cross_market/round3_policy.json"), date(2026, 8, 3 + offset), fake_fetcher, sleep_seconds=0)
    run_current = json.loads((root / "investment_os_runtime/30_STATE_CURRENT/46_CROSS_MARKET_OPERATIONS/CROSS_MARKET_LIMITED_RUN_CURRENT.json").read_text())
    run_id = run_current["run_id"]
    evidence_dir = root / f"investment_os_runtime/40_EVIDENCE_AND_LINEAGE/CROSS_MARKET_LIMITED/{run_id}"
    return configured, evidence_dir


def test_official_observer_results_complete_cycle_and_accept_operating_state(tmp_path: Path) -> None:
    configured, evidence_dir = prepare_completed_market_cycle(tmp_path)
    queue = json.loads((evidence_dir / "ROUND3_SEC_OFFICIAL_RETRIEVAL_QUEUE.json").read_text())
    inbox = {
        "schema_version": "1.0.0",
        "run_id": queue["run_id"],
        "as_of_date": queue["as_of_date"],
        "retrieval_environment": "CHATGPT_WEB_CONTROLLED_OFFICIAL_RETRIEVAL",
        "retrieved_at": "2026-08-08T10:30:00+08:00",
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

    assert result["status"] == "ROUND3_SEC_OBSERVER_RESULTS_APPLIED"
    assert result["cycle_completed"] is True
    assert result["operating_state"] == "ROUND3_LIMITED_PRODUCTION_ACCEPTED"
    assert cycle["sec_official_completed_issuer_count"] == 2
    assert cycle["sec_official_retrieval_status"] == "PASS_CHATGPT_WEB_OFFICIAL_RETRIEVAL"
    assert run_current["united_states"]["sec_official_success_claimed"] is True
    assert proposal["status"] == "WEEKLY_RESEARCH_REVIEW_READY"
    assert (evidence_dir / "ROUND3_SEC_OFFICIAL_RETRIEVAL_RESULT.json").exists()
    assert (evidence_dir / "ROUND3_SEC_OBSERVER_MANIFEST.json").exists()
    assert validate(run_current, proposal, ledger, configured)["status"] == "ROUND3_OUTPUTS_VALID"


def test_observer_rejects_unqueued_issuer_and_authority_escalation(tmp_path: Path) -> None:
    _, evidence_dir = prepare_completed_market_cycle(tmp_path)
    queue = json.loads((evidence_dir / "ROUND3_SEC_OFFICIAL_RETRIEVAL_QUEUE.json").read_text())
    row = official_row(queue["queue"][0])
    row["canonical_issuer_id"] = "USISS-NOT-QUEUED"
    inbox = {
        "schema_version": "1.0.0",
        "run_id": queue["run_id"],
        "as_of_date": queue["as_of_date"],
        "retrieval_environment": "CHATGPT_WEB_CONTROLLED_OFFICIAL_RETRIEVAL",
        "retrieved_at": "2026-08-08T10:30:00+08:00",
        "issuers": [row],
        "failures": [],
        "orders": 0,
        "trade_authority": "NONE",
    }
    try:
        validate_inbox(inbox, queue)
    except SystemExit as exc:
        assert "NOT_QUEUED_OR_DUPLICATE" in str(exc)
    else:
        raise AssertionError("unqueued issuer must fail")

    inbox["issuers"] = []
    inbox["orders"] = 1
    try:
        validate_inbox(inbox, queue)
    except SystemExit as exc:
        assert "AUTHORITY_VIOLATION" in str(exc)
    else:
        raise AssertionError("observer authority escalation must fail")
