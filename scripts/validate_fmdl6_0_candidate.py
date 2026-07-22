#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from publish_fmdl6_0_plan import build_candidate, canonical_payload, load_json, sha256_bytes, sha256_file, stable_json

PROGRAM_ID = "FMDL-6-0"
REQUIRED_FILES = {
    "FMDL6_0_RELEASE.json",
    "FMDL6_0_DECISION.json",
    "FMDL6_0_VALIDATION.json",
    "FMDL6_0_PLAN.json",
    "FMDL6_0_MANIFEST.json",
    "FMDL6_START_HERE.md",
    "FMDL6_ACTIVATION_GATE.json",
    "FMDL6_DEFERRED_BACKLOG.json",
    "FMDL6_SOURCE_INTERFACE_PLAN.json",
}


def compare_directories(left: Path, right: Path) -> list[str]:
    errors: list[str] = []
    left_files = {path.name for path in left.iterdir() if path.is_file()}
    right_files = {path.name for path in right.iterdir() if path.is_file()}
    if left_files != right_files:
        errors.append("REPLAY_FILE_SET_MISMATCH")
        return errors
    for name in sorted(left_files):
        if sha256_file(left / name) != sha256_file(right / name):
            errors.append(f"REPLAY_HASH_MISMATCH:{name}")
    return errors


def validate(repo_root: Path, candidate: Path) -> dict[str, Any]:
    errors: list[str] = []
    found = {path.name for path in candidate.iterdir() if path.is_file()}
    if found != REQUIRED_FILES:
        errors.append(f"FILE_SET_MISMATCH:{sorted(found)}")

    release = load_json(candidate / "FMDL6_0_RELEASE.json")
    decision = load_json(candidate / "FMDL6_0_DECISION.json")
    validation = load_json(candidate / "FMDL6_0_VALIDATION.json")
    plan = load_json(candidate / "FMDL6_0_PLAN.json")
    manifest = load_json(candidate / "FMDL6_0_MANIFEST.json")
    activation = load_json(candidate / "FMDL6_ACTIVATION_GATE.json")
    deferred = load_json(candidate / "FMDL6_DEFERRED_BACKLOG.json")
    source_plan = load_json(candidate / "FMDL6_SOURCE_INTERFACE_PLAN.json")

    if release.get("program_id") != PROGRAM_ID:
        errors.append("PROGRAM_ID_MISMATCH")
    if release.get("status") != "FMDL6_0_US_EQUITY_RESUME_READY_PILOT_ARCHITECTURE_ACCEPTED":
        errors.append("RELEASE_STATUS_MISMATCH")
    if release.get("scope_mode") != "INTERFACE_AND_SMALL_BENCHMARK_ONLY":
        errors.append("SCOPE_MODE_MISMATCH")
    if release.get("benchmark_security_target") != 24:
        errors.append("BENCHMARK_TARGET_MISMATCH")
    if release.get("next_gate") != "FMDL-6A_US_MARKET_CONTRACT_AND_SECURITY_IDENTITY":
        errors.append("NEXT_GATE_MISMATCH")
    if release.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY_ERROR")

    for key in (
        "full_universe_development_authorized",
        "candidate_pool_integration_authorized",
        "simulation_integration_authorized",
        "real_account_integration_authorized",
        "order_generation_authorized",
    ):
        if release.get(key) is not False:
            errors.append(f"UNAUTHORIZED_RELEASE_FLAG:{key}")

    if decision.get("hard_failures"):
        errors.append("DECISION_HAS_HARD_FAILURES")
    if validation.get("validation") != "PASS" or validation.get("error_count") != 0:
        errors.append("VALIDATION_NOT_PASS")
    if activation.get("gate_status") != "CLOSED":
        errors.append("ACTIVATION_GATE_NOT_CLOSED")
    if activation.get("full_universe_development_authorized") is not False:
        errors.append("ACTIVATION_FULL_BUILD_AUTHORIZED")
    if deferred.get("status") != "DEFERRED_FULL_BUILD_NOT_AUTHORIZED" or len(deferred.get("items", [])) != 4:
        errors.append("DEFERRED_BACKLOG_INVALID")
    if source_plan.get("decision_grade_claimed_in_fmdl6_0") is not False:
        errors.append("PREMATURE_DECISION_GRADE_SOURCE_CLAIM")
    if len(source_plan.get("interfaces", [])) != 4:
        errors.append("SOURCE_INTERFACE_COUNT_MISMATCH")

    payload = canonical_payload(plan, decision, {
        "validation": validation.get("validation"),
    })
    expected_canonical = sha256_bytes(stable_json(payload).encode("utf-8"))
    if release.get("canonical_sha256") != expected_canonical:
        errors.append("CANONICAL_SHA_MISMATCH")
    if manifest.get("canonical_sha256") != release.get("canonical_sha256"):
        errors.append("MANIFEST_CANONICAL_SHA_MISMATCH")
    if manifest.get("release_id") != release.get("release_id"):
        errors.append("MANIFEST_RELEASE_ID_MISMATCH")

    manifest_files = manifest.get("files", {})
    expected_manifest_names = REQUIRED_FILES - {"FMDL6_0_MANIFEST.json"}
    if set(manifest_files) != expected_manifest_names:
        errors.append("MANIFEST_FILE_SET_MISMATCH")
    for name in sorted(expected_manifest_names):
        path = candidate / name
        row = manifest_files.get(name, {})
        if row.get("sha256") != sha256_file(path):
            errors.append(f"MANIFEST_HASH_MISMATCH:{name}")
        if row.get("size_bytes") != path.stat().st_size:
            errors.append(f"MANIFEST_SIZE_MISMATCH:{name}")

    with tempfile.TemporaryDirectory(prefix="fmdl6_0_replay_") as temp:
        replay = Path(temp) / "candidate"
        build_candidate(repo_root, replay, plan, decision, {
            "validation": validation["validation"],
            "check_count": validation["check_count"],
            "pass_count": validation["pass_count"],
            "error_count": validation["error_count"],
            "errors": validation["errors"],
        })
        errors.extend(compare_directories(candidate, replay))

    return {
        "program_id": PROGRAM_ID,
        "release_id": release.get("release_id"),
        "canonical_sha256": release.get("canonical_sha256"),
        "validation": "PASS" if not errors else "FAIL",
        "same_input_replay": "PASS" if not any(error.startswith("REPLAY_") for error in errors) else "FAIL",
        "error_count": len(errors),
        "errors": errors,
        "trade_authority": "NONE",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--candidate", default="outputs/fmdl6_0/candidate")
    parser.add_argument("--output", default="outputs/fmdl6_0/candidate/FMDL6_0_INDEPENDENT_ACCEPTANCE.json")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    result = validate(repo_root, repo_root / args.candidate)
    output = repo_root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["validation"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
