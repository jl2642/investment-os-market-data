#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

INPUT_RELEASE_ID = "FMDL5A_20260720_031b3430a7d0"
INPUT_PATH = Path("outputs/fmdl5a/current/FMDL5A_CANONICAL_UNIVERSE.csv")
EXPECTED_COUNT = 644


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def classify_security(name_zh: str, name_en: str) -> tuple[str, str]:
    zh = name_zh.upper()
    en = name_en.upper()
    if "REIT" in en or "房地产投资信托" in name_zh or "房产信托" in name_zh:
        return "REIT", "NAME_MARKER_CLASSIFIED"
    if "ETF" in en or "ETF" in zh or "交易所买卖基金" in name_zh:
        return "ETF", "NAME_MARKER_CLASSIFIED"
    return "UNKNOWN", "PENDING_SEMANTIC_ENRICHMENT"


def to_bool(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def build_row(source: dict[str, str]) -> dict[str, object]:
    code = source["stock_code"].zfill(5)
    security_type, semantic_status = classify_security(source["name_cn"], source["name_en"])
    return {
        "security_id": f"HKEX:{code}",
        "issuer_id": f"HKISSUER-PROVISIONAL:{code}",
        "stock_code_5d": code,
        "ticker_hk": f"{code}.HK",
        "name_zh": source["name_cn"].strip(),
        "name_en": source["name_en"].strip(),
        "market": "HKEX",
        "country_of_listing": "HK",
        "trading_currency": "HKD",
        "security_type": security_type,
        "identity_status": "PROVISIONAL_SECURITY_LEVEL_IDENTITY",
        "semantic_enrichment_status": semantic_status,
        "shanghai_connect": to_bool(source["shanghai_connect"]),
        "shenzhen_connect": to_bool(source["shenzhen_connect"]),
        "eligibility_status": source["eligibility_status"].strip(),
        "source_release_id": INPUT_RELEASE_ID,
    }


def build(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    source_bytes = INPUT_PATH.read_bytes()
    with INPUT_PATH.open("r", encoding="utf-8-sig", newline="") as fh:
        source_rows = list(csv.DictReader(fh))
    rows = [build_row(row) for row in source_rows]
    rows.sort(key=lambda row: str(row["stock_code_5d"]))

    hard_failures: list[str] = []
    if len(rows) != EXPECTED_COUNT:
        hard_failures.append(f"ROW_COUNT_MISMATCH:{len(rows)}")
    if len({row["security_id"] for row in rows}) != len(rows):
        hard_failures.append("DUPLICATE_SECURITY_ID")
    if len({row["stock_code_5d"] for row in rows}) != len(rows):
        hard_failures.append("DUPLICATE_STOCK_CODE")
    if any(row["source_release_id"] != INPUT_RELEASE_ID for row in rows):
        hard_failures.append("SOURCE_RELEASE_MISMATCH")

    fields = list(rows[0].keys()) if rows else []
    csv_path = output / "FMDL5B1_HK_SECURITY_MASTER.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    ndjson_path = output / "FMDL5B1_HK_SECURITY_MASTER.ndjson"
    ndjson_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    master_sha = sha256_bytes(ndjson_path.read_bytes())
    release_id = f"FMDL5B1_20260720_{master_sha[:12]}"
    type_counts: dict[str, int] = {}
    for row in rows:
        key = str(row["security_type"])
        type_counts[key] = type_counts.get(key, 0) + 1

    decision = {
        "program_id": "FMDL-5B-1",
        "status": "FMDL5B1_SECURITY_IDENTITY_CONTRACT_AND_CANONICAL_MASTER_ACCEPTED" if not hard_failures else "FMDL5B1_REJECTED",
        "release_id": release_id,
        "release_sequence": 11,
        "authority": "HK_SECURITY_IDENTITY_MASTER_ONLY",
        "source_release_id": INPUT_RELEASE_ID,
        "source_universe_sha256": sha256_bytes(source_bytes),
        "security_master_sha256": master_sha,
        "metrics": {
            "source_count": len(source_rows),
            "security_master_count": len(rows),
            "unique_security_id_count": len({row["security_id"] for row in rows}),
            "unique_stock_code_count": len({row["stock_code_5d"] for row in rows}),
            "security_type_counts": type_counts,
            "pending_semantic_enrichment_count": sum(row["semantic_enrichment_status"] == "PENDING_SEMANTIC_ENRICHMENT" for row in rows),
        },
        "hard_failures": hard_failures,
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "trade_authority": "NONE",
        "next_gate": "FMDL-5B-2_ISSUER_AND_CROSS_MARKET_SEMANTICS",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output / "FMDL5B1_DECISION.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest_files = {}
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name != "FMDL5B1_MANIFEST.json":
            manifest_files[path.name] = {"sha256": sha256_bytes(path.read_bytes()), "size_bytes": path.stat().st_size}
    manifest = {"program_id": "FMDL-5B-1", "release_id": release_id, "files": manifest_files}
    (output / "FMDL5B1_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return decision


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    decision = build(Path(args.output))
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not decision["hard_failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
