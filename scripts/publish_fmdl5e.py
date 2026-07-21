#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ACCEPTED_STATUS = "FMDL5E_HONG_KONG_FACTOR_AND_SCREENING_ADAPTER_ACCEPTED"


def copy_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root)
    candidate = Path(args.candidate)
    decision = json.loads((candidate / "FMDL5E_DECISION.json").read_text(encoding="utf-8"))
    manifest = json.loads((candidate / "FMDL5E_MANIFEST.json").read_text(encoding="utf-8"))
    if decision.get("status") != ACCEPTED_STATUS:
        raise ValueError(f"CANDIDATE_NOT_ACCEPTED:{decision.get('status')}")
    if decision.get("hard_failures"):
        raise ValueError(f"HARD_FAILURES:{decision['hard_failures']}")
    if decision.get("trade_authority") != "NONE":
        raise ValueError("TRADE_AUTHORITY_VIOLATION")
    for key in ("candidate_pool_mutation_count", "simulation_mutation_count", "real_account_mutation_count", "order_generation_count"):
        if decision.get(key) != 0:
            raise ValueError(f"STATE_MUTATION_VIOLATION:{key}")

    release_id = decision["release_id"]
    current = root / "outputs/fmdl5e/current"
    immutable = root / f"datasets/fmdl5e/releases/{release_id}"
    archive = root / f"outputs/fmdl5e/archive/{release_id}"
    copy_tree(candidate, current)
    copy_tree(candidate, immutable)
    copy_tree(candidate, archive)
    metrics = decision["metrics"]
    last_success = {
        "program_id": "FMDL-5E",
        "status": decision["status"],
        "release_id": release_id,
        "release_sequence": decision["release_sequence"],
        "source_release_ids": decision["source_release_ids"],
        "as_of_date": decision["as_of_date"],
        "canonical_sha256": decision["canonical_sha256"],
        "security_count": metrics["source_security_count"],
        "equity_security_count": metrics["equity_security_count"],
        "factor_count": metrics["factor_count"],
        "longlist_count": metrics["longlist_count"],
        "priority_bucket_counts": metrics["priority_bucket_counts"],
        "current_path": str(current.relative_to(root)),
        "immutable_path": str(immutable.relative_to(root)),
        "archive_path": str(archive.relative_to(root)),
        "manifest_release_id": manifest["release_id"],
        "next_gate": decision["next_gate"],
        "trade_authority": "NONE",
    }
    status_dir = root / "outputs/status"
    status_dir.mkdir(parents=True, exist_ok=True)
    (status_dir / "FMDL5E_LAST_SUCCESS.json").write_text(
        json.dumps(last_success, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(last_success, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
