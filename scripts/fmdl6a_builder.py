from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

PROGRAM_ID = "FMDL-6A"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def validate_contract(repo_root: Path, contract_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    contract = load_json(contract_path)
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def check(check_id: str, condition: bool, actual: Any, expected: Any) -> None:
        checks.append({"check_id": check_id, "status": "PASS" if condition else "FAIL", "actual": actual, "expected": expected})
        if not condition:
            errors.append(check_id)

    check("PROGRAM_ID", contract.get("program_id") == PROGRAM_ID, contract.get("program_id"), PROGRAM_ID)
    check("STATUS", contract.get("status") == "CONTRACT_CANDIDATE", contract.get("status"), "CONTRACT_CANDIDATE")
    check("TRADE_AUTHORITY", contract.get("trade_authority") == "NONE", contract.get("trade_authority"), "NONE")

    entry = contract.get("entry_gate", {})
    pointer_path = repo_root / str(entry.get("pointer_path", ""))
    check("ENTRY_POINTER_EXISTS", pointer_path.is_file(), str(pointer_path), "existing file")
    if pointer_path.is_file():
        pointer = load_json(pointer_path)
        check("ENTRY_RELEASE", pointer.get("release_id") == entry.get("required_release_id"), pointer.get("release_id"), entry.get("required_release_id"))
        check("ENTRY_STATUS", pointer.get("status") == entry.get("required_status"), pointer.get("status"), entry.get("required_status"))
        check("ENTRY_GATE", pointer.get("next_gate") == entry.get("required_next_gate"), pointer.get("next_gate"), entry.get("required_next_gate"))
        check("ENTRY_AUTHORITY", pointer.get("trade_authority") == "NONE", pointer.get("trade_authority"), "NONE")

    scope = contract.get("scope", {})
    check("SCOPE_MODE", scope.get("mode") == "CONTRACT_AND_IDENTITY_ONLY", scope.get("mode"), "CONTRACT_AND_IDENTITY_ONLY")
    check("RESERVED_BENCHMARK_TARGET", scope.get("benchmark_security_target_reserved_for_fmdl6c") == 24, scope.get("benchmark_security_target_reserved_for_fmdl6c"), 24)
    for key in (
        "live_security_master_build_authorized",
        "source_access_benchmark_authorized",
        "market_history_build_authorized",
        "financial_fact_build_authorized",
        "candidate_pool_integration_authorized",
        "simulation_integration_authorized",
        "real_account_integration_authorized",
        "order_generation_authorized",
    ):
        check(f"AUTHORIZATION_FALSE:{key}", scope.get(key) is False, scope.get(key), False)

    market = contract.get("market_contract", {})
    check("PILOT_VENUES", market.get("current_pilot_venues") == ["XNYS", "XNAS", "XASE"], market.get("current_pilot_venues"), ["XNYS", "XNAS", "XASE"])
    for key in ("benchmark_pool_is_not_investable_universe", "effective_dating_required", "point_in_time_membership_required", "otc_fallback_membership_forbidden"):
        check(f"MARKET_BOUNDARY_TRUE:{key}", market.get(key) is True, market.get(key), True)

    boundary = contract.get("instrument_boundary", {})
    included = boundary.get("included", [])
    excluded = boundary.get("excluded", [])
    check("INCLUDED_TYPE_COUNT", len(included) == 4, len(included), 4)
    check("INCLUDED_TYPE_UNIQUE", len({row.get("instrument_type") for row in included}) == 4, len({row.get("instrument_type") for row in included}), 4)
    check("EXCLUDED_TYPE_MINIMUM", len(excluded) >= 10, len(excluded), ">=10")
    check("EXCLUDED_TYPE_UNIQUE", len(excluded) == len(set(excluded)), len(excluded) - len(set(excluded)), 0)
    check("UNKNOWN_QUARANTINE", boundary.get("unknown_instrument_policy") == "QUARANTINE_NOT_DEFAULT_INCLUDE", boundary.get("unknown_instrument_policy"), "QUARANTINE_NOT_DEFAULT_INCLUDE")

    identity = contract.get("identity_model", {})
    layers = identity.get("layers", [])
    check("IDENTITY_LAYER_COUNT", len(layers) == 4, len(layers), 4)
    check("IDENTITY_LAYER_SET", {row.get("layer") for row in layers} == {"ISSUER", "SHARE_CLASS", "SECURITY", "LISTING"}, sorted(row.get("layer") for row in layers), ["ISSUER", "LISTING", "SECURITY", "SHARE_CLASS"])
    check("TICKER_NOT_IDENTITY", identity.get("ticker_is_identity") is False, identity.get("ticker_is_identity"), False)
    check("EXCHANGE_NOT_IDENTITY", identity.get("exchange_is_identity") is False, identity.get("exchange_is_identity"), False)
    check("MULTI_SECURITY_ALLOWED", identity.get("one_issuer_may_have_multiple_securities") is True, identity.get("one_issuer_may_have_multiple_securities"), True)
    check("MULTI_LISTING_HISTORY_ALLOWED", identity.get("one_security_may_have_multiple_effective_dated_listings") is True, identity.get("one_security_may_have_multiple_effective_dated_listings"), True)
    refinement = identity.get("controlled_refinement_of_fmdl6_0", {})
    check("FMDL6_0_RELEASE_PRESERVED", refinement.get("historical_release_mutation_authorized") is False, refinement.get("historical_release_mutation_authorized"), False)
    check("PROVISIONAL_PATTERN_RECLASSIFIED", refinement.get("fmdl6a_interpretation") == "EFFECTIVE_DATED_LISTING_LOCATOR_NOT_IMMUTABLE_SECURITY_ID", refinement.get("fmdl6a_interpretation"), "EFFECTIVE_DATED_LISTING_LOCATOR_NOT_IMMUTABLE_SECURITY_ID")

    lifecycle = contract.get("lifecycle_rules", [])
    check("LIFECYCLE_RULE_COUNT", len(lifecycle) == 10, len(lifecycle), 10)
    check("LIFECYCLE_EVENT_UNIQUE", len({row.get("event_type") for row in lifecycle}) == 10, len({row.get("event_type") for row in lifecycle}), 10)
    for required_event in ("TICKER_CHANGE", "EXCHANGE_TRANSFER", "MERGER_OR_ACQUISITION", "SPINOFF", "DELISTING_TO_OTC"):
        check(f"LIFECYCLE_REQUIRED:{required_event}", required_event in {row.get("event_type") for row in lifecycle}, required_event in {row.get("event_type") for row in lifecycle}, True)

    fixtures = contract.get("identity_case_fixtures", [])
    case_ids = [row.get("case_id") for row in fixtures]
    check("FIXTURE_COUNT", len(fixtures) == 12, len(fixtures), 12)
    check("FIXTURE_IDS_UNIQUE", len(case_ids) == len(set(case_ids)), len(case_ids) - len(set(case_ids)), 0)
    for required_case in ("CASE_MULTIPLE_SHARE_CLASSES", "CASE_ADR_WITH_UNDERLYING", "CASE_TICKER_CHANGE", "CASE_DELISTING_TO_OTC", "CASE_UNKNOWN_INSTRUMENT"):
        check(f"FIXTURE_REQUIRED:{required_case}", required_case in case_ids, required_case in case_ids, True)

    fields = contract.get("required_record_fields", {})
    for record_type in ("issuer", "share_class", "security", "listing", "identity_event"):
        check(f"RECORD_FIELDS:{record_type}", isinstance(fields.get(record_type), list) and len(fields[record_type]) >= 7, len(fields.get(record_type, [])), ">=7")

    fallback = contract.get("source_authority_and_conflict_policy", {})
    check("FALLBACK_NOT_DECISION_GRADE", fallback.get("fallback_may_create_decision_grade_identity") is False, fallback.get("fallback_may_create_decision_grade_identity"), False)
    check("CONFLICT_QUARANTINE", "QUARANTINE_UNRESOLVED_CONFLICT" in fallback.get("conflict_resolution", []), fallback.get("conflict_resolution"), "contains QUARANTINE_UNRESOLVED_CONFLICT")

    gates = contract.get("acceptance_gates", {})
    check("ZERO_CANDIDATE_MUTATION", gates.get("candidate_pool_mutation_count") == 0, gates.get("candidate_pool_mutation_count"), 0)
    check("ZERO_SIMULATION_MUTATION", gates.get("simulation_mutation_count") == 0, gates.get("simulation_mutation_count"), 0)
    check("ZERO_REAL_ACCOUNT_MUTATION", gates.get("real_account_mutation_count") == 0, gates.get("real_account_mutation_count"), 0)
    check("ZERO_ORDERS", gates.get("order_generation_count") == 0, gates.get("order_generation_count"), 0)
    check("GATE_TRADE_AUTHORITY", gates.get("trade_authority") == "NONE", gates.get("trade_authority"), "NONE")
    check("RELEASE_SEQUENCE", contract.get("publication", {}).get("release_sequence") == 20, contract.get("publication", {}).get("release_sequence"), 20)
    check("EXIT_STATUS", contract.get("exit_status") == "FMDL6A_US_MARKET_CONTRACT_AND_SECURITY_IDENTITY_ACCEPTED", contract.get("exit_status"), "FMDL6A_US_MARKET_CONTRACT_AND_SECURITY_IDENTITY_ACCEPTED")
    check("NEXT_GATE", contract.get("next_gate") == "FMDL-6B_SOURCE_INTERFACE_AND_ACCESS_BENCHMARK", contract.get("next_gate"), "FMDL-6B_SOURCE_INTERFACE_AND_ACCESS_BENCHMARK")
    return checks, errors


def canonical_payload(contract: dict[str, Any], contract_sha: str) -> dict[str, Any]:
    return {
        "program_id": PROGRAM_ID,
        "contract_sha256": contract_sha,
        "entry_release_id": contract["entry_gate"]["required_release_id"],
        "market_id": contract["market_contract"]["market_id"],
        "pilot_venues": contract["market_contract"]["current_pilot_venues"],
        "included_instrument_types": [row["instrument_type"] for row in contract["instrument_boundary"]["included"]],
        "excluded_instrument_types": contract["instrument_boundary"]["excluded"],
        "identity_layers": contract["identity_model"]["layers"],
        "lifecycle_rules": contract["lifecycle_rules"],
        "identity_case_fixtures": contract["identity_case_fixtures"],
        "next_gate": contract["next_gate"],
        "trade_authority": "NONE",
    }


def build_candidate(repo_root: Path, contract_path: Path, candidate_root: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    checks, errors = validate_contract(repo_root, contract_path)
    if errors:
        raise ValueError(f"contract validation failed: {errors}")
    if candidate_root.exists():
        shutil.rmtree(candidate_root)
    candidate_root.mkdir(parents=True, exist_ok=True)

    contract_sha = sha256_file(contract_path)
    canonical_sha = sha256_bytes(stable_json(canonical_payload(contract, contract_sha)).encode("utf-8"))
    release_id = f"FMDL6A_{contract['as_of_date'].replace('-', '')}_{canonical_sha[:12]}"

    decision = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "status": contract["exit_status"],
        "hard_failures": [],
        "canonical_sha256": canonical_sha,
        "contract_sha256": contract_sha,
        "identity_layer_count": len(contract["identity_model"]["layers"]),
        "included_instrument_type_count": len(contract["instrument_boundary"]["included"]),
        "excluded_instrument_type_count": len(contract["instrument_boundary"]["excluded"]),
        "lifecycle_rule_count": len(contract["lifecycle_rules"]),
        "identity_case_fixture_count": len(contract["identity_case_fixtures"]),
        "duplicate_case_id_count": 0,
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "next_gate": contract["next_gate"],
        "trade_authority": "NONE",
    }
    validation = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "canonical_sha256": canonical_sha,
        "validation": "PASS",
        "check_count": len(checks),
        "pass_count": len(checks),
        "error_count": 0,
        "errors": [],
        "trade_authority": "NONE",
    }
    release = {
        "program_id": PROGRAM_ID,
        "program_name": contract["program_name"],
        "release_id": release_id,
        "release_sequence": contract["publication"]["release_sequence"],
        "as_of_date": contract["as_of_date"],
        "status": contract["exit_status"],
        "authority": contract["authority"],
        "canonical_sha256": canonical_sha,
        "contract_sha256": contract_sha,
        "scope_mode": contract["scope"]["mode"],
        "market_id": contract["market_contract"]["market_id"],
        "pilot_venues": contract["market_contract"]["current_pilot_venues"],
        "identity_layer_count": 4,
        "identity_case_fixture_count": 12,
        "live_security_master_build_authorized": False,
        "source_access_benchmark_authorized": False,
        "candidate_pool_integration_authorized": False,
        "simulation_integration_authorized": False,
        "real_account_integration_authorized": False,
        "order_generation_authorized": False,
        "next_gate": contract["next_gate"],
        "trade_authority": "NONE",
    }
    market_contract = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        **contract["market_contract"],
        "instrument_boundary": contract["instrument_boundary"],
        "trade_authority": "NONE",
    }
    identity_contract = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        **contract["identity_model"],
        "source_authority_and_conflict_policy": contract["source_authority_and_conflict_policy"],
        "required_record_fields": contract["required_record_fields"],
        "trade_authority": "NONE",
    }

    write_json(candidate_root / "FMDL6A_RELEASE.json", release)
    write_json(candidate_root / "FMDL6A_DECISION.json", decision)
    write_json(candidate_root / "FMDL6A_VALIDATION.json", validation)
    write_json(candidate_root / "FMDL6A_MARKET_CONTRACT.json", market_contract)
    write_json(candidate_root / "FMDL6A_SECURITY_IDENTITY_CONTRACT.json", identity_contract)

    included_rows = [{"boundary": "INCLUDED", "instrument_type": row["instrument_type"], "pilot_role": row["pilot_role"], "rule": "|".join(row["conditions"])} for row in contract["instrument_boundary"]["included"]]
    excluded_rows = [{"boundary": "EXCLUDED", "instrument_type": value, "pilot_role": "NOT_IN_PILOT", "rule": "EXPLICIT_EXCLUSION"} for value in contract["instrument_boundary"]["excluded"]]
    write_csv(candidate_root / "FMDL6A_INSTRUMENT_BOUNDARY.csv", ["boundary", "instrument_type", "pilot_role", "rule"], included_rows + excluded_rows)
    write_csv(candidate_root / "FMDL6A_LIFECYCLE_RULES.csv", ["event_type", "issuer_id_action", "share_class_id_action", "security_id_action", "listing_id_action", "required_link", "pilot_membership_action"], contract["lifecycle_rules"])
    write_csv(candidate_root / "FMDL6A_IDENTITY_CASE_MATRIX.csv", ["case_id", "case_type", "expected_identity_result"], contract["identity_case_fixtures"])

    files: dict[str, dict[str, Any]] = {}
    for path in sorted(candidate_root.iterdir()):
        if path.is_file() and path.name != "FMDL6A_MANIFEST.json":
            files[path.name] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
    write_json(candidate_root / "FMDL6A_MANIFEST.json", {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": release["release_sequence"],
        "canonical_sha256": canonical_sha,
        "contract_sha256": contract_sha,
        "files": files,
        "trade_authority": "NONE",
    })
    return release


def publish(repo_root: Path, candidate_root: Path, release: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    release_id = release["release_id"]
    targets = [
        repo_root / contract["publication"]["current_root"],
        repo_root / contract["publication"]["release_root"] / release_id,
        repo_root / contract["publication"]["archive_root"] / release_id,
    ]
    for target in targets:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(candidate_root, target)
    last_success = {
        "program_id": PROGRAM_ID,
        "release_id": release_id,
        "release_sequence": release["release_sequence"],
        "status": release["status"],
        "canonical_sha256": release["canonical_sha256"],
        "contract_sha256": release["contract_sha256"],
        "current_path": contract["publication"]["current_root"],
        "immutable_path": f"{contract['publication']['release_root']}/{release_id}",
        "archive_path": f"{contract['publication']['archive_root']}/{release_id}",
        "identity_contract_path": f"{contract['publication']['current_root']}/FMDL6A_SECURITY_IDENTITY_CONTRACT.json",
        "market_contract_path": f"{contract['publication']['current_root']}/FMDL6A_MARKET_CONTRACT.json",
        "next_gate": release["next_gate"],
        "trade_authority": "NONE",
    }
    write_json(repo_root / contract["publication"]["last_success"], last_success)
    return last_success


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--contract", default="config/fmdl6a_us_market_security_identity_contract.json")
    parser.add_argument("--candidate", default="outputs/fmdl6a/candidate")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    contract_path = repo_root / args.contract
    candidate_root = repo_root / args.candidate
    release = build_candidate(repo_root, contract_path, candidate_root)
    result: dict[str, Any] = release
    if args.publish:
        result = publish(repo_root, candidate_root, release, load_json(contract_path))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0
