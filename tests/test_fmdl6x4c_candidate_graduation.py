from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from fmdl6x4c_candidate_graduation import build_candidate, validate_candidate, validate_contract


class FMDL6X4CTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo = Path('.').resolve()
        cls.tmp = Path(tempfile.mkdtemp(prefix='fmdl6x4c_'))
        cls.candidate = cls.tmp / 'candidate'
        cls.acceptance = cls.tmp / 'acceptance.json'
        build_candidate(cls.repo, cls.candidate, '2026-07-23T00:00:00Z', 'TEST_SOURCE_COMMIT')
        cls.quality = json.loads((cls.candidate / 'FMDL6X4C_QUALITY_REPORT.json').read_text())
        cls.coverage = json.loads((cls.candidate / 'FMDL6X4C_COVERAGE_REPORT.json').read_text())
        cls.queues = json.loads((cls.candidate / 'FMDL6X4C_QUEUE_SUMMARY.json').read_text())['queue_counts']
        cls.decision = json.loads((cls.candidate / 'FMDL6X4C_DECISION.json').read_text())
        cls.source = json.loads((cls.candidate / 'FMDL6X4C_SOURCE_BINDING.json').read_text())

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp)

    def test_01_contract_and_entry_gate(self) -> None:
        contract, errors = validate_contract(self.repo)
        self.assertFalse(errors)
        self.assertEqual(contract['entry_gate']['required_release_sequence'], 43)
        self.assertEqual(contract['storage_contract']['release_sequence'], 44)

    def test_02_rule_registry(self) -> None:
        registry = json.loads((self.candidate / 'FMDL6X4C_RULE_REGISTRY.json').read_text())
        self.assertEqual(registry['rule_count'], 12)
        self.assertTrue(all(not row['weighted_score_used'] for row in registry['rules']))
        self.assertTrue(all(not row['neutral_fill_allowed'] for row in registry['rules']))

    def test_03_rule_assessment_accounting(self) -> None:
        self.assertEqual(self.quality['graduation_rule_assessment_count'], 84)
        self.assertEqual(self.quality['rule_assessment_status_counts'], {
            'FAIL': 45,
            'NOT_APPLICABLE': 9,
            'PASS': 30,
        })

    def test_04_decision_dispositions(self) -> None:
        self.assertEqual(self.quality['blocked_issuer_count'], 6)
        self.assertEqual(self.quality['not_applicable_reference_count'], 1)
        self.assertEqual(self.coverage['security_count'], 7)

    def test_05_human_approval_and_decision_interface(self) -> None:
        self.assertEqual(self.quality['decision_interface_count'], 7)
        self.assertEqual(self.quality['human_approval_state_count'], 7)
        self.assertEqual(self.decision['investment_os_candidate_pool_gate'], 'CLOSED_NOT_AUTHORIZED_IN_FMDL6X4C')

    def test_06_guardrails(self) -> None:
        registry = json.loads((self.candidate / 'FMDL6X4C_GUARDRAIL_REGISTRY.json').read_text())
        self.assertEqual(registry['guardrail_count'], 16)
        self.assertTrue(all(row['guardrail_status'] == 'ACTIVE_ENFORCED' for row in registry['guardrails']))
        self.assertTrue(all(row['violation_count'] == 0 for row in registry['guardrails']))

    def test_07_zero_graduation_and_actions(self) -> None:
        events = json.loads((self.candidate / 'FMDL6X4C_GRADUATION_EVENT_REGISTER.json').read_text())
        self.assertEqual(events['graduation_event_count'], 0)
        self.assertEqual(self.quality['formal_candidate_promotion_count'], 0)
        self.assertEqual(self.quality['investment_recommendation_count'], 0)
        self.assertEqual(self.decision['trade_authority'], 'NONE')

    def test_08_queue_accounting_and_source_boundaries(self) -> None:
        self.assertEqual(self.queues, {
            'DECISION_GRADE_MARKET_UPGRADE_QUEUE': 6,
            'FORMAL_PEER_COMPARABILITY_QUEUE': 6,
            'HUMAN_APPROVAL_PREREQUISITE_QUEUE': 6,
            'HUMAN_INVESTMENT_CONTEXT_QUEUE': 6,
            'REFERENCE_INSTRUMENT_REGISTRY': 1,
            'REGISTERED_WORKFLOW_OUTPUT_BACKFILL_QUEUE': 6,
            'THESIS_FALSIFIER_REGISTRATION_QUEUE': 6,
            'VALUATION_READINESS_QUEUE': 6,
        })
        self.assertEqual(self.source['registered_workflow_output_count'], 0)
        self.assertEqual(self.source['market_data_grade'], 'NON_DECISION_GRADE_FALLBACK')
        self.assertEqual(self.source['valuation_factor_observation_count'], 0)
        self.assertEqual(self.source['formal_peer_group_count'], 0)

    def test_09_shards_and_replay(self) -> None:
        self.assertEqual(self.quality['manifested_shard_count'], 320)
        with zipfile.ZipFile(self.candidate / 'FMDL6X4C_GRADUATION_SHARDS.zip') as archive:
            self.assertEqual(len(archive.namelist()), 320)
        result = validate_candidate(self.repo, self.candidate, '2026-07-23T00:00:00Z', 'TEST_SOURCE_COMMIT', self.acceptance)
        self.assertEqual(result['same_input_replay'], 'PASS')


if __name__ == '__main__':
    unittest.main()
