from __future__ import annotations

import gzip
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from fmdl6x2b_candidate import build_candidate, load_input, publish, validate_candidate
from fmdl6x2b_classification import classify, enrich_identity
from fmdl6x2b_common import deterministic_gzip, deterministic_zip, load_json, sha256_file, validate_contract


def base_record(symbol: str, name: str, venue: str = 'XNAS', etf: bool = False, test: bool = False) -> dict:
    return {
        'active_listing_observation_key': f'{venue}|{symbol}', 'canonical_issuer_id': None,
        'canonical_listing_id': None, 'canonical_security_id': None, 'canonical_share_class_id': None,
        'channel_status': 'CHANNEL_ELIGIBILITY_PENDING', 'cqs_symbol': symbol,
        'effective_date_confidence': 'OBSERVATION_ONLY', 'etf_flag': etf, 'financial_status': None,
        'identity_resolution_status': 'PENDING_FMDL6X2B', 'instrument_type_preliminary': 'UNRESOLVED_EXCHANGE_LISTED_SECURITY',
        'listing_lifecycle_status': 'ACTIVE_LISTED_OBSERVED', 'market_category': None, 'nasdaq_symbol': symbol,
        'nextshares_flag': False, 'observation_date': '2026-07-22', 'official_security_name': name,
        'portfolio_status': 'PORTFOLIO_ADMISSION_NOT_AUTHORIZED',
        'provisional_security_record_id': 'USOBS-' + symbol, 'research_status': 'RESEARCH_REVIEW_REQUIRED',
        'round_lot_size': '100', 'row_disposition': 'INCLUDED', 'source_authority': 'NASDAQ_OFFICIAL',
        'source_exchange_code': 'Q' if venue == 'XNAS' else 'N', 'source_line_number': 2,
        'source_route_id': 'TEST_ROUTE', 'source_row_id': 'SNAP:' + symbol,
        'source_row_sha256': 'a' * 64, 'source_snapshot_id': 'SNAP', 'symbol': symbol,
        'test_issue': test, 'trade_authority': 'NONE', 'venue': venue,
    }


class IdentityClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix='fmdl6x2b-test-'))
        shutil.copytree(ROOT / 'config', cls.tmp / 'config')
        (cls.tmp / 'outputs/status').mkdir(parents=True)
        pointer = {
            'phase_id': 'FMDL-6X2-A', 'release_id': 'FMDL6X2A_20260722_3d3768bf5492',
            'status': 'FMDL6X2A_CURRENT_SECURITY_MASTER_PRODUCTION_ACCEPTED', 'release_sequence': 30,
            'next_gate': 'FMDL-6X2-B_ISSUER_IDENTITY_CLASSIFICATION_AND_REVIEW_QUEUES', 'trade_authority': 'NONE'
        }
        (cls.tmp / 'outputs/status/FMDL6X2A_LAST_SUCCESS.json').write_text(json.dumps(pointer), encoding='utf-8')
        current = cls.tmp / 'outputs/fmdl6x2/current/security_master'
        current.mkdir(parents=True)
        rows = [
            base_record('AAPL', 'Apple Inc. - Common Stock'),
            base_record('QQQ', 'Invesco QQQ Trust ETF', etf=True),
            base_record('BABA', 'Alibaba Group Holding Limited American Depositary Shares', venue='XNYS'),
            base_record('SPAC', 'Example Acquisition Corp. - Class A Ordinary Shares'),
            base_record('SPACW', 'Example Acquisition Corp. - Warrants'),
            base_record('SAME', 'Same Issuer Inc. - Common Stock', venue='XNAS'),
            base_record('SAME2', 'Same Issuer Inc. Common Stock', venue='XNYS'),
            base_record('ODD', 'Odd Listed Instrument'),
        ]
        entries = {'XNAS/00.jsonl': ''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows).encode('utf-8')}
        (current / 'FMDL6X2A_SECURITY_MASTER_SHARDS.zip').write_bytes(deterministic_zip(entries))
        quarantine = [{'symbol': 'MTEST', 'reason': 'UNKNOWN_EXCHANGE_CODE', 'source_exchange_code': 'M'}]
        (current / 'FMDL6X2A_QUARANTINE.jsonl.gz').write_bytes(deterministic_gzip(quarantine))
        decision = {'release_id': 'FMDL6X2A_20260722_3d3768bf5492', 'observation_date': '2026-07-22', 'included_security_records': len(rows), 'quarantined_rows': 1}
        for name, data in [
            ('FMDL6X2A_DECISION.json', decision), ('FMDL6X2A_MANIFEST.json', {'phase_id': 'FMDL-6X2-A', 'files': {}}),
            ('FMDL6X2A_QUALITY_REPORT.json', {'quality_status': 'PASS'})
        ]:
            (current / name).write_text(json.dumps(data, sort_keys=True), encoding='utf-8')
        cls.candidate = cls.tmp / 'outputs/fmdl6x2b/candidate'
        cls.result = build_candidate(cls.tmp, cls.candidate, '2026-07-22T12:00:00Z', 'TESTSHA')

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp)

    def test_01_contract_valid(self) -> None:
        _, errors = validate_contract(self.tmp)
        self.assertEqual(errors, [])

    def test_02_official_flags_and_explicit_types(self) -> None:
        self.assertEqual(classify(base_record('Q', 'Fund ETF', etf=True))['research_status'], 'REFERENCE_ONLY')
        self.assertEqual(classify(base_record('W', 'Issuer Warrants'))['instrument_type'], 'WARRANT')
        self.assertEqual(classify(base_record('U', 'Issuer Units, each consisting of one share and one-half warrant'))['instrument_type'], 'COMPOSITE_UNIT')
        self.assertEqual(classify(base_record('P', 'Issuer 6% Preferred Stock'))['research_status'], 'EXCLUDED')

    def test_03_no_fuzzy_issuer_merge(self) -> None:
        a = enrich_identity(base_record('A', 'Alpha Corp. Common Stock'))
        b = enrich_identity(base_record('B', 'Alpha Corporation Common Stock'))
        self.assertNotEqual(a['canonical_issuer_id'], b['canonical_issuer_id'])

    def test_04_exact_name_cross_market_group(self) -> None:
        summary = load_json(self.candidate / 'FMDL6X2B_CLASSIFICATION_SUMMARY.json')
        self.assertEqual(summary['cross_market_groups'], 1)

    def test_05_security_dedup_and_listing_preservation(self) -> None:
        summary = load_json(self.candidate / 'FMDL6X2B_CLASSIFICATION_SUMMARY.json')
        self.assertEqual(summary['input_security_records'], 8)
        self.assertEqual(summary['listing_records'], 8)
        self.assertEqual(summary['security_records'], 7)

    def test_06_review_queues_and_inherited_quarantine(self) -> None:
        summary = load_json(self.candidate / 'FMDL6X2B_CLASSIFICATION_SUMMARY.json')
        self.assertEqual(summary['review_queue_counts']['ADR_UNDERLYING_DEPOSITARY_AND_RATIO_QUEUE'], 1)
        self.assertEqual(summary['review_queue_counts']['INHERITED_SOURCE_SCOPE_QUARANTINE'], 1)
        self.assertGreaterEqual(summary['review_queue_counts']['SEC_OFFICIAL_IDENTITY_PENDING_QUEUE'], 4)

    def test_07_no_sec_cik_inference_and_no_trade_authority(self) -> None:
        lineage = []
        with gzip.open(self.candidate / 'FMDL6X2B_IDENTITY_LINEAGE.jsonl.gz', 'rt', encoding='utf-8') as handle:
            lineage = [json.loads(line) for line in handle]
        self.assertTrue(all(row['sec_cik10'] is None for row in lineage))
        self.assertTrue(all(row['trade_authority'] == 'NONE' for row in lineage))

    def test_08_same_input_replay(self) -> None:
        acceptance = self.tmp / 'outputs/fmdl6x2b/acceptance/acceptance.json'
        result = validate_candidate(self.tmp, self.candidate, '2026-07-22T12:00:00Z', 'TESTSHA', acceptance)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['same_input_replay'], 'PASS')

    def test_09_publish_parity_lkg_and_collision(self) -> None:
        pointer = publish(self.tmp, self.candidate, '2026-07-22T12:00:00Z', 'TESTSHA')
        current = self.tmp / pointer['current_path']
        release = self.tmp / pointer['release_path']
        self.assertEqual(sha256_file(current / 'FMDL6X2B_MANIFEST.json'), sha256_file(release / 'FMDL6X2B_MANIFEST.json'))
        lkg_path = self.tmp / 'outputs/status/FMDL6X2_IDENTITY_LKG.json'
        before = lkg_path.read_bytes()
        with self.assertRaises(RuntimeError):
            publish(self.tmp, self.candidate, '2026-07-22T12:00:01Z', 'TESTSHA')
        self.assertEqual(before, lkg_path.read_bytes())


if __name__ == '__main__':
    unittest.main()
