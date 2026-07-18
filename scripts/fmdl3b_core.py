from __future__ import annotations

import hashlib
import json
import math
import re
from bisect import bisect_right
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import pandas as pd

TZ = ZoneInfo("Asia/Shanghai")
DATE_FIELDS = {"REPORT_DATE", "报告日", "NOTICE_DATE", "UPDATE_DATE", "SECURITY_CODE", "SECUCODE", "ORG_CODE", "SECURITY_NAME_ABBR"}


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def stable_hash(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def code(symbol: str) -> str:
    return symbol.split(".")[0]


def em_symbol(symbol: str) -> str:
    c, exchange = symbol.split(".")
    return f"{exchange}{c}"


def sina_symbol(symbol: str) -> str:
    return em_symbol(symbol).lower()


def normalize_alias(value: Any) -> str:
    return re.sub(r"[\s_\-（）()：:]", "", str(value)).upper()


def load_registry(path: Path) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for field in payload["fields"]:
        for alias in field["aliases"]:
            index[(field["statement"], normalize_alias(alias))] = field
    return index, payload


def map_field(statement: str, source_field: str, registry: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any] | None:
    return registry.get((statement, normalize_alias(source_field)))


def apply_sign(value: float, rule: str) -> float:
    if rule == "POSITIVE_ABS":
        return abs(value)
    if rule == "NEGATIVE_ABS":
        return -abs(value)
    return value


def fiscal_period_type(period_end: str) -> tuple[str, str, str]:
    value = pd.Timestamp(period_end)
    md = value.strftime("%m-%d")
    if md == "03-31":
        return "Q1", "ytd", f"Q1-{value.year}"
    if md == "06-30":
        return "H1", "ytd", f"H1-{value.year}"
    if md == "09-30":
        return "Q3", "ytd", f"Q3YTD-{value.year}"
    if md == "12-31":
        return "FY", "annual", f"FY{value.year}"
    return "STUB", "ytd", value.date().isoformat()


def next_trading_open(announcement_date: str, trading_days: list[date], market_open: str = "09:30:00") -> str | None:
    announced = pd.Timestamp(announcement_date).date()
    position = bisect_right(trading_days, announced)
    if position >= len(trading_days):
        return None
    return f"{trading_days[position].isoformat()}T{market_open}+08:00"


def build_revision_intervals(filings: list[dict[str, Any]], trading_days: list[date], market_open: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for filing in filings:
        groups.setdefault((filing["symbol"], filing["report_period_end"]), []).append(dict(filing))
    for (symbol, period), group in groups.items():
        group.sort(key=lambda item: (item["announcement_timestamp_raw"], item.get("filing_title", "")))
        prepared: list[dict[str, Any]] = []
        for sequence, item in enumerate(group, start=1):
            available = next_trading_open(item["announcement_date"], trading_days, market_open)
            item["revision_sequence"] = sequence
            item["available_from"] = available
            item["effective_from"] = available
            prepared.append(item)
        for idx, item in enumerate(prepared):
            item["superseded_at"] = prepared[idx + 1]["available_from"] if idx + 1 < len(prepared) else None
            item["structured_value_status"] = "CURRENT_PROVIDER_VALUE_BOUND_TO_LATEST_REVISION" if idx + 1 == len(prepared) else "DOCUMENT_ONLY_PRIOR_REVISION_NO_HISTORICAL_STRUCTURED_VALUE"
            item["revision_id"] = stable_hash({"symbol": symbol, "period": period, "sequence": item["revision_sequence"], "title": item.get("filing_title"), "announcement": item.get("announcement_timestamp_raw")})
            rows.append(item)
    return rows


def latest_revision_map(revision_rows: Iterable[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in revision_rows:
        key = (row["symbol"], row["report_period_end"])
        if key not in result or int(row["revision_sequence"]) > int(result[key]["revision_sequence"]):
            result[key] = row
    return result


def numeric_columns(frame: pd.DataFrame) -> list[str]:
    result: list[str] = []
    for column in frame.columns:
        if str(column) in DATE_FIELDS:
            continue
        converted = pd.to_numeric(frame[column], errors="coerce")
        if converted.notna().any():
            result.append(str(column))
    return result


def extract_raw_facts(
    frame: pd.DataFrame,
    sample: dict[str, Any],
    statement: str,
    source_id: str,
    source_route_id: str,
    source_adapter: str,
    source_rank: str,
    source_retrieved_at: str,
    latest_revisions: dict[tuple[str, str], dict[str, Any]],
    minimum_period: str,
    maximum_periods: int,
    registry: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    report_col = "REPORT_DATE" if "REPORT_DATE" in frame.columns else ("报告日" if "报告日" in frame.columns else None)
    if not report_col:
        return []
    prepared = frame.copy()
    prepared["__period"] = pd.to_datetime(prepared[report_col], errors="coerce")
    prepared = prepared[prepared["__period"].notna() & (prepared["__period"] >= pd.Timestamp(minimum_period))]
    prepared = prepared.sort_values("__period", ascending=False).head(maximum_periods)
    fields = numeric_columns(prepared)
    rows: list[dict[str, Any]] = []
    for _, record in prepared.iterrows():
        period = record["__period"].date().isoformat()
        revision = latest_revisions.get((sample["symbol"], period))
        for field in fields:
            value = pd.to_numeric(pd.Series([record.get(field)]), errors="coerce").iloc[0]
            if pd.isna(value):
                continue
            mapping = map_field(statement, field, registry)
            payload = {
                "symbol": sample["symbol"],
                "entity": sample["name"],
                "profile": sample["profile"],
                "board": sample["board"],
                "statement": statement,
                "report_period_end": period,
                "source_id": source_id,
                "source_name": source_route_id,
                "source_route_id": source_route_id,
                "source_type": "provider_export",
                "source_rank": source_rank,
                "source_adapter": source_adapter,
                "source_location": f"{source_adapter}:{sample['symbol']}:{statement}:{period}:{field}",
                "source_retrieved_at": source_retrieved_at,
                "provider_field_name": field,
                "source_value": float(value),
                "source_units": mapping.get("units", "CNY_ONES") if mapping else "PROVIDER_NATIVE_UNKNOWN",
                "currency": "CNY",
                "canonical_field_id": mapping["line_item_id"] if mapping else None,
                "canonical_field_name": mapping["line_item_standard"] if mapping else None,
                "mapping_status": "MAPPED_EXACT_ALIAS" if mapping else "UNMAPPED_RAW_ONLY",
                "evidence_label": "fact_provider_standardized",
                "confidence": "high" if source_route_id == "EASTMONEY_STATEMENTS" else "medium",
                "announcement_date": revision.get("announcement_date") if revision else None,
                "announcement_timestamp_raw": revision.get("announcement_timestamp_raw") if revision else None,
                "available_from": revision.get("available_from") if revision else None,
                "revision_sequence": revision.get("revision_sequence") if revision else None,
                "effective_from": revision.get("effective_from") if revision else None,
                "superseded_at": revision.get("superseded_at") if revision else None,
                "official_filing_source_id": revision.get("source_id") if revision else None,
                "official_filing_link": revision.get("filing_link") if revision else None,
                "record_quality": "VALID_PIT_MATCHED" if revision else "BLOCKED_NO_OFFICIAL_PIT_MATCH",
                "decision_grade_eligible": bool(revision and mapping),
                "trade_authority": "NONE"
            }
            payload["raw_fact_id"] = stable_hash({key: payload[key] for key in ["symbol","statement","report_period_end","source_id","provider_field_name","revision_sequence"]})
            rows.append(payload)
    return rows


def relative_close(a: float, b: float, rel_tol: float, abs_tol: float) -> bool:
    return math.isclose(float(a), float(b), rel_tol=rel_tol, abs_tol=abs_tol)


def select_normalized_facts(raw: pd.DataFrame, registry_payload: dict[str, Any], rel_tol: float, abs_tol: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    if raw.empty:
        return pd.DataFrame(), pd.DataFrame()
    mapped = raw[raw["canonical_field_id"].notna()].copy()
    conflicts: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    field_by_id = {field["line_item_id"]: field for field in registry_payload["fields"]}
    key_cols = ["symbol", "statement", "report_period_end", "canonical_field_id"]
    for key, group in mapped.groupby(key_cols, dropna=False):
        preferred = group[group["source_route_id"] == "EASTMONEY_STATEMENTS"]
        fallback = group[group["source_route_id"] == "SINA_STATEMENTS"]
        selected = preferred.iloc[0] if len(preferred) else fallback.iloc[0]
        conflict_status = "NONE"
        if len(preferred) and len(fallback):
            a = float(preferred.iloc[0]["source_value"])
            b = float(fallback.iloc[0]["source_value"])
            if not relative_close(a, b, rel_tol, abs_tol):
                conflict_status = "CONTROLLED_EXCLUSION"
                conflicts.append({
                    "conflict_id": stable_hash({"key": list(key), "a": a, "b": b}),
                    "entity": selected["entity"], "symbol": key[0], "metric": key[3], "period": key[2],
                    "source_a": "EASTMONEY_STATEMENTS", "value_a": a,
                    "source_b": "SINA_STATEMENTS", "value_b": b,
                    "conflict_type": "MATERIAL_PROVIDER_VALUE_DIFFERENCE",
                    "working_value": None,
                    "resolution_basis": "CONTROLLED_EXCLUSION_FROM_DECISION_GRADE_CURRENT",
                    "open_question": "Reconcile against official filing document in later hardening pass.",
                    "status": "CLASSIFIED_CONTROLLED_EXCLUSION",
                    "trade_authority": "NONE"
                })
        field = field_by_id[key[3]]
        fiscal_type, period_type, period_label = fiscal_period_type(key[2])
        normalized_value = apply_sign(float(selected["source_value"]), field.get("sign_rule", "AS_REPORTED"))
        row = {
            "entity": selected["entity"], "symbol": key[0], "profile": selected["profile"], "board": selected["board"],
            "source_id": selected["source_id"], "source_route_id": selected["source_route_id"], "statement": key[1],
            "line_item_original": selected["provider_field_name"], "line_item_standard": selected["canonical_field_name"],
            "line_item_id": key[3], "period_end": key[2], "period_label": period_label,
            "period_type": period_type, "fiscal_period_type": fiscal_type, "basis": "reported_cumulative_ytd" if period_type == "ytd" else "reported_annual",
            "currency": selected["currency"], "units": field.get("units", registry_payload["default_units"]),
            "source_value": float(selected["source_value"]), "normalized_value": normalized_value,
            "normalization_method": "mapped_and_sign_normalized" if field.get("sign_rule") != "AS_REPORTED" else "mapped_as_reported",
            "source_location": selected["source_location"], "evidence_label": selected["evidence_label"],
            "confidence": selected["confidence"] if conflict_status == "NONE" else "low",
            "normalization_note": f"preferred_route={selected['source_route_id']}; conflict_status={conflict_status}",
            "announcement_date": selected["announcement_date"], "announcement_timestamp_raw": selected["announcement_timestamp_raw"],
            "available_from": selected["available_from"], "source_retrieved_at": selected["source_retrieved_at"],
            "revision_sequence": selected["revision_sequence"], "effective_from": selected["effective_from"], "superseded_at": selected["superseded_at"],
            "record_quality": "VALID" if conflict_status == "NONE" else "CONFLICTED_AUDIT_ONLY",
            "decision_grade_eligible": conflict_status == "NONE" and bool(selected["available_from"]),
            "comparison_status": "comparable" if conflict_status == "NONE" else "not_comparable",
            "model_treatment": "LOADABLE_ACTUAL" if conflict_status == "NONE" else "AUDIT_ONLY_PENDING_OFFICIAL_RECONCILIATION",
            "trade_authority": "NONE"
        }
        row["normalized_fact_id"] = stable_hash({key: row[key] for key in ["symbol","statement","line_item_id","period_end","source_id","revision_sequence"]})
        normalized.append(row)
    return pd.DataFrame(normalized), pd.DataFrame(conflicts)


def duplicate_effective_intervals(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    keys = ["symbol","statement","line_item_id","period_end","effective_from","superseded_at"]
    return int(frame.duplicated(keys, keep=False).sum())
