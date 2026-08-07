#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

PROGRAM_ID="HKCU-P2B-E2-S1"
TRADE_AUTHORITY="NONE"


def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',required=True); a=p.parse_args(); out=Path(a.output)
    failures=[]
    decision=json.loads((out/'HKCU_P2B_E2_S1_DECISION.json').read_text())
    quality=json.loads((out/'HKCU_P2B_E2_S1_QUALITY_REPORT.json').read_text())
    sec=pd.read_csv(out/'HKCU_P2B_E2_S1_TOP20_SECURITY_DECISION_SYNTHESIS.csv',dtype={'stock_code_5d':str},keep_default_na=False)
    dim=pd.read_csv(out/'HKCU_P2B_E2_S1_TOP20_DIMENSION_DECISION_SURFACE.csv',dtype={'stock_code_5d':str},keep_default_na=False)
    blockers=pd.read_csv(out/'HKCU_P2B_E2_S1_RETAINED_INVESTMENT_BLOCKERS.csv',dtype={'stock_code_5d':str},keep_default_na=False)
    if decision.get('status')!='PASS_P2B_E2_TOP20_DECISION_SYNTHESIS': failures.append('DECISION_NOT_PASS')
    if quality.get('status')!='PASS': failures.append('QUALITY_NOT_PASS')
    if len(sec)!=20 or sec['security_id'].nunique()!=20: failures.append('SECURITY_COUNT')
    if len(dim)!=60: failures.append('DIMENSION_COUNT')
    if dim.duplicated(['security_id','research_dimension']).any(): failures.append('DUPLICATE_DIMENSION')
    if set(dim.groupby('security_id').size())!={3}: failures.append('NOT_THREE_DIMENSIONS_PER_SECURITY')
    if len(blockers)!=2 or set(blockers['security_id'])!={'HKEX:00551','HKEX:01114'}: failures.append('BLOCKER_SET')
    if int((sec['decision_state']=='ADVANCE_TO_P2B_CROSS_SECTIONAL_SYNTHESIS_WITH_CONFIDENCE_CAP').sum())!=18: failures.append('ADVANCE_COUNT')
    if int((sec['decision_state']=='HOLD_RETAINED_INVESTMENT_BLOCKER').sum())!=2: failures.append('HOLD_COUNT')
    if dim['alpha_score'].astype(str).str.strip().ne('').any() or sec['alpha_score'].astype(str).str.strip().ne('').any(): failures.append('ALPHA_SCORE_PRESENT')
    if not sec['formal_candidate_graduation_allowed'].astype(str).str.lower().eq('false').all(): failures.append('GRADUATION_ALLOWED')
    if not (dim['trade_authority']==TRADE_AUTHORITY).all() or not (sec['trade_authority']==TRADE_AUTHORITY).all(): failures.append('TRADE_AUTHORITY')
    neg=dim[dim['final_dimension_state'].isin(['RETAINED_DIRECT_NEGATIVE_SIGNAL','RETAINED_INVESTMENT_BLOCKER'])]
    for r in neg.itertuples(index=False):
        s=sec[sec['security_id']==r.security_id]
        if s.empty or s.iloc[0]['decision_state']!='HOLD_RETAINED_INVESTMENT_BLOCKER': failures.append('NEGATIVE_NOT_HELD:'+r.security_id)
    if failures: raise SystemExit('P2B_E2_S1_VALIDATION_FAILED:'+'|'.join(sorted(set(failures))))
    print('PASS_P2B_E2_TOP20_DECISION_SYNTHESIS_VALIDATION')

if __name__=='__main__': main()
