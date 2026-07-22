from __future__ import annotations
import json,shutil,tempfile,unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from fmdl6x2e_sec_store import build,contract_checks,dzip,evidence,load,publish,stable,validate
class T(unittest.TestCase):
 def setUp(self):
  self.t=Path(tempfile.mkdtemp())
  for n in ('config','scripts','evidence'):shutil.copytree(ROOT/n,self.t/n)
  p=self.t/'outputs/status/FMDL6X2D_LAST_SUCCESS.json';p.parent.mkdir(parents=True);p.write_text(json.dumps({'phase_id':'FMDL-6X2-D','release_id':'FMDL6X2D_20260722_632e61097490','release_sequence':33,'status':'FMDL6X2D_MARKET_HISTORY_CORPORATE_ACTIONS_AND_FX_ACCEPTED','next_gate':'FMDL-6X2-E_SEC_FILINGS_AND_FINANCIAL_FACTS_STORE','trade_authority':'NONE'}))
  ev=list(__import__('csv').DictReader(open(self.t/'evidence/fmdl6x2e/2026-07-22/FMDL6X2E_FILINGS.csv')));syms=[x['symbol'] for x in ev];sec=[];lst=[]
  for i in range(7419):
   iid=f'USISS-{i:024d}';sid=f'USSEC-{i:024d}';sym=syms[i] if i<len(syms) else f'T{i:04d}';sec.append({'canonical_issuer_id':iid,'canonical_security_id':sid});lst.append({'canonical_listing_id':f'USLST-{i:024d}','canonical_security_id':sid,'symbol':sym,'venue':'XNAS'})
  d=self.t/'outputs/fmdl6x2/current/identity';d.mkdir(parents=True);(d/'FMDL6X2B_IDENTITY_SHARDS.zip').write_bytes(dzip({'SECURITY/00.jsonl':''.join(stable(x)+'\n' for x in sec).encode(),'LISTING/XNAS/00.jsonl':''.join(stable(x)+'\n' for x in lst).encode()}));(d/'FMDL6X2B_MANIFEST.json').write_text('{}\n');self.c=self.t/'outputs/fmdl6x2e/candidate'
 def tearDown(self):shutil.rmtree(self.t)
 def test_01_contract(self):self.assertEqual(contract_checks(self.t)[2],[])
 def test_02_evidence(self):self.assertEqual(evidence(self.t)[3],[])
 def test_03_counts(self):
  r=build(self.t,self.c,'2026-07-22T15:00:00Z','TEST');self.assertEqual((r['coverage']['filing_count'],r['coverage']['fact_count'],r['coverage']['backfill_queue_count']),(6,33,7413))
 def test_04_quality(self):self.assertEqual(build(self.t,self.c,'2026-07-22T15:00:00Z','TEST')['quality']['quality_status'],'PASS')
 def test_05_shards(self):self.assertEqual(build(self.t,self.c,'2026-07-22T15:00:00Z','TEST')['quality']['manifested_shard_count'],2368)
 def test_06_replay(self):
  build(self.t,self.c,'2026-07-22T15:00:00Z','TEST');self.assertEqual(validate(self.t,self.c,'2026-07-22T15:00:00Z','TEST',self.t/'outputs/fmdl6x2e/acceptance/a.json')['status'],'PASS')
 def test_07_hash_gate(self):
  p=self.t/'evidence/fmdl6x2e/2026-07-22/FMDL6X2E_SEC_OFFICIAL_EVIDENCE.json';v=load(p);v['files']['FMDL6X2E_FACTS.csv']['sha256']='bad';p.write_text(json.dumps(v));self.assertTrue(evidence(self.t)[3])
 def test_08_publish(self):
  build(self.t,self.c,'2026-07-22T15:00:00Z','TEST');p=publish(self.t,self.c,'2026-07-22T15:00:00Z','TEST');self.assertTrue((self.t/p['current_path']/'FMDL6X2E_MANIFEST.json').is_file())
 def test_09_authority(self):
  r=build(self.t,self.c,'2026-07-22T15:00:00Z','TEST');self.assertEqual(r['decision']['trade_authority'],'NONE');self.assertEqual(set(r['decision']['zero_mutation_proof'].values()),{0})
if __name__=='__main__':unittest.main()
