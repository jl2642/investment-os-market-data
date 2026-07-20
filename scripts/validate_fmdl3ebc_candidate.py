from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts import fmdl3ebc_core as bc

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3ebc_incremental_refresh.json"


def main() -> int:
    cfg = bc.read_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    decision = bc.read_json(candidate / "FMDL3EBC_DECISION.json")
    manifest = bc.read_json(candidate / "FMDL3EBC_MANIFEST.json")
    market = pd.read_parquet(candidate / "FMDL3EB_MARKET_DELTA.parquet")
    events = pd.read_parquet(candidate / "FMDL3EBC_DELTA_EVENT_LEDGER.parquet")
    financial_events = pd.read_parquet(candidate / "FMDL3EC_FINANCIAL_EVENT_LEDGER.parquet")
    facts = pd.read_parquet(candidate / "FMDL3EC_FINANCIAL_FACT_DELTA.parquet")
    versions = pd.read_parquet(candidate / "FMDL3EC_FINANCIAL_VERSION_LEDGER.parquet")
    scope = pd.read_csv(candidate / "FMDL3EBC_AFFECTED_SCOPE.csv", encoding="utf-8-sig")
    errors: list[str] = []
    expected_files = {row["path"]: row for row in manifest["files"]}
    for name, row in expected_files.items():
        path = candidate / name
        if not path.exists() or bc.sha256_file(path) != row["sha256"] or int(path.stat().st_size) != int(row["bytes"]):
            errors.append(f"MANIFEST_MISMATCH:{name}")
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        errors.append("DECISION_NOT_ACCEPTED")
    if market["symbol"].duplicated().any():
        errors.append("DUPLICATE_MARKET_SYMBOL")
    if events["event_id"].duplicated().any():
        errors.append("DUPLICATE_EVENT_ID")
    if len(scope) != len(events):
        errors.append("AFFECTED_SCOPE_NOT_EXPLICIT")
    if not set(events["trade_authority"].astype(str)).issubset({"NONE"}):
        errors.append("TRADE_AUTHORITY_PRESENT")
    if len(financial_events) < int(cfg["financial"]["minimum_financial_event_count"]):
        errors.append("FINANCIAL_EVENT_COUNT_TOO_LOW")
    if not (financial_events["event_type"] == "FINANCIAL_DISCLOSURE_NEW").any():
        errors.append("FIRST_DISCLOSURE_CASE_MISSING")
    if not (financial_events["event_type"] != "FINANCIAL_DISCLOSURE_NEW").any():
        errors.append("REVISION_CASE_MISSING")
    revision_event_ids = set(financial_events.loc[financial_events["event_type"] != "FINANCIAL_DISCLOSURE_NEW", "event_id"].astype(str))
    if revision_event_ids and not any(len(group) >= 2 for event_id, group in versions.groupby("event_id") if str(event_id) in revision_event_ids):
        errors.append("OLD_VERSION_NOT_PRESERVED")
    future_count = 0
    target = pd.Timestamp(decision["metrics"]["refreshed_market_as_of_date"], tz="Asia/Shanghai").tz_convert("UTC")
    if len(versions):
        available = pd.to_datetime(versions["available_from"], errors="coerce", utc=True)
        future_count += int((available > target).sum())
    if len(facts):
        available = pd.to_datetime(facts["refreshed_available_from"], errors="coerce", utc=True)
        future_count += int((available > target).sum())
    if future_count:
        errors.append(f"FUTURE_INFORMATION:{future_count}")
    recomputed = {
        "market_delta": bc.semantic_frame_hash(market),
        "financial_events": bc.semantic_frame_hash(financial_events),
        "financial_facts": bc.semantic_frame_hash(facts),
        "financial_versions": bc.semantic_frame_hash(versions),
        "affected_scope": bc.semantic_frame_hash(scope),
    }
    if recomputed != decision.get("semantic_hashes"):
        errors.append("SEMANTIC_HASH_REPLAY_MISMATCH")
    check_prefixes = [
        "MANIFEST", "DECISION", "DUPLICATE_MARKET_SYMBOL", "DUPLICATE_EVENT_ID",
        "AFFECTED_SCOPE", "TRADE_AUTHORITY", "FINANCIAL_EVENT_COUNT",
        "FIRST_DISCLOSURE", "REVISION_CASE", "OLD_VERSION", "FUTURE_INFORMATION", "SEMANTIC_HASH"
    ]
    checks = [
        {"check_id": name, "status": "FAIL" if any(error.startswith(name) for error in errors) else "PASS"}
        for name in check_prefixes
    ]
    validation = {
        "validation_version": "1.0.0",
        "release_id": decision["release_id"],
        "program_id": "FMDL-3E-BC",
        "status": "PASS" if not errors else "FAIL",
        "hard_failures": errors,
        "checks": checks,
        "metrics": {
            **decision["metrics"],
            "manifest_error_count": sum(error.startswith("MANIFEST") for error in errors),
            "future_information_count_independent": future_count,
            "semantic_hash_error_count": int(recomputed != decision.get("semantic_hashes")),
        },
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    bc.write_json(candidate / "FMDL3EBC_VALIDATION.json", validation)
    bc.write_json(candidate / "FMDL3EBC_MANIFEST.json", bc.manifest_for_directory(candidate, decision["release_id"]))
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
