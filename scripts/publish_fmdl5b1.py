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
    decision = json.loads((candidate / "FMDL5B1_DECISION.json").read_text(encoding="utf-8"))
    if decision["hard_failures"]:
        raise SystemExit("cannot publish rejected candidate")
    release_id = decision["release_id"]
    current = root / "outputs/fmdl5b1/current"
    immutable = root / f"datasets/fmdl5b1/releases/{release_id}"
    archive = root / f"outputs/fmdl5b1/archive/{release_id}"
    copy_tree(candidate, current)
    copy_tree(candidate, immutable)
    copy_tree(candidate, archive)
    release = {
        "program_id": "FMDL-5B-1",
        "release_id": release_id,
        "status": decision["status"],
        "release_sequence": 11,
        "current_path": "outputs/fmdl5b1/current",
        "immutable_path": f"datasets/fmdl5b1/releases/{release_id}",
        "archive_path": f"outputs/fmdl5b1/archive/{release_id}",
        "security_master_count": decision["metrics"]["security_master_count"],
        "security_master_sha256": decision["security_master_sha256"],
        "next_gate": decision["next_gate"],
        "trade_authority": "NONE"
    }
    payload = json.dumps(release, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    for folder in (current, immutable, archive):
        (folder / "FMDL5B1_RELEASE.json").write_text(payload, encoding="utf-8")
    status_dir = root / "outputs/status"
    status_dir.mkdir(parents=True, exist_ok=True)
    (status_dir / "FMDL5B1_LAST_SUCCESS.json").write_text(json.dumps(release, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(release, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
