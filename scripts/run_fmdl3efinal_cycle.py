from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from scripts import fmdl3efinal_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3efinal_operational_closure.json"


def run(*args: str) -> None:
    subprocess.run([sys.executable, "-m", *args], cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()
    cfg = core.read_json(CONFIG)
    fmdl1 = core.read_json(ROOT / cfg["inputs"]["fmdl1_current_release"])
    de_release = core.read_json(ROOT / cfg["entry_chain"]["fmdl3ede_release"])
    source_date = str(fmdl1.get("as_of_date") or "")
    target_date = str(de_release.get("metrics", {}).get("target_market_as_of_date") or "")
    should_refresh = bool(args.force_refresh or (source_date and target_date and source_date > target_date))

    if should_refresh:
        baseline = core.read_json(ROOT / "outputs/fmdl3e/contract/current/FMDL3EA_BASELINE_MANIFEST.json")
        if source_date > str(baseline.get("market_as_of_date") or ""):
            run("scripts.run_fmdl3ebc_incremental", "--mode", "live")
        else:
            run("scripts.run_fmdl3ebc_replay_closure")
        run("scripts.validate_fmdl3ebc_candidate")
        run("scripts.publish_fmdl3ebc")
        run("scripts.run_fmdl3ede_acceptance")
        run("scripts.validate_fmdl3ede_candidate")
        run("scripts.publish_fmdl3ede")
        result = "REFRESHED"
    else:
        result = "NO_OP_ALREADY_CURRENT"

    run("scripts.run_fmdl3efinal_acceptance")
    run("scripts.validate_fmdl3efinal_candidate")
    if should_refresh:
        run("scripts.publish_fmdl3efinal")
    print(json.dumps({
        "status": result,
        "source_market_date": source_date,
        "current_fmdl3e_target_date": target_date,
        "force_refresh": args.force_refresh,
        "trade_authority": "NONE",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
