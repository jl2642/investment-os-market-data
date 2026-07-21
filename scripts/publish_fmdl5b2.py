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
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root)
    candidate = Path(args.candidate)
    decision = json.loads((candidate / "FMDL5B2_DECISION.json").read_text(encoding="utf-8"))
    if decision.get("hard_failures"):
        raise SystemExit("Cannot publish rejected FMDL-5B-2 candidate")
    release_id = str(decision["release_id"])
    current = root / "outputs/fmdl5b2/current"
    immutable = root / f"datasets/fmdl5b2/releases/{release_id}"
    archive = root / f"outputs/fmdl5b2/archive/{release_id}"
    copy_tree(candidate, current)
    copy_tree(candidate, immutable)
    copy_tree(candidate, archive)
    last_success = {
        "program_id": "FMDL-5B-2",
        "release_id": release_id,
        "release_sequence": 12,
        "status": decision["status"],
        "canonical_sha256": decision["canonical_sha256"],
        "security_count": decision["metrics"]["semantic_overlay_count"],
        "issuer_count": decision["metrics"]["issuer_count"],
        "official_di_issuer_mapping_count": decision["metrics"]["official_di_issuer_mapping_count"],
        "current_path": str(current),
        "immutable_path": str(immutable),
        "archive_path": str(archive),
        "next_gate": decision["next_gate"],
        "trade_authority": "NONE",
    }
    status = root / "outputs/status/FMDL5B2_LAST_SUCCESS.json"
    status.parent.mkdir(parents=True, exist_ok=True)
    status.write_text(json.dumps(last_success, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(last_success, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
