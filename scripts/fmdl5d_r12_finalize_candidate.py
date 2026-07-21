#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from fmdl5d_core import file_sha256, stable_hash
from run_fmdl5d_disclosure_financial_store import now_utc


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--contract", default="config/fmdl5d_hkex_disclosure_financial_contract.json")
    parser.add_argument("--registry", default="config/fmdl5d_hk_financial_field_registry.json")
    args = parser.parse_args()

    candidate = Path(args.candidate)
    contract = read_json(Path(args.contract))
    registry = read_json(Path(args.registry))
    quality = read_json(candidate / "FMDL5D_QUALITY_REPORT.json")
    runtime = read_json(candidate / "FMDL5D_R1_RUNTIME_REPORT.json")
    source_registry = read_json(candidate / "FMDL5D_SOURCE_REGISTRY.json")
    decision = read_json(candidate / "FMDL5D_DECISION.json")

    disclosure = runtime.get("disclosure_status", {})
    if disclosure.get("program_id") != "FMDL-5D-R1.2":
        raise ValueError(f"R12_DISCLOSURE_STATUS_MISSING:{disclosure.get('program_id')}")
    if disclosure.get("runtime_failures"):
        raise ValueError(f"R12_DISCLOSURE_RUNTIME_FAILURES:{disclosure['runtime_failures']}")

    runtime["program_id"] = "FMDL-5D-R1.2"
    runtime["repair_round"] = "FMDL-5D-R1.2"
    runtime["runtime_orchestration"] = "MONTH_SHARDED_BOUNDED_CHECKPOINTED_DISCLOSURE_PLUS_SECURITY_SHARDED_FINANCIAL_AGGREGATION"
    write_json(candidate / "FMDL5D_R1_RUNTIME_REPORT.json", runtime)

    limitations = list(quality.get("controlled_limitations", []))
    limitations = [
        item
        for item in limitations
        if "FMDL-5D-R1 executes disclosure" not in item and "FMDL-5D-R1.1 executes HKEXnews disclosure" not in item
    ]
    limitations.append(
        "FMDL-5D-R1.2 executes each HKEXnews disclosure month as an independently rerunnable job with weekly incremental checkpoints, request-level hard deadlines and pagination caps before deterministic aggregation."
    )
    quality["controlled_limitations"] = limitations
    quality["r12_disclosure_expected_month_count"] = disclosure.get("expected_month_count")
    quality["r12_disclosure_completed_month_count"] = disclosure.get("completed_month_count")
    quality["r12_disclosure_warning_count"] = disclosure.get("warning_count")
    write_json(candidate / "FMDL5D_QUALITY_REPORT.json", quality)

    source_registry["runtime_orchestration"] = "FMDL-5D-R1.2_MONTH_SHARDED_BOUNDED_DISCLOSURE_AND_SECURITY_SHARDED_FINANCIAL_AGGREGATION"
    source_registry["disclosure_checkpoint_summary"] = {
        "expected_month_count": disclosure.get("expected_month_count"),
        "completed_month_count": disclosure.get("completed_month_count"),
        "warning_count": disclosure.get("warning_count"),
        "request_policy": disclosure.get("request_policy"),
    }
    write_json(candidate / "FMDL5D_SOURCE_REGISTRY.json", source_registry)

    primary_files = [
        "FMDL5D_HKEX_FINANCIAL_DISCLOSURES.csv",
        "FMDL5D_MAPPED_RAW_FACTS.parquet",
        "FMDL5D_NORMALIZED_FINANCIAL_FACTS.parquet",
        "FMDL5D_ISSUER_FINANCIAL_CURRENT.csv",
        "FMDL5D_UNMAPPED_FIELD_CATALOG.csv",
        "FMDL5D_FAILURES.csv",
        "FMDL5D_QUALITY_REPORT.json",
        "FMDL5D_SOURCE_REGISTRY.json",
        "FMDL5D_R1_RUNTIME_REPORT.json",
    ]
    data_hashes = {name: file_sha256(candidate / name) for name in primary_files}
    canonical_sha256 = stable_hash(
        {
            "program_id": "FMDL-5D",
            "source_release_id": decision["source_release_id"],
            "metrics": decision["metrics"],
            "data_hashes": data_hashes,
            "contract_version": contract["contract_version"],
            "registry_version": registry["registry_version"],
            "runtime_orchestration": "R1.2_MONTH_SHARDED_BOUNDED_DISCLOSURE_PLUS_SECURITY_SHARDED_FINANCIAL",
        }
    )
    market_max_date = pd.Timestamp(decision["metrics"]["market_max_date"])
    release_id = f"FMDL5D_{market_max_date.strftime('%Y%m%d')}_{canonical_sha256[:12]}"

    decision["repair_round"] = "FMDL-5D-R1.2"
    decision["canonical_sha256"] = canonical_sha256
    decision["release_id"] = release_id
    decision["limitations"] = limitations
    write_json(candidate / "FMDL5D_DECISION.json", decision)

    manifest_files = primary_files + ["FMDL5D_DECISION.json"]
    manifest = {
        "program_id": "FMDL-5D",
        "repair_round": "FMDL-5D-R1.2",
        "release_id": release_id,
        "release_sequence": decision["release_sequence"],
        "source_release_id": decision["source_release_id"],
        "canonical_sha256": canonical_sha256,
        "generated_at_utc": now_utc(),
        "files": {
            name: {"sha256": file_sha256(candidate / name), "size_bytes": (candidate / name).stat().st_size}
            for name in manifest_files
        },
    }
    write_json(candidate / "FMDL5D_MANIFEST.json", manifest)
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
