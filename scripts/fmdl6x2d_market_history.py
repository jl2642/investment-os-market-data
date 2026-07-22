from __future__ import annotations

import argparse
from pathlib import Path

from fmdl6x2d_candidate import build_candidate, publish, validate_candidate
from fmdl6x2d_common import CONTRACT_PATH, load_json, validate_contract
from fmdl6x2d_fetch import capture_routes
from fmdl6x2d_market import load_security_universe, select_cohort


def main() -> None:
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest='cmd',required=True)
    for name in ('validate-contract','capture','build','validate-candidate','publish'):
        p=sub.add_parser(name); p.add_argument('--repo-root',default='.')
        if name in ('capture','build','validate-candidate','publish'): p.add_argument('--raw',required=True)
        if name in ('build','validate-candidate','publish'): p.add_argument('--candidate',required=True)
        if name in ('build','validate-candidate'): p.add_argument('--accepted-at',required=True); p.add_argument('--source-commit',required=True)
        if name=='validate-candidate': p.add_argument('--acceptance',required=True)
        if name=='publish': p.add_argument('--published-at',required=True); p.add_argument('--source-commit',required=True)
    args=parser.parse_args(); root=Path(args.repo_root)
    if args.cmd=='validate-contract':
        checks,errors=validate_contract(root); print({'checks':checks,'errors':errors})
        if errors: raise SystemExit(1)
    elif args.cmd=='capture':
        contract=load_json(root/CONTRACT_PATH); securities,listings=load_security_universe(root); cohort,_=select_cohort(securities,listings,contract); capture_routes(contract,cohort,Path(args.raw))
    elif args.cmd=='build': build_candidate(root,Path(args.raw),Path(args.candidate),args.accepted_at,args.source_commit)
    elif args.cmd=='validate-candidate': validate_candidate(root,Path(args.raw),Path(args.candidate),args.accepted_at,args.source_commit,Path(args.acceptance))
    elif args.cmd=='publish': publish(root,Path(args.raw),Path(args.candidate),args.published_at,args.source_commit)

if __name__=='__main__': main()
