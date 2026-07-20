#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path

import run_fmdl5a_universe as universe
from fmdl5a_robust_sources import configure_retries, fetch_szse_robust


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    universe.fetch_szse = fetch_szse_robust
    original_session = universe.session
    universe.session = lambda: configure_retries(original_session())
    try:
        release = universe.build(output)
        print(json.dumps(release, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        failure = {
            "status": "FAIL",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        (output / "FMDL5A_FAILURE.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
