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


def rebuild_previous_e2(root: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable,
        str(root / "pipeline/hkcu_p2b_apply_e2_company_evidence.py"),
        "--repo-root", str(root),
        "--output", str(out),
    ], check=True)
    subprocess.run([
        sys.executable,
        str(root / "scripts/validate_hkcu_p2b_e2.py"),
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
    contract_path = root / "config/hkcu_p2b_e2_rank21_40_contract.json"
    evidence_path = root / "evidence/hkcu_p2b/HKCU_P2B_E2_COMPANY_EVIDENCE_RANK21_40_20260807.csv"
    contract = read_json(contract_path)
    policy = contract["batch_policy"]
    cumulative_expected = contract["cumulative_acceptance"]
    failures: list[str] = []

    previous = out / "_previous_top20"
    rebuild_previous_e2(root, previous)
    previous_decision = read_json(previous / "HKCU_P2B_E2_DECISION.json")
    if previous_decision.get("status") != "PASS_P2B_E2_TOP_QUARTILE_BATCH":
        failures.append("UPSTREAM_TOP20_NOT_PASS")

    previous_ledger = pd.read_csv(
        previous / "HKCU_P2B_E2_EVIDENCE_LEDGER.csv",
        dtype={"stock_code_5d": str},
        keep_default_na=False,
    )
    dim = pd.read_csv(
        previous / "HKCU_P2B_E2_DIMENSION_MATRIX.csv",
        dtype={"stock_code_5d": str},
    )
    wide = pd.read_csv(evidence_path, dtype={"stock_code_5d": str}, keep_default_na=False)
    evidence = expand_registry(wide)

    if len(wide) != int(policy["batch_security_count"]):
        failures.append(f"WIDE_SECURITY_COUNT:{len(wide)}")
    if wide["security_id"].duplicated().any():
        failures.append("DUPLICATE_WIDE_SECURITY")
    expected_ranks = set(range(int(policy["required_rank_start"]), int(policy["required_rank_end"]) + 1))
    actual_ranks = set(pd.to_numeric(wide["p2a_overall_rank"], errors="coerce").dropna().astype(int))
    if actual_ranks != expected_ranks:
        failures.append("BATCH_RANK_SET_INVALID")
    if len(evidence) != int(policy["required_evidence_rows"]):
        failures.append(f"EVIDENCE_ROW_COUNT:{len(evidence)}")
    if evidence.duplicated(["security_id", "research_dimension"]).any():
        failures.append("DUPLICATE_SECURITY_DIMENSION")
    if set(evidence["research_dimension"]) != set(policy["required_dimensions"]):
        failures.append("DIMENSION_SET_INVALID")
    if not set(evidence["evidence_status"]).issubset(set(policy["allowed_statuses"])):
        failures.append("STATUS_VOCABULARY_INVALID")
    if evidence["score"].notna().any():
        failures.append("ALPHA_SCORE_PRESENT_IN_BATCH")

    as_of = pd.Timestamp(policy["as_of_date"])
    for _, row in evidence.iterrows():
        ev_date = pd.to_datetime(row["evidence_date"], errors="coerce")
        if pd.isna(ev_date):
            failures.append(f"EVIDENCE_DATE_INVALID:{row['security_id']}:{row['research_dimension']}")
        elif ev_date > as_of:
            failures.append(f"FUTURE_EVIDENCE:{row['security_id']}:{row['research_dimension']}")
        if row["evidence_status"] in {"EVIDENCE_PARTIAL", "EVIDENCE_COMPLETE"}:
            if not str(row["source_url"]).startswith("https://www1.hkexnews.hk/"):
                failures.append(f"HKEX_SOURCE_REQUIRED:{row['security_id']}:{row['research_dimension']}")
            if not str(row["evidence_title"]).strip() or not str(row["evidence_summary"]).strip():
                failures.append(f"EVIDENCE_CONTENT_MISSING:{row['security_id']}:{row['research_dimension']}")

    status_counts = evidence["evidence_status"].value_counts().to_dict()
    collected = int(evidence["evidence_status"].isin(["EVIDENCE_PARTIAL", "EVIDENCE_COMPLETE"]).sum())
    complete = int((evidence["evidence_status"] == "EVIDENCE_COMPLETE").sum())
    partial = int((evidence["evidence_status"] == "EVIDENCE_PARTIAL").sum())
    research_required = int((evidence["evidence_status"] == "RESEARCH_REQUIRED").sum())
    if collected != int(policy["expected_collected_rows"]):
        failures.append(f"BATCH_COLLECTED_COUNT:{collected}")
    if complete != int(policy["expected_complete_rows"]):
        failures.append(f"BATCH_COMPLETE_COUNT:{complete}")
    if partial != int(policy["expected_partial_rows"]):
        failures.append(f"BATCH_PARTIAL_COUNT:{partial}")
    if research_required != int(policy["expected_research_required_rows"]):
        failures.append(f"BATCH_RESEARCH_REQUIRED_COUNT:{research_required}")

    previous_keys = set(zip(previous_ledger["security_id"], previous_ledger["research_dimension"]))
    new_keys = set(zip(evidence["security_id"], evidence["research_dimension"]))
    if previous_keys & new_keys:
        failures.append("BATCH_OVERLAPS_TOP20_EVIDENCE")

    idx_map = {(sid, rd): idx for idx, sid, rd in zip(dim.index, dim["security_id"], dim["research_dimension"])}
    rank_map = dim[["security_id", "p2a_overall_rank"]].drop_duplicates().set_index("security_id")["p2a_overall_rank"].to_dict()
    for _, ev in evidence.iterrows():
        key = (ev["security_id"], ev["research_dimension"])
        idx = idx_map.get(key)
        if idx is None:
            failures.append(f"DIMENSION_ROW_MISSING:{ev['security_id']}:{ev['research_dimension']}")
            continue
        if int(rank_map.get(ev["security_id"], -1)) != int(ev["p2a_overall_rank"]):
            failures.append(f"RANK_MISMATCH:{ev['security_id']}")
        if str(dim.at[idx, "evidence_status"]) != "RESEARCH_REQUIRED":
            failures.append(f"BATCH_TARGET_NOT_UNSTARTED:{ev['security_id']}:{ev['research_dimension']}")
        status = ev["evidence_status"]
        dim.at[idx, "evidence_status"] = status
        dim.at[idx, "evidence_count"] = int(ev["evidence_count"])
        dim.at[idx, "score"] = pd.NA
        dim.at[idx, "score_status"] = (
            "EVIDENCE_COLLECTED_NO_ALPHA_SCORE"
            if status in {"EVIDENCE_PARTIAL", "EVIDENCE_COMPLETE"}
            else "NO_SCORE_BEFORE_EVIDENCE"
        )
        dim.at[idx, "next_action"] = ev["next_action"]
        dim.at[idx, "applicability_reason"] = str(dim.at[idx, "applicability_reason"]) + "|E2:" + str(ev["batch_id"])

    cumulative_ledger = pd.concat([previous_ledger, evidence], ignore_index=True)
    if cumulative_ledger.duplicated(["security_id", "research_dimension"]).any():
        failures.append("CUMULATIVE_DUPLICATE_SECURITY_DIMENSION")

    company = dim[dim["research_dimension"].isin(DIMS)].copy()
    openq = company[company["evidence_status"] != "EVIDENCE_COMPLETE"].copy().sort_values(
        ["p2a_overall_rank", "dimension_order", "security_id"]
    ).reset_index(drop=True)
    openq.insert(0, "queue_rank", range(1, len(openq) + 1))
    unstarted = company[company["evidence_status"] == "RESEARCH_REQUIRED"].copy().sort_values(
        ["p2a_overall_rank", "dimension_order", "security_id"]
    ).reset_index(drop=True)
    unstarted.insert(0, "queue_rank", range(1, len(unstarted) + 1))

    cumulative_complete = int((company["evidence_status"] == "EVIDENCE_COMPLETE").sum())
    cumulative_partial = int((company["evidence_status"] == "EVIDENCE_PARTIAL").sum())
    cumulative_collected = cumulative_complete + cumulative_partial
    covered_security_count = int(cumulative_ledger["security_id"].nunique())
    if covered_security_count != int(cumulative_expected["covered_security_count"]):
        failures.append(f"CUMULATIVE_COVERED_SECURITIES:{covered_security_count}")
    if len(cumulative_ledger) != int(cumulative_expected["cumulative_batch_rows"]):
        failures.append(f"CUMULATIVE_LEDGER_ROWS:{len(cumulative_ledger)}")
    if cumulative_collected != int(cumulative_expected["cumulative_collected_rows"]):
        failures.append(f"CUMULATIVE_COLLECTED:{cumulative_collected}")
    if cumulative_complete != int(cumulative_expected["cumulative_complete_rows"]):
        failures.append(f"CUMULATIVE_COMPLETE:{cumulative_complete}")
    if len(openq) != int(cumulative_expected["company_specific_open_tasks"]):
        failures.append(f"OPEN_TASKS:{len(openq)}")
    if len(unstarted) != int(cumulative_expected["company_specific_unstarted_tasks"]):
        failures.append(f"UNSTARTED_TASKS:{len(unstarted)}")
    if int(company["score"].notna().sum()) != int(cumulative_expected["required_score_non_null_count"]):
        failures.append("ALPHA_SCORE_PRESENT_CUMULATIVE")

    out.mkdir(parents=True, exist_ok=True)
    batch_ledger_path = out / "HKCU_P2B_E2_R21_40_EVIDENCE_LEDGER.csv"
    cumulative_ledger_path = out / "HKCU_P2B_E2_CUMULATIVE_EVIDENCE_LEDGER.csv"
    dim_path = out / "HKCU_P2B_E2_CUMULATIVE_DIMENSION_MATRIX.csv"
    open_path = out / "HKCU_P2B_E2_CUMULATIVE_OPEN_RESEARCH_QUEUE.csv"
    unstarted_path = out / "HKCU_P2B_E2_CUMULATIVE_UNSTARTED_QUEUE.csv"
    decision_path = out / "HKCU_P2B_E2_R21_40_DECISION.json"
    quality_path = out / "HKCU_P2B_E2_R21_40_QUALITY_REPORT.json"

    evidence.to_csv(batch_ledger_path, index=False)
    cumulative_ledger.to_csv(cumulative_ledger_path, index=False)
    dim.to_csv(dim_path, index=False)
    openq.to_csv(open_path, index=False)
    unstarted.to_csv(unstarted_path, index=False)

    decision = {
        "program_id": "HKCU-P2B-E2-R21-40",
        "phase": "P2B_E2_CONTINUE_COMPANY_SPECIFIC_EVIDENCE",
        "status": "PASS_P2B_E2_RANK21_40_BATCH" if not failures else "FAIL_P2B_E2_RANK21_40",
        "accepted_longlist_count": 77,
        "batch_rank_start": 21,
        "batch_rank_end": 40,
        "batch_security_count": int(wide["security_id"].nunique()),
        "batch_evidence_rows": int(len(evidence)),
        "batch_evidence_collected_rows": collected,
        "batch_evidence_complete_rows": complete,
        "batch_evidence_partial_rows": partial,
        "batch_research_required_rows": research_required,
        "cumulative_covered_security_count": covered_security_count,
        "cumulative_evidence_rows": int(len(cumulative_ledger)),
        "cumulative_evidence_collected_rows": cumulative_collected,
        "cumulative_evidence_complete_rows": cumulative_complete,
        "cumulative_evidence_partial_rows": cumulative_partial,
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
        "program_id": "HKCU-P2B-E2-R21-40",
        "status": "PASS" if not failures else "FAIL",
        "upstream_top20_status": previous_decision.get("status"),
        "batch_status_counts": {str(k): int(v) for k, v in status_counts.items()},
        "company_status_counts_after_batch": {
            str(k): int(v) for k, v in company["evidence_status"].value_counts().items()
        },
        "score_non_null_count": int(company["score"].notna().sum()),
        "batch_rank_min": int(wide["p2a_overall_rank"].min()),
        "batch_rank_max": int(wide["p2a_overall_rank"].max()),
        "hard_failures": failures,
        "trade_authority": TRADE_AUTHORITY,
    }
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest_path = out / "HKCU_P2B_E2_R21_40_MANIFEST.json"
    outputs = [
        batch_ledger_path, cumulative_ledger_path, dim_path, open_path,
        unstarted_path, decision_path, quality_path,
    ]
    manifest = {
        "program_id": "HKCU-P2B-E2-R21-40",
        "inputs": {
            str(contract_path.relative_to(root)): sha256_file(contract_path),
            str(evidence_path.relative_to(root)): sha256_file(evidence_path),
            "upstream_top20_decision_sha256": sha256_file(previous / "HKCU_P2B_E2_DECISION.json"),
            "upstream_top20_dimension_matrix_sha256": sha256_file(previous / "HKCU_P2B_E2_DIMENSION_MATRIX.csv"),
        },
        "outputs": {p.name: sha256_file(p) for p in outputs},
        "trade_authority": TRADE_AUTHORITY,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if failures:
        raise SystemExit("P2B_E2_R21_40_FAILED:" + "|".join(sorted(set(failures))))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
