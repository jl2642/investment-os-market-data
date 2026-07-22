#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from fmdl6e_quality_benchmark import DEFAULT_CANDIDATE, DEFAULT_CONTRACT, publish_candidate


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish an accepted FMDL-6E candidate")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--contract", default=DEFAULT_CONTRACT)
    parser.add_argument("--candidate", default=DEFAULT_CANDIDATE)
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    publish_candidate(
        repo_root,
        (repo_root / args.contract).resolve(),
        (repo_root / args.candidate).resolve(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
