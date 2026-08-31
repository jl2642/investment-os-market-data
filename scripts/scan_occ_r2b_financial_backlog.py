from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Iterable

import akshare as ak
import pandas as pd

from scripts import fmdl3ebc_core as bc

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATEGORIES = ["财务报告", "信息变更"]


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


def fetch_notice_index(
    day: date,
    category: str,
    universe: set[str],
    *,
    max_attempts: int,
    initial_backoff_seconds: float,
    fetcher: Callable[..., pd.DataFrame] = ak.stock_notice_report,
) -> tuple[list[dict], dict]:
    frame = pd.DataFrame()
    error_type = None
    error_message = None
    attempt_count = 0
    state = "FAILED"
    for attempt in range(1, max_attempts + 1):
        attempt_count = attempt
        try:
            frame = fetcher(symbol=category, date=day.strftime("%Y%m%d"))
            state = (
                "SUCCESS_EMPTY"
                if not isinstance(frame, pd.DataFrame) or frame.empty
                else "SUCCESS"
            )
            error_type = None
            error_message = None
            break
        except Exception as exc:
            error_type = type(exc).__name__
            error_message = str(exc)[:300]
            if attempt < max_attempts:
                time.sleep(initial_backoff_seconds * attempt)
    normalized = normalize_notice_frame(
        frame, day=day, category=category, universe=universe
    )
    attempt_row = {
        "date": day.isoformat(),
        "category": category,
        "source_state": state,
        "attempt_count": attempt_count,
        "source_row_count": int(len(frame)) if isinstance(frame, pd.DataFrame) else 0,
        "financial_event_count": int(len(normalized)),
        "error_type": error_type,
        "error_message": error_message,
        "trade_authority": "NONE",
    }
    return normalized, attempt_row


def scan_live(
    start: date,
    end: date,
    universe: set[str],
    categories: list[str],
    *,
    max_attempts: int = 3,
    initial_backoff_seconds: float = 0.75,
    workers: int = 4,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    events: dict[str, dict] = {}
    attempts: list[dict] = []
    tasks = [(day, category) for day in daterange(start, end) for category in categories]
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(
                fetch_notice_index,
                day,
                category,
                universe,
                max_attempts=max_attempts,
                initial_backoff_seconds=initial_backoff_seconds,
            ): (day, category)
            for day, category in tasks
        }
        for future in as_completed(futures):
            normalized, attempt_row = future.result()
            for row in normalized:
                events[row["event_id"]] = row
            attempts.append(attempt_row)
    event_frame = pd.DataFrame(list(events.values()))
    if len(event_frame):
        event_frame = event_frame.sort_values(
            ["effective_at", "symbol", "event_id"]
        ).reset_index(drop=True)
    attempt_frame = pd.DataFrame(attempts)
    if len(attempt_frame):
        attempt_frame = attempt_frame.sort_values(["date", "category"]).reset_index(drop=True)
    return event_frame, attempt_frame


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--universe", default="outputs/current/DAILY_MARKET_SNAPSHOT.csv")
    parser.add_argument("--output-root", default="outputs/occ_r2/financial_backlog_audit")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--initial-backoff-seconds", type=float, default=0.75)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--fail-on-degraded", action="store_true")
    args = parser.parse_args()

    start = pd.Timestamp(args.start_date).date()
    end = pd.Timestamp(args.end_date).date()
    if end < start:
        raise SystemExit("END_BEFORE_START")
    universe_frame = pd.read_csv(ROOT / args.universe, encoding="utf-8-sig")
    universe = set(universe_frame["symbol"].dropna().astype(str))
    events, attempts = scan_live(
        start,
        end,
        universe,
        DEFAULT_CATEGORIES,
        max_attempts=max(1, args.max_attempts),
        initial_backoff_seconds=max(0.0, args.initial_backoff_seconds),
        workers=max(1, args.workers),
    )
    output = ROOT / args.output_root
    output.mkdir(parents=True, exist_ok=True)
    events.to_csv(output / "FINANCIAL_FILING_BACKLOG.csv", index=False, encoding="utf-8-sig")
    attempts.to_csv(output / "NOTICE_SCAN_ATTEMPTS.csv", index=False, encoding="utf-8-sig")

    success = attempts["source_state"].isin(["SUCCESS", "SUCCESS_EMPTY"])
    success_ratio = float(success.mean()) if len(attempts) else 0.0
    affected_symbols = int(events["symbol"].nunique()) if len(events) else 0
    period_counts = {} if not len(events) else {str(k): int(v) for k, v in events["period_end"].fillna("UNKNOWN").value_counts().items()}
    event_type_counts = {} if not len(events) else {str(k): int(v) for k, v in events["event_type"].value_counts().items()}
    complete = bool(len(attempts)) and success_ratio == 1.0
    failed_queries = attempts.loc[
        ~attempts["source_state"].isin(["SUCCESS", "SUCCESS_EMPTY"]),
        ["date", "category", "attempt_count", "error_type", "error_message"],
    ].to_dict("records")
    decision = {
        "schema_version": "1.1.0",
        "status": "PASS_COMPLETE_QUEUE" if complete else "DEGRADED_SOURCE_COVERAGE",
        "queue_complete": complete,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "notice_attempt_count": int(len(attempts)),
        "notice_source_success_ratio": success_ratio,
        "failed_notice_query_count": int(len(failed_queries)),
        "failed_notice_queries": failed_queries,
        "financial_event_count": int(len(events)),
        "affected_symbol_count": affected_symbols,
        "period_end_counts": period_counts,
        "event_type_counts": event_type_counts,
        "maximum_live_symbols_in_legacy_incremental": 8,
        "legacy_maximum_notice_lookback_days": 31,
        "recommended_catchup_mode": "BATCHED_CURSOR_CATCHUP" if affected_symbols > 8 or (end - start).days + 1 > 31 else "DIRECT_INCREMENTAL",
        "evidence_semantics": (
            "COMPLETE_BACKLOG_QUEUE"
            if complete
            else "PARTIAL_BACKLOG_EVIDENCE_DO_NOT_TREAT_AS_EXHAUSTIVE"
        ),
        "mutations": {"candidate_membership":0,"real_account":0,"simulation":0,"orders":0},
        "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
        "trade_authority": "NONE",
    }
    (output / "FINANCIAL_FILING_BACKLOG_DECISION.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
    if args.fail_on_degraded and not complete:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
