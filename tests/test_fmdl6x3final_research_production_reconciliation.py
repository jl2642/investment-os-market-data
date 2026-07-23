from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from fmdl6x3final_research_production_reconciliation import (
    build_candidate,
    validate_candidate,
    validate_contract,
)


class FMDL6X3FinalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo = Path('.').resolve()
        cls.tmp = Path(tempfile.mkdtemp(prefix='fmdl6x3final_'))
        cls.candidate = cls.tmp / 'candidate'
        cls.acceptance = cls.tmp / 'acceptance.json'
        build_candidate(cls.repo, cls.candidate, '2026-07-23T00:00:00Z', 'TEST_SOURCE_COMMIT')
        cls.quality = json.loads((cls.candidate / 'FMDL6X3FINAL_QUALITY_REPORT.json').read_text())
        cls.coverage = json.loads((cls.candidate / 'FMDL6X3FINAL_COVERAGE_BOUNDARY.json').read_text())
        cls.decision = json.loads((cls.candidate / 'FMDL6X3FINAL_DECISION.json').read_text())
        cls.registry = json.loads((cls.candidate / 'FMDL6X3FINAL_DOMAIN_REGISTRY.json').read_text())
        cls.screening = json.loads((cls.candidate / 'FMDL6X3FINAL_SCREENING_RECONCILIATION.json').read_text())
        cls.handoff = json.loads((cls.candidate / 'FMDL6X3FINAL_FMDL6X4A_HANDOFF.json').read_text())

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp)

    def test_01_contract_and_release_sequence(self) -> None:
        checks, errors = validate_contract(self.repo)
        self.assertFalse(errors)
        self.assertIn('STRICT_RELEASE_SEQUENCE', checks)
        self.assertEqual([row['release_sequence'] for row in self.registry['domains']], [36, 37, 38, 39, 40])

    def test_02_domain_current_release_and_lkg(self) -> None:
        self.assertEqual(self.registry['domain_count'], 5)
        for row in self.registry['domains']:
            self.assertTrue(row['current_release_manifest_parity'])
            self.assertTrue(row['current_release_decision_parity'])
            self.assertTrue(row['last_success_manifest_binding'])
            self.assertTrue(row['lkg_binding'])
            self.assertEqual(row['quality_status'], 'PASS')

    def test_03_security_and_issuer_reconciliation(self) -> None:
        self.assertEqual(self.coverage['security_universe_count'], 8785)
        self.assertEqual(self.coverage['issuer_universe_count'], 7419)
        self.assertEqual(self.coverage['research_card_count'], 8785)

    def test_04_financial_quality_and_classification_identity(self) -> None:
        self.assertEqual(self.coverage['quarterly_financial_security_count'], 3)
        self.assertEqual(self.coverage['quality_sandbox_security_count'], 3)
        self.assertEqual(self.coverage['official_sic_security_count'], 6)
        self.assertEqual(len(self.screening['core_research_security_ids']), 3)
        self.assertEqual(len(self.screening['official_filing_watch_security_ids']), 3)
        self.assertEqual(set(self.screening['official_sic_security_ids']), set(self.screening['core_research_security_ids']) | set(self.screening['official_filing_watch_security_ids']))

    def test_05_market_valuation_peer_boundaries(self) -> None:
        self.assertEqual(self.coverage['market_risk_sandbox_security_count'], 63)
        self.assertEqual(self.coverage['valuation_ready_security_count'], 0)
        self.assertEqual(self.coverage['formal_peer_group_count'], 0)
        self.assertEqual(self.coverage['global_rank_count'], 0)

    def test_06_benchmark_pool_is_not_candidate_pool(self) -> None:
        self.assertEqual(self.coverage['benchmark_pool_member_count'], 7)
        self.assertEqual(len(self.screening['benchmark_pool_security_ids']), 7)
        self.assertEqual(self.coverage['formal_candidate_promotion_count'], 0)
        self.assertFalse(self.handoff['candidate_pool_authorized'])

    def test_07_operational_handoff(self) -> None:
        self.assertTrue(self.coverage['fmdl6x3_architecture_operationally_complete'])
        self.assertFalse(self.coverage['global_full_data_completion_claimed'])
        self.assertFalse(self.coverage['formal_investment_ranking_claimed'])
        self.assertEqual(self.handoff['next_gate'], 'FMDL-6X4-A_PUBLIC_EQUITY_INVESTING_ADAPTER_AND_CONTRACT_MAPPING')
        self.assertEqual(self.decision['fmdl6x4a_gate'], 'OPEN_ADAPTER_AND_CONTRACT_MAPPING_ONLY')

    def test_08_zero_mutation_and_authority(self) -> None:
        self.assertEqual(self.quality['formal_candidate_promotion_count'], 0)
        self.assertEqual(self.quality['research_recommendation_count'], 0)
        self.assertEqual(self.decision['trade_authority'], 'NONE')
        self.assertEqual(self.decision['zero_mutation_proof'], {
            'candidate_pool_mutations': 0,
            'simulation_mutations': 0,
            'real_account_mutations': 0,
            'orders': 0,
        })

    def test_09_shards_and_same_input_replay(self) -> None:
        self.assertEqual(self.quality['manifested_shard_count'], 128)
        with zipfile.ZipFile(self.candidate / 'FMDL6X3FINAL_RECONCILIATION_SHARDS.zip') as archive:
            self.assertEqual(len(archive.namelist()), 128)
        result = validate_candidate(self.repo, self.candidate, '2026-07-23T00:00:00Z', 'TEST_SOURCE_COMMIT', self.acceptance)
        self.assertEqual(result['same_input_replay'], 'PASS')


if __name__ == '__main__':
    unittest.main()
