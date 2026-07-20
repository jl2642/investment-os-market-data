#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision", required=True)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    repo = Path(args.repo_root).resolve()
    decision = json.loads(Path(args.decision).read_text(encoding="utf-8"))
    if decision.get("hard_failures"):
        raise SystemExit("cannot publish failed architecture decision")
    release_id = "FMDL5_0_20260720_" + decision["plan_sha256"][:12]
    release = {
        **decision,
        "release_id": release_id,
        "release_sequence": 9,
        "authority": "CROSS_MARKET_ADAPTER_ARCHITECTURE_AND_MASTER_PLAN_ONLY",
    }
    candidate = repo / "outputs/fmdl5_0/candidate/FMDL5_0_RELEASE.json"
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.publish:
        print(json.dumps(release, ensure_ascii=False, indent=2))
        return 0
    targets = [
        repo / "outputs/fmdl5_0/current",
        repo / f"datasets/fmdl5_0/releases/{release_id}",
        repo / f"outputs/fmdl5_0/archive/{release_id}",
    ]
    for target in targets:
        if target.exists(): shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate, target / "FMDL5_0_RELEASE.json")
        shutil.copy2(repo / "config/fmdl5_0_cross_market_master_plan.json", target / "FMDL5_0_MASTER_PLAN.json")
    last = {
        "program_id": "FMDL-5-0",
        "release_id": release_id,
        "status": release["status"],
        "current_release_path": "outputs/fmdl5_0/current/FMDL5_0_RELEASE.json",
        "release_root": f"datasets/fmdl5_0/releases/{release_id}",
        "archive_path": f"outputs/fmdl5_0/archive/{release_id}",
        "next_gate": release["next_gate"],
        "trade_authority": "NONE",
    }
    status = repo / "outputs/status/FMDL5_0_LAST_SUCCESS.json"
    status.parent.mkdir(parents=True, exist_ok=True)
    status.write_text(json.dumps(last, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(last, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
