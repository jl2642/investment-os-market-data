from __future__ import annotations

import argparse
from pathlib import Path

from fmdl6x2c_candidate import build_candidate, publish, validate_candidate
from fmdl6x2c_common import validate_contract


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-contract")
    validate.add_argument("--repo-root", default=".")

    build = sub.add_parser("build")
    build.add_argument("--repo-root", default=".")
    build.add_argument("--candidate", required=True)
    build.add_argument("--accepted-at", required=True)
    build.add_argument("--source-commit", required=True)

    check = sub.add_parser("validate-candidate")
    check.add_argument("--repo-root", default=".")
    check.add_argument("--candidate", required=True)
    check.add_argument("--accepted-at", required=True)
    check.add_argument("--source-commit", required=True)
    check.add_argument("--acceptance", required=True)

    promote = sub.add_parser("publish")
    promote.add_argument("--repo-root", default=".")
    promote.add_argument("--candidate", required=True)
    promote.add_argument("--published-at", required=True)
    promote.add_argument("--source-commit", required=True)

    args = parser.parse_args()
    repo = Path(args.repo_root)
    if args.command == "validate-contract":
        checks, errors = validate_contract(repo)
        print({"status": "PASS" if not errors else "FAIL", "checks": checks, "errors": errors})
        if errors:
            raise SystemExit(1)
    elif args.command == "build":
        print(build_candidate(repo, Path(args.candidate), args.accepted_at, args.source_commit))
    elif args.command == "validate-candidate":
        print(validate_candidate(repo, Path(args.candidate), args.accepted_at, args.source_commit, Path(args.acceptance)))
    elif args.command == "publish":
        print(publish(repo, Path(args.candidate), args.published_at, args.source_commit))


if __name__ == "__main__":
    main()
