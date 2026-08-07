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


def rebuild_batch3(root: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable,
        str(root / "pipeline/hkcu_p2b_apply_e2_batch3.py"),
        "--repo-root", str(root),
        "--output", str(out),
    ], check=True)
    subprocess.run([
        sys.executable,
        str(root / "scripts/validate_hkcu_p2b_e2_batch3.py"),
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
    contract_path = root / "config/hkcu_p2b_e2_final_contract.json"
    evidence_path = root / "evidence/hkcu_p2b/HKCU_P2B_E2_COMPANY_EVIDENCE_RANKS_61_77_20260807.csv"
    contract = read_json(contract_path)
    policy = contract["batch_policy"]
    wide = pd.read_csv(evidence_path, dtype={"stock_code_5d": str}, keep_default_na=False)
    final_batch = expand_registry(wide)
    failures: list[str] = []

    expected_ranks = set(range(int(policy["required_rank_start"]), int(policy["required_rank_end"]) + 1))
    actual_ranks = set(pd.to_numeric(wide["p2a_overall_rank"], errors="coerce").dropna().astype(int))
    if len(wide) != int(policy["batch_security_count"]):
        failures.append(f"WIDE_SECURITY_COUNT:{len(wide)}")
    if wide["security_id"].duplicated().any():
        failures.append("DUPLICATE_WIDE_SECURITY")
    if actual_ranks != expected_ranks:
        failures.append("FINAL_BATCH_RANK_SET_INVALID")
    if len(final_batch) != int(policy["required_evidence_rows"]):
        failures.append(f"FINAL_EVIDENCE_ROWS:{len(final_batch)}")
    if final_batch.duplicated(["security_id", "research_dimension"]).any():
        failures.append("FINAL_DUPLICATE_SECURITY_DIMENSION")
    if set(final_batch["research_dimension"]) != set(policy["required_dimensions"]):
        failures.append("FINAL_DIMENSION_SET_INVALID")
    if not set(final_batch["evidence_status"]).issubset(set(contract["evidence_policy"]["allowed_statuses"])):
        failures.append("FINAL_STATUS_VOCABULARY_INVALID")
    if final_batch["score"].notna().any():
        failures.append("FINAL_ALPHA_SCORE_PRESENT")

    as_of = pd.Timestamp(policy["as_of_date"])
    for _, row in final_batch.iterrows():
        ev_date = pd.to_datetime(row["evidence_date"], errors="coerce")
        if pd.isna(ev_date):
            failures.append(f"EVIDENCE_DATE_INVALID:{row['security_id']}:{row['research_dimension']}")
        elif ev_date > as_of:
            failures.append(f"FUTURE_EVIDENCE:{row['security_id']}:{row['research_dimension']}")
        if row["evidence_status"] in {"EVIDENCE_PARTIAL", "EVIDENCE_COMPLETE"}:
            if not str(row["source_url"]).startswith("https://www1.hkexnews.hk/"):
                failures.append(f"HKEX_PRIMARY_SOURCE_REQUIRED:{row['security_id']}:{row['research_dimension']}")
            if not str(row["evidence_title"]).strip() or not str(row["evidence_summary"]).strip():
                failures.append(f"EVIDENCE_CONTENT_MISSING:{row['security_id']}:{row['research_dimension']}")

    expected_batch = contract["expected_batch_counts"]
    batch_counts = final_batch["evidence_status"].value_counts().to_dict()
    for status in ["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL", "RESEARCH_REQUIRED"]:
        if int(batch_counts.get(status, 0)) != int(expected_batch[status]):
            failures.append(f"FINAL_STATUS_COUNT:{status}:{int(batch_counts.get(status,0))}")
    final_collected = int(final_batch["evidence_status"].isin(["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL"]).sum())
    if final_collected != int(expected_batch["evidence_collected_rows"]):
        failures.append(f"FINAL_COLLECTED_COUNT:{final_collected}")

    direct = set(
        final_batch.loc[
            (final_batch["research_dimension"] == "EARNINGS_EXPECTATION_REVISION")
            & (final_batch["evidence_status"] == "EVIDENCE_COMPLETE"),
            "stock_code_5d",
        ].astype(str).str.zfill(5)
    )
    if direct != set(contract["direct_expectation_complete_codes"]):
        failures.append("DIRECT_EXPECTATION_CODES")
    topsports = final_batch[
        (final_batch["stock_code_5d"].astype(str).str.zfill(5) == "06110")
        & (final_batch["research_dimension"] == "EARNINGS_EXPECTATION_REVISION")
    ]
    if len(topsports) != 1:
        failures.append("TOPSPORTS_EXPECTATION_ROW")
    else:
        txt = (str(topsports.iloc[0]["evidence_title"]) + " " + str(topsports.iloc[0]["evidence_summary"])).lower()
        if "nike" not in txt or "significant" not in txt or "22%" not in txt:
            failures.append("TOPSPORTS_FORWARD_IMPACT_GUARD")

    b3 = out / "_batch3_rebuild"
    rebuild_batch3(root, b3)
    b3_decision = read_json(b3 / "HKCU_P2B_E2_B3_DECISION.json")
    if b3_decision.get("status") != "PASS_P2B_E2_RANKS_41_60_BATCH":
        failures.append("UPSTREAM_BATCH3_NOT_PASS")
    b3_ledger = pd.read_csv(
        b3 / "HKCU_P2B_E2_B3_CUMULATIVE_EVIDENCE_LEDGER.csv",
        dtype={"stock_code_5d": str},
    )
    dim = pd.read_csv(
        b3 / "HKCU_P2B_E2_B3_DIMENSION_MATRIX.csv",
        dtype={"stock_code_5d": str},
    )
    if len(b3_ledger) != 180 or b3_ledger["security_id"].nunique() != 60:
        failures.append("UPSTREAM_BATCH3_LEDGER_INVALID")
    if set(b3_ledger["p2a_overall_rank"].astype(int)) & expected_ranks:
        failures.append("FINAL_RANK_OVERLAP")

    company = dim[dim["research_dimension"].isin(DIMS)].copy()
    company_keys = set(zip(company["security_id"], company["research_dimension"]))
    final_keys = set(zip(final_batch["security_id"], final_batch["research_dimension"]))
    if final_keys - company_keys:
        failures.append("FINAL_EVIDENCE_NOT_IN_COMPANY_MATRIX")
    rank_map = (
        company[["security_id", "p2a_overall_rank"]]
        .drop_duplicates()
        .set_index("security_id")["p2a_overall_rank"]
        .to_dict()
    )
    for _, row in final_batch.iterrows():
        if int(row["p2a_overall_rank"]) != int(rank_map.get(row["security_id"], -1)):
            failures.append(f"RANK_MISMATCH:{row['security_id']}")
        prior = company[
            (company["security_id"] == row["security_id"])
            & (company["research_dimension"] == row["research_dimension"])
        ]
        if len(prior) != 1 or str(prior.iloc[0]["evidence_status"]) != "RESEARCH_REQUIRED":
            failures.append(f"FINAL_TARGET_NOT_UNSTARTED:{row['security_id']}:{row['research_dimension']}")

    idx_map = {
        (sid, rd): idx
        for idx, sid, rd in zip(dim.index, dim["security_id"], dim["research_dimension"])
    }
    for _, ev in final_batch.iterrows():
        idx = idx_map.get((ev["security_id"], ev["research_dimension"]))
        if idx is None:
            failures.append(f"DIMENSION_ROW_MISSING:{ev['security_id']}:{ev['research_dimension']}")
            continue
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
        dim.at[idx, "applicability_reason"] = (
            str(dim.at[idx, "applicability_reason"]) + "|E2:" + str(ev["batch_id"])
        )

    cumulative_ledger = pd.concat([b3_ledger, final_batch], ignore_index=True)
    if cumulative_ledger.duplicated(["security_id", "research_dimension"]).any():
        failures.append("CUMULATIVE_LEDGER_DUPLICATE")

    company_after = dim[dim["research_dimension"].isin(DIMS)].copy()
    openq = (
        company_after[company_after["evidence_status"] != "EVIDENCE_COMPLETE"]
        .copy()
        .sort_values(["p2a_overall_rank", "dimension_order", "security_id"])
        .reset_index(drop=True)
    )
    openq.insert(0, "queue_rank", range(1, len(openq) + 1))
    unstarted = (
        company_after[company_after["evidence_status"] == "RESEARCH_REQUIRED"]
        .copy()
        .sort_values(["p2a_overall_rank", "dimension_order", "security_id"])
        .reset_index(drop=True)
    )
    unstarted.insert(0, "queue_rank", range(1, len(unstarted) + 1))

    expected_cum = contract["expected_cumulative_after_final"]
    cumulative_counts = company_after["evidence_status"].value_counts().to_dict()
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
    cumulative_collected = int(
        cumulative_ledger["evidence_status"].isin(["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL"]).sum()
    )
    if cumulative_collected != int(expected_cum["cumulative_evidence_collected_rows"]):
        failures.append(f"CUMULATIVE_COLLECTED_ROWS:{cumulative_collected}")
    started = int(cumulative_ledger["security_id"].nunique())
    if started != int(expected_cum["cumulative_security_count_started"]):
        failures.append(f"CUMULATIVE_STARTED:{started}")
    if company_after["score"].notna().any():
        failures.append("CUMULATIVE_ALPHA_SCORE_PRESENT")

    out.mkdir(parents=True, exist_ok=True)
    batch_path = out / "HKCU_P2B_E2_FINAL_EVIDENCE_LEDGER.csv"
    ledger_path = out / "HKCU_P2B_E2_FINAL_CUMULATIVE_EVIDENCE_LEDGER.csv"
    dim_path = out / "HKCU_P2B_E2_FINAL_DIMENSION_MATRIX.csv"
    open_path = out / "HKCU_P2B_E2_FINAL_OPEN_RESEARCH_QUEUE.csv"
    unstarted_path = out / "HKCU_P2B_E2_FINAL_UNSTARTED_QUEUE.csv"
    decision_path = out / "HKCU_P2B_E2_FINAL_DECISION.json"
    quality_path = out / "HKCU_P2B_E2_FINAL_QUALITY_REPORT.json"

    final_batch.to_csv(batch_path, index=False)
    cumulative_ledger.to_csv(ledger_path, index=False)
    dim.to_csv(dim_path, index=False)
    openq.to_csv(open_path, index=False)
    unstarted.to_csv(unstarted_path, index=False)

    decision = {
        "program_id": "HKCU-P2B-E2-FINAL",
        "phase": "P2B_E2_COMPANY_SPECIFIC_EVIDENCE",
        "status": "PASS_P2B_E2_ALL_77_FIRST_PASS_EVIDENCE" if not failures else "FAIL_P2B_E2_FINAL",
        "accepted_longlist_count": 77,
        "batch_rank_start": 61,
        "batch_rank_end": 77,
        "batch_security_count": int(wide["security_id"].nunique()),
        "batch_evidence_rows": int(len(final_batch)),
        "batch_evidence_collected_rows": final_collected,
        "cumulative_security_count_started": started,
        "cumulative_evidence_rows": int(len(cumulative_ledger)),
        "cumulative_evidence_collected_rows": cumulative_collected,
        "cumulative_evidence_complete_rows": int((company_after["evidence_status"] == "EVIDENCE_COMPLETE").sum()),
        "cumulative_evidence_partial_rows": int((company_after["evidence_status"] == "EVIDENCE_PARTIAL").sum()),
        "company_specific_open_tasks": int(len(openq)),
        "company_specific_unstarted_tasks": int(len(unstarted)),
        "all_77_securities_started": started == 77,
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
        "program_id": "HKCU-P2B-E2-FINAL",
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": sorted(set(failures)),
        "upstream_batch3_status": b3_decision.get("status"),
        "final_batch_status_counts": {str(k): int(v) for k, v in final_batch["evidence_status"].value_counts().items()},
        "cumulative_company_status_counts": {str(k): int(v) for k, v in company_after["evidence_status"].value_counts().items()},
        "score_non_null_count": int(company_after["score"].notna().sum()),
        "batch_rank_min": int(wide["p2a_overall_rank"].min()),
        "batch_rank_max": int(wide["p2a_overall_rank"].max()),
        "trade_authority": TRADE_AUTHORITY,
    }
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest_path = out / "HKCU_P2B_E2_FINAL_MANIFEST.json"
    outputs = [batch_path, ledger_path, dim_path, open_path, unstarted_path, decision_path, quality_path]
    manifest = {
        "program_id": "HKCU-P2B-E2-FINAL",
        "inputs": {
            str(contract_path.relative_to(root)): sha256_file(contract_path),
            str(evidence_path.relative_to(root)): sha256_file(evidence_path),
            "upstream_batch3_decision_sha256": sha256_file(b3 / "HKCU_P2B_E2_B3_DECISION.json"),
            "upstream_batch3_dimension_matrix_sha256": sha256_file(b3 / "HKCU_P2B_E2_B3_DIMENSION_MATRIX.csv"),
        },
        "outputs": {p.name: sha256_file(p) for p in outputs},
        "trade_authority": TRADE_AUTHORITY,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if failures:
        raise SystemExit("P2B_E2_FINAL_FAILED:" + "|".join(sorted(set(failures))))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
