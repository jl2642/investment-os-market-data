from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "fmdl6x2a_current_security_master.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("fmdl6x2a", MODULE_PATH)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)

NASDAQ = """Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N
QQQ|Invesco QQQ Trust ETF|Q|N|N|100|Y|N
ZTEST|NASDAQ TEST ISSUE|S|Y|N|100|N|N
File Creation Time: 0722202617:00|||||||
"""

OTHER = """ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
IBM|International Business Machines Corporation Common Stock|N|IBM|N|100|N|IBM
BAM|Brookfield Asset Management Inc Class A Limited Voting Shares|A|BAM|N|100|N|BAM
SPY|SPDR S&P 500 ETF Trust|P|SPY|Y|100|N|SPY
ZXYZ|Cboe Example|Z|ZXYZ|N|100|N|ZXYZ
File Creation Time: 0722202617:00|||||||
"""

class CurrentSecurityMasterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        source_root = Path(__file__).resolve().parents[1]
        for rel in [
            "config/fmdl6x2a_current_security_master_contract.json",
            "outputs/status/FMDL6X1_LAST_SUCCESS.json",
            "outputs/fmdl6x1/current/FMDL6X2_BUILD_CONTRACT.json",
            "outputs/fmdl6x1/current/FMDL6X2_SOURCE_EXECUTION_REGISTRY.json",
            "outputs/fmdl6x1/current/FMDL6X2_DOMAIN_SCHEMA_REGISTRY.json",
            "outputs/fmdl6x1/current/FMDL6X2_SHARD_PLAN.json",
            "outputs/fmdl6x1/current/FMDL6X2_QUALITY_GATE_REGISTRY.json",
        ]:
            dst = self.tmp / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_root / rel, dst)
        self.raw = self.tmp / "raw"
        self.raw.mkdir()
        self._write_raw("NASDAQ_TRADER_NASDAQLISTED", NASDAQ)
        self._write_raw("NASDAQ_TRADER_OTHERLISTED", OTHER)
        mod.write_json(self.raw / "SOURCE_SNAPSHOTS.json", {
            "phase_id":mod.PHASE_ID,
            "captured_at":"2026-07-22T12:00:00Z",
            "snapshots":[
                mod.load_json(self.raw/"nasdaq_trader_nasdaqlisted.txt.meta.json"),
                mod.load_json(self.raw/"nasdaq_trader_otherlisted.txt.meta.json"),
            ],
        })
        self.candidate = self.tmp / "candidate"
        self.accepted_at = "2026-07-22T12:00:00Z"
        self.commit = "a"*40

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _write_raw(self, route_id, text):
        filename = route_id.lower() + ".txt"
        payload = text.encode()
        (self.raw/filename).write_bytes(payload)
        mod.write_json(self.raw/(filename+".meta.json"), {
            "route_id":route_id,"url":"https://official.example/"+filename,
            "source_authority":"NASDAQ_OFFICIAL","retrieved_at":"2026-07-22T12:00:00Z",
            "http_status":200,"bytes":len(payload),"payload_sha256":mod.sha256_bytes(payload),
            "raw_filename":filename,"snapshot_id":f"{route_id}_20260722_{mod.sha256_bytes(payload)[:12]}",
        })

    def test_contract_passes(self):
        _, errors = mod.validate_contract(self.tmp)
        self.assertEqual(errors, [])

    def test_build_accounts_all_rows_and_all_shards(self):
        result = mod.build_candidate(self.tmp, self.raw, self.candidate, self.accepted_at, self.commit)
        self.assertEqual(result["quality_status"], "PASS")
        quality = mod.load_json(self.candidate/"FMDL6X2A_QUALITY_REPORT.json")
        self.assertEqual(quality["row_accounting_percent"], 100)
        self.assertEqual(quality["included_by_venue"], {"XASE":1,"XNAS":3,"XNYS":1})
        self.assertEqual(quality["excluded_rows"], 2)
        self.assertEqual(quality["quarantined_rows"], 0)
        self.assertEqual(quality["manifested_shard_count"], 192)

    def test_preliminary_statuses_are_conservative(self):
        mod.build_candidate(self.tmp, self.raw, self.candidate, self.accepted_at, self.commit)
        import zipfile
        records=[]
        with zipfile.ZipFile(self.candidate/"FMDL6X2A_SECURITY_MASTER_SHARDS.zip") as z:
            for name in z.namelist():
                records.extend(json.loads(line) for line in z.read(name).decode().splitlines() if line)
        by_symbol={r["symbol"]:r for r in records}
        self.assertEqual(by_symbol["QQQ"]["research_status"], "REFERENCE_ONLY")
        self.assertEqual(by_symbol["ZTEST"]["research_status"], "EXCLUDED")
        self.assertEqual(by_symbol["AAPL"]["research_status"], "RESEARCH_REVIEW_REQUIRED")
        self.assertIsNone(by_symbol["AAPL"]["canonical_security_id"])
        self.assertEqual(by_symbol["AAPL"]["identity_resolution_status"], "PENDING_FMDL6X2B")

    def test_unknown_exchange_is_quarantined(self):
        bad = OTHER.replace("ZXYZ|Cboe Example|Z|", "UXYZ|Unknown Example|U|")
        self._write_raw("NASDAQ_TRADER_OTHERLISTED", bad)
        data=mod.load_json(self.raw/"SOURCE_SNAPSHOTS.json")
        data["snapshots"][1]=mod.load_json(self.raw/"nasdaq_trader_otherlisted.txt.meta.json")
        mod.write_json(self.raw/"SOURCE_SNAPSHOTS.json",data)
        result=mod.build_candidate(self.tmp,self.raw,self.candidate,self.accepted_at,self.commit)
        self.assertEqual(result["quality"]["quarantined_rows"],1)
        self.assertEqual(result["quality"]["excluded_rows"],1)

    def test_duplicate_listing_is_quarantined_not_silently_dropped(self):
        dup = NASDAQ.replace("File Creation Time:", "AAPL|Apple Inc. Duplicate|Q|N|N|100|N|N\nFile Creation Time:")
        self._write_raw("NASDAQ_TRADER_NASDAQLISTED", dup)
        data=mod.load_json(self.raw/"SOURCE_SNAPSHOTS.json")
        data["snapshots"][0]=mod.load_json(self.raw/"nasdaq_trader_nasdaqlisted.txt.meta.json")
        mod.write_json(self.raw/"SOURCE_SNAPSHOTS.json",data)
        result=mod.build_candidate(self.tmp,self.raw,self.candidate,self.accepted_at,self.commit)
        self.assertEqual(result["quality"]["quarantined_rows"],2)
        self.assertEqual(result["quality"]["row_accounting_percent"],100)

    def test_header_drift_fails_build(self):
        bad=NASDAQ.replace("Security Name","Bad Name",1)
        self._write_raw("NASDAQ_TRADER_NASDAQLISTED",bad)
        data=mod.load_json(self.raw/"SOURCE_SNAPSHOTS.json")
        data["snapshots"][0]=mod.load_json(self.raw/"nasdaq_trader_nasdaqlisted.txt.meta.json")
        mod.write_json(self.raw/"SOURCE_SNAPSHOTS.json",data)
        with self.assertRaises(ValueError):
            mod.build_candidate(self.tmp,self.raw,self.candidate,self.accepted_at,self.commit)

    def test_candidate_validation_and_replay(self):
        mod.build_candidate(self.tmp,self.raw,self.candidate,self.accepted_at,self.commit)
        acceptance=self.tmp/"acceptance.json"
        _, errors=mod.validate_candidate(self.tmp,self.raw,self.candidate,self.accepted_at,self.commit,acceptance)
        self.assertEqual(errors,[])
        self.assertEqual(mod.load_json(acceptance)["status"],"PASS")

    def test_publish_creates_current_release_and_pointers(self):
        mod.build_candidate(self.tmp,self.raw,self.candidate,self.accepted_at,self.commit)
        pointer=mod.publish(self.tmp,self.candidate,self.accepted_at,self.commit)
        current=self.tmp/pointer["current_path"]
        release=self.tmp/pointer["release_path"]
        self.assertEqual(mod.compare_directories(current,release),[])
        self.assertTrue((self.tmp/"outputs/status/FMDL6X2A_LAST_SUCCESS.json").is_file())
        self.assertTrue((self.tmp/"outputs/status/FMDL6X2_SECURITY_MASTER_LKG.json").is_file())

    def test_failure_does_not_mutate_existing_current_or_lkg(self):
        current=self.tmp/"outputs/fmdl6x2/current/security_master"
        current.mkdir(parents=True)
        (current/"sentinel.txt").write_text("LKG")
        lkg=self.tmp/"outputs/status/FMDL6X2_SECURITY_MASTER_LKG.json"
        lkg.write_text('{"sentinel":"LKG"}')
        bad=NASDAQ.replace("Security Name","Broken",1)
        self._write_raw("NASDAQ_TRADER_NASDAQLISTED",bad)
        before_current=(current/"sentinel.txt").read_bytes()
        before_lkg=lkg.read_bytes()
        with self.assertRaises(ValueError):
            mod.build_candidate(self.tmp,self.raw,self.candidate,self.accepted_at,self.commit)
        self.assertEqual((current/"sentinel.txt").read_bytes(),before_current)
        self.assertEqual(lkg.read_bytes(),before_lkg)

if __name__ == "__main__":
    unittest.main()
