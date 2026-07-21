#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ACCEPTED_STATUS = "FMDL5D_HKEX_DISCLOSURE_AND_FINANCIAL_NORMALIZATION_ACCEPTED_WITH_CONTROLLED_QUARANTINE"


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
    decision = json.loads((candidate / "FMDL5D_DECISION.json").read_text(encoding="utf-8"))
    manifest = json.loads((candidate / "FMDL5D_MANIFEST.json").read_text(encoding="utf-8"))
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
    current = root / "outputs/fmdl5d/current"
    immutable = root / f"datasets/fmdl5d/releases/{release_id}"
    archive = root / f"outputs/fmdl5d/archive/{release_id}"
    copy_tree(candidate, current)
    copy_tree(candidate, immutable)
    copy_tree(candidate, archive)
    last_success = {
        "program_id": "FMDL-5D",
        "repair_round": decision.get("repair_round"),
        "status": decision["status"],
        "release_id": release_id,
        "release_sequence": decision["release_sequence"],
        "source_release_id": decision["source_release_id"],
        "canonical_sha256": decision["canonical_sha256"],
        "security_count": decision["metrics"]["source_security_count"],
        "equity_security_count": decision["metrics"]["equity_security_count"],
        "official_financial_disclosure_count": decision["metrics"]["official_financial_disclosure_count"],
        "normalized_fact_count": decision["metrics"]["normalized_fact_count"],
        "decision_grade_security_count": decision["metrics"]["decision_grade_security_count"],
        "runtime_shard_count": decision["metrics"].get("r1_completed_shard_count"),
        "runtime_completed_security_count": decision["metrics"].get("r1_completed_security_count"),
        "current_path": str(current.relative_to(root)),
        "immutable_path": str(immutable.relative_to(root)),
        "archive_path": str(archive.relative_to(root)),
        "manifest_release_id": manifest["release_id"],
        "next_gate": decision["next_gate"],
        "trade_authority": "NONE",
    }
    status_dir = root / "outputs/status"
    status_dir.mkdir(parents=True, exist_ok=True)
    (status_dir / "FMDL5D_LAST_SUCCESS.json").write_text(
        json.dumps(last_success, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(last_success, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
