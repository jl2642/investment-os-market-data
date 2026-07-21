from __future__ import annotations

import hashlib
import json
import math
import re
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


FINANCIAL_TITLE_PATTERNS = (
    "ANNUAL REPORT",
    "ANNUAL RESULTS",
    "FINAL RESULTS",
    "PRELIMINARY RESULTS",
    "INTERIM REPORT",
    "INTERIM RESULTS",
    "HALF-YEAR",
    "HALF YEAR",
    "QUARTERLY RESULTS",
    "FIRST QUARTER RESULTS",
    "THIRD QUARTER RESULTS",
    "FINANCIAL STATEMENTS",
    "RESULTS ANNOUNCEMENT",
)
REVISION_TITLE_PATTERNS = ("REVISED", "UPDATED", "CORRECTION", "SUPPLEMENTAL", "CLARIFICATION")
MONTHS = {
    "JANUARY": 1,
    "FEBRUARY": 2,
    "MARCH": 3,
    "APRIL": 4,
    "MAY": 5,
    "JUNE": 6,
    "JULY": 7,
    "AUGUST": 8,
    "SEPTEMBER": 9,
    "OCTOBER": 10,
    "NOVEMBER": 11,
    "DECEMBER": 12,
}


def stable_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def normalize_token(value: Any) -> str:
    text = str(value or "").upper().strip()
    text = text.replace("&", "AND")
    return re.sub(r"[\s_\-—–,，。．、:：;；()（）\[\]【】/\\]+", "", text)


def load_field_registry(path: Path) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for field in payload["fields"]:
        for alias in field["aliases"]:
            key = (field["statement"], normalize_token(alias))
            if key in index and index[key]["field_id"] != field["field_id"]:
                raise ValueError(f"DUPLICATE_ALIAS:{key}")
            index[key] = field
    return index, payload


def map_line_item(
    statement: str,
    source_item_code: Any,
    source_item_name: Any,
    registry: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any] | None:
    for candidate in (source_item_code, source_item_name):
        mapped = registry.get((statement, normalize_token(candidate)))
        if mapped:
            return mapped
    return None


def apply_sign(value: float, rule: str) -> float:
    if rule == "POSITIVE_ABS":
        return abs(value)
    if rule == "NEGATIVE_ABS":
        return -abs(value)
    return value


def is_financial_filing(title: str, category: str = "") -> bool:
    haystack = f"{title} {category}".upper()
    return any(pattern in haystack for pattern in FINANCIAL_TITLE_PATTERNS)


def classify_filing(title: str, category: str = "") -> tuple[str, bool]:
    haystack = f"{title} {category}".upper()
    revised = any(pattern in haystack for pattern in REVISION_TITLE_PATTERNS)
    if "ANNUAL REPORT" in haystack:
        return "ANNUAL_REPORT", revised
    if any(pattern in haystack for pattern in ("ANNUAL RESULTS", "FINAL RESULTS", "PRELIMINARY RESULTS")):
        return "ANNUAL_RESULTS", revised
    if "INTERIM REPORT" in haystack or "HALF-YEAR REPORT" in haystack or "HALF YEAR REPORT" in haystack:
        return "INTERIM_REPORT", revised
    if "INTERIM RESULTS" in haystack or "HALF-YEAR RESULTS" in haystack or "HALF YEAR RESULTS" in haystack:
        return "INTERIM_RESULTS", revised
    if "QUARTER" in haystack and "RESULT" in haystack:
        return "QUARTERLY_RESULTS", revised
    return "FINANCIAL_STATEMENTS", revised


def parse_period_end_from_title(title: str) -> str | None:
    upper = title.upper().replace(",", " ")
    patterns = (
        r"(?:ENDED|AS AT|AT)\s+(\d{1,2})\s+(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+(20\d{2})",
        r"(?:ENDED|AS AT|AT)\s+(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+(\d{1,2})\s+(20\d{2})",
    )
    first = re.search(patterns[0], upper)
    if first:
        day, month_name, year = first.groups()
        try:
            return date(int(year), MONTHS[month_name], int(day)).isoformat()
        except ValueError:
            return None
    second = re.search(patterns[1], upper)
    if second:
        month_name, day, year = second.groups()
        try:
            return date(int(year), MONTHS[month_name], int(day)).isoformat()
        except ValueError:
            return None
    compact = re.search(r"(?:ENDED|AS AT|AT)\s+(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})", upper)
    if compact:
        year, month, day = compact.groups()
        try:
            return date(int(year), int(month), int(day)).isoformat()
        except ValueError:
            return None
    return None


def next_trading_open(announcement_date: str, trading_days: list[date], timezone_offset: str = "+08:00") -> str | None:
    announced = pd.Timestamp(announcement_date).date()
    position = bisect_right(trading_days, announced)
    if position >= len(trading_days):
        return None
    return f"{trading_days[position].isoformat()}T09:30:00{timezone_offset}"


def infer_profile(item_names: Iterable[str], official_name: str = "") -> str:
    tokens = " ".join(str(item) for item in item_names).upper()
    name = official_name.upper()
    if any(token in tokens for token in ("保险合同负债", "保险合约负债", "INSURANCE CONTRACT", "已赚保费", "保险服务收入")):
        return "INSURANCE"
    if any(token in tokens for token in ("客户存款", "吸收存款", "客户贷款及垫款", "NET INTEREST INCOME", "利息净收入")):
        return "BANK"
    if any(token in tokens for token in ("经纪佣金", "证券经纪", "承销", "BROKERAGE", "UNDERWRITING")):
        return "SECURITIES_AND_BROKERAGE"
    if "REIT" in name or "房托" in name:
        return "REIT"
    return "GENERAL_NON_FINANCIAL"


def _fiscal_month_day(fiscal_year: Any) -> tuple[int, int] | None:
    text = str(fiscal_year or "").strip()
    match = re.search(r"(\d{1,2})[-/](\d{1,2})", text)
    if not match:
        return None
    month, day = map(int, match.groups())
    try:
        date(2000, month, day)
    except ValueError:
        return None
    return month, day


def assign_filing_periods(
    filings: list[dict[str, Any]],
    periods_by_code: dict[str, list[str]],
    fiscal_year_end_by_code: dict[str, str | None],
    trading_days: list[date],
) -> list[dict[str, Any]]:
    assigned: list[dict[str, Any]] = []
    for filing in filings:
        row = dict(filing)
        code = row["stock_code_5d"]
        release_date = pd.Timestamp(row["release_timestamp"]).date()
        periods = sorted({pd.Timestamp(value).date() for value in periods_by_code.get(code, [])})
        filing_type, revised = classify_filing(row.get("title", ""), row.get("category", ""))
        explicit = parse_period_end_from_title(row.get("title", ""))
        selected: date | None = None
        basis = "UNMATCHED"
        if explicit:
            target = pd.Timestamp(explicit).date()
            close = sorted(periods, key=lambda value: abs((value - target).days))
            if close and abs((close[0] - target).days) <= 31:
                selected = close[0]
                basis = "TITLE_EXPLICIT_DATE"
        if selected is None and periods:
            fiscal_md = _fiscal_month_day(fiscal_year_end_by_code.get(code))
            candidates = [value for value in periods if value < release_date]
            if filing_type.startswith("ANNUAL") and fiscal_md:
                candidates = [value for value in candidates if (value.month, value.day) == fiscal_md]
                max_lag = 270
            elif filing_type.startswith("INTERIM"):
                if fiscal_md:
                    annual = {value for value in candidates if (value.month, value.day) == fiscal_md}
                    candidates = [value for value in candidates if value not in annual]
                max_lag = 210
            elif filing_type == "QUARTERLY_RESULTS":
                max_lag = 150
            else:
                max_lag = 270
            candidates = [value for value in candidates if 0 <= (release_date - value).days <= max_lag]
            if candidates:
                selected = max(candidates)
                basis = "TYPE_AND_FISCAL_CALENDAR_MATCH"
        row["filing_type"] = filing_type
        row["revision_signal"] = revised
        row["report_period_end"] = selected.isoformat() if selected else None
        row["period_match_basis"] = basis
        row["available_from"] = next_trading_open(release_date.isoformat(), trading_days)
        row["filing_id"] = stable_hash(
            {
                "news_id": row.get("news_id"),
                "stock_code_5d": code,
                "release_timestamp": row.get("release_timestamp"),
                "url": row.get("filing_url"),
            }
        )
        assigned.append(row)

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in assigned:
        if row.get("report_period_end"):
            groups[(row["stock_code_5d"], row["report_period_end"])].append(row)
    for group in groups.values():
        group.sort(key=lambda item: (item["release_timestamp"], item.get("news_id", "")))
        for sequence, item in enumerate(group, start=1):
            item["revision_sequence"] = sequence
            item["superseded_at"] = group[sequence]["available_from"] if sequence < len(group) else None
    for row in assigned:
        row.setdefault("revision_sequence", None)
        row.setdefault("superseded_at", None)
    return assigned


def latest_filing_map(filings: Iterable[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in filings:
        period = row.get("report_period_end")
        if not period:
            continue
        key = (row["stock_code_5d"], period)
        current = result.get(key)
        if current is None or (row.get("revision_sequence") or 0) >= (current.get("revision_sequence") or 0):
            result[key] = row
    return result


def normalize_raw_facts(
    raw_rows: list[dict[str, Any]],
    latest_filings: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in raw_rows:
        grouped[(row["security_id"], row["statement"], row["period_end"], row["field_id"])].append(row)
    normalized: list[dict[str, Any]] = []
    for key, group in grouped.items():
        group.sort(key=lambda item: (item.get("mapping_priority", 999), item.get("source_item_code", ""), item.get("source_item_name", "")))
        selected = dict(group[0])
        values = {round(float(item["source_value"]), 8) for item in group}
        conflict = len(values) > 1
        filing = latest_filings.get((selected["stock_code_5d"], selected["period_end"]))
        selected["normalized_value"] = apply_sign(float(selected["source_value"]), selected["sign_rule"])
        selected["official_filing_id"] = filing.get("filing_id") if filing else None
        selected["official_filing_url"] = filing.get("filing_url") if filing else None
        selected["announcement_timestamp"] = filing.get("release_timestamp") if filing else None
        selected["available_from"] = filing.get("available_from") if filing else None
        selected["revision_sequence"] = filing.get("revision_sequence") if filing else None
        selected["conflict_status"] = "MULTIPLE_VENDOR_ROWS_DIFFER" if conflict else "NONE"
        selected["record_quality"] = (
            "CONFLICTED_AUDIT_ONLY" if conflict else "VALID_PIT_MATCHED" if filing and filing.get("available_from") else "BLOCKED_NO_OFFICIAL_PIT_MATCH"
        )
        selected["decision_grade_eligible"] = bool(not conflict and filing and filing.get("available_from"))
        selected["trade_authority"] = "NONE"
        selected["normalized_fact_id"] = stable_hash(
            {
                "security_id": key[0],
                "statement": key[1],
                "period_end": key[2],
                "field_id": key[3],
                "source_id": selected["source_id"],
                "revision_sequence": selected["revision_sequence"],
            }
        )
        normalized.append(selected)
    return normalized


def count_duplicate_keys(frame: pd.DataFrame, keys: list[str]) -> int:
    if frame.empty:
        return 0
    return int(frame.duplicated(keys, keep=False).sum())


def build_unmapped_catalog(unmapped: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[tuple[str, str, str]] = Counter()
    for row in unmapped:
        counter[(row["statement"], row.get("source_item_code", ""), row.get("source_item_name", ""))] += 1
    return [
        {
            "statement": statement,
            "source_item_code": source_code,
            "source_item_name": source_name,
            "occurrence_count": count,
        }
        for (statement, source_code, source_name), count in counter.most_common()
    ]
