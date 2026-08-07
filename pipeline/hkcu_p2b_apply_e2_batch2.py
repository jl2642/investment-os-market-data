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


def rebuild_batch1(root: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable, str(root / "pipeline/hkcu_p2b_apply_e2_company_evidence.py"),
        "--repo-root", str(root), "--output", str(out),
    ], check=True)
    subprocess.run([
        sys.executable, str(root / "scripts/validate_hkcu_p2b_e2.py"),
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
    contract_path = root / "config/hkcu_p2b_e2_batch2_contract.json"
    evidence_path = root / "evidence/hkcu_p2b/HKCU_P2B_E2_COMPANY_EVIDENCE_RANKS_21_40_20260807.csv"
    contract = read_json(contract_path)
    wide = pd.read_csv(evidence_path, dtype={"stock_code_5d": str}, keep_default_na=False)
    batch2 = expand_registry(wide)
    failures: list[str] = []

    policy = contract["batch_policy"]
    expected_ranks = set(range(int(policy["required_rank_start"]), int(policy["required_rank_end"]) + 1))
    if len(wide) != int(policy["batch_security_count"]):
        failures.append(f"WIDE_SECURITY_COUNT:{len(wide)}")
    if wide["security_id"].duplicated().any():
        failures.append("DUPLICATE_WIDE_SECURITY")
    if set(pd.to_numeric(wide["p2a_overall_rank"], errors="coerce").dropna().astype(int)) != expected_ranks:
        failures.append("BATCH_RANK_SET_INVALID")
    if len(batch2) != int(policy["required_evidence_rows"]):
        failures.append(f"BATCH2_EVIDENCE_ROWS:{len(batch2)}")
    if batch2.duplicated(["security_id", "research_dimension"]).any():
        failures.append("BATCH2_DUPLICATE_SECURITY_DIMENSION")
    if set(batch2["research_dimension"]) != set(policy["required_dimensions"]):
        failures.append("BATCH2_DIMENSION_SET_INVALID")
    if not set(batch2["evidence_status"]).issubset(set(contract["evidence_policy"]["allowed_statuses"])):
        failures.append("BATCH2_STATUS_VOCABULARY_INVALID")
    if batch2["score"].notna().any():
        failures.append("BATCH2_ALPHA_SCORE_PRESENT")

    as_of = pd.Timestamp(policy["as_of_date"])
    for _, row in batch2.iterrows():
        date = pd.to_datetime(row["evidence_date"], errors="coerce")
        if pd.isna(date):
            failures.append(f"EVIDENCE_DATE_INVALID:{row['security_id']}:{row['research_dimension']}")
        elif date > as_of:
            failures.append(f"FUTURE_EVIDENCE:{row['security_id']}:{row['research_dimension']}")
        if row["evidence_status"] in {"EVIDENCE_PARTIAL", "EVIDENCE_COMPLETE"}:
            if not str(row["source_url"]).startswith("https://www1.hkexnews.hk/"):
                failures.append(f"HKEX_PRIMARY_SOURCE_REQUIRED:{row['security_id']}:{row['research_dimension']}")
            if not str(row["evidence_title"]).strip() or not str(row["evidence_summary"]).strip():
                failures.append(f"EVIDENCE_CONTENT_MISSING:{row['security_id']}:{row['research_dimension']}")

    expected_batch = contract["expected_batch_counts"]
    batch_counts = batch2["evidence_status"].value_counts().to_dict()
    for status in ["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL", "RESEARCH_REQUIRED"]:
        if int(batch_counts.get(status, 0)) != int(expected_batch[status]):
            failures.append(f"BATCH_STATUS_COUNT:{status}:{int(batch_counts.get(status,0))}")
    collected2 = int(batch2["evidence_status"].isin(["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL"]).sum())
    if collected2 != int(expected_batch["evidence_collected_rows"]):
        failures.append(f"BATCH_COLLECTED_COUNT:{collected2}")

    b1 = out / "_batch1_rebuild"
    rebuild_batch1(root, b1)
    b1_decision = read_json(b1 / "HKCU_P2B_E2_DECISION.json")
    if b1_decision.get("status") != "PASS_P2B_E2_TOP_QUARTILE_BATCH":
        failures.append("UPSTREAM_BATCH1_NOT_PASS")
    b1_ledger = pd.read_csv(b1 / "HKCU_P2B_E2_EVIDENCE_LEDGER.csv", dtype={"stock_code_5d": str})
    dim = pd.read_csv(b1 / "HKCU_P2B_E2_DIMENSION_MATRIX.csv", dtype={"stock_code_5d": str})
    if len(b1_ledger) != 60 or b1_ledger["security_id"].nunique() != 20:
        failures.append("UPSTREAM_BATCH1_LEDGER_INVALID")
    if set(b1_ledger["p2a_overall_rank"].astype(int)) & expected_ranks:
        failures.append("BATCH_RANK_OVERLAP")

    company = dim[dim["research_dimension"].isin(DIMS)].copy()
    company_keys = set(zip(company["security_id"], company["research_dimension"]))
    batch2_keys = set(zip(batch2["security_id"], batch2["research_dimension"]))
    if batch2_keys - company_keys:
        failures.append("BATCH2_EVIDENCE_NOT_IN_COMPANY_MATRIX")
    rank_map = company[["security_id", "p2a_overall_rank"]].drop_duplicates().set_index("security_id")["p2a_overall_rank"].to_dict()
    for _, row in batch2.iterrows():
        if int(row["p2a_overall_rank"]) != int(rank_map.get(row["security_id"], -1)):
            failures.append(f"RANK_MISMATCH:{row['security_id']}")
        prior = company[(company["security_id"] == row["security_id"]) & (company["research_dimension"] == row["research_dimension"])]
        if len(prior) != 1 or str(prior.iloc[0]["evidence_status"]) != "RESEARCH_REQUIRED":
            failures.append(f"BATCH2_TARGET_NOT_UNSTARTED:{row['security_id']}:{row['research_dimension']}")

    idx_map = {(sid, rd): idx for idx, sid, rd in zip(dim.index, dim["security_id"], dim["research_dimension"])}
    for _, ev in batch2.iterrows():
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

    cumulative_ledger = pd.concat([b1_ledger, batch2], ignore_index=True)
    if cumulative_ledger.duplicated(["security_id", "research_dimension"]).any():
        failures.append("CUMULATIVE_LEDGER_DUPLICATE")

    company_after = dim[dim["research_dimension"].isin(DIMS)].copy()
    openq = company_after[company_after["evidence_status"] != "EVIDENCE_COMPLETE"].copy().sort_values(["p2a_overall_rank", "dimension_order", "security_id"]).reset_index(drop=True)
    openq.insert(0, "queue_rank", range(1, len(openq) + 1))
    unstarted = company_after[company_after["evidence_status"] == "RESEARCH_REQUIRED"].copy().sort_values(["p2a_overall_rank", "dimension_order", "security_id"]).reset_index(drop=True)
    unstarted.insert(0, "queue_rank", range(1, len(unstarted) + 1))

    cumulative_counts = company_after["evidence_status"].value_counts().to_dict()
    expected_cum = contract["expected_cumulative_after_batch2"]
    for status in ["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL", "RESEARCH_REQUIRED"]:
        if int(cumulative_counts.get(status, 0)) != int(expected_cum[status]):
            failures.append(f"CUMULATIVE_STATUS_COUNT:{status}:{int(cumulative_counts.get(status,0))}")
    if len(company_after) != int(expected_cum["company_specific_dimension_rows"]):
        failures.append(f"COMPANY_DIMENSION_ROWS:{len(company_after)}")
    if len(openq) != int(expected_cum["company_specific_open_tasks"]):
        failures.append(f"OPEN_QUEUE_COUNT:{len(openq)}")
    if len(unstarted) != int(expected_cum["company_specific_unstarted_tasks"]):
        failures.append(f"UNSTARTED_QUEUE_COUNT:{len(unstarted)}")
    if len(cumulative_ledger) != int(expected_cum["cumulative_batch_evidence_rows"]):
        failures.append(f"CUMULATIVE_LEDGER_ROWS:{len(cumulative_ledger)}")
    cumulative_collected = int(cumulative_ledger["evidence_status"].isin(["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL"]).sum())
    if cumulative_collected != int(expected_cum["cumulative_evidence_collected_rows"]):
        failures.append(f"CUMULATIVE_COLLECTED_ROWS:{cumulative_collected}")
    if company_after["score"].notna().any():
        failures.append("CUMULATIVE_ALPHA_SCORE_PRESENT")

    out.mkdir(parents=True, exist_ok=True)
    ledger_path = out / "HKCU_P2B_E2_B2_CUMULATIVE_EVIDENCE_LEDGER.csv"
    dim_path = out / "HKCU_P2B_E2_B2_DIMENSION_MATRIX.csv"
    open_path = out / "HKCU_P2B_E2_B2_OPEN_RESEARCH_QUEUE.csv"
    unstarted_path = out / "HKCU_P2B_E2_B2_UNSTARTED_QUEUE.csv"
    decision_path = out / "HKCU_P2B_E2_B2_DECISION.json"
    quality_path = out / "HKCU_P2B_E2_B2_QUALITY_REPORT.json"
    cumulative_ledger.to_csv(ledger_path, index=False)
    dim.to_csv(dim_path, index=False)
    openq.to_csv(open_path, index=False)
    unstarted.to_csv(unstarted_path, index=False)

    decision = {
        "program_id": "HKCU-P2B-E2-B2",
        "phase": "P2B_E2_COMPANY_SPECIFIC_EVIDENCE",
        "status": "PASS_P2B_E2_RANKS_21_40_BATCH" if not failures else "FAIL_P2B_E2_BATCH2",
        "accepted_longlist_count": 77,
        "batch_rank_start": 21,
        "batch_rank_end": 40,
        "batch_security_count": int(wide["security_id"].nunique()),
        "batch_evidence_rows": int(len(batch2)),
        "batch_evidence_collected_rows": collected2,
        "cumulative_security_count_started": int(cumulative_ledger["security_id"].nunique()),
        "cumulative_evidence_rows": int(len(cumulative_ledger)),
        "cumulative_evidence_collected_rows": cumulative_collected,
        "cumulative_evidence_complete_rows": int((company_after["evidence_status"] == "EVIDENCE_COMPLETE").sum()),
        "cumulative_evidence_partial_rows": int((company_after["evidence_status"] == "EVIDENCE_PARTIAL").sum()),
        "company_specific_open_tasks": int(len(openq)),
        "company_specific_unstarted_tasks": int(len(unstarted)),
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
        "program_id": "HKCU-P2B-E2-B2",
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": sorted(set(failures)),
        "upstream_batch1_status": b1_decision.get("status"),
        "batch2_status_counts": {str(k): int(v) for k, v in batch2["evidence_status"].value_counts().items()},
        "cumulative_company_status_counts": {str(k): int(v) for k, v in company_after["evidence_status"].value_counts().items()},
        "score_non_null_count": int(company_after["score"].notna().sum()),
        "batch_rank_min": int(wide["p2a_overall_rank"].min()),
        "batch_rank_max": int(wide["p2a_overall_rank"].max()),
        "trade_authority": TRADE_AUTHORITY,
    }
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest_path = out / "HKCU_P2B_E2_B2_MANIFEST.json"
    manifest = {
        "program_id": "HKCU-P2B-E2-B2",
        "inputs": {
            str(contract_path.relative_to(root)): sha256_file(contract_path),
            str(evidence_path.relative_to(root)): sha256_file(evidence_path),
            "upstream_batch1_decision_sha256": sha256_file(b1 / "HKCU_P2B_E2_DECISION.json"),
            "upstream_batch1_dimension_matrix_sha256": sha256_file(b1 / "HKCU_P2B_E2_DIMENSION_MATRIX.csv"),
            "upstream_batch1_ledger_sha256": sha256_file(b1 / "HKCU_P2B_E2_EVIDENCE_LEDGER.csv"),
        },
        "outputs": {p.name: sha256_file(p) for p in [ledger_path, dim_path, open_path, unstarted_path, decision_path, quality_path]},
        "trade_authority": TRADE_AUTHORITY,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise SystemExit("P2B_E2_BATCH2_FAILED:" + "|".join(sorted(set(failures))))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
