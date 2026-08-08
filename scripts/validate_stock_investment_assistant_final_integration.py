#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]

def readj(p:str): return json.loads((ROOT/p).read_text(encoding='utf-8'))
def fail(errors, cond, code):
    if not cond: errors.append(code)

def published_current(x:dict)->bool:
    return x.get('as_of_date')=='2026-08-07' and x.get('status') in {'READY','PUBLISHED','PUBLISHED_WITH_WARNINGS'} and not x.get('hard_failures',[])

def main():
    c=readj('config/stock_investment_assistant_final_integration_contract.json')
    current=readj(c['output_path']); interface=readj(c['interface_path']); e=[]
    market=readj(c['authoritative_inputs']['a_market_release']); history=readj(c['authoritative_inputs']['a_history_release']); factors=readj(c['authoritative_inputs']['a_factor_release']); screening=readj(c['authoritative_inputs']['a_screening_report'])
    ac=readj(c['authoritative_inputs']['a_candidate_current']); loop=readj(c['authoritative_inputs']['a_candidate_dynamic_loop']); hk=pd.read_csv(ROOT/c['authoritative_inputs']['hk_candidate_current'],keep_default_na=False); hkdec=readj(c['authoritative_inputs']['hk_candidate_decision']); p5e=readj(c['authoritative_inputs']['hk_p5e_contract']); real=readj(c['authoritative_inputs']['real_current']); sim=readj(c['authoritative_inputs']['simulation_current']); wp3r=readj(c['authoritative_inputs']['wp3r_acceptance'])
    fail(e, published_current(market) and market.get('qa_status') in {'PASS','PASS_WITH_WARNINGS'}, 'A_MARKET')
    fail(e, published_current(history) and history.get('trade_authority')=='NONE', 'A_HISTORY')
    fail(e, published_current(factors) and factors.get('trade_authority')=='NONE', 'A_FACTORS')
    screening_ok=(screening.get('as_of_date')=='2026-08-07' and not screening.get('universe',{}).get('hard_failures',[]) and not screening.get('snapshot',{}).get('hard_failures',[]) and screening.get('universe',{}).get('qa_status') in {'PASS','PASS_WITH_WARNINGS'} and screening.get('snapshot',{}).get('qa_status') in {'PASS','PASS_WITH_WARNINGS'})
    fail(e, screening_ok, 'A_SCREENING')
    counts=ac.get('counts',{}); fail(e, counts.get('candidate_core')==2 and counts.get('research_queue')==33 and counts.get('shadow_track')==38 and counts.get('ready_for_user_decision')==0, 'A_CANDIDATE_COUNTS')
    fail(e, loop.get('status')=='ROUND2_OPERATING_OBSERVATION' and loop.get('completed_weekly_cycle_count',0)>=1 and loop.get('admission_count')==0 and loop.get('dynamic_exit_count')==0 and loop.get('trade_authority')=='NONE', 'A_DYNAMIC_LOOP')
    fail(e, c['accepted_external_evidence']['a_round2_natural_workflow_run_observed'] is True and c['accepted_external_evidence']['a_round2_natural_workflow_run_conclusion']=='SUCCESS', 'A_NATURAL_TRIGGER')
    fail(e, len(hk)==70 and int((hk['candidate_tier'].astype(str)=='CORE').sum())==2 and int((hk['candidate_tier'].astype(str)=='WATCH').sum())==68, 'HK_CANDIDATE')
    fail(e, hkdec.get('status')=='PASS_P3_2_CANDIDATE_POOL_PROMOTION' or hkdec.get('formal_candidate_count')==70, 'HK_DECISION')
    fail(e, p5e['acceptance']['phase_5_close_status']=='PHASE_5_CLOSED' and p5e['acceptance']['post_p5e_operating_state']=='HKCU_SPECIAL_DEVELOPMENT_COMPLETE_OPERATING_OBSERVATION', 'HK_P5E')
    fail(e, real.get('trade_authority')=='NONE' and sim.get('trade_authority')=='NONE', 'PORTFOLIO_AUTHORITY')
    fail(e, wp3r.get('status')=='WP3R_CONTINUOUS_CANDIDATE_ENGINE_CAPABILITY_ACCEPTED' and wp3r.get('continuous_candidate_engine_complete') is True, 'WP3R')
    round3=(ROOT/c['authoritative_inputs']['round3_workflow']).read_text(encoding='utf-8').lower(); fail(e, 'bounded cross-market' in round3 and 'us_rotation_pool_count' in round3 and 'workflow_dispatch' in round3 and 'trade_authority: none' in round3, 'US_BOUNDED_WORKFLOW')
    fail(e, current.get('development_status')==c['pass_status'] and all(v=='PASS' for v in current.get('acceptance',{}).values()), 'FINAL_CURRENT')
    fail(e, interface.get('trade_authority')=='NONE' and interface.get('orders')==0 and len(interface.get('query_modes',[]))>=6, 'CHATGPT_INTERFACE')
    fail(e, c['governance']['trade_authority']=='NONE' and c['governance']['orders']==0, 'GOVERNANCE')
    result={'status':'PASS' if not e else 'FAIL','errors':e,'development_status':current.get('development_status'),'a_candidate_counts':counts,'hk_candidate_count':len(hk),'wp3r_status':wp3r.get('status'),'trade_authority':'NONE'}
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    if e: raise SystemExit(1)
if __name__=='__main__': main()
