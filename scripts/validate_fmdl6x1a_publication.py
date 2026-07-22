#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CURRENT=ROOT/'outputs/fmdl6x1a/current'
LAST=ROOT/'outputs/status/FMDL6X1A_LAST_SUCCESS.json'
CONFIG=ROOT/'config/fmdl6x1a_existing_pilot_audit_dual_activation_contract.json'

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def validate():
    errors=[]
    config=load(CONFIG); last=load(LAST); release=load(CURRENT/'FMDL6X1A_RELEASE.json'); manifest=load(CURRENT/'FMDL6X1A_MANIFEST.json')
    if config.get('status')!='ACCEPTED': errors.append('config not ACCEPTED')
    if config.get('repair_identity')!='FMDL-6X1-A-R1': errors.append('repair identity mismatch')
    if release.get('release_id')!=last.get('release_id'): errors.append('release/last-success mismatch')
    if release.get('status')!='FMDL6X1A_EXISTING_PILOT_AUDIT_AND_DUAL_ACTIVATION_CONTRACT_ACCEPTED': errors.append('exit status mismatch')
    if release.get('research_production_gate')!='OPEN_FOR_CONTROLLED_BUILD': errors.append('research gate mismatch')
    if release.get('brokerage_real_account_gate')!='CLOSED_NO_CHANNEL': errors.append('brokerage gate mismatch')
    for key in ('candidate_pool_mutations','simulation_mutations','real_account_mutations','orders'):
        if release.get(key)!=0: errors.append(f'{key} nonzero')
    if release.get('trade_authority')!='NONE': errors.append('trade authority escalated')
    for row in manifest.get('files',[]):
        p=CURRENT/row['path']
        if not p.exists(): errors.append(f'missing {row["path"]}'); continue
        b=p.read_bytes()
        if len(b)!=row['size_bytes']: errors.append(f'size mismatch {row["path"]}')
        if hashlib.sha256(b).hexdigest()!=row['sha256']: errors.append(f'hash mismatch {row["path"]}')
    immutable=ROOT/'datasets/fmdl6x1a/releases'/release['release_id']
    for p in CURRENT.iterdir():
        q=immutable/p.name
        if not q.exists() or q.read_bytes()!=p.read_bytes(): errors.append(f'immutable parity mismatch {p.name}')
    return errors

if __name__=='__main__':
    errors=validate(); print(json.dumps({'status':'PASS' if not errors else 'FAIL','errors':errors},indent=2)); raise SystemExit(1 if errors else 0)
