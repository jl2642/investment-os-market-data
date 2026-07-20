from __future__ import annotations

import json, tempfile, zipfile
from pathlib import Path
import pandas as pd
from scripts import fmdl4c_core as core

ROOT=Path(__file__).resolve().parents[1]; CFG=ROOT/'config/fmdl4c_reentry_controls.json'


def main():
    cfg=core.read_json(CFG); out=ROOT/cfg['overlay']['candidate_root']; ns=out/cfg['overlay']['namespace']; st=ns/'STATE_CURRENT'
    d=core.read_json(out/'FMDL4C_DECISION.json'); m=core.read_json(out/'FMDL4C_RELEASE6_COMPOSITION_MANIFEST.json'); diff=core.read_json(st/'FMDL4C_VERSIONED_DIFF.json'); rb=core.read_json(st/'FMDL4C_ROLLBACK_AND_LKG_PROOF.json'); bind=core.read_json(st/'FMDL4C_BINDING_STATE.json'); fw=core.read_json(ns/'CORE_STATIC/FMDL4C_AUTHORITY_FIREWALL.json')
    trans=core.read_jsonl(st/'FMDL4C_STATE_TRANSITIONS.jsonl'); q=pd.read_csv(st/'FMDL4C_REENTRY_REVIEW_QUEUE.csv',dtype={'symbol':str}); cr=pd.read_csv(st/'FMDL4C_CANDIDATE_ROUTER.csv',dtype={'symbol':str}); sr=pd.read_csv(st/'FMDL4C_SIMULATION_ROUTER.csv',dtype={'symbol':str}); rr=pd.read_csv(st/'FMDL4C_REAL_ACCOUNT_ROUTER.csv',dtype={'symbol':str})
    grad=pd.read_csv(ROOT/cfg['entry_gate']['graduation_decisions_path'],dtype={'symbol':str}); gs=set(grad[grad.graduation_decision=='GRADUATED'].symbol); sets=[set(x.symbol) for x in (q,cr,sr,rr)]+[{x['symbol'] for x in trans}]
    failures=[]
    if d.get('status')!=cfg['exit_status'] or d.get('hard_failures')!=[]: failures.append('DECISION')
    if any(s!=gs for s in sets): failures.append('SYMBOL_SET_IDENTITY')
    terr=sum(bool(core.validate_transition(x,cfg)) for x in trans)
    if terr: failures.append('TRANSITION_SCHEMA')
    counts=q.queue_state.value_counts().to_dict()
    if len(trans)!=6 or counts.get('CANDIDATE_POOL_REENTRY_REVIEW_READY',0)!=4 or counts.get('SHADOW_TRACK_REENTRY_REVIEW_READY',0)!=2: failures.append('ROUTE_COUNTS')
    if q.transition_id.duplicated().any() or q.symbol.duplicated().any(): failures.append('DUPLICATES')
    router_permission_errors=int(cr.candidate_pool_mutation_authorized.astype(bool).sum()+sr.simulation_mutation_authorized.astype(bool).sum()+rr.real_account_mutation_authorized.astype(bool).sum())
    if router_permission_errors: failures.append('ROUTER_PERMISSION')
    trade_errors=sum(x.get('trade_authority')!='NONE' for x in (d,m,diff,rb,bind,fw))+sum((x.trade_authority!='NONE').sum() for x in (q,cr,sr,rr))+sum(x['trade_authority']!='NONE' for x in trans)
    if trade_errors: failures.append('TRADE_AUTHORITY')
    before=core.stable_hash([]); after=core.stable_hash([{'symbol':x['symbol'],'queue_state':x['queue_state'],'transition_id':x['transition_id']} for x in q.sort_values(['priority','symbol']).to_dict('records')])
    diff_errors=int(diff.get('before_state_hash')!=before)+int(diff.get('after_state_hash')!=after)+int(diff.get('operation_count')!=6)+sum(int(diff.get(k,0)) for k in ('candidate_pool_mutation_count','simulation_mutation_count','real_account_mutation_count'))
    if diff_errors: failures.append('VERSIONED_DIFF')
    rollback_errors=int(rb.get('expected_post_rollback_hash')!=before)+int(not rb.get('preserves_external_base'))+int(not rb.get('preserves_fmdl4a_adapter'))+int(not rb.get('preserves_fmdl4b_research'))+int(bool(rb.get('failed_run_replaces_current')))+int(bool(rb.get('failed_run_replaces_last_known_good')))+int(set(rb.get('rollback_tokens',[]))!={x['rollback_token'] for x in trans})
    if rollback_errors: failures.append('ROLLBACK_LKG')
    state_errors=sum(int(bind.get(k,0)) for k in ('candidate_pool_mutation_count','simulation_mutation_count','real_account_mutation_count','trade_register_mutation_count','order_generation_count'))+int(bind.get('applied_transition_count')!=6)+int(bind.get('applied_state_domain')!=cfg['state_domains']['overlay_reentry_queue'])
    if state_errors: failures.append('STATE_DOMAIN_SEPARATION')
    base=cfg['composition_inputs']['external_canonical_base']; base_errors=int(m.get('base_package',{}).get('package_sha256')!=base['package_sha256'])+int(m.get('base_package',{}).get('release_sequence')!=4)+int(m.get('release5_adapter',{}).get('release_id')!=cfg['composition_inputs']['release5_adapter_release_id'])+int(m.get('release4b_research',{}).get('release_id')!=d.get('bindings',{}).get('fmdl4b_release_id'))
    if base_errors: failures.append('COMPOSITION_BINDING')
    manifest_errors=0; expected={}
    for item in m.get('files',[]):
        p=ROOT/item['source_path']; manifest_errors+=int(not p.exists() or (p.exists() and (core.sha256_file(p)!=item['sha256'] or p.stat().st_size!=item['bytes']))); expected[item['package_path'].split('/',1)[1]]=item
    with zipfile.ZipFile(out/'FMDL4C_RELEASE6_STATE_OVERLAY.zip') as z:
        zip_errors=int(set(z.namelist())!=set(expected))
        for name,item in expected.items():
            try: data=z.read(name); zip_errors+=int(len(data)!=item['bytes'])+int(core.hashlib.sha256(data).hexdigest()!=item['sha256'])
            except KeyError: zip_errors+=1
    if manifest_errors: failures.append('MANIFEST')
    if zip_errors: failures.append('ZIP')
    with tempfile.TemporaryDirectory() as td:
        replay=Path(td)/'replay.zip'; core.deterministic_zip(ns,replay); replay_sha=core.sha256_file(replay)
    zip_sha=core.sha256_file(out/'FMDL4C_RELEASE6_STATE_OVERLAY.zip')
    if replay_sha!=zip_sha or zip_sha!=d['semantic_hashes']['overlay_zip']: failures.append('IDEMPOTENCE')
    hashes={'state_transitions':core.stable_hash([{k:v for k,v in x.items() if k!='created_at'} for x in sorted(trans,key=lambda x:x['symbol'])]),'reentry_queue':core.semantic_frame_hash(q,sort_by=('priority','symbol')),'candidate_router':core.semantic_frame_hash(cr),'simulation_router':core.semantic_frame_hash(sr),'real_account_router':core.semantic_frame_hash(rr),'versioned_diff':core.stable_hash(diff),'rollback_and_lkg':core.stable_hash(rb),'composition_manifest':core.stable_hash(m),'overlay_zip':zip_sha}
    hash_errors=sum(hashes.get(k)!=v for k,v in d.get('semantic_hashes',{}).items())
    if hash_errors: failures.append('SEMANTIC_HASHES')
    metrics={**d.get('metrics',{}),'transition_schema_error_count_independent':terr,'router_permission_error_count':router_permission_errors,'trade_authority_error_count_independent':trade_errors,'diff_error_count':diff_errors,'rollback_error_count':rollback_errors,'state_domain_error_count':state_errors,'base_binding_error_count':base_errors,'manifest_error_count':manifest_errors,'zip_error_count':zip_errors,'semantic_hash_error_count':hash_errors,'independent_overlay_zip_sha256':zip_sha,'idempotence_replay_zip_sha256':replay_sha}
    checks=['DECISION','SYMBOLS_AND_TRANSITIONS','ROUTE_COUNTS','VERSIONED_DIFF','ROLLBACK_AND_LKG','STATE_DOMAIN_SEPARATION','COMPOSITION_AND_ZIP','SAME_INPUT_IDEMPOTENCE','ZERO_TRADE_AUTHORITY']
    result={'validation_version':'1.0.0','program_id':'FMDL-4C','release_id':d.get('release_id'),'status':'PASS' if not failures else 'FAIL','hard_failures':sorted(set(failures)),'checks':[{'check_id':x,'status':'PASS' if not failures else 'FAIL'} for x in checks],'metrics':metrics,'controlled_limitations':cfg['controlled_limitations'],'authority':cfg['authority'],'trade_authority':'NONE','next_gate':cfg['next_gate']}
    core.write_json(out/'FMDL4C_VALIDATION.json',result); print(json.dumps(core.canonical(result),ensure_ascii=False,indent=2)); return 0 if not failures else 1

if __name__=='__main__': raise SystemExit(main())
