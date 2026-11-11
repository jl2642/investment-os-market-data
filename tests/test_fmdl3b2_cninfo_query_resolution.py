"""Regression: a completed zero-row CNINFO call is not an adapter failure."""
import pandas as pd

from scripts.run_fmdl3b2_shard_v2 import (
    _completed_cninfo_query,
    _parse_source_notes,
    enrich_official_query_resolution,
)


def _enrich(notes: str, filings: int = 0):
    support = pd.DataFrame([{
        "symbol": "920001.BJ", "board": "BSE",
        "official_filing_count": filings,
        "status_reason": "BSE_OFFICIAL_DOCUMENT_EXTRACTION_REQUIRED",
    }])
    sources = pd.DataFrame([{
        "source_id": "SRC-CNINFO-920001",
        "notes": notes,
    }])
    return enrich_official_query_resolution(support, sources).iloc[0]


def test_nonempty_official_response_remains_classified():
    row = _enrich("status=SUCCESS; rows=5; error=", filings=2)
    assert row["official_query_status"] == "SUCCESS"
    assert row["official_query_adapter_status"] == "SUCCESS"
    assert row["official_document_status"] == "INDEXED_CLASSIFIED_PERIODIC_REPORTS"
    assert row["official_query_resolution_basis"] == "COMPLETED_NONEMPTY_CNINFO_RESPONSE"


def test_successful_empty_response_is_controlled_quarantine_not_error():
    row = _enrich("status=EMPTY; rows=0; error=", filings=0)
    assert row["official_query_status"] == "SUCCESS"
    assert row["official_query_adapter_status"] == "EMPTY"
    assert row["official_query_raw_row_count"] == 0
    assert row["official_query_resolution_basis"] == "COMPLETED_EMPTY_CNINFO_RESPONSE"
    assert row["official_document_status"] == (
        "NO_CLASSIFIED_PERIODIC_REPORT_IN_SCOPE_AFTER_SUCCESSFUL_CNINFO_QUERY"
    )
    assert row["status_reason"] == row["official_document_status"]


def test_transport_error_stays_unresolved_and_blocks_bse_acceptance():
    row = _enrich("status=ERROR; rows=0; error=ConnectionError: denied")
    assert row["official_query_status"] == "ERROR"
    assert row["official_query_adapter_error"].startswith("ConnectionError")
    assert row["official_document_status"] == "CNINFO_QUERY_UNRESOLVED"
    assert row["status_reason"] == "BSE_CNINFO_QUERY_UNRESOLVED"


def test_inconsistent_or_unattributed_empty_result_is_not_accepted():
    assert not _completed_cninfo_query("EMPTY", 0, None)
    assert not _completed_cninfo_query("EMPTY", 1, "")
    assert not _completed_cninfo_query("SUCCESS", 0, "")
    assert not _completed_cninfo_query("ERROR", 0, "")
    assert _parse_source_notes("status=EMPTY; rows=0")[2] is None
    row = _enrich("status=EMPTY; rows=0")
    assert row["official_document_status"] == "CNINFO_QUERY_UNRESOLVED"


def test_missing_source_evidence_remains_fail_closed():
    support = pd.DataFrame([{
        "symbol": "920001.BJ", "board": "BSE",
        "official_filing_count": 0, "status_reason": None,
    }])
    row = enrich_official_query_resolution(support, pd.DataFrame()).iloc[0]
    assert row["official_query_status"] == "UNKNOWN"
    assert row["official_document_status"] == "CNINFO_QUERY_UNRESOLVED"
    assert row["official_query_adapter_error"] == "MISSING_SOURCE_EVIDENCE"

from scripts import fmdl3b2_non_equity as instruments


def _bond(symbol, raw=None, normalized=None, filing_count=0):
    code = symbol[:6]
    support = pd.DataFrame([{
        "symbol": symbol, "board": "BSE", "statement_status": "QUARANTINED",
        "official_filing_count": filing_count,
        "status_reason": "BSE_OFFICIAL_DOCUMENT_EXTRACTION_REQUIRED",
    }])
    sources = pd.DataFrame([{
        "source_id": f"SRC-CNINFO-{code}",
        "notes": f"status=ERROR; rows=0; error='{code}'",
    }])
    return enrich_official_query_resolution(support, sources, raw=raw, normalized=normalized).iloc[0]


def test_three_officially_verified_bse_convertibles_are_not_equities():
    for symbol, info in instruments.VERIFIED_BSE_NON_EQUITY.items():
        row = _bond(symbol)
        assert row["security_type"] == "PRIVATE_CONVERTIBLE_BOND"
        assert row["issuer_equity_symbol"] == info["issuer_equity_symbol"]
        assert row["classification_evidence_url"] == info["evidence_url"]
        assert row["official_document_status"] == instruments.BOND_EXCLUSION_STATUS
        assert row["official_query_status"] == instruments.BOND_QUERY_STATUS
        assert row["official_query_adapter_status"] == "ERROR"  # Original error is retained.
        assert row["official_query_adapter_error"] == f"'{symbol[:6]}'"
        assert instruments.bse_query_row_passes(row)
        assert row["status_reason"] == "INDEPENDENTLY_VERIFIED_NON_EQUITY_BOND_EXCLUDED_FROM_STOCK_FINANCIALS"


def test_unknown_bse_code_and_spoofed_exchange_cannot_bypass_equity_query():
    assert instruments.verified_non_equity("810012.BJ", "BSE") is None
    assert instruments.verified_non_equity("810011.SZ", "BSE") is None
    assert instruments.verified_non_equity("810011.BJ", "SZ_MAIN") is None
    row = _bond("810012.BJ")
    assert row["official_document_status"] == "CNINFO_QUERY_UNRESOLVED"
    assert not instruments.bse_query_row_passes(row)


def test_bond_exception_fails_if_equity_fact_or_filing_is_present():
    symbol = "810011.BJ"
    raw = pd.DataFrame([{"symbol": symbol, "statement": "balance_sheet"}])
    normalized = pd.DataFrame([{"symbol": symbol, "decision_grade_eligible": True}])
    for row in (_bond(symbol, raw=raw), _bond(symbol, normalized=normalized), _bond(symbol, filing_count=1)):
        assert row["official_document_status"] == "CNINFO_QUERY_UNRESOLVED"
        assert not instruments.bse_query_row_passes(row)


def test_non_equity_claim_requires_exact_issuer_and_official_evidence():
    original = _bond("810013.BJ")
    assert instruments.bse_query_row_passes(original)
    for field, altered in (
        ("classification_evidence_url", "https://example.com/unverified.pdf"),
        ("issuer_equity_symbol", "810013.BJ"),
        ("security_type", "A_SHARE_EQUITY"),
        ("official_query_status", "SUCCESS"),
        ("official_filing_count", 3),
    ):
        row = original.copy()
        row[field] = altered
        assert not instruments.bse_query_row_passes(row), field


def test_bse_gate_accepts_only_verified_bonds_or_successful_equity_queries():
    valid_bond = _bond("810014.BJ")
    valid_equity = _enrich("status=SUCCESS; rows=2; error=", filings=1)
    invalid_equity = _enrich("status=ERROR; rows=0; error=ConnectionError")
    bse = pd.DataFrame([valid_bond.to_dict(), valid_equity.to_dict()])
    assert instruments.bse_gate_passes(bse)
    assert instruments.bse_unresolved_count(bse) == 0
    mixed = pd.DataFrame([valid_bond.to_dict(), invalid_equity.to_dict()])
    assert not instruments.bse_gate_passes(mixed)
    assert instruments.bse_unresolved_count(mixed) == 1
