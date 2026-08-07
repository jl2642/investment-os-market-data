#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd

PROGRAM_ID = "HKCU-P2B"
TRADE_AUTHORITY = "NONE"
DIMENSION_ORDER = {
    "GOVERNANCE_VALUE_TRAP": 1,
    "EARNINGS_EXPECTATION_REVISION": 2,
    "CATALYST": 3,
    "TRANSACTION_COST_TAX": 4,
    "A_H_RELATIVE_VALUATION": 5,
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def as_bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "y"}


def nested_get(payload: dict[str, Any], dotted: str) -> Any:
    value: Any = payload
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(dotted)
        value = value[part]
    return value


def rebuild_and_lock_p2a(repo_root: Path, work_root: Path, acceptance: dict[str, Any]) -> Path:
    p2a_dir = work_root / "_p2a_rebuild"
    if p2a_dir.exists():
        import shutil
        shutil.rmtree(p2a_dir)
    p2a_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            sys.executable,
            str(repo_root / "pipeline/hkcu_p2a_build_longlist.py"),
            "--repo-root", str(repo_root),
            "--output", str(p2a_dir),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts/validate_hkcu_p2a.py"),
            "--repo-root", str(repo_root),
            "--output", str(p2a_dir),
        ],
        check=True,
    )

    expected = acceptance["accepted_outputs_sha256"]
    actual = {name: sha256_file(p2a_dir / name) for name in expected}
    mismatches = [name for name in expected if actual[name] != expected[name]]
    if mismatches:
        raise RuntimeError("P2A_ACCEPTED_HASH_DRIFT:" + ",".join(sorted(mismatches)))
    return p2a_dir


def classify_security(profile: str, contract: dict[str, Any]) -> str:
    mapping = contract["security_type_map"]
    if profile in mapping:
        return str(mapping[profile])
    return "UNKNOWN_RESEARCH_REQUIRED"


def build_security_matrix(longlist: pd.DataFrame, contract: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in longlist.iterrows():
        profile = str(row.get("profile") or "")
        security_type = classify_security(profile, contract)
        rows.append({
            "p2a_overall_rank": int(row["overall_rank"]),
            "security_id": str(row["security_id"]),
            "stock_code_5d": str(row["stock_code_5d"]).zfill(5),
            "official_security_name_en": str(row["official_security_name_en"]),
            "official_issuer_name_en": str(row["official_issuer_name_en"]),
            "p2a_primary_sleeve": str(row["primary_sleeve"]),
            "p2a_aggregate_score": float(row["aggregate_score"]),
            "profile": profile,
            "p2b_security_type": security_type,
            "a_share_class_exists_lead": as_bool(row.get("a_share_class_exists")),
            "h_share_flag": as_bool(row.get("h_share_flag")),
            "research_readiness": str(row.get("research_readiness") or ""),
            "authority": "RESEARCH_ENRICHMENT_ONLY",
            "trade_authority": TRADE_AUTHORITY,
        })
    return pd.DataFrame(rows).sort_values(["p2a_overall_rank", "security_id"]).reset_index(drop=True)


def build_dimension_matrix(security_matrix: pd.DataFrame, contract: dict[str, Any]) -> pd.DataFrame:
    dim_contract = {d["dimension_id"]: d for d in contract["dimensions"]}
    rows: list[dict[str, Any]] = []
    for _, sec in security_matrix.iterrows():
        for dimension_id in DIMENSION_ORDER:
            status = "RESEARCH_REQUIRED"
            applicability = "APPLICABLE"
            applicability_reason = "DIMENSION_APPLIES_TO_ALL_SECURITIES"
            if dimension_id == "A_H_RELATIVE_VALUATION":
                if bool(sec["a_share_class_exists_lead"]):
                    status = "RESEARCH_REQUIRED"
                    applicability = "POTENTIALLY_APPLICABLE"
                    applicability_reason = "A_SHARE_CLASS_LEAD_PRESENT_PAIR_EVIDENCE_REQUIRED"
                else:
                    status = "NOT_APPLICABLE"
                    applicability = "NOT_APPLICABLE"
                    applicability_reason = "NO_SAME_ISSUER_A_SHARE_CLASS_LEAD"
            rows.append({
                "p2a_overall_rank": int(sec["p2a_overall_rank"]),
                "security_id": sec["security_id"],
                "stock_code_5d": sec["stock_code_5d"],
                "official_security_name_en": sec["official_security_name_en"],
                "p2b_security_type": sec["p2b_security_type"],
                "dimension_order": DIMENSION_ORDER[dimension_id],
                "research_dimension": dimension_id,
                "applicability": applicability,
                "applicability_reason": applicability_reason,
                "evidence_status": status,
                "evidence_count": 0,
                "score": pd.NA,
                "score_status": "NO_SCORE_BEFORE_EVIDENCE",
                "minimum_evidence_standard": dim_contract[dimension_id]["minimum_evidence_standard"],
                "next_action": "COLLECT_EVIDENCE" if status == "RESEARCH_REQUIRED" else "NONE",
                "authority": "RESEARCH_ENRICHMENT_ONLY",
                "trade_authority": TRADE_AUTHORITY,
            })
    return pd.DataFrame(rows).sort_values(
        ["p2a_overall_rank", "dimension_order", "security_id"]
    ).reset_index(drop=True)


def build_outputs(repo_root: Path, output: Path) -> None:
    contract_path = repo_root / "config/hkcu_p2b_research_enrichment_contract.json"
    acceptance_path = repo_root / "outputs/hkcu_p2a/current/HKCU_P2A_ACCEPTANCE.json"
    contract = read_json(contract_path)
    acceptance = read_json(acceptance_path)

    if acceptance.get("status") != contract["upstream_lock"]["required_p2a_status"]:
        raise RuntimeError("P2A_ACCEPTANCE_STATUS_INVALID")
    if acceptance.get("trade_authority") != TRADE_AUTHORITY:
        raise RuntimeError("P2A_TRADE_AUTHORITY_INVALID")
    if int(acceptance.get("longlist_count", -1)) != int(contract["upstream_lock"]["required_longlist_count"]):
        raise RuntimeError("P2A_ACCEPTED_LONGLIST_COUNT_INVALID")

    output.mkdir(parents=True, exist_ok=True)
    p2a_dir = rebuild_and_lock_p2a(repo_root, output, acceptance)
    longlist = pd.read_csv(p2a_dir / "HKCU_P2A_RESEARCH_LONGLIST.csv")
    if len(longlist) != 77 or longlist["security_id"].astype(str).duplicated().any():
        raise RuntimeError("P2A_LONG_LIST_MEMBERSHIP_INVALID")

    security_matrix = build_security_matrix(longlist, contract)
    dimension_matrix = build_dimension_matrix(security_matrix, contract)
    queue = dimension_matrix.loc[dimension_matrix["evidence_status"] == "RESEARCH_REQUIRED"].copy()
    queue["queue_rank"] = range(1, len(queue) + 1)
    queue = queue[[
        "queue_rank", "p2a_overall_rank", "security_id", "stock_code_5d",
        "official_security_name_en", "p2b_security_type", "dimension_order",
        "research_dimension", "applicability", "applicability_reason",
        "evidence_status", "minimum_evidence_standard", "next_action",
        "authority", "trade_authority"
    ]]

    sec_path = output / "HKCU_P2B_SECURITY_TYPE_MATRIX.csv"
    dim_path = output / "HKCU_P2B_DIMENSION_MATRIX.csv"
    queue_path = output / "HKCU_P2B_RESEARCH_QUEUE.csv"
    security_matrix.to_csv(sec_path, index=False, encoding="utf-8-sig")
    dimension_matrix.to_csv(dim_path, index=False, encoding="utf-8-sig")
    queue.to_csv(queue_path, index=False, encoding="utf-8-sig")

    type_counts = {str(k): int(v) for k, v in security_matrix["p2b_security_type"].value_counts().items()}
    status_counts = {
        str(k): int(v) for k, v in dimension_matrix["evidence_status"].value_counts().items()
    }
    dimension_required_counts = {
        dim: int(((dimension_matrix["research_dimension"] == dim) &
                  (dimension_matrix["evidence_status"] == "RESEARCH_REQUIRED")).sum())
        for dim in DIMENSION_ORDER
    }
    ah_potential = dimension_required_counts["A_H_RELATIVE_VALUATION"]
    ah_not_applicable = int(((dimension_matrix["research_dimension"] == "A_H_RELATIVE_VALUATION") &
                             (dimension_matrix["evidence_status"] == "NOT_APPLICABLE")).sum())

    hard_failures: list[str] = []
    if len(security_matrix) != 77:
        hard_failures.append("SECURITY_COUNT_NOT_77")
    if int(security_matrix["security_id"].duplicated().sum()) != 0:
        hard_failures.append("DUPLICATE_SECURITY_ID")
    if len(dimension_matrix) != 77 * 5:
        hard_failures.append("DIMENSION_MATRIX_ROW_COUNT_INVALID")
    if (security_matrix["trade_authority"] != TRADE_AUTHORITY).any() or (dimension_matrix["trade_authority"] != TRADE_AUTHORITY).any():
        hard_failures.append("TRADE_AUTHORITY_NOT_NONE")
    if dimension_matrix.loc[dimension_matrix["evidence_status"] != "NOT_APPLICABLE", "score"].notna().any():
        hard_failures.append("UNEVIDENCED_SCORE_PRESENT")

    quality = {
        "program_id": PROGRAM_ID,
        "phase": "P2B_BASELINE",
        "status": "PASS" if not hard_failures else "FAIL",
        "p2a_hash_lock": "PASS",
        "security_count": int(len(security_matrix)),
        "duplicate_security_count": int(security_matrix["security_id"].duplicated().sum()),
        "security_type_counts": type_counts,
        "dimension_matrix_rows": int(len(dimension_matrix)),
        "research_queue_rows": int(len(queue)),
        "evidence_status_counts": status_counts,
        "research_required_by_dimension": dimension_required_counts,
        "a_h_potentially_applicable_count": ah_potential,
        "a_h_not_applicable_count": ah_not_applicable,
        "hard_failures": hard_failures,
        "warnings": [
            "A-share-class existence is only an applicability lead; P2B evidence collection must verify same-issuer A/H pairing before relative-valuation analysis."
        ],
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    quality_path = output / "HKCU_P2B_QUALITY_REPORT.json"
    write_json(quality_path, quality)

    decision = {
        "program_id": PROGRAM_ID,
        "phase": "P2B_BASELINE",
        "status": "PASS_P2B_BASELINE_EVIDENCE_COLLECTION_REQUIRED" if not hard_failures else "BLOCKED",
        "accepted_p2a_security_count": 77,
        "research_queue_rows": int(len(queue)),
        "a_h_relative_valuation_research_leads": ah_potential,
        "formal_candidate_graduation_allowed": False,
        "next_gate": "P2B_EVIDENCE_COLLECTION" if not hard_failures else "BLOCKED_REPAIR",
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    decision_path = output / "HKCU_P2B_DECISION.json"
    write_json(decision_path, decision)

    outputs = [sec_path, dim_path, queue_path, quality_path, decision_path]
    manifest = {
        "program_id": PROGRAM_ID,
        "phase": "P2B_BASELINE",
        "inputs": {
            str(contract_path.relative_to(repo_root)): sha256_file(contract_path),
            str(acceptance_path.relative_to(repo_root)): sha256_file(acceptance_path),
            "accepted_p2a_longlist_sha256": acceptance["accepted_outputs_sha256"]["HKCU_P2A_RESEARCH_LONGLIST.csv"],
        },
        "outputs": {p.name: sha256_file(p) for p in outputs},
        "p2a_rebuild_hash_lock": "PASS",
        "trade_authority": TRADE_AUTHORITY,
    }
    manifest_path = output / "HKCU_P2B_MANIFEST.json"
    write_json(manifest_path, manifest)

    if hard_failures:
        raise RuntimeError("P2B_BASELINE_FAILED:" + ",".join(hard_failures))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    build_outputs(Path(args.repo_root).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
