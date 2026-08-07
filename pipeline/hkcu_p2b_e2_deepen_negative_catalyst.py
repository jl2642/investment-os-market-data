#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

PROGRAM_ID = "HKCU-P2B-E2-D1"
TRADE_AUTHORITY = "NONE"
TARGET_DIMENSION = "CATALYST"
NEGATIVE_FINDING = "NO_QUALIFYING_ACTIVE_CATALYST"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rebuild_batch4(root: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable,
        str(root / "pipeline/hkcu_p2b_apply_e2_batch4.py"),
        "--repo-root", str(root),
        "--output", str(out),
    ], check=True)
    subprocess.run([
        sys.executable,
        str(root / "scripts/validate_hkcu_p2b_e2_batch4.py"),
        "--output", str(out),
    ], check=True)


def build(root: Path, out: Path) -> None:
    contract_path = root / "config/hkcu_p2b_e2_deepening_d1_contract.json"
    contract = read_json(contract_path)
    out.mkdir(parents=True, exist_ok=True)
    b4 = out / "_batch4_rebuild"
    rebuild_batch4(root, b4)

    decision_b4 = read_json(b4 / "HKCU_P2B_E2_B4_DECISION.json")
    quality_b4 = read_json(b4 / "HKCU_P2B_E2_B4_QUALITY_REPORT.json")
    if decision_b4.get("status") != "PASS_P2B_E2_RANKS_61_77_BATCH" or quality_b4.get("status") != "PASS":
        raise SystemExit("UPSTREAM_BATCH4_NOT_PASS")

    ledger = pd.read_csv(
        b4 / "HKCU_P2B_E2_B4_CUMULATIVE_EVIDENCE_LEDGER.csv",
        dtype={"stock_code_5d": str},
        keep_default_na=False,
    )
    dim = pd.read_csv(
        b4 / "HKCU_P2B_E2_B4_DIMENSION_MATRIX.csv",
        dtype={"stock_code_5d": str},
    )
    failures: list[str] = []

    target = ledger[
        (ledger["research_dimension"] == TARGET_DIMENSION)
        & (ledger["evidence_status"] == "RESEARCH_REQUIRED")
    ].copy().sort_values(["p2a_overall_rank", "security_id"]).reset_index(drop=True)
    target["stock_code_5d"] = target["stock_code_5d"].astype(str).str.zfill(5)

    expected_codes = set(str(x).zfill(5) for x in contract["expected_target_codes"])
    actual_codes = set(target["stock_code_5d"])
    if len(target) != int(contract["expected_target_count"]):
        failures.append(f"TARGET_COUNT:{len(target)}")
    if actual_codes != expected_codes:
        failures.append("TARGET_CODE_SET_MISMATCH")
    if target["security_id"].duplicated().any():
        failures.append("DUPLICATE_TARGET_SECURITY")
    if target["research_dimension"].nunique() != 1 or not target["research_dimension"].eq(TARGET_DIMENSION).all():
        failures.append("TARGET_DIMENSION_INVALID")
    if not target["evidence_status"].eq("RESEARCH_REQUIRED").all():
        failures.append("TARGET_PRIOR_STATUS_INVALID")
    if not target["source_url"].astype(str).str.startswith("https://www1.hkexnews.hk/").all():
        failures.append("TARGET_NOT_HKEX_PRIMARY_SURFACE")
    if target["evidence_title"].astype(str).str.strip().eq("").any():
        failures.append("TARGET_PRIOR_REVIEW_TITLE_MISSING")
    if target["evidence_summary"].astype(str).str.strip().eq("").any():
        failures.append("TARGET_PRIOR_REVIEW_SUMMARY_MISSING")
    dates = pd.to_datetime(target["evidence_date"], errors="coerce")
    if dates.isna().any():
        failures.append("TARGET_PRIOR_REVIEW_DATE_INVALID")
    elif (dates > pd.Timestamp(contract["negative_evidence_policy"]["as_of_date"])).any():
        failures.append("TARGET_FUTURE_REVIEW_DATE")

    closure = target[[
        "p2a_overall_rank", "security_id", "stock_code_5d", "security_name",
        "source_url", "evidence_date", "evidence_title", "evidence_summary"
    ]].copy()
    closure = closure.rename(columns={
        "evidence_date": "latest_reviewed_event_date",
        "evidence_title": "latest_reviewed_event_title",
        "evidence_summary": "first_pass_review_summary",
    })
    closure.insert(0, "deepening_id", "P2B_E2_D1_NEGATIVE_CATALYST_20260807")
    closure["review_as_of_date"] = contract["negative_evidence_policy"]["as_of_date"]
    closure["research_dimension"] = TARGET_DIMENSION
    closure["prior_status"] = "RESEARCH_REQUIRED"
    closure["closure_status"] = "EVIDENCE_COMPLETE"
    closure["catalyst_outcome"] = NEGATIVE_FINDING
    closure["closure_reason"] = (
        "Primary HKEX disclosure surface was already reviewed in first pass; no unresolved event met the required dated, security-specific, falsifiable and directionally relevant catalyst standard as of 2026-08-07."
    )
    closure["directional_signal"] = "NONE"
    closure["alpha_score"] = pd.NA
    closure["trade_authority"] = TRADE_AUTHORITY

    # Build a one-row-per-company-dimension current evidence ledger by overwriting only the 23 closed catalyst keys.
    current_ledger = ledger.copy()
    current_ledger["stock_code_5d"] = current_ledger["stock_code_5d"].astype(str).str.zfill(5)
    current_ledger["deepening_review_as_of"] = ""
    current_ledger["deepening_finding"] = ""
    current_ledger["deepening_reason"] = ""
    closure_keys = set(zip(closure["security_id"], closure["research_dimension"]))
    for idx, row in current_ledger.iterrows():
        key = (row["security_id"], row["research_dimension"])
        if key not in closure_keys:
            continue
        current_ledger.at[idx, "evidence_status"] = "EVIDENCE_COMPLETE"
        current_ledger.at[idx, "evidence_count"] = 1
        current_ledger.at[idx, "score"] = pd.NA
        current_ledger.at[idx, "score_status"] = "NEGATIVE_CATALYST_FINDING_NO_ALPHA_SCORE"
        current_ledger.at[idx, "next_action"] = "MONITOR_FOR_NEW_CATALYST"
        current_ledger.at[idx, "deepening_review_as_of"] = contract["negative_evidence_policy"]["as_of_date"]
        current_ledger.at[idx, "deepening_finding"] = NEGATIVE_FINDING
        current_ledger.at[idx, "deepening_reason"] = (
            "No qualifying active catalyst identified on reviewed primary HKEX disclosure surface as of the review date."
        )

    idx_map = {
        (sid, rd): idx
        for idx, sid, rd in zip(dim.index, dim["security_id"], dim["research_dimension"])
    }
    for _, row in closure.iterrows():
        idx = idx_map.get((row["security_id"], TARGET_DIMENSION))
        if idx is None:
            failures.append(f"DIMENSION_ROW_MISSING:{row['security_id']}")
            continue
        if str(dim.at[idx, "evidence_status"]) != "RESEARCH_REQUIRED":
            failures.append(f"DIMENSION_PRIOR_STATUS_NOT_REQUIRED:{row['security_id']}")
            continue
        dim.at[idx, "evidence_status"] = "EVIDENCE_COMPLETE"
        dim.at[idx, "evidence_count"] = 1
        dim.at[idx, "score"] = pd.NA
        dim.at[idx, "score_status"] = "NEGATIVE_CATALYST_FINDING_NO_ALPHA_SCORE"
        dim.at[idx, "next_action"] = "MONITOR_FOR_NEW_CATALYST"
        dim.at[idx, "applicability_reason"] = (
            str(dim.at[idx, "applicability_reason"])
            + "|E2_D1:NO_QUALIFYING_ACTIVE_CATALYST_AS_OF_20260807"
        )

    company = dim[dim["research_dimension"].isin(["GOVERNANCE_VALUE_TRAP", "EARNINGS_EXPECTATION_REVISION", "CATALYST"])].copy()
    status_counts = company["evidence_status"].value_counts().to_dict()
    expected = contract["expected_cumulative_after_d1"]
    for status in ["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL", "RESEARCH_REQUIRED"]:
        if int(status_counts.get(status, 0)) != int(expected[status]):
            failures.append(f"STATUS_COUNT:{status}:{int(status_counts.get(status,0))}")
    if len(company) != int(expected["company_specific_dimension_rows"]):
        failures.append(f"COMPANY_DIMENSION_ROWS:{len(company)}")
    if company["score"].notna().any():
        failures.append("ALPHA_SCORE_PRESENT")

    openq = company[company["evidence_status"] != "EVIDENCE_COMPLETE"].copy().sort_values(
        ["p2a_overall_rank", "dimension_order", "security_id"]
    ).reset_index(drop=True)
    openq.insert(0, "queue_rank", range(1, len(openq) + 1))
    unstarted = company[company["evidence_status"] == "RESEARCH_REQUIRED"].copy().sort_values(
        ["p2a_overall_rank", "dimension_order", "security_id"]
    ).reset_index(drop=True)
    unstarted.insert(0, "queue_rank", range(1, len(unstarted) + 1))
    if len(openq) != int(expected["company_specific_open_tasks"]):
        failures.append(f"OPEN_TASK_COUNT:{len(openq)}")
    if len(unstarted) != int(expected["company_specific_unstarted_tasks"]):
        failures.append(f"UNSTARTED_TASK_COUNT:{len(unstarted)}")
    if len(closure) != int(expected["negative_catalyst_closure_count"]):
        failures.append(f"CLOSURE_COUNT:{len(closure)}")
    if company["security_id"].nunique() != 77:
        failures.append("ALL_77_NOT_PRESENT")

    closure_path = out / "HKCU_P2B_E2_D1_NEGATIVE_CATALYST_CLOSURES.csv"
    ledger_path = out / "HKCU_P2B_E2_D1_CURRENT_EVIDENCE_LEDGER.csv"
    dim_path = out / "HKCU_P2B_E2_D1_DIMENSION_MATRIX.csv"
    open_path = out / "HKCU_P2B_E2_D1_OPEN_RESEARCH_QUEUE.csv"
    unstarted_path = out / "HKCU_P2B_E2_D1_UNSTARTED_QUEUE.csv"
    decision_path = out / "HKCU_P2B_E2_D1_DECISION.json"
    quality_path = out / "HKCU_P2B_E2_D1_QUALITY_REPORT.json"

    closure.to_csv(closure_path, index=False)
    current_ledger.to_csv(ledger_path, index=False)
    dim.to_csv(dim_path, index=False)
    openq.to_csv(open_path, index=False)
    unstarted.to_csv(unstarted_path, index=False)

    decision = {
        "program_id": PROGRAM_ID,
        "phase": contract["phase"],
        "status": "PASS_P2B_E2_D1_NEGATIVE_CATALYST_CLOSURE" if not failures else "FAIL_P2B_E2_D1",
        "accepted_longlist_count": 77,
        "negative_catalyst_closure_count": int(len(closure)),
        "company_specific_complete_tasks": int((company["evidence_status"] == "EVIDENCE_COMPLETE").sum()),
        "company_specific_partial_tasks": int((company["evidence_status"] == "EVIDENCE_PARTIAL").sum()),
        "company_specific_research_required_tasks": int((company["evidence_status"] == "RESEARCH_REQUIRED").sum()),
        "company_specific_open_tasks": int(len(openq)),
        "company_specific_unstarted_tasks": int(len(unstarted)),
        "all_77_securities_started": True,
        "negative_finding_is_not_bearish_score": True,
        "formal_candidate_graduation_allowed": False,
        "next_gate": contract["next_gate"] if not failures else "BLOCKED_REPAIR",
        "hard_failures": sorted(set(failures)),
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    quality = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not failures else "FAIL",
        "upstream_batch4_status": decision_b4.get("status"),
        "target_count": int(len(target)),
        "target_code_set_matches_contract": actual_codes == expected_codes,
        "closure_finding": NEGATIVE_FINDING,
        "company_status_counts": {str(k): int(v) for k, v in status_counts.items()},
        "score_non_null_count": int(company["score"].notna().sum()),
        "hard_failures": sorted(set(failures)),
        "trade_authority": TRADE_AUTHORITY,
    }
    write_json(decision_path, decision)
    write_json(quality_path, quality)

    outputs = [closure_path, ledger_path, dim_path, open_path, unstarted_path, decision_path, quality_path]
    manifest = {
        "program_id": PROGRAM_ID,
        "inputs": {
            str(contract_path.relative_to(root)): sha256_file(contract_path),
            "upstream_batch4_decision_sha256": sha256_file(b4 / "HKCU_P2B_E2_B4_DECISION.json"),
            "upstream_batch4_evidence_ledger_sha256": sha256_file(b4 / "HKCU_P2B_E2_B4_CUMULATIVE_EVIDENCE_LEDGER.csv"),
        },
        "outputs": {p.name: sha256_file(p) for p in outputs},
        "trade_authority": TRADE_AUTHORITY,
    }
    write_json(out / "HKCU_P2B_E2_D1_MANIFEST.json", manifest)

    if failures:
        raise SystemExit("P2B_E2_D1_FAILED:" + "|".join(sorted(set(failures))))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
