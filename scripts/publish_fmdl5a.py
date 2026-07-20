#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def publish(repo: Path, candidate: Path) -> None:
    decision = read_json(candidate / "FMDL5A_DECISION.json")
    if decision["status"] != "FMDL5A_MARKET_CONTRACT_AND_UNIVERSE_BOUNDARY_ACCEPTED" or decision["hard_failures"]:
        raise SystemExit("FMDL5A_CANDIDATE_NOT_ACCEPTED")
    if decision["trade_authority"] != "NONE" or any(decision[x] for x in ["candidate_pool_mutation_count","simulation_mutation_count","real_account_mutation_count","order_generation_count"]):
        raise SystemExit("FMDL5A_MUTATION_BOUNDARY")
    release_id = decision["release_id"]
    targets = [
        repo / "outputs/fmdl5a/current",
        repo / f"datasets/fmdl5a/releases/{release_id}",
        repo / f"outputs/fmdl5a/archive/{release_id}",
    ]
    for target in targets:
        if target.exists(): shutil.rmtree(target)
        shutil.copytree(candidate, target)
    write_json(repo / "outputs/status/FMDL5A_LAST_SUCCESS.json", {
        "program_id":"FMDL-5A","release_id":release_id,
        "status":decision["status"],
        "current_release_path":"outputs/fmdl5a/current/FMDL5A_RELEASE.json",
        "release_root":f"datasets/fmdl5a/releases/{release_id}",
        "archive_path":f"outputs/fmdl5a/archive/{release_id}",
        "source_update_date":decision["source_update_date"],
        "effective_southbound_trading_date":decision["effective_southbound_trading_date"],
        "canonical_count":decision["metrics"]["canonical_count"],
        "next_gate":decision["next_gate"],"trade_authority":"NONE"
    })


def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--repo-root",default="."); p.add_argument("--candidate",required=True); a=p.parse_args()
    publish(Path(a.repo_root).resolve(),Path(a.candidate).resolve()); return 0

if __name__ == "__main__": raise SystemExit(main())
