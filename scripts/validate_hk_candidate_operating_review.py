#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument('--repo-root',default='.'); p.add_argument('--output',required=True); a=p.parse_args()
    root=Path(a.repo_root); out=Path(a.output)
    current=pd.read_csv(root/'outputs/hk_candidate/current/HK_CANDIDATE_CURRENT.csv',dtype={'stock_code_5d':str},keep_default_na=False)
    review=pd.read_csv(out/'HK_CANDIDATE_OPERATING_REVIEW.csv',dtype={'stock_code_5d':str},keep_default_na=False)
    decision=json.loads((out/'HK_CANDIDATE_OPERATING_REVIEW.json').read_text(encoding='utf-8'))
    errors=[]
    if len(current)!=70 or len(review)!=70: errors.append('COUNT')
    if set(current.security_id.astype(str))!=set(review.security_id.astype(str)): errors.append('MEMBERSHIP')
    if decision.get('status')!='PASS_HK_CANDIDATE_OPERATING_REVIEW': errors.append('STATUS')
    if decision.get('core_count')!=2 or decision.get('watch_count')!=68: errors.append('TIERS')
    for k in ('candidate_mutations','portfolio_mutations','orders'):
        if int(decision.get(k,-1))!=0: errors.append(k.upper())
    if decision.get('trade_authority')!='NONE': errors.append('AUTHORITY')
    for c in ('candidate_change_proposed','candidate_tier_change_proposed','portfolio_action_proposed','order_created'):
        if review[c].astype(str).str.lower().ne('false').any(): errors.append(c.upper())
    result={'status':'PASS' if not errors else 'FAIL','errors':sorted(set(errors)),'candidate_count':len(review),'trade_authority':decision.get('trade_authority')}
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    if errors: raise SystemExit(1)
if __name__=='__main__': main()
