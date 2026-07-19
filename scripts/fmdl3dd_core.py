from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def as_date(value: Any) -> str | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def as_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if text in {"", "--", "-", "None", "nan"}:
            return None
        match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
        if not match:
            return None
        text = match.group(0)
        value = text
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def first_value(row: pd.Series, names: list[str]) -> Any:
    for name in names:
        if name in row.index:
            value = row.get(name)
            if value is not None and not pd.isna(value):
                return value
    return None


def normalize_dividend_frame(
    symbol: str,
    name: str | None,
    frame: pd.DataFrame,
    retrieved_at: str,
    cfg: dict[str, Any],
) -> pd.DataFrame:
    columns = [
        "event_id", "symbol", "name", "event_type", "event_stage",
        "announcement_date", "effective_date", "report_period",
        "cash_amount_per_share", "cash_amount_total_cny", "prior_total_shares",
        "post_total_shares", "share_change_count", "share_change_ratio",
        "event_state", "share_count_effective", "shareholder_yield_effective",
        "source_id", "source_adapter", "source_document_id", "source_location",
        "retrieved_at", "source_row_hash", "raw_fields_json", "authority",
        "trade_authority"
    ]
    if frame is None or frame.empty:
        return pd.DataFrame(columns=columns)
    implemented_tokens = tuple(cfg["dividend_policy"]["implemented_stage_tokens"])
    basis = float(cfg["dividend_policy"]["cash_ratio_basis_shares"])
    rows: list[dict[str, Any]] = []
    for _, source_row in frame.iterrows():
        raw = {
            str(key): (None if pd.isna(value) else value)
            for key, value in source_row.to_dict().items()
        }
        progress = str(first_value(source_row, ["方案进度", "进度", "状态", "分配状态"]) or "")
        cash_ratio = as_number(first_value(source_row, [
            "现金分红-现金分红比例", "现金分红比例", "派息比例", "每10股派息"
        ]))
        report_period = as_date(first_value(source_row, ["报告期", "报告日期"]))
        announcement_date = as_date(first_value(source_row, [
            "公告日期", "预案公告日", "业绩披露日期", "董事会日期"
        ]))
        effective_date = None
        for field in cfg["dividend_policy"]["implementation_date_priority"]:
            effective_date = as_date(first_value(source_row, [field]))
            if effective_date:
                break
        implemented = any(token in progress for token in implemented_tokens)
        if not implemented and effective_date:
            implemented = True
        if not announcement_date:
            announcement_date = effective_date or report_period
        if not effective_date:
            effective_date = announcement_date or report_period
        if not announcement_date or not effective_date:
            continue
        if cash_ratio is None or cash_ratio <= 0:
            event_state = "NON_CASH_DISTRIBUTION"
            cash_per_share = None
            yield_effective = False
        elif implemented:
            event_state = "VALID"
            cash_per_share = cash_ratio / basis
            yield_effective = True
        else:
            event_state = "VALID_WITH_WARNING"
            cash_per_share = cash_ratio / basis
            yield_effective = False
        event_stage = "IMPLEMENTED" if implemented else "ANNOUNCED"
        source_document_id = stable_hash({
            "symbol": symbol,
            "report_period": report_period,
            "announcement_date": announcement_date,
            "effective_date": effective_date,
            "progress": progress,
            "cash_ratio": cash_ratio,
        })
        source_row_hash = stable_hash(raw)
        event_id = stable_hash({
            "symbol": symbol,
            "event_type": "CASH_DIVIDEND",
            "event_stage": event_stage,
            "report_period": report_period,
            "effective_date": effective_date,
            "cash_per_share": cash_per_share,
            "source_row_hash": source_row_hash,
        })
        rows.append({
            "event_id": event_id,
            "symbol": symbol,
            "name": name,
            "event_type": "CASH_DIVIDEND",
            "event_stage": event_stage,
            "announcement_date": announcement_date,
            "effective_date": effective_date,
            "report_period": report_period,
            "cash_amount_per_share": cash_per_share,
            "cash_amount_total_cny": None,
            "prior_total_shares": None,
            "post_total_shares": None,
            "share_change_count": None,
            "share_change_ratio": None,
            "event_state": event_state,
            "share_count_effective": False,
            "shareholder_yield_effective": bool(yield_effective),
            "source_id": cfg["source"]["dividend_source_id"],
            "source_adapter": cfg["source"]["dividend_source_adapter"],
            "source_document_id": source_document_id,
            "source_location": f"https://data.eastmoney.com/yjfp/detail/{symbol[:6]}.html",
            "retrieved_at": retrieved_at,
            "source_row_hash": source_row_hash,
            "raw_fields_json": json.dumps(raw, ensure_ascii=False, sort_keys=True, default=str),
            "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
            "trade_authority": "NONE",
        })
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows)[columns].drop_duplicates("event_id").reset_index(drop=True)


def contains_any(text: str, tokens: list[str]) -> bool:
    normalized = str(text or "").lower()
    return any(str(token).lower() in normalized for token in tokens)


def classify_share_change(reason: str, change: float, policy: dict[str, Any]) -> tuple[str, str, bool]:
    if abs(change) < float(policy["minimum_absolute_share_change"]):
        return "UNCLASSIFIED_SHARE_CHANGE", "UNCLASSIFIED_SHARE_CHANGE", False
    if contains_any(reason, policy["neutral_rescaling_tokens"]):
        return "STOCK_DIVIDEND_OR_SPLIT", "VALID", False
    if change < 0 and contains_any(reason, policy["buyback_or_cancellation_tokens"]):
        return "SHARE_CANCELLATION", "VALID", True
    if change > 0 and contains_any(reason, policy["private_placement_tokens"]):
        return "PRIVATE_PLACEMENT", "VALID", True
    if change > 0 and contains_any(reason, policy["rights_issue_tokens"]):
        return "RIGHTS_ISSUE", "VALID", True
    if change > 0 and contains_any(reason, policy["convertible_conversion_tokens"]):
        return "CONVERTIBLE_CONVERSION", "VALID", True
    if change > 0 and contains_any(reason, policy["equity_incentive_tokens"]):
        return "EQUITY_INCENTIVE_ISSUANCE", "VALID", True
    return "UNCLASSIFIED_SHARE_CHANGE", "UNCLASSIFIED_SHARE_CHANGE", False


def derive_share_change_events(
    ledger: pd.DataFrame,
    cfg: dict[str, Any],
    market_as_of_date: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    market_date = pd.Timestamp(market_as_of_date)
    for symbol, group in ledger.groupby("symbol", sort=False):
        ordered = group.copy()
        ordered["source_effective_date"] = pd.to_datetime(ordered["source_effective_date"], errors="coerce")
        ordered = ordered.dropna(subset=["source_effective_date", "total_shares"])
        ordered = ordered.sort_values(["source_effective_date", "total_shares"]).drop_duplicates(
            ["source_effective_date"], keep="last"
        )
        prior = None
        for row in ordered.itertuples(index=False):
            current_shares = float(row.total_shares)
            effective_date = pd.Timestamp(row.source_effective_date)
            if prior is None:
                prior = row
                continue
            prior_shares = float(prior.total_shares)
            change = current_shares - prior_shares
            if abs(change) < float(cfg["share_change_policy"]["minimum_absolute_share_change"]):
                prior = row
                continue
            reason = str(getattr(row, "change_reason", "") or "")
            event_type, event_state, yield_effective = classify_share_change(
                reason, change, cfg["share_change_policy"]
            )
            future = effective_date > market_date
            if future:
                event_state = "FUTURE_EVENT_BLOCKED"
                yield_effective = False
            share_ratio = change / prior_shares if prior_shares > 0 else None
            raw = {
                "prior_source_row_hash": getattr(prior, "source_row_hash", None),
                "post_source_row_hash": getattr(row, "source_row_hash", None),
                "change_reason": reason,
            }
            event_id = stable_hash({
                "symbol": symbol,
                "event_type": event_type,
                "effective_date": effective_date.date().isoformat(),
                "prior_total_shares": prior_shares,
                "post_total_shares": current_shares,
                "source_row_hash": getattr(row, "source_row_hash", None),
            })
            rows.append({
                "event_id": event_id,
                "symbol": str(symbol),
                "name": getattr(row, "name", None),
                "event_type": event_type,
                "event_stage": "COMPLETED" if event_type != "STOCK_DIVIDEND_OR_SPLIT" else "IMPLEMENTED",
                "announcement_date": effective_date.date().isoformat(),
                "effective_date": effective_date.date().isoformat(),
                "report_period": None,
                "cash_amount_per_share": None,
                "cash_amount_total_cny": None,
                "prior_total_shares": prior_shares,
                "post_total_shares": current_shares,
                "share_change_count": change,
                "share_change_ratio": share_ratio,
                "event_state": event_state,
                "share_count_effective": not future,
                "shareholder_yield_effective": bool(yield_effective and not future),
                "source_id": cfg["source"]["share_change_source_id"],
                "source_adapter": cfg["source"]["share_change_source_adapter"],
                "source_document_id": getattr(row, "source_row_hash", None),
                "source_location": None,
                "retrieved_at": str(getattr(row, "retrieved_at", datetime.utcnow().isoformat() + "Z")),
                "source_row_hash": stable_hash(raw),
                "raw_fields_json": json.dumps(raw, ensure_ascii=False, sort_keys=True, default=str),
                "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
                "trade_authority": "NONE",
            })
            prior = row
    return pd.DataFrame(rows)


def shares_at_date(ledger_group: pd.DataFrame, event_date: str) -> float | None:
    date = pd.Timestamp(event_date)
    eligible = ledger_group[
        pd.to_datetime(ledger_group["source_effective_date"], errors="coerce") <= date
    ].copy()
    eligible = eligible[pd.to_numeric(eligible["total_shares"], errors="coerce") > 0]
    if eligible.empty:
        return None
    eligible["_date"] = pd.to_datetime(eligible["source_effective_date"], errors="coerce")
    return float(eligible.sort_values("_date").iloc[-1]["total_shares"])


def build_shareholder_return_current(
    capitalization: pd.DataFrame,
    dividend_attempts: pd.DataFrame,
    events: pd.DataFrame,
    ledger: pd.DataFrame,
    cfg: dict[str, Any],
    release_ids: dict[str, str],
) -> pd.DataFrame:
    market_date = pd.Timestamp(capitalization["price_as_of_date"].dropna().astype(str).max())
    start = market_date - pd.Timedelta(days=int(cfg["source"]["ttm_days"]))
    events = events.copy()
    events["effective_date_ts"] = pd.to_datetime(events["effective_date"], errors="coerce")
    ttm = events[(events["effective_date_ts"] > start) & (events["effective_date_ts"] <= market_date)]
    event_groups = {str(k): v for k, v in ttm.groupby("symbol", sort=False)}
    attempt_index = dividend_attempts.set_index("symbol", drop=False)
    ledger_groups = {str(k): v for k, v in ledger.groupby("symbol", sort=False)}
    rows: list[dict[str, Any]] = []
    for cap in capitalization.itertuples(index=False):
        symbol = str(cap.symbol)
        group = event_groups.get(symbol, pd.DataFrame())
        dividends = group[
            group.get("event_type", pd.Series(dtype=str)).eq("CASH_DIVIDEND")
            & group.get("shareholder_yield_effective", pd.Series(dtype=bool)).eq(True)
        ] if len(group) else pd.DataFrame()
        buybacks = group[
            group.get("event_type", pd.Series(dtype=str)).isin(["BUYBACK", "SHARE_CANCELLATION"])
            & group.get("shareholder_yield_effective", pd.Series(dtype=bool)).eq(True)
        ] if len(group) else pd.DataFrame()
        issuances = group[
            group.get("event_type", pd.Series(dtype=str)).isin([
                "PRIVATE_PLACEMENT", "RIGHTS_ISSUE", "CONVERTIBLE_CONVERSION", "EQUITY_INCENTIVE_ISSUANCE"
            ])
            & group.get("shareholder_yield_effective", pd.Series(dtype=bool)).eq(True)
        ] if len(group) else pd.DataFrame()
        cash_per_share = float(pd.to_numeric(dividends.get("cash_amount_per_share", pd.Series(dtype=float)), errors="coerce").sum())
        buyback_yield = float((-pd.to_numeric(buybacks.get("share_change_ratio", pd.Series(dtype=float)), errors="coerce")).clip(lower=0).sum())
        issuance_yield = float(pd.to_numeric(issuances.get("share_change_ratio", pd.Series(dtype=float)), errors="coerce").clip(lower=0).sum())
        attempt = attempt_index.loc[symbol] if symbol in attempt_index.index else None
        dividend_source_state = str(attempt["source_state"]) if attempt is not None else "NO_ATTEMPT_RECORD"
        share_ledger_state = "AVAILABLE" if symbol in ledger_groups and len(ledger_groups[symbol]) else "MISSING"
        close = as_number(getattr(cap, "close", None))
        total_shares = as_number(getattr(cap, "total_shares", None))
        total_market_cap = as_number(getattr(cap, "total_market_cap_cny", None))
        dividend_yield = cash_per_share / close if close and close > 0 and dividend_source_state in {"SUCCESS", "SUCCESS_EMPTY"} else None
        total_cash = cash_per_share * total_shares if total_shares and cash_per_share >= 0 else None
        complete = dividend_source_state in {"SUCCESS", "SUCCESS_EMPTY"} and share_ledger_state == "AVAILABLE" and close is not None and close > 0
        shareholder_yield = dividend_yield + buyback_yield - issuance_yield if complete and dividend_yield is not None else None
        if complete:
            state = "COMPLETE"
        elif dividend_yield is not None or share_ledger_state == "AVAILABLE":
            state = "PARTIAL"
        else:
            state = "UNAVAILABLE"
        lineage_ids = list(group.get("event_id", pd.Series(dtype=str)).astype(str)) if len(group) else []
        rows.append({
            "symbol": symbol,
            "name": getattr(cap, "name", None),
            "market_as_of_date": market_date.date().isoformat(),
            "close": close,
            "total_market_cap_cny": total_market_cap,
            "implemented_cash_dividend_per_share_ttm": cash_per_share if dividend_source_state in {"SUCCESS", "SUCCESS_EMPTY"} else None,
            "implemented_cash_dividend_total_cny_ttm": total_cash if dividend_source_state in {"SUCCESS", "SUCCESS_EMPTY"} else None,
            "dividend_yield_ttm": dividend_yield,
            "completed_buyback_yield_ttm": buyback_yield if share_ledger_state == "AVAILABLE" else None,
            "completed_issuance_dilution_yield_ttm": issuance_yield if share_ledger_state == "AVAILABLE" else None,
            "shareholder_yield_ttm": shareholder_yield,
            "dividend_event_count_ttm": int(len(dividends)),
            "buyback_event_count_ttm": int(len(buybacks)),
            "issuance_event_count_ttm": int(len(issuances)),
            "dividend_source_state": dividend_source_state,
            "share_ledger_state": share_ledger_state,
            "shareholder_return_state": state,
            "complete_shareholder_yield": bool(complete),
            "source_release_ids_json": json.dumps(release_ids, sort_keys=True),
            "lineage_ids_json": json.dumps(sorted(lineage_ids)),
            "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
            "trade_authority": "NONE",
        })
    return pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)
