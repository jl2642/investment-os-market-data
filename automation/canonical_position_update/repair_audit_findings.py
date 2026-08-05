#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BRANCH_PENDING = "PENDING_PR_MERGE"

PATHS = {
    "real_source": ROOT / "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_CURRENT.json",
    "real": ROOT / "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json",
    "sim_source": ROOT / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_LEDGER_CURRENT.json",
    "sim": ROOT / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json",
    "marks": ROOT / "investment_os_runtime/30_STATE_CURRENT/25_PORTFOLIO_MARKS/PORTFOLIO_MARKS_CURRENT.json",
    "run": ROOT / "investment_os_runtime/30_STATE_CURRENT/70_OPERATIONS/PORTFOLIO_CURRENT_RUN_CURRENT.json",
    "acceptance": ROOT / "investment_os_runtime/00_CONTROL/WP2_R_PORTFOLIO_CURRENT_ACCEPTANCE_RECORD.json",
    "evidence": ROOT / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/POSITION_UPDATE_2026_08_04/USER_CONFIRMED_INTRADAY_SNAPSHOT_20260804.json",
    "run_manifest": ROOT / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1/RUN_MANIFESTS/POSITION_UPDATE_20260804_USER_INTRADAY.json",
    "report_manifest": ROOT / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1/REPORT_MANIFESTS/POSITION_UPDATE_20260804_USER_INTRADAY.json",
    "status_product": ROOT / "investment_os_runtime/50_OPERATING_PRODUCTS/OBSERVATION/STATUS/POSITION_UPDATE_STATUS_20260804_USER_INTRADAY.json",
    "operating_ledger": ROOT / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1/OPERATING_RUN_LEDGER_CURRENT.json",
}
WORKFLOW = ROOT / ".github/workflows/wp2_r_portfolio_current.yml"


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def replace_exception(exceptions: list[dict[str, Any]], exception_id: str, payload: dict[str, Any]) -> None:
    for index, item in enumerate(exceptions):
        if item.get("exception_id") == exception_id:
            exceptions[index] = payload
            return
    exceptions.append(payload)


def repair() -> None:
    real_source = read(PATHS["real_source"])
    real = read(PATHS["real"])
    sim_source = read(PATHS["sim_source"])
    sim = read(PATHS["sim"])
    marks = read(PATHS["marks"])
    run = read(PATHS["run"])
    acceptance = read(PATHS["acceptance"])
    evidence = read(PATHS["evidence"])
    run_manifest = read(PATHS["run_manifest"])
    report_manifest = read(PATHS["report_manifest"])
    status_product = read(PATHS["status_product"])
    operating_ledger = read(PATHS["operating_ledger"])

    # Correct disclosed comparisons. These are account-total comparisons, not line-sum comparisons.
    real_difference = round(float(real["summary"]["account_total_assets"]) - float(real["summary"]["historical_wp2_3_total_assets"]), 6)
    sim_difference = round(float(sim["summary"]["account_total_assets"]) - float(sim["summary"]["historical_wp2_3_total_assets"]), 6)
    assert real_difference == 162901.95
    assert sim_difference == 12448.0
    real["summary"]["difference_vs_historical_wp2_3"] = real_difference
    sim["summary"]["difference_vs_historical_wp2_3"] = sim_difference

    # Replace stale source limitations with the actual intraday and equity-compensation limits.
    real_source["limitations"] = [
        "USER_CONFIRMED_INTRADAY_NOT_FORMAL_EOD",
        "BROKER_STOCK_TOTAL_LINE_SUM_EXCEPTION_237_50_UNALLOCATED",
        "605090_CURRENT_4950_BATCH_IDENTITY_UNRESOLVED",
        "605090_SECOND_4950_PENDING_ZERO_MARKET_VALUE",
        "605090_TAX_BASIS_AND_FEES_PENDING_DOCUMENTATION",
    ]
    real_source["summary"]["source_as_of"] = "2026-08-04T09:51:00+08:00"
    real_source["summary"]["source_run_id"] = "POSITION_UPDATE_20260804_USER_INTRADAY"
    real_source["summary"]["source_schema_version"] = "3.5.0"

    # Remove stale close-price and promoted-state labels from the Simulation source summary.
    sim_summary = sim_source["summary"]
    sim_summary["market_value"] = 799495.1
    sim_summary["position_pct"] = "78.29%"
    sim_summary["position_ratio"] = 0.7829
    sim_summary["pricing_caveat"] = (
        "User-confirmed intraday simulation snapshot at approximately 09:52 Asia/Shanghai; "
        "not a formal EOD close. Quantities and unit costs are unchanged because no new trade was confirmed."
    )
    sim_summary["promotion_status"] = "USER_CONFIRMED_INTRADAY_PROVISIONAL"
    sim_summary["snapshot_type"] = "USER_CONFIRMED_INTRADAY"
    sim_summary["source_as_of"] = "2026-08-04T09:52:00+08:00"
    sim_summary["source_run_id"] = "POSITION_UPDATE_20260804_USER_INTRADAY"
    sim_summary["source_schema_version"] = "3.5.0"
    sim_source["limitations"] = [
        "USER_CONFIRMED_INTRADAY_NOT_FORMAL_EOD",
        "NO_NEW_SIMULATION_TRADES_CONFIRMED",
        "TOP_MARKET_VALUE_LINE_SUM_EXCEPTION_NEGATIVE_43_UNALLOCATED",
        "LEGACY_TRADE_LEDGER_RETAINED_FOR_HISTORY_ONLY",
    ]

    # Correct Current-run disclosures and include settlement/identity triggers.
    run["real_difference_vs_historical_wp2_3"] = real_difference
    run["simulation_difference_vs_historical_wp2_3"] = sim_difference
    run["next_user_input_trigger"] = (
        "WHEN_REAL_OR_SIMULATION_TRANSACTION_OCCURS_OR_605090_BATCH_IDENTITY_SETTLEMENT_TAX_OR_FEE_EVIDENCE_CHANGES"
    )

    controls = acceptance["account_summary_controls"]
    controls["real_difference_disclosed"] = real_difference
    controls["simulation_difference_disclosed"] = sim_difference
    controls["reported_total_reconciliation_exceptions_preserved"] = True
    controls["real_reported_total_formula"] = "POSITION_MARKET_VALUE_PLUS_EXECUTION_CASH_PLUS_UNALLOCATED_EXCEPTION"
    controls["simulation_reported_total_formula"] = "TOP_MARKET_VALUE_PLUS_AVAILABLE_CASH"

    # Evidence boundary: referenced files were not mounted in this conversation and were not inspected.
    evidence.pop("input_files", None)
    evidence["input_evidence"] = [
        {
            "type": "USER_PASTED_HANDOFF_TEXT",
            "status": "AVAILABLE_AND_USED",
            "scope": "STRUCTURED_FACTS_AND_NUMERIC_VALUES_IN_CHAT",
        },
        {
            "type": "REFERENCED_FILE",
            "name": "canonical_position_update_2026-08-04.json",
            "status": "NOT_MOUNTED_NOT_INSPECTED_IN_CURRENT_CONVERSATION",
        },
        {
            "type": "REFERENCED_FILE",
            "name": "持仓更新与风险复核_2026-08-04.xlsx",
            "status": "NOT_MOUNTED_NOT_INSPECTED_IN_CURRENT_CONVERSATION",
        },
    ]
    evidence["input_reconciliation"] = "NOT_PERFORMED_REFERENCED_FILES_NOT_MOUNTED; USER_PASTED_HANDOFF_USED"
    evidence["economic_state_commit"] = BRANCH_PENDING
    evidence["economic_state_commit_role"] = "TO_BE_RESOLVED_BY_PULL_REQUEST_MERGE"

    evidence_exception = {
        "exception_id": "REFERENCED_INPUT_FILES_NOT_MOUNTED",
        "status": "OPEN_EVIDENCE_BOUNDARY",
        "treatment": "USE_USER_PASTED_HANDOFF; DO_NOT_CLAIM_FILE_RECONCILIATION",
    }
    replace_exception(run_manifest["exceptions"], evidence_exception["exception_id"], evidence_exception)
    replace_exception(report_manifest["exceptions"], evidence_exception["exception_id"], evidence_exception)
    replace_exception(status_product["exceptions"], evidence_exception["exception_id"], evidence_exception)

    source_inputs = [
        "USER_PASTED_HANDOFF_TEXT_2026-08-05",
        "REFERENCED_NOT_MOUNTED:canonical_position_update_2026-08-04.json",
        "REFERENCED_NOT_MOUNTED:持仓更新与风险复核_2026-08-04.xlsx",
        "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_CURRENT.json@84544c3",
        "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_LEDGER_CURRENT.json@84544c3",
        "investment_os_runtime/30_STATE_CURRENT/15_PORTFOLIO_INPUT/USER_TRANSACTION_DELTA_LEDGER_CURRENT.json@84544c3",
    ]
    run_manifest["inputs"] = source_inputs
    run_manifest["canonical_commit_after"] = BRANCH_PENDING
    run_manifest["canonical_commit_after_role"] = "TO_BE_RESOLVED_BY_PULL_REQUEST_MERGE"
    run_manifest["evidence_boundary"] = "REFERENCED_FILES_NOT_MOUNTED; USER_PASTED_HANDOFF_USED"
    report_manifest["input_assets"] = source_inputs
    report_manifest["canonical_commit_sha"] = BRANCH_PENDING
    report_manifest["canonical_commit_sha_role"] = "TO_BE_RESOLVED_BY_PULL_REQUEST_MERGE"
    report_manifest["evidence_boundary"] = "REFERENCED_FILES_NOT_MOUNTED; USER_PASTED_HANDOFF_USED"
    status_product["economic_state_commit"] = BRANCH_PENDING
    status_product["economic_state_commit_role"] = "TO_BE_RESOLVED_BY_PULL_REQUEST_MERGE"
    status_product["evidence_boundary"] = "REFERENCED_FILES_NOT_MOUNTED; USER_PASTED_HANDOFF_USED"
    operating_ledger["status"] = "PASS_WITH_EXCEPTIONS_REMOTE_PR_GATES_PENDING"
    operating_ledger["entries"][0]["validation_status"] = "LOCAL_BRANCH_VALIDATION_PASS_REMOTE_PR_GATES_PENDING"
    operating_ledger["entries"][0]["exception_count"] = 5

    # Write state before computing semantic hashes.
    write(PATHS["real_source"], real_source)
    write(PATHS["real"], real)
    write(PATHS["sim_source"], sim_source)
    write(PATHS["sim"], sim)
    write(PATHS["run"], run)
    write(PATHS["evidence"], evidence)
    write(PATHS["run_manifest"], run_manifest)
    write(PATHS["report_manifest"], report_manifest)
    write(PATHS["status_product"], status_product)
    write(PATHS["operating_ledger"], operating_ledger)

    # Recompute all semantic hashes tied to Current outputs.
    acceptance["outputs"]["real_positions"]["semantic_hash"] = digest(real)
    acceptance["outputs"]["simulation_positions"]["semantic_hash"] = digest(sim)
    acceptance["outputs"]["run_current"]["semantic_hash"] = digest(run)
    acceptance["outputs"]["portfolio_marks"]["semantic_hash"] = digest(marks)
    write(PATHS["acceptance"], acceptance)

    # Repair the WP2-R formula without allocating the broker exception to a security.
    workflow = WORKFLOW.read_text(encoding="utf-8")
    old = "assert real['summary']['account_total_assets'] == round(real['summary']['position_market_value'] + real['summary']['execution_cash_balance'], 6)"
    new = "assert real['summary']['account_total_assets'] == round(real['summary']['position_market_value'] + real['summary']['execution_cash_balance'] + real['summary']['broker_reconciliation_exception_amount'], 6)"
    if old in workflow:
        workflow = workflow.replace(old, new)
    assert new in workflow
    WORKFLOW.write_text(workflow, encoding="utf-8")

    # Final audit assertions.
    assert real["summary"]["account_total_assets"] == round(
        real["summary"]["position_market_value"]
        + real["summary"]["execution_cash_balance"]
        + real["summary"]["broker_reconciliation_exception_amount"], 6
    )
    assert sim["summary"]["account_total_assets"] == round(
        sim["summary"]["top_market_value_reported"] + sim["summary"]["execution_cash_balance"], 6
    )
    assert real_source["limitations"][0] == "USER_CONFIRMED_INTRADAY_NOT_FORMAL_EOD"
    assert sim_source["summary"]["snapshot_type"] == "USER_CONFIRMED_INTRADAY"
    assert evidence["input_reconciliation"].startswith("NOT_PERFORMED")
    assert run_manifest["canonical_commit_after"] == BRANCH_PENDING
    assert acceptance["trade_authority"] == run["trade_authority"] == "NONE"
    assert run["orders"] == 0

    print(json.dumps({
        "status": "PASS",
        "real_difference_vs_historical": real_difference,
        "simulation_difference_vs_historical": sim_difference,
        "real_reconciliation_exception": real["summary"]["broker_reconciliation_exception_amount"],
        "simulation_reconciliation_exception": sim["summary"]["market_value_reconciliation_exception_amount"],
        "evidence_boundary": "USER_PASTED_HANDOFF_USED_REFERENCED_FILES_NOT_MOUNTED",
        "orders": 0,
        "trade_authority": "NONE",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    repair()
