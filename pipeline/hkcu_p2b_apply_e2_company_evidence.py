#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

TRADE_AUTHORITY = "NONE"
DIMS = {
    "GOVERNANCE_VALUE_TRAP": "governance",
    "EARNINGS_EXPECTATION_REVISION": "earnings",
    "CATALYST": "catalyst",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rebuild_e1(root: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable, str(root / "pipeline/hkcu_p2b_apply_e1_evidence.py"),
        "--repo-root", str(root), "--output", str(out),
    ], check=True)
    subprocess.run([
        sys.executable, str(root / "scripts/validate_hkcu_p2b_e1.py"),
        "--output", str(out),
    ], check=True)


def expand_registry(wide: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, sec in wide.iterrows():
        for dimension, prefix in DIMS.items():
            status = str(sec[f"{prefix}_status"])
            rows.append({
                "batch_id": sec["batch_id"],
                "p2a_overall_rank": int(sec["p2a_overall_rank"]),
                "security_id": sec["security_id"],
                "stock_code_5d": str(sec["stock_code_5d"]).zfill(5),
                "security_name": sec["security_name"],
                "research_dimension": dimension,
                "evidence_status": status,
                "evidence_date": sec[f"{prefix}_date"],
                "source_authority": "HKEX",
                "source_type": "PRIMARY_OFFICIAL",
                "source_url": sec["source_url"],
                "evidence_title": sec[f"{prefix}_title"],
                "evidence_summary": sec[f"{prefix}_summary"],
                "evidence_count": 1 if status in {"EVIDENCE_PARTIAL", "EVIDENCE_COMPLETE"} else 0,
                "score": pd.NA,
                "score_status": "NO_ALPHA_SCORE",
                "next_action": (
                    "EVIDENCE_READY_FOR_P2B_SYNTHESIS" if status == "EVIDENCE_COMPLETE"
                    else "DEEPEN_COMPANY_EVIDENCE" if status == "EVIDENCE_PARTIAL"
                    else "COLLECT_EVIDENCE" if status == "RESEARCH_REQUIRED"
                    else "DATA_GAP_RETAINED"
                ),
                "trade_authority": TRADE_AUTHORITY,
            })
    return pd.DataFrame(rows)


def build(root: Path, out: Path) -> None:
    contract_path = root / "config/hkcu_p2b_e2_company_evidence_contract.json"
    evidence_path = root / "evidence/hkcu_p2b/HKCU_P2B_E2_COMPANY_EVIDENCE_TOP_QUARTILE_20260807.csv"
    contract = read_json(contract_path)
    wide = pd.read_csv(evidence_path, dtype={"stock_code_5d": str}, keep_default_na=False)
    evidence = expand_registry(wide)
    failures = []
    policy = contract["batch_policy"]

    if len(wide) != int(policy["batch_security_count"]):
        failures.append(f"WIDE_SECURITY_COUNT:{len(wide)}")
    if wide["security_id"].duplicated().any():
        failures.append("DUPLICATE_WIDE_SECURITY")
    expected_ranks = set(range(int(policy["required_rank_start"]), int(policy["required_rank_end"]) + 1))
    if set(pd.to_numeric(wide["p2a_overall_rank"], errors="coerce").dropna().astype(int)) != expected_ranks:
        failures.append("BATCH_RANK_SET_INVALID")
    if len(evidence) != int(policy["required_evidence_rows"]):
        failures.append(f"EVIDENCE_ROW_COUNT:{len(evidence)}")
    if evidence.duplicated(["security_id", "research_dimension"]).any():
        failures.append("DUPLICATE_SECURITY_DIMENSION")
    if set(evidence["research_dimension"]) != set(policy["required_dimensions"]):
        failures.append("DIMENSION_SET_INVALID")
    if not set(evidence["evidence_status"]).issubset(set(contract["evidence_policy"]["allowed_statuses"])):
        failures.append("STATUS_VOCABULARY_INVALID")
    if evidence["score"].notna().any():
        failures.append("ALPHA_SCORE_PRESENT_IN_E2")

    as_of = pd.Timestamp(policy["as_of_date"])
    for _, row in evidence.iterrows():
        date = pd.to_datetime(row["evidence_date"], errors="coerce")
        if pd.isna(date):
            failures.append(f"EVIDENCE_DATE_INVALID:{row['security_id']}:{row['research_dimension']}")
        elif date > as_of:
            failures.append(f"FUTURE_EVIDENCE:{row['security_id']}:{row['research_dimension']}")
        if row["evidence_status"] in {"EVIDENCE_PARTIAL", "EVIDENCE_COMPLETE"}:
            if not str(row["source_url"]).startswith("https://"):
                failures.append(f"HTTPS_SOURCE_REQUIRED:{row['security_id']}:{row['research_dimension']}")
            if not str(row["evidence_title"]).strip() or not str(row["evidence_summary"]).strip():
                failures.append(f"EVIDENCE_CONTENT_MISSING:{row['security_id']}:{row['research_dimension']}")

    e1 = out / "_e1_rebuild"
    rebuild_e1(root, e1)
    e1_dim = pd.read_csv(e1 / "HKCU_P2B_E1_DIMENSION_MATRIX.csv", dtype={"stock_code_5d": str})
    e1_queue = pd.read_csv(e1 / "HKCU_P2B_E1_REMAINING_RESEARCH_QUEUE.csv", dtype={"stock_code_5d": str})
    e1_decision = read_json(e1 / "HKCU_P2B_E1_DECISION.json")
    if e1_decision.get("status") != "PASS_P2B_E1_COMMON_AH_EVIDENCE":
        failures.append("UPSTREAM_E1_NOT_PASS")
    if len(e1_queue) != 231:
        failures.append(f"UPSTREAM_E1_QUEUE_NOT_231:{len(e1_queue)}")

    queue_keys = set(zip(e1_queue["security_id"], e1_queue["research_dimension"]))
    evidence_keys = set(zip(evidence["security_id"], evidence["research_dimension"]))
    if evidence_keys - queue_keys:
        failures.append("EVIDENCE_NOT_IN_E1_QUEUE")
    rank_map = e1_queue[["security_id", "p2a_overall_rank"]].drop_duplicates().set_index("security_id")["p2a_overall_rank"].to_dict()
    for _, row in evidence.iterrows():
        if int(row["p2a_overall_rank"]) != int(rank_map.get(row["security_id"], -1)):
            failures.append(f"RANK_MISMATCH:{row['security_id']}")

    dim = e1_dim.copy()
    idx_map = {(sid, rd): idx for idx, sid, rd in zip(dim.index, dim["security_id"], dim["research_dimension"])}
    for _, ev in evidence.iterrows():
        idx = idx_map.get((ev["security_id"], ev["research_dimension"]))
        if idx is None:
            failures.append(f"DIMENSION_ROW_MISSING:{ev['security_id']}:{ev['research_dimension']}")
            continue
        status = ev["evidence_status"]
        dim.at[idx, "evidence_status"] = status
        dim.at[idx, "evidence_count"] = int(ev["evidence_count"])
        dim.at[idx, "score"] = pd.NA
        dim.at[idx, "score_status"] = "EVIDENCE_COLLECTED_NO_ALPHA_SCORE" if status in {"EVIDENCE_PARTIAL", "EVIDENCE_COMPLETE"} else "NO_SCORE_BEFORE_EVIDENCE"
        dim.at[idx, "next_action"] = ev["next_action"]
        dim.at[idx, "applicability_reason"] = str(dim.at[idx, "applicability_reason"]) + "|E2:" + str(ev["batch_id"])

    company = dim[dim["research_dimension"].isin(DIMS)].copy()
    openq = company[company["evidence_status"] != "EVIDENCE_COMPLETE"].copy().sort_values(["p2a_overall_rank", "dimension_order", "security_id"]).reset_index(drop=True)
    openq.insert(0, "queue_rank", range(1, len(openq) + 1))
    unstarted = company[company["evidence_status"] == "RESEARCH_REQUIRED"].copy().sort_values(["p2a_overall_rank", "dimension_order", "security_id"]).reset_index(drop=True)
    unstarted.insert(0, "queue_rank", range(1, len(unstarted) + 1))

    complete = int((company["evidence_status"] == "EVIDENCE_COMPLETE").sum())
    partial = int((company["evidence_status"] == "EVIDENCE_PARTIAL").sum())
    collected = complete + partial
    if len(company) != 231:
        failures.append(f"COMPANY_DIMENSION_COUNT:{len(company)}")
    if company["score"].notna().any():
        failures.append("COMPANY_ALPHA_SCORE_PRESENT")
    if len(openq) != 231 - complete:
        failures.append("OPEN_QUEUE_COUNT_MISMATCH")

    out.mkdir(parents=True, exist_ok=True)
    ledger_path = out / "HKCU_P2B_E2_EVIDENCE_LEDGER.csv"
    dim_path = out / "HKCU_P2B_E2_DIMENSION_MATRIX.csv"
    open_path = out / "HKCU_P2B_E2_OPEN_RESEARCH_QUEUE.csv"
    unstarted_path = out / "HKCU_P2B_E2_UNSTARTED_QUEUE.csv"
    decision_path = out / "HKCU_P2B_E2_DECISION.json"
    quality_path = out / "HKCU_P2B_E2_QUALITY_REPORT.json"
    evidence.to_csv(ledger_path, index=False)
    dim.to_csv(dim_path, index=False)
    openq.to_csv(open_path, index=False)
    unstarted.to_csv(unstarted_path, index=False)

    decision = {
        "program_id": "HKCU-P2B-E2",
        "phase": "P2B_E2_COMPANY_SPECIFIC_EVIDENCE",
        "status": "PASS_P2B_E2_TOP_QUARTILE_BATCH" if not failures else "FAIL_P2B_E2",
        "accepted_longlist_count": 77,
        "batch_selection": "P2A_TOP_QUARTILE",
        "batch_security_count": int(wide["security_id"].nunique()),
        "batch_evidence_rows": int(len(evidence)),
        "evidence_collected_rows": collected,
        "evidence_complete_rows": complete,
        "evidence_partial_rows": partial,
        "company_specific_open_tasks": int(len(openq)),
        "company_specific_unstarted_tasks": int(len(unstarted)),
        "formal_candidate_graduation_allowed": False,
        "next_gate": contract["next_gate"] if not failures else "BLOCKED_REPAIR",
        "hard_failures": failures,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    quality = {
        "program_id": "HKCU-P2B-E2",
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": failures,
        "upstream_e1_status": e1_decision.get("status"),
        "upstream_company_task_count": 231,
        "batch_status_counts": {str(k): int(v) for k, v in evidence["evidence_status"].value_counts().items()},
        "company_status_counts_after_batch": {str(k): int(v) for k, v in company["evidence_status"].value_counts().items()},
        "score_non_null_count": int(company["score"].notna().sum()),
        "batch_rank_min": int(wide["p2a_overall_rank"].min()),
        "batch_rank_max": int(wide["p2a_overall_rank"].max()),
        "trade_authority": TRADE_AUTHORITY,
    }
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest_path = out / "HKCU_P2B_E2_MANIFEST.json"
    manifest = {
        "program_id": "HKCU-P2B-E2",
        "inputs": {
            str(contract_path.relative_to(root)): sha256_file(contract_path),
            str(evidence_path.relative_to(root)): sha256_file(evidence_path),
            "upstream_e1_decision_sha256": sha256_file(e1 / "HKCU_P2B_E1_DECISION.json"),
            "upstream_e1_dimension_matrix_sha256": sha256_file(e1 / "HKCU_P2B_E1_DIMENSION_MATRIX.csv"),
        },
        "outputs": {p.name: sha256_file(p) for p in [ledger_path, dim_path, open_path, unstarted_path, decision_path, quality_path]},
        "trade_authority": TRADE_AUTHORITY,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise SystemExit("P2B_E2_FAILED:" + "|".join(sorted(set(failures))))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
