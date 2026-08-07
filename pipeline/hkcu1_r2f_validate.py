#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Iterable

ALLOWED_PR_PREFIXES = (
    ".github/workflows/hkcu-1-",
    "config/hkcu1_",
    "docs/HKCU",
    "outputs/hkcu1/",
    "pipeline/hkcu1_",
    "schemas/hkcu1_",
    "tests/test_hkcu1_",
)

R2E_FROZEN_PREFIXES = (
    ".github/workflows/hkcu-1-r2d-hkex-crosscheck.yml",
    ".github/workflows/hkcu-1-r2e-fmdl5e-universe.yml",
    ".github/workflows/hkcu-1-stock-connect-universe.yml",
    "config/hkcu1_hkex_crosscheck_contract.json",
    "config/hkcu1_lkg_snapshot.json",
    "config/hkcu1_r2c_bootstrap_contract.json",
    "config/hkcu1_r2e_universe_contract.json",
    "config/hkcu1_stock_connect_calendar_2026.json",
    "config/hkcu1_stock_connect_universe_contract.json",
    "pipeline/hkcu1_build_universe.py",
    "pipeline/hkcu1_discover_adjustment_notices_browser.py",
    "pipeline/hkcu1_discover_official_endpoints.py",
    "pipeline/hkcu1_fetch_adjustment_events.py",
    "pipeline/hkcu1_fetch_official_lists.py",
    "pipeline/hkcu1_fetch_sse_browser.py",
    "pipeline/hkcu1_hkex_crosscheck.py",
    "pipeline/hkcu1_probe_endpoint_contracts.py",
    "pipeline/hkcu1_r2e_merge_fmdl5e.py",
    "pipeline/hkcu1_r2e_prepare_bootstrap.py",
    "pipeline/hkcu1_r2e_r2c_gate.py",
    "pipeline/hkcu1_r2e_refresh_research_inputs.py",
    "pipeline/hkcu1_reconstruct_eligibility.py",
    "pipeline/hkcu1_resilience.py",
    "pipeline/hkcu1_resolve_effective_dates.py",
    "pipeline/hkcu1_validate_release.py",
    "schemas/hkcu1_stock_connect_eligibility.schema.json",
    "tests/test_hkcu1_build_universe.py",
    "tests/test_hkcu1_r2.py",
    "tests/test_hkcu1_r2c.py",
    "tests/test_hkcu1_r2d.py",
    "tests/test_hkcu1_r2e.py",
    "tests/test_hkcu1_r2e_bootstrap.py",
    "tests/test_hkcu1_r2e_r2c_gate.py",
    "tests/test_hkcu1_r2e_refresh_research_inputs.py",
)

REQUIRED_CURRENT_FILES = (
    "HKCU1_POINT_IN_TIME_ELIGIBILITY.csv",
    "HKCU1_R2E_INVESTABLE_UNIVERSE.csv",
    "HKCU1_R2E_EXCLUSIONS.csv",
    "HKCU1_R2E_QUALITY_REPORT.json",
    "HKCU1_R2E_DECISION.json",
    "HKCU1_R2E_MANIFEST.json",
)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _git_lines(repo_root: Path, *args: str) -> list[str]:
    proc = subprocess.run(
        ["git", *args], cwd=repo_root, check=True, capture_output=True, text=True
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def validate_changed_paths(paths: Iterable[str]) -> list[str]:
    errors: list[str] = []
    for path in paths:
        if not path.startswith(ALLOWED_PR_PREFIXES):
            errors.append(f"OUT_OF_SCOPE_PR_PATH:{path}")
    return errors


def validate_frozen_r2e_core(paths: Iterable[str]) -> list[str]:
    changed = set(paths)
    return [f"R2E_CORE_CHANGED_AFTER_ACCEPTED_RUN:{path}" for path in R2E_FROZEN_PREFIXES if path in changed]


def validate_acceptance(acceptance: dict, registry: dict, r2e_contract: dict) -> list[str]:
    errors: list[str] = []
    if acceptance.get("decision") != "PASS_CURRENT":
        errors.append("R2E_ACCEPTANCE_NOT_PASS_CURRENT")
    scope = acceptance.get("r2e_scope_boundary") or {}
    if scope.get("eligible_for_r2f") is not True:
        errors.append("R2E_NOT_ELIGIBLE_FOR_R2F")
    if scope.get("post_writeback_regression_passed") is not True:
        errors.append("R2E_POST_WRITEBACK_REGRESSION_NOT_PASS")
    if scope.get("main_or_canonical_published") is not False:
        errors.append("R2E_ALREADY_CLAIMS_CANONICAL_PUBLICATION")
    for key in ("candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"):
        if scope.get(key) != 0:
            errors.append(f"AUTHORITY_BOUNDARY_MUTATION:{key}:{scope.get(key)}")
    if scope.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY_NOT_NONE")

    latest_ci = acceptance.get("post_writeback_regression_ci") or {}
    if latest_ci.get("conclusion") != "success":
        errors.append("ACCEPTED_R2E_CI_NOT_SUCCESS")
    if not str(latest_ci.get("head_sha") or ""):
        errors.append("ACCEPTED_R2E_HEAD_SHA_MISSING")
    if not isinstance(latest_ci.get("run_id"), int):
        errors.append("ACCEPTED_R2E_RUN_ID_MISSING")
    if not isinstance(latest_ci.get("artifact_id"), int):
        errors.append("ACCEPTED_R2E_ARTIFACT_ID_MISSING")

    eligibility = acceptance.get("eligibility_evidence") or {}
    if eligibility.get("source_status") != "FRESH_OFFICIAL":
        errors.append("ACCEPTED_ELIGIBILITY_NOT_FRESH_OFFICIAL")
    if eligibility.get("buy_eligible_entity_rows", 0) <= 0:
        errors.append("ACCEPTED_BUY_ELIGIBLE_COUNT_INVALID")
    if eligibility.get("repeatability") != "IDENTICAL_ACROSS_RUN_18_AND_RUN_23":
        errors.append("ELIGIBILITY_REPEATABILITY_NOT_PROVEN")

    latest_research = acceptance.get("latest_research_input_refresh") or {}
    fmdl5c = latest_research.get("fmdl5c") or {}
    fmdl5e = latest_research.get("fmdl5e") or {}
    if fmdl5c.get("max_market_date") != fmdl5c.get("physical_max_market_date"):
        errors.append("FMDL5C_DECISION_PHYSICAL_DATE_MISMATCH")
    if fmdl5c.get("future_or_partial_session_rows_allowed") != 0:
        errors.append("FMDL5C_PARTIAL_SESSION_NOT_ZERO")
    max_age = int((r2e_contract.get("freshness") or {}).get("maximum_fmdl5e_age_stock_connect_service_days", 5))
    if int(fmdl5e.get("age_stock_connect_service_days", 10**9)) > max_age:
        errors.append("FMDL5E_TOO_STALE_FOR_R2F")
    for key in ("future_price_row_count", "future_financial_row_count", "future_action_row_count"):
        if fmdl5e.get(key) != 0:
            errors.append(f"FMDL5E_FUTURE_INFORMATION:{key}:{fmdl5e.get(key)}")

    zq = acceptance.get("zero_tolerance_quality") or {}
    for key in ("duplicate_security_count", "sell_only_in_investable_count", "unknown_in_investable_count", "future_information_count"):
        if zq.get(key) != 0:
            errors.append(f"ZERO_TOLERANCE_FAILURE:{key}:{zq.get(key)}")
    if zq.get("hard_failures") not in ([], None):
        errors.append("R2E_HARD_FAILURES_PRESENT")

    gate = registry.get("endpoint_resolution_gate") or {}
    if gate.get("status") not in {"R2B_PASS_R2C_PASS_R2D_PASS_R2E_PASS", "R2B_PASS_R2C_PASS_R2D_PASS_R2E_PASS_R2F_PASS"}:
        errors.append(f"REGISTRY_R2E_GATE_NOT_PASS:{gate.get('status')}")
    boundary = registry.get("authority_boundary") or {}
    for key in ("candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"):
        if boundary.get(key) != 0:
            errors.append(f"REGISTRY_AUTHORITY_BOUNDARY_MUTATION:{key}:{boundary.get(key)}")
    if boundary.get("trade_authority") != "NONE":
        errors.append("REGISTRY_TRADE_AUTHORITY_NOT_NONE")
    return errors


def validate_current_payload(current_dir: Path, acceptance: dict, r2e_contract: dict) -> tuple[list[str], dict]:
    errors: list[str] = []
    metrics: dict[str, object] = {}
    missing = [name for name in REQUIRED_CURRENT_FILES if not (current_dir / name).is_file()]
    if missing:
        return [f"CURRENT_REQUIRED_FILE_MISSING:{name}" for name in missing], metrics

    manifest = _json(current_dir / "HKCU1_R2E_MANIFEST.json")
    decision = _json(current_dir / "HKCU1_R2E_DECISION.json")
    quality = _json(current_dir / "HKCU1_R2E_QUALITY_REPORT.json")
    manifest_files = manifest.get("files") or {}
    for name in REQUIRED_CURRENT_FILES:
        if name == "HKCU1_R2E_MANIFEST.json":
            continue
        actual = _sha256(current_dir / name)
        if manifest_files.get(name) != actual:
            errors.append(f"CURRENT_MANIFEST_HASH_MISMATCH:{name}")

    accepted_hashes = acceptance.get("latest_release_manifest_hashes") or {}
    for name, expected in accepted_hashes.items():
        path = current_dir / name
        if not path.is_file():
            errors.append(f"ACCEPTED_CURRENT_FILE_MISSING:{name}")
        elif _sha256(path) != expected:
            errors.append(f"ACCEPTED_HASH_MISMATCH:{name}")
    if manifest.get("eligibility_source_status") != "FRESH_OFFICIAL":
        errors.append("CURRENT_MANIFEST_NOT_FRESH_OFFICIAL")
    if manifest.get("trade_authority") != "NONE":
        errors.append("CURRENT_MANIFEST_TRADE_AUTHORITY_NOT_NONE")

    if decision.get("status") != "PASS_CURRENT" or decision.get("publication_allowed") is not True:
        errors.append("CURRENT_DECISION_NOT_PASS_CURRENT")
    if decision.get("eligibility_source_status") != "FRESH_OFFICIAL" or decision.get("eligibility_source_fresh") is not True:
        errors.append("CURRENT_DECISION_NOT_FRESH_OFFICIAL")
    if decision.get("hard_failures") not in ([], None):
        errors.append("CURRENT_DECISION_HARD_FAILURES")
    for key in ("candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"):
        if decision.get(key) != 0:
            errors.append(f"CURRENT_DECISION_AUTHORITY_MUTATION:{key}:{decision.get(key)}")
    if decision.get("trade_authority") != "NONE":
        errors.append("CURRENT_DECISION_TRADE_AUTHORITY_NOT_NONE")

    for key in ("duplicate_security_count", "sell_only_in_investable_count", "unknown_in_investable_count", "future_information_count"):
        if quality.get(key) != 0:
            errors.append(f"CURRENT_ZERO_TOLERANCE_FAILURE:{key}:{quality.get(key)}")
    if quality.get("hard_failures") not in ([], None):
        errors.append("CURRENT_QUALITY_HARD_FAILURES")
    if quality.get("status") != "PASS":
        errors.append("CURRENT_QUALITY_STATUS_NOT_PASS")

    universe = _csv(current_dir / "HKCU1_R2E_INVESTABLE_UNIVERSE.csv")
    exclusions = _csv(current_dir / "HKCU1_R2E_EXCLUSIONS.csv")
    eligibility = _csv(current_dir / "HKCU1_POINT_IN_TIME_ELIGIBILITY.csv")
    metrics.update({"investable_count": len(universe), "excluded_count": len(exclusions), "eligibility_count": len(eligibility)})
    accepted_count = int((acceptance.get("latest_investable_universe") or {}).get("count", -1))
    if len(universe) != accepted_count:
        errors.append(f"CURRENT_INVESTABLE_COUNT_MISMATCH:{len(universe)}:{accepted_count}")
    if len(universe) != int(decision.get("provisional_investable_count", -1)):
        errors.append("CURRENT_DECISION_COUNT_MISMATCH")
    if len(universe) != int(quality.get("provisional_investable_count", -1)):
        errors.append("CURRENT_QUALITY_COUNT_MISMATCH")
    if len(exclusions) != int(quality.get("excluded_count", -1)):
        errors.append("CURRENT_EXCLUSION_COUNT_MISMATCH")
    if len(universe) + len(exclusions) != len(eligibility):
        errors.append("CURRENT_PARTITION_COUNT_MISMATCH")

    universe_codes = [row.get("security_code", "") for row in universe]
    exclusion_codes = [row.get("security_code", "") for row in exclusions]
    eligibility_codes = [row.get("security_code", "") for row in eligibility]
    if len(set(universe_codes)) != len(universe_codes):
        errors.append("CURRENT_UNIVERSE_DUPLICATE_SECURITY")
    if len(set(exclusion_codes)) != len(exclusion_codes):
        errors.append("CURRENT_EXCLUSIONS_DUPLICATE_SECURITY")
    if len(set(eligibility_codes)) != len(eligibility_codes):
        errors.append("CURRENT_ELIGIBILITY_DUPLICATE_SECURITY")
    if set(universe_codes) & set(exclusion_codes):
        errors.append("CURRENT_UNIVERSE_EXCLUSION_OVERLAP")
    if set(universe_codes) | set(exclusion_codes) != set(eligibility_codes):
        errors.append("CURRENT_PARTITION_MEMBERSHIP_MISMATCH")

    allowed_inv = set((r2e_contract.get("investable_gate") or {}).get("allowed_fmdl5e_investability_status", []))
    allowed_types = set((r2e_contract.get("investable_gate") or {}).get("allowed_security_types", []))
    if not allowed_inv:
        errors.append("R2E_CONTRACT_ALLOWED_INVESTABILITY_EMPTY")
    if not allowed_types:
        errors.append("R2E_CONTRACT_ALLOWED_SECURITY_TYPES_EMPTY")
    for row in universe:
        code = row.get("security_code", "")
        if not str(row.get("combined_status", "")).startswith("BUY_ELIGIBLE"):
            errors.append(f"CURRENT_NOT_BUY_ELIGIBLE:{code}")
        if not _truthy(row.get("buy_eligible")) or _truthy(row.get("sell_only")):
            errors.append(f"CURRENT_BUY_SELL_SEMANTICS_INVALID:{code}")
        if row.get("investability_status") not in allowed_inv:
            errors.append(f"CURRENT_FMDL5E_INVESTABILITY_INVALID:{code}")
        if row.get("security_type") not in allowed_types:
            errors.append(f"CURRENT_SECURITY_TYPE_INVALID:{code}")
        if not _truthy(row.get("financial_decision_grade")):
            errors.append(f"CURRENT_FINANCIAL_EVIDENCE_INVALID:{code}")
        if not _truthy(row.get("r2e_gate_pass")) or not _truthy(row.get("publication_eligible")):
            errors.append(f"CURRENT_R2E_GATE_INVALID:{code}")
        if row.get("trade_authority") != "NONE":
            errors.append(f"CURRENT_ROW_TRADE_AUTHORITY_NOT_NONE:{code}")
        if row.get("freshness_status") != "CURRENT":
            errors.append(f"CURRENT_ROW_FRESHNESS_NOT_CURRENT:{code}")
        if row.get("eligibility_source_status") != "FRESH_OFFICIAL":
            errors.append(f"CURRENT_ROW_ELIGIBILITY_SOURCE_NOT_FRESH:{code}")
    return errors, metrics


def validate(repo_root: Path, contract_path: Path, acceptance_path: Path, registry_path: Path, output_path: Path) -> dict:
    release_contract = _json(contract_path)
    acceptance = _json(acceptance_path)
    registry = _json(registry_path)
    source_r2e_contract = str(release_contract.get("source_r2e_contract") or "")
    if not source_r2e_contract:
        raise RuntimeError("R2F_SOURCE_R2E_CONTRACT_NOT_CONFIGURED")
    r2e_contract_path = repo_root / source_r2e_contract
    if not r2e_contract_path.is_file():
        raise RuntimeError(f"R2F_SOURCE_R2E_CONTRACT_MISSING:{source_r2e_contract}")
    r2e_contract = _json(r2e_contract_path)

    errors: list[str] = []
    errors.extend(validate_acceptance(acceptance, registry, r2e_contract))

    base_ref = str((release_contract.get("diff_policy") or {}).get("base_ref", "origin/main"))
    successful_head = str((acceptance.get("post_writeback_regression_ci") or {}).get("head_sha") or "")
    changed_paths = _git_lines(repo_root, "diff", "--name-only", f"{base_ref}...HEAD")
    errors.extend(validate_changed_paths(changed_paths))
    if successful_head:
        post_acceptance_paths = _git_lines(repo_root, "diff", "--name-only", f"{successful_head}..HEAD")
        errors.extend(validate_frozen_r2e_core(post_acceptance_paths))
    else:
        post_acceptance_paths = []
    subprocess.run(["git", "diff", "--check", f"{base_ref}...HEAD"], cwd=repo_root, check=True)

    current_dir = repo_root / str(release_contract.get("canonical_current_dir", "outputs/hkcu1/current"))
    stage = "CANDIDATE_CANONICAL" if current_dir.is_dir() else "PRE_PUBLISH_READY"
    current_metrics: dict[str, object] = {}
    if stage == "CANDIDATE_CANONICAL":
        current_errors, current_metrics = validate_current_payload(current_dir, acceptance, r2e_contract)
        errors.extend(current_errors)

    decision = {
        "program_id": "HKCU-1",
        "phase": "R2F",
        "stage": stage,
        "status": "PASS" if not errors else "BLOCKED",
        "ready_for_current_promotion": stage == "PRE_PUBLISH_READY" and not errors,
        "ready_for_pr_ready_and_merge": stage == "CANDIDATE_CANONICAL" and not errors,
        "base_ref": base_ref,
        "source_r2e_contract": source_r2e_contract,
        "accepted_r2e_head_sha": successful_head,
        "changed_file_count": len(changed_paths),
        "post_accepted_run_changed_file_count": len(post_acceptance_paths),
        "current_metrics": current_metrics,
        "errors": errors,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "trade_authority": "NONE",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return decision


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--acceptance", type=Path, required=True)
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    root = a.repo_root.resolve()
    resolve = lambda path: path if path.is_absolute() else root / path
    decision = validate(root, resolve(a.contract), resolve(a.acceptance), resolve(a.registry), resolve(a.output))
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if decision["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
