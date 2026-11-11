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
