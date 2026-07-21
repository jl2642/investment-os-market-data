from __future__ import annotations

import argparse
from pathlib import Path

from fmdl5g_core import build_candidate


def main() -> None:
    parser = argparse.ArgumentParser(description="Build FMDL-5G Investment OS integration candidate")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", default="outputs/fmdl5g/integration/candidate")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    output = (repo_root / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output).resolve()
    decision = build_candidate(repo_root, output)
    print(f"{decision['status']} {decision['release_id']} {decision['canonical_sha256']}")


if __name__ == "__main__":
    main()
