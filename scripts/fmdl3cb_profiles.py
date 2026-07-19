from __future__ import annotations

from pathlib import Path

import pandas as pd


ALLOWED_PROFILES = {
    "GENERAL_NON_FINANCIAL",
    "BANK",
    "INSURANCE",
    "SECURITIES_AND_BROKERAGE",
    "UNRESOLVED",
}


def load_sector_overrides(path: Path) -> dict[str, dict[str, str]]:
    frame = pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")
    required = {"symbol", "sector_profile", "reason", "source_basis"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"sector override columns missing: {sorted(missing)}")
    if frame["symbol"].duplicated().any():
        raise ValueError("duplicate sector override symbol")
    if not set(frame["sector_profile"]).issubset(ALLOWED_PROFILES):
        raise ValueError("uncontrolled sector override profile")
    return {
        str(row.symbol): {
            "sector_profile": str(row.sector_profile),
            "reason": str(row.reason),
            "source_basis": str(row.source_basis),
        }
        for row in frame.itertuples(index=False)
    }


def infer_sector_profile(
    frame: pd.DataFrame,
    symbol: str | None = None,
    overrides: dict[str, dict[str, str]] | None = None,
) -> tuple[str, str, str]:
    if symbol and overrides and symbol in overrides:
        override = overrides[symbol]
        return (
            override["sector_profile"],
            override["source_basis"],
            override["reason"],
        )

    fields = set(
        frame.get("line_item_id", pd.Series(dtype=str)).dropna().astype(str)
    )
    insurance = {"insurance_revenue", "insurance_contract_liabilities"}
    bank_core = {"net_interest_income", "loans_advances"}
    brokerage_core = {"fee_commission_net", "net_interest_income"}
    general = {
        "revenue",
        "cogs",
        "operating_income",
        "cfo",
        "total_assets",
        "parent_equity",
    }

    if fields & insurance:
        return (
            "INSURANCE",
            "STATEMENT_FIELD_SIGNATURE_STRICT_V2",
            "INSURANCE_SPECIFIC_FIELD_PRESENT",
        )
    if bank_core.issubset(fields):
        return (
            "BANK",
            "STATEMENT_FIELD_SIGNATURE_STRICT_V2",
            "NET_INTEREST_INCOME_AND_LOANS_ADVANCES_PRESENT",
        )
    if brokerage_core.issubset(fields) and "loans_advances" not in fields:
        return (
            "SECURITIES_AND_BROKERAGE",
            "STATEMENT_FIELD_SIGNATURE_STRICT_V2",
            "FEE_COMMISSION_AND_NET_INTEREST_WITHOUT_LOANS_ADVANCES",
        )
    if fields & general:
        return (
            "GENERAL_NON_FINANCIAL",
            "STATEMENT_FIELD_SIGNATURE_STRICT_V2",
            "GENERAL_STATEMENT_FIELDS_PRESENT_WITHOUT_FINANCIAL_CORE_SIGNATURE",
        )
    return (
        "UNRESOLVED",
        "STATEMENT_FIELD_SIGNATURE_STRICT_V2",
        "NO_CONTROLLED_PROFILE_SIGNATURE",
    )
