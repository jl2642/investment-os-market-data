from __future__ import annotations

import argparse
from pathlib import Path

from fmdl5_final_core import build_candidate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", default="outputs/fmdl5/final/candidate")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    output = (repo_root / args.output).resolve()
    decision = build_candidate(repo_root, output)
    print(decision["status"])
    print(decision["release_id"])


if __name__ == "__main__":
    main()
