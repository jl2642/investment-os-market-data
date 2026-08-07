#!/usr/bin/env python3
"""Independent fail-closed validator for an HKCU-1 release candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate(release_dir: Path) -> dict:
    required = [
        "HKCU1_SOURCE_LEDGER.csv",
        "HKCU1_POINT_IN_TIME_ELIGIBILITY.csv",
        "HKCU1_STOCK_CONNECT_INVESTABLE_UNIVERSE.csv",
        "HKCU1_EXCLUSIONS.csv",
        "HKCU1_QUALITY_REPORT.json",
        "HKCU1_MANIFEST.json",
        "HKCU1_DECISION.json",
    ]
    failures: list[str] = []
    missing = [x for x in required if not (release_dir / x).exists()]
    if missing:
        failures.append("MISSING_OUTPUTS:" + ",".join(missing))
        return {"status": "BLOCKED", "failures": failures, "trade_authority": "NONE"}

    source = pd.read_csv(release_dir / required[0], dtype=str).fillna("")
    elig = pd.read_csv(release_dir / required[1], dtype=str).fillna("")
    investable = pd.read_csv(release_dir / required[2], dtype=str).fillna("")
    exclusions = pd.read_csv(release_dir / required[3], dtype=str).fillna("")
    quality = json.loads((release_dir / required[4]).read_text(encoding="utf-8"))
    manifest = json.loads((release_dir / required[5]).read_text(encoding="utf-8"))
    decision = json.loads((release_dir / required[6]).read_text(encoding="utf-8"))

    if source.empty or (source.get("status", pd.Series(dtype=str)) != "PASS").any():
        failures.append("OFFICIAL_SOURCE_LEDGER_NOT_ALL_PASS")
    if elig.empty:
        failures.append("EMPTY_ELIGIBILITY")
    if elig.get("security_code", pd.Series(dtype=str)).duplicated().any():
        failures.append("DUPLICATE_ELIGIBILITY_CODES")
    if investable.get("security_code", pd.Series(dtype=str)).duplicated().any():
        failures.append("DUPLICATE_INVESTABLE_CODES")
    if "combined_status" in investable and not investable["combined_status"].str.startswith("BUY_ELIGIBLE").all():
        failures.append("NON_BUY_ELIGIBLE_IN_INVESTABLE")
    if "combined_status" in investable and (investable["combined_status"] == "SELL_ONLY").any():
        failures.append("SELL_ONLY_IN_INVESTABLE")
    if quality.get("future_source_count", 0) != 0:
        failures.append("FUTURE_SOURCE_PRESENT")
    if quality.get("source_conflict_count", 0) != 0:
        failures.append("SOURCE_CONFLICT_PRESENT")
    if decision.get("trade_authority") != "NONE":
        failures.append("TRADE_AUTHORITY_VIOLATION")
    for key in ("candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"):
        if decision.get(key, 0) != 0:
            failures.append("FORBIDDEN_MUTATION:" + key)

    manifest_files = manifest.get("files", {})
    for name, expected in manifest_files.items():
        path = release_dir / name
        if not path.exists() or sha256(path) != expected:
            failures.append("MANIFEST_HASH_MISMATCH:" + name)

    covered = set(investable.get("security_code", [])) | set(exclusions.get("security_code", []))
    expected_rows = int(quality.get("fmdl5e_input_rows", len(covered)))
    if len(covered) != expected_rows:
        failures.append(f"FMDL5E_COVERAGE_MISMATCH:{len(covered)}!={expected_rows}")

    return {
        "status": "PASS" if not failures else "BLOCKED",
        "failures": failures,
        "metrics": {
            "official_sources": len(source), "eligibility_rows": len(elig),
            "investable_rows": len(investable), "excluded_rows": len(exclusions),
            "fmdl5e_covered_rows": len(covered),
        },
        "trade_authority": "NONE",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--release-dir", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    result = validate(a.release_dir)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
