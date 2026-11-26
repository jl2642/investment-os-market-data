from __future__ import annotations

import argparse
import json
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

import akshare as ak
import pandas as pd
import requests

from scripts import fmdl3ebc_core as bc

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATEGORIES = ["财务报告", "信息变更"]


def accepted_baseline_start(pointer: dict, context: dict) -> str:
    """Start at the accepted PIT cutoff, inclusive, not its later publish date."""
    if (pointer.get("status") != "PASS"
        or pointer.get("domain_id") != "FINANCIAL_STATEMENT_CONTEXT"
        or pointer.get("qc_status") != "PASS_FINANCIAL_BASELINE_REBUILT"
        or context.get("status") != "PASS"
        or context.get("qc_status") != pointer.get("qc_status")
        or pointer.get("trade_authority") != "NONE"
        or context.get("trade_authority") != "NONE"):
        raise ValueError("FINANCIAL_BASELINE_NOT_ACCEPTED")
    cutoff = date.fromisoformat(context["market_as_of_date"])
    if cutoff.isoformat() != pointer.get("data_watermark"):
        raise ValueError("FINANCIAL_BASELINE_WATERMARK_MISMATCH")
    if date.fromisoformat(context["financial_report_period_watermark"]) > cutoff:
        raise ValueError("FUTURE_REPORT_PERIOD")
    if not pointer.get("source_commit_sha") or not context.get("releases", {}).get("statement_release_id"):
        raise ValueError("FINANCIAL_BASELINE_LINEAGE_MISSING")
    return cutoff.isoformat()


def notice_columns(frame: pd.DataFrame) -> dict[str, str | None]:
    return {
        name: bc.first_existing(frame.columns, candidates)
        for name, candidates in {
            "code": ["代码", "股票代码", "证券代码"],
            "name": ["名称", "股票简称", "简称"],
            "title": ["公告标题", "标题"],
            "date": ["公告日期", "公告时间", "日期"],
            "url": ["网址", "公告链接", "链接"],
        }.items()
    }


def normalize_notice_frame(frame: pd.DataFrame, *, day: date, category: str, universe: set[str]) -> list[dict]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    cols = notice_columns(frame)
    if not cols["code"] or not cols["title"]:
        return []
    rows: list[dict] = []
    for _, row in frame.iterrows():
        symbol = bc.symbol_from_code(row.get(cols["code"]))
        title = str(row.get(cols["title"]) or "")
        if symbol not in universe or not bc.is_financial_report_title(title):
            continue
        parsed = pd.to_datetime(row.get(cols["date"]), errors="coerce") if cols["date"] else pd.NaT
        effective = parsed.date().isoformat() if pd.notna(parsed) else day.isoformat()
        source = str(row.get(cols["url"]) if cols["url"] else "") or f"akshare.stock_notice_report:{category}:{day.isoformat()}"
        event_id = bc.stable_hash({"symbol": symbol, "title": title, "date": effective, "source": source})
        rows.append({
            "event_id": event_id,
            "symbol": symbol,
            "name": str(row.get(cols["name"]) or symbol) if cols["name"] else symbol,
            "effective_at": effective,
            "period_end": bc.period_end_from_title(title),
            "event_type": bc.classify_financial_title(title),
            "title": title,
            "category": category,
            "source_reference": source,
            "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
            "trade_authority": "NONE",
        })
    return rows


def daterange(start: date, end: date) -> Iterable[date]:
    value = start
    while value <= end:
        yield value
        value += timedelta(days=1)


def confirm_provider_empty(day: date, category: str) -> bool:
    """Confirm AKShare's empty-result KeyError from its existing Eastmoney endpoint.

    A weekend, KeyError, missing payload or HTTP failure alone is not evidence of
    no filings. Only an explicit zero hit count and empty list qualify.
    """
    category_ids = {"财务报告": "1", "信息变更": "4"}
    if category not in category_ids:
        return False
    response = requests.get(
        "https://np-anotice-stock.eastmoney.com/api/security/ann",
        params={"sr": "-1", "page_size": "100", "page_index": "1",
                "ann_type": "A", "client_source": "web", "f_node": category_ids[category],
                "s_node": "0", "begin_time": day.isoformat(), "end_time": day.isoformat()},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("success") not in (True, 1):
        return False
    data = payload.get("data")
    return (isinstance(data, dict) and type(data.get("total_hits")) is int
            and data["total_hits"] == 0 and data.get("list") == [])


def _scan_slot(day: date, category: str, universe: set[str]) -> tuple[list[dict], dict]:
    """An invalid response must not count as an empty successful notice day."""
    frame = None
    confirmed_empty_after_adapter_error = False
    empty_confirmation_attempted = False
    adapter_error_before_confirmation = None
    rows: list[dict] = []
    try:
        frame = ak.stock_notice_report(symbol=category, date=day.strftime("%Y%m%d"))
        if not isinstance(frame, pd.DataFrame):
            raise TypeError("NOTICE_RESPONSE_NOT_DATAFRAME")
        if not frame.empty:
            cols = notice_columns(frame)
            if not cols["code"] or not cols["title"]:
                raise ValueError("NOTICE_RESPONSE_REQUIRED_COLUMNS_MISSING")
        rows = normalize_notice_frame(frame, day=day, category=category, universe=universe)
        state = "SUCCESS_EMPTY" if frame.empty else "SUCCESS"
        error_type = error_message = None
    except Exception as exc:
        state = "FAILED"
        error_type = type(exc).__name__
        error_message = str(exc)[:300]
        rows = []
        if isinstance(exc, KeyError) and exc.args == ("代码",):
            empty_confirmation_attempted = True
            adapter_error_before_confirmation = repr(exc)
            try:
                if confirm_provider_empty(day, category):
                    state = "SUCCESS_EMPTY"
                    error_type = error_message = None
                    frame = pd.DataFrame()
                    confirmed_empty_after_adapter_error = True
            except Exception:
                # Retain the original error and fail closed if confirmation fails.
                pass
    return rows, {
        "date": day.isoformat(),
        "category": category,
        "source_state": state,
        "confirmed_empty_after_adapter_error": confirmed_empty_after_adapter_error,
        "empty_confirmation_attempted": empty_confirmation_attempted,
        "adapter_error_before_confirmation": adapter_error_before_confirmation,
        "source_row_count": int(len(frame)) if isinstance(frame, pd.DataFrame) else 0,
        "financial_event_count": int(len(rows)),
        "error_type": error_type,
        "error_message": error_message,
        "trade_authority": "NONE",
    }


def scan_live(start: date, end: date, universe: set[str], categories: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    events: dict[str, dict] = {}
    attempts: list[dict] = []
    failed: list[tuple[int, date, str]] = []
    for day in daterange(start, end):
        for category in categories:
            rows, attempt = _scan_slot(day, category, universe)
            attempt["attempt_count"] = 1
            attempt["initial_error_type"] = attempt["error_type"]
            attempt["initial_error_message"] = attempt["error_message"]
            if attempt["source_state"] == "FAILED":
                failed.append((len(attempts), day, category))
            attempts.append(attempt)
            for row in rows:
                events[row["event_id"]] = row
    # Recover only failed date/category slots once, after the first pass.
    # Explicit rate limits are not retried; do not turn a provider outage into a retry storm.
    # If all slots failed, do not rescan a fully unavailable source.
    retryable = [(i, day, category) for i, day, category in failed
                 if not attempts[i]["empty_confirmation_attempted"]
                 and attempts[i]["error_type"] not in {"Push2RateLimitError", "RateLimitError"}
                 and "429" not in (attempts[i]["error_message"] or "")
                 and "rate limit" not in (attempts[i]["error_message"] or "").lower()
                 and "限流" not in (attempts[i]["error_message"] or "")]
    if retryable and len(failed) < len(attempts):
        time.sleep(3)
        for i, day, category in retryable:
            rows, attempt = _scan_slot(day, category, universe)
            attempt["attempt_count"] = 2
            attempt["initial_error_type"] = attempts[i]["initial_error_type"]
            attempt["initial_error_message"] = attempts[i]["initial_error_message"]
            attempts[i] = attempt
            for row in rows:
                events[row["event_id"]] = row
    event_frame = pd.DataFrame(list(events.values()))
    if len(event_frame):
        event_frame = event_frame.sort_values(["effective_at", "symbol", "event_id"]).reset_index(drop=True)
    return event_frame, pd.DataFrame(attempts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--universe", default="outputs/current/DAILY_MARKET_SNAPSHOT.csv")
    parser.add_argument("--output-root", default="outputs/occ_r2/financial_backlog_audit")
    args = parser.parse_args()

    start = pd.Timestamp(args.start_date).date()
    end = pd.Timestamp(args.end_date).date()
    if end < start:
        raise SystemExit("END_BEFORE_START")
    universe_frame = pd.read_csv(ROOT / args.universe, encoding="utf-8-sig")
    universe = set(universe_frame["symbol"].dropna().astype(str))
    events, attempts = scan_live(start, end, universe, DEFAULT_CATEGORIES)
    output = ROOT / args.output_root
    output.mkdir(parents=True, exist_ok=True)
    events.to_csv(output / "FINANCIAL_FILING_BACKLOG.csv", index=False, encoding="utf-8-sig")
    attempts.to_csv(output / "NOTICE_SCAN_ATTEMPTS.csv", index=False, encoding="utf-8-sig")

    success = attempts["source_state"].isin(["SUCCESS", "SUCCESS_EMPTY"])
    success_ratio = float(success.mean()) if len(attempts) else 0.0
    affected_symbols = int(events["symbol"].nunique()) if len(events) else 0
    period_counts = {} if not len(events) else {str(k): int(v) for k, v in events["period_end"].fillna("UNKNOWN").value_counts().items()}
    event_type_counts = {} if not len(events) else {str(k): int(v) for k, v in events["event_type"].value_counts().items()}
    decision = {
        "schema_version": "1.0.0",
        "status": "PASS" if success_ratio >= 0.95 else "DEGRADED_SOURCE_COVERAGE",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "notice_attempt_count": int(len(attempts)),
        "notice_provider_call_count": int(attempts["attempt_count"].sum() + attempts["empty_confirmation_attempted"].sum()),
        "notice_empty_confirmation_call_count": int(attempts["empty_confirmation_attempted"].sum()),
        "notice_recovered_slot_count": int(((attempts["attempt_count"] == 2) & success).sum()),
        "notice_unresolved_slot_count": int((~success).sum()),
        "notice_confirmed_empty_after_adapter_error_count": int(attempts["confirmed_empty_after_adapter_error"].sum()),
        "notice_source_success_ratio": success_ratio,
        "financial_event_count": int(len(events)),
        "affected_symbol_count": affected_symbols,
        "period_end_counts": period_counts,
        "event_type_counts": event_type_counts,
        "maximum_live_symbols_in_legacy_incremental": 8,
        "legacy_maximum_notice_lookback_days": 31,
        "recommended_catchup_mode": "BATCHED_CURSOR_CATCHUP" if affected_symbols > 8 or (end - start).days + 1 > 31 else "DIRECT_INCREMENTAL",
        "mutations": {"candidate_membership":0,"real_account":0,"simulation":0,"orders":0},
        "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
        "trade_authority": "NONE",
    }
    (output / "FINANCIAL_FILING_BACKLOG_DECISION.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
    return 0 if decision["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
