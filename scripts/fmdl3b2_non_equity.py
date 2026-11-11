"""Audited exceptions: non-equity BSE convertible bonds in the market snapshot.

These instruments are *not* issuer equities and have no standalone stock
financial statements. The exact list is supported by dated issuer disclosures.
Do not generalize by prefix; new instruments must be independently classified.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

BOND_EXCLUSION_STATUS = "VERIFIED_NON_EQUITY_CONVERTIBLE_BOND_EXCLUDED"
BOND_QUERY_STATUS = "NOT_APPLICABLE_NON_EQUITY"
EQUITY_QUERY_STATES = frozenset({
    "INDEXED_CLASSIFIED_PERIODIC_REPORTS",
    "NO_CLASSIFIED_PERIODIC_REPORT_IN_SCOPE_AFTER_SUCCESSFUL_CNINFO_QUERY",
})

# Evidence identifies the bond separately from the issuer's actual equity.
VERIFIED_BSE_NON_EQUITY: dict[str, dict[str, str]] = {
    "810011.BJ": {
        "security_type": "PRIVATE_CONVERTIBLE_BOND",
        "security_name": "优机定转",
        "issuer_equity_symbol": "920943.BJ",
        "evidence_url": "https://static.cninfo.com.cn/finalpage/2026-02-10/1224975124.PDF",
    },
    "810013.BJ": {
        "security_type": "PRIVATE_CONVERTIBLE_BOND",
        "security_name": "万通定转",
        "issuer_equity_symbol": "920839.BJ",
        "evidence_url": "https://www.bse.cn/disclosure/2026/2026-04-15/4ada2ad06a8747f5a750fc4ec7effc13.pdf",
    },
    "810014.BJ": {
        "security_type": "PRIVATE_CONVERTIBLE_BOND",
        "security_name": "莱特定转",
        "issuer_equity_symbol": "920689.BJ",
        "evidence_url": "https://www.bse.cn/disclosure/2026/2026-07-27/95d0e7e2b0b74f79baf5274c81ed5ae6.pdf",
    },
}


def verified_non_equity(symbol: str, board: str) -> dict[str, str] | None:
    """An exact, official-evidence-backed match; no prefix shortcuts."""
    if board != "BSE":
        return None
    return VERIFIED_BSE_NON_EQUITY.get(symbol)


def bse_query_row_passes(row: Any) -> bool:
    """Equities require a completed CNINFO query; verified bonds need independent type evidence."""
    status = str(row.get("official_query_status") or "")
    document = str(row.get("official_document_status") or "")
    symbol = str(row.get("symbol") or "")
    classified = verified_non_equity(symbol, str(row.get("board") or ""))
    if status == "SUCCESS" and document in EQUITY_QUERY_STATES:
        return classified is None
    if classified is None:
        return False
    return (
        status == BOND_QUERY_STATUS
        and document == BOND_EXCLUSION_STATUS
        and str(row.get("statement_status") or "") == "QUARANTINED"
        and str(row.get("security_type") or "") == classified["security_type"]
        and str(row.get("classification_evidence_url") or "") == classified["evidence_url"]
        and str(row.get("issuer_equity_symbol") or "") == classified["issuer_equity_symbol"]
        and int(pd.to_numeric(pd.Series([row.get("official_filing_count", 0)]), errors="coerce").fillna(-1).iloc[0]) == 0
    )


def bse_gate_passes(bse: pd.DataFrame) -> bool:
    return all(bse_query_row_passes(row) for _, row in bse.iterrows())


def bse_unresolved_count(bse: pd.DataFrame) -> int:
    return sum(not bse_query_row_passes(row) for _, row in bse.iterrows())
