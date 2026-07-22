from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

from fmdl6x2a_common import (
    CONTRACT_PATH, EXIT_STATUS, NEXT_GATE, PHASE_ID, fetch_sources, load_json,
    pretty_json, sha256_bytes, sha256_file, validate_contract, write_json,
)
from fmdl6x2a_candidate import build_candidate, compare_directories, validate_candidate

def copy_tree_exact(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)

def publish(repo_root: Path, candidate_root: Path, published_at: str, source_commit: str) -> dict[str, Any]:
    contract = load_json(repo_root / CONTRACT_PATH)
    decision = load_json(candidate_root / "FMDL6X2A_DECISION.json")
    if decision.get("status") != EXIT_STATUS:
        raise RuntimeError("CANDIDATE_NOT_ACCEPTED")
    release_id = decision["release_id"]
    current_root = repo_root / contract["storage_contract"]["current_root"]
    release_root = repo_root / contract["storage_contract"]["release_root"] / release_id / "security_master"
    if release_root.exists():
        raise RuntimeError("IMMUTABLE_RELEASE_COLLISION")
    if current_root.exists():
        archive_id = published_at.replace(":", "").replace("-", "")
        archive_root = repo_root / contract["storage_contract"]["archive_root"] / archive_id / "security_master"
        archive_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(current_root, archive_root)
    copy_tree_exact(candidate_root, current_root)
    release_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(candidate_root, release_root)
    parity_errors = compare_directories(current_root, release_root)
    if parity_errors:
        raise RuntimeError("CURRENT_RELEASE_PARITY_FAILURE:" + ",".join(parity_errors))
    observation_date = decision["observation_date"]
    raw_archive = repo_root / contract["storage_contract"]["raw_root"] / observation_date / release_id
    normalized_archive = repo_root / contract["storage_contract"]["normalized_root"] / release_id
    raw_archive.mkdir(parents=True, exist_ok=True)
    for path in (candidate_root / "raw").iterdir():
        shutil.copy2(path, raw_archive / path.name)
    normalized_archive.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate_root / "FMDL6X2A_SECURITY_MASTER_SHARDS.zip", normalized_archive / "FMDL6X2A_SECURITY_MASTER_SHARDS.zip")
    shutil.copy2(candidate_root / "FMDL6X2A_MANIFEST.json", normalized_archive / "FMDL6X2A_MANIFEST.json")
    pointer = {
        "phase_id": PHASE_ID, "status": EXIT_STATUS, "release_id": release_id,
        "release_sequence": contract["storage_contract"]["release_sequence"],
        "current_path": contract["storage_contract"]["current_root"],
        "release_path": f"{contract['storage_contract']['release_root']}/{release_id}/security_master",
        "raw_snapshot_path": f"{contract['storage_contract']['raw_root']}/{observation_date}/{release_id}",
        "normalized_path": f"{contract['storage_contract']['normalized_root']}/{release_id}",
        "manifest_sha256": sha256_file(current_root / "FMDL6X2A_MANIFEST.json"),
        "published_at": published_at, "source_commit": source_commit,
        "included_security_records": decision["included_security_records"],
        "included_by_venue": decision["included_by_venue"],
        "excluded_rows": decision["excluded_rows"], "quarantined_rows": decision["quarantined_rows"],
        "next_gate": NEXT_GATE, "research_production_gate": "OPEN_FOR_FMDL6X2_DATA_PRODUCTION",
        "brokerage_real_account_gate": "CLOSED_NO_CHANNEL", "trade_authority": "NONE",
    }
    write_json(repo_root / contract["storage_contract"]["last_success_path"], pointer)
    write_json(repo_root / contract["storage_contract"]["lkg_path"], {
        **pointer, "lkg_scope": "SECURITY_MASTER_DOMAIN",
        "lkg_reason": "LATEST_ACCEPTED_COMPLETE_CURRENT_SECURITY_MASTER",
    })
    return pointer

def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("validate-contract"); p.add_argument("--repo-root", default=".")
    p = sub.add_parser("fetch"); p.add_argument("--repo-root", default="."); p.add_argument("--raw-root", required=True)
    p = sub.add_parser("build")
    p.add_argument("--repo-root", default="."); p.add_argument("--raw-root", required=True)
    p.add_argument("--candidate", required=True); p.add_argument("--accepted-at", required=True)
    p.add_argument("--source-commit", required=True)
    p = sub.add_parser("validate-candidate")
    p.add_argument("--repo-root", default="."); p.add_argument("--raw-root", required=True)
    p.add_argument("--candidate", required=True); p.add_argument("--accepted-at", required=True)
    p.add_argument("--source-commit", required=True); p.add_argument("--acceptance", required=True)
    p = sub.add_parser("publish")
    p.add_argument("--repo-root", default="."); p.add_argument("--candidate", required=True)
    p.add_argument("--published-at", required=True); p.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    repo = Path(args.repo_root).resolve()
    if args.command == "validate-contract":
        checks, errors = validate_contract(repo)
        print(pretty_json({"phase_id": PHASE_ID, "checks": checks, "errors": errors}), end="")
        return 1 if errors else 0
    if args.command == "fetch":
        print(pretty_json(fetch_sources(repo, Path(args.raw_root))), end="")
        return 0
    if args.command == "build":
        result = build_candidate(repo, Path(args.raw_root), Path(args.candidate), args.accepted_at, args.source_commit)
        print(pretty_json(result), end="")
        return 0 if result["quality_status"] == "PASS" else 1
    if args.command == "validate-candidate":
        _, errors = validate_candidate(repo, Path(args.raw_root), Path(args.candidate), args.accepted_at, args.source_commit, Path(args.acceptance))
        print(pretty_json({"phase_id": PHASE_ID, "errors": errors}), end="")
        return 1 if errors else 0
    if args.command == "publish":
        print(pretty_json(publish(repo, Path(args.candidate), args.published_at, args.source_commit)), end="")
        return 0
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
