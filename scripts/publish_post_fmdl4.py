#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

EVIDENCE_FILES = {
    "package_identity": "POST_FMDL4_PACKAGE_IDENTITY.json",
    "validation": "POST_FMDL4_REFRESH_VALIDATION.json",
    "action_review": "POST_FMDL4_ACTION_REVIEW.json",
    "cleanup_manifest": "POST_FMDL4_FILE_LIBRARY_RETAIN_DELETE_MANIFEST.json",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def z6(value: str) -> str:
    return str(value).strip().zfill(6)


def build_decision(repo: Path, market_dir: Path) -> dict[str, Any]:
    publication = load_json(repo / "config/post_fmdl4_release8_publication.json")
    binding = load_json(repo / "config/post_fmdl4_release4_state_binding.json")
    universe = load_json(repo / "config/post_fmdl4_symbol_universe.json")
    evidence_dir = repo / "evidence/post_fmdl4"
    errors: list[str] = []

    if publication["trade_authority"] != "NONE" or binding["trade_authority"] != "NONE":
        errors.append("TRADE_AUTHORITY_NOT_NONE")
    if binding["source_package_sha256"] != publication["source_release4_sha256"]:
        errors.append("SOURCE_RELEASE4_SHA_MISMATCH")
    if not binding["no_trade_confirmation_after_source_as_of"]:
        errors.append("NO_TRADE_CONFIRMATION_MISSING")

    for key, filename in EVIDENCE_FILES.items():
        path = evidence_dir / filename
        if not path.exists():
            errors.append(f"MISSING_EVIDENCE:{filename}")
        elif sha256(path) != publication["evidence_hashes"][key]:
            errors.append(f"EVIDENCE_HASH:{filename}")

    package_identity = load_json(evidence_dir / EVIDENCE_FILES["package_identity"])
    local_validation = load_json(evidence_dir / EVIDENCE_FILES["validation"])
    action_review = load_json(evidence_dir / EVIDENCE_FILES["action_review"])
    cleanup = load_json(evidence_dir / EVIDENCE_FILES["cleanup_manifest"])
    if package_identity["package_sha256"] != publication["package_sha256"]:
        errors.append("PACKAGE_SHA_MISMATCH")
    if package_identity["deterministic_replay_sha256"] != publication["package_sha256"]:
        errors.append("PACKAGE_REPLAY_MISMATCH")
    binary = package_identity["binary_validation"]
    if not (
        binary["outer_zip_openable"] is True
        and binary["nested_zip_openable_count"] == 4
        and binary["manifest_hash_error_count"] == 0
        and binary["same_input_replay_match"] is True
    ):
        errors.append("BINARY_VALIDATION_NOT_PASS")
    if local_validation["status"] != "PASS" or local_validation["hard_failures"]:
        errors.append("LOCAL_VALIDATION_NOT_PASS")
    if cleanup["safety_rule"] != "DO_NOT_DELETE_RELEASE4_UNTIL_RELEASE8_IS_UPLOADED_OPENABLE_AND_SHA_VERIFIED":
        errors.append("CLEANUP_SAFETY_RULE")

    date_key = publication["market_as_of"].replace("-", "")
    quotes = read_csv(market_dir / f"POST_FMDL4_A_SHARE_QUOTES_{date_key}.csv")
    navs = read_csv(market_dir / f"POST_FMDL4_FUND_NAV_{date_key}.csv")
    qmap = {z6(row["symbol"]): row for row in quotes}
    nmap = {z6(row["fund_code"]): row for row in navs}
    if len(qmap) != 30 or any(
        row["quote_date"] != publication["market_as_of"] or row["validation_status"] != "PASS"
        for row in quotes
    ):
        errors.append("QUOTE_SET_OR_DATE")
    if len(nmap) != 3 or any(row["validation_status"] != "PASS" for row in navs):
        errors.append("FUND_NAV_SET")
    if len(universe["symbols"]) != 30 or len({z6(x["symbol"]) for x in universe["symbols"]}) != 30:
        errors.append("SYMBOL_UNIVERSE")

    real_total = float(binding["real_execution_cash"])
    for row in binding["real_holdings"]:
        code = z6(row["code"])
        qty = float(row["quantity_or_shares"])
        price = float(nmap[code]["unit_nav"]) if code in nmap else float(qmap[code]["close"])
        real_total += round(qty * price, 2)
    sim_market = sum(
        round(float(row["quantity"]) * float(qmap[z6(row["security_code"])]["close"]), 2)
        for row in binding["simulation_holdings"]
    )
    sim_total = sim_market + float(binding["simulation_available_cash"])
    trigger_met = sum(
        float(qmap[code]["close"]) <= float(threshold)
        for code, threshold in binding["active_memo_price_thresholds"].items()
    )

    calculated = {
        "quote_count": len(qmap),
        "fund_nav_count": len(nmap),
        "real_holding_count": len(binding["real_holdings"]),
        "simulation_holding_count": len(binding["simulation_holdings"]),
        "candidate_core_count": len(binding["candidate_core_20"]),
        "active_memo_count": len(binding["active_memo_price_thresholds"]),
        "active_memo_trigger_met_count": trigger_met,
        "graduated_reconciliation_count": len(universe["graduated_routes"]),
        "formal_candidate_membership_change_count": 0,
        "simulation_admission_count": 0,
        "real_account_admission_count": 0,
        "order_generation_count": 0,
        "real_total_assets": round(real_total, 2),
        "simulation_total_assets": round(sim_total, 2),
    }
    for key, expected in publication["metrics"].items():
        if calculated.get(key) != expected:
            errors.append(f"METRIC:{key}:{calculated.get(key)}!={expected}")

    if (
        action_review["real_account"]["immediate_trade_proposal_count"] != 0
        or action_review["simulation"]["immediate_trade_proposal_count"] != 0
    ):
        errors.append("IMMEDIATE_TRADE_PROPOSAL_NOT_ZERO")
    if action_review["candidate_pool"]["formal_membership_add_count"] != 0:
        errors.append("CANDIDATE_MUTATION_NOT_ZERO")

    checks = {
        "source_release4_binding": "PASS" if not any(x.startswith("SOURCE_") for x in errors) else "FAIL",
        "committed_evidence_hashes": "PASS" if not any(x.startswith(("MISSING_EVIDENCE", "EVIDENCE_HASH")) for x in errors) else "FAIL",
        "local_binary_validation": "PASS" if not any(x.startswith(("PACKAGE_", "BINARY_", "LOCAL_")) for x in errors) else "FAIL",
        "market_replay": "PASS" if not any(x.startswith(("QUOTE_", "FUND_", "SYMBOL_")) for x in errors) else "FAIL",
        "state_recalculation": "PASS" if not any(x.startswith("METRIC:") for x in errors) else "FAIL",
        "zero_mutation_and_trade_authority": "PASS" if not any(
            x in errors
            for x in ["TRADE_AUTHORITY_NOT_NONE", "IMMEDIATE_TRADE_PROPOSAL_NOT_ZERO", "CANDIDATE_MUTATION_NOT_ZERO"]
        ) else "FAIL",
    }
    return {
        "program_id": publication["program_id"],
        "release_id": publication["release_id"],
        "run_id": publication["run_id"],
        "status": publication["status"] if not errors else "FAIL",
        "hard_failures": errors,
        "checks": checks,
        "metrics": calculated,
        "package_identity": {
            "filename": publication["package_filename"],
            "sha256": publication["package_sha256"],
            "size_bytes": publication["package_size_bytes"],
            "binary_validation_posture": publication["binary_validation_posture"],
            "file_library_import_status": publication["file_library_import_status"],
        },
        "fmdl_release_ids": publication["fmdl_release_ids"],
        "cash_policy": publication["cash_policy"],
        "trade_authority": "NONE",
        "next_program_gate": publication["next_program_gate"],
        "generated_at": publication["generated_at"],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def publish(repo: Path, decision: dict[str, Any], output: Path, do_publish: bool) -> None:
    write_json(output / "POST_FMDL4_DECISION.json", decision)
    write_json(output / "POST_FMDL4_VALIDATION.json", {**decision, "validation_status": "PASS" if not decision["hard_failures"] else "FAIL"})
    release = {**decision, "release_sequence": 8, "authority": "CANONICAL_REFRESH_AND_STATE_RECONCILIATION_ONLY"}
    write_json(output / "POST_FMDL4_RELEASE.json", release)
    if not do_publish:
        return
    release_id = decision["release_id"]
    targets = [
        repo / "outputs/post_fmdl4/current",
        repo / f"datasets/post_fmdl4/releases/{release_id}",
        repo / f"outputs/post_fmdl4/archive/{release_id}",
    ]
    for target in targets:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(output, target)
    write_json(
        repo / "outputs/status/POST_FMDL4_LAST_SUCCESS.json",
        {
            "program_id": decision["program_id"],
            "release_id": release_id,
            "run_id": decision["run_id"],
            "status": decision["status"],
            "current_release_path": "outputs/post_fmdl4/current/POST_FMDL4_RELEASE.json",
            "release_root": f"datasets/post_fmdl4/releases/{release_id}",
            "archive_path": f"outputs/post_fmdl4/archive/{release_id}",
            "package_sha256": decision["package_identity"]["sha256"],
            "file_library_import_status": decision["package_identity"]["file_library_import_status"],
            "next_program_gate": decision["next_program_gate"],
            "trade_authority": "NONE",
            "generated_at": decision["generated_at"],
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--market-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    repo = Path(args.repo_root).resolve()
    decision = build_decision(repo, Path(args.market_dir))
    publish(repo, decision, Path(args.output), args.publish)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not decision["hard_failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
