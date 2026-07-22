#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from fmdl6a_builder import build_candidate, load_json, sha256_file

PROGRAM_ID = "FMDL-6A"
REQUIRED_FILES = {
    "FMDL6A_RELEASE.json",
    "FMDL6A_DECISION.json",
    "FMDL6A_VALIDATION.json",
    "FMDL6A_MARKET_CONTRACT.json",
    "FMDL6A_SECURITY_IDENTITY_CONTRACT.json",
    "FMDL6A_INSTRUMENT_BOUNDARY.csv",
    "FMDL6A_LIFECYCLE_RULES.csv",
    "FMDL6A_IDENTITY_CASE_MATRIX.csv",
    "FMDL6A_MANIFEST.json",
}


def directory_hashes(path: Path) -> dict[str, str]:
    return {item.name: sha256_file(item) for item in path.iterdir() if item.is_file()}


def validate(repo_root: Path, contract_path: Path, candidate_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    found = {item.name for item in candidate_root.iterdir() if item.is_file()}
    if found != REQUIRED_FILES:
        errors.append("FILE_SET_MISMATCH")

    release = load_json(candidate_root / "FMDL6A_RELEASE.json")
    decision = load_json(candidate_root / "FMDL6A_DECISION.json")
    validation = load_json(candidate_root / "FMDL6A_VALIDATION.json")
    market = load_json(candidate_root / "FMDL6A_MARKET_CONTRACT.json")
    identity = load_json(candidate_root / "FMDL6A_SECURITY_IDENTITY_CONTRACT.json")
    manifest = load_json(candidate_root / "FMDL6A_MANIFEST.json")

    if release.get("program_id") != PROGRAM_ID:
        errors.append("PROGRAM_ID_MISMATCH")
    if release.get("status") != "FMDL6A_US_MARKET_CONTRACT_AND_SECURITY_IDENTITY_ACCEPTED":
        errors.append("STATUS_MISMATCH")
    if release.get("scope_mode") != "CONTRACT_AND_IDENTITY_ONLY":
        errors.append("SCOPE_MISMATCH")
    if release.get("next_gate") != "FMDL-6B_SOURCE_INTERFACE_AND_ACCESS_BENCHMARK":
        errors.append("NEXT_GATE_MISMATCH")
    if release.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY_ERROR")
    for key in (
        "live_security_master_build_authorized",
        "source_access_benchmark_authorized",
        "candidate_pool_integration_authorized",
        "simulation_integration_authorized",
        "real_account_integration_authorized",
        "order_generation_authorized",
    ):
        if release.get(key) is not False:
            errors.append(f"UNAUTHORIZED_FLAG:{key}")

    if decision.get("hard_failures"):
        errors.append("DECISION_HAS_FAILURES")
    for key in ("candidate_pool_mutation_count", "simulation_mutation_count", "real_account_mutation_count", "order_generation_count", "duplicate_case_id_count"):
        if decision.get(key) != 0:
            errors.append(f"NONZERO_DECISION_METRIC:{key}")
    if validation.get("validation") != "PASS" or validation.get("error_count") != 0:
        errors.append("VALIDATION_NOT_PASS")

    if market.get("benchmark_pool_is_not_investable_universe") is not True:
        errors.append("BENCHMARK_AUTHORITY_ERROR")
    if market.get("otc_fallback_membership_forbidden") is not True:
        errors.append("OTC_FALLBACK_ERROR")
    if len(market.get("instrument_boundary", {}).get("included", [])) != 4:
        errors.append("INCLUDED_TYPE_COUNT")
    if len(identity.get("layers", [])) != 4:
        errors.append("IDENTITY_LAYER_COUNT")
    if identity.get("ticker_is_identity") is not False or identity.get("exchange_is_identity") is not False:
        errors.append("MUTABLE_LISTING_KEY_USED_AS_IDENTITY")
    if identity.get("controlled_refinement_of_fmdl6_0", {}).get("historical_release_mutation_authorized") is not False:
        errors.append("FMDL6_0_MUTATION_AUTHORIZED")

    if manifest.get("release_id") != release.get("release_id"):
        errors.append("MANIFEST_RELEASE_MISMATCH")
    if manifest.get("canonical_sha256") != release.get("canonical_sha256"):
        errors.append("MANIFEST_CANONICAL_MISMATCH")
    expected_manifest = REQUIRED_FILES - {"FMDL6A_MANIFEST.json"}
    if set(manifest.get("files", {})) != expected_manifest:
        errors.append("MANIFEST_FILE_SET_MISMATCH")
    for name in sorted(expected_manifest):
        row = manifest.get("files", {}).get(name, {})
        path = candidate_root / name
        if row.get("sha256") != sha256_file(path):
            errors.append(f"MANIFEST_HASH_MISMATCH:{name}")
        if row.get("size_bytes") != path.stat().st_size:
            errors.append(f"MANIFEST_SIZE_MISMATCH:{name}")

    replay_status = "PASS"
    with tempfile.TemporaryDirectory(prefix="fmdl6a_replay_") as tmp:
        replay_root = Path(tmp) / "candidate"
        build_candidate(repo_root, contract_path, replay_root)
        if directory_hashes(candidate_root) != directory_hashes(replay_root):
            replay_status = "FAIL"
            errors.append("SAME_INPUT_REPLAY_MISMATCH")

    return {
        "program_id": PROGRAM_ID,
        "release_id": release.get("release_id"),
        "canonical_sha256": release.get("canonical_sha256"),
        "validation": "PASS" if not errors else "FAIL",
        "same_input_replay": replay_status,
        "error_count": len(errors),
        "errors": errors,
        "trade_authority": "NONE",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--contract", default="config/fmdl6a_us_market_security_identity_contract.json")
    parser.add_argument("--candidate", default="outputs/fmdl6a/candidate")
    parser.add_argument("--output", default="outputs/fmdl6a/acceptance/FMDL6A_INDEPENDENT_ACCEPTANCE.json")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    result = validate(repo_root, repo_root / args.contract, repo_root / args.candidate)
    output = repo_root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["validation"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
