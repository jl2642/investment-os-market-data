from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_s2_contract_boundaries():
    c = json.loads((ROOT / 'config/hkcu_p2b_e2_ranks21_40_decision_synthesis_s2_contract.json').read_text())
    assert c['program_id'] == 'HKCU-P2B-E2-S2'
    assert c['selection_policy']['rank_start'] == 21
    assert c['selection_policy']['rank_end'] == 40
    assert c['selection_policy']['expected_security_count'] == 20
    assert c['selection_policy']['expected_dimension_rows'] == 60
    assert c['selection_policy']['expected_partial_rows'] == 47
    assert c['selection_policy']['expected_non_partial_rows'] == 13
    assert c['selection_policy']['expected_targeted_override_rows'] == 5
    assert c['expected_result']['advance_security_count'] == 19
    assert c['expected_result']['blocked_security_count'] == 1
    assert c['expected_result']['retained_blocker_security_ids'] == ['HKEX:09636']
    assert c['expected_result']['retained_blocker_event_count'] == 1
    assert c['next_gate'] == 'P2B_E2_RANKS41_60_DECISION_SYNTHESIS'
    assert c['acceptance']['formal_candidate_graduation_allowed'] is False
    assert c['trade_authority'] == 'NONE'


def test_reusable_engine_guards_present():
    t = (ROOT / 'pipeline/hkcu_p2b_e2_window_decision_synthesis.py').read_text()
    for token in [
        '--contract',
        'cross_dimension_event_deduplication_enabled',
        'fresh_primary_override_guard',
        'RETAINED_DIRECT_NEGATIVE_SIGNAL',
        'GENERIC_CONNECTED_TRANSACTION_CONFIDENCE_CAP',
        'GENERIC_INFORMATION_LIMIT_CONFIDENCE_CAP',
        'formal_candidate_graduation_allowed',
        'trade_authority',
    ]:
        assert token in t
