from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from fmdl5_final_core import load_json, write_json
from validate_fmdl5_final_candidate import validate


def replace_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)


def publish(repo_root: Path, candidate: Path) -> dict:
    validation = validate(repo_root, candidate)
    decision = load_json(candidate / "FMDL5_FINAL_DECISION.json")
    if validation.get("validation") != "PASS":
        raise ValueError("CANDIDATE_VALIDATION_NOT_PASS")
    if decision.get("status") != "FMDL5_HONG_KONG_STOCK_CONNECT_OPERATIONAL_ACCEPTANCE_ACCEPTED":
        raise ValueError("CANDIDATE_DECISION_NOT_ACCEPTED")

    release_id = str(decision["release_id"])
    current = repo_root / "outputs/fmdl5/final/current"
    immutable = repo_root / "datasets/fmdl5/final/releases" / release_id
    archive = repo_root / "outputs/fmdl5/final/archive" / release_id
    if immutable.exists():
        existing = load_json(immutable / "FMDL5_FINAL_DECISION.json")
        if existing.get("canonical_sha256") != decision.get("canonical_sha256"):
            raise ValueError("IMMUTABLE_RELEASE_ID_COLLISION")
    else:
        immutable.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(candidate, immutable)
    replace_tree(candidate, current)
    if not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(candidate, archive)

    metrics = decision["metrics"]
    pointer = {
        "program_id": "FMDL-5-FINAL",
        "release_id": release_id,
        "manifest_release_id": load_json(candidate / "FMDL5_FINAL_MANIFEST.json")["release_id"],
        "release_sequence": decision["release_sequence"],
        "as_of_date": decision["as_of_date"],
        "canonical_sha256": decision["canonical_sha256"],
        "status": decision["status"],
        "current_path": "outputs/fmdl5/final/current",
        "immutable_path": f"datasets/fmdl5/final/releases/{release_id}",
        "archive_path": f"outputs/fmdl5/final/archive/{release_id}",
        "southbound_security_count": metrics["southbound_security_count"],
        "common_equity_count": metrics["common_equity_count"],
        "longlist_count": metrics["longlist_count"],
        "formal_research_object_count": metrics["formal_research_object_count"],
        "state_transition_count": metrics["state_transition_count"],
        "candidate_reentry_review_count": metrics["candidate_reentry_review_count"],
        "shadow_track_count": metrics["shadow_track_count"],
        "cross_market_duplication_review_count": metrics["cross_market_duplication_review_count"],
        "candidate_pool_mutation_count": metrics["candidate_pool_mutation_count"],
        "simulation_mutation_count": metrics["simulation_mutation_count"],
        "real_account_mutation_count": metrics["real_account_mutation_count"],
        "order_generation_count": metrics["order_generation_count"],
        "canonical_base_release_id": "INVESTMENT_OS_R8_20260720_501345e84562",
        "canonical_package_posture": decision["canonical_package_posture"],
        "next_gate": decision["next_gate"],
        "next_program_scope": decision["next_program_scope"],
        "trade_authority": "NONE"
    }
    write_json(repo_root / "outputs/status/FMDL5_FINAL_LAST_SUCCESS.json", pointer)
    return pointer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--candidate", default="outputs/fmdl5/final/candidate")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    candidate = (repo_root / args.candidate).resolve()
    pointer = publish(repo_root, candidate)
    print(pointer["status"])
    print(pointer["release_id"])


if __name__ == "__main__":
    main()
