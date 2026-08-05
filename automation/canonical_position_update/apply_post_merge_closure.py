#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CLOSURE = ROOT / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1/POSITION_UPDATE_POST_MERGE_CLOSURE_CURRENT.json"
PATHS = {
    "evidence": ROOT / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/POSITION_UPDATE_2026_08_04/USER_CONFIRMED_INTRADAY_SNAPSHOT_20260804.json",
    "run_manifest": ROOT / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1/RUN_MANIFESTS/POSITION_UPDATE_20260804_USER_INTRADAY.json",
    "report_manifest": ROOT / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1/REPORT_MANIFESTS/POSITION_UPDATE_20260804_USER_INTRADAY.json",
    "status_product": ROOT / "investment_os_runtime/50_OPERATING_PRODUCTS/OBSERVATION/STATUS/POSITION_UPDATE_STATUS_20260804_USER_INTRADAY.json",
    "operating_ledger": ROOT / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/P0_I1/OPERATING_RUN_LEDGER_CURRENT.json",
}


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    if not CLOSURE.exists():
        print(json.dumps({"status": "SKIP_NO_POST_MERGE_CLOSURE_RECORD"}))
        return

    closure = read(CLOSURE)
    merge_sha = str(closure["economic_state_merge_sha"])
    pr_number = int(closure["economic_state_pr"])
    merged_at = str(closure["economic_state_merged_at"])
    closure_id = str(closure["closure_id"])
    remote_gates = closure["remote_gate_results"]

    assert re.fullmatch(r"[0-9a-f]{40}", merge_sha)
    assert pr_number == 165
    assert closure["closure_scope"] == "EVIDENCE_AND_LINEAGE_ONLY_NO_ECONOMIC_STATE_MUTATION"
    assert closure["orders"] == 0
    assert closure["trade_authority"] == "NONE"
    assert all(item["status"] == "PASS" for item in remote_gates.values())
    assert closure["non_mutation_proof"] == {
        "real_or_simulation_economic_state_mutations": 0,
        "candidate_mutations": 0,
        "decision_mutations": 0,
        "order_mutations": 0,
        "formal_eod_mutations": 0,
    }

    evidence = read(PATHS["evidence"])
    evidence["economic_state_commit"] = merge_sha
    evidence["economic_state_commit_role"] = "PR_165_MERGE_SHA_CANONICAL_ON_MAIN"
    evidence["economic_state_pr"] = pr_number
    evidence["canonicalized_at"] = merged_at
    evidence["post_merge_closure_id"] = closure_id

    run_manifest = read(PATHS["run_manifest"])
    run_manifest["canonical_commit_after"] = merge_sha
    run_manifest["canonical_commit_after_role"] = "PR_165_MERGE_SHA_CANONICAL_ON_MAIN"
    run_manifest["economic_state_pr"] = pr_number
    run_manifest["canonicalized_at"] = merged_at
    run_manifest["post_merge_closure_id"] = closure_id
    run_manifest["remote_gate_results"] = remote_gates
    run_manifest["status"] = "PASS_WITH_EXCEPTIONS_CANONICAL_ON_MAIN"

    report_manifest = read(PATHS["report_manifest"])
    report_manifest["canonical_commit_sha"] = merge_sha
    report_manifest["canonical_commit_sha_role"] = "PR_165_MERGE_SHA_CANONICAL_ON_MAIN"
    report_manifest["economic_state_pr"] = pr_number
    report_manifest["canonicalized_at"] = merged_at
    report_manifest["post_merge_closure_id"] = closure_id
    report_manifest["publication_status"] = "CANONICAL_ON_MAIN"

    status_product = read(PATHS["status_product"])
    status_product["economic_state_commit"] = merge_sha
    status_product["economic_state_commit_role"] = "PR_165_MERGE_SHA_CANONICAL_ON_MAIN"
    status_product["economic_state_pr"] = pr_number
    status_product["canonicalized_at"] = merged_at
    status_product["post_merge_closure_id"] = closure_id
    status_product["canonical_status"] = "CANONICAL_ON_MAIN"
    status_product["remote_gate_results"] = remote_gates

    operating_ledger = read(PATHS["operating_ledger"])
    assert operating_ledger["run_count"] == 1
    assert operating_ledger["orders"] == 0
    assert operating_ledger["trade_authority"] == "NONE"
    operating_ledger["status"] = "PASS_WITH_EXCEPTIONS_CANONICAL_ON_MAIN"
    operating_ledger["post_merge_closure_id"] = closure_id
    entry = operating_ledger["entries"][0]
    entry["economic_state_commit"] = merge_sha
    entry["economic_state_pr"] = pr_number
    entry["economic_state_merged_at"] = merged_at
    entry["validation_status"] = "REMOTE_PR_GATES_PASS_MERGED_TO_MAIN"
    entry["remote_gate_results"] = remote_gates

    for path, payload in [
        (PATHS["evidence"], evidence),
        (PATHS["run_manifest"], run_manifest),
        (PATHS["report_manifest"], report_manifest),
        (PATHS["status_product"], status_product),
        (PATHS["operating_ledger"], operating_ledger),
    ]:
        write(path, payload)

    # Final no-authority / no-order assertions across closure outputs.
    assert evidence["trade_authority"] == "NONE" and evidence["orders"] == 0
    assert run_manifest["trade_authority"] == "NONE" and run_manifest["orders"] == 0
    assert report_manifest["trade_authority"] == "NONE"
    assert status_product["trade_authority"] == "NONE" and status_product["orders"] == 0
    assert operating_ledger["trade_authority"] == "NONE" and operating_ledger["orders"] == 0

    print(json.dumps({
        "status": "PASS_POST_MERGE_CLOSURE_APPLIED",
        "economic_state_pr": pr_number,
        "economic_state_merge_sha": merge_sha,
        "outputs_updated": len(PATHS),
        "economic_state_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
