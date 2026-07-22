from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from fmdl5_final_core import build_candidate, load_json, read_csv, sha256_file, write_json

EXPECTED_STATUS = "FMDL5_HONG_KONG_STOCK_CONNECT_OPERATIONAL_ACCEPTANCE_ACCEPTED"


def validate(repo_root: Path, candidate: Path) -> dict:
    errors: list[str] = []
    decision = load_json(candidate / "FMDL5_FINAL_DECISION.json")
    quality = load_json(candidate / "FMDL5_FINAL_QUALITY_REPORT.json")
    release = load_json(candidate / "FMDL5_FINAL_RELEASE.json")
    manifest = load_json(candidate / "FMDL5_FINAL_MANIFEST.json")

    if decision.get("status") != EXPECTED_STATUS:
        errors.append("DECISION_STATUS_MISMATCH")
    if quality.get("validation") != "PASS" or quality.get("hard_failures"):
        errors.append("QUALITY_NOT_PASS")
    identities = {
        decision.get("release_id"), quality.get("release_id"), release.get("release_id"), manifest.get("release_id")
    }
    if len(identities) != 1:
        errors.append("RELEASE_ID_IDENTITY_MISMATCH")
    canonical = {
        decision.get("canonical_sha256"), quality.get("canonical_sha256"), release.get("canonical_sha256"), manifest.get("canonical_sha256")
    }
    if len(canonical) != 1:
        errors.append("CANONICAL_SHA_IDENTITY_MISMATCH")
    for name, meta in manifest.get("files", {}).items():
        path = candidate / name
        if not path.exists():
            errors.append(f"MANIFEST_FILE_MISSING:{name}")
            continue
        if sha256_file(path) != meta.get("sha256"):
            errors.append(f"MANIFEST_HASH_MISMATCH:{name}")
        if path.stat().st_size != int(meta.get("size_bytes", -1)):
            errors.append(f"MANIFEST_SIZE_MISMATCH:{name}")

    lineage = read_csv(candidate / "FMDL5_FINAL_END_TO_END_LINEAGE.csv")
    if len(lineage) != 6:
        errors.append("LINEAGE_ROW_COUNT_MISMATCH")
    if any(row.get("lineage_status") != "PASS" for row in lineage):
        errors.append("LINEAGE_STATUS_FAILURE")
    if len({row.get("security_id") for row in lineage}) != len(lineage):
        errors.append("DUPLICATE_LINEAGE_SECURITY")
    if any(row.get("trade_authority") != "NONE" for row in lineage):
        errors.append("LINEAGE_TRADE_AUTHORITY_ERROR")

    capability = read_csv(candidate / "FMDL5_FINAL_CAPABILITY_MATRIX.csv")
    required_capabilities = {
        "A_SHARE_FULL_MARKET_DATA",
        "A_SHARE_SCREENING_AND_RESEARCH",
        "HONG_KONG_STOCK_CONNECT_UNIVERSE",
        "HONG_KONG_FACTOR_AND_SCREENING",
        "HONG_KONG_PUBLIC_EQUITY_RESEARCH",
        "CROSS_MARKET_A_H_DUPLICATION_CONTROL",
        "INVESTMENT_OS_STATE_ROUTING"
    }
    if not required_capabilities.issubset({row.get("capability") for row in capability}):
        errors.append("CAPABILITY_MATRIX_INCOMPLETE")

    failure = load_json(candidate / "FMDL5_FINAL_FAILURE_INJECTION.json")
    if len(failure.get("tests", [])) != 5 or not failure.get("all_rejected"):
        errors.append("FAILURE_INJECTION_NOT_PASS")
    us_plan = load_json(candidate / "FMDL6_US_INTERFACE_BENCHMARK_PLAN.json")
    if us_plan.get("scope_mode") != "INTERFACE_AND_SMALL_BENCHMARK_ONLY":
        errors.append("US_PILOT_SCOPE_NOT_BOUNDED")
    if us_plan.get("full_universe_development_authorized") is not False:
        errors.append("US_FULL_UNIVERSE_WRONGLY_AUTHORIZED")
    if int(us_plan.get("benchmark_security_target", 0)) != 24:
        errors.append("US_BENCHMARK_TARGET_MISMATCH")

    metrics = decision.get("metrics", {})
    zero_fields = [
        "candidate_pool_mutation_count", "simulation_mutation_count",
        "real_account_mutation_count", "order_generation_count", "trade_authority_error_count"
    ]
    if any(int(metrics.get(field, -1)) != 0 for field in zero_fields):
        errors.append("STATE_OR_AUTHORITY_MUTATION_DETECTED")

    with tempfile.TemporaryDirectory(prefix="fmdl5-final-replay-") as temp_dir:
        replay_dir = Path(temp_dir) / "candidate"
        replay = build_candidate(repo_root, replay_dir)
        if replay.get("release_id") != decision.get("release_id"):
            errors.append("SAME_INPUT_RELEASE_ID_MISMATCH")
        if replay.get("canonical_sha256") != decision.get("canonical_sha256"):
            errors.append("SAME_INPUT_CANONICAL_SHA_MISMATCH")

    validation = {
        "program_id": "FMDL-5-FINAL",
        "release_id": decision.get("release_id"),
        "canonical_sha256": decision.get("canonical_sha256"),
        "error_count": len(errors),
        "errors": errors,
        "lineage_count": len(lineage),
        "capability_count": len(capability),
        "same_input_replay": "PASS" if not any(error.startswith("SAME_INPUT") for error in errors) else "FAIL",
        "validation": "PASS" if not errors else "FAIL",
        "trade_authority": "NONE"
    }
    write_json(candidate / "FMDL5_FINAL_VALIDATION.json", validation)
    manifest = load_json(candidate / "FMDL5_FINAL_MANIFEST.json")
    validation_path = candidate / "FMDL5_FINAL_VALIDATION.json"
    manifest.setdefault("files", {})[validation_path.name] = {
        "sha256": sha256_file(validation_path),
        "size_bytes": validation_path.stat().st_size
    }
    write_json(candidate / "FMDL5_FINAL_MANIFEST.json", manifest)
    if errors:
        raise ValueError(";".join(errors))
    return validation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--candidate", default="outputs/fmdl5/final/candidate")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    candidate = (repo_root / args.candidate).resolve()
    result = validate(repo_root, candidate)
    print(result["validation"])


if __name__ == "__main__":
    main()
