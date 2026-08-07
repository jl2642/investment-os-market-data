from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def test_contract_boundaries():
    c=json.loads((ROOT/'config/hkcu_p2b_e2_top20_decision_synthesis_s1_contract.json').read_text())
    assert c['program_id']=='HKCU-P2B-E2-S1'
    assert c['selection_policy']['expected_security_count']==20
    assert c['selection_policy']['expected_dimension_rows']==60
    assert c['expected_result']['advance_security_count']==18
    assert c['expected_result']['blocked_security_count']==2
    assert set(c['expected_result']['retained_blocker_security_ids'])=={'HKEX:00551','HKEX:01114'}
    assert c['acceptance']['formal_candidate_graduation_allowed'] is False
    assert c['acceptance']['trade_authority']=='NONE'
    assert c['next_gate']=='P2B_E2_RANKS21_40_PARTIAL_SYNTHESIS'

def test_pipeline_guards_present():
    t=(ROOT/'pipeline/hkcu_p2b_e2_top20_decision_synthesis.py').read_text()
    assert 'RETAINED_DIRECT_NEGATIVE_SIGNAL' in t
    assert 'P2A_RANK_NOT_PRESERVED' in t
    assert 'formal_candidate_graduation_allowed' in t
    assert 'alpha_score' in t
    assert 'trade_authority' in t
