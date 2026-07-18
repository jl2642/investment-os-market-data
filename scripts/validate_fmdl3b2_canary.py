from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from scripts import fmdl3b_core as core
from scripts import fmdl3b_semantic_overrides as semantic

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3b2_full_build.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    cfg = load(CONFIG)
    root = ROOT / cfg["publication"]["candidate_root"]
    decision = load(root / "FMDL3B2_CANARY_DECISION.json")
    manifest = load(root / "FMDL3B2_CANARY_MANIFEST.json")
    runtime = load(root / "FMDL3B2_CANARY_RUNTIME_STORAGE.json")
    raw = pd.read_parquet(root / "FMDL3B2_CANARY_RAW_FACTS.parquet")
    normalized = pd.read_parquet(root / "FMDL3B2_CANARY_NORMALIZED_LONG.parquet")
    revisions = pd.read_parquet(root / "FMDL3B2_CANARY_REVISION_LEDGER.parquet")
    sources = pd.read_parquet(root / "FMDL3B2_CANARY_SOURCE_INDEX.parquet")
    support = pd.read_csv(root / "FMDL3B2_CANARY_SUPPORT_MAP.csv", encoding="utf-8-sig")
    symbols = pd.read_csv(root / "FMDL3B2_CANARY_SYMBOLS.csv", encoding="utf-8-sig")
    conflicts = pd.read_csv(root / "FMDL3B2_CANARY_CONFLICT_LOG.csv", encoding="utf-8-sig")
    checks_frame = pd.read_csv(root / "FMDL3B2_CANARY_VALIDATION_CHECKS.csv", encoding="utf-8-sig")

    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: Any) -> None:
        checks.append({"check_id": check_id, "status": "PASS" if passed else "FAIL", "detail": detail})

    add("DECISION_STATUS", decision.get("status") == "FMDL3B2_CANARY_ACCEPTED_FULL_UNIVERSE_MATRIX_AUTHORIZED", decision.get("status"))
    add("DECISION_HARD_FAILURES", decision.get("hard_failures") == [], decision.get("hard_failures"))
    add("CANARY_SYMBOL_COUNT", len(symbols) >= cfg["acceptance_policy"]["minimum_canary_symbol_count"], len(symbols))
    add("SUPPORT_MAP_EXACT_SYMBOLS", set(symbols["symbol"]) == set(support["symbol"]), sorted(set(symbols["symbol"]) ^ set(support["symbol"])))
    add("ALL_SUPPORTED_OR_QUARANTINED", set(support["statement_status"]).issubset({"SUPPORTED", "QUARANTINED"}), sorted(set(support["statement_status"])))

    non_bse = support[support["board"] != "BSE"]
    supported_ratio = float((non_bse["statement_status"] == "SUPPORTED").mean()) if len(non_bse) else 0.0
    primary_share = float(non_bse["primary_only"].astype(bool).mean()) if len(non_bse) else 0.0
    add("NON_BSE_BUNDLE_GATE", supported_ratio >= cfg["acceptance_policy"]["minimum_non_bse_primary_bundle_success_ratio"], supported_ratio)
    add("PRIMARY_ONLY_SHARE", primary_share >= cfg["acceptance_policy"]["minimum_primary_only_share"], primary_share)
    bse = support[support["board"] == "BSE"]
    bse_ok = len(bse) > 0 and bse["official_document_index_available"].astype(bool).all()
    add("BSE_OFFICIAL_DOCUMENT_INDEX", bse_ok, len(bse))

    pit_ratio = float(raw["available_from"].notna().mean()) if len(raw) else 0.0
    future = int((pd.to_datetime(raw["available_from"], errors="coerce", utc=True) < pd.to_datetime(raw["announcement_date"], errors="coerce", utc=True)).sum()) if len(raw) else 0
    add("PIT_MATCH_GATE", pit_ratio >= cfg["acceptance_policy"]["minimum_official_pit_match_ratio"], pit_ratio)
    add("ZERO_FUTURE_FACTS", future == 0, future)

    source_ids = set(sources["source_id"].dropna())
    missing_source = set(normalized["source_id"].dropna()) - source_ids
    decision_grade = normalized["decision_grade_eligible"].astype(bool)
    source_less = int((decision_grade & normalized["source_id"].isna()).sum())
    add("SOURCE_LINEAGE", not missing_source, sorted(missing_source))
    add("ZERO_SOURCELESS_DECISION_GRADE", source_less == 0, source_less)
    duplicate = core.duplicate_effective_intervals(normalized)
    add("ZERO_DUPLICATE_EFFECTIVE_INTERVALS", duplicate == 0, duplicate)
    ambiguity = semantic.ambiguous_source_mapping_groups(raw)
    add("ZERO_AMBIGUOUS_MAPPING_GROUPS", len(ambiguity) == 0, len(ambiguity))
    unclassified = int((conflicts["status"] != "CLASSIFIED_CONTROLLED_EXCLUSION").sum()) if len(conflicts) else 0
    add("ALL_CONFLICTS_CLASSIFIED", unclassified == 0, unclassified)
    add("STATEMENT_FAMILY_REPRESENTATION", set(normalized["statement"]) == {"balance_sheet", "income_statement", "cash_flow"}, sorted(set(normalized["statement"])))
    add("REVISION_LEDGER_NONEMPTY", len(revisions) > 0 and revisions["revision_sequence"].notna().all(), len(revisions))
    add("PERFORMED_CHECKS_NO_FAILURE", not len(checks_frame) or not (checks_frame["result"] == "FAIL").any(), checks_frame["result"].value_counts().to_dict() if len(checks_frame) else {})

    roundtrip = runtime["parquet_roundtrip"]
    add("PARQUET_ROUNDTRIP", all(roundtrip.values()), roundtrip)
    add("MAX_FILE_SIZE", runtime["maximum_canary_file_mib"] < cfg["storage"]["maximum_git_file_mib"], runtime["maximum_canary_file_mib"])
    add("NORMALIZED_STORAGE_PROJECTION", runtime["projected_full_universe_normalized_mib"] <= cfg["storage"]["maximum_projected_normalized_store_mib"], runtime["projected_full_universe_normalized_mib"])
    add("RUNTIME_PROJECTION", runtime["projected_wall_minutes_per_shard_at_canary_rate"] > 0, runtime["projected_wall_minutes_per_shard_at_canary_rate"])

    manifest_errors: list[str] = []
    for entry in manifest["files"]:
        path = root / entry["path"]
        if not path.exists() or sha256(path) != entry["sha256"] or path.stat().st_size != entry["bytes"]:
            manifest_errors.append(entry["path"])
    add("MANIFEST_INTEGRITY", not manifest_errors, manifest_errors)
    trade_values = set(raw["trade_authority"].dropna()) | set(normalized["trade_authority"].dropna())
    add("ZERO_TRADE_AUTHORITY", trade_values == {"NONE"} and decision.get("trade_authority") == "NONE", sorted(trade_values))

    failures = [item["check_id"] for item in checks if item["status"] != "PASS"]
    payload = {
        "validation_version": "1.0.0",
        "run_id": decision["run_id"],
        "program_id": "FMDL-3B-2-CANARY",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "hard_failures": failures,
        "decision_status": decision["status"],
        "metrics": decision["metrics"],
        "runtime_storage": runtime,
        "authority": decision["authority"],
        "trade_authority": "NONE",
        "next_gate": decision["next_gate"],
    }
    dump(root / "FMDL3B2_CANARY_VALIDATION.json", payload)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
