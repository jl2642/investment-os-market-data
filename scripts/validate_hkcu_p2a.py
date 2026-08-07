#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

TRADE_AUTHORITY = "NONE"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate(repo_root: Path, output: Path) -> dict:
    errors: list[str] = []
    canonical_path = repo_root / "outputs/hkcu1/current/HKCU1_R2E_INVESTABLE_UNIVERSE.csv"
    canonical = pd.read_csv(canonical_path, dtype={"stock_code_5d": str}, encoding="utf-8-sig")
    longlist = pd.read_csv(output / "HKCU_P2A_RESEARCH_LONGLIST.csv", dtype={"stock_code_5d": str}, encoding="utf-8-sig")
    sleeve = pd.read_csv(output / "HKCU_P2A_SLEEVE_DETAIL.csv", dtype={"stock_code_5d": str}, encoding="utf-8-sig")
    missingness = pd.read_csv(output / "HKCU_P2A_RESEARCH_MISSINGNESS.csv", dtype={"stock_code_5d": str}, encoding="utf-8-sig")
    decision = read_json(output / "HKCU_P2A_DECISION.json")
    quality = read_json(output / "HKCU_P2A_QUALITY_REPORT.json")
    manifest = read_json(output / "HKCU_P2A_MANIFEST.json")

    if decision.get("status") != "PASS_P2A_RESEARCH_LONGLIST":
        errors.append("DECISION_NOT_PASS")
    if quality.get("status") != "PASS" or quality.get("hard_failures"):
        errors.append("QUALITY_NOT_PASS")
    if int(decision.get("canonical_hkcu_count", -1)) != len(canonical):
        errors.append("CANONICAL_COUNT_MISMATCH")
    if int(decision.get("longlist_count", -1)) != len(longlist):
        errors.append("LONGLIST_COUNT_MISMATCH")
    if decision.get("longlist_count_policy") != "DISTRIBUTION_DERIVED_NO_FIXED_TARGET":
        errors.append("FIXED_TARGET_POLICY_REGRESSION")
    if int(longlist["security_id"].astype(str).duplicated().sum()) != 0:
        errors.append("DUPLICATE_LONGLIST_SECURITY")
    canonical_ids = set(canonical["security_id"].astype(str))
    longlist_ids = set(longlist["security_id"].astype(str))
    if not longlist_ids.issubset(canonical_ids):
        errors.append("LONGLIST_OUTSIDE_CANONICAL")
    if not longlist["trade_authority"].astype(str).eq(TRADE_AUTHORITY).all():
        errors.append("LONGLIST_TRADE_AUTHORITY")
    if not missingness.empty:
        if not missingness["score_contribution_in_p2a"].fillna(-1).eq(0).all():
            errors.append("MISSING_DIMENSION_SCORE_LEAKAGE")
        if not missingness["status"].astype(str).eq("P2B_REQUIRED").all():
            errors.append("MISSINGNESS_STATUS")
    if set(sleeve["security_id"].astype(str)) - canonical_ids:
        errors.append("SLEEVE_OUTSIDE_CANONICAL")
    manifest_input = manifest.get("inputs", {}).get(
        "outputs/hkcu1/current/HKCU1_R2E_INVESTABLE_UNIVERSE.csv"
    )
    if manifest_input != sha256_file(canonical_path):
        errors.append("CANONICAL_HASH_MISMATCH")
    for protected in ("candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"):
        if int(decision.get(protected, -1)) != 0 or int(quality.get(protected, -1)) != 0:
            errors.append(f"PROTECTED_MUTATION:{protected}")
    if decision.get("trade_authority") != TRADE_AUTHORITY or quality.get("trade_authority") != TRADE_AUTHORITY:
        errors.append("TRADE_AUTHORITY_REGRESSION")
    result = {
        "program_id": "HKCU-P2A",
        "validator": "INDEPENDENT_OUTPUT_VALIDATOR",
        "status": "PASS" if not errors else "FAIL",
        "canonical_count": len(canonical),
        "longlist_count": len(longlist),
        "formal_sleeve_union_count": int(sleeve["security_id"].astype(str).nunique()),
        "missingness_rows": len(missingness),
        "errors": errors,
        "trade_authority": TRADE_AUTHORITY,
    }
    if errors:
        raise RuntimeError("HKCU_P2A_VALIDATION_FAILED:" + ";".join(errors))
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    root = a.repo_root.resolve()
    output = a.output if a.output.is_absolute() else root / a.output
    result = validate(root, output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
