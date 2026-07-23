from __future__ import annotations
import json, tempfile, unittest, zipfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import fmdl6x3c_factor_engine as m


class FactorEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.tmp = tempfile.TemporaryDirectory()
        cls.candidate = Path(cls.tmp.name) / 'candidate'
        cls.result = m.build(cls.root, cls.candidate, '2026-07-22T18:00:00Z', 'test-source-commit')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_01_contract_is_frozen(self):
        contract = m.validate_contract(self.root)
        self.assertEqual(contract['trade_authority'], 'NONE')
        self.assertFalse(contract['factor_contract']['neutral_fill_allowed'])
        self.assertFalse(contract['factor_contract']['global_composite_allowed'])

    def test_02_percentile_direction(self):
        rows = [
            {'canonical_security_id': 'A', 'factor_name': 'X', 'factor_value': 1},
            {'canonical_security_id': 'B', 'factor_name': 'X', 'factor_value': 3},
        ]
        self.assertEqual(m.percentile_map(rows, higher=True)['X|B'], 1)
        self.assertEqual(m.percentile_map(rows, higher=False)['X|B'], 0)

    def test_03_quality_coverage(self):
        q = self.result['quality']
        self.assertEqual(q['quality_security_count'], 3)
        self.assertEqual(q['quality_observation_count'], 27)
        self.assertEqual(q['quality_composite_count'], 3)

    def test_04_market_and_risk_coverage(self):
        q = self.result['quality']
        self.assertEqual(q['market_source_security_count'], 64)
        self.assertGreaterEqual(q['market_security_count'], 63)
        self.assertGreaterEqual(q['market_factor_observation_count'], 300)
        self.assertGreaterEqual(q['risk_factor_observation_count'], 250)

    def test_05_blocked_layers_emit_nothing(self):
        q = self.result['quality']
        self.assertEqual(q['valuation_factor_observation_count'], 0)
        self.assertEqual(q['global_factor_score_count'], 0)
        self.assertEqual(q['neutral_fill_count'], 0)

    def test_06_no_future_leakage(self):
        q = self.result['quality']
        self.assertEqual(q['future_dated_financial_rows'], 0)
        self.assertEqual(q['future_dated_market_rows'], 0)

    def test_07_shards_and_queues(self):
        manifest = json.loads((self.candidate / 'FMDL6X3C_MANIFEST.json').read_text())
        self.assertEqual(len(manifest['shards']), 320)
        with zipfile.ZipFile(self.candidate / 'FMDL6X3C_REVIEW_QUEUES.zip') as z:
            self.assertEqual(len(z.namelist()), 5)

    def test_08_market_rows_remain_non_decision_grade(self):
        with zipfile.ZipFile(self.candidate / 'FMDL6X3C_FACTOR_SHARDS.zip') as z:
            rows = []
            for name in z.namelist():
                if name.startswith(('MARKET_FACTOR/', 'RISK_FACTOR/')):
                    rows += [json.loads(x) for x in z.read(name).decode().splitlines() if x]
        self.assertTrue(rows)
        self.assertTrue(all(r['data_grade'] == 'NON_DECISION_GRADE_FALLBACK' for r in rows))
        self.assertTrue(all(r['factor_usage'] == 'MARKET_SANDBOX_ONLY' for r in rows))

    def test_09_same_input_byte_replay(self):
        replay = Path(self.tmp.name) / 'candidate_replay_test'
        m.build(self.root, replay, '2026-07-22T18:00:00Z', 'test-source-commit')
        left = {p.name: m.sha_file(p) for p in self.candidate.iterdir() if p.is_file()}
        right = {p.name: m.sha_file(p) for p in replay.iterdir() if p.is_file()}
        self.assertEqual(left, right)


if __name__ == '__main__':
    unittest.main()
