from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from fmdl6x4a_public_equity_investing_adapter import build_candidate, validate_candidate, validate_contract


class FMDL6X4ATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo = Path('.').resolve()
        cls.tmp = Path(tempfile.mkdtemp(prefix='fmdl6x4a_'))
        cls.candidate = cls.tmp / 'candidate'
        cls.acceptance = cls.tmp / 'acceptance.json'
        build_candidate(cls.repo, cls.candidate, '2026-07-23T00:00:00Z', 'TEST_SOURCE_COMMIT')
        cls.quality = json.loads((cls.candidate / 'FMDL6X4A_QUALITY_REPORT.json').read_text())
        cls.mapping = json.loads((cls.candidate / 'FMDL6X4A_MAPPING_SUMMARY.json').read_text())
        cls.payload = json.loads((cls.candidate / 'FMDL6X4A_ADAPTER_PAYLOAD_SUMMARY.json').read_text())
        cls.queues = json.loads((cls.candidate / 'FMDL6X4A_QUEUE_SUMMARY.json').read_text())['queue_counts']
        cls.source = json.loads((cls.candidate / 'FMDL6X4A_SOURCE_BINDING.json').read_text())
        cls.decision = json.loads((cls.candidate / 'FMDL6X4A_DECISION.json').read_text())

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp)

    def test_01_contract_and_entry_gate(self) -> None:
        contract, errors = validate_contract(self.repo)
        self.assertFalse(errors)
        self.assertEqual(contract['entry_gate']['required_release_sequence'], 41)
        self.assertEqual(contract['next_gate'], 'FMDL-6X4-B_RESEARCH_WORKFLOW_INTEGRATION_AND_EVIDENCE_REGISTRATION')

    def test_02_workflow_registry(self) -> None:
        registry = json.loads((self.candidate / 'FMDL6X4A_WORKFLOW_CONTRACT_REGISTRY.json').read_text())
        self.assertEqual(registry['workflow_count'], 14)
        self.assertTrue(all(not row['workflow_execution_authorized'] for row in registry['workflows']))
        self.assertTrue(all(row['trade_authority'] == 'NONE' for row in registry['workflows']))

    def test_03_pool_and_mapping_accounting(self) -> None:
        self.assertEqual(self.quality['benchmark_pool_member_count'], 7)
        self.assertEqual(self.quality['security_workflow_mapping_count'], 98)
        self.assertEqual(self.quality['adapter_payload_count'], 7)
        self.assertEqual(self.payload['symbols'], ['AAPL', 'BRK.B', 'JPM', 'MSFT', 'NVDA', 'QQQ', 'XOM'])

    def test_04_mapping_state_counts(self) -> None:
        expected = {
            'PARTIAL_ADAPTER_READY': 10,
            'HUMAN_CONFIRMATION_REQUIRED': 19,
            'BLOCKED_REQUIRED_INPUTS_MISSING': 58,
            'NOT_APPLICABLE_REFERENCE_INSTRUMENT': 11,
        }
        self.assertEqual(self.mapping['status_counts'], expected)

    def test_05_workflow_specific_boundaries(self) -> None:
        counts = self.mapping['workflow_status_counts']
        self.assertEqual(counts['company-tearsheet'], {'PARTIAL_ADAPTER_READY': 7})
        self.assertEqual(counts['financials-normalizer'], {
            'BLOCKED_REQUIRED_INPUTS_MISSING': 3,
            'NOT_APPLICABLE_REFERENCE_INSTRUMENT': 1,
            'PARTIAL_ADAPTER_READY': 3,
        })
        self.assertEqual(counts['thesis-tracker'], {'HUMAN_CONFIRMATION_REQUIRED': 7})

    def test_06_zero_execution_and_zero_investment_actions(self) -> None:
        self.assertEqual(self.quality['formal_workflow_execution_count'], 0)
        self.assertEqual(self.quality['completed_workflow_artifact_count'], 0)
        self.assertEqual(self.quality['investment_recommendation_count'], 0)
        self.assertEqual(self.quality['candidate_promotion_count'], 0)
        self.assertEqual(self.decision['investment_os_candidate_pool_gate'], 'CLOSED_NOT_AUTHORIZED_IN_FMDL6X4A')
        self.assertEqual(self.decision['trade_authority'], 'NONE')

    def test_07_queue_accounting(self) -> None:
        self.assertEqual(self.queues, {
            'BLOCKED_INPUT_QUEUE': 58,
            'HUMAN_CONFIRMATION_QUEUE': 19,
            'NOT_APPLICABLE_REGISTRY': 11,
            'PARTIAL_RUNTIME_SOURCE_CHECK_QUEUE': 10,
        })

    def test_08_source_category_boundary(self) -> None:
        source_registry = json.loads((self.candidate / 'FMDL6X4A_SOURCE_CATEGORY_REGISTRY.json').read_text())
        self.assertFalse(source_registry['connector_readiness_claimed'])
        self.assertTrue(source_registry['runtime_source_check_required'])
        self.assertFalse(self.source['source_category_mapping_is_connector_readiness'])
        self.assertFalse(self.source['neutral_fill_used'])
        self.assertFalse(self.source['silent_source_substitution'])

    def test_09_shards_and_replay(self) -> None:
        self.assertEqual(self.quality['manifested_shard_count'], 256)
        with zipfile.ZipFile(self.candidate / 'FMDL6X4A_ADAPTER_SHARDS.zip') as archive:
            self.assertEqual(len(archive.namelist()), 256)
        result = validate_candidate(self.repo, self.candidate, '2026-07-23T00:00:00Z', 'TEST_SOURCE_COMMIT', self.acceptance)
        self.assertEqual(result['same_input_replay'], 'PASS')


if __name__ == '__main__':
    unittest.main()
