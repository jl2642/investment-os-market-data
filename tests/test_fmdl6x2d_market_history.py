from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
import zipfile
from datetime import date, timedelta
from pathlib import Path

from fmdl6x2d_candidate import build_candidate, build_fx, load_security_universe, publish, reconcile_market, select_cohort, validate_candidate
from fmdl6x2d_common import deterministic_zip, load_json, stable_json, validate_contract, write_json

ROOT=Path(__file__).resolve().parents[1]


def yahoo_payload(symbol: str, close_delta: float=0.0) -> bytes:
    value={"chart":{"result":[{"meta":{"currency":"USD","symbol":symbol,"exchangeTimezoneName":"America/New_York"},"timestamp":[1577971800,1578058200],"indicators":{"quote":[{"open":[10.0,11.0],"high":[12.0,13.0],"low":[9.0,10.0],"close":[11.0,12.0+close_delta],"volume":[100,120]}]},"events":{"dividends":{"1577971800":{"date":1577971800,"amount":0.1}},"splits":{}}}],"error":None}}
    return json.dumps(value,separators=(',',':')).encode()


def ecb_history_zip() -> bytes:
    rows=['Date,USD,CNY,HKD']
    start=date(2010,1,1)
    for i in range(3105):
        d=(start+timedelta(days=i)).isoformat()
        rows.append(f"{d},{1.1+i*0.00001:.6f},{7.7+i*0.00001:.6f},{8.5+i*0.00001:.6f}")
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('eurofxref-hist.csv','\n'.join(rows)+'\n')
    return out.getvalue()


class MarketHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp=Path(tempfile.mkdtemp())
        for name in ('config','scripts'):
            shutil.copytree(ROOT/name,self.tmp/name)
        pointer={"phase_id":"FMDL-6X2-C","release_id":"FMDL6X2C_20260722_e55a579723f1","release_sequence":32,"status":"FMDL6X2C_HISTORICAL_LISTING_AND_LIFECYCLE_BACKFILL_ACCEPTED","next_gate":"FMDL-6X2-D_MARKET_HISTORY_CORPORATE_ACTIONS_AND_FX_STORE","trade_authority":"NONE"}
        write_json(self.tmp/'outputs/status/FMDL6X2C_LAST_SUCCESS.json',pointer)
        identity=self.tmp/'outputs/fmdl6x2/current/identity'; identity.mkdir(parents=True)
        securities=[]; listings=[]
        mandatory=['AAPL','MSFT','NVDA','JPM','XOM','BRK.B','SPY','QQQ']
        for i in range(8785):
            sid=f'USSEC-{i:024d}'; sym=mandatory[i] if i<len(mandatory) else f'T{i:04d}'
            securities.append({'canonical_security_id':sid,'canonical_issuer_id':f'USISS-{i:024d}','instrument_type':'COMMON_EQUITY','research_status':'RESEARCH_REVIEW_REQUIRED','test_issue':False,'symbols':[sym],'venues':['XNAS']})
            listings.append({'canonical_listing_id':f'USLST-{i:024d}','canonical_security_id':sid,'symbol':sym,'venue':'XNAS'})
        entries={'SECURITY/00.jsonl':(''.join(stable_json(x)+'\n' for x in securities)).encode(),'LISTING/XNAS/00.jsonl':(''.join(stable_json(x)+'\n' for x in listings)).encode()}
        (identity/'FMDL6X2B_IDENTITY_SHARDS.zip').write_bytes(deterministic_zip(entries))
        write_json(identity/'FMDL6X2B_MANIFEST.json',{'release_id':'FMDL6X2B_20260722_9159b4ed7f17'})
        self.securities,self.listings=load_security_universe(self.tmp)
        self.contract=load_json(self.tmp/'config/fmdl6x2d_market_history_contract.json')
        self.cohort,self.queued=select_cohort(self.securities,self.listings,self.contract)
        self.raw=self.tmp/'outputs/fmdl6x2d/raw'; self.raw.mkdir(parents=True)
        payloads={}
        observations=[]
        for row in self.cohort:
            sid=row['canonical_security_id']; sym=row['selected_symbol']
            for route in ('YAHOO_QUERY1_CHART','YAHOO_QUERY2_CHART'):
                payloads[f'market/{sid}/{route}.json']=yahoo_payload(sym)
                observations.append({'canonical_security_id':sid,'route_id':route,'success':True,'http_status':200})
        payloads['fx/ECB_EUROFXREF_HIST.zip']=ecb_history_zip()
        observations.append({'route_id':'ECB_EUROFXREF_HIST_ZIP','success':True,'http_status':200})
        payloads['fx/FRANKFURTER_USD_CNY_HKD.json']=b'{"base":"USD","rates":{"CNY":7.0,"HKD":7.8}}'
        (self.raw/'FMDL6X2D_RAW_PAYLOADS.zip').write_bytes(deterministic_zip(payloads))
        write_json(self.raw/'FMDL6X2D_ROUTE_OBSERVATIONS.json',{'phase_id':'FMDL-6X2-D','route_observations':observations})
        self.candidate=self.tmp/'outputs/fmdl6x2d/candidate'

    def tearDown(self) -> None: shutil.rmtree(self.tmp)

    def test_01_contract(self):
        _,errors=validate_contract(self.tmp); self.assertEqual(errors,[])

    def test_02_cohort_and_accounting(self):
        self.assertEqual(len(self.cohort),64); self.assertEqual(len(self.queued),8721); self.assertTrue({'AAPL','MSFT','SPY'} <= {x['selected_symbol'] for x in self.cohort})

    def test_03_dual_route_reconciliation(self):
        with zipfile.ZipFile(self.raw/'FMDL6X2D_RAW_PAYLOADS.zip') as archive: entries={n:archive.read(n) for n in archive.namelist()}
        bars,events,accepted,quarantine=reconcile_market(self.cohort,entries,load_json(self.raw/'FMDL6X2D_ROUTE_OBSERVATIONS.json'))
        self.assertEqual(len(accepted),64); self.assertEqual(len(quarantine),0); self.assertEqual(len(bars),128); self.assertEqual(len(events),64)

    def test_04_divergence_quarantine(self):
        with zipfile.ZipFile(self.raw/'FMDL6X2D_RAW_PAYLOADS.zip') as archive: entries={n:archive.read(n) for n in archive.namelist()}
        sec=self.cohort[0]['canonical_security_id']; entries[f'market/{sec}/YAHOO_QUERY2_CHART.json']=yahoo_payload('BAD',1.0)
        _,_,accepted,quarantine=reconcile_market(self.cohort,entries,load_json(self.raw/'FMDL6X2D_ROUTE_OBSERVATIONS.json'))
        self.assertEqual(len(quarantine),1); self.assertEqual(len(accepted),63)

    def test_05_fx_cross_rates(self):
        with zipfile.ZipFile(self.raw/'FMDL6X2D_RAW_PAYLOADS.zip') as archive: entries={n:archive.read(n) for n in archive.namelist()}
        rows,support=build_fx(entries); self.assertGreater(len(rows),6000); self.assertEqual({r['pair'] for r in rows},{'USD_CNY','USD_HKD'}); self.assertTrue(support['route_present'])

    def test_06_build_quality_and_grade(self):
        result=build_candidate(self.tmp,self.raw,self.candidate,'2026-07-22T14:00:00Z','TESTSHA')
        self.assertEqual(result['quality']['quality_status'],'PASS'); self.assertFalse(result['coverage']['full_universe_market_history_claimed']); self.assertEqual(result['quality']['accepted_dual_route_securities'],64); self.assertEqual(result['quality']['ecb_official_archives_observed'],1); self.assertEqual(result['quality']['ecb_official_archive_failures'],0)

    def test_07_captured_input_replay(self):
        build_candidate(self.tmp,self.raw,self.candidate,'2026-07-22T14:00:00Z','TESTSHA')
        result=validate_candidate(self.tmp,self.raw,self.candidate,'2026-07-22T14:00:00Z','TESTSHA',self.tmp/'outputs/fmdl6x2d/acceptance/a.json')
        self.assertEqual(result['status'],'PASS')

    def test_08_publish_and_lkg(self):
        build_candidate(self.tmp,self.raw,self.candidate,'2026-07-22T14:00:00Z','TESTSHA')
        pointer=publish(self.tmp,self.raw,self.candidate,'2026-07-22T14:00:00Z','TESTSHA')
        self.assertTrue((self.tmp/pointer['current_path']/'FMDL6X2D_MANIFEST.json').is_file()); self.assertTrue((self.tmp/'outputs/status/FMDL6X2_MARKET_REFERENCE_LKG.json').is_file())

    def test_09_no_investment_authority(self):
        result=build_candidate(self.tmp,self.raw,self.candidate,'2026-07-22T14:00:00Z','TESTSHA')
        self.assertEqual(result['decision']['trade_authority'],'NONE'); self.assertEqual(set(result['decision']['zero_mutation_proof'].values()),{0})

if __name__=='__main__': unittest.main()
