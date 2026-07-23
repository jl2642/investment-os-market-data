from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from fmdl6x3d_sector_peer_benchmark import build_candidate, validate_candidate, validate_contract


class FMDL6X3DTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo = Path('.').resolve()
        cls.tmp = Path(tempfile.mkdtemp(prefix='fmdl6x3d_'))
        cls.candidate = cls.tmp / 'candidate'
        cls.acceptance = cls.tmp / 'acceptance.json'
        build_candidate(cls.repo, cls.candidate, '2026-07-23T00:00:00Z', 'TEST_SOURCE_COMMIT')
        cls.quality = json.loads((cls.candidate / 'FMDL6X3D_QUALITY_REPORT.json').read_text())
        cls.coverage = json.loads((cls.candidate / 'FMDL6X3D_COVERAGE_REPORT.json').read_text())
        cls.queues = json.loads((cls.candidate / 'FMDL6X3D_QUEUE_SUMMARY.json').read_text())['queue_counts']
        cls.decision = json.loads((cls.candidate / 'FMDL6X3D_DECISION.json').read_text())
        cls.source = json.loads((cls.candidate / 'FMDL6X3D_SOURCE_BINDING.json').read_text())

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp)

    def test_01_contract(self) -> None:
        checks, errors = validate_contract(self.repo)
        self.assertFalse(errors)
        self.assertIn('UPSTREAM_INPUTS', checks)

    def test_02_universe_accounting(self) -> None:
        self.assertEqual(self.quality['security_universe_actual'], 8785)
        self.assertEqual(self.quality['security_universe_expected'], 8785)

    def test_03_official_sic_boundary(self) -> None:
        self.assertEqual(self.quality['official_sic_evidence_count'], 6)
        self.assertEqual(self.coverage['official_sector_count'], 3)
        self.assertFalse(self.coverage['full_classification_completion_claimed'])

    def test_04_peer_boundary(self) -> None:
        self.assertEqual(self.quality['formal_peer_group_count'], 0)
        self.assertEqual(self.queues['PEER_GROUP_MINIMUM_SIZE_QUEUE'], 6)
        self.assertEqual(self.queues['SPECIAL_PROFILE_OVERRIDE_QUEUE'], 2)

    def test_05_benchmark_registry(self) -> None:
        registry = json.loads((self.candidate / 'FMDL6X3D_BENCHMARK_REGISTRY.json').read_text())
        self.assertEqual(len(registry['available_benchmarks']), 1)
        self.assertEqual(registry['available_benchmarks'][0]['symbol'], 'QQQ')
        self.assertEqual(registry['formal_benchmark_usage_status'], 'BLOCKED_DECISION_GRADE_AND_COVERAGE_PENDING')

    def test_06_relative_observations(self) -> None:
        self.assertEqual(self.quality['benchmark_relative_observation_count'], 15)
        self.assertEqual(self.quality['non_decision_benchmark_relative_rows'], 15)
        self.assertEqual(self.queues['BENCHMARK_DATA_GRADE_UPGRADE_QUEUE'], 1)

    def test_07_no_formal_ranks_or_scores(self) -> None:
        self.assertEqual(self.quality['sector_neutral_factor_count'], 0)
        self.assertEqual(self.quality['global_factor_score_count'], 0)
        self.assertEqual(self.decision['investment_os_candidate_pool_gate'], 'CLOSED_NOT_AUTHORIZED_IN_FMDL6X3D')

    def test_08_source_and_zero_fill(self) -> None:
        self.assertEqual(self.source['sic_authority'], 'SEC_OFFICIAL')
        self.assertEqual(self.source['benchmark_market_data_grade'], 'NON_DECISION_GRADE_FALLBACK')
        self.assertFalse(self.source['neutral_fill_used'])
        self.assertFalse(self.source['silent_source_substitution'])

    def test_09_shards_and_replay(self) -> None:
        self.assertEqual(self.quality['manifested_shard_count'], 320)
        with zipfile.ZipFile(self.candidate / 'FMDL6X3D_FRAMEWORK_SHARDS.zip') as archive:
            self.assertEqual(len(archive.namelist()), 320)
        result = validate_candidate(self.repo, self.candidate, '2026-07-23T00:00:00Z', 'TEST_SOURCE_COMMIT', self.acceptance)
        self.assertEqual(result['same_input_replay'], 'PASS')


if __name__ == '__main__':
    unittest.main()
