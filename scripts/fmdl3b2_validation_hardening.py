from __future__ import annotations

import re
from typing import Any

import pandas as pd


CONTROLLED_RESULT = "CONTROLLED_EXCLUSION"
CONTROLLED_FLAG_STATUS = "CONTROLLED_PROVIDER_INCONSISTENCY"
ALLOWED_CHECK_RESULTS = {"PASS", "FAIL", CONTROLLED_RESULT}


def _tolerance(reference: float, relative_tolerance: float) -> float:
    return max(abs(float(reference)) * float(relative_tolerance), 1.0)


def _close(left: float, right: float, relative_tolerance: float) -> bool:
    return abs(float(left) - float(right)) <= _tolerance(float(right), relative_tolerance)


def _symbol_from_test(value: Any) -> str | None:
    text = str(value)
    match = re.match(r"^([0-9]{6}\.(?:SH|SZ|BJ)):", text)
    return match.group(1) if match else None


def _next_flag_id(flags: pd.DataFrame) -> str:
    maximum = 0
    if len(flags) and "flag_id" in flags.columns:
        for value in flags["flag_id"].dropna().astype(str):
            match = re.search(r"(\d+)$", value)
            if match:
                maximum = max(maximum, int(match.group(1)))
    return f"FLAG-{maximum + 1:05d}"


def _append_flag(flags: pd.DataFrame, row: dict[str, Any]) -> pd.DataFrame:
    columns = [
        "flag_id", "severity", "entity", "period", "area", "issue", "impact",
        "recommended_fix", "source_id", "status",
    ]
    for column in columns:
        if column not in flags.columns:
            flags[column] = pd.Series(dtype="object")
    return pd.concat([flags, pd.DataFrame([row], columns=columns)], ignore_index=True)


def _downgrade(
    normalized: pd.DataFrame,
    symbol: str,
    period: str,
    line_items: list[str],
    treatment: str,
) -> int:
    if normalized.empty:
        return 0
    mask = (
        normalized["symbol"].astype(str).eq(symbol)
        & normalized["period_end"].astype(str).eq(period)
        & normalized["line_item_id"].astype(str).isin(line_items)
    )
    count = int(mask.sum())
    if not count:
        return 0
    normalized.loc[mask, "decision_grade_eligible"] = False
    normalized.loc[mask, "record_quality"] = CONTROLLED_FLAG_STATUS
    normalized.loc[mask, "comparison_status"] = "not_comparable"
    normalized.loc[mask, "model_treatment"] = treatment
    normalized.loc[mask, "normalization_note"] = (
        normalized.loc[mask, "normalization_note"].fillna("").astype(str).str.rstrip("; ")
        + "; controlled provider-internal statement inconsistency; excluded from derived factors"
    ).str.lstrip("; ")
    return count


def _rollforward_passes(checks: pd.DataFrame, symbol: str, period: str) -> bool:
    if checks.empty:
        return False
    mask = (
        checks["period"].astype(str).eq(period)
        & checks["test"].astype(str).eq(f"{symbol}: beginning cash + net change = ending cash")
        & checks["result"].astype(str).eq("PASS")
    )
    return bool(mask.any())


def harden_statement_validation(
    normalized: pd.DataFrame,
    checks: pd.DataFrame,
    flags: pd.DataFrame,
    *,
    balance_relative_tolerance: float,
    cash_relative_tolerance: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    """Convert only independently evidenced provider inconsistencies to controlled exclusions.

    The function never changes source values. It downgrades affected canonical facts from
    decision-grade eligibility and leaves any unexplained arithmetic failure as FAIL.
    """
    normalized = normalized.copy()
    checks = checks.copy()
    flags = flags.copy()
    evidence: list[dict[str, Any]] = []

    if checks.empty or normalized.empty:
        return normalized, checks, flags, evidence

    failed_indices = checks.index[checks["result"].astype(str).eq("FAIL")].tolist()
    for index in failed_indices:
        row = checks.loc[index]
        symbol = _symbol_from_test(row.get("test"))
        period = str(row.get("period"))
        area = str(row.get("area"))
        if not symbol:
            continue
        group = normalized[
            normalized["symbol"].astype(str).eq(symbol)
            & normalized["period_end"].astype(str).eq(period)
        ]
        if group.empty:
            continue
        values = group.drop_duplicates("line_item_id", keep="first").set_index("line_item_id")["normalized_value"].to_dict()

        reason: str | None = None
        implicated: list[str] = []
        independent_test: str | None = None

        if area == "cash_flow" and "CFO+CFI+CFF+FX" in str(row.get("test")):
            required = {"cfo", "cfi", "cff", "fx_cash_effect", "net_change_cash"}
            if required.issubset(values) and _rollforward_passes(checks, symbol, period):
                expected = float(values["net_change_cash"])
                no_fx = float(values["cfo"] + values["cfi"] + values["cff"])
                no_cff = float(values["cfo"] + values["cfi"] + values["fx_cash_effect"])
                matches = []
                if _close(no_fx, expected, cash_relative_tolerance):
                    matches.append(("NET_CHANGE_MATCHES_CFO_CFI_CFF_WITH_SEPARATELY_REPORTED_FX", "fx_cash_effect"))
                if _close(no_cff, expected, cash_relative_tolerance):
                    matches.append(("NET_CHANGE_MATCHES_CFO_CFI_FX_BUT_REPORTED_CFF_IS_INCONSISTENT", "cff"))
                if len(matches) == 1:
                    reason, item = matches[0]
                    implicated = [item, "net_change_cash"]
                    independent_test = "BEGINNING_CASH_PLUS_NET_CHANGE_EQUALS_ENDING_CASH"

        elif area == "balance_sheet" and "assets = liabilities + equity" in str(row.get("test")):
            required = {"total_assets", "total_liabilities", "total_equity", "liabilities_equity"}
            if required.issubset(values):
                liabilities_plus_equity = float(values["total_liabilities"] + values["total_equity"])
                direct_total = float(values["liabilities_equity"])
                assets = float(values["total_assets"])
                if _close(liabilities_plus_equity, direct_total, balance_relative_tolerance) and not _close(assets, direct_total, balance_relative_tolerance):
                    reason = "LIABILITIES_PLUS_EQUITY_MATCH_DIRECT_TOTAL_BUT_CONFLICT_WITH_TOTAL_ASSETS"
                    implicated = ["total_assets", "total_liabilities", "total_equity", "liabilities_equity"]
                    independent_test = "LIABILITIES_PLUS_EQUITY_EQUALS_DIRECT_LIABILITIES_AND_EQUITY_TOTAL"

        if not reason:
            continue

        treatment = "EXCLUDE_AFFECTED_PERIOD_FROM_DERIVED_CASH_FLOW_FACTORS_PENDING_OFFICIAL_RECONCILIATION" if area == "cash_flow" else "EXCLUDE_AFFECTED_PERIOD_FROM_BALANCE_SHEET_DERIVED_FACTORS_PENDING_OFFICIAL_RECONCILIATION"
        downgraded = _downgrade(normalized, symbol, period, implicated, treatment)
        checks.loc[index, "result"] = CONTROLLED_RESULT
        checks.loc[index, "notes"] = (
            f"{reason}; independent_evidence={independent_test}; "
            f"affected_line_items={','.join(implicated)}; downgraded_fact_count={downgraded}; "
            "source values retained without rewrite"
        )
        flag_id = _next_flag_id(flags)
        flags = _append_flag(
            flags,
            {
                "flag_id": flag_id,
                "severity": "high",
                "entity": symbol,
                "period": period,
                "area": area,
                "issue": reason,
                "impact": f"Affected canonical facts ({','.join(implicated)}) are audit-only and excluded from derived factors",
                "recommended_fix": "Reconcile against the official filing during FMDL-3B-3; do not overwrite provider facts",
                "source_id": "MULTI_SOURCE",
                "status": CONTROLLED_FLAG_STATUS,
            },
        )
        evidence.append(
            {
                "symbol": symbol,
                "period": period,
                "area": area,
                "reason": reason,
                "independent_evidence": independent_test,
                "affected_line_items": implicated,
                "downgraded_fact_count": downgraded,
                "flag_id": flag_id,
                "trade_authority": "NONE",
            }
        )

    return normalized, checks, flags, evidence


def controlled_exclusions_are_classified(checks: pd.DataFrame, flags: pd.DataFrame) -> tuple[bool, list[str]]:
    controlled = checks[checks["result"].astype(str).eq(CONTROLLED_RESULT)] if len(checks) else checks
    errors: list[str] = []
    if len(checks):
        unexpected = sorted(set(checks["result"].dropna().astype(str)) - ALLOWED_CHECK_RESULTS)
        if unexpected:
            errors.append(f"unexpected_results={unexpected}")
    controlled_flags = flags[flags["status"].astype(str).eq(CONTROLLED_FLAG_STATUS)] if len(flags) else flags
    for _, row in controlled.iterrows():
        symbol = _symbol_from_test(row.get("test"))
        period = str(row.get("period"))
        if not symbol:
            errors.append(f"unparseable_test={row.get('test')}")
            continue
        match = (
            controlled_flags["entity"].astype(str).eq(symbol)
            & controlled_flags["period"].astype(str).eq(period)
            & controlled_flags["area"].astype(str).eq(str(row.get("area")))
        ) if len(controlled_flags) else pd.Series(dtype=bool)
        if not len(controlled_flags) or not bool(match.any()):
            errors.append(f"missing_controlled_flag={symbol}:{period}:{row.get('area')}")
        if not str(row.get("notes", "")).strip():
            errors.append(f"missing_controlled_notes={symbol}:{period}:{row.get('area')}")
    return not errors, errors
