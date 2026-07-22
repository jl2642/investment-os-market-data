from __future__ import annotations
import argparse,csv,gzip,hashlib,io,json,shutil,zipfile
from datetime import datetime,timezone
from pathlib import Path
PHASE='FMDL-6X2-E'; EXIT='FMDL6X2E_SEC_FILINGS_AND_FINANCIAL_FACTS_STORE_ACCEPTED'; NEXT='FMDL-6X2-FINAL_FULL_STORE_RECONCILIATION_AND_OPERATIONAL_ACCEPTANCE'; CONTRACT=Path('config/fmdl6x2e_sec_filings_facts_contract.json'); EVID=Path('evidence/fmdl6x2e/2026-07-22'); ZTIME=(1980,1,1,0,0,0)
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def stable(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
def sha(b):return hashlib.sha256(b).hexdigest()
def shaf(p):return sha(p.read_bytes())
def rh(ns,*x):return sha((ns+'|'+'|'.join(map(str,x))).encode())
def bh(v,n=64):return f'{int(sha(v.encode()),16)%n:02X}'
def dgzip(rows):
 o=io.BytesIO();raw=''.join(stable(r)+'\n' for r in rows).encode()
 with gzip.GzipFile(filename='',mode='wb',fileobj=o,mtime=0) as h:h.write(raw)
 return o.getvalue()
def dzip(entries):
 o=io.BytesIO()
 with zipfile.ZipFile(o,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for n in sorted(entries):
   i=zipfile.ZipInfo(n,ZTIME);i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o100644<<16;z.writestr(i,entries[n])
 return o.getvalue()
def zrows(p,prefix):
 out=[]
 with zipfile.ZipFile(p) as z:
  for n in sorted(z.namelist()):
   if n.startswith(prefix) and n.endswith('.jsonl'):out += [json.loads(x) for x in z.read(n).decode().splitlines() if x.strip()]
 return out
def csvrows(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def contract_checks(root):
 c=load(root/CONTRACT);e=[];checks=[]
 def ck(i,v,a=None,x=None):checks.append({'check_id':i,'status':'PASS' if v else 'FAIL','actual':a,'expected':x});e.append(i) if not v else None
 ck('PHASE',c.get('phase_id')==PHASE,c.get('phase_id'),PHASE);ck('TRADE',c.get('trade_authority')=='NONE');p=root/c['entry_gate']['pointer_path'];ck('ENTRY_EXISTS',p.is_file())
 if p.is_file():
  v=load(p)
  for f,k in [('phase_id','required_phase_id'),('release_id','required_release_id'),('release_sequence','required_release_sequence'),('status','required_status'),('next_gate','required_next_gate'),('trade_authority','required_trade_authority')]:ck('ENTRY_'+f.upper(),v.get(f)==c['entry_gate'][k],v.get(f),c['entry_gate'][k])
 ck('SEC_ONLY',c['source_contract']['accepted_authority']=='SEC_OFFICIAL');ck('NO_PROXY',c['source_contract']['third_party_sec_proxy_authorized'] is False);ck('EXECUTOR',c['source_contract']['production_execution_environment']=='CHATGPT_WEB_CONTROLLED_OFFICIAL_RETRIEVAL');ck('UNIVERSE',c['coverage_contract']['universe_issuer_count_expected']==7419);ck('SHARDS',c['quality_contract']['expected_shard_count']==2368);ck('EXIT',c['required_exit_status']==EXIT);ck('NEXT',c['next_gate']==NEXT);ck('ZERO',all(v==0 for v in c['zero_mutation_gate'].values()))
 return c,checks,sorted(set(e))
def evidence(root):
 meta=load(root/EVID/'FMDL6X2E_SEC_OFFICIAL_EVIDENCE.json');err=[]
 if meta.get('source_authority')!='SEC_OFFICIAL' or meta.get('third_party_sec_proxy_used') is not False:err.append('AUTHORITY')
 if meta.get('execution_environment')!='CHATGPT_WEB_CONTROLLED_OFFICIAL_RETRIEVAL':err.append('EXECUTOR')
 probe=meta.get('github_hosted_probe',{});obs=probe.get('observations',[])
 if probe.get('all_routes_success') is not False or len(obs)!=3 or any(o.get('http_status')!=403 for o in obs):err.append('PROBE')
 for n,m in meta.get('files',{}).items():
  p=root/EVID/n
  if not p.is_file() or p.stat().st_size!=m['bytes'] or shaf(p)!=m['sha256']:err.append('FILE:'+n)
 filings=csvrows(root/EVID/'FMDL6X2E_FILINGS.csv');facts=csvrows(root/EVID/'FMDL6X2E_FACTS.csv')
 if any(not r['filing_index_url'].startswith('https://www.sec.gov/Archives/edgar/') for r in filings):err.append('FILING_SOURCE')
 if any(not r['source_url'].startswith('https://www.sec.gov/Archives/edgar/') or r['data_grade']!='DECISION_GRADE_OFFICIAL_SEC' for r in facts):err.append('FACT_SOURCE')
 if len({r['accession_number'] for r in filings})!=len(filings):err.append('DUP_ACCESSION')
 return meta,filings,facts,sorted(set(err))
def identity(root):
 p=root/'outputs/fmdl6x2/current/identity/FMDL6X2B_IDENTITY_SHARDS.zip';sec=zrows(p,'SECURITY/');lst=zrows(p,'LISTING/');smap={r['canonical_security_id']:r for r in sec};sym={}
 for r in lst:sym.setdefault(r['symbol'].upper(),[]).append(r)
 return smap,sym,sorted({r['canonical_issuer_id'] for r in sec})
def build(root,cand,at,commit):
 c,checks,err=contract_checks(root);meta,fin,fx,e2=evidence(root);err+=e2
 if err:raise RuntimeError('PREBUILD:'+','.join(err))
 smap,sym,issuers=identity(root);maps=[];filings=[];facts=[]
 for r in fin:
  hits=[]
  for a in r['symbol_aliases'].split('|'):hits+=sym.get(a.upper(),[])
  hits={x['canonical_listing_id']:x for x in hits};iids={smap[x['canonical_security_id']]['canonical_issuer_id'] for x in hits.values()}
  if len(iids)!=1:raise RuntimeError('IDENTITY:'+r['symbol'])
  iid=next(iter(iids));l=sorted(hits.values(),key=lambda x:x['canonical_listing_id'])[0];sid=l['canonical_security_id'];ev='SEC-'+r['accession_number']
  maps.append({'canonical_issuer_id':iid,'canonical_security_id':sid,'canonical_listing_id':l['canonical_listing_id'],'symbol':r['symbol'],'cik10':r['cik10'],'registrant_name':r['registrant_name'],'identity_status':'SEC_OFFICIAL_CIK_LINKED','evidence_id':ev,'data_grade':'DECISION_GRADE_OFFICIAL_SEC'})
  filings.append({'filing_id':'USFIL-'+rh('F',r['cik10'],r['accession_number'])[:24],'canonical_issuer_id':iid,'canonical_security_id':sid,'symbol':r['symbol'],'cik10':r['cik10'],'registrant_name':r['registrant_name'],'accession_number':r['accession_number'],'form':r['form'],'filing_date':r['filing_date'],'accepted_at':r['accepted_at'],'report_period':r['report_period'],'filing_index_url':r['filing_index_url'],'main_document_url':r['main_document_url'],'evidence_id':ev,'source_authority':'SEC_OFFICIAL','data_grade':'DECISION_GRADE_OFFICIAL_SEC','amendment_flag':False})
 byacc={r['accession_number']:r for r in filings}
 for r in fx:
  f=byacc[r['accession_number']];val=float(r['value']) if '.' in r['value'] else int(r['value']);facts.append({'fact_id':'USFACT-'+rh('X',r['cik10'],r['accession_number'],r['tag'],r['start_date'],r['end_date'],r['unit'],r['value'])[:24],**{k:f[k] for k in ('canonical_issuer_id','canonical_security_id','symbol','cik10','accession_number','form','filing_date','accepted_at','report_period','evidence_id')},'taxonomy':r['taxonomy'],'tag':r['tag'],'label':r['label'],'value':val,'unit':r['unit'],'start_date':r['start_date'],'end_date':r['end_date'],'period_type':'duration','fiscal_year':int(r['fiscal_year']),'fiscal_period':r['fiscal_period'],'source_url':r['source_url'],'source_authority':'SEC_OFFICIAL','data_grade':r['data_grade']})
 maps.sort(key=lambda x:x['canonical_issuer_id']);filings.sort(key=lambda x:x['accession_number']);facts.sort(key=lambda x:(x['cik10'],x['tag']));accepted={x['canonical_issuer_id'] for x in maps};queue=[{'canonical_issuer_id':x,'queue_reason':'SEC_OFFICIAL_EVIDENCE_NOT_YET_CAPTURED','required_execution_environment':'CHATGPT_WEB_OR_LOCAL_OR_SELF_HOSTED_OFFICIAL_RETRIEVAL','status':'PENDING'} for x in issuers if x not in accepted]
 n=c['storage_contract']['bucket_count'];years=range(2009,2027);shards=[];ie={};fe={};xe={}
 def add(entries,name,rows,domain,year=None,b=None):
  p=''.join(stable(x)+'\n' for x in rows).encode();entries[name]=p;d={'shard_id':name[:-6].replace('/','-'),'domain':domain,'row_count':len(rows),'payload_sha256':sha(p),'quality_status':'PASS'}
  if year is not None:d['year']=year
  if b is not None:d['bucket']=b
  shards.append(d)
 for i in range(n):
  b=f'{i:02X}';add(ie,f'ISSUER_CIK/{b}.jsonl',[x for x in maps if bh(x['canonical_issuer_id'],n)==b],'ISSUER_CIK',b=b)
 for y in years:
  for i in range(n):
   b=f'{i:02X}';add(fe,f'FILINGS/{y}/{b}.jsonl',[x for x in filings if int(x['filing_date'][:4])==y and bh(x['cik10'],n)==b],'FILINGS',y,b);add(xe,f'FACTS/{y}/{b}.jsonl',[x for x in facts if int(x['end_date'][:4])==y and bh(x['cik10'],n)==b],'FACTS',y,b)
 contract_sha=shaf(root/CONTRACT);evidence_sha=shaf(root/EVID/'FMDL6X2E_SEC_OFFICIAL_EVIDENCE.json');identity_sha=shaf(root/'outputs/fmdl6x2/current/identity/FMDL6X2B_MANIFEST.json');rid='FMDL6X2E_20260722_'+rh('R',contract_sha,evidence_sha,identity_sha)[:12];cand.mkdir(parents=True,exist_ok=True);(cand/'FMDL6X2E_ISSUER_CIK_SHARDS.zip').write_bytes(dzip(ie));(cand/'FMDL6X2E_FILINGS_SHARDS.zip').write_bytes(dzip(fe));(cand/'FMDL6X2E_FACTS_SHARDS.zip').write_bytes(dzip(xe));(cand/'FMDL6X2E_BACKFILL_QUEUE.jsonl.gz').write_bytes(dgzip(queue));write(cand/'FMDL6X2E_EVIDENCE_REGISTRY.json',meta)
 cov={'phase_id':PHASE,'release_id':rid,'universe_issuer_count':len(issuers),'initial_filing_issuer_count':len(maps),'initial_fact_issuer_count':len({x['canonical_issuer_id'] for x in facts}),'filing_count':len(filings),'fact_count':len(facts),'backfill_queue_count':len(queue),'full_universe_sec_store_claimed':False,'history_target_start_date':'2009-01-01','store_status':'PARTIAL_OFFICIAL_SEC_EVIDENCE_BASELINE_WITH_EXTERNAL_BACKFILL_QUEUE'};write(cand/'FMDL6X2E_COVERAGE_REPORT.json',cov)
 dupf=len(facts)-len({(x['cik10'],x['accession_number'],x['tag'],x['start_date'],x['end_date'],x['unit'],str(x['value'])) for x in facts});q={'phase_id':PHASE,'release_id':rid,'quality_status':'PASS','universe_expected':7419,'universe_accounted':len(maps)+len(queue),'initial_filings':len(filings),'initial_fact_issuers':cov['initial_fact_issuer_count'],'fact_count':len(facts),'duplicate_accessions':len(filings)-len({x['accession_number'] for x in filings}),'duplicate_fact_keys':dupf,'non_official_fact_rows':sum(x['data_grade']!='DECISION_GRADE_OFFICIAL_SEC' for x in facts),'unmapped_initial_evidence':0,'manifested_shard_count':len(shards),'expected_shard_count':2368,'full_universe_sec_store_claimed':False,'trade_authority':'NONE','zero_mutation_proof':c['zero_mutation_gate']};qe=[]
 if q['universe_accounted']!=7419:qe.append('UNIVERSE')
 if len(filings)<6 or cov['initial_fact_issuer_count']<3 or len(facts)<25:qe.append('COVERAGE')
 if q['duplicate_accessions'] or dupf or q['non_official_fact_rows']:qe.append('INTEGRITY')
 if len(shards)!=2368:qe.append('SHARDS')
 if qe:q['quality_status']='FAIL';q['errors']=qe
 write(cand/'FMDL6X2E_QUALITY_REPORT.json',q)
 if qe:raise RuntimeError('QUALITY:'+','.join(qe))
 write(cand/'FMDL6X2E_SOURCE_BINDING.json',{'phase_id':PHASE,'release_id':rid,'accepted_authority':'SEC_OFFICIAL','production_execution_environment':'CHATGPT_WEB_CONTROLLED_OFFICIAL_RETRIEVAL','github_hosted_direct_execution':'BLOCKED_BY_REPEATABLE_403','third_party_sec_proxy_used':False,'silent_source_substitution':False,'evidence_manifest_sha256':evidence_sha,'filings_csv_sha256':meta['files']['FMDL6X2E_FILINGS.csv']['sha256'],'facts_csv_sha256':meta['files']['FMDL6X2E_FACTS.csv']['sha256'],'identity_manifest_sha256':identity_sha,'hash_scope':meta['hash_scope']})
 dec={'phase_id':PHASE,'status':EXIT,'release_id':rid,'release_sequence':34,'accepted_at':at,'source_commit':commit,'input_release_id':'FMDL6X2D_20260722_632e61097490','next_gate':NEXT,'sec_store_status':cov['store_status'],'full_universe_sec_store_claimed':False,'filing_count':len(filings),'fact_count':len(facts),'backfill_queue_count':len(queue),'research_production_gate':'OPEN_FOR_FMDL6X2_DATA_PRODUCTION','brokerage_real_account_gate':'CLOSED_NO_CHANNEL','trade_authority':'NONE','zero_mutation_proof':c['zero_mutation_gate']};write(cand/'FMDL6X2E_DECISION.json',dec);files={p.name:{'bytes':p.stat().st_size,'sha256':shaf(p)} for p in sorted(cand.iterdir()) if p.is_file() and p.name!='FMDL6X2E_MANIFEST.json'};write(cand/'FMDL6X2E_MANIFEST.json',{'phase_id':PHASE,'release_id':rid,'release_sequence':34,'generated_at':at,'contract_sha256':contract_sha,'evidence_manifest_sha256':evidence_sha,'identity_manifest_sha256':identity_sha,'files':files,'shards':shards});return {'decision':dec,'quality':q,'coverage':cov,'contract_checks':checks}
def validate(root,cand,at,commit,out):
 r=cand.parent/(cand.name+'_replay');shutil.rmtree(r,ignore_errors=True);build(root,r,at,commit);l={p.name:shaf(p) for p in cand.iterdir() if p.is_file()};rr={p.name:shaf(p) for p in r.iterdir() if p.is_file()};e=[]
 if l!=rr:e.append('REPLAY')
 m=load(cand/'FMDL6X2E_MANIFEST.json')
 for n,x in m['files'].items():
  p=cand/n
  if not p.is_file() or p.stat().st_size!=x['bytes'] or shaf(p)!=x['sha256']:e.append('MANIFEST:'+n)
 d=load(cand/'FMDL6X2E_DECISION.json')
 if d['trade_authority']!='NONE':e.append('TRADE')
 o={'phase_id':PHASE,'status':'PASS' if not e else 'FAIL','captured_input_replay':'PASS' if l==rr else 'FAIL','errors':e,'release_id':d['release_id']};write(out,o)
 if e:raise RuntimeError(','.join(e))
 return o
def publish(root,cand,at,commit):
 c=load(root/CONTRACT);d=load(cand/'FMDL6X2E_DECISION.json');rid=d['release_id'];cur=root/c['storage_contract']['current_root'];rel=root/f'datasets/fmdl6x2/releases/{rid}/sec_filings_facts';norm=root/f'datasets/fmdl6x2/normalized/sec_filings_facts/{rid}';raw=root/f'datasets/fmdl6x2/raw/sec_official/2026-07-22/{rid}';arc=root/c['storage_contract']['archive_root']
 if rel.exists() and shaf(rel/'FMDL6X2E_MANIFEST.json')!=shaf(cand/'FMDL6X2E_MANIFEST.json'):raise RuntimeError('IMMUTABLE_COLLISION')
 if not rel.exists():shutil.copytree(cand,rel)
 if cur.exists():
  old=load(cur/'FMDL6X2E_DECISION.json');dst=arc/f"{old['release_id']}/sec_filings_facts";dst.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(cur,dst,dirs_exist_ok=True);shutil.rmtree(cur)
 shutil.copytree(cand,cur);shutil.copytree(cand,norm,dirs_exist_ok=True);raw.mkdir(parents=True,exist_ok=True)
 for n in ('FMDL6X2E_SEC_OFFICIAL_EVIDENCE.json','FMDL6X2E_FILINGS.csv','FMDL6X2E_FACTS.csv'):shutil.copy2(root/EVID/n,raw/n)
 p={**d,'published_at':at,'source_commit':commit,'manifest_sha256':shaf(cand/'FMDL6X2E_MANIFEST.json'),'current_path':str(cur.relative_to(root)),'release_path':str(rel.relative_to(root)),'normalized_path':str(norm.relative_to(root)),'raw_path':str(raw.relative_to(root))};write(root/c['storage_contract']['last_success'],p);write(root/c['storage_contract']['last_known_good'],{**p,'lkg_scope':'SEC_FILINGS_AND_FINANCIAL_FACTS_DOMAIN','lkg_reason':'LATEST_ACCEPTED_OFFICIAL_SEC_BASELINE'});return p
def main():
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='cmd',required=True)
 for x in ('validate-contract','build','validate-candidate','publish'):
  q=s.add_parser(x);q.add_argument('--repo-root',default='.')
  if x!='validate-contract':q.add_argument('--candidate',required=True)
  if x in ('build','validate-candidate'):q.add_argument('--accepted-at',required=True);q.add_argument('--source-commit',required=True)
  if x=='validate-candidate':q.add_argument('--acceptance',required=True)
  if x=='publish':q.add_argument('--published-at',required=True);q.add_argument('--source-commit',required=True)
 a=p.parse_args();root=Path(a.repo_root)
 if a.cmd=='validate-contract':
  _,c,e=contract_checks(root);print(json.dumps({'checks':c,'errors':e},indent=2));raise SystemExit(bool(e))
 if a.cmd=='build':o=build(root,Path(a.candidate),a.accepted_at,a.source_commit)
 elif a.cmd=='validate-candidate':o=validate(root,Path(a.candidate),a.accepted_at,a.source_commit,Path(a.acceptance))
 else:o=publish(root,Path(a.candidate),a.published_at,a.source_commit)
 print(json.dumps(o,indent=2,sort_keys=True))
if __name__=='__main__':main()
