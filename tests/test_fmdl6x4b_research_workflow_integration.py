from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from fmdl6x4b_research_workflow_integration import build_candidate, validate_candidate, validate_contract


class FMDL6X4BTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo = Path('.').resolve()
        cls.tmp = Path(tempfile.mkdtemp(prefix='fmdl6x4b_'))
        cls.candidate = cls.tmp / 'candidate'
        cls.acceptance = cls.tmp / 'acceptance.json'
        build_candidate(cls.repo, cls.candidate, '2026-07-23T00:00:00Z', 'TEST_SOURCE_COMMIT')
        cls.quality = json.loads((cls.candidate / 'FMDL6X4B_QUALITY_REPORT.json').read_text())
        cls.integration = json.loads((cls.candidate / 'FMDL6X4B_INTEGRATION_SUMMARY.json').read_text())
        cls.queues = json.loads((cls.candidate / 'FMDL6X4B_QUEUE_SUMMARY.json').read_text())['queue_counts']
        cls.source = json.loads((cls.candidate / 'FMDL6X4B_SOURCE_BINDING.json').read_text())
        cls.decision = json.loads((cls.candidate / 'FMDL6X4B_DECISION.json').read_text())

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp)

    def test_01_contract_and_entry_gate(self) -> None:
        contract, errors = validate_contract(self.repo)
        self.assertFalse(errors)
        self.assertEqual(contract['entry_gate']['required_release_sequence'], 42)
        self.assertEqual(contract['next_gate'], 'FMDL-6X4-C_CANDIDATE_GRADUATION_DECISION_INTERFACE_AND_GUARDRAILS')

    def test_02_source_and_evidence_registry(self) -> None:
        self.assertEqual(self.quality['source_registry_count'], 7)
        self.assertEqual(self.quality['evidence_registration_count'], 53)
        self.assertEqual(self.quality['security_evidence_ledger_count'], 7)

    def test_03_workflow_integration_accounting(self) -> None:
        self.assertEqual(self.quality['workflow_contract_count'], 14)
        self.assertEqual(self.quality['security_workflow_mapping_count'], 98)
        self.assertEqual(self.quality['output_registration_contract_count'], 14)

    def test_04_integration_state_counts(self) -> None:
        self.assertEqual(self.integration['integration_status_counts'], {
            'BLOCKED_REQUIRED_INPUTS_MISSING': 58,
            'INVOCATION_ENVELOPE_REGISTERED_RUNTIME_SOURCE_CHECK_PENDING': 10,
            'NOT_APPLICABLE_REFERENCE_INSTRUMENT': 11,
            'WAITING_USER_CONFIRMATION': 19,
        })

    def test_05_invocation_envelope_boundary(self) -> None:
        self.assertEqual(self.quality['invocation_envelope_count'], 10)
        with zipfile.ZipFile(self.candidate / 'FMDL6X4B_INTEGRATION_SHARDS.zip') as archive:
            envelope_rows = []
            for name in archive.namelist():
                if name.startswith('INVOCATION_ENVELOPE/'):
                    envelope_rows.extend(json.loads(line) for line in archive.read(name).decode().splitlines() if line.strip())
        self.assertEqual(len(envelope_rows), 10)
        self.assertTrue(all(row['execution_status'] == 'NOT_EXECUTED' for row in envelope_rows))
        self.assertTrue(all(not row['workflow_execution_authorized'] for row in envelope_rows))

    def test_06_zero_workflow_outputs_and_investment_actions(self) -> None:
        self.assertEqual(self.quality['formal_workflow_execution_count'], 0)
        self.assertEqual(self.quality['registered_workflow_output_count'], 0)
        self.assertEqual(self.quality['investment_recommendation_count'], 0)
        self.assertEqual(self.quality['candidate_promotion_count'], 0)
        self.assertEqual(self.decision['investment_os_candidate_pool_gate'], 'CLOSED_NOT_AUTHORIZED_IN_FMDL6X4B')
        self.assertEqual(self.decision['trade_authority'], 'NONE')

    def test_07_queue_accounting(self) -> None:
        self.assertEqual(self.queues, {
            'BLOCKED_INPUT_QUEUE': 58,
            'HUMAN_CONFIRMATION_QUEUE': 19,
            'NOT_APPLICABLE_REGISTRY': 11,
            'RUNTIME_SOURCE_CHECK_QUEUE': 10,
        })

    def test_08_source_boundary(self) -> None:
        self.assertTrue(self.source['runtime_source_check_required'])
        self.assertFalse(self.source['runtime_connector_readiness_claimed'])
        self.assertFalse(self.source['source_category_mapping_is_connector_readiness'])
        self.assertFalse(self.source['neutral_fill_used'])
        self.assertFalse(self.source['silent_source_substitution'])

    def test_09_shards_and_replay(self) -> None:
        self.assertEqual(self.quality['manifested_shard_count'], 320)
        with zipfile.ZipFile(self.candidate / 'FMDL6X4B_INTEGRATION_SHARDS.zip') as archive:
            self.assertEqual(len(archive.namelist()), 320)
        result = validate_candidate(self.repo, self.candidate, '2026-07-23T00:00:00Z', 'TEST_SOURCE_COMMIT', self.acceptance)
        self.assertEqual(result['same_input_replay'], 'PASS')


if __name__ == '__main__':
    unittest.main()
