#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

TRADE_AUTHORITY = "NONE"
EXPECTED_OUTPUTS = [
    "HKCU_P2B_SECURITY_TYPE_MATRIX.csv",
    "HKCU_P2B_DIMENSION_MATRIX.csv",
    "HKCU_P2B_RESEARCH_QUEUE.csv",
    "HKCU_P2B_QUALITY_REPORT.json",
    "HKCU_P2B_DECISION.json",
    "HKCU_P2B_MANIFEST.json",
]
EXPECTED_DIMENSIONS = {
    "GOVERNANCE_VALUE_TRAP",
    "EARNINGS_EXPECTATION_REVISION",
    "CATALYST",
    "TRANSACTION_COST_TAX",
    "A_H_RELATIVE_VALUATION",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(repo_root: Path, output: Path) -> list[str]:
    errors: list[str] = []
    for name in EXPECTED_OUTPUTS:
        if not (output / name).exists():
            errors.append(f"MISSING_OUTPUT:{name}")
    if errors:
        return errors

    acceptance = read_json(repo_root / "outputs/hkcu_p2a/current/HKCU_P2A_ACCEPTANCE.json")
    security = pd.read_csv(output / "HKCU_P2B_SECURITY_TYPE_MATRIX.csv")
    dimensions = pd.read_csv(output / "HKCU_P2B_DIMENSION_MATRIX.csv")
    queue = pd.read_csv(output / "HKCU_P2B_RESEARCH_QUEUE.csv")
    quality = read_json(output / "HKCU_P2B_QUALITY_REPORT.json")
    decision = read_json(output / "HKCU_P2B_DECISION.json")
    manifest = read_json(output / "HKCU_P2B_MANIFEST.json")

    if acceptance.get("status") != "PASS_P2A_CURRENT" or int(acceptance.get("longlist_count", -1)) != 77:
        errors.append("UPSTREAM_P2A_ACCEPTANCE_INVALID")
    if len(security) != 77:
        errors.append(f"SECURITY_COUNT:{len(security)}")
    if security["security_id"].astype(str).duplicated().any():
        errors.append("DUPLICATE_SECURITY")
    if set(dimensions["research_dimension"].astype(str)) != EXPECTED_DIMENSIONS:
        errors.append("DIMENSION_SET_INVALID")
    if len(dimensions) != 385:
        errors.append(f"DIMENSION_ROW_COUNT:{len(dimensions)}")
    per_security = dimensions.groupby("security_id")["research_dimension"].nunique()
    if not (per_security == 5).all():
        errors.append("DIMENSIONS_PER_SECURITY_INVALID")

    ah = dimensions[dimensions["research_dimension"] == "A_H_RELATIVE_VALUATION"].copy()
    ah_required = ah[ah["evidence_status"] == "RESEARCH_REQUIRED"]
    ah_na = ah[ah["evidence_status"] == "NOT_APPLICABLE"]
    security_index = security.set_index("security_id")
    for _, row in ah_required.iterrows():
        if not bool(security_index.loc[row["security_id"], "a_share_class_exists_lead"]):
            errors.append(f"AH_REQUIRED_WITHOUT_A_SHARE_LEAD:{row['security_id']}")
    for _, row in ah_na.iterrows():
        if bool(security_index.loc[row["security_id"], "a_share_class_exists_lead"]):
            errors.append(f"AH_NOT_APPLICABLE_WITH_A_SHARE_LEAD:{row['security_id']}")

    if len(queue) != int((dimensions["evidence_status"] == "RESEARCH_REQUIRED").sum()):
        errors.append("QUEUE_COUNT_MISMATCH")
    if not queue.empty and not (queue["evidence_status"] == "RESEARCH_REQUIRED").all():
        errors.append("QUEUE_CONTAINS_NON_REQUIRED")
    if dimensions.loc[dimensions["evidence_status"] != "NOT_APPLICABLE", "score"].notna().any():
        errors.append("UNEVIDENCED_SCORE_PRESENT")

    for frame_name, frame in [("security", security), ("dimensions", dimensions), ("queue", queue)]:
        if "trade_authority" not in frame.columns or not (frame["trade_authority"].astype(str) == TRADE_AUTHORITY).all():
            errors.append(f"TRADE_AUTHORITY_INVALID:{frame_name}")

    if quality.get("status") != "PASS" or quality.get("hard_failures"):
        errors.append("QUALITY_NOT_PASS")
    if quality.get("p2a_hash_lock") != "PASS" or manifest.get("p2a_rebuild_hash_lock") != "PASS":
        errors.append("P2A_HASH_LOCK_NOT_PASS")
    if decision.get("status") != "PASS_P2B_BASELINE_EVIDENCE_COLLECTION_REQUIRED":
        errors.append("DECISION_STATUS_INVALID")
    if decision.get("formal_candidate_graduation_allowed") is not False:
        errors.append("PREMATURE_CANDIDATE_GRADUATION")
    if decision.get("next_gate") != "P2B_EVIDENCE_COLLECTION":
        errors.append("NEXT_GATE_INVALID")

    for payload_name, payload in [("acceptance", acceptance), ("quality", quality), ("decision", decision), ("manifest", manifest)]:
        if payload.get("trade_authority") != TRADE_AUTHORITY:
            errors.append(f"TRADE_AUTHORITY_INVALID:{payload_name}")
    for payload_name, payload in [("quality", quality), ("decision", decision)]:
        for key in ["candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"]:
            if int(payload.get(key, -1)) != 0:
                errors.append(f"PROTECTED_MUTATION:{payload_name}:{key}")
    return sorted(set(errors))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    errors = validate(Path(args.repo_root).resolve(), Path(args.output).resolve())
    if errors:
        raise SystemExit("P2B_VALIDATION_FAILED:" + "|".join(errors))
    print("PASS_P2B_BASELINE_VALIDATION")


if __name__ == "__main__":
    main()
