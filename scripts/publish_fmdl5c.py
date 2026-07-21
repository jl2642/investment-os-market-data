#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


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
    decision = json.loads((candidate / "FMDL5C_DECISION.json").read_text(encoding="utf-8"))
    manifest = json.loads((candidate / "FMDL5C_MANIFEST.json").read_text(encoding="utf-8"))
    if decision.get("status") != "FMDL5C_PRICE_VOLUME_CORPORATE_ACTION_AND_FX_STORE_ACCEPTED":
        raise ValueError(f"CANDIDATE_NOT_ACCEPTED:{decision.get('status')}")
    if decision.get("hard_failures"):
        raise ValueError(f"HARD_FAILURES:{decision['hard_failures']}")
    if decision.get("trade_authority") != "NONE":
        raise ValueError("TRADE_AUTHORITY_VIOLATION")
    release_id = decision["release_id"]
    current = root / "outputs/fmdl5c/current"
    immutable = root / f"datasets/fmdl5c/releases/{release_id}"
    archive = root / f"outputs/fmdl5c/archive/{release_id}"
    copy_tree(candidate, current)
    copy_tree(candidate, immutable)
    copy_tree(candidate, archive)
    last_success = {
        "program_id": "FMDL-5C",
        "status": decision["status"],
        "release_id": release_id,
        "release_sequence": decision["release_sequence"],
        "canonical_sha256": decision["canonical_sha256"],
        "source_release_id": decision["source_release_id"],
        "security_count": decision["metrics"]["source_security_count"],
        "latest_snapshot_count": decision["metrics"]["latest_snapshot_count"],
        "price_row_count": decision["metrics"]["price_row_count"],
        "corporate_action_count": decision["metrics"]["corporate_action_count"],
        "fx_row_count": decision["metrics"]["fx_row_count"],
        "current_path": str(current.relative_to(root)),
        "immutable_path": str(immutable.relative_to(root)),
        "archive_path": str(archive.relative_to(root)),
        "next_gate": decision["next_gate"],
        "trade_authority": "NONE",
        "manifest_release_id": manifest["release_id"],
    }
    status_dir = root / "outputs/status"
    status_dir.mkdir(parents=True, exist_ok=True)
    (status_dir / "FMDL5C_LAST_SUCCESS.json").write_text(
        json.dumps(last_success, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(last_success, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
