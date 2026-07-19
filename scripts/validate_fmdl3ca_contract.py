from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONTRACT = ROOT / "config/fmdl3c_factor_contract.json"
SCHEMA = ROOT / "schemas/fmdl3c_factor_contract_v1.schema.json"
DICTIONARY = ROOT / "config/fmdl3c_factor_dictionary.csv"
ENTRY = ROOT / "outputs/status/FMDL3B4_LAST_SUCCESS.json"
REGISTRY = ROOT / "config/fmdl3b_field_registry.json"
CANDIDATE = ROOT / "outputs/financial_factors/contract/candidate"
DESIGN_FILES = [
    CONTRACT,
    SCHEMA,
    DICTIONARY,
    ROOT / "docs/FMDL-3C_PRODUCT_SPEC.md",
    ROOT / "docs/FMDL-3C_VALIDATION_RULES.md",
    ROOT / "docs/FMDL-3C_ROADMAP.md",
]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recursive_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from recursive_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from recursive_keys(item)


def main() -> int:
    contract = load_json(CONTRACT)
    schema = load_json(SCHEMA)
    entry = load_json(ENTRY)
    registry = load_json(REGISTRY)
    schema_errors = sorted(Draft202012Validator(schema).iter_errors(contract), key=lambda e: list(e.path))

    with DICTIONARY.open(encoding="utf-8-sig", newline="") as handle:
        dictionary_rows = list(csv.DictReader(handle))

    factors = dictionary_rows
    factor_ids = [item["factor_id"] for item in factors]
    factor_names = [item["factor_name"] for item in factors]
    family_ids = {item["family_id"] for item in contract["factor_families"]}
    derived = contract["derived_input_definitions"]
    registry_ids = {item["line_item_id"] for item in registry["fields"]}
    deferred_ids = {item["factor_id"] for item in contract["deferred_factor_policy"]["deferred_factors"]}
    dictionary_ids = factor_ids
    available_tokens = set(derived)

    derived_sources_valid = True
    for token, definition in derived.items():
        if "source_line_item_id" in definition and definition["source_line_item_id"] not in registry_ids:
            derived_sources_valid = False
        if "source_token" in definition and definition["source_token"] not in available_tokens:
            derived_sources_valid = False
        if "source_factor_id" in definition and definition["source_factor_id"] not in factor_ids:
            derived_sources_valid = False

    all_inputs_declared = all(set(item["required_inputs"].split("|")).issubset(available_tokens) for item in factors)
    growth_comparable = all(item["comparability_requirement"] == "REQUIRED" for item in factors if item["family_id"] == "GROWTH")
    ttm_rule_complete = (
        contract["temporal_policy"]["derived_available_from_rule"].startswith("max(")
        and bool(contract["temporal_policy"]["ttm_rule"]["interim"])
        and all(item["comparability_requirement"] == "REQUIRED" for item in factors if "TTM" in item["period_basis"])
    )
    sector_fail_closed = (
        "UNRESOLVED" in contract["sector_profiles"]["required_profiles"]
        and all("UNRESOLVED" not in item["applicable_sector_profiles"] for item in factors)
        and "must not" in contract["sector_profiles"]["routing_rule"]
    )
    no_score = not any(key.lower() in {"score", "weight", "composite_score"} for key in recursive_keys(contract))
    no_deferred_mvp = deferred_ids.isdisjoint(factor_ids)
    required_columns = contract["factor_dictionary"]["required_columns"]
    dictionary_matches = len(factors) == contract["factor_dictionary"]["factor_count"] and list(factors[0].keys()) == required_columns and len(dictionary_ids) == len(set(dictionary_ids))
    dictionary_trade_none = all(item.get("trade_authority") == "NONE" for item in dictionary_rows)
    all_trade_none = contract["trade_authority"] == "NONE" and all(item["trade_authority"] == "NONE" for item in factors)

    checks = {
        "ENTRY_STATEMENT_CURRENT_ACCEPTED": entry.get("status") == contract["entry_gate"]["required_status"],
        "ENTRY_EXIT_GATE_MATCHES": entry.get("status") == "FMDL3B4_POINT_IN_TIME_STATEMENT_STORE_ACCEPTED",
        "CONTRACT_SCHEMA_VALID": not schema_errors,
        "FACTOR_IDS_UNIQUE": len(factor_ids) == len(set(factor_ids)),
        "FACTOR_NAMES_UNIQUE": len(factor_names) == len(set(factor_names)),
        "FACTOR_DICTIONARY_MATCHES_CONTRACT": dictionary_matches,
        "FACTOR_FAMILIES_VALID": all(item["family_id"] in family_ids for item in factors),
        "ALL_MVP_INPUTS_DECLARED": all_inputs_declared,
        "ALL_MVP_INPUTS_AVAILABLE_OR_DERIVABLE": derived_sources_valid,
        "ALL_FACTORS_HAVE_DENOMINATOR_POLICY": all(bool(item["denominator_rule"]) for item in factors),
        "ALL_GROWTH_FACTORS_REQUIRE_COMPARABILITY": growth_comparable,
        "ALL_TTM_FACTORS_INHERIT_LATEST_INPUT_AVAILABILITY": ttm_rule_complete,
        "SECTOR_ROUTING_FAILS_CLOSED": sector_fail_closed,
        "NO_DEFERRED_FACTOR_MARKED_MVP": no_deferred_mvp,
        "NO_COMPOSITE_SCORE_DEFINED": no_score,
        "DICTIONARY_ZERO_TRADE_AUTHORITY": dictionary_trade_none,
        "ZERO_TRADE_AUTHORITY": all_trade_none,
    }
    failures = [name for name, passed in checks.items() if not passed]
    release_id = f"FMDL3CA_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"
    status = contract["exit_status"] if not failures else "FMDL3CA_REMEDIATION_REQUIRED"

    if CANDIDATE.exists():
        shutil.rmtree(CANDIDATE)
    CANDIDATE.mkdir(parents=True)
    for source in DESIGN_FILES:
        shutil.copy2(source, CANDIDATE / source.name)

    decision = {
        "decision_version": "1.0.0",
        "release_id": release_id,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "program_id": "FMDL-3C-A",
        "status": status,
        "hard_failures": failures,
        "checks": [{"check_id": name, "status": "PASS" if passed else "FAIL"} for name, passed in checks.items()],
        "metrics": {
            "factor_count": len(factors),
            "mvp_required_factor_count": sum(item["build_state"] == "MVP_REQUIRED" for item in factors),
            "diagnostic_factor_count": sum(item["build_state"] == "MVP_DIAGNOSTIC" for item in factors),
            "deferred_factor_count": len(deferred_ids),
            "factor_family_count": len(family_ids),
            "derived_input_token_count": len(derived),
            "schema_error_count": len(schema_errors),
        },
        "schema_errors": [error.message for error in schema_errors],
        "input_release_id": entry.get("release_id"),
        "authority": contract["authority"],
        "trade_authority": "NONE",
        "next_gate": contract["next_gate"],
    }
    (CANDIDATE / "FMDL3CA_DECISION.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "manifest_version": "1.0.0",
        "release_id": release_id,
        "files": [],
        "authority": contract["authority"],
        "trade_authority": "NONE",
    }
    for path in sorted(CANDIDATE.iterdir()):
        if path.is_file() and path.name != "FMDL3CA_MANIFEST.json":
            manifest["files"].append({"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size})
    (CANDIDATE / "FMDL3CA_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    validation = {
        "validation_version": "1.0.0",
        "release_id": release_id,
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": failures,
        "checks": decision["checks"],
        "metrics": decision["metrics"],
        "manifest_hash_errors": [],
        "authority": contract["authority"],
        "trade_authority": "NONE",
        "next_gate": contract["next_gate"],
    }
    (CANDIDATE / "FMDL3CA_VALIDATION.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
