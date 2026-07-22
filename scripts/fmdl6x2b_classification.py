from __future__ import annotations

import re
from typing import Any

from fmdl6x2b_common import ascii_key, normalize_text, record_hash

CLASSIFICATION_RULE_VERSION = 'fmdl6x2b.classification.v1.0.0'


def classify(record: dict[str, Any]) -> dict[str, str]:
    name = normalize_text(record.get('official_security_name', ''))
    etf = bool(record.get('etf_flag'))
    test = bool(record.get('test_issue'))

    if test:
        return _result('TEST_ISSUE', 'EXCLUDED', 'TEST_ISSUE', 'HIGH', 'TEST_ISSUE')
    if etf:
        if re.search(r'\bETN\b|exchange[- ]traded notes?', name, re.I):
            return _result('ETN', 'REFERENCE_ONLY', 'REFERENCE_ETN', 'HIGH', 'OFFICIAL_ETF_FLAG_PLUS_NAME')
        if re.search(r'closed[- ]end fund', name, re.I):
            return _result('CLOSED_END_FUND', 'REFERENCE_ONLY', 'REFERENCE_CEF', 'HIGH', 'OFFICIAL_ETF_FLAG_PLUS_NAME')
        return _result('ETF_OR_EXCHANGE_TRADED_PRODUCT', 'REFERENCE_ONLY', 'REFERENCE_ETP', 'HIGH', 'OFFICIAL_ETF_FLAG')
    if re.search(r'\bwarrants?\b', name, re.I):
        return _result('WARRANT', 'EXCLUDED', 'DERIVATIVE_WARRANT', 'HIGH', 'EXPLICIT_SECURITY_NAME')
    if re.search(r'\brights?\b', name, re.I):
        return _result('RIGHT', 'EXCLUDED', 'DERIVATIVE_RIGHT', 'HIGH', 'EXPLICIT_SECURITY_NAME')
    if re.search(r'\bunits?\b', name, re.I) and re.search(r'warrant|right', name, re.I):
        return _result('COMPOSITE_UNIT', 'EXCLUDED', 'COMPOSITE_SPAC_OR_OFFERING_UNIT', 'HIGH', 'EXPLICIT_SECURITY_NAME')
    if re.search(r'\bpreferred\b|\bpreference shares?\b|trust preferred', name, re.I):
        return _result('PREFERRED_EQUITY', 'EXCLUDED', 'NON_COMMON_PREFERRED', 'HIGH', 'EXPLICIT_SECURITY_NAME')
    if re.search(r'\bsenior notes?\b|\bnotes? due\b|\bbonds?\b|\bdebentures?\b', name, re.I):
        return _result('DEBT_SECURITY', 'EXCLUDED', 'NON_EQUITY_DEBT', 'HIGH', 'EXPLICIT_SECURITY_NAME')
    if re.search(r'closed[- ]end fund', name, re.I):
        return _result('CLOSED_END_FUND', 'REFERENCE_ONLY', 'REFERENCE_CEF', 'HIGH', 'EXPLICIT_SECURITY_NAME')
    if re.search(r'royalty trust', name, re.I):
        return _result('ROYALTY_TRUST_UNIT', 'RESEARCH_ELIGIBLE_SPECIAL_PROFILE', 'SPECIAL_ROYALTY_TRUST', 'HIGH', 'EXPLICIT_SECURITY_NAME')
    if re.search(r'\blimited partnership\b|\bL\.?P\.?\b|\bLP\b', name) and re.search(r'common units?|limited partner interests?|depositary units?', name, re.I):
        return _result('PTP_MLP_UNIT', 'RESEARCH_ELIGIBLE_SPECIAL_PROFILE', 'SPECIAL_PTP_MLP', 'HIGH', 'EXPLICIT_SECURITY_NAME')
    if re.search(r'american depositary (shares?|receipts?)|\bADS\b|\bADR\b', name, re.I):
        return _result('ADR_OR_ADS', 'RESEARCH_REVIEW_REQUIRED', 'ADR_PENDING_UNDERLYING_DEPOSITARY_RATIO', 'HIGH', 'EXPLICIT_SECURITY_NAME')
    if re.search(r'\bacquisition\b', name, re.I) and re.search(r'common stock|ordinary shares?|class [A-Z0-9-]+', name, re.I):
        return _result('SPAC_COMMON', 'RESEARCH_ELIGIBLE_SPECIAL_PROFILE', 'SPECIAL_SPAC_PRE_BUSINESS_COMBINATION', 'MEDIUM', 'NAME_RULE')
    if re.search(r'\bREIT\b|real estate investment trust', name, re.I):
        return _result('REIT_COMMON_OR_BENEFICIAL', 'RESEARCH_ELIGIBLE_SPECIAL_PROFILE', 'SPECIAL_REIT', 'HIGH', 'EXPLICIT_SECURITY_NAME')
    if re.search(r'\bfund\b', name, re.I) and re.search(r'common stock|common shares?|shares of beneficial interest|fund\b', name, re.I):
        return _result('CLOSED_END_OR_LISTED_FUND', 'REFERENCE_ONLY', 'REFERENCE_LISTED_FUND', 'MEDIUM', 'NAME_RULE')
    if re.search(r'\bcommon units?\b', name, re.I):
        return _result('COMMON_UNIT_UNRESOLVED', 'RESEARCH_REVIEW_REQUIRED', 'UNIT_STRUCTURE_PENDING', 'MEDIUM', 'EXPLICIT_SECURITY_NAME')
    if re.search(r'\bcommon stock\b|\bordinary shares?\b|\bcommon shares?\b|shares of beneficial interest', name, re.I):
        return _result('COMMON_EQUITY', 'RESEARCH_REVIEW_REQUIRED', 'CORE_EQUITY_PENDING_SEC_PROFILE', 'MEDIUM', 'EXPLICIT_SECURITY_NAME')
    if re.search(r'\bunits?\b', name, re.I):
        return _result('UNIT_UNRESOLVED', 'RESEARCH_REVIEW_REQUIRED', 'UNIT_STRUCTURE_PENDING', 'LOW', 'NAME_RULE')
    return _result('UNRESOLVED_LISTED_SECURITY', 'RESEARCH_REVIEW_REQUIRED', 'CLASSIFICATION_EVIDENCE_PENDING', 'LOW', 'INSUFFICIENT_DIRECTORY_EVIDENCE')


def _result(instrument_type: str, research_status: str, research_profile: str, confidence: str, basis: str) -> dict[str, str]:
    return {
        'instrument_type': instrument_type,
        'research_status': research_status,
        'research_profile': research_profile,
        'classification_confidence': confidence,
        'classification_basis': basis,
        'classification_rule_version': CLASSIFICATION_RULE_VERSION,
    }


def extract_share_class(name: str, instrument_type: str) -> str | None:
    text = normalize_text(name)
    match = re.search(r'\bClass\s+([A-Z0-9-]+)\b', text, re.I)
    if match:
        return 'CLASS_' + match.group(1).upper()
    match = re.search(r'\bSeries\s+([A-Z0-9-]+)\b', text, re.I)
    if match and instrument_type == 'PREFERRED_EQUITY':
        return 'SERIES_' + match.group(1).upper()
    if instrument_type in {'COMMON_EQUITY', 'SPAC_COMMON', 'REIT_COMMON_OR_BENEFICIAL'}:
        if re.search(r'ordinary shares?', text, re.I):
            return 'ORDINARY_PRIMARY'
        return 'COMMON_PRIMARY'
    if instrument_type == 'ADR_OR_ADS':
        return 'ADR_UNRESOLVED_RATIO'
    if instrument_type in {'PTP_MLP_UNIT', 'ROYALTY_TRUST_UNIT', 'COMMON_UNIT_UNRESOLVED'}:
        return 'UNIT_PRIMARY_OR_UNRESOLVED'
    return None


def extract_issuer_base(name: str, instrument_type: str) -> tuple[str, str]:
    text = normalize_text(name)
    if ' - ' in text:
        left, right = text.split(' - ', 1)
        if re.search(r'common|ordinary|depositary|warrant|right|unit|preferred|notes?|fund', right, re.I):
            text = left
    patterns: list[str] = []
    if instrument_type == 'ADR_OR_ADS':
        patterns = [r'\s+American Depositary (Shares?|Receipts?)\b.*$', r'\s+\bADS\b.*$', r'\s+\bADR\b.*$']
    elif instrument_type == 'PREFERRED_EQUITY':
        patterns = [
            r'\s+Depositary Shares?,?\s+Each Representing.*$', r'\s+\d+(?:\.\d+)?%\s+.*$',
            r'\s+Series\s+[A-Z0-9-]+\s+.*Preferred.*$', r'\s+Preferred (Stock|Shares?)\b.*$',
            r'\s+Trust Preferred Securities\b.*$',
        ]
    elif instrument_type == 'DEBT_SECURITY':
        patterns = [r'\s+\d+(?:\.\d+)?%\s+.*$', r'\s+Senior Notes?\b.*$', r'\s+Notes?\s+Due\b.*$', r'\s+Debentures?\b.*$']
    elif instrument_type == 'WARRANT':
        patterns = [r'\s+(Redeemable )?Warrants?\b.*$', r'\s+Common Stock Purchase Warrant\b.*$', r'\s+Warrant\b.*$']
    elif instrument_type == 'RIGHT':
        patterns = [r'\s+Rights?\b.*$']
    elif instrument_type in {'COMPOSITE_UNIT', 'UNIT_UNRESOLVED', 'COMMON_UNIT_UNRESOLVED', 'PTP_MLP_UNIT', 'ROYALTY_TRUST_UNIT'}:
        patterns = [r'\s+Units?,?\s+each\b.*$', r'\s+Common Units?\b.*$', r'\s+Depositary Units?\b.*$', r'\s+Units?\b.*$']
    elif instrument_type in {'COMMON_EQUITY', 'SPAC_COMMON', 'REIT_COMMON_OR_BENEFICIAL'}:
        patterns = [
            r'\s+Class\s+[A-Z0-9-]+\s+(Common Stock|Ordinary Shares?|Common Shares?)\b.*$',
            r'\s+(Common Stock|Ordinary Shares?|Common Shares?)\b.*$', r'\s+Shares of Beneficial Interest\b.*$',
        ]
    elif instrument_type == 'TEST_ISSUE':
        patterns = [r'\s+TEST Common Stock\b.*$']
    for pattern in patterns:
        candidate = re.sub(pattern, '', text, flags=re.I).strip(' ,.-')
        if candidate != text and len(candidate) >= 2:
            return candidate, 'EXPLICIT_DESCRIPTOR_REMOVAL'
    return text.strip(' ,.-'), 'FULL_OFFICIAL_SECURITY_NAME'


def enrich_identity(record: dict[str, Any]) -> dict[str, Any]:
    classification = classify(record)
    instrument_type = classification['instrument_type']
    base_name, extraction_basis = extract_issuer_base(record.get('official_security_name', ''), instrument_type)
    normalized_issuer_key = ascii_key(base_name)
    if len(normalized_issuer_key) < 2:
        normalized_issuer_key = ascii_key(record.get('official_security_name', ''))
        extraction_basis = 'FALLBACK_FULL_NAME'
    issuer_id = 'USISS-' + record_hash('ISSUER', normalized_issuer_key)[:24]
    class_token = extract_share_class(record.get('official_security_name', ''), instrument_type)
    share_class_id = None if class_token is None else 'USCLS-' + record_hash('SHARE_CLASS', issuer_id, class_token)[:24]
    if instrument_type in {'COMMON_EQUITY', 'SPAC_COMMON', 'REIT_COMMON_OR_BENEFICIAL', 'PTP_MLP_UNIT', 'ROYALTY_TRUST_UNIT'}:
        security_basis = class_token or instrument_type
    else:
        security_basis = normalize_text(record.get('official_security_name', ''))
    security_id = 'USSEC-' + record_hash('SECURITY', issuer_id, instrument_type, class_token, security_basis)[:24]
    listing_id = 'USLST-' + record_hash('LISTING', security_id, record.get('venue'), record.get('symbol'))[:24]
    enriched = dict(record)
    enriched.update(classification)
    enriched.update({
        'canonical_issuer_id': issuer_id,
        'canonical_share_class_id': share_class_id,
        'canonical_security_id': security_id,
        'canonical_listing_id': listing_id,
        'canonical_id_status': 'PROVISIONAL_DIRECTORY_DERIVED_MERGEABLE',
        'issuer_display_name_directory_derived': base_name,
        'issuer_normalized_key': normalized_issuer_key,
        'issuer_extraction_basis': extraction_basis,
        'issuer_identity_confidence': 'MEDIUM' if extraction_basis == 'EXPLICIT_DESCRIPTOR_REMOVAL' else 'LOW',
        'sec_cik10': None,
        'sec_identity_status': 'PENDING_OFFICIAL_SEC_EVIDENCE',
        'share_class_token': class_token,
        'identity_resolution_status': 'DIRECTORY_IDENTITY_SKELETON_ISSUED',
        'identity_merge_policy': 'ALIAS_AND_SUPERSESSION_NO_DESTRUCTIVE_REKEY',
    })
    return enriched
