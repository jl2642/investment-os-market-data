from __future__ import annotations

import argparse
import csv
import json
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from fmdl5g_core import build_candidate, load_json, load_jsonl, sha256_file, sha256_object


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validate(repo_root: Path, candidate: Path) -> dict[str, Any]:
    contract = load_json(repo_root / "config/fmdl5g_investment_os_integration.json")
    decision = load_json(candidate / "FMDL5G_DECISION.json")
    quality = load_json(candidate / "FMDL5G_QUALITY_REPORT.json")
    manifest = load_json(candidate / "FMDL5G_MANIFEST.json")
    state_diff = load_json(candidate / "FMDL5G_STATE_DIFF.json")
    rollback = load_json(candidate / "FMDL5G_ROLLBACK_PROOF.json")
    transitions = load_jsonl(candidate / "FMDL5G_STATE_TRANSITIONS.jsonl")

    errors: list[str] = []
    if decision.get("status") != contract["exit_status"]:
        errors.append("DECISION_STATUS_MISMATCH")
    if decision.get("next_gate") != contract["next_gate"]:
        errors.append("NEXT_GATE_MISMATCH")
    if decision.get("trade_authority") != "NONE":
        errors.append("DECISION_TRADE_AUTHORITY_ERROR")
    if quality.get("hard_failures"):
        errors.append("QUALITY_HARD_FAILURES_PRESENT")
    if quality.get("validation_state") != "PASS":
        errors.append("QUALITY_NOT_PASS")
    if manifest.get("release_id") != decision.get("release_id"):
        errors.append("MANIFEST_RELEASE_ID_MISMATCH")
    if manifest.get("canonical_sha256") != decision.get("canonical_sha256"):
        errors.append("MANIFEST_CANONICAL_SHA_MISMATCH")

    schema = load_json(repo_root / "schemas/fmdl5g_state_transition_v1.schema.json")
    validator = Draft202012Validator(schema)
    for index, row in enumerate(transitions):
        schema_errors = sorted(validator.iter_errors(row), key=lambda item: list(item.path))
        if schema_errors:
            errors.append(f"TRANSITION_SCHEMA_ERROR_{index}_{schema_errors[0].message}")
        expected_hash = sha256_object({key: value for key, value in row.items() if key != "transition_sha256"})
        if row.get("transition_sha256") != expected_hash:
            errors.append(f"TRANSITION_HASH_MISMATCH_{index}")

    metrics = decision["metrics"]
    if len(transitions) != contract["transition_policy"]["required_transition_count"]:
        errors.append("TRANSITION_COUNT_MISMATCH")
    if len({row["security_id"] for row in transitions}) != len(transitions):
        errors.append("DUPLICATE_TRANSITION_SECURITY")
    if sum(row["target_route"] == "HK_CANDIDATE_REENTRY_REVIEW" for row in transitions) != contract["transition_policy"]["required_reentry_review_count"]:
        errors.append("REENTRY_COUNT_MISMATCH")
    if sum(row["target_route"] == "HK_SHADOW_TRACK_REVIEW" for row in transitions) != contract["transition_policy"]["required_shadow_track_count"]:
        errors.append("SHADOW_COUNT_MISMATCH")
    if sum(bool(row["cross_market_duplication_review_required"]) for row in transitions) < contract["acceptance"]["minimum_cross_market_duplication_review_count"]:
        errors.append("DUPLICATION_REVIEW_COUNT_BELOW_MINIMUM")

    for row in transitions:
        if any([
            row.get("candidate_pool_mutation_authorized"),
            row.get("simulation_mutation_authorized"),
            row.get("real_account_mutation_authorized"),
            row.get("order_generation_authorized"),
        ]):
            errors.append(f"UNAUTHORIZED_MUTATION_{row['security_id']}")
        if row.get("trade_authority") != "NONE":
            errors.append(f"TRADE_AUTHORITY_ERROR_{row['security_id']}")

    expected_zero_metrics = [
        "duplicate_transition_security_count",
        "missing_research_binding_count",
        "research_object_hash_mismatch_count",
        "existing_candidate_pool_mutation_count",
        "simulation_mutation_count",
        "real_account_mutation_count",
        "order_generation_count",
        "trade_authority_error_count",
    ]
    for name in expected_zero_metrics:
        if int(metrics.get(name, -1)) != 0:
            errors.append(f"NONZERO_METRIC_{name}")

    if state_diff.get("canonical_base_repack_count") != 0:
        errors.append("CANONICAL_BASE_REPACK_DETECTED")
    for name in ["existing_candidate_pool_mutation_count", "simulation_mutation_count", "real_account_mutation_count", "order_generation_count"]:
        if state_diff.get(name) != 0:
            errors.append(f"STATE_DIFF_NONZERO_{name}")
    if rollback.get("proof_state") != "PASS":
        errors.append("ROLLBACK_PROOF_NOT_PASS")
    if rollback.get("base_release_id_before") != rollback.get("base_release_id_after_candidate"):
        errors.append("ROLLBACK_BASE_RELEASE_CHANGED")
    if rollback.get("base_package_sha256_before") != rollback.get("base_package_sha256_after_candidate"):
        errors.append("ROLLBACK_BASE_PACKAGE_CHANGED")

    for name, metadata in manifest["files"].items():
        path = candidate / name
        if not path.exists():
            errors.append(f"MANIFEST_FILE_MISSING_{name}")
            continue
        if sha256_file(path) != metadata["sha256"]:
            errors.append(f"MANIFEST_HASH_MISMATCH_{name}")
        if path.stat().st_size != int(metadata["size_bytes"]):
            errors.append(f"MANIFEST_SIZE_MISMATCH_{name}")

    reentry = read_csv(candidate / "FMDL5G_HK_CANDIDATE_REENTRY_REVIEW_QUEUE.csv")
    shadow = read_csv(candidate / "FMDL5G_HK_SHADOW_TRACK_QUEUE.csv")
    duplicate_reviews = read_csv(candidate / "FMDL5G_CROSS_MARKET_DUPLICATION_REVIEW.csv")
    simulation = read_csv(candidate / "FMDL5G_SIMULATION_ROUTER.csv")
    real = read_csv(candidate / "FMDL5G_REAL_ACCOUNT_ROUTER.csv")
    if len(reentry) != 4 or len(shadow) != 2 or len(duplicate_reviews) < 2:
        errors.append("QUEUE_COUNTS_INVALID")
    if any(row.get("mutation_count") != "0" or row.get("router_decision") != "NOT_ADMITTED" for row in simulation + real):
        errors.append("DOWNSTREAM_ROUTER_MUTATION_OR_ADMISSION")

    with tempfile.TemporaryDirectory(prefix="fmdl5g-replay-") as tmp:
        replay_dir = Path(tmp) / "candidate"
        replay_decision = build_candidate(repo_root, replay_dir)
        if replay_decision["canonical_sha256"] != decision["canonical_sha256"]:
            errors.append("SAME_INPUT_CANONICAL_SHA_MISMATCH")
        replay_transitions = load_jsonl(replay_dir / "FMDL5G_STATE_TRANSITIONS.jsonl")
        if [row["transition_sha256"] for row in replay_transitions] != [row["transition_sha256"] for row in transitions]:
            errors.append("SAME_INPUT_TRANSITION_HASH_MISMATCH")

    result = {
        "program_id": "FMDL-5G",
        "release_id": decision.get("release_id"),
        "validation": "PASS" if not errors else "FAIL",
        "error_count": len(errors),
        "errors": errors,
        "state_transition_count": len(transitions),
        "candidate_reentry_review_count": len(reentry),
        "shadow_track_review_count": len(shadow),
        "cross_market_duplication_review_count": len(duplicate_reviews),
        "trade_authority": "NONE",
    }
    (candidate / "FMDL5G_INDEPENDENT_VALIDATION.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if errors:
        raise RuntimeError("FMDL-5G independent validation failed: " + ";".join(errors))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate FMDL-5G candidate")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--candidate", default="outputs/fmdl5g/integration/candidate")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    candidate = (repo_root / args.candidate).resolve() if not Path(args.candidate).is_absolute() else Path(args.candidate).resolve()
    result = validate(repo_root, candidate)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
