from __future__ import annotations

import argparse
from pathlib import Path

from fmdl6x2b_candidate import build_candidate, publish, validate_candidate
from fmdl6x2b_common import validate_contract


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('validate-contract')
    p.add_argument('--repo-root', default='.')

    p = sub.add_parser('build')
    p.add_argument('--repo-root', default='.')
    p.add_argument('--candidate', required=True)
    p.add_argument('--accepted-at', required=True)
    p.add_argument('--source-commit', required=True)

    p = sub.add_parser('validate-candidate')
    p.add_argument('--repo-root', default='.')
    p.add_argument('--candidate', required=True)
    p.add_argument('--accepted-at', required=True)
    p.add_argument('--source-commit', required=True)
    p.add_argument('--acceptance', required=True)

    p = sub.add_parser('publish')
    p.add_argument('--repo-root', default='.')
    p.add_argument('--candidate', required=True)
    p.add_argument('--published-at', required=True)
    p.add_argument('--source-commit', required=True)

    args = parser.parse_args()
    root = Path(args.repo_root)
    if args.command == 'validate-contract':
        checks, errors = validate_contract(root)
        print({'checks': len(checks), 'errors': errors})
        if errors:
            raise SystemExit(1)
    elif args.command == 'build':
        result = build_candidate(root, Path(args.candidate), args.accepted_at, args.source_commit)
        print(result['summary'])
    elif args.command == 'validate-candidate':
        print(validate_candidate(root, Path(args.candidate), args.accepted_at, args.source_commit, Path(args.acceptance)))
    elif args.command == 'publish':
        print(publish(root, Path(args.candidate), args.published_at, args.source_commit))


if __name__ == '__main__':
    main()
