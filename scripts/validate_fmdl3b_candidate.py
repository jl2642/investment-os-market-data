from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from jsonschema import Draft202012Validator

from scripts import fmdl3b_core as core

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/fmdl3b_statement_store.json"
SCHEMA = ROOT / "schemas/fmdl3b_statement_store.schema.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> int:
    cfg = load(CFG)
    schema = load(SCHEMA)
    schema_errors = [error.message for error in Draft202012Validator(schema).iter_errors(cfg)]
    root = ROOT / cfg["publication"]["candidate_root"]
    required = [
        "FMDL3B_RAW_FACTS.csv",
        "FMDL3B_NORMALIZED_LONG.csv",
        "FMDL3B_SOURCE_INDEX.csv",
        "FMDL3B_REVISION_LEDGER.csv",
        "FMDL3B_COMPARABILITY_BRIDGE.csv",
        "FMDL3B_CONFLICT_LOG.csv",
        "FMDL3B_QA_FLAGS.csv",
        "FMDL3B_VALIDATION_CHECKS.csv",
        "FMDL3B_SUPPORT_MAP.csv",
        "FMDL3B_COVERAGE.csv",
        "FMDL3B1_DECISION.json",
        "FMDL3B1_MANIFEST.json",
    ]
    checks: list[dict[str, Any]] = []

    def add(check_id: str, status: str, detail: Any) -> None:
        checks.append({"check_id": check_id, "status": status, "detail": detail})

    add("CONFIG_SCHEMA", "PASS" if not schema_errors else "FAIL", schema_errors)
    missing = [name for name in required if not (root / name).exists()]
    add("REQUIRED_OUTPUTS", "PASS" if not missing else "FAIL", missing)
    if missing:
        payload = {"validation_version": "1.0.0", "status": "FAIL", "checks": checks, "hard_failures": ["REQUIRED_OUTPUTS"], "trade_authority": "NONE"}
        dump(root / "FMDL3B1_VALIDATION.json", payload)
        return 1

    raw = pd.read_csv(root / "FMDL3B_RAW_FACTS.csv", encoding="utf-8-sig")
    normalized = pd.read_csv(root / "FMDL3B_NORMALIZED_LONG.csv", encoding="utf-8-sig")
    sources = pd.read_csv(root / "FMDL3B_SOURCE_INDEX.csv", encoding="utf-8-sig")
    support = pd.read_csv(root / "FMDL3B_SUPPORT_MAP.csv", encoding="utf-8-sig")
    conflicts = pd.read_csv(root / "FMDL3B_CONFLICT_LOG.csv", encoding="utf-8-sig")
    revisions = pd.read_csv(root / "FMDL3B_REVISION_LEDGER.csv", encoding="utf-8-sig")
    decision = load(root / "FMDL3B1_DECISION.json")

    add("DECISION_STATUS", "PASS" if decision.get("status") == "FMDL3B1_ACCEPTED_NORMALIZATION_PILOT" else "FAIL", decision.get("status"))
    add("RAW_FACT_STORE_NONEMPTY", "PASS" if len(raw) > 0 else "FAIL", len(raw))
    add("NORMALIZED_STORE_NONEMPTY", "PASS" if len(normalized) >= cfg["acceptance_policy"]["minimum_mapped_fact_count"] else "FAIL", len(normalized))
    add("SOURCE_INDEX_NONEMPTY", "PASS" if len(sources) > 0 else "FAIL", len(sources))

    missing_source = set(normalized["source_id"].dropna()) - set(sources["source_id"].dropna())
    add("SOURCE_LINEAGE", "PASS" if normalized["source_id"].notna().all() and not missing_source else "FAIL", sorted(missing_source))
    decision_grade_count = int(normalized["decision_grade_eligible"].astype(str).str.lower().eq("true").sum())
    add("MINIMUM_DECISION_GRADE_FACTS", "PASS" if decision_grade_count >= cfg["acceptance_policy"]["minimum_decision_grade_fact_count"] else "FAIL", decision_grade_count)

    future = int((pd.to_datetime(raw["available_from"], errors="coerce", utc=True) < pd.to_datetime(raw["announcement_date"], errors="coerce", utc=True)).sum())
    add("ZERO_FUTURE_FACTS", "PASS" if future == 0 else "FAIL", future)
    duplicate = core.duplicate_effective_intervals(normalized)
    add("ZERO_DUPLICATE_EFFECTIVE_INTERVALS", "PASS" if duplicate == 0 else "FAIL", duplicate)

    unclassified = int((conflicts.get("status", pd.Series(dtype=str)) != "CLASSIFIED_CONTROLLED_EXCLUSION").sum()) if len(conflicts) else 0
    add("ALL_CONFLICTS_CLASSIFIED", "PASS" if unclassified == 0 else "FAIL", unclassified)

    supported_non_bse = support[support["board"] != "BSE"]
    ratio = float((supported_non_bse["statement_status"] == "SUPPORTED").mean()) if len(supported_non_bse) else 0.0
    add("SUPPORTED_STATEMENT_GATE", "PASS" if ratio >= cfg["acceptance_policy"]["minimum_supported_symbol_statement_bundle_ratio"] else "FAIL", ratio)

    bse = support[support["board"] == "BSE"]
    bse_ratio = float(bse["official_document_index_available"].astype(str).str.lower().eq("true").mean()) if len(bse) else 0.0
    add("BSE_OFFICIAL_DOCUMENT_INDEX", "PASS" if bse_ratio == 1.0 else "FAIL", bse_ratio)

    required_profiles = set(cfg["scope"]["required_profiles"])
    profiles = set(support["profile"])
    add("PROFILE_REPRESENTATION", "PASS" if required_profiles.issubset(profiles) else "FAIL", sorted(required_profiles - profiles))
    add("STATEMENT_FAMILY_REPRESENTATION", "PASS" if set(normalized["statement"]) == {"balance_sheet", "income_statement", "cash_flow"} else "FAIL", sorted(set(normalized["statement"])))
    add("REVISION_LEDGER", "PASS" if len(revisions) > 0 and revisions["revision_sequence"].notna().all() else "FAIL", len(revisions))

    source_less = ((normalized["decision_grade_eligible"].astype(str).str.lower() == "true") & normalized["source_id"].isna()).any()
    add("ZERO_SOURCELESS_DECISION_GRADE", "PASS" if not source_less else "FAIL", "checked")
    add("ZERO_TRADE_AUTHORITY", "PASS" if set(raw["trade_authority"]) == {"NONE"} and set(normalized["trade_authority"]) == {"NONE"} else "FAIL", "raw+normalized")

    failures = [check["check_id"] for check in checks if check["status"] != "PASS"]
    payload = {
        "validation_version": "1.0.0",
        "run_id": decision["run_id"],
        "program_id": "FMDL-3B-1",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "hard_failures": failures,
        "decision_status": decision["status"],
        "metrics": decision["metrics"],
        "authority": decision["authority"],
        "trade_authority": "NONE",
        "next_phase": "FMDL-3B-2",
    }
    dump(root / "FMDL3B1_VALIDATION.json", payload)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
