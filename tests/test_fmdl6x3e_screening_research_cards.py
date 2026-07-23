from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from fmdl6x3e_screening_research_cards import build_candidate, validate_candidate, validate_contract


class FMDL6X3ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo = Path('.').resolve()
        cls.tmp = Path(tempfile.mkdtemp(prefix='fmdl6x3e_'))
        cls.candidate = cls.tmp / 'candidate'
        cls.acceptance = cls.tmp / 'acceptance.json'
        build_candidate(cls.repo, cls.candidate, '2026-07-23T02:00:00Z', 'TEST_SOURCE_COMMIT')
        cls.quality = json.loads((cls.candidate / 'FMDL6X3E_QUALITY_REPORT.json').read_text())
        cls.coverage = json.loads((cls.candidate / 'FMDL6X3E_COVERAGE_REPORT.json').read_text())
        cls.funnel = json.loads((cls.candidate / 'FMDL6X3E_SCREENING_FUNNEL_SUMMARY.json').read_text())
        cls.pool = json.loads((cls.candidate / 'FMDL6X3E_US_BENCHMARK_POOL.json').read_text())
        cls.queues = json.loads((cls.candidate / 'FMDL6X3E_QUEUE_SUMMARY.json').read_text())['queue_counts']
        cls.decision = json.loads((cls.candidate / 'FMDL6X3E_DECISION.json').read_text())
        cls.source = json.loads((cls.candidate / 'FMDL6X3E_SOURCE_BINDING.json').read_text())

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp)

    def test_01_contract(self) -> None:
        checks, errors = validate_contract(self.repo)
        self.assertFalse(errors)
        self.assertIn('POOL_CANDIDATE_SEPARATION', checks)

    def test_02_universe_and_cards(self) -> None:
        self.assertEqual(self.quality['security_universe_actual'], 8785)
        self.assertEqual(self.quality['research_card_count'], 8785)

    def test_03_disposition_accounting(self) -> None:
        self.assertEqual(self.quality['disposition_counts'], {
            'BENCHMARK_REFERENCE': 1,
            'CORE_RESEARCH_SANDBOX': 3,
            'DATA_BACKFILL_PENDING': 5428,
            'EXCLUDED': 1273,
            'INSTRUMENT_REVIEW_REQUIRED': 437,
            'MARKET_RISK_SANDBOX_OBSERVATION': 39,
            'OFFICIAL_FILING_WATCH': 3,
            'REFERENCE_ONLY': 1601,
        })

    def test_04_benchmark_pool(self) -> None:
        self.assertEqual(self.pool['member_count'], 7)
        self.assertEqual({row['symbol'] for row in self.pool['members']}, {'AAPL', 'MSFT', 'NVDA', 'JPM', 'BRK.B', 'XOM', 'QQQ'})
        self.assertEqual(self.pool['formal_candidate_pool_member_count'], 0)
        self.assertEqual(self.pool['investment_recommendation_count'], 0)

    def test_05_funnel_boundaries(self) -> None:
        gates = {row['gate_name']: row for row in self.funnel['funnel_gates']}
        self.assertEqual(gates['MARKET_RISK_SANDBOX_READY']['security_count'], 63)
        self.assertEqual(gates['QUARTERLY_QUALITY_SANDBOX_READY']['security_count'], 3)
        self.assertEqual(gates['FORMAL_VALUATION_READY']['security_count'], 0)
        self.assertEqual(gates['FORMAL_PEER_READY']['security_count'], 0)
        self.assertEqual(gates['INVESTMENT_OS_GRADUATION_READY']['security_count'], 0)

    def test_06_queues(self) -> None:
        self.assertEqual(self.queues['RESEARCH_CARD_DATA_BACKFILL_QUEUE'], 5428)
        self.assertEqual(self.queues['DECISION_GRADE_MARKET_UPGRADE_QUEUE'], 63)
        self.assertEqual(self.queues['FORMAL_CANDIDATE_PROMOTION_BLOCK_QUEUE'], 6)
        self.assertEqual(self.queues['US_BENCHMARK_POOL_REVIEW_QUEUE'], 7)

    def test_07_no_rank_or_promotion(self) -> None:
        self.assertEqual(self.quality['formal_candidate_promotion_count'], 0)
        self.assertEqual(self.quality['global_rank_count'], 0)
        self.assertEqual(self.decision['investment_os_candidate_pool_gate'], 'CLOSED_NOT_AUTHORIZED_IN_FMDL6X3E')

    def test_08_source_boundary(self) -> None:
        self.assertEqual(self.source['market_source_grade'], 'NON_DECISION_GRADE_FALLBACK')
        self.assertFalse(self.source['benchmark_pool_is_candidate_pool'])
        self.assertFalse(self.source['neutral_fill_used'])
        self.assertFalse(self.source['silent_source_substitution'])

    def test_09_shards_and_replay(self) -> None:
        self.assertEqual(self.quality['manifested_shard_count'], 256)
        with zipfile.ZipFile(self.candidate / 'FMDL6X3E_RESEARCH_SHARDS.zip') as archive:
            self.assertEqual(len(archive.namelist()), 256)
        result = validate_candidate(self.repo, self.candidate, '2026-07-23T02:00:00Z', 'TEST_SOURCE_COMMIT', self.acceptance)
        self.assertEqual(result['same_input_replay'], 'PASS')


if __name__ == '__main__':
    unittest.main()
